"""Recherche d'extraits par le sens.

Ce module est le lecteur qui manquait a `excerpt_indexing`. Les vecteurs
etaient calcules, tronques, normalises et ecrits a chaque modification
d'extrait, et **rien ne les relisait** : une depense a chaque indexation pour
zero usage, et une promesse d'accueil qu'il a fallu retirer faute de code
derriere.

Deux regles tenues ici, heritees du reste du projet :

- **« indisponible » n'est pas « aucun resultat ».** Sans service
  d'embeddings, la recherche ne rend pas une liste vide -- elle rend `None`, et
  l'ecran dit qu'elle ne peut pas repondre. Confondre les deux ferait conclure
  au lecteur que ses extraits ne parlent pas de ce qu'il cherche ;
- **on ne repond que sur ce qu'on possede.** Le filtre par proprietaire est
  dans la requete elle-meme, pas apres coup : un extrait vit dans une source
  qui vit dans une fiche qui a un·e propietaire, et une fiche privee n'a pas a
  se laisser deviner par similarite.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text

from app.core.config import get_settings
from app.services.embeddings import embed

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: En dessous, ce n'est plus une reponse mais du remplissage. Le seuil coupe le
#: bruit franc -- la requete qui ne rencontre rien dans le corpus doit rendre
#: une liste vide, pas les vingt extraits les moins eloignes. Il ne pretend pas
#: trancher la pertinence : c'est un plancher, pas un jugement, et il se
#: recalibrera sur des mesures le jour ou un corpus reel le permettra.
SIMILARITE_MINIMALE = 0.30

#: Un nom de schema Postgres, tel que `pg_catalog` le rend. Verifie malgre tout
#: avant interpolation : cette valeur entre dans du SQL textuel, et une regle
#: qui n'a jamais servi coute moins cher qu'une injection.
_SCHEMA_VALIDE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

_schema_vector: str | None = None


@dataclass(frozen=True)
class Resultat:
    """Un extrait retrouve, avec de quoi le situer sans seconde requete.

    La source et la fiche voyagent avec : un passage rendu seul obligerait le
    lecteur a cliquer pour savoir d'ou il vient, ce qui est exactement ce que
    la recherche est censee lui epargner.
    """

    excerpt_id: UUID
    text: str
    title: str | None
    context: str | None
    source_id: UUID
    source_title: str | None
    source_url: str
    card_id: UUID
    card_slug: str
    card_title: str
    similarite: float


def litteral_vecteur(vecteur: list[float]) -> str:
    """Le vecteur au format que pgvector accepte en parametre texte.

    Passer une liste Python ne suffit pas : le pilote l'enverrait en tableau
    de reels, que Postgres refuse de comparer a un `vector` sans conversion
    explicite. La forme textuelle se laisse convertir par un simple `CAST`.
    """
    return "[" + ",".join(repr(float(x)) for x in vecteur) + "]"


async def schema_du_type_vector(db: AsyncSession) -> str | None:
    """Le schema ou l'extension pgvector a atterri, ou `None` si absente.

    La migration 036 le notait deja : sur une base nue l'extension va dans
    `public`, sur Supabase elle est souvent deja installee dans `extensions`.
    L'operateur `<=>` et le type `vector` se resolvent par le `search_path` de
    la session, que personne ne garantit ici -- on les qualifie donc, et il
    faut pour cela savoir ou ils vivent. Retenu apres la premiere lecture : le
    schema d'une extension ne bouge pas sous les pieds d'un processus.
    """
    global _schema_vector
    if _schema_vector is not None:
        return _schema_vector
    ligne = (
        await db.execute(
            text(
                "SELECT n.nspname FROM pg_type t "
                "JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typname = 'vector'"
            )
        )
    ).first()
    if ligne is None:
        return None
    schema = str(ligne[0])
    if not _SCHEMA_VALIDE.match(schema):
        logger.warning("Schema pgvector inattendu, recherche desactivee : %r", schema)
        return None
    _schema_vector = schema
    return schema


def requete_sql(schema: str) -> str:
    """La requete de similarite, qualifiee par le schema de pgvector.

    `OPERATOR(schema.<=>)` et `schema.vector` evitent de dependre du
    `search_path` de la session. Aucun index n'est vise : la migration 036 a
    laisse la table sans index de similarite, un parcours sequentiel restant
    exact et rapide en dessous de quelques dizaines de milliers de vecteurs.
    """
    distance = f"em.embedding OPERATOR({schema}.<=>) CAST(:vecteur AS {schema}.vector)"
    return f"""
        SELECT
            e.id AS excerpt_id,
            e.text AS text,
            e.title AS title,
            e.context AS context,
            s.id AS source_id,
            s.title AS source_title,
            s.url AS source_url,
            c.id AS card_id,
            c.slug AS card_slug,
            c.title AS card_title,
            1 - ({distance}) AS similarite
        FROM excerpt_embeddings em
        JOIN source_excerpts e ON e.id = em.excerpt_id
        JOIN sources s ON s.id = e.source_id
        JOIN biblio_cards c ON c.id = s.biblio_card_id
        WHERE em.model = :modele
          AND c.user_id = :user_id
          AND c.deleted_at IS NULL
          AND s.deleted_at IS NULL
        ORDER BY {distance}
        LIMIT :limite
    """


async def rechercher(
    db: AsyncSession,
    user_id: UUID,
    requete: str,
    limite: int = 20,
) -> list[Resultat] | None:
    """Les extraits de `user_id` les plus proches de `requete`, ou `None`.

    `None` veut dire que la recherche n'a pas pu avoir lieu : service
    d'embeddings absent, injoignable, ou pgvector introuvable sur la base. Une
    liste vide veut dire que la recherche a eu lieu et n'a rien trouve. Les
    deux se disent differemment a l'ecran.
    """
    requete = requete.strip()
    if not requete:
        return []

    vecteurs = await embed([requete])
    if not vecteurs:
        return None

    schema = await schema_du_type_vector(db)
    if schema is None:
        logger.warning("pgvector introuvable : recherche par le sens indisponible")
        return None

    lignes = await db.execute(
        text(requete_sql(schema)),
        {
            "vecteur": litteral_vecteur(vecteurs[0]),
            "modele": get_settings().embedding_model,
            "user_id": str(user_id),
            "limite": limite,
        },
    )
    return [
        Resultat(
            excerpt_id=ligne.excerpt_id,
            text=ligne.text,
            title=ligne.title,
            context=ligne.context,
            source_id=ligne.source_id,
            source_title=ligne.source_title,
            source_url=ligne.source_url,
            card_id=ligne.card_id,
            card_slug=ligne.card_slug,
            card_title=ligne.card_title,
            similarite=float(ligne.similarite),
        )
        for ligne in lignes
        if float(ligne.similarite) >= SIMILARITE_MINIMALE
    ]
