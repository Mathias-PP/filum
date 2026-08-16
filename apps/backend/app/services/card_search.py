"""Ce qu'une recherche de fiches doit atteindre.

Mesure en production le 2026-08-16 : le corpus vitrine cite « Optogenetic
Stimulation of a Hippocampal Engram Activates Fear Memory Recall », et
chercher « engram » ne ramenait rien, ni sur /discover ni par le serveur MCP.
Les deux surfaces cherchaient les cinq colonnes de la fiche et jamais la
bibliographie, alors que la bibliographie est l'objet meme du produit.

Le predicat vit ici, seul, parce que deux surfaces qui repondent
differemment a la meme question sont deux corpus aux yeux de qui cherche.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, exists, or_

from app.db.text_search import contient
from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User


def cite_le_terme(terme: str) -> ColumnElement[bool]:
    """La fiche cite une source dont le titre ou les auteurs portent le terme.

    `exists` plutot qu'une jointure : une fiche qui cite dix fois le meme
    auteur reste une fiche, et le decompte des facettes de /discover repose
    sur la meme requete que les resultats.

    Le titre et les auteurs seulement. Etendre a la revue ferait remonter
    toutes les fiches citant Nature des qu'on cherche « nature », un mot qui
    veut dire autre chose.
    """
    return (
        exists()
        .where(
            Source.biblio_card_id == BiblioCard.id,
            Source.deleted_at.is_(None),
            or_(contient(Source.title, terme), contient(Source.authors, terme)),
        )
        .correlate(BiblioCard)
    )


def correspond(terme: str) -> ColumnElement[bool]:
    """La fiche repond au terme, par ce qu'elle dit ou par ce qu'elle cite.

    Suppose `User` deja joint : les deux appelants le font, et une fiche sans
    createur n'existe pas.
    """
    return or_(
        contient(BiblioCard.title, terme),
        contient(BiblioCard.description, terme),
        contient(BiblioCard.content_authors, terme),
        contient(User.username, terme),
        contient(User.display_name, terme),
        cite_le_terme(terme),
    )
