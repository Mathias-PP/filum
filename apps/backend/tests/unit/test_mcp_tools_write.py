"""Une IA connectee au MCP fabrique une fiche complete de bout en bout.

Ces tools existent pour que le geste « je viens de lire un corpus, je te
laisse en tirer une fiche » puisse se faire depuis le protocole standard,
sans qu'un agent ait besoin de piloter un navigateur ou d'appeler l'API
REST par un autre chemin.

Ils partagent les invariants du REST (propriete, unicite, capacite) sans
les reimplementer : chaque fonction delegue au meme service metier.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import (
    add_excerpt,
    add_source,
    add_sources_batch,
    archive_sources,
    confirm_connection,
    create_card,
    create_claim_request,
    create_content_attestation,
    delete_card,
    delete_excerpt,
    delete_source,
    list_connections,
    list_deleted_cards,
    list_incoming_citations,
    list_my_cards,
    list_sources,
    mark_citations_seen,
    parse_biblio,
    publish_card,
    remove_connection,
    restore_card,
    search_my_excerpts,
    set_content_text,
    update_card,
    update_source,
    verify_excerpts,
)

#: Page servie a la place du web pendant ces tests. `add_excerpt` va desormais
#: relire la source avant d'ecrire : sans cette page, chaque test d'extrait
#: partirait telecharger `https://example.org/...`. Elle porte mot pour mot tous
#: les passages que ce fichier cite, pour que ces tests continuent d'eprouver ce
#: qu'ils eprouvent (position, garde-fous, propriete) et rien d'autre.
_PAGE_DE_TEST = """
La memoire n'est pas un enregistrement. Le protocole de re-consolidation
apres apprentissage etudie ici porte sur le sommeil lent. Cela ameliore la
memoire de 12 %. Cela ameliore la memoire declarative chez les participants
ayant beneficie d'une re-consolidation nocturne, comparativement au groupe
temoin sans re-consolidation.

Ce que la premiere source dit exactement. Un passage suffisamment long pour
passer le garde-fou. Le passage exact que la source contient. Une affirmation
precise avec le mot cle magique.
"""


@pytest.fixture(autouse=True)
def _source_lisible(monkeypatch):
    """Toute source repond `_PAGE_DE_TEST`, en entier et sans reseau."""
    from app.services import excerpt_insertion

    async def _page(_url: str | None) -> tuple[str, bool, bool]:
        return _PAGE_DE_TEST, False, True

    excerpt_insertion.vider_le_cache()
    monkeypatch.setattr(excerpt_insertion, "texte_de_page", _page)


@pytest.mark.asyncio
async def test_creer_une_fiche_donne_un_brouillon(db_session, test_user):
    result = await create_card(
        db_session,
        test_user,
        slug="ma-nouvelle-fiche",
        title="Ma nouvelle fiche",
        content_url="https://example.org/contenu",
    )
    assert result["creator"] == test_user.username
    assert result["slug"] == "ma-nouvelle-fiche"
    assert result["status"] == "draft"


@pytest.mark.asyncio
async def test_deux_fiches_avec_le_meme_slug_est_refuse(db_session, test_user):
    await create_card(db_session, test_user, slug="duplique", title="Premiere")
    with pytest.raises(ToolError, match="existe deja"):
        await create_card(db_session, test_user, slug="duplique", title="Seconde")


@pytest.mark.asyncio
async def test_un_slug_invalide_leve_un_message_lisible(db_session, test_user):
    with pytest.raises(ToolError):
        await create_card(db_session, test_user, slug="A", title="Trop court")


@pytest_asyncio.fixture
async def fiche_brouillon(db_session, test_user):
    return await create_card(
        db_session,
        test_user,
        slug="fiche-en-cours",
        title="Fiche en cours",
        content_url="https://example.org/video",
    )


@pytest.mark.asyncio
async def test_ajouter_une_source_la_lie_a_la_fiche(db_session, test_user, fiche_brouillon):
    result = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/article",
        title="Article cite",
        authors="Alice",
    )
    assert result["card_slug"] == "fiche-en-cours"
    assert result["position"] == 1
    result2 = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/autre",
        title="Autre article",
    )
    assert result2["position"] == 2


@pytest.mark.asyncio
async def test_ajouter_deux_fois_la_meme_source_est_refuse(db_session, test_user, fiche_brouillon):
    await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/article",
    )
    with pytest.raises(ToolError, match="deja"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            url="https://example.org/article",
        )


@pytest.mark.asyncio
async def test_meme_source_ecrite_differemment_est_refusee(db_session, test_user, fiche_brouillon):
    """Deux ecritures de la meme URL comptent comme une seule reference."""
    await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://www.example.org/article/",
    )
    with pytest.raises(ToolError, match="deja"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            url="http://example.org/article",
        )


@pytest.mark.asyncio
async def test_ajouter_une_source_a_la_fiche_d_autrui_est_refuse(db_session, test_user):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        google_id="autre-google",
        email="autre@example.org",
        username="autre",
        display_name="Autre",
        public_key="a" * 64,
        encrypted_private_key="k",
    )
    db_session.add(autre)
    await db_session.commit()
    await create_card(db_session, autre, slug="fiche-d-autrui", title="D'autrui")
    with pytest.raises(ToolError, match="Aucune fiche"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-d-autrui",
            url="https://example.org/x",
        )


@pytest.mark.asyncio
async def test_ajouter_un_extrait_le_marque_comme_ia(db_session, test_user, fiche_brouillon):
    source = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/article",
    )
    from sqlalchemy import select as _select

    from app.models.source_excerpt import SourceExcerpt

    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source["id"],
        text="La memoire n'est pas un enregistrement.",
        context="Chapitre sur la reconsolidation.",
    )
    assert result["position"] == 1
    ex = await db_session.scalar(
        _select(SourceExcerpt).where(SourceExcerpt.id == UUID_from_str(result["id"]))
    )
    assert ex.suggested_by_ai is True
    assert ex.annotated_by_ai is True
    assert ex.text == "La memoire n'est pas un enregistrement."


def UUID_from_str(s):
    from uuid import UUID

    return UUID(s)


@pytest.mark.asyncio
async def test_un_extrait_vide_est_refuse(db_session, test_user, fiche_brouillon):
    source = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://example.org/article"
    )
    with pytest.raises(ToolError, match="vide"):
        await add_excerpt(db_session, test_user, source_id=source["id"], text="   ")


@pytest.mark.asyncio
async def test_extrait_court_referentiel_sans_contexte_est_refuse(
    db_session, test_user, fiche_brouillon
):
    """« Cela ameliore la memoire » cite seul est un contresens : ce que
    « cela » nomme n'apparait nulle part. Le tool refuse pour forcer soit
    l'elargissement, soit une mise en situation."""
    source = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://example.org/x"
    )
    with pytest.raises(ToolError, match="referentiel"):
        await add_excerpt(
            db_session,
            test_user,
            source_id=source["id"],
            text="Cela ameliore la memoire de 12 %.",
        )


@pytest.mark.asyncio
async def test_extrait_court_referentiel_avec_contexte_passe(
    db_session, test_user, fiche_brouillon
):
    """La mise en situation nomme le referent en clair : le meme extrait
    devient utilisable pour un lecteur qui le rencontre isole."""
    source = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://example.org/y"
    )
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source["id"],
        text="Cela ameliore la memoire de 12 %.",
        context="Le protocole de re-consolidation apres apprentissage etudie ici, "
        "compare a un groupe temoin qui ne relit pas les mots.",
    )
    assert result["position"] == 1


@pytest.mark.asyncio
async def test_extrait_long_autonome_passe_sans_contexte(db_session, test_user, fiche_brouillon):
    """Au-dela de 15 mots, le passage porte son propre contexte lexical :
    le garde-fou ne mord plus, meme sans mise en situation."""
    source = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://example.org/z"
    )
    result = await add_excerpt(
        db_session,
        test_user,
        source_id=source["id"],
        text="Cela ameliore la memoire declarative chez les participants ayant "
        "beneficie d'une re-consolidation nocturne, comparativement au groupe "
        "temoin sans re-consolidation.",
    )
    assert result["position"] == 1


@pytest.mark.asyncio
async def test_ajouter_un_extrait_a_une_source_d_autrui_est_refuse(db_session, test_user):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        google_id="autre-google-2",
        email="autre2@example.org",
        username="autre2",
        display_name="Autre 2",
        public_key="b" * 64,
        encrypted_private_key="k",
    )
    db_session.add(autre)
    await db_session.commit()
    await create_card(db_session, autre, slug="fiche-etrangere", title="Etrangere")
    source = await add_source(
        db_session,
        autre,
        card_slug="fiche-etrangere",
        url="https://example.org/etranger",
    )
    with pytest.raises(ToolError, match="Aucune source"):
        await add_excerpt(db_session, test_user, source_id=source["id"], text="Contenu")


@pytest.mark.asyncio
async def test_publier_rend_la_fiche_visible(db_session, test_user, fiche_brouillon):
    result = await publish_card(db_session, test_user, slug="fiche-en-cours")
    assert result["status"] == "published"
    assert result["public_url"].endswith(f"/@{test_user.username}/fiche-en-cours")
    assert result["published_at"]


@pytest.mark.asyncio
async def test_publier_la_fiche_d_autrui_est_refuse(db_session, test_user):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        google_id="autre-google-3",
        email="autre3@example.org",
        username="autre3",
        display_name="Autre 3",
        public_key="c" * 64,
        encrypted_private_key="k",
    )
    db_session.add(autre)
    await db_session.commit()
    await create_card(db_session, autre, slug="a-publier", title="A publier")
    with pytest.raises(ToolError, match="Aucune fiche"):
        await publish_card(db_session, test_user, slug="a-publier")


@pytest.mark.asyncio
async def test_le_parcours_complet_produit_une_fiche_qu_un_agent_peut_relire(db_session, test_user):
    """Le geste que la PR existe pour rendre possible.

    Une IA cree la fiche, y colle deux sources dont une avec un extrait, puis
    publie. Apres, `search_cards` doit la trouver et `get_card` doit rendre
    ses sources.
    """
    from app.mcp_server.tools import get_card, search_cards

    await create_card(
        db_session,
        test_user,
        slug="parcours-complet",
        title="Parcours complet du MCP",
        description="Fiche produite par un agent pour valider la chaine.",
        # Une bibliographie sur une question, sans contenu source a documenter.
        card_kind="sujet",
    )
    s1 = await add_source(
        db_session,
        test_user,
        card_slug="parcours-complet",
        url="https://example.org/premiere-source",
        title="Premiere source",
        authors="Alice Martin",
    )
    await add_source(
        db_session,
        test_user,
        card_slug="parcours-complet",
        url="https://example.org/seconde-source",
        title="Seconde source",
    )
    await add_excerpt(
        db_session,
        test_user,
        source_id=s1["id"],
        text="Ce que la premiere source dit exactement.",
        context="Le passage decisif du papier, chapitre resultats.",
    )
    await publish_card(db_session, test_user, slug="parcours-complet")

    trouvees = await search_cards(db_session, query="parcours")
    assert any(f["slug"] == "parcours-complet" for f in trouvees)
    detail = await get_card(db_session, creator=test_user.username, slug="parcours-complet")
    assert detail is not None
    assert len(detail["sources"]) == 2


@pytest.mark.asyncio
async def test_set_content_text_sans_confirmation_est_refuse(
    db_session, test_user, fiche_brouillon
):
    """L'agent doit engager sa responsabilite : passer False refuse la pose
    avec un message qui dit ce qu'il faut faire."""
    with pytest.raises(ToolError, match="confirm_publication_rights"):
        await set_content_text(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            text="Texte a publier.",
            confirm_publication_rights=False,
        )


@pytest.mark.asyncio
async def test_set_content_text_pose_le_texte_sur_la_fiche(db_session, test_user, fiche_brouillon):
    from app.mcp_server.tools import get_card

    result = await set_content_text(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        text="Le texte integral du contenu.",
        confirm_publication_rights=True,
    )
    assert result["content_text_length"] == len("Le texte integral du contenu.")
    assert result["content_text_cleared"] is False
    # Publier pour verifier que le texte remonte sur la vue publique.
    await publish_card(db_session, test_user, slug="fiche-en-cours")
    detail = await get_card(db_session, creator=test_user.username, slug="fiche-en-cours")
    # get_card MCP renvoie une vue compacte : content_text est expose au meme
    # niveau que description quand il existe. Verifions plutot en BDD :
    from sqlalchemy import select as _select

    from app.models.biblio_card import BiblioCard

    card = await db_session.scalar(_select(BiblioCard).where(BiblioCard.slug == "fiche-en-cours"))
    assert card.content_text == "Le texte integral du contenu."
    # `detail` disponible pour un futur test si on ajoute content_text a get_card.
    assert detail is not None


@pytest.mark.asyncio
async def test_set_content_text_chaine_vide_efface_le_texte(db_session, test_user, fiche_brouillon):
    await set_content_text(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        text="Un texte.",
        confirm_publication_rights=True,
    )
    result = await set_content_text(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        text="",
        confirm_publication_rights=True,
    )
    assert result["content_text_cleared"] is True


@pytest.mark.asyncio
async def test_set_content_text_trop_long_est_refuse(db_session, test_user, fiche_brouillon):
    with pytest.raises(ToolError, match="Texte trop long"):
        await set_content_text(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            text="x" * 500_001,
            confirm_publication_rights=True,
        )


@pytest.mark.asyncio
async def test_set_content_text_fiche_d_autrui_est_refuse(db_session, test_user, fiche_brouillon):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        google_id="autre-google-ct",
        email="autrect@example.org",
        username="autrect",
        display_name="Autre CT",
        public_key="d" * 64,
        encrypted_private_key="k",
    )
    db_session.add(autre)
    await db_session.commit()
    with pytest.raises(ToolError, match="Aucune fiche"):
        await set_content_text(
            db_session,
            autre,
            card_slug="fiche-en-cours",
            text="Tentative.",
            confirm_publication_rights=True,
        )


# --- Mutations post-creation ------------------------------------------------
#
# Ces tests figent la parite MCP <-> UI cote mutations : un agent MCP-only
# doit pouvoir corriger sa fiche apres coup sans rebuild. Ils couvrent aussi
# le refus systematique d'un non-proprietaire, meme discretion que
# `_fiche_du_createur` (ne jamais reveler l'existence d'une ressource d'autrui).


@pytest_asyncio.fixture
async def autre_utilisateur(db_session):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        google_id="autre-google-mut",
        email="autremut@example.org",
        username="autremut",
        display_name="Autre Mut",
        public_key="e" * 64,
        encrypted_private_key="k",
    )
    db_session.add(autre)
    await db_session.commit()
    return autre


@pytest.mark.asyncio
async def test_update_card_corrige_titre_et_description(db_session, test_user, fiche_brouillon):
    result = await update_card(
        db_session,
        test_user,
        slug="fiche-en-cours",
        title="Nouveau titre",
        description="Nouvelle description",
    )
    assert result["title"] == "Nouveau titre"
    assert result["description"] == "Nouvelle description"


@pytest.mark.asyncio
async def test_update_card_champ_none_laisse_inchange(db_session, test_user, fiche_brouillon):
    await update_card(db_session, test_user, slug="fiche-en-cours", title="Titre A")
    result = await update_card(db_session, test_user, slug="fiche-en-cours", description="Descr B")
    assert result["title"] == "Titre A"
    assert result["description"] == "Descr B"


@pytest.mark.asyncio
async def test_update_card_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await update_card(db_session, autre_utilisateur, slug="fiche-en-cours", title="Hacked")


@pytest.mark.asyncio
async def test_update_source_pose_stance_et_annotation(db_session, test_user, fiche_brouillon):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
        title="Un article",
    )
    result = await update_source(
        db_session,
        test_user,
        source_id=src["id"],
        stance="appuie",
        annotation="Ce papier fige la mesure.",
        is_pivot=True,
    )
    assert result["stance"] == "appuie"
    assert result["annotation"] == "Ce papier fige la mesure."
    assert result["is_pivot"] is True


@pytest.mark.asyncio
async def test_add_source_pose_published_at(db_session, test_user, fiche_brouillon):
    """Une source sans date n'est pas une bibliographie : l'agent doit pouvoir
    poser l'annee (au minimum) des la creation. Defaut constate sur la fiche
    creatine (2026-08-21) : add_source n'exposait pas le champ, toutes les
    sources sont sorties sans date."""
    from app.models.source import Source

    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/efsa-2016",
        title="Scientific Opinion on creatine",
        published_at="2016",
    )
    lu = await db_session.get(Source, UUID(src["id"]))
    assert lu is not None and lu.published_at is not None
    assert lu.published_at.year == 2016


@pytest.mark.asyncio
async def test_add_source_deduit_l_url_du_doi(db_session, test_user, fiche_brouillon):
    """Un DOI seul laissait une source sans adresse, donc ni archivable ni relisible."""
    from app.models.source import Source

    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        doi="10.1038/nature12373",
        title="Sommeil et memoire",
    )
    lu = await db_session.get(Source, UUID(src["id"]))
    assert lu is not None
    assert lu.url == "https://doi.org/10.1038/nature12373"
    assert lu.doi == "10.1038/nature12373"


@pytest.mark.asyncio
async def test_add_source_url_explicite_prime_sur_le_doi(db_session, test_user, fiche_brouillon):
    """La deduction ne comble qu'une absence : une URL donnee n'est jamais ecrasee."""
    from app.models.source import Source

    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://www.nature.com/articles/nature12373",
        doi="10.1038/nature12373",
    )
    lu = await db_session.get(Source, UUID(src["id"]))
    assert lu is not None
    assert lu.url == "https://www.nature.com/articles/nature12373"


@pytest.mark.asyncio
async def test_add_source_pose_les_extraits_fournis(db_session, test_user, fiche_brouillon):
    """Les extraits inline evitent l'aller-retour par l'identifiant de la source."""
    from app.models.source_excerpt import SourceExcerpt

    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/memoire",
        excerpts=[
            {"text": "La memoire n'est pas un enregistrement.", "title": "Le point"},
            {"text": "Le passage exact que la source contient.", "context": "Conclusion"},
        ],
    )
    assert len(src["excerpts"]) == 2
    assert "excerpts_refuses" not in src
    assert all(e["verified_status"] == "found" for e in src["excerpts"])

    from sqlalchemy import select

    resultat = await db_session.execute(
        select(SourceExcerpt).where(SourceExcerpt.source_id == UUID(src["id"]))
    )
    assert len(resultat.scalars().all()) == 2


@pytest.mark.asyncio
async def test_add_source_dit_quels_extraits_ont_ete_refuses(
    db_session, test_user, fiche_brouillon
):
    """Un extrait refuse n'annule pas la source, mais il ne disparait pas non plus.

    Taire l'echec ferait annoncer a l'agent deux extraits poses la ou un seul
    l'est : exactement la fausse declaration que cette couche existe pour
    empecher.
    """
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/memoire",
        excerpts=[
            {"text": "La memoire n'est pas un enregistrement."},
            {
                "text": "Une phrase que cette page ne contient nulle part, inventee de toutes pieces."
            },
        ],
    )
    assert src["id"]
    assert len(src["excerpts"]) == 1
    assert len(src["excerpts_refuses"]) == 1
    assert src["excerpts_refuses"][0]["rang"] == "2"


@pytest.mark.asyncio
async def test_add_source_published_at_formats_souples(db_session, test_user, fiche_brouillon):
    from app.models.source import Source

    s_mois = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/format-mois",
        title="Article mois",
        published_at="2016-03",
    )
    s_jour = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/format-jour",
        title="Article jour",
        published_at="2016-03-15",
    )
    s_an = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/format-an",
        title="Article an",
        published_at="2016",
    )
    lu_mois = await db_session.get(Source, UUID(s_mois["id"]))
    lu_jour = await db_session.get(Source, UUID(s_jour["id"]))
    lu_an = await db_session.get(Source, UUID(s_an["id"]))
    assert lu_mois and lu_mois.published_at
    assert (lu_mois.published_at.year, lu_mois.published_at.month) == (2016, 3)
    assert lu_jour and lu_jour.published_at and lu_jour.published_at.day == 15
    assert lu_an and lu_an.published_at
    assert (
        lu_an.published_at.year,
        lu_an.published_at.month,
        lu_an.published_at.day,
    ) == (2016, 1, 1)


@pytest.mark.asyncio
async def test_add_source_published_at_illisible_refuse(db_session, test_user, fiche_brouillon):
    with pytest.raises(ToolError, match="format illisible"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            url="https://example.org/date-bizarre",
            title="Article",
            published_at="vers 2016",
        )


@pytest.mark.asyncio
async def test_update_source_efface_published_at_par_chaine_vide(
    db_session, test_user, fiche_brouillon
):
    from app.models.source import Source

    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/a-corrigee",
        title="Article date",
        published_at="2016-03-15",
    )
    await update_source(db_session, test_user, source_id=src["id"], published_at="")
    lu = await db_session.get(Source, UUID(src["id"]))
    assert lu is not None and lu.published_at is None


@pytest.mark.asyncio
async def test_update_source_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="Aucune source"):
        await update_source(db_session, autre_utilisateur, source_id=src["id"], stance="appuie")


@pytest.mark.asyncio
async def test_delete_source_marque_deleted_at(db_session, test_user, fiche_brouillon):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    result = await delete_source(db_session, test_user, source_id=src["id"])
    assert result["deleted"] is True
    # La source est bien filtree hors des vues publiques.
    with pytest.raises(ToolError, match="Aucune source"):
        await update_source(db_session, test_user, source_id=src["id"], stance="appuie")


@pytest.mark.asyncio
async def test_delete_source_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="Aucune source"):
        await delete_source(db_session, autre_utilisateur, source_id=src["id"])


@pytest.mark.asyncio
async def test_delete_excerpt_retire_l_extrait(db_session, test_user, fiche_brouillon):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    ex = await add_excerpt(
        db_session,
        test_user,
        source_id=src["id"],
        text="Un passage suffisamment long pour passer le garde-fou.",
    )
    result = await delete_excerpt(db_session, test_user, source_id=src["id"], excerpt_id=ex["id"])
    assert result["deleted"] is True


@pytest.mark.asyncio
async def test_delete_excerpt_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    ex = await add_excerpt(
        db_session,
        test_user,
        source_id=src["id"],
        text="Un passage suffisamment long pour passer le garde-fou.",
    )
    with pytest.raises(ToolError, match="Aucune source"):
        await delete_excerpt(
            db_session, autre_utilisateur, source_id=src["id"], excerpt_id=ex["id"]
        )


@pytest.mark.asyncio
async def test_verify_excerpts_avec_texte_fourni_marque_verified(
    db_session, test_user, fiche_brouillon
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    await add_excerpt(
        db_session,
        test_user,
        source_id=src["id"],
        text="Le passage exact que la source contient.",
    )
    result = await verify_excerpts(
        db_session,
        test_user,
        source_id=src["id"],
        provided_text="Un contexte. Le passage exact que la source contient. Fin.",
    )
    assert result["text_source"] == "provided"
    assert len(result["checks"]) == 1
    assert result["checks"][0]["status"] == "found"


@pytest.mark.asyncio
async def test_verify_excerpts_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="Aucune source"):
        await verify_excerpts(
            db_session,
            autre_utilisateur,
            source_id=src["id"],
            provided_text="rien",
        )


@pytest.mark.asyncio
async def test_list_connections_rend_les_deux_sens(db_session, test_user, fiche_brouillon):
    result = await list_connections(db_session, test_user, card_slug="fiche-en-cours")
    assert "outgoing" in result
    assert "incoming" in result
    assert isinstance(result["outgoing"], list)
    assert isinstance(result["incoming"], list)


@pytest.mark.asyncio
async def test_list_connections_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await list_connections(db_session, autre_utilisateur, card_slug="fiche-en-cours")


@pytest.mark.asyncio
async def test_confirm_connection_refuse_source_sans_lien(db_session, test_user, fiche_brouillon):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="ne designe aucune fiche"):
        await confirm_connection(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            source_id=src["id"],
        )


@pytest.mark.asyncio
async def test_confirm_connection_refuse_source_autre_fiche(db_session, test_user):
    await create_card(db_session, test_user, slug="fiche-a", title="A")
    await create_card(db_session, test_user, slug="fiche-b", title="B")
    src_a = await add_source(
        db_session,
        test_user,
        card_slug="fiche-a",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="n'appartient pas"):
        await confirm_connection(
            db_session,
            test_user,
            card_slug="fiche-b",
            source_id=src_a["id"],
        )


@pytest.mark.asyncio
async def test_remove_connection_efface_le_lien(db_session, test_user):
    # Deux fiches du meme user : la source de A designe B (linked automatique
    # via effective_linked_card_id lors du add_source).
    await create_card(db_session, test_user, slug="fiche-a", title="A")
    fiche_b_res = await create_card(
        db_session, test_user, slug="fiche-b", title="B", card_kind="sujet"
    )
    # `fiche-b` publiee pour que effective_linked_card_id la resolve.
    await publish_card(db_session, test_user, slug="fiche-b")
    # Utiliser l'URL publique de fiche-b comme source de fiche-a.
    src_a = await add_source(
        db_session,
        test_user,
        card_slug="fiche-a",
        url=fiche_b_res["public_url_when_published"],
    )
    # Meme si le lien est pose automatiquement, remove_connection doit
    # marcher sans erreur (idempotent quand pas de linked_card).
    result = await remove_connection(
        db_session,
        test_user,
        card_slug="fiche-a",
        source_id=src_a["id"],
    )
    assert result["linked_card_removed"] is True


@pytest.mark.asyncio
async def test_remove_connection_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        url="https://example.org/paper",
    )
    with pytest.raises(ToolError, match="Aucune fiche"):
        await remove_connection(
            db_session,
            autre_utilisateur,
            card_slug="fiche-en-cours",
            source_id=src["id"],
        )


# --- Import, LLM, listing, cycle de vie (chantier C - P2) -------------------


@pytest.mark.asyncio
async def test_list_my_cards_rend_les_fiches_du_user(db_session, test_user, fiche_brouillon):
    result = await list_my_cards(db_session, test_user)
    slugs = {c["slug"] for c in result["cards"]}
    assert "fiche-en-cours" in slugs
    assert "total" in result
    assert result["total"] >= 1


@pytest.mark.asyncio
async def test_list_my_cards_isole_par_user(db_session, test_user, autre_utilisateur):
    await create_card(db_session, test_user, slug="a-moi", title="A moi")
    await create_card(db_session, autre_utilisateur, slug="a-lui", title="A lui")
    mine = await list_my_cards(db_session, test_user)
    slugs = {c["slug"] for c in mine["cards"]}
    assert "a-moi" in slugs
    assert "a-lui" not in slugs


@pytest.mark.asyncio
async def test_list_sources_rend_les_sources_de_la_fiche(db_session, test_user, fiche_brouillon):
    await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org")
    await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://b.org")
    result = await list_sources(db_session, test_user, card_slug="fiche-en-cours")
    assert len(result) == 2
    assert result[0]["position"] < result[1]["position"]


@pytest.mark.asyncio
async def test_list_sources_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await list_sources(db_session, autre_utilisateur, card_slug="fiche-en-cours")


@pytest.mark.asyncio
async def test_search_my_excerpts_trouve_par_texte(db_session, test_user, fiche_brouillon):
    src = await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org")
    await add_excerpt(
        db_session,
        test_user,
        source_id=src["id"],
        text="Une affirmation precise avec le mot cle magique.",
    )
    result = await search_my_excerpts(db_session, test_user, query="magique")
    assert len(result) == 1
    assert "magique" in result[0]["text"]


@pytest.mark.asyncio
async def test_search_my_excerpts_isole_par_user(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org")
    await add_excerpt(
        db_session,
        test_user,
        source_id=src["id"],
        text="Une affirmation precise avec le mot cle magique.",
    )
    result = await search_my_excerpts(db_session, autre_utilisateur, query="magique")
    assert result == []


@pytest.mark.asyncio
async def test_delete_card_puis_restore_est_reversible(db_session, test_user, fiche_brouillon):
    del_result = await delete_card(db_session, test_user, slug="fiche-en-cours")
    assert del_result["deleted"] is True
    # Plus visible via list_my_cards
    mine = await list_my_cards(db_session, test_user)
    assert "fiche-en-cours" not in {c["slug"] for c in mine["cards"]}
    # Restore
    restore_result = await restore_card(db_session, test_user, slug="fiche-en-cours")
    assert restore_result["restored"] is True
    mine = await list_my_cards(db_session, test_user)
    assert "fiche-en-cours" in {c["slug"] for c in mine["cards"]}


@pytest.mark.asyncio
async def test_delete_card_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await delete_card(db_session, autre_utilisateur, slug="fiche-en-cours")


@pytest.mark.asyncio
async def test_archive_sources_accepte_les_sources_du_user(db_session, test_user, fiche_brouillon):
    src = await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org")
    result = await archive_sources(db_session, test_user, source_ids=[src["id"]])
    assert src["id"] in result["accepted"]
    assert result["refused"] == []


@pytest.mark.asyncio
async def test_archive_sources_refuse_les_sources_d_autrui(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    src = await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org")
    result = await archive_sources(db_session, autre_utilisateur, source_ids=[src["id"]])
    assert result["accepted"] == []
    assert len(result["refused"]) == 1


# --- Attestations, citations entrantes, batch, claim, parsers (chantier D) --


@pytest.mark.asyncio
async def test_add_sources_batch_pose_plusieurs_sources_en_un_appel(
    db_session, test_user, fiche_brouillon
):
    result = await add_sources_batch(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        sources=[
            {"url": "https://a.org/1", "title": "A"},
            {"url": "https://a.org/2", "title": "B"},
            {"url": "https://a.org/3", "title": "C"},
        ],
    )
    assert len(result["created"]) == 3
    assert result["failed"] == []


@pytest.mark.asyncio
async def test_add_sources_batch_dedup_dans_le_meme_lot(db_session, test_user, fiche_brouillon):
    result = await add_sources_batch(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        sources=[
            {"url": "https://a.org/1"},
            {"url": "https://a.org/1"},  # doublon
        ],
    )
    assert len(result["created"]) == 1
    assert len(result["failed"]) == 1


@pytest.mark.asyncio
async def test_add_sources_batch_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await add_sources_batch(
            db_session,
            autre_utilisateur,
            card_slug="fiche-en-cours",
            sources=[{"url": "https://x.org"}],
        )


@pytest.mark.asyncio
async def test_list_incoming_citations_rend_zero_par_defaut(db_session, test_user):
    result = await list_incoming_citations(db_session, test_user)
    assert result["citations"] == []
    assert result["new_count"] == 0


@pytest.mark.asyncio
async def test_mark_citations_seen_pose_un_timestamp(db_session, test_user):
    result = await mark_citations_seen(db_session, test_user)
    assert result["seen_at"] is not None


@pytest.mark.asyncio
async def test_list_deleted_cards_rend_les_fiches_de_la_corbeille(
    db_session, test_user, fiche_brouillon
):
    await delete_card(db_session, test_user, slug="fiche-en-cours")
    result = await list_deleted_cards(db_session, test_user)
    slugs = {c["slug"] for c in result}
    assert "fiche-en-cours" in slugs


@pytest.mark.asyncio
async def test_parse_biblio_extrait_des_references_d_un_texte(db_session, test_user):
    text = """
- [Article 1](https://example.org/1)
- [Article 2](https://example.org/2)
"""
    result = await parse_biblio(db_session, test_user, text=text)
    assert len(result["refs"]) >= 1


@pytest.mark.asyncio
async def test_parse_biblio_texte_vide_rend_liste_vide(db_session, test_user):
    result = await parse_biblio(db_session, test_user, text="")
    assert result["refs"] == []


@pytest.mark.asyncio
async def test_create_claim_request_refuse_fiche_non_seed(db_session, test_user, fiche_brouillon):
    # La fiche_brouillon n'est pas seed (creee par le user directement).
    # Il faut d'abord publier pour tester ; mais meme publiee elle n'est pas
    # seed. Le check est_seed refuse.
    await publish_card(db_session, test_user, slug="fiche-en-cours")
    from sqlalchemy import select as _select

    from app.models.biblio_card import BiblioCard as _BC

    card = await db_session.scalar(_select(_BC).where(_BC.slug == "fiche-en-cours"))
    with pytest.raises(ToolError, match="pas une fiche seed"):
        await create_claim_request(db_session, test_user, card_id=str(card.id))


@pytest.mark.asyncio
async def test_create_content_attestation_refuse_fiche_sans_url(db_session, test_user):
    # Sans content_url, l'attestation refuse (rien a signer).
    await create_card(db_session, test_user, slug="sans-url", title="Sans URL")
    with pytest.raises(ToolError, match="content_url"):
        await create_content_attestation(db_session, test_user, card_slug="sans-url")


@pytest.mark.asyncio
async def test_create_content_attestation_refuse_non_proprietaire(
    db_session, test_user, fiche_brouillon, autre_utilisateur
):
    with pytest.raises(ToolError, match="Aucune fiche"):
        await create_content_attestation(db_session, autre_utilisateur, card_slug="fiche-en-cours")


@pytest.mark.asyncio
async def test_get_attestation_refuse_id_invalide(db_session, test_user):
    with pytest.raises(ToolError, match="invalide"):
        await create_claim_request(db_session, test_user, card_id="pas-un-uuid")


# --- Validation des enums a l'entree (regression fiche creatine 2026-08-21) --


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("champ", "valeur"),
    [
        ("stance", "soutient"),
        ("category", "rapport-officiel"),
        ("author_kind", "institution"),
        ("format", "pdf"),
    ],
)
async def test_add_source_refuse_une_valeur_hors_vocabulaire(
    db_session, test_user, fiche_brouillon, champ, valeur
):
    with pytest.raises(ToolError, match="Valeurs acceptees"):
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            url="https://a.org/refusee",
            **{champ: valeur},
        )


@pytest.mark.asyncio
async def test_add_source_message_d_erreur_cite_le_vocabulaire(
    db_session, test_user, fiche_brouillon
):
    with pytest.raises(ToolError) as exc_info:
        await add_source(
            db_session,
            test_user,
            card_slug="fiche-en-cours",
            url="https://a.org/x",
            stance="soutient",
        )
    # L'agent doit pouvoir se corriger seul : la bonne valeur est dans le message.
    assert "appuie" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_source_stance_vide_vaut_silence(db_session, test_user, fiche_brouillon):
    from sqlalchemy import select as _select

    from app.models.source import Source as _Source

    src = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://a.org/silence", stance=""
    )
    ligne = await db_session.scalar(_select(_Source).where(_Source.id == UUID(src["id"])))
    # Chaine vide = silence declare, jamais une valeur hors vocabulaire.
    assert ligne.stance is None


@pytest.mark.asyncio
async def test_update_source_refuse_une_valeur_hors_vocabulaire(
    db_session, test_user, fiche_brouillon
):
    src = await add_source(db_session, test_user, card_slug="fiche-en-cours", url="https://a.org/u")
    with pytest.raises(ToolError, match="Valeurs acceptees"):
        await update_source(db_session, test_user, source_id=src["id"], stance="soutient")


@pytest.mark.asyncio
async def test_update_source_stance_vide_efface_la_position(db_session, test_user, fiche_brouillon):
    src = await add_source(
        db_session, test_user, card_slug="fiche-en-cours", url="https://a.org/v", stance="appuie"
    )
    result = await update_source(db_session, test_user, source_id=src["id"], stance="")
    assert result["stance"] is None


@pytest.mark.asyncio
async def test_add_sources_batch_rejette_dans_failed_sans_bloquer_le_lot(
    db_session, test_user, fiche_brouillon
):
    result = await add_sources_batch(
        db_session,
        test_user,
        card_slug="fiche-en-cours",
        sources=[
            {"url": "https://a.org/ok", "stance": "soutient"},  # refuse
            {"url": "https://a.org/bon", "stance": "appuie"},  # accepte
        ],
    )
    assert [c["url"] for c in result["created"]] == ["https://a.org/bon"]
    assert len(result["failed"]) == 1
    assert "Valeurs acceptees" in result["failed"][0]["reason"]
