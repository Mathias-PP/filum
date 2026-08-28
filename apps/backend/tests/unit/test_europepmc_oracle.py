"""Le texte plein d'Europe PMC, quand l'editeur bloque le scraping."""

from __future__ import annotations

import pytest

from app.extractors.europepmc_oracle import pmcid_du_resultat, texte_du_xml


class TestPmcidDuResultat:
    def test_un_article_libre_donne_son_pmcid(self):
        charge = {
            "resultList": {
                "result": [{"pmcid": "PMC12016192", "fullTextIdList": {"fullTextId": ["PMC12016192"]}}]
            }
        }
        assert pmcid_du_resultat(charge) == "PMC12016192"

    def test_un_article_ferme_ne_donne_rien(self):
        # Un article ferme porte un `pmcid` sans que le texte plein soit
        # servi : s'y fier ferait demander un document qui repond 404.
        charge = {"resultList": {"result": [{"pmcid": "PMC999", "pmid": "27804847"}]}}
        assert pmcid_du_resultat(charge) is None

    def test_une_recherche_vide_ne_donne_rien(self):
        assert pmcid_du_resultat({"resultList": {"result": []}}) is None
        assert pmcid_du_resultat(None) is None


class TestTexteDuXml:
    def test_le_corps_est_aplati(self):
        xml = "<article><body><sec><p>Les mitochondries</p><p>produisent l'ATP.</p></sec></body></article>"
        assert texte_du_xml(xml) == "Les mitochondries produisent l'ATP."

    def test_la_bibliographie_est_ecartee(self):
        # Garder la bibliographie ferait passer pour retrouve un extrait qui
        # n'est que le titre d'un ouvrage cite.
        xml = (
            "<article><body><p>Le corps.</p>"
            "<ref-list><ref><article-title>Un titre cite</article-title></ref></ref-list>"
            "</body></article>"
        )
        texte = texte_du_xml(xml)
        assert "Le corps." in texte
        assert "Un titre cite" not in texte

    def test_un_article_sans_corps_ne_rend_rien(self):
        assert texte_du_xml("<article><front><title>Titre</title></front></article>") is None

    def test_un_xml_casse_ne_leve_pas(self):
        assert texte_du_xml("<article><body>pas ferme") is None


@pytest.mark.asyncio
async def test_un_doi_vide_n_appelle_pas_le_reseau():
    from app.extractors.europepmc_oracle import texte_europepmc

    assert await texte_europepmc(None) is None
    assert await texte_europepmc("   ") is None
