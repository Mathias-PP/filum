from __future__ import annotations

import io
import zipfile
from datetime import datetime
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client(db_session):
    from app.db.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def published_card(db_session, test_user):
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source
    from app.models.source_excerpt import SourceExcerpt

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="fiche-export",
        title="Fiche d'export, avec virgule",
        description="Une description",
        content_url="https://youtube.com/watch?v=abc",
        content_type="video",
        platform="youtube",
        status="published",
    )
    db_session.add(card)
    await db_session.flush()
    pivot_id = uuid4()
    db_session.add_all(
        [
            Source(
                id=pivot_id,
                biblio_card_id=card.id,
                position=0,
                url="https://example.org/paper",
                title="Titre {avec} accolades",
                authors="Dupont, Marie",
                published_at=datetime(2024, 3, 1),
                format="texte",
                category="article-scientifique",
                author_kind="chercheur",
                annotation='Note "importante"',
                is_pivot=True,
            ),
            Source(
                id=uuid4(),
                biblio_card_id=card.id,
                position=1,
                url="https://example.org/video",
                format="video",
                category="documentaire",
                author_kind="media",
            ),
        ]
    )
    await db_session.flush()
    db_session.add(
        SourceExcerpt(
            id=uuid4(),
            source_id=pivot_id,
            position=0,
            title="Le passage decisif",
            text="Les enfants de six ans montrent deja une inhibition mesurable.",
            anchor_prefix="Or, ",
            anchor_offset=1204,
        )
    )
    await db_session.commit()
    await db_session.refresh(card)
    return card


@pytest.mark.asyncio
async def test_export_json(client, published_card, test_user):
    resp = await client.get(f"/api/v1/@{test_user.username}/{published_card.slug}/export")
    assert resp.status_code == 200
    assert "attachment" in resp.headers["content-disposition"]
    data = resp.json()
    assert data["philum_export_version"] == 1
    assert data["card"]["title"] == published_card.title
    assert len(data["sources"]) == 2
    assert data["sources"][0]["is_pivot"] is True


@pytest.mark.asyncio
async def test_export_csv_has_bom_and_rows(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "csv"},
    )
    assert resp.status_code == 200
    raw = resp.content.decode("utf-8")
    assert raw.startswith("\ufeff")
    lines = [line for line in raw.lstrip("\ufeff").splitlines() if line]
    assert len(lines) == 3  # header + 2 sources
    assert lines[0].startswith("position,reference,title,authors,url")


@pytest.mark.asyncio
async def test_le_style_de_citation_traverse_tous_les_formats(client, published_card, test_user):
    """Chaque format porte la reference formatee, dans une place qui a du sens.

    L'exigence : choisir « Harvard » doit changer ce que l'utilisateur voit,
    que le fichier soit un JSON, un CSV, un Markdown, un DOCX ou un fichier
    de gestionnaire de references. Avant, seul le txt honorait le style ;
    les autres formats ignoraient silencieusement le choix. Ce test fige la
    presence de la reference stylee dans chaque format, sous la forme qui
    lui est propre.
    """
    base = f"/api/v1/@{test_user.username}/{published_card.slug}/export"

    # Harvard rend « Dupont, M. » (initiale sans espace) et « (2024) ».
    # APA rendrait « Dupont, M. (2024). » : signature differente.
    # Testons les deux pour prouver que le style change bien le contenu.

    async def contenu(params):
        r = await client.get(base, params=params)
        assert r.status_code == 200
        return r

    # JSON : champ `reference` par source, champ `citation_style` en tete.
    r = await contenu({"format": "json", "style": "harvard"})
    data = r.json()
    assert data["citation_style"] == "harvard"
    assert data["sources"][0]["reference"].startswith("Dupont, M. (2024)")

    r = await contenu({"format": "json", "style": "apa"})
    assert r.json()["sources"][0]["reference"].startswith("Dupont, M. (2024).")

    # Philum JSON-LD : `philum:formattedReference` par source.
    r = await contenu({"format": "philum", "style": "chicago"})
    data = r.json()
    assert data["philum:citationStyle"] == "chicago"
    assert "Dupont" in data["citation"][0]["philum:formattedReference"]

    # CSV : colonne `reference` en 2e position.
    r = await contenu({"format": "csv", "style": "harvard"})
    raw = r.content.decode("utf-8").lstrip("﻿")
    header = raw.splitlines()[0].split(",")
    assert header[1] == "reference"
    # La ligne pivot commence par « 0, », suivie de la reference Harvard.
    assert "Dupont, M. (2024)" in raw

    # Markdown : ligne italique sous le lien.
    r = await contenu({"format": "markdown", "style": "mla"})
    assert "MLA 9" in r.text
    assert "Dupont, Marie" in r.text  # MLA ecrit « Famille, Prenom »

    # DOCX : la reference formatee vit dans le XML du document.
    r = await contenu({"format": "docx", "style": "vancouver"})
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        doc = zf.read("word/document.xml").decode("utf-8")
    assert "Vancouver" in doc
    # Vancouver n'utilise pas la virgule apres la famille : « Dupont M ».
    assert "Dupont M" in doc

    # XLSX : la colonne reference est ecrite dans la premiere feuille.
    r = await contenu({"format": "xlsx", "style": "ieee"})
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    # IEEE ecrit les initiales en premier : « M. Dupont ».
    assert "M. Dupont" in sheet

    # BibTeX : le style se retrouve dans le champ `annote`.
    r = await contenu({"format": "bibtex", "style": "harvard"})
    assert "annote = {Reference formatee (harvard)" in r.text
    assert "Dupont, M. (2024)" in r.text

    # RIS : le style se retrouve dans le champ `N1`.
    r = await contenu({"format": "ris", "style": "chicago"})
    assert "N1  - Reference formatee (chicago)" in r.text

    # CSL-JSON : le style se retrouve dans le champ `note`.
    r = await contenu({"format": "csl", "style": "mla"})
    items = r.json()
    assert any("Reference formatee (mla)" in item.get("note", "") for item in items)

    # Le txt continue de rendre la bibliographie entiere dans le style demande.
    r = await contenu({"format": "txt", "style": "vancouver"})
    assert "(Vancouver)" in r.text or "Vancouver" in r.text
    assert "Dupont M" in r.text


@pytest.mark.asyncio
async def test_un_style_inconnu_est_refuse(client, published_card, test_user):
    """Le message dit la liste : un utilisateur qui tape mal peut lire ce
    qu'il aurait du ecrire, plutot que d'ecran neutre."""
    r = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "style": "bluebook"},
    )
    assert r.status_code == 422
    assert "apa" in r.text


@pytest.mark.asyncio
async def test_export_bibtex(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "bibtex"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "@article{" in body  # article-scientifique
    assert "@misc{" in body  # documentaire
    assert "Titre \\{avec\\} accolades" in body
    assert "year = {2024}" in body


@pytest.mark.asyncio
async def test_export_markdown_frontmatter(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "markdown"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert body.startswith("---\n")
    assert "tags:" in body
    assert "## Sources" in body
    assert "[Titre {avec} accolades](https://example.org/paper)" in body


@pytest.mark.asyncio
async def test_export_xlsx_is_valid_zip(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "xlsx"},
    )
    assert resp.status_code == 200
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "[Content_Types].xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "Titre {avec} accolades" in sheet
        assert 'r="A3"' in sheet  # 2e source presente


@pytest.mark.asyncio
async def test_export_docx_is_valid_zip(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "docx"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-disposition"].endswith('.docx"')
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        names = zf.namelist()
        assert "[Content_Types].xml" in names
        assert "word/document.xml" in names
        doc = zf.read("word/document.xml").decode("utf-8")
        assert "Titre {avec} accolades" in doc
        assert "(source pivot)" in doc
        assert "https://example.org/video" in doc


@pytest.mark.asyncio
async def test_export_csl_json(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "csl"},
    )
    assert resp.status_code == 200
    items = resp.json()
    assert isinstance(items, list) and len(items) == 2
    assert items[0]["type"] in {"article-journal", "webpage", "motion_picture"}
    assert items[0]["URL"].startswith("http")


@pytest.mark.asyncio
async def test_export_apa_text(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "apa"},
    )
    assert resp.status_code == 200
    body = resp.text
    # L'en-tete nomme le style : une bibliographie collee dans un document
    # perd sinon la trace de la convention qui l'a produite.
    assert body.startswith("Bibliographie (APA 7) —")
    assert "https://" in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("style", "libelle"),
    [
        ("harvard", "Harvard"),
        ("mla", "MLA 9"),
        ("chicago", "Chicago (auteur-date)"),
        ("vancouver", "Vancouver"),
        ("ieee", "IEEE"),
    ],
)
async def test_export_chaque_style_de_citation(client, published_card, test_user, style, libelle):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": style},
    )
    assert resp.status_code == 200
    assert resp.text.startswith(f"Bibliographie ({libelle}) —")
    assert "https://" in resp.text
    assert resp.headers["content-disposition"].endswith(f'.{style}.txt"')


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("style", "libelle"),
    [
        ("apa", "APA 7"),
        ("harvard", "Harvard"),
        ("mla", "MLA 9"),
        ("chicago", "Chicago (auteur-date)"),
        ("vancouver", "Vancouver"),
        ("ieee", "IEEE"),
    ],
)
async def test_export_txt_avec_style_explicite(client, published_card, test_user, style, libelle):
    """Le nouveau contrat : `format=txt&style=X`. L'utilisateur choisit d'abord
    le format de fichier (texte), puis le style de citation. C'est deux axes
    distincts, pas une soupe unique."""
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "txt", "style": style},
    )
    assert resp.status_code == 200
    assert resp.text.startswith(f"Bibliographie ({libelle}) —")
    assert resp.headers["content-disposition"].endswith(f'.{style}.txt"')


@pytest.mark.asyncio
async def test_export_txt_sans_style_prend_apa_par_defaut(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "txt"},
    )
    assert resp.status_code == 200
    assert resp.text.startswith("Bibliographie (APA 7) —")
    assert resp.headers["content-disposition"].endswith('.apa.txt"')


@pytest.mark.asyncio
async def test_export_style_inconnu_est_refuse_clairement(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "txt", "style": "papyrus"},
    )
    assert resp.status_code == 422
    body = resp.json()
    detail = body.get("detail") or body.get("error") or {}
    assert detail.get("code") == "validation_error"
    assert "papyrus" in detail.get("message", "")


@pytest.mark.asyncio
async def test_export_style_ignore_par_les_formats_de_donnees(client, published_card, test_user):
    """Passer `style=harvard` sur `format=json` n'est pas une erreur : les
    formats structures ont leur propre grammaire (ils portent les donnees
    brutes), le style n'a rien a y faire. L'ignorer silencieusement evite
    de casser des liens qui melangeraient les deux."""
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "style": "harvard"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_export_complet_par_defaut_porte_les_extraits(client, published_card, test_user):
    """Sans `include`, l'export est complet — extraits compris.

    Les extraits n'apparaissaient dans aucun format avant le perimetre : c'est
    pourtant le verbatim qui relie une affirmation a sa source, donc la piece la
    plus specifique a Philum.
    """
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "markdown"},
    )
    assert resp.status_code == 200
    assert "Les enfants de six ans" in resp.text
    assert "Le passage decisif" in resp.text


@pytest.mark.asyncio
async def test_export_include_vide_donne_la_bibliographie_seule(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "markdown", "include": ""},
    )
    assert resp.status_code == 200
    body = resp.text
    # Les references restent : le perimetre choisit ce qu'on ajoute autour.
    assert "[Titre {avec} accolades](https://example.org/paper)" in body
    assert "Les enfants de six ans" not in body
    assert 'Note "importante"' not in body
    assert "## Fiabilité des sources" not in body


@pytest.mark.asyncio
async def test_export_json_selection_partielle(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "include": "excerpts"},
    )
    assert resp.status_code == 200
    source = resp.json()["sources"][0]
    assert source["excerpts"][0]["anchor"]["offset"] == 1204
    assert "annotation" not in source
    assert "archive_url" not in source


@pytest.mark.asyncio
async def test_export_section_inconnue_422(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "include": "fiches-connectees"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_bibtex_ignore_le_perimetre(client, published_card, test_user):
    """Un format bibliographique obeit a sa convention, pas au perimetre.

    Y glisser un extrait produirait un `.bib` que Zotero refuserait.
    """
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "bibtex", "include": ""},
    )
    assert resp.status_code == 200
    assert "@article{" in resp.text


@pytest.mark.asyncio
async def test_export_unknown_format_422(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "odt"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_export_404_on_draft_card(client, db_session, test_user):
    from app.models.biblio_card import BiblioCard

    card = BiblioCard(
        id=uuid4(),
        user_id=test_user.id,
        slug="brouillon",
        title="Brouillon",
        content_type="video",
        platform="youtube",
        status="draft",
    )
    db_session.add(card)
    await db_session.commit()
    resp = await client.get(f"/api/v1/@{test_user.username}/brouillon/export")
    assert resp.status_code == 404


@pytest_asyncio.fixture
async def chaine_de_fiches(db_session, test_user, published_card):
    """D -> fiche -> B -> C.

    « D cite la fiche », « la fiche cite B », « B cite C ». De quoi verifier
    qu'un export sait distinguer sa posterite (D) de ses fondations (B, C), et
    que le degre 2 descendant atteint bien C sans passer par D.
    """
    from app.models.biblio_card import BiblioCard
    from app.models.source import Source

    def _fiche(slug, titre):
        return BiblioCard(
            id=uuid4(),
            user_id=test_user.id,
            slug=slug,
            title=titre,
            content_type="video",
            platform="youtube",
            status="published",
            visibility="public",
        )

    b, c, d = _fiche("fiche-b", "Fiche B"), _fiche("fiche-c", "Fiche C"), _fiche("fiche-d", "D")
    db_session.add_all([b, c, d])
    await db_session.flush()

    def _lien(depuis, vers, titre):
        return Source(
            id=uuid4(),
            biblio_card_id=depuis.id,
            position=9,
            url=f"https://philum.example/@x/{titre}",
            title=titre,
            format="texte",
            category="article-scientifique",
            author_kind="chercheur",
            linked_card_id=vers.id,
        )

    db_session.add_all(
        [
            _lien(published_card, b, "vers-b"),
            _lien(b, c, "vers-c"),
            _lien(d, published_card, "vers-la-fiche"),
            # C doit porter une reference ordinaire : sans elle, le test du
            # perimetre par degre passerait au vert sur une liste vide.
            Source(
                id=uuid4(),
                biblio_card_id=c.id,
                position=0,
                url="https://example.org/fond",
                title="Une source de C",
                format="texte",
                category="article-scientifique",
                author_kind="chercheur",
                archive_url="https://web.archive.org/x",
            ),
        ]
    )
    await db_session.commit()
    return {"b": b, "c": c, "d": d}


@pytest.mark.asyncio
async def test_les_deux_sens_ne_se_melangent_pas(
    client, published_card, test_user, chaine_de_fiches
):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "cited": "1", "citing": "1"},
    )
    assert resp.status_code == 200
    voisins = resp.json()["connected_cards"]
    assert [v["title"] for v in voisins["cited"]] == ["Fiche B"]
    assert [v["title"] for v in voisins["citing"]] == ["D"]


@pytest.mark.asyncio
async def test_le_degre_2_descendant_atteint_la_fiche_citee_par_la_citee(
    client, published_card, test_user, chaine_de_fiches
):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "cited": "2"},
    )
    assert resp.status_code == 200
    cites = resp.json()["connected_cards"]["cited"]
    assert {(v["title"], v["degree"]) for v in cites} == {("Fiche B", 1), ("Fiche C", 2)}


@pytest.mark.asyncio
async def test_un_perimetre_par_degre(client, published_card, test_user, chaine_de_fiches):
    """Le degre 1 complet, le degre 2 en references seules."""
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "cited": "1:archives|2:"},
    )
    assert resp.status_code == 200
    par_degre = {v["degree"]: v for v in resp.json()["connected_cards"]["cited"]}
    assert "archive_url" in par_degre[1]["sources"][0]
    assert "archive_url" not in par_degre[2]["sources"][0]


@pytest.mark.asyncio
async def test_sans_demande_aucune_cle_de_voisinage(client, published_card, test_user):
    """Pas de voisinage vide : ne pas chercher n'est pas ne rien trouver."""
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json"},
    )
    assert "connected_cards" not in resp.json()


@pytest.mark.asyncio
async def test_le_markdown_nomme_les_deux_sens(client, published_card, test_user, chaine_de_fiches):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "markdown", "cited": "1", "citing": "1"},
    )
    assert resp.status_code == 200
    body = resp.text
    assert "## Fiches citées par celle-ci" in body
    assert "## Fiches qui citent celle-ci" in body


@pytest.mark.asyncio
async def test_degre_hors_bornes_422(client, published_card, test_user):
    resp = await client.get(
        f"/api/v1/@{test_user.username}/{published_card.slug}/export",
        params={"format": "json", "cited": "9"},
    )
    assert resp.status_code == 422
