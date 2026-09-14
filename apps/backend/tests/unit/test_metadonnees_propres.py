"""Les metadonnees d'une source arrivent propres dans la fiche.

Mesures du 2026-09-13, constellation « endometriose » :
- un titre Crossref inscrit avec ses balises et ses sauts de ligne ;
- le dossier Inserm avec « https://www.facebook.com/inserm.fr » pour auteur ;
- des adresses PubMed refusees par intermittence (reCAPTCHA) alors que leur
  identifiant donne le DOI.
"""

from __future__ import annotations

import pytest

from app.extractors import url_extractor
from app.extractors.url_extractor import ExtractedMetadata, auteur_lisible, texte_sans_balises
from app.services import metadonnees_source

PAGE_INSERM = """<html><head>
<meta property="og:title" content="Endométriose">
<meta property="article:author" content="https://www.facebook.com/inserm.fr">
<script type="application/ld+json">{"@type": "Article", "headline": "Endométriose", "author": "Inserm"}</script>
</head><body><p>L'endométriose est une maladie gynécologique chronique fréquente.
Elle se caractérise par la présence de tissu semblable à la muqueuse utérine
en dehors de l'utérus, et touche une femme sur dix en âge de procréer.</p></body></html>"""


class _Reponse:
    status_code = 200

    def __init__(self, texte: str) -> None:
        self.text = texte
        self.headers = {"content-type": "text/html; charset=utf-8"}


class _Client:
    page = ""

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def get(self, url: str) -> _Reponse:
        return _Reponse(self.page)


def test_un_titre_crossref_perd_ses_balises_et_ses_sauts_de_ligne():
    meta = url_extractor._parse_crossref_work(
        {
            "title": [
                "<i>Fusobacterium</i>\n                    infection facilitates the development "
                "of endometriosis"
            ]
        }
    )
    assert meta.title == "Fusobacterium infection facilitates the development of endometriosis"


def test_les_entites_html_sont_decodees():
    assert texte_sans_balises("Smith &amp; Wesson <b>revisited</b>") == "Smith & Wesson revisited"


@pytest.mark.parametrize(
    "valeur", ["https://www.facebook.com/inserm.fr", "www.twitter.com/x", "@inserm", "", None]
)
def test_une_adresse_n_est_pas_un_auteur(valeur):
    assert auteur_lisible(valeur) is None


def test_un_nom_reste_un_auteur():
    assert auteur_lisible("  Camille Durand  ") == "Camille Durand"


@pytest.mark.asyncio
async def test_le_json_ld_nomme_l_auteur_quand_open_graph_donne_une_adresse(monkeypatch):
    _Client.page = PAGE_INSERM
    monkeypatch.setattr(url_extractor.httpx, "AsyncClient", _Client)

    meta = await url_extractor._html_scrape("https://www.inserm.fr/dossier/endometriose/")

    assert meta is not None
    assert meta.authors == "Inserm"


@pytest.mark.asyncio
async def test_une_page_pubmed_bloquee_est_resolue_par_son_doi(monkeypatch):
    async def bloquee(url):
        return ExtractedMetadata(access_blocked=True)

    async def doi(url):
        return "10.1093/humrep/dey117"

    async def notice(identifiant):
        assert identifiant == "10.1093/humrep/dey117"
        return ExtractedMetadata(title="Early life abuse and risk of endometriosis")

    monkeypatch.setattr(metadonnees_source, "metadonnees_de_la_page", bloquee)
    monkeypatch.setattr(metadonnees_source, "resolve_doi_from_pubmed", doi)
    monkeypatch.setattr(metadonnees_source, "crossref_lookup", notice)

    meta = await metadonnees_source.resoudre(
        "page", url="https://pubmed.ncbi.nlm.nih.gov/30016439/", doi=None
    )

    assert meta is not None and meta.title == "Early life abuse and risk of endometriosis"


@pytest.mark.asyncio
async def test_une_page_bloquee_hors_ncbi_reste_un_refus(monkeypatch):
    async def bloquee(url):
        return ExtractedMetadata(access_blocked=True)

    async def aucun_doi(url):
        return None

    monkeypatch.setattr(metadonnees_source, "metadonnees_de_la_page", bloquee)
    monkeypatch.setattr(metadonnees_source, "resolve_doi_from_pubmed", aucun_doi)

    with pytest.raises(metadonnees_source.OrigineIndisponibleError):
        await metadonnees_source.resoudre("page", url="https://editeur.test/article", doi=None)
