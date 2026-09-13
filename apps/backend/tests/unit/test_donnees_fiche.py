"""Les donnees d'une fiche creee par l'agent doivent etre bien formees.

Mesures du 2026-09-13, conversations « arthrose » : une seconde fiche sur le
meme sujet, une fiche « contenu » dont le contenu etait aussi une source, un
PDF reste sans titre, un extrait inscrit avec les sauts de ligne bruts du PDF.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastmcp.exceptions import ToolError

from app.mcp_server import tools_write
from app.mcp_server.tools_write import add_source, create_card
from app.services import excerpt_insertion, metadonnees_source
from app.services.excerpt_insertion import texte_lisible

OMS = "https://www.who.int/fr/news-room/fact-sheets/detail/osteoarthritis"


class TestFicheEnDouble:
    @pytest.mark.asyncio
    async def test_un_titre_du_meme_sujet_est_refuse_en_nommant_l_existante(
        self, db_session, test_user
    ):
        await create_card(
            db_session,
            test_user,
            slug="prevention-arthrose",
            title="Prévention de l'arthrose",
            card_kind="sujet",
        )
        with pytest.raises(ToolError, match="prevention-arthrose"):
            await create_card(
                db_session,
                test_user,
                slug="prevention-arthrose-strategies",
                title="Prévention de l'arthrose : stratégies scientifiques",
                card_kind="sujet",
            )

    @pytest.mark.asyncio
    async def test_un_autre_angle_assume_passe(self, db_session, test_user):
        await create_card(
            db_session,
            test_user,
            slug="prevention-arthrose",
            title="Prévention de l'arthrose",
            card_kind="sujet",
        )
        cree = await create_card(
            db_session,
            test_user,
            slug="arthrose-sport",
            title="Prévention de l'arthrose chez les sportifs",
            card_kind="sujet",
            confirm_distinct=True,
        )
        assert cree["slug"] == "arthrose-sport"

    @pytest.mark.asyncio
    async def test_un_autre_sujet_passe(self, db_session, test_user):
        await create_card(
            db_session,
            test_user,
            slug="prevention-arthrose",
            title="Prévention de l'arthrose",
            card_kind="sujet",
        )
        cree = await create_card(
            db_session,
            test_user,
            slug="warburg",
            title="L'effet Warburg et le cancer",
            card_kind="sujet",
        )
        assert cree["slug"] == "warburg"


@pytest.mark.asyncio
async def test_le_contenu_documente_n_est_pas_une_source(db_session, test_user):
    await create_card(
        db_session,
        test_user,
        slug="oms-arthrose",
        title="Arthrose selon l'OMS",
        card_kind="contenu",
        content_url=OMS,
    )
    with pytest.raises(ToolError, match="fiche sujet"):
        await add_source(
            db_session, test_user, card_slug="oms-arthrose", metadata_from="page", url=OMS
        )


@pytest.mark.asyncio
async def test_un_titre_que_l_origine_ne_rend_pas_est_garde_et_signale(monkeypatch):
    async def resoudre(origine, *, url, doi):
        return SimpleNamespace(
            title=None, authors=None, published_at=None, journal=None, publisher=None
        )

    monkeypatch.setattr(metadonnees_source, "resoudre", resoudre)
    retenues, signales = await tools_write._resoudre_metadonnees(
        "page",
        url="https://example.org/recommandations.pdf",
        doi=None,
        propose={"title": "Recommandations arthrose", "authors": None},
    )
    assert retenues["title"] == "Recommandations arthrose"
    assert [s["champ"] for s in signales if "note" in s] == ["title"]


class TestExtraitLisible:
    def test_cesures_et_sauts_de_ligne(self):
        brut = "Les 10 messages\nclés : facteurs démo-\ngraphiques   et poids."
        assert texte_lisible(brut) == "Les 10 messages clés : facteurs démographiques et poids."

    def test_un_mot_compose_sur_une_ligne_garde_son_trait_d_union(self):
        assert texte_lisible("une étude franco-allemande") == "une étude franco-allemande"

    def test_l_extrait_inscrit_est_le_texte_lisible(self):
        page = "Introduction.\nLes facteurs démo-\ngraphiques expliquent\nla hausse. Suite."
        preleve = excerpt_insertion._prelever(
            page, "Les facteurs démographiques expliquent la hausse.", True
        )
        assert preleve.texte == "Les facteurs démographiques expliquent la hausse."
