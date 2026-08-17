from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1.endpoints.excerpts import verify_quote

PAGE_TEXT = (
    "Introduction. La mémoire à long terme requiert la synthèse de nouvelles "
    "protéines et un remodelage durable des connexions synaptiques. "
    "Par ailleurs, le sommeil joue un rôle actif dans la consolidation."
)


def test_verify_quote_exact():
    m = verify_quote(PAGE_TEXT, "le sommeil joue un rôle actif")
    assert m is not None
    assert PAGE_TEXT[m.start() : m.end()] == "le sommeil joue un rôle actif"


def test_verify_quote_whitespace_tolerant():
    m = verify_quote(PAGE_TEXT, "la synthèse   de\nnouvelles protéines")
    assert m is not None


def test_verify_quote_rejects_hallucination():
    assert verify_quote(PAGE_TEXT, "les neurones miroirs expliquent l'empathie") is None
    assert verify_quote(PAGE_TEXT, "court") is None


@pytest_asyncio.fixture
async def client(db_session, test_user):
    from app.api.v1.endpoints.sources import get_current_user
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    async def override_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def source(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-test",
        title="Fiche test",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.flush()
    src = Source(
        biblio_card_id=card.id,
        position=1,
        url="https://example.org/article",
        title="Un article",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
    )
    db_session.add(src)
    await db_session.commit()
    await db_session.refresh(src)
    return src


@pytest.mark.asyncio
async def test_create_and_delete_excerpt(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Une citation importante.", "suggested_by_ai": True},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "Une citation importante."
    assert body["suggested_by_ai"] is True
    assert body["position"] == 1

    resp = await client.delete(f"/api/v1/sources/{source.id}/excerpts/{body['id']}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_unknown_excerpt_404(client, source):
    resp = await client.delete(f"/api/v1/sources/{source.id}/excerpts/{uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_suggest_verifies_quotes(client, source, monkeypatch):
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=PAGE_TEXT)

    async def fake_llm(page_text, context=None, existing_excerpts=None):
        return [
            "le sommeil joue un rôle actif dans la consolidation",
            "citation inventée qui n'apparaît nulle part dans le texte",
        ]

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.suggest_excerpts", fake_llm)

    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    body = resp.json()
    assert body["llm_enabled"] is True
    assert len(body["suggestions"]) == 1
    s = body["suggestions"][0]
    assert s["text"] == "le sommeil joue un rôle actif dans la consolidation"
    assert s["char_offset"] == PAGE_TEXT.index("le sommeil")
    assert "Par ailleurs" in s["context_before"]


@pytest.mark.asyncio
async def test_suggest_transmet_les_options_de_contexte_selon_les_cases(
    client, source, db_session, monkeypatch
):
    """Les cases a cocher orientent ce que le modele voit.

    Sans elles, un auteur ne pouvait ni empecher l'annotation de biaiser la
    selection, ni pousser le modele a couvrir d'autres passages que ceux
    deja pris. Le test fige que les trois flags de la requete atteignent le
    LLM sous la forme des trois arguments : contexte compose et liste
    d'extraits deja cites.
    """
    from app.extractors.url_extractor import ExtractedMetadata
    from app.models.biblio_card import BiblioCard
    from app.models.source_excerpt import SourceExcerpt

    card = await db_session.scalar(select(BiblioCard).where(BiblioCard.id == source.biblio_card_id))
    card.description = "Une video sur la memoire."
    source.annotation = "Le passage cle est en fin d'article."
    db_session.add(
        SourceExcerpt(
            source_id=source.id,
            position=1,
            text="le sommeil joue un rôle actif dans la consolidation",
        )
    )
    await db_session.commit()

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=PAGE_TEXT)

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)

    captures: dict = {}

    async def capture(page_text, context=None, existing_excerpts=None):
        captures["context"] = context
        captures["existing_excerpts"] = existing_excerpts
        return []

    monkeypatch.setattr("app.api.v1.endpoints.excerpts.suggest_excerpts", capture)

    # Tout coche : titre source + annotation + contexte fiche + extraits pris.
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    assert "Un article" in (captures["context"] or "")
    assert "Le passage cle" in captures["context"]
    assert "Une video sur la memoire" in captures["context"]
    assert captures["existing_excerpts"] and "le sommeil" in captures["existing_excerpts"][0]

    # Tout decoche : plus rien que le titre de la source.
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/suggest",
        json={
            "include_source_annotation": False,
            "include_existing_excerpts": False,
            "include_card_context": False,
        },
    )
    assert resp.status_code == 200
    assert captures["context"] == "Un article"
    assert captures["existing_excerpts"] is None


@pytest.mark.asyncio
async def test_suggest_llm_disabled(client, source, monkeypatch):
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=PAGE_TEXT)

    async def no_llm(page_text, context=None, existing_excerpts=None):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.suggest_excerpts", no_llm)

    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    assert resp.json() == {
        "suggestions": [],
        "page_text_length": len(PAGE_TEXT),
        "llm_enabled": False,
        "access_blocked": False,
    }


@pytest.mark.asyncio
async def test_suggest_une_page_illisible_est_un_etat_pas_une_erreur(client, source, monkeypatch):
    """Mesure du 2026-08-08 : cinq URLs sur dix ne rendent aucun texte.

    Le `422` d'origine arretait la fonctionnalite a la porte, alors que la
    personne a le texte sous les yeux et peut le coller. Une reponse vide
    laisse l'ecran basculer sur le mode de collage.
    """

    async def fake_scrape(url):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/suggest")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []
    assert resp.json()["page_text_length"] == 0
    # Et l'etat annonce est celui du serveur, pas un `True` de commodite :
    # sans modele configure, dire l'inverse ferait afficher « aucun passage
    # citable repere » pour une absence de modele.
    assert resp.json()["llm_enabled"] is False


@pytest.mark.asyncio
async def test_chunk_du_texte_colle_ne_touche_pas_au_reseau(client, source, monkeypatch):
    """Le collage est le seul chemin qui marche derriere un anti-crawler."""

    async def fake_scrape(url):  # pragma: no cover - ne doit pas etre appele
        raise AssertionError("le collage ne doit rien aller chercher")

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    texte = (
        "La memoire de travail retient une information brievement. "
        "Elle ne dure que quelques secondes. Baddeley en a propose un modele."
    )
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/chunk",
        json={"text": texte, "unit": "mots", "size": 8},
    )
    assert resp.status_code == 200
    corps = resp.json()
    assert corps["text_source"] == "pasted"
    assert corps["chunks"]
    for c in corps["chunks"]:
        assert c["text"] in texte
        assert corps["text"][c["start"] : c["end"]] == c["text"]


@pytest.mark.asyncio
async def test_chunk_sur_page_illisible_rend_un_decoupage_vide(client, source, monkeypatch):
    async def fake_scrape(url):
        return None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/chunk", json={})
    assert resp.status_code == 200
    assert resp.json()["text_source"] == "none"
    assert resp.json()["chunks"] == []


@pytest.mark.asyncio
async def test_un_extrait_peut_porter_un_intitule(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Elle ne dure que quelques secondes.", "title": "Duree de retention"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Duree de retention"


@pytest.mark.asyncio
async def test_un_extrait_sans_intitule_reste_sans_intitule(client, source):
    """Une chaine vide n'est pas un intitule : elle ne doit pas s'enregistrer."""
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Elle ne dure que quelques secondes.", "title": "   "},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] is None


# --- Verification : l'extrait est-il encore dans la source ? ----------------
#
# Sans cette passe, une fiche affirme qu'une source dit quelque chose sans que
# rien ne l'ait jamais confirme. Les quatre etats sont distincts a dessein :
# confondre « la page ne se laisse pas lire » avec « le passage n'y est pas »
# ferait passer une source inaccessible pour une citation inventee.


async def _ajouter(client, source, texte: str) -> str:
    debut = PAGE_TEXT.index(texte)
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={
            "text": texte,
            "anchor_prefix": PAGE_TEXT[max(0, debut - 48) : debut],
            "anchor_suffix": PAGE_TEXT[debut + len(texte) : debut + len(texte) + 48],
            "anchor_offset": debut,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _page(monkeypatch, texte: str | None):
    from app.extractors.url_extractor import ExtractedMetadata

    async def fake_scrape(url):
        return ExtractedMetadata(page_text=texte) if texte is not None else None

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", fake_scrape)
    monkeypatch.setattr("app.api.v1.endpoints.excerpts.assert_url_is_safe", lambda url: None)


@pytest.mark.asyncio
async def test_les_selecteurs_sont_persistes(client, source, db_session):
    """Sans eux, un extrait ne se retrouve qu'au mot pres."""
    from sqlalchemy import select

    from app.models.source_excerpt import SourceExcerpt

    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    stored = await db_session.scalar(select(SourceExcerpt).where(SourceExcerpt.id == UUID(eid)))
    assert stored.anchor_offset == PAGE_TEXT.index("le sommeil joue un rôle actif")
    assert stored.anchor_prefix.endswith("Par ailleurs, ")
    assert stored.anchor_suffix.startswith(" dans la consolidation")


@pytest.mark.asyncio
async def test_un_extrait_sans_selecteurs_reste_acceptable(client, source):
    """Une saisie a la main n'a pas de voisinage. C'est un fait, pas une erreur."""
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "Une citation saisie a la main."},
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_un_extrait_intact_est_retrouve(client, source, monkeypatch):
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, PAGE_TEXT)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    assert resp.status_code == 200
    (check,) = resp.json()["checks"]
    assert check["excerpt_id"] == eid
    assert check["status"] == "found"
    assert PAGE_TEXT[check["start"] : check["end"]] == "le sommeil joue un rôle actif"


@pytest.mark.asyncio
async def test_une_page_remaniee_retrouve_quand_meme_l_extrait(client, source, monkeypatch):
    """Un paragraphe ajoute en tete rend l'offset faux, pas l'extrait absent."""
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, "Mise à jour de la rédaction, mars 2026. " + PAGE_TEXT)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    (check,) = resp.json()["checks"]
    assert check["status"] == "found"


@pytest.mark.asyncio
async def test_un_extrait_dont_la_source_a_change_est_signale(client, source, monkeypatch):
    """« Toujours la, mais plus dans ces mots » n'est ni « verifie » ni « absent »."""
    await _ajouter(client, source, "le sommeil joue un rôle actif dans la consolidation")
    _page(monkeypatch, PAGE_TEXT.replace("un rôle actif", "un rôle actif et central"))
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    (check,) = resp.json()["checks"]
    assert check["status"] == "moved"


@pytest.mark.asyncio
async def test_un_extrait_absent_est_dit_absent(client, source, monkeypatch):
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, "Les abeilles butinent selon un trajet optimisé par la colonie.")
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    (check,) = resp.json()["checks"]
    assert check["status"] == "missing"


@pytest.mark.asyncio
async def test_une_page_illisible_n_accuse_personne(client, source, monkeypatch):
    """Cinq URLs sur dix ne rendent aucun texte : « on ne sait pas » se dit."""
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, None)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    (check,) = resp.json()["checks"]
    assert check["status"] == "unreadable"
    assert check["start"] is None


# --- Le texte fourni : ce qui debloque les pages qui ne rendent rien --------
#
# Un extrait qui reste « on ne sait pas » a vie n'est pas verifiable. Quand la
# page se derobe, c'est l'auteur·ice qui fournit le texte de la source ; la
# reponse dit d'ou vient ce texte, parce qu'une relecture contre un texte
# fourni ne vaut pas la meme chose qu'une relecture contre la page publique.


@pytest.mark.asyncio
async def test_un_texte_fourni_debloque_une_page_muette(client, source, monkeypatch):
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, None)
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/verify", json={"text": PAGE_TEXT}
    )
    assert resp.status_code == 200
    corps = resp.json()
    assert corps["text_source"] == "provided"
    (check,) = corps["checks"]
    assert check["status"] == "found"


@pytest.mark.asyncio
async def test_le_texte_fourni_ne_touche_pas_au_reseau(client, source, monkeypatch):
    """Sinon on paierait un aller-retour pour un texte qu'on a deja."""
    await _ajouter(client, source, "le sommeil joue un rôle actif")

    async def interdit(url):  # pragma: no cover - ne doit pas etre appele
        raise AssertionError("la page ne doit pas etre recuperee")

    monkeypatch.setattr("app.extractors.url_extractor._html_scrape", interdit)
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/verify", json={"text": PAGE_TEXT}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_sans_texte_fourni_la_page_reste_la_reference(client, source, monkeypatch):
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, PAGE_TEXT)
    resp = await client.post(f"/api/v1/sources/{source.id}/excerpts/verify", json={"text": ""})
    assert resp.json()["text_source"] == "fetched"


# --- Le document depose ------------------------------------------------------
#
# Un chapitre ne se colle pas. Ce qui se joue ici n'est pas le confort : c'est
# la difference entre un decoupage possible et une source dont on renonce a
# tirer le moindre extrait.


def _docx(paragraphes: list[str]) -> bytes:
    import io
    import zipfile

    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    corps = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphes)
    xml = f'<?xml version="1.0"?><w:document {ns}><w:body>{corps}</w:body></w:document>'
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return tampon.getvalue()


@pytest.mark.asyncio
async def test_un_docx_depose_donne_un_decoupage(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/chunk-file",
        files={"file": ("chapitre.docx", _docx([PAGE_TEXT]), "application/octet-stream")},
        data={"unit": "caracteres", "size": "80"},
    )
    assert resp.status_code == 200, resp.text
    corps = resp.json()
    assert corps["text_source"] == "uploaded"
    assert corps["chunks"]
    assert "sommeil" in corps["text"]


@pytest.mark.asyncio
async def test_un_document_illisible_dit_quoi_faire(client, source):
    """Un « erreur 422 » nu laisserait l'auteur·ice sans prochaine action."""
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/chunk-file",
        files={"file": ("photo.png", b"\x89PNG...", "image/png")},
    )
    assert resp.status_code == 422, resp.text
    corps = resp.json()["error"]
    assert corps["code"] == "unreadable_document"
    assert "Formats acceptés" in corps["message"]


@pytest.mark.asyncio
async def test_un_document_depose_sur_une_source_dautrui_est_refuse(client):
    resp = await client.post(
        f"/api/v1/sources/{uuid4()}/excerpts/chunk-file",
        files={"file": ("n.txt", b"texte", "text/plain")},
    )
    assert resp.status_code == 404


# --- Le verdict garde, pour que le lecteur puisse le lire -------------------
#
# Le verdict de relecture ne vivait que le temps de la reponse HTTP. La fiche
# publique affichait ensuite la citation nue : rien n'y distinguait un passage
# relu ce matin d'un passage jamais verifie. C'est pourtant cette distinction
# que Philum existe pour rendre visible ; la garder pour soi revient a demander
# au lecteur de croire sur parole.


async def _relire(db_session, excerpt_id):
    from app.models.source_excerpt import SourceExcerpt

    return await db_session.get(SourceExcerpt, UUID(excerpt_id))


@pytest.mark.asyncio
async def test_un_extrait_neuf_n_est_pas_dit_verifie(client, source, db_session):
    """`None` est un etat a afficher, pas un vide a combler."""
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    extrait = await _relire(db_session, eid)
    assert extrait.verified_at is None
    assert extrait.verified_status is None


@pytest.mark.asyncio
async def test_la_relecture_laisse_sa_trace(client, source, db_session, monkeypatch):
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, PAGE_TEXT)
    await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    extrait = await _relire(db_session, eid)
    assert extrait.verified_status == "found"
    assert extrait.verified_at is not None
    assert extrait.verified_text_source == "fetched"


@pytest.mark.asyncio
async def test_le_verdict_dit_contre_quoi_il_a_ete_rendu(client, source, db_session, monkeypatch):
    """Relu contre un texte fourni n'engage pas ce qu'engage la page publique."""
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, None)
    await client.post(
        f"/api/v1/sources/{source.id}/excerpts/verify",
        json={"text": PAGE_TEXT},
    )
    extrait = await _relire(db_session, eid)
    assert extrait.verified_status == "found"
    assert extrait.verified_text_source == "provided"


@pytest.mark.asyncio
async def test_une_source_illisible_se_garde_aussi(client, source, db_session, monkeypatch):
    """« On ne sait pas » est une information : elle doit survivre a la reponse."""
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, None)
    await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    extrait = await _relire(db_session, eid)
    assert extrait.verified_status == "unreadable"
    assert extrait.verified_at is not None


@pytest.mark.asyncio
async def test_un_extrait_disparu_reste_marque_disparu(client, source, db_session, monkeypatch):
    eid = await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, "Les abeilles butinent selon un trajet optimisé par la colonie.")
    await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    extrait = await _relire(db_session, eid)
    assert extrait.verified_status == "missing"


@pytest.mark.asyncio
async def test_le_verdict_part_avec_la_fiche_publique(client, source, monkeypatch):
    """Sans cela, tout ce travail resterait invisible du seul qui en a besoin."""
    await _ajouter(client, source, "le sommeil joue un rôle actif")
    _page(monkeypatch, PAGE_TEXT)
    await client.post(f"/api/v1/sources/{source.id}/excerpts/verify")
    resp = await client.get(f"/api/v1/sources?card_id={source.biblio_card_id}")
    assert resp.status_code == 200
    (extrait,) = resp.json()[0]["excerpts"]
    assert extrait["verified_status"] == "found"
    assert extrait["verified_text_source"] == "fetched"
    assert extrait["verified_at"] is not None


# --- Mise en situation d'un passage ---------------------------------------
#
# Un extrait voyage seul : export, reponse MCP, moteur. La phrase de mise en
# situation lui rend les reperes que son document portait pour lui. Elle
# cotoie donc du verbatim, d'ou la regle que ces tests tiennent : elle reste
# un champ a part, et son origine se sait.


@pytest.mark.asyncio
async def test_la_mise_en_situation_ne_se_recolle_pas_dans_la_citation(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={
            "text": "le sommeil joue un rôle actif",
            "context": "Extrait d'une revue sur la consolidation mnésique.",
            "title": "Rôle du sommeil",
        },
    )
    assert resp.status_code == 201
    corps = resp.json()
    # La citation doit rester exactement ce que la source dit.
    assert corps["text"] == "le sommeil joue un rôle actif"
    assert corps["context"] == "Extrait d'une revue sur la consolidation mnésique."


@pytest.mark.asyncio
async def test_l_origine_de_l_annotation_se_sait(client, source):
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "le sommeil joue un rôle actif", "annotated_by_ai": True},
    )
    assert resp.json()["annotated_by_ai"] is True


@pytest.mark.asyncio
async def test_un_passage_sans_annotation_reste_sans_annotation(client, source):
    # Rien ne doit combler ces champs par defaut : une mise en situation
    # inventee ferait dire au passage ce qu'il ne dit pas.
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts", json={"text": "le sommeil joue un rôle actif"}
    )
    corps = resp.json()
    assert corps["context"] is None
    assert corps["annotated_by_ai"] is False


@pytest.mark.asyncio
async def test_la_mise_en_situation_part_avec_la_fiche_publique(client, source):
    await client.post(
        f"/api/v1/sources/{source.id}/excerpts",
        json={"text": "le sommeil joue un rôle actif", "context": "Revue sur la consolidation."},
    )
    resp = await client.get(f"/api/v1/sources?card_id={source.biblio_card_id}")
    (extrait,) = resp.json()[0]["excerpts"]
    assert extrait["context"] == "Revue sur la consolidation."


@pytest.mark.asyncio
async def test_sans_modele_annoter_le_dit_plutot_que_de_se_taire(client, source, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "litellm_base_url", "")
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/annotate", json={"text": "un passage"}
    )
    assert resp.status_code == 200
    corps = resp.json()
    # Sans ce drapeau, l'ecran lirait l'absence de modele comme un modele qui
    # n'a rien trouve, et donnerait la mauvaise cause a corriger.
    assert corps["llm_enabled"] is False
    assert corps["title"] is None and corps["context"] is None


@pytest.mark.asyncio
async def test_annoter_ne_persiste_rien(client, source, monkeypatch):
    from app.api.v1.endpoints import excerpts as module
    from app.core.config import get_settings
    from app.services.llm import LlmAnnotation

    monkeypatch.setattr(get_settings(), "litellm_base_url", "https://exemple.test")

    async def faux(passage, entourage=""):
        return LlmAnnotation(title="Rôle du sommeil", context="Revue sur la consolidation.")

    monkeypatch.setattr(module, "suggest_annotation", faux)
    resp = await client.post(
        f"/api/v1/sources/{source.id}/excerpts/annotate",
        json={"text": "le sommeil joue un rôle actif", "surrounding": PAGE_TEXT},
    )
    assert resp.json()["context"] == "Revue sur la consolidation."
    # La suggestion n'engage a rien : elle remplit un champ que l'auteur·ice
    # relit. Rien ne doit avoir ete cree en base.
    liste = await client.get(f"/api/v1/sources?card_id={source.biblio_card_id}")
    assert liste.json()[0]["excerpts"] == []
