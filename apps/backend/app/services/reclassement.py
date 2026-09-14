"""Reclasser des passages pour une question avec un modele de reclassement.

Etude du 2026-09-14 : les outils les mieux notes classent en etages. Un filet
large (rangs des moteurs), un premier tri par proximite de sens (embeddings,
qui comparent deux vecteurs calcules separement), puis un reclasseur qui lit la
question et le passage ensemble et juge plus finement (Consensus, Ai2 Scholar
QA, Scira avec Cohere, Khoj avec un cross-encoder).

Philum vise Jina Reranker : multilingue, et gratuit sans carte bancaire pour
commencer (releve du 2026-09-14). Sans cle, ou en panne, rien n'est reclasse et
la recherche garde son ordre par le sens : meme contrat que `embeddings`, la
couche ne leve jamais.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MODELE_RECLASSEMENT = "jina-reranker-v3.5"
_URL = "https://api.jina.ai/v1/rerank"
_TIMEOUT = 30.0

#: Passages envoyes par appel. Borne reseau, pas editoriale : un echec ne coute
#: qu'un lot, et la requete reste de taille raisonnable. Meme valeur que les lots
#: d'embeddings.
_TAILLE_LOT = 64


def reclasseur_disponible() -> bool:
    return bool(get_settings().jina_api_key.strip())


async def reclasser(question: str, textes: list[str]) -> list[float] | None:
    """La pertinence de chaque texte pour la question, dans l'ordre des textes. None si impossible.

    Tout ou rien, comme `embeddings.embed` : une liste trouee obligerait chaque
    appelant a recoudre les scores avec les textes.
    """
    cle = get_settings().jina_api_key.strip()
    if not cle or not question.strip():
        return None
    if not textes:
        return []
    scores: list[float] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for debut in range(0, len(textes), _TAILLE_LOT):
                lot = textes[debut : debut + _TAILLE_LOT]
                reponse = await client.post(
                    _URL,
                    headers={"Authorization": f"Bearer {cle}"},
                    json={
                        "model": MODELE_RECLASSEMENT,
                        "query": question,
                        "documents": lot,
                        "top_n": len(lot),
                        "return_documents": False,
                    },
                )
                if reponse.status_code != 200:
                    logger.warning(
                        "Reclassement HTTP %s : %s", reponse.status_code, reponse.text[:200]
                    )
                    return None
                par_rang = {
                    int(r["index"]): float(r["relevance_score"])
                    for r in reponse.json().get("results") or []
                }
                if set(par_rang) != set(range(len(lot))):
                    logger.warning(
                        "Reclassement : %s scores pour %s passages", len(par_rang), len(lot)
                    )
                    return None
                scores += [par_rang[rang] for rang in range(len(lot))]
    except Exception as exc:  # noqa: BLE001  # le reclassement affine, il ne bloque jamais la recherche
        logger.warning("Reclassement impossible : %s", exc)
        return None
    return scores
