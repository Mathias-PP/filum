"""Calcul des vecteurs d'extraits.

Meme contrat que `app.services.llm` : la couche ne leve jamais et rend None
quand elle est desactivee ou qu'elle echoue. Un vecteur manquant se traduit
par une absence de ligne dans `excerpt_embeddings`, jamais par une erreur
remontee a l'utilisateur.

Le point d'entree est le meme que celui du chat (`litellm_base_url`), au
format OpenAI `/embeddings`. Viser un fournisseur different ne demande donc
aucune modification ici, seulement une variable d'environnement.
"""

from __future__ import annotations

import hashlib
import logging
import math
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.models.excerpt_embedding import EMBEDDING_DIM

if TYPE_CHECKING:
    from app.models.source_excerpt import SourceExcerpt

logger = logging.getLogger(__name__)

_TIMEOUT = 30.0
#: Au-dela, on paie un vecteur pour un texte dont la fin ne pese deja plus
#: rien. Un extrait est un passage cite, pas un chapitre.
_MAX_CHARS = 8_000
#: Bornes du lot. Assez grand pour que la reindexation d'une fiche tienne en
#: un appel, assez petit pour qu'un echec ne coute pas tout le lot.
_TAILLE_LOT = 64


def url_embeddings(base: str) -> str:
    """L'adresse `embeddings` derriere une racine configuree.

    Meme regle que `llm.url_chat` : un proxy s'annonce par son hote nu et
    attend qu'on prefixe `/v1`, un fournisseur vise directement s'annonce
    deja par un chemin complet.
    """
    base = base.rstrip("/")
    chemin = urlparse(base).path
    return f"{base}/embeddings" if chemin else f"{base}/v1/embeddings"


def texte_a_embedder(excerpt: SourceExcerpt) -> str:
    """Ce qui part au modele pour un extrait donne.

    L'intitule et la mise en situation sont joints au verbatim. Un passage
    voyage seul et ne se suffit pas toujours : « ce modele distingue trois
    composantes » ne dit ni de quel modele ni de quel texte il s'agit, et le
    vecteur du verbatim seul ne rattrape pas ce que la phrase ne contient pas.

    Cette composition n'est jamais affichee ni exportee : elle ne sert qu'a
    calculer un vecteur. La regle qui interdit de meler prose generee et
    verbatim porte sur ce qu'on donne a lire, pas sur ce qu'on donne a
    compter.
    """
    morceaux = [excerpt.title, excerpt.context, excerpt.text]
    return "\n".join(m.strip() for m in morceaux if m and m.strip())[:_MAX_CHARS]


def empreinte(texte: str) -> str:
    """SHA-256 du texte soumis, pour savoir si un vecteur est perime."""
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def tronquer_et_normaliser(vecteur: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    """Ramene un vecteur a `dim` dimensions, de norme 1.

    `gemini-embedding-001` rend 3072 dimensions et est entraine en Matryoshka :
    les premieres portent l'essentiel du signal, couper a 768 est prevu par le
    modele. La renormalisation qui suit n'est pas cosmetique : une troncature
    ampute une part de la norme, et deux vecteurs de normes differentes ne se
    comparent plus par distance euclidienne.
    """
    coupe = vecteur[:dim]
    norme = math.sqrt(sum(x * x for x in coupe))
    if norme == 0:
        return coupe
    return [x / norme for x in coupe]


async def embed(textes: list[str]) -> list[list[float]] | None:
    """Les vecteurs de plusieurs textes, dans l'ordre. Rend None si echec.

    Un echec partiel n'existe pas ici : soit le lot entier revient, soit rien.
    Rendre une liste trouee obligerait chaque appelant a la recoudre avec les
    entrees, et la premiere erreur d'alignement attribuerait le vecteur d'un
    passage a un autre.
    """
    if not textes:
        return []
    settings = get_settings()
    base = settings.litellm_base_url.strip()
    if not base:
        return None

    vecteurs: list[list[float]] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            for debut in range(0, len(textes), _TAILLE_LOT):
                lot = textes[debut : debut + _TAILLE_LOT]
                r = await client.post(
                    url_embeddings(base),
                    json={"model": settings.embedding_model, "input": lot},
                    headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
                )
                if r.status_code != 200:
                    logger.warning("Embeddings HTTP %s: %s", r.status_code, r.text[:200])
                    return None
                donnees = r.json()["data"]
                if len(donnees) != len(lot):
                    logger.warning("Embeddings: %s vecteurs pour %s textes", len(donnees), len(lot))
                    return None
                # L'ordre de `data` n'est pas garanti par la specification,
                # seul `index` l'est. Trier coute une comparaison et evite
                # d'attribuer un vecteur au mauvais passage.
                #
                # `index` peut manquer : Gemini serialise en protobuf, ou une
                # valeur egale au defaut du type est elidee, si bien que le
                # premier element d'un lot n'a jamais de champ `index`. Exiger
                # la cle faisait echouer tout appel, et l'indexation entiere
                # avec. Sa position dans le tableau en tient lieu.
                for _, element in sorted(enumerate(donnees), key=lambda p: p[1].get("index", p[0])):
                    vecteurs.append(tronquer_et_normaliser(element["embedding"]))
    except Exception as e:
        logger.warning("Embeddings failed: %s", e)
        return None
    return vecteurs
