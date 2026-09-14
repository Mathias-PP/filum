"""Le serveur propose des passages exacts de la page, classes par le sens."""

from __future__ import annotations

import pytest

from app.mcp_server.tools_write import propose_passages
from app.services import embeddings, excerpt_insertion, passages_candidats
from app.services.passages_candidats import proposer, questions_avec_reserve

PAGE = (
    "La taxe carbone suedoise, introduite en 1991, a ete relevee plusieurs fois. "
    "Les emissions du transport ont baisse d'environ 11 % par rapport au scenario sans taxe."
    "\n\n"
    "Le secteur industriel beneficiait d'exemptions importantes jusqu'en 2018. "
    "Ces exemptions limitaient l'effet de la taxe sur l'industrie lourde."
)


def _vecteur(texte: str) -> list[float]:
    # Deux axes : transport et industrie. Assez pour classer sans reseau.
    t = texte.lower()
    v = [1.0 if "transport" in t else 0.0, 1.0 if "industri" in t else 0.0]
    norme = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / norme for x in v]


@pytest.fixture
def sens(monkeypatch):
    async def embed(textes):
        return [_vecteur(t) for t in textes]

    monkeypatch.setattr(embeddings, "embed", embed)
    monkeypatch.setattr(passages_candidats, "TAILLE_PASSAGE", 120)


@pytest.mark.asyncio
async def test_chaque_question_recoit_les_passages_les_plus_proches(sens):
    candidats = await proposer(PAGE, ["effet sur le transport", "effet sur l'industrie"])

    transport = [c for c in candidats if c.question == "effet sur le transport"]
    industrie = [c for c in candidats if c.question == "effet sur l'industrie"]
    assert transport and "transport" in transport[0].texte
    assert industrie and "industrie" in industrie[0].texte.lower()
    assert all(PAGE[c.debut : c.debut + len(c.texte)] == c.texte for c in candidats)
    assert {c.methode for c in candidats} == {"sens"}


@pytest.mark.asyncio
async def test_sans_embeddings_le_classement_par_mots_prend_le_relais(monkeypatch):
    async def embed(textes):
        return None

    monkeypatch.setattr(embeddings, "embed", embed)
    candidats = await proposer(PAGE, ["exemptions industrie lourde taxe"])
    assert candidats and candidats[0].methode == "mots"
    assert candidats[0].texte in PAGE


@pytest.mark.asyncio
async def test_une_source_dense_passe_en_extraction_exhaustive_sans_redite(sens):
    paragraphes = [
        f"Le transport routier du canton {i} a reduit ses emissions de {i} points cette annee."
        for i in range(10)
    ] + [
        f"L'industrie du canton {i} a obtenu une exemption de {i} points sur la meme periode."
        for i in range(10)
    ]
    page = "\n\n".join(paragraphes)

    candidats = await proposer(page, ["effet sur le transport", "effet sur l'industrie"])

    transport = [c for c in candidats if c.question == "effet sur le transport"]
    assert len(transport) == 10 > passages_candidats.PASSAGES_PAR_QUESTION
    textes = [c.texte for c in candidats]
    assert len(textes) == len(set(textes)) == 20


def test_la_question_de_reserve_est_ajoutee_d_office():
    assert questions_avec_reserve(["La taxe carbone a-t-elle reduit les emissions ?", " "]) == [
        "La taxe carbone a-t-elle reduit les emissions ?",
        "Limites, réserves ou résultats contraires : La taxe carbone a-t-elle reduit les emissions ?",
    ]
    assert questions_avec_reserve(["  "]) == []


@pytest.mark.asyncio
async def test_une_page_vide_ne_propose_rien():
    assert await proposer("", ["n'importe quoi"]) == []


@pytest.mark.asyncio
async def test_un_passage_trop_long_est_coupe_a_une_fin_de_phrase(monkeypatch):
    async def embed(textes):
        return [[1.0] for _ in textes]

    phrase = "La commune a vote le budget du port et de la halle aux grains. "
    page = phrase * 40
    monkeypatch.setattr(embeddings, "embed", embed)
    candidats = await proposer(page, ["budget communal"])
    assert candidats
    assert all(len(c.texte) <= 1000 and c.texte.endswith(".") for c in candidats)
    assert all(c.texte in page for c in candidats)


@pytest.mark.asyncio
async def test_l_outil_rend_les_passages_et_dit_quand_rien_ne_repond(
    db_session, test_user, monkeypatch, sens
):
    async def page(url):
        return PAGE, False, True

    monkeypatch.setattr(excerpt_insertion, "texte_de_page", page)

    rendu = await propose_passages(
        db_session, test_user, url="https://exemple.test/taxe", questions=["transport"]
    )
    assert rendu["passages"] and "transport" in rendu["passages"][0]["texte"]

    vide = await propose_passages(
        db_session, test_user, url="https://exemple.test/taxe", questions=["volcanologie"]
    )
    assert vide["passages"] == []
    assert "passe a la candidate suivante" in vide["message"]
