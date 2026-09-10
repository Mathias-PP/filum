"""Le titre d'une source vient d'un resolveur, jamais du modele qui l'appelle.

Un agent qui tape lui-meme le titre et les auteurs peut les inventer, et un
titre plausible ne se distingue d'un titre vrai qu'en allant verifier. Ces
tests eprouvent la forme choisie pour rendre l'invention impossible plutot que
deconseillee : l'appelant declare une origine, l'origine remplit les champs, et
ce qu'elle ne rend pas reste vide.
"""

from __future__ import annotations

import httpx
import pytest
from fastmcp.exceptions import ToolError

from app.agent_tools import philum
from app.extractors.openalex_metadonnees import chercher_par_doi, parser_work_openalex
from app.extractors.url_extractor import ExtractedMetadata
from app.mcp_server.tools_write import add_source, add_sources_batch, create_card, update_source
from app.models.source import MetadataOrigin, Source
from app.services import metadonnees_source

_WORK = {
    "display_name": "Sleep and memory consolidation",
    "authorships": [
        {"author": {"display_name": "Jan Born"}},
        {"author": {"display_name": "Susanne Diekelmann"}},
    ],
    "publication_date": "2010-02-01",
    "primary_location": {
        "source": {
            "display_name": "Nature Reviews Neuroscience",
            "host_organization_name": "Springer Nature",
        }
    },
    "biblio": {"volume": "11", "first_page": "114", "last_page": "126"},
    "doi": "https://doi.org/10.1038/nrn2762",
    "cited_by_count": 3421,
}


class TestParserOpenAlex:
    """Fonction pure : le parsing se teste sans reseau."""

    def test_un_work_complet_rend_ses_champs(self):
        m = parser_work_openalex(_WORK)
        assert m is not None
        assert m.title == "Sleep and memory consolidation"
        assert m.authors == "Jan Born, Susanne Diekelmann"
        assert m.journal == "Nature Reviews Neuroscience"
        assert m.publisher == "Springer Nature"
        assert m.volume == "11"
        assert m.pages == "114-126"
        assert m.doi == "10.1038/nrn2762"

    def test_sans_titre_rien_n_est_rendu(self):
        """Une reference sans titre n'est pas identifiable.

        Remplir les autres champs donnerait une source anonyme que personne ne
        peut verifier, et une ligne anonyme se voit moins qu'une ligne absente.
        """
        assert parser_work_openalex({"authorships": [{"author": {"display_name": "X"}}]}) is None
        assert parser_work_openalex(None) is None

    def test_le_nom_d_auteur_n_est_pas_recoupe(self):
        """OpenAlex ne separe pas nom et prenom de facon fiable.

        Deviner ou couper « van der Berg » produirait des auteurs faux, ce que
        la regle entiere cherche a empecher.
        """
        m = parser_work_openalex(
            {
                "display_name": "T",
                "authorships": [{"author": {"display_name": "Pieter van der Berg"}}],
            }
        )
        assert m is not None and m.authors == "Pieter van der Berg"


@pytest.mark.asyncio
async def test_openalex_ne_leve_jamais(monkeypatch):
    """Un resolveur muet laisse un champ vide, il ne casse pas l'appel."""

    async def _boum(*_a, **_k):
        raise httpx.ConnectError("reseau coupe")

    monkeypatch.setattr(httpx.AsyncClient, "get", _boum)
    assert await chercher_par_doi("10.1038/nrn2762") is None
    assert await chercher_par_doi(None) is None


class TestResoudre:
    """L'origine demandee repond, ou dit pourquoi elle ne peut pas."""

    @pytest.mark.asyncio
    async def test_createur_ne_resout_rien(self):
        assert await metadonnees_source.resoudre("createur", url="https://x.test", doi=None) is None

    @pytest.mark.asyncio
    async def test_page_sans_url_nomme_la_sortie(self):
        with pytest.raises(metadonnees_source.OrigineIndisponibleError) as capture:
            await metadonnees_source.resoudre("page", url="", doi="10.1/x")
        assert "crossref" in str(capture.value)

    @pytest.mark.asyncio
    async def test_crossref_sans_doi_nomme_la_sortie(self):
        with pytest.raises(metadonnees_source.OrigineIndisponibleError) as capture:
            await metadonnees_source.resoudre("crossref", url="https://x.test", doi=None)
        assert "page" in str(capture.value)

    @pytest.mark.asyncio
    async def test_une_page_qui_refuse_la_lecture_nomme_les_autres_origines(self, monkeypatch):
        """Un refus qui ne dit pas par ou sortir fait boucler le modele."""

        async def _bloquee(_url):
            return ExtractedMetadata(access_blocked=True)

        monkeypatch.setattr(metadonnees_source, "scraper_la_page", _bloquee)
        with pytest.raises(metadonnees_source.OrigineIndisponibleError) as capture:
            await metadonnees_source.resoudre("page", url="https://mur.test", doi=None)
        message = str(capture.value)
        assert "crossref" in message and "createur" in message

    @pytest.mark.asyncio
    async def test_une_origine_inconnue_liste_les_connues(self):
        with pytest.raises(metadonnees_source.OrigineIndisponibleError) as capture:
            await metadonnees_source.resoudre("wikipedia", url=None, doi=None)
        assert "openalex" in str(capture.value)


class TestEcarts:
    """Ce que l'appelant proposait et que le resolveur contredit."""

    def test_une_valeur_contredite_est_signalee(self):
        retenu = ExtractedMetadata(title="Le vrai titre")
        trouves = metadonnees_source.ecarts(retenu, {"title": "Un titre plausible"})
        assert len(trouves) == 1
        assert trouves[0].propose == "Un titre plausible"
        assert trouves[0].retenu == "Le vrai titre"

    def test_un_champ_que_le_resolveur_ne_remplit_pas_n_est_pas_un_ecart(self):
        """Un vide n'est pas une contradiction : il n'y a rien a signaler."""
        assert metadonnees_source.ecarts(ExtractedMetadata(), {"title": "Un titre"}) == []

    def test_sans_resolveur_il_n_y_a_pas_d_ecart(self):
        assert metadonnees_source.ecarts(None, {"title": "Un titre"}) == []


@pytest.fixture
def _resolveur(monkeypatch):
    """Toute origine rend le meme work, sans reseau."""

    async def _resoudre(origine, *, url, doi):
        if origine == MetadataOrigin.CREATEUR.value:
            return None
        return parser_work_openalex(_WORK)

    monkeypatch.setattr(metadonnees_source, "resoudre", _resoudre)


@pytest.fixture
def _existence(monkeypatch):
    """Les adresses de test existent : ce fichier n'eprouve pas la verification."""
    from app.mcp_server import tools_write

    async def _existe(_url, _doi=None):
        return None

    monkeypatch.setattr(tools_write, "verifier_que_la_source_existe", _existe)


class TestAddSource:
    @pytest.mark.asyncio
    async def test_sans_origine_l_appel_est_refuse(self, db_session, test_user, _existence):
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        with pytest.raises(ToolError, match="metadata_from"):
            await add_source(
                db_session,
                test_user,
                metadata_from="",
                card_slug="fiche-origine",
                url="https://exemple.test/a",
                title="Un titre que le modele a tape",
            )

    @pytest.mark.asyncio
    async def test_le_resolveur_ecrit_le_titre_pas_l_appelant(
        self, db_session, test_user, _resolveur, _existence
    ):
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        resultat = await add_source(
            db_session,
            test_user,
            metadata_from="openalex",
            card_slug="fiche-origine",
            doi="10.1038/nrn2762",
            title="Un titre invente",
        )
        assert resultat["title"] == "Sleep and memory consolidation"
        assert resultat["metadata_origin"] == "openalex"

    @pytest.mark.asyncio
    async def test_l_ecart_est_rendu_a_l_appelant(
        self, db_session, test_user, _resolveur, _existence
    ):
        """Un modele qui ne voit pas l'ecart le refera au tour suivant."""
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        resultat = await add_source(
            db_session,
            test_user,
            metadata_from="openalex",
            card_slug="fiche-origine",
            doi="10.1038/nrn2762",
            title="Un titre invente",
        )
        ecarts = resultat["metadata_ecarts"]
        assert [e["champ"] for e in ecarts] == ["title"]
        assert ecarts[0]["retenu"] == "Sleep and memory consolidation"

    @pytest.mark.asyncio
    async def test_createur_ecrit_ce_qu_on_lui_passe(self, db_session, test_user, _existence):
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        resultat = await add_source(
            db_session,
            test_user,
            metadata_from="createur",
            card_slug="fiche-origine",
            url="https://exemple.test/dicte",
            title="Ce que le createur a sous les yeux",
        )
        assert resultat["title"] == "Ce que le createur a sous les yeux"
        assert resultat["metadata_origin"] == "createur"


class TestUpdateSource:
    @pytest.mark.asyncio
    async def test_corriger_un_titre_sans_origine_est_refuse(
        self, db_session, test_user, _existence
    ):
        """Sinon `update_source` rouvre en deux appels ce que `add_source` ferme."""
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        src = await add_source(
            db_session,
            test_user,
            metadata_from="createur",
            card_slug="fiche-origine",
            url="https://exemple.test/a",
            title="Titre de depart",
        )
        with pytest.raises(ToolError, match="metadata_from"):
            await update_source(
                db_session, test_user, source_id=src["id"], title="Un titre invente"
            )

    @pytest.mark.asyncio
    async def test_corriger_une_annotation_ne_demande_pas_d_origine(
        self, db_session, test_user, _existence
    ):
        """`annotation` et `stance` sont des choix editoriaux, pas des faits."""
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        src = await add_source(
            db_session,
            test_user,
            metadata_from="createur",
            card_slug="fiche-origine",
            url="https://exemple.test/a",
            title="Titre de depart",
        )
        resultat = await update_source(
            db_session, test_user, source_id=src["id"], annotation="Ce que j'en pense"
        )
        assert resultat["annotation"] == "Ce que j'en pense"

    @pytest.mark.asyncio
    async def test_une_origine_muette_fait_echouer_plutot_que_de_ne_rien_faire(
        self, db_session, test_user, _existence, monkeypatch
    ):
        """Une correction sans effet et sans message est pire qu'un refus."""
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        src = await add_source(
            db_session,
            test_user,
            metadata_from="createur",
            card_slug="fiche-origine",
            url="https://exemple.test/a",
            title="Titre de depart",
        )

        async def _muet(origine, *, url, doi):
            return ExtractedMetadata()

        monkeypatch.setattr(metadonnees_source, "resoudre", _muet)
        with pytest.raises(ToolError, match="ne rend rien"):
            await update_source(
                db_session,
                test_user,
                source_id=src["id"],
                metadata_from="page",
                title="Un titre invente",
            )

    @pytest.mark.asyncio
    async def test_le_resolveur_reecrit_le_titre(
        self, db_session, test_user, _existence, _resolveur
    ):
        await create_card(db_session, test_user, slug="fiche-origine", title="Fiche origine")
        src = await add_source(
            db_session,
            test_user,
            metadata_from="createur",
            card_slug="fiche-origine",
            url="https://exemple.test/a",
            doi="10.1038/nrn2762",
            title="Titre de depart",
        )
        await update_source(
            db_session,
            test_user,
            source_id=src["id"],
            metadata_from="openalex",
            title="Un titre invente",
        )
        from uuid import UUID

        lu = await db_session.get(Source, UUID(src["id"]))
        assert lu is not None
        assert lu.title == "Sleep and memory consolidation"
        assert lu.metadata_origin == "openalex"


class TestAddSourcesBatch:
    @pytest.mark.asyncio
    async def test_une_entree_sans_origine_part_dans_failed(
        self, db_session, test_user, _existence
    ):
        """Le lot continue sans elle : une entree fautive n'annule pas les autres."""
        await create_card(db_session, test_user, slug="fiche-lot", title="Fiche lot")
        resultat = await add_sources_batch(
            db_session,
            test_user,
            card_slug="fiche-lot",
            sources=[
                {"url": "https://exemple.test/sans-origine", "title": "A"},
                {"metadata_from": "createur", "url": "https://exemple.test/avec", "title": "B"},
            ],
        )
        assert len(resultat["failed"]) == 1
        assert "metadata_from" in resultat["failed"][0]["reason"]
        assert len(resultat["created"]) == 1

    @pytest.mark.asyncio
    async def test_deux_entrees_peuvent_porter_deux_origines(
        self, db_session, test_user, _existence, _resolveur
    ):
        """Un lot melant articles a DOI et pages web n'a pas a etre coupe en deux."""
        await create_card(db_session, test_user, slug="fiche-lot", title="Fiche lot")
        resultat = await add_sources_batch(
            db_session,
            test_user,
            card_slug="fiche-lot",
            sources=[
                {
                    "metadata_from": "openalex",
                    "doi": "10.1038/nrn2762",
                    "url": "https://exemple.test/un",
                },
                {
                    "metadata_from": "createur",
                    "url": "https://exemple.test/deux",
                    "title": "Dicte par le createur",
                },
            ],
        )
        assert resultat["failed"] == []
        titres = [c["title"] for c in resultat["created"]]
        assert "Sleep and memory consolidation" in titres
        assert "Dicte par le createur" in titres


class TestApprobation:
    """`createur` est la porte de sortie legitime, et elle doit se voir.

    Sans approbation, un agent s'y rabat des qu'un resolveur reste muet, et la
    regle entiere se vide de son effet.
    """

    def test_createur_demande_une_approbation(self):
        assert philum.est_sensible("add_source", {"metadata_from": "createur"}) is True
        assert philum.est_sensible("update_source", {"metadata_from": "createur"}) is True

    def test_un_resolveur_n_en_demande_pas(self):
        assert philum.est_sensible("add_source", {"metadata_from": "openalex"}) is False
        assert philum.est_sensible("update_source", {"metadata_from": "page"}) is False

    def test_un_lot_qui_contient_une_entree_createur_est_sensible(self):
        sensible = philum.est_sensible(
            "add_sources_batch",
            {"sources": [{"metadata_from": "crossref"}, {"metadata_from": "createur"}]},
        )
        assert sensible is True

    def test_un_lot_entierement_resolu_ne_l_est_pas(self):
        sensible = philum.est_sensible(
            "add_sources_batch",
            {"sources": [{"metadata_from": "crossref"}, {"metadata_from": "openalex"}]},
        )
        assert sensible is False


def test_le_schema_expose_les_origines():
    """Le modele lit les valeurs acceptees dans le schema, pas dans le prompt."""
    schema = next(o.parameters for o in philum.philum_tools() if o.name == "add_source")
    assert schema["properties"]["metadata_from"]["enum"] == [e.value for e in MetadataOrigin]
    assert "metadata_from" in schema["required"]
