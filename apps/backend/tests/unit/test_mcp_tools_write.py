"""Une IA connectee au MCP fabrique une fiche complete de bout en bout.

Ces tools existent pour que le geste « je viens de lire un corpus, je te
laisse en tirer une fiche » puisse se faire depuis le protocole standard,
sans qu'un agent ait besoin de piloter un navigateur ou d'appeler l'API
REST par un autre chemin.

Ils partagent les invariants du REST (propriete, unicite, capacite) sans
les reimplementer : chaque fonction delegue au meme service metier.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from fastmcp.exceptions import ToolError

from app.mcp_server.tools_write import (
    add_excerpt,
    add_source,
    create_card,
    publish_card,
)


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
    from app.models.source_excerpt import SourceExcerpt
    from sqlalchemy import select as _select

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
    )
    await publish_card(db_session, test_user, slug="parcours-complet")

    trouvees = await search_cards(db_session, query="parcours")
    assert any(f["slug"] == "parcours-complet" for f in trouvees)
    detail = await get_card(db_session, creator=test_user.username, slug="parcours-complet")
    assert detail is not None
    assert len(detail["sources"]) == 2
