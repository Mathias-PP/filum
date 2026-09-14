"""La recherche d'une sous-question : collecte large, passages, suivi, arret a saturation."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.extractors import body_links, recherche_litterature, retraction
from app.extractors.recherche_litterature import Candidate
from app.extractors.retraction import RetractionResult, RetractionStatus
from app.services import embeddings, excerpt_insertion, passages_candidats
from app.services.fusion_candidates import identite
from app.services.recherche_approfondie import (
    NUANCE,
    REPONSE,
    SourceTrouvee,
    estimer_restantes,
    nature_reconnue,
    pages,
    rechercher_sous_question,
)

SOUS_QUESTION = "Quel effet de la taxe sur le transport ?"
CONTRADICTION = "Limites de la taxe dans l'industrie"
TRANSPORT = "Les emissions du transport ont baisse de 11 % apres la taxe."
INDUSTRIE = "Les exemptions accordees a l'industrie ont limite l'effet de la taxe."
HORS_SUJET = "Le prix du pain a double au printemps."


def _vecteur(texte: str) -> list[float]:
    t = texte.lower()
    v = [1.0 if "transport" in t else 0.0, 1.0 if "industri" in t else 0.0]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.fixture
def pages_web(monkeypatch):
    """Le texte de chaque adresse ; une adresse absente est illisible. Note les lectures."""
    textes: dict[str, str] = {}
    lues: list[str] = []

    async def texte_de_page(url):
        lues.append(url)
        return textes.get(url, ""), False, True

    async def embed(liste):
        return [_vecteur(t) for t in liste]

    async def aucune_retractation(doi):
        return RetractionResult(status=RetractionStatus.NONE)

    async def aucun_voisin(doi, **_):
        return []

    async def aucun_lien(url):
        return []

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", texte_de_page)
    monkeypatch.setattr(embeddings, "embed", embed)
    monkeypatch.setattr(passages_candidats, "TAILLE_PASSAGE", 60)
    monkeypatch.setattr(retraction, "check_retraction", aucune_retractation)
    monkeypatch.setattr(recherche_litterature, "voisinage_openalex", aucun_voisin)
    monkeypatch.setattr(body_links, "liens_de_la_page", aucun_lien)
    return textes, lues


def _corpus(*reponses: list[str], appels: list[tuple[str, str]] | None = None):
    """Un corpus par liste d'adresses ; chaque appel rend des candidates neuves."""

    def moteur(nom: str, adresses: list[str]):
        async def chercher(requete):
            if appels is not None:
                appels.append((nom, requete))
            return [
                Candidate(url=a, titre=a.rsplit("/", 1)[-1], famille="web", sources=[nom])
                for a in adresses
            ]

        return chercher

    return {f"moteur{rang}": moteur(f"moteur{rang}", liste) for rang, liste in enumerate(reponses)}


@pytest.mark.asyncio
async def test_chaque_formulation_part_vers_tous_les_corpus_et_les_listes_sont_fusionnees(
    pages_web,
):
    textes, _lues = pages_web
    textes["https://a.test/a"] = TRANSPORT
    appels: list[tuple[str, str]] = []
    corpus = _corpus(["https://a.test/a"], ["https://a.test/a", "https://b.test/b"], appels=appels)

    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe transport", "carbon tax transport"], [CONTRADICTION], corpus=corpus
    )

    assert sorted(appels) == sorted(
        (nom, q)
        for q in ("taxe transport", "carbon tax transport", CONTRADICTION)
        for nom in ("moteur0", "moteur1")
    )
    assert recherche.journal.requetes == 6
    assert [s.url_lue for s in recherche.sources] == ["https://a.test/a"]
    trouvee = recherche.sources[0].candidate
    assert trouvee.sources == ["moteur0", "moteur1"]
    assert any("carbon tax transport" in r for r in trouvee.raisons)


@pytest.mark.asyncio
async def test_un_passage_repond_a_la_sous_question_ou_nuance_par_la_contradiction(pages_web):
    textes, _lues = pages_web
    textes["https://a.test/a"] = f"{TRANSPORT} {INDUSTRIE}"
    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=_corpus(["https://a.test/a"])
    )
    roles = {p.role: p.texte for p in recherche.sources[0].passages}
    assert "transport" in roles[REPONSE] and "industrie" in roles[NUANCE]


@pytest.mark.asyncio
async def test_la_lecture_s_arrete_au_premier_lot_lisible_sans_source_nouvelle(pages_web):
    textes, lues = pages_web
    textes["https://a.test/1"] = TRANSPORT
    textes["https://a.test/2"] = HORS_SUJET
    textes["https://a.test/3"] = TRANSPORT
    corpus = _corpus(["https://a.test/1", "https://a.test/2", "https://a.test/3"])

    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=corpus, lot=1
    )

    assert lues == ["https://a.test/1", "https://a.test/2"]
    assert recherche.journal.lues == 2
    assert recherche.journal.courbe == [1, 1]


@pytest.mark.asyncio
async def test_une_page_illisible_n_arrete_pas_la_lecture(pages_web):
    textes, _lues = pages_web
    textes["https://a.test/2"] = TRANSPORT
    corpus = _corpus(["https://a.test/1", "https://a.test/2"])
    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=corpus, lot=1
    )
    assert [s.url_lue for s in recherche.sources] == ["https://a.test/2"]
    assert recherche.journal.illisibles == 1


@pytest.mark.asyncio
async def test_les_sources_pertinentes_menent_a_leurs_citants_et_aux_liens_de_leurs_pages(
    pages_web, monkeypatch
):
    textes, _lues = pages_web
    textes["https://doi.org/10.1/pivot"] = TRANSPORT
    textes["https://blog.test/billet"] = f"Sur le transport : {TRANSPORT}"
    textes["https://doi.org/10.1/citant"] = f"Confirmation pour le transport. {TRANSPORT}"
    textes["https://rapport.test/cite"] = f"Rapport transport. {TRANSPORT}"

    async def voisins(doi, *, sens, **_):
        if doi == "10.1/pivot" and sens == "citants":
            return [
                Candidate(
                    url="https://doi.org/10.1/citant",
                    titre="Citant",
                    famille="litterature",
                    doi="10.1/citant",
                )
            ]
        return []

    async def liens(url):
        if url == "https://blog.test/billet":
            return [body_links.ImportedRef(url="https://rapport.test/cite", raw_text="le rapport")]
        return []

    monkeypatch.setattr(recherche_litterature, "voisinage_openalex", voisins)
    monkeypatch.setattr(body_links, "liens_de_la_page", liens)
    corpus = {
        "litterature": _doi_corpus("https://doi.org/10.1/pivot", "10.1/pivot"),
        "web": _corpus(["https://blog.test/billet"])["moteur0"],
    }

    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=corpus
    )

    par_url = {s.url_lue: s for s in recherche.sources}
    assert par_url["https://doi.org/10.1/citant"].tour == 2
    assert par_url["https://doi.org/10.1/citant"].candidate.raisons[0].startswith("cite « ")
    assert par_url["https://rapport.test/cite"].candidate.raisons[0].startswith("lien dans « ")
    assert recherche.journal.pertinentes_par_tour[:2] == [2, 2]
    assert "plus aucune candidate" in recherche.journal.arret


def _doi_corpus(url: str, doi: str):
    async def chercher(requete):
        return [
            Candidate(url=url, titre="Pivot", famille="litterature", sources=["openalex"], doi=doi)
        ]

    return chercher


@pytest.mark.asyncio
async def test_un_tour_de_suivi_sans_source_pertinente_nouvelle_arrete_la_recherche(
    pages_web, monkeypatch
):
    textes, _lues = pages_web
    textes["https://doi.org/10.1/pivot"] = TRANSPORT
    textes["https://doi.org/10.1/voisin"] = HORS_SUJET

    async def voisins(doi, **_):
        return [
            Candidate(
                url="https://doi.org/10.1/voisin",
                titre="V",
                famille="litterature",
                doi="10.1/voisin",
            )
        ]

    monkeypatch.setattr(recherche_litterature, "voisinage_openalex", voisins)
    recherche = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus={"litterature": _doi_corpus("https://doi.org/10.1/pivot", "10.1/pivot")},
    )
    assert recherche.journal.pertinentes_par_tour == [1, 0]
    assert recherche.journal.arret.startswith("saturation : le tour 2")


@pytest.mark.asyncio
async def test_le_delai_atteint_est_dit_et_jamais_pris_pour_une_saturation(pages_web):
    textes, _lues = pages_web
    textes["https://a.test/a"] = TRANSPORT
    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=_corpus(["https://a.test/a"]), delai=0
    )
    assert recherche.sources == []
    assert "delai" in recherche.journal.arret and "pas sature" in recherche.journal.arret


@pytest.mark.asyncio
async def test_une_source_deja_posee_rend_son_identifiant_et_une_exclue_n_est_jamais_lue(pages_web):
    textes, lues = pages_web
    textes["https://a.test/a"] = TRANSPORT
    textes["https://b.test/b"] = TRANSPORT
    a = Candidate(url="https://a.test/a", titre=None, famille="")
    b = Candidate(url="https://b.test/b", titre=None, famille="")
    recherche = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus=_corpus(["https://a.test/a", "https://b.test/b"]),
        deja={identite(a): "source-1"},
        exclure=frozenset({identite(b)}),
    )
    assert "https://b.test/b" not in lues
    assert recherche.sources[0].source_id == "source-1"
    assert recherche.sources[0].en_dict()["source_id"] == "source-1"


@pytest.mark.asyncio
async def test_une_source_retractee_le_dit(pages_web, monkeypatch):
    textes, _lues = pages_web
    textes["https://doi.org/10.1/pivot"] = TRANSPORT

    async def retractee(doi):
        return RetractionResult(status=RetractionStatus.RETRACTED)

    monkeypatch.setattr(retraction, "check_retraction", retractee)
    recherche = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus={"litterature": _doi_corpus("https://doi.org/10.1/pivot", "10.1/pivot")},
        expansion=False,
    )
    assert recherche.sources[0].retractation == "retracted"


@pytest.mark.asyncio
async def test_un_corpus_en_panne_est_note_sans_empecher_les_autres(pages_web):
    textes, _lues = pages_web
    textes["https://a.test/a"] = TRANSPORT

    async def panne(requete):
        raise RuntimeError("quota")

    corpus = {"panne": panne, **_corpus(["https://a.test/a"])}
    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=corpus
    )
    assert recherche.journal.corpus_muets == ["panne"]
    assert len(recherche.sources) == 1


@pytest.mark.parametrize("courbe", [[], [0, 0], [1, 2, 3, 4]])
def test_sans_ralentissement_visible_aucune_estimation(courbe):
    assert estimer_restantes(courbe) is None


@pytest.mark.parametrize(("courbe", "attendu"), [([1, 2, 2, 2], 0.0), ([2, 3, 3, 4], 0.5)])
def test_la_courbe_de_decouverte_estime_ce_qui_reste(courbe, attendu):
    assert estimer_restantes(courbe) == pytest.approx(attendu)


def test_les_pages_ne_coupent_jamais_une_source():
    def source(n: int) -> SourceTrouvee:
        return SourceTrouvee(
            candidate=Candidate(url=f"https://a.test/{n}", titre=None, famille="web"),
            url_lue=f"https://a.test/{n}",
            passages=[passages_candidats_passage("x" * 200)],
            tour=1,
            texte_complet=True,
        )

    sources = [source(n) for n in range(3)]
    assert [len(p) for p in pages(sources, budget=10)] == [1, 1, 1]
    assert [len(p) for p in pages(sources, budget=100_000)] == [3]


def passages_candidats_passage(texte: str):
    from app.services.recherche_approfondie import Passage

    return Passage(texte, REPONSE, 0.9)


@pytest.mark.asyncio
async def test_une_version_en_acces_libre_passe_avant_le_resume_de_l_editeur(
    pages_web, monkeypatch
):
    _textes, lues = pages_web

    async def texte_de_page(url):
        lues.append(url)
        if url == "https://oa.test/texte":
            return f"Introduction. {TRANSPORT}", False, True
        return TRANSPORT, True, False

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", texte_de_page)

    async def chercher(requete):
        return [
            Candidate(
                url="https://doi.org/10.1/ferme",
                titre="Article payant",
                famille="litterature",
                doi="10.1/ferme",
                acces_libre_url="https://oa.test/texte",
            )
        ]

    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus={"openalex": chercher}, expansion=False
    )
    assert recherche.sources[0].url_lue == "https://oa.test/texte"
    assert recherche.sources[0].texte_complet
    assert lues == ["https://oa.test/texte"]


@pytest.mark.asyncio
async def test_sans_texte_entier_le_texte_le_plus_long_est_garde(pages_web, monkeypatch):
    async def texte_de_page(url):
        if url == "https://oa.test/court":
            return TRANSPORT, False, False
        return f"{TRANSPORT} {INDUSTRIE}", True, False

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", texte_de_page)

    async def chercher(requete):
        return [
            Candidate(
                url="https://doi.org/10.1/ferme",
                titre="Article",
                famille="litterature",
                acces_libre_url="https://oa.test/court",
            )
        ]

    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus={"openalex": chercher}, expansion=False
    )
    assert recherche.sources[0].url_lue == "https://doi.org/10.1/ferme"
    assert not recherche.sources[0].texte_complet


@pytest.mark.asyncio
async def test_une_lecture_trop_lente_est_coupee_au_delai(pages_web, monkeypatch):
    async def lente(url):
        await asyncio.sleep(5)
        return TRANSPORT, False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", lente)
    debut = time.monotonic()
    recherche = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=_corpus(["https://a.test/a"]), delai=0.2
    )
    assert time.monotonic() - debut < 2
    assert recherche.journal.hors_delai == 1
    assert "delai" in recherche.journal.arret
    assert recherche.journal.en_dict()["candidates_coupees_par_le_delai"] == 1


@pytest.mark.asyncio
async def test_le_suivi_lit_d_abord_les_voisins_proches_de_la_sous_question(pages_web, monkeypatch):
    textes, lues = pages_web
    textes["https://doi.org/10.1/pivot"] = TRANSPORT
    textes["https://doi.org/10.1/proche"] = f"Resultat. {TRANSPORT}"
    textes["https://doi.org/10.1/loin"] = HORS_SUJET
    recu: dict[str, object] = {}

    async def voisins(doi, *, sens, requete=None, **_):
        recu[sens] = requete
        if doi == "10.1/pivot" and sens == "citants":
            return [
                Candidate(
                    url="https://doi.org/10.1/loin",
                    titre="Le prix du pain",
                    famille="litterature",
                    doi="10.1/loin",
                ),
                Candidate(
                    url="https://doi.org/10.1/proche",
                    titre="Taxe et emissions du transport",
                    famille="litterature",
                    doi="10.1/proche",
                ),
            ]
        return []

    monkeypatch.setattr(recherche_litterature, "voisinage_openalex", voisins)
    recherche = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus={"litterature": _doi_corpus("https://doi.org/10.1/pivot", "10.1/pivot")},
        lot=1,
    )
    assert recu["citants"] == SOUS_QUESTION and recu["references"] is None
    assert lues.index("https://doi.org/10.1/proche") < lues.index("https://doi.org/10.1/loin")
    assert "https://doi.org/10.1/proche" in [s.url_lue for s in recherche.sources]


ARTICLE_UTILE = "https://www.nature.com/articles/b"
ARTICLE_HORS_SUJET = "https://www.nature.com/articles/a"
BLOG = ["https://blog.test/1", "https://blog.test/2", "https://blog.test/3"]


def _pages_melangees(textes: dict[str, str]) -> list[str]:
    textes[BLOG[0]] = TRANSPORT
    textes[BLOG[1]] = HORS_SUJET
    textes[ARTICLE_UTILE] = TRANSPORT
    textes[ARTICLE_HORS_SUJET] = HORS_SUJET
    textes[BLOG[2]] = TRANSPORT
    return [BLOG[0], BLOG[1], ARTICLE_UTILE, ARTICLE_HORS_SUJET, BLOG[2]]


@pytest.mark.asyncio
async def test_les_publications_et_institutions_sont_lues_d_abord_sans_exclure_les_autres(pages_web):
    textes, lues = pages_web
    adresses = _pages_melangees(textes)

    await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=_corpus(adresses), lot=1, expansion=False
    )

    # Chaque groupe s'arrete a sa propre saturation : les articles, puis les autres pages.
    assert lues == [ARTICLE_UTILE, ARTICLE_HORS_SUJET, BLOG[0], BLOG[1]]


@pytest.mark.asyncio
async def test_les_publications_et_institutions_sont_rendues_en_tete_sauf_toutes_a_egalite(pages_web):
    textes, _lues = pages_web
    corpus = _corpus(_pages_melangees(textes))

    publications = await rechercher_sous_question(
        SOUS_QUESTION, ["taxe"], [CONTRADICTION], corpus=corpus, expansion=False
    )
    egales = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus=corpus,
        expansion=False,
        publications_d_abord=False,
    )

    assert [s.url_lue for s in publications.sources] == [ARTICLE_UTILE, BLOG[0], BLOG[2]]
    assert publications.sources[0].en_dict()["reference"] == "article scientifique"
    assert "reference" not in publications.sources[1].en_dict()
    assert [s.url_lue for s in egales.sources] == [BLOG[0], ARTICLE_UTILE, BLOG[2]]


def test_la_nature_d_une_reference_se_lit_dans_les_faits():
    def candidate(url: str, famille: str = "web") -> Candidate:
        return Candidate(url=url, titre="t", famille=famille, sources=[famille])

    assert nature_reconnue(candidate("https://openalex.org/W1", "litterature")) == (
        "article scientifique"
    )
    assert nature_reconnue(candidate("https://arxiv.org/abs/2401.1")) == "preprint"
    assert nature_reconnue(candidate("https://www.who.int/news/x")) == "institution publique"
    assert nature_reconnue(candidate("https://cs.stanford.edu/x")) == "université ou école"
    assert nature_reconnue(candidate("https://blog.vendeur.com/agents")) is None


@pytest.mark.asyncio
async def test_chaque_passage_porte_un_id_unique_dans_l_ordre_rendu(pages_web):
    textes, _lues = pages_web
    recherche = await rechercher_sous_question(
        SOUS_QUESTION,
        ["taxe"],
        [CONTRADICTION],
        corpus=_corpus(_pages_melangees(textes)),
        expansion=False,
    )
    numeros = [p.numero for s in recherche.sources for p in s.passages]
    assert numeros == list(range(1, len(numeros) + 1))
    assert recherche.sources[0].en_dict()["passages"][0]["id"] == 1
