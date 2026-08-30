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
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import text

from app.core.config import get_settings
from app.services.embeddings import embed

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: En dessous, ce n'est plus une reponse mais du remplissage. La requete qui ne
#: rencontre rien dans le corpus doit rendre une liste vide, pas les vingt
#: extraits les moins eloignes.
#:
#: Mesure sur le corpus de production (51 extraits portant sur le sommeil,
#: `gemini-embedding-001` tronque a 768) : six questions etrangeres au corpus
#: -- meduses, cuivre, tarte tatin, guitare, fiscalite, hors-jeu -- plafonnent
#: entre 0.473 et 0.560, tandis que cinq questions du domaine s'echelonnent de
#: 0.651 a 0.828. Le plancher initial de 0.30 ne coupait donc rien : la tarte
#: tatin rendait cinq extraits sur les phases du sommeil.
#:
#: Ce seuil vaut pour ce modele. En changer decale toute l'echelle, y compris
#: les paliers de `proximite()` cote frontend, et demande de refaire la mesure.
SIMILARITE_MINIMALE = 0.60

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
    verified_status: str | None
    similarite: float
    #: Les jambes qui ont ramene cet extrait : `sens`, `mots`, ou les deux.
    #: Sans ce champ la fusion serait une boite noire de plus, et le lecteur
    #: n'aurait aucun moyen de savoir si un extrait remonte parce qu'il porte
    #: le mot cherche ou parce qu'il en porte le sens.
    trouve_par: frozenset[str] = frozenset({"sens"})


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


#: Le seul trou du modele est `{distance}`, l'expression de distance cosinus.
#: Toutes les valeurs venant de l'appelant sont des parametres lies.
_MODELE_REQUETE = """
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
        e.verified_status AS verified_status,
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


def requete_sql(schema: str) -> str:
    """La requete de similarite, qualifiee par le schema de pgvector.

    `OPERATOR(schema.<=>)` et `schema.vector` evitent de dependre du
    `search_path` de la session. Aucun index n'est vise : la migration 036 a
    laisse la table sans index de similarite, un parcours sequentiel restant
    exact et rapide en dessous de quelques dizaines de milliers de vecteurs.
    """
    distance = f"em.embedding OPERATOR({schema}.<=>) CAST(:vecteur AS {schema}.vector)"
    # La seule valeur assemblee est un nom de schema lu dans `pg_catalog` puis
    # confronte a `_SCHEMA_VALIDE`. Rien de ce que fournit l'appelant n'entre
    # ici : :vecteur, :modele, :user_id et :limite sont des parametres lies.
    return _MODELE_REQUETE.format(distance=distance)  # nosec B608


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
            verified_status=ligne.verified_status,
            similarite=float(ligne.similarite),
        )
        for ligne in lignes
        if float(ligne.similarite) >= SIMILARITE_MINIMALE
    ]


#: La jambe lexicale. Elle vivait dans `tools_write.search_my_excerpts`, triee
#: par date de creation : un ordre qui n'ordonne rien de ce que la requete
#: demande. Elle rend ici l'ordre du plus grand nombre d'occurrences, qui est la
#: seule mesure qu'un `ILIKE` sache produire.
#:
#: Le compte se fait en SQL par difference de longueur : `replace` retire toutes
#: les occurrences, l'ecart divise par la longueur du motif les compte. `length`
#: et `replace` existent des deux cotes, Postgres en production et SQLite dans
#: les tests.
_REQUETE_MOTS = """
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
        e.verified_status AS verified_status,
        (length(lower(e.text)) - length(replace(lower(e.text), :motif, ''))) AS ecart
    FROM source_excerpts e
    JOIN sources s ON s.id = e.source_id
    JOIN biblio_cards c ON c.id = s.biblio_card_id
    WHERE c.user_id = :user_id
      AND c.deleted_at IS NULL
      AND s.deleted_at IS NULL
      AND lower(e.text) LIKE :comme
    ORDER BY ecart DESC
    LIMIT :limite
"""


async def rechercher_par_mots(
    db: AsyncSession,
    user_id: UUID,
    requete: str,
    limite: int = 20,
) -> list[Resultat]:
    """Les extraits de `user_id` qui portent `requete` mot pour mot.

    Rend toujours une liste : une recherche lexicale ne peut pas etre
    indisponible, contrairement a la recherche par le sens qui depend d'un
    service externe. La liste vide veut donc bien dire « rien ne correspond ».
    """
    requete = requete.strip()
    if not requete:
        return []
    motif = requete.lower()
    echappe = motif.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    lignes = await db.execute(
        text(_REQUETE_MOTS),
        {
            "motif": motif,
            "comme": f"%{echappe}%",
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
            verified_status=ligne.verified_status,
            similarite=0.0,
            trouve_par=frozenset({"mots"}),
        )
        for ligne in lignes
    ]


async def rechercher_fusionne(
    db: AsyncSession,
    user_id: UUID,
    requete: str,
    limite: int = 20,
) -> list[Resultat]:
    """Les deux jambes, fusionnees par le rang reciproque.

    Le seuil semantique s'applique **avant** la fusion, pas a sa place : un
    extrait etranger a la question ne doit pas remonter au seul motif qu'il est
    premier de sa liste. La fusion ordonne ce que chaque jambe a juge digne
    d'etre rendu, elle ne rattrape pas ce qu'elles ont ecarte.

    La jambe semantique indisponible ne fait pas echouer la recherche : sa liste
    est simplement absente de la fusion, et les extraits rendus le disent par
    leur `trouve_par`.
    """
    from app.services.fusion_rangs import fusionner

    par_sens = await rechercher(db, user_id, requete, limite)
    par_mots = await rechercher_par_mots(db, user_id, requete, limite)

    classements: dict[str, list[UUID]] = {"mots": [r.excerpt_id for r in par_mots]}
    if par_sens is not None:
        classements["sens"] = [r.excerpt_id for r in par_sens]

    connus: dict[UUID, Resultat] = {r.excerpt_id: r for r in par_mots}
    for resultat in par_sens or []:
        # La jambe semantique gagne quand les deux portent le meme extrait :
        # elle seule connait la similarite, que la jambe lexicale laisse a zero.
        connus[resultat.excerpt_id] = resultat

    ordonnes = []
    for fusion in fusionner(classements)[:limite]:
        resultat = connus[fusion.identifiant]
        ordonnes.append(replace(resultat, trouve_par=fusion.jambes))
    return ordonnes
