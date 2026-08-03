"""Citations entrantes : qui s'appuie sur mes fiches, et depuis quand."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio

from app.models.biblio_card import BiblioCard, CardStatus, ContentType, Platform
from app.models.source import AuthorKind, Source, SourceCategory, SourceFormat
from app.models.user import User
from app.services.citations import list_incoming_citations, mark_citations_seen


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None)


NOW = _naive(datetime.now(UTC))


async def _make_card(db, user, slug, *, published=True, published_at=None):
    card = BiblioCard(
        id=uuid4(),
        user_id=user.id,
        slug=slug,
        title=f"Fiche {slug}",
        content_type=ContentType.ARTICLE.value,
        platform=Platform.BLOG.value,
        status=CardStatus.PUBLISHED.value if published else CardStatus.DRAFT.value,
        visibility="public",
        published_at=published_at if published else None,
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return card


async def _cite(db, *, from_card, to_card, created_at=None, stance=None):
    source = Source(
        id=uuid4(),
        biblio_card_id=from_card.id,
        position=0,
        url="https://example.com/ref",
        title="Une reference",
        format=SourceFormat.TEXTE.value,
        category=SourceCategory.BLOG.value,
        author_kind=AuthorKind.INDIVIDU.value,
        linked_card_id=to_card.id,
        stance=stance,
    )
    if created_at is not None:
        source.created_at = created_at
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@pytest_asyncio.fixture
async def other_user(db_session):
    user = User(
        id=uuid4(),
        email="other@example.com",
        username="otheruser",
        display_name="Other User",
        public_key="o" * 64,
        encrypted_private_key="encrypted_other_key",
        google_id="google_other_456",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    yield user


@pytest_asyncio.fixture
async def my_card(db_session, test_user):
    return await _make_card(db_session, test_user, "ma-fiche", published_at=NOW)


class TestCeQuiCompteCommeCitation:
    async def test_une_fiche_publique_tierce_est_remontee(
        self, db_session, test_user, other_user, my_card
    ):
        citing = await _make_card(db_session, other_user, "leur-fiche", published_at=NOW)
        await _cite(db_session, from_card=citing, to_card=my_card)

        result = await list_incoming_citations(db_session, test_user)
        assert len(result.citations) == 1
        c = result.citations[0]
        assert c.citing_card_slug == "leur-fiche"
        assert c.citing_creator_slug == "otheruser"
        assert c.cited_card_slug == "ma-fiche"

    async def test_un_brouillon_qui_cite_ne_remonte_pas(
        self, db_session, test_user, other_user, my_card
    ):
        # Alerter revelerait l'existence d'un travail non publie, et le lien
        # peut encore disparaitre avant publication.
        citing = await _make_card(db_session, other_user, "brouillon", published=False)
        await _cite(db_session, from_card=citing, to_card=my_card)

        assert (await list_incoming_citations(db_session, test_user)).citations == []

    async def test_une_fiche_privee_qui_cite_ne_remonte_pas(
        self, db_session, test_user, other_user, my_card
    ):
        citing = await _make_card(db_session, other_user, "privee", published_at=NOW)
        citing.visibility = "private"
        await db_session.commit()
        await _cite(db_session, from_card=citing, to_card=my_card)

        assert (await list_incoming_citations(db_session, test_user)).citations == []

    async def test_s_auto_citer_ne_compte_pas(self, db_session, test_user, my_card):
        # Relier deux de ses propres fiches est un acte d'edition, pas une
        # reprise par un tiers.
        mine = await _make_card(db_session, test_user, "mon-autre-fiche", published_at=NOW)
        await _cite(db_session, from_card=mine, to_card=my_card)

        assert (await list_incoming_citations(db_session, test_user)).citations == []

    async def test_une_source_supprimee_ne_compte_plus(
        self, db_session, test_user, other_user, my_card
    ):
        citing = await _make_card(db_session, other_user, "leur-fiche", published_at=NOW)
        source = await _cite(db_session, from_card=citing, to_card=my_card)
        source.deleted_at = NOW
        await db_session.commit()

        assert (await list_incoming_citations(db_session, test_user)).citations == []

    async def test_le_rapport_declare_est_transmis(
        self, db_session, test_user, other_user, my_card
    ):
        # « On me cite » et « on me contredit » ne sont pas la meme nouvelle.
        citing = await _make_card(db_session, other_user, "leur-fiche", published_at=NOW)
        await _cite(db_session, from_card=citing, to_card=my_card, stance="contredit")

        assert (await list_incoming_citations(db_session, test_user)).citations[0].stance == (
            "contredit"
        )


class TestNouveaute:
    async def test_jamais_consulte_rend_tout_neuf(self, db_session, test_user, other_user, my_card):
        # NULL ne veut pas dire « rien de nouveau » : personne n'a regarde.
        assert test_user.citations_seen_at is None
        citing = await _make_card(db_session, other_user, "leur-fiche", published_at=NOW)
        await _cite(
            db_session, from_card=citing, to_card=my_card, created_at=NOW - timedelta(days=400)
        )

        result = await list_incoming_citations(db_session, test_user)
        assert result.seen_at is None
        assert result.new_count == 1
        assert result.citations[0].is_new is True

    async def test_apres_consultation_l_ancien_n_est_plus_neuf(
        self, db_session, test_user, other_user, my_card
    ):
        old = NOW - timedelta(days=10)
        citing = await _make_card(db_session, other_user, "ancienne", published_at=old)
        await _cite(db_session, from_card=citing, to_card=my_card, created_at=old)
        mark_citations_seen(test_user)
        await db_session.commit()

        result = await list_incoming_citations(db_session, test_user)
        assert result.new_count == 0
        assert result.citations[0].is_new is False

    async def test_une_citation_posterieure_redevient_neuve(
        self, db_session, test_user, other_user, my_card
    ):
        test_user.citations_seen_at = NOW - timedelta(days=5)
        await db_session.commit()
        recent = await _make_card(db_session, other_user, "recente", published_at=NOW)
        await _cite(db_session, from_card=recent, to_card=my_card, created_at=NOW)

        result = await list_incoming_citations(db_session, test_user)
        assert result.new_count == 1

    async def test_marquer_vu_pose_un_datetime_naif(self, test_user):
        # Un datetime tz-aware casse asyncpg sur TIMESTAMP WITHOUT TIME ZONE.
        seen = mark_citations_seen(test_user)
        assert seen.tzinfo is None
        assert test_user.citations_seen_at == seen


class TestDateDeLaCitation:
    async def test_la_publication_tardive_fait_foi(
        self, db_session, test_user, other_user, my_card
    ):
        # Fiche redigee en brouillon il y a un an, publiee aujourd'hui : la
        # citation nait aujourd'hui. Dater de la source la ferait naitre
        # deja vue par quiconque a consulte entre-temps.
        old = NOW - timedelta(days=365)
        citing = await _make_card(db_session, other_user, "tardive", published_at=NOW)
        await _cite(db_session, from_card=citing, to_card=my_card, created_at=old)

        c = (await list_incoming_citations(db_session, test_user)).citations[0]
        assert c.cited_at > old

    async def test_sans_published_at_la_source_fait_foi(
        self, db_session, test_user, other_user, my_card
    ):
        # Fiches anterieures au champ published_at : faute de mieux.
        citing = await _make_card(db_session, other_user, "sans-date", published_at=None)
        citing.status = CardStatus.PUBLISHED.value
        await db_session.commit()
        created = NOW - timedelta(days=3)
        await _cite(db_session, from_card=citing, to_card=my_card, created_at=created)

        c = (await list_incoming_citations(db_session, test_user)).citations[0]
        assert c.cited_at == created


class TestTri:
    async def test_les_plus_recentes_d_abord(self, db_session, test_user, other_user, my_card):
        a = await _make_card(
            db_session, other_user, "ancienne", published_at=NOW - timedelta(days=9)
        )
        b = await _make_card(db_session, other_user, "recente", published_at=NOW)
        await _cite(db_session, from_card=a, to_card=my_card, created_at=NOW - timedelta(days=9))
        await _cite(db_session, from_card=b, to_card=my_card, created_at=NOW)

        slugs = [
            c.citing_card_slug
            for c in (await list_incoming_citations(db_session, test_user)).citations
        ]
        assert slugs == ["recente", "ancienne"]
