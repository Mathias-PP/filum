"""Mise a jour des vecteurs d'extraits.

Ce module decide *quoi* recalculer et l'ecrit ; le calcul lui-meme est dans
`app.services.embeddings`. Meme contrat qu'elle : rien ne leve. Un extrait sans
vecteur reste consultable, citable et verifiable ; il est seulement absent de la
recherche semantique tant qu'il n'a pas ete indexe.

L'indexation est idempotente et se rejoue sans dommage : c'est ce qui permet de
l'appeler apres n'importe quelle modification d'extrait sans tenir de file
d'attente.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.models.excerpt_embedding import ExcerptEmbedding
from app.services.embeddings import embed, empreinte, texte_a_embedder

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.source_excerpt import SourceExcerpt

logger = logging.getLogger(__name__)


def a_reindexer(
    excerpts: list[SourceExcerpt],
    empreintes_en_base: dict[UUID, str],
) -> list[SourceExcerpt]:
    """Les extraits dont le vecteur manque ou ne correspond plus au texte.

    Fonction pure, separee de l'ecriture : c'est la seule regle du module qui
    merite d'etre lue et testee seule. Un extrait est a reprendre si aucun
    vecteur n'existe pour lui, ou si l'empreinte rangee a cote de l'ancien
    vecteur differe de celle de son texte actuel.

    Un extrait dont il ne reste rien a soumettre est ignore : un vecteur de
    chaine vide ne veut rien dire et occuperait une ligne pour polluer les
    resultats.
    """
    a_faire = []
    for excerpt in excerpts:
        texte = texte_a_embedder(excerpt)
        if not texte.strip():
            continue
        if empreintes_en_base.get(excerpt.id) != empreinte(texte):
            a_faire.append(excerpt)
    return a_faire


async def indexer_extraits(db: AsyncSession, excerpts: list[SourceExcerpt]) -> int:
    """Recalcule les vecteurs manquants ou perimes. Rend le nombre ecrit.

    Ne commit pas : l'appelant decide quand valider, et le vecteur suit le sort
    de la transaction qui a modifie l'extrait.
    """
    if not excerpts:
        return 0
    modele = get_settings().embedding_model

    ids = [e.id for e in excerpts]
    lignes = await db.execute(
        select(ExcerptEmbedding.excerpt_id, ExcerptEmbedding.content_hash).where(
            ExcerptEmbedding.excerpt_id.in_(ids),
            ExcerptEmbedding.model == modele,
        )
    )
    empreintes_en_base = {ligne[0]: ligne[1] for ligne in lignes}

    a_faire = a_reindexer(excerpts, empreintes_en_base)
    if not a_faire:
        return 0

    textes = [texte_a_embedder(e) for e in a_faire]
    vecteurs = await embed(textes)
    if vecteurs is None:
        logger.info("Indexation abandonnee : le service d'embeddings n'a pas repondu")
        return 0

    # Supprimer puis reinserer plutot que d'ecrire un upsert : la contrainte
    # d'unicite porte sur `(excerpt_id, model)`, et la syntaxe `ON CONFLICT`
    # est propre a Postgres. Le couple tient dans la meme transaction, donc
    # personne ne voit l'intervalle sans vecteur.
    deja_vus = [e.id for e in a_faire if e.id in empreintes_en_base]
    if deja_vus:
        await db.execute(
            delete(ExcerptEmbedding).where(
                ExcerptEmbedding.excerpt_id.in_(deja_vus),
                ExcerptEmbedding.model == modele,
            )
        )

    for excerpt, texte, vecteur in zip(a_faire, textes, vecteurs, strict=True):
        db.add(
            ExcerptEmbedding(
                excerpt_id=excerpt.id,
                model=modele,
                dim=len(vecteur),
                content_hash=empreinte(texte),
                embedding=vecteur,
            )
        )
    await db.flush()
    return len(a_faire)


async def indexer_sans_bruit(db: AsyncSession, excerpts: list[SourceExcerpt]) -> int:
    """Indexe et valide, en avalant tout ce qui pourrait mal tourner.

    A appeler apres que l'extrait a ete valide, jamais dans la meme transaction
    que lui : un vecteur est un agrement, un extrait est le travail de
    l'utilisateur. Aucune panne d'indexation, y compris une erreur de schema,
    ne doit lui couter ce qu'il vient d'ecrire.

    Le `rollback` n'est pas une precaution de style : une exception SQLAlchemy
    laisse la session inutilisable, et la suite de la requete echouerait alors
    loin d'ici, sans rapport apparent.
    """
    try:
        nombre = await indexer_extraits(db, excerpts)
        if nombre:
            await db.commit()
        return nombre
    except Exception as e:
        logger.warning("Indexation des extraits abandonnee : %s", e)
        await db.rollback()
        return 0
