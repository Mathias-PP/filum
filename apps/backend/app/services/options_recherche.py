"""Le mode et les sources choisis par le créateur, pour le tour en cours.

Perplexity, Vane et Morphic offrent le même geste : une recherche rapide ou
approfondie, et un choix des sources (Focus chez Perplexity, groupes chez
Scira). Chez Philum, la méthode ne change pas d'un mode à l'autre, seuls les
budgets changent ; et sans choix, tous les corpus sont interrogés.

Sans choix non plus, les publications scientifiques et les sites d'institutions
passent d'abord : ils sont lus et rendus avant les autres pages, qui restent
cherchées. Quand la question ne dit pas clairement quelles sources conviennent,
le cadrage le demande au créateur (`demander_sources`).

Les options voyagent dans une `ContextVar` posée par le chat, comme le profil
du modèle : les outils de recherche les lisent sans que chaque signature ait à
les transporter.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextvars import ContextVar
from dataclasses import dataclass, replace

RAPIDE = "rapide"
APPROFONDI = "approfondi"

#: Toutes les sources à égalité, sans priorité aux publications et aux institutions.
EGALE = "egale"

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
    #: Publications et sites d'institutions lus et rendus d'abord ; faux : toutes à égalité.
    publications_d_abord: bool = True
    #: Le créateur a choisi ses sources : le cadrage ne les lui redemande pas.
    sources_choisies: bool = False

    @property
    def rapide(self) -> bool:
        return self.mode == RAPIDE


#: Les choix proposés au créateur quand la question ne dit pas quelles sources
#: conviennent, avec leur effet. Tenus par le serveur : la réponse se traduit en
#: options sans que le modèle ait à l'interpréter.
CHOIX_SOURCES: dict[str, tuple[frozenset[str], bool]] = {
    "Publications scientifiques et sites d'institutions d'abord": (frozenset(), True),
    "Toutes les sources à égalité, presse, blogs et documentation compris": (frozenset(), False),
    "Littérature scientifique seulement": (frozenset({"litterature"}), True),
}

QUESTION_SOURCES = "Quelles sources la recherche doit-elle privilégier ?"

OPTIONS_RECHERCHE: ContextVar[Options | None] = ContextVar("options_recherche", default=None)


def options_courantes() -> Options:
    """Les options du tour en cours ; hors chat (MCP, tests), la méthode complète."""
    return OPTIONS_RECHERCHE.get() or Options()


def options_demandees(mode: str, sources: Iterable[str], priorite: str | None) -> Options:
    """Les options d'une requête du chat. Fonction pure.

    Une famille de sources ou une priorité explicite est un choix du créateur ;
    sans l'un ni l'autre, les publications et les sites d'institutions passent
    d'abord et le cadrage peut demander.
    """
    familles = frozenset(sources)
    return Options(
        mode=mode,
        sources=familles,
        publications_d_abord=priorite != EGALE,
        sources_choisies=bool(familles) or priorite is not None,
    )


def options_choisies(options: Options, choix: str) -> Options | None:
    """Les options après la réponse du créateur à `QUESTION_SOURCES`. None : réponse hors des choix."""
    effet = CHOIX_SOURCES.get(choix)
    if effet is None:
        return None
    sources, publications_d_abord = effet
    return replace(
        options, sources=sources, publications_d_abord=publications_d_abord, sources_choisies=True
    )


def filtrer_corpus[T](corpus: Mapping[str, T], options: Options) -> dict[str, T]:
    """Les corpus que les familles choisies autorisent. Sans choix, tous. Fonction pure."""
    if not options.sources:
        return dict(corpus)
    permis = frozenset().union(*(FAMILLES.get(f, frozenset()) for f in options.sources))
    return {nom: chercheur for nom, chercheur in corpus.items() if nom in permis}
