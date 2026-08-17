"""CardService — cycle de vie d'une fiche.

`test_cards.py` teste les endpoints HTTP ; ce fichier teste directement le
service, plus rapide et plus precis pour les branches metier qui n'ont pas
d'ecran (ownership, publish_card ordre de commit + eager-load, soft/restore,
compute_stats sur les archivables).

Ces branches ont un historique de regressions (PRs #33-#36 mai 2026,
MissingGreenlet sur publish_card) ; les tenir sous test unitaire raccourcit
la boucle de detection.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.models.biblio_card import CardStatus
from app.models.source import ArchiveStatus, AuthorKind, Source
from app.schemas.biblio_card import CardCreate, ContentType, Platform, Visibility
from app.services.card import CardService


@pytest.fixture
def service(db_session):
    return CardService(db_session)


def _payload(**overrides) -> CardCreate:
    base = {
        "slug": "ma-fiche",
        "title": "Ma fiche",
        "description": "Une fiche de test.",
        "content_url": "https://example.org/video",
        "content_authors": "Alice, Bob",
        "platform": Platform.YOUTUBE,
        "content_type": ContentType.VIDEO,
        "visibility": Visibility.PUBLIC,
    }
    base.update(overrides)
    return CardCreate(**base)


@pytest.mark.asyncio
async def test_creer_une_fiche_persiste_les_champs_declares(service, test_user):
    card = await service.create_card(test_user.id, _payload())
    assert card.id is not None
    assert card.user_id == test_user.id
    assert card.slug == "ma-fiche"
    assert card.title == "Ma fiche"
    assert card.content_url == "https://example.org/video"
    assert card.content_authors == "Alice, Bob"
    assert card.status == CardStatus.DRAFT.value
    assert card.published_at is None


@pytest.mark.asyncio
async def test_get_card_by_id_ignore_les_fiches_supprimees(db_session, service, test_user):
    card = await service.create_card(test_user.id, _payload())
    assert await service.get_card_by_id(card.id) is not None
    await service.delete_card(card.id, test_user.id)
    assert await service.get_card_by_id(card.id) is None


@pytest.mark.asyncio
async def test_get_card_by_slug_par_defaut_publiee_seulement(service, test_user):
    """Le proxy /discover / profil public ne doit voir que les fiches publiees."""
    card = await service.create_card(test_user.id, _payload(slug="brouillon"))
    # Draft : invisible en mode public.
    assert (
        await service.get_card_by_slug(test_user.username, "brouillon", published_only=True) is None
    )
    # Draft : visible quand on lit tout (dashboard owner).
    assert (
        await service.get_card_by_slug(test_user.username, "brouillon", published_only=False)
        is not None
    )
    # Publication.
    await service.publish_card(card)
    assert (
        await service.get_card_by_slug(test_user.username, "brouillon", published_only=True)
        is not None
    )


@pytest.mark.asyncio
async def test_publish_card_met_status_published_et_horodatage(service, test_user):
    card = await service.create_card(test_user.id, _payload())
    assert card.status == CardStatus.DRAFT.value
    result = await service.publish_card(card)
    assert result["status"] == CardStatus.PUBLISHED
    assert result["published_at"] is not None
    assert result["public_url"].endswith(f"/@{test_user.username}/ma-fiche")


@pytest.mark.asyncio
async def test_publish_card_capture_le_username_avant_commit(service, test_user):
    """Regression PR #33 (mai 2026) : publish_card lisait card.user.username
    APRES commit + refresh, provoquant MissingGreenlet. La capture avant commit
    est le contrat ; ce test le fige."""
    card = await service.create_card(test_user.id, _payload())
    result = await service.publish_card(card)
    # public_url reconstruit depuis le username capture : si le contrat casse,
    # ce champ contiendra l'exception au lieu du slug.
    assert f"/@{test_user.username}/" in result["public_url"]


@pytest.mark.asyncio
async def test_publish_deux_fois_n_ajoute_pas_deux_events_de_feed(db_session, service, test_user):
    """Le feed est le registre du premier passage au public, pas un journal
    d'edition. Republier une fiche publique n'ajoute rien."""
    from sqlalchemy import func, select

    from app.models.feed_event import FeedEvent, FeedEventKind

    card = await service.create_card(test_user.id, _payload())
    await service.publish_card(card)
    await service.publish_card(card)  # second publish
    count = await db_session.scalar(
        select(func.count())
        .select_from(FeedEvent)
        .where(
            FeedEvent.card_id == card.id,
            FeedEvent.kind == FeedEventKind.CARD_PUBLISHED,
        )
    )
    assert count == 1


@pytest.mark.asyncio
async def test_delete_puis_restore_rend_la_fiche_a_la_vue(db_session, service, test_user):
    card = await service.create_card(test_user.id, _payload())
    assert await service.delete_card(card.id, test_user.id) is True
    assert await service.get_card_by_id(card.id) is None
    restored = await service.restore_card(card.id, test_user.id)
    assert restored is not None
    assert restored.deleted_at is None
    assert await service.get_card_by_id(card.id) is not None


@pytest.mark.asyncio
async def test_delete_par_un_autre_user_est_refuse(db_session, service, test_user):
    """Deux fiches, deux users : personne ne peut supprimer celle de l'autre."""
    from app.models.user import User

    autre = User(
        id=uuid4(),
        email="autre@example.org",
        username="autre",
        display_name="Autre",
        public_key="a" * 64,
        encrypted_private_key="k",
        google_id="g_autre",
        is_verified=True,
    )
    db_session.add(autre)
    await db_session.commit()
    card = await service.create_card(test_user.id, _payload())
    ok = await service.delete_card(card.id, autre.id)
    assert ok is False
    # Fiche toujours la.
    assert await service.get_card_by_id(card.id) is not None


@pytest.mark.asyncio
async def test_delete_d_une_fiche_deja_supprimee_retourne_false(service, test_user):
    """Deuxieme delete = no-op explicite, pas exception."""
    card = await service.create_card(test_user.id, _payload())
    await service.delete_card(card.id, test_user.id)
    assert await service.delete_card(card.id, test_user.id) is False


@pytest.mark.asyncio
async def test_restore_d_une_fiche_non_supprimee_rend_none(service, test_user):
    card = await service.create_card(test_user.id, _payload())
    assert await service.restore_card(card.id, test_user.id) is None


@pytest.mark.asyncio
async def test_compute_stats_ne_compte_que_les_sources_archivables(db_session, service, test_user):
    """Une source sans URL n'a rien a archiver. La compter au denominateur
    condamnerait une fiche complete a afficher '148/152' pour toujours."""
    card = await service.create_card(test_user.id, _payload())

    # Une source archivee.
    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=card.id,
            position=1,
            url="https://ex.org/a",
            format="texte",
            category="article-scientifique",
            author_kind=AuthorKind.CHERCHEUR.value,
            archive_status=ArchiveStatus.ARCHIVED.value,
        )
    )
    # Une source pending (archivable).
    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=card.id,
            position=2,
            url="https://ex.org/b",
            format="texte",
            category="article-scientifique",
            author_kind=AuthorKind.CHERCHEUR.value,
            archive_status=ArchiveStatus.PENDING.value,
        )
    )
    # Une source non_applicable (livre sans URL par exemple) : hors denominateur.
    db_session.add(
        Source(
            id=uuid4(),
            biblio_card_id=card.id,
            position=3,
            url="",
            format="texte",
            category="livre",
            author_kind=AuthorKind.CHERCHEUR.value,
            archive_status=ArchiveStatus.NOT_APPLICABLE.value,
        )
    )
    await db_session.commit()
    card = await service.get_card_by_id(card.id)  # recharge avec sources
    stats = service.compute_stats(card)
    assert stats.total_sources == 3
    assert stats.archived_count == 1
    assert stats.archivable_count == 2
    assert stats.all_archived is False


@pytest_asyncio.fixture
async def get_user_cards_fixtures(service, db_session, test_user):
    from app.models.user import User

    autre = User(
        id=uuid4(),
        email="autre2@example.org",
        username="autre2",
        display_name="Autre 2",
        public_key="b" * 64,
        encrypted_private_key="k",
        google_id="g_autre2",
        is_verified=True,
    )
    db_session.add(autre)
    await db_session.commit()
    a = await service.create_card(test_user.id, _payload(slug="fiche-a"))
    b = await service.create_card(test_user.id, _payload(slug="fiche-b"))
    c = await service.create_card(autre.id, _payload(slug="fiche-c"))
    return test_user, autre, a, b, c


@pytest.mark.asyncio
async def test_get_user_cards_isole_par_user(service, get_user_cards_fixtures):
    test_user, autre, a, b, c = get_user_cards_fixtures
    mine = await service.get_user_cards(test_user.id)
    slugs = {card.slug for card in mine}
    assert slugs == {"fiche-a", "fiche-b"}
    others = await service.get_user_cards(autre.id)
    assert {card.slug for card in others} == {"fiche-c"}


@pytest.mark.asyncio
async def test_get_user_cards_filtre_par_status(service, get_user_cards_fixtures):
    test_user, _, a, b, _ = get_user_cards_fixtures
    await service.publish_card(a)
    published = await service.get_user_cards(test_user.id, status=CardStatus.PUBLISHED)
    assert {card.slug for card in published} == {"fiche-a"}
    drafts = await service.get_user_cards(test_user.id, status=CardStatus.DRAFT)
    assert {card.slug for card in drafts} == {"fiche-b"}
