"""Le mode et les sources choisis par le créateur, pour le tour en cours.

Perplexity, Vane et Morphic offrent le même geste : une recherche rapide ou
approfondie, et un choix des sources (Focus chez Perplexity, groupes chez
Scira). Chez Philum, la méthode ne change pas d'un mode à l'autre, seuls les
budgets changent ; et sans choix, tous les corpus sont interrogés.

Les options voyagent dans une `ContextVar` posée par le chat, comme le profil
du modèle : les outils de recherche les lisent sans que chaque signature ait à
les transporter.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass

RAPIDE = "rapide"
APPROFONDI = "approfondi"

#: Les corpus de chaque famille proposée au créateur.
FAMILLES: dict[str, frozenset[str]] = {
    "litterature": frozenset({"openalex", "europepmc", "semantic_scholar"}),
    "web": frozenset({"web"}),
}


@dataclass(frozen=True)
class Options:
    mode: str = APPROFONDI
    #: Familles retenues ; vide : toutes.
    sources: frozenset[str] = frozenset()

    @property
    def rapide(self) -> bool:
        return self.mode == RAPIDE


OPTIONS_RECHERCHE: ContextVar[Options | None] = ContextVar("options_recherche", default=None)


def options_courantes() -> Options:
    """Les options du tour en cours ; hors chat (MCP, tests), la méthode complète."""
    return OPTIONS_RECHERCHE.get() or Options()


def filtrer_corpus[T](corpus: Mapping[str, T], options: Options) -> dict[str, T]:
    """Les corpus que les familles choisies autorisent. Sans choix, tous. Fonction pure."""
    if not options.sources:
        return dict(corpus)
    permis = frozenset().union(*(FAMILLES.get(f, frozenset()) for f in options.sources))
    return {nom: chercheur for nom, chercheur in corpus.items() if nom in permis}
