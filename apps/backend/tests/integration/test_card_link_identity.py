"""Rattachement d'une source a la fiche qui documente le meme contenu.

Contrat produit : une reference vers un article et la fiche Philum qui
documente cet article sont le meme objet. Le lien ne doit pas dependre de
quelqu'un qui l'aurait pose a la main : sinon la meme reference apparait deux
fois sur le meta-graphe, une fois comme fiche, une fois comme source isolee.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.card_link import link_sources_designating_card, resolve_card_by_content

FRONTIERS = (
    "https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2022.651547/full"
)


def _card(user_id, slug, title, *, content_url=None, status="published", visibility="public"):
    from app.models.biblio_card import BiblioCard

    return BiblioCard(
        id=uuid4(),
        user_id=user_id,
        slug=slug,
        title=title,
        content_url=content_url,
        content_type="article",
        platform="blog",
        status=status,
        visibility=visibility,
    )


def _source(card_id, url, *, doi=None, linked_card_id=None):
    from app.models.source import Source

    return Source(
        id=uuid4(),
        biblio_card_id=card_id,
        position=0,
        url=url,
        title="Inhibitory control development: A network neuroscience perspective",
        format="texte",
        category="article-scientifique",
        author_kind="chercheur",
        doi=doi,
        linked_card_id=linked_card_id,
    )


@pytest.mark.asyncio
class TestResolveCardByContent:
    async def test_matches_on_the_doi_across_two_publisher_urls(self, db_session, test_user):
        # La fiche est saisie depuis l'URL Frontiers, la source depuis doi.org :
        # deux ecritures du meme article.
        card = _card(test_user.id, "inhib", "Inhibitory control", content_url=FRONTIERS)
        db_session.add(card)
        await db_session.commit()

        found = await resolve_card_by_content(
            db_session,
            "https://doi.org/10.3389/fpsyg.2022.651547",
            doi="10.3389/fpsyg.2022.651547",
        )
        assert found == card.id

    async def test_matches_on_the_url_despite_www_slash_and_tracking(self, db_session, test_user):
        card = _card(
            test_user.id, "nat", "Nature", content_url="https://www.nature.com/articles/abc"
        )
        db_session.add(card)
        await db_session.commit()

        found = await resolve_card_by_content(
            db_session, "http://nature.com/articles/abc/?utm_source=x"
        )
        assert found == card.id

    async def test_never_reveals_a_draft_or_private_card(self, db_session, test_user):
        draft = _card(test_user.id, "d", "D", content_url=FRONTIERS, status="draft")
        private = _card(test_user.id, "p", "P", content_url=FRONTIERS, visibility="private")
        db_session.add_all([draft, private])
        await db_session.commit()

        assert await resolve_card_by_content(db_session, FRONTIERS) is None

    async def test_a_card_does_not_designate_itself(self, db_session, test_user):
        card = _card(test_user.id, "self", "Self", content_url=FRONTIERS)
        db_session.add(card)
        await db_session.commit()

        assert await resolve_card_by_content(db_session, FRONTIERS, exclude_card_id=card.id) is None

    async def test_ignores_a_url_that_designates_nothing(self, db_session, test_user):
        card = _card(test_user.id, "x", "X", content_url=FRONTIERS)
        db_session.add(card)
        await db_session.commit()

        assert await resolve_card_by_content(db_session, "https://example.com/autre") is None


@pytest.mark.asyncio
class TestLinkSourcesDesignatingCard:
    async def test_catches_up_references_entered_before_the_card_existed(
        self, db_session, test_user
    ):
        citing = _card(test_user.id, "citing", "Fiche citante")
        db_session.add(citing)
        await db_session.flush()
        orphan = _source(citing.id, "https://doi.org/10.3389/fpsyg.2022.651547")
        db_session.add(orphan)
        await db_session.commit()

        target = _card(test_user.id, "inhib", "Inhibitory control", content_url=FRONTIERS)
        db_session.add(target)
        await db_session.flush()
        await link_sources_designating_card(db_session, target)
        await db_session.commit()

        await db_session.refresh(orphan)
        assert orphan.linked_card_id == target.id

    async def test_leaves_an_explicit_link_alone(self, db_session, test_user):
        citing = _card(test_user.id, "citing", "Fiche citante")
        other = _card(test_user.id, "other", "Autre fiche")
        db_session.add_all([citing, other])
        await db_session.flush()
        chosen = _source(
            citing.id, "https://doi.org/10.3389/fpsyg.2022.651547", linked_card_id=other.id
        )
        db_session.add(chosen)
        await db_session.commit()

        target = _card(test_user.id, "inhib", "Inhibitory control", content_url=FRONTIERS)
        db_session.add(target)
        await db_session.flush()
        await link_sources_designating_card(db_session, target)
        await db_session.commit()

        await db_session.refresh(chosen)
        assert chosen.linked_card_id == other.id

    async def test_a_card_never_links_its_own_sources_to_itself(self, db_session, test_user):
        target = _card(test_user.id, "inhib", "Inhibitory control", content_url=FRONTIERS)
        db_session.add(target)
        await db_session.flush()
        # Une fiche cite parfois le contenu qu'elle documente : ce lien ferait
        # une boucle sur elle-meme.
        own = _source(target.id, FRONTIERS)
        db_session.add(own)
        await db_session.commit()

        await link_sources_designating_card(db_session, target)
        await db_session.commit()

        await db_session.refresh(own)
        assert own.linked_card_id is None
