"""Les fiches voisines qu'un export emporte, par sens et par degre.

`build_card_graph` sert a *dessiner* : il confond les deux sens du lien parce
qu'un lecteur qui regarde une constellation se moque de savoir par quel bout il
est entre. Un export ne peut pas se le permettre. « Les fiches qui citent
celle-ci » et « les fiches qu'elle cite » ne disent pas la meme chose — l'une
est sa posterite, l'autre ses fondations — et melanger les deux dans un meme
fichier produirait une liste dont on ne saurait plus lire le sens.

Le parcours est donc oriente, avec une profondeur propre a chaque sens :

    degre 2 descendant : une fiche citee par une fiche citee par la racine
    degre 2 montant    : une fiche qui cite une fiche qui cite la racine

Et un perimetre propre a chaque degre, parce qu'on veut rarement autant de
detail d'un voisin lointain que de la fiche elle-meme : le degre 1 avec ses
extraits, le degre 2 en references seules, par exemple.

Une fiche n'apparait qu'une fois, au degre ou elle est atteinte en premier, et
jamais dans les deux sens : le degre le plus court gagne. Sans cette regle, un
cycle de fiches qui se citent mutuellement — frequent et legitime — ferait
gonfler l'export sans rien y ajouter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User
from app.services.export_scope import FULL, ExportScope, parse_scope

#: Meme plafond que le graphe : au-dela, un export cesse d'etre une fiche
#: enrichie pour devenir un dump de la base.
MAX_DEGREE = 3

#: Plafond de fiches voisines rapportees, tous sens et degres confondus. Une
#: fiche tres citee peut en avoir des centaines ; l'export tronque plutot que
#: de servir un fichier de plusieurs dizaines de megaoctets.
MAX_CARDS = 100


@dataclass
class NeighbourCard:
    card: BiblioCard
    degree: int
    #: "cited" (la racine la cite) | "citing" (elle cite la racine)
    direction: str
    scope: ExportScope


@dataclass
class Neighbourhood:
    cited: list[NeighbourCard] = field(default_factory=list)
    citing: list[NeighbourCard] = field(default_factory=list)
    truncated: bool = False

    def __bool__(self) -> bool:
        return bool(self.cited or self.citing)


def parse_degrees(spec: str | None) -> dict[int, ExportScope]:
    """`"1:excerpts|2:"` -> `{1: <extraits seuls>, 2: <references seules>}`.

    Trois ecritures, de la plus courte a la plus precise :

    - `None` ou `""` : aucun voisin. C'est le defaut — emporter le voisinage
      d'une fiche tres citee sans l'avoir demande serait une surprise couteuse.
    - `"2"` : les degres 1 et 2, perimetre complet pour chacun.
    - `"1:excerpts,archives|2:"` : un perimetre par degre. Apres le `:`, la
      meme grammaire que `?include=` — vide veut donc dire « references seules ».

    Un degre au-dela de `MAX_DEGREE`, ou nul, est refuse plutot que rabote : un
    export silencieusement moins profond que demande se lit comme un voisinage
    complet alors qu'il ne l'est pas.
    """
    if not spec:
        return {}
    if ":" not in spec and "|" not in spec:
        try:
            profondeur = int(spec)
        except ValueError:
            raise ValueError(f"Degré illisible : « {spec} »") from None
        _valider_degre(profondeur)
        # `ExportScope` est fige : partager la meme instance entre les degres
        # est sans risque.
        return dict.fromkeys(range(1, profondeur + 1), FULL)

    par_degre: dict[int, ExportScope] = {}
    for morceau in spec.split("|"):
        if not morceau.strip():
            continue
        degre_txt, _, include = morceau.partition(":")
        try:
            degre = int(degre_txt.strip())
        except ValueError:
            raise ValueError(f"Degré illisible : « {degre_txt.strip()} »") from None
        _valider_degre(degre)
        par_degre[degre] = parse_scope(include)
    return par_degre


def _valider_degre(degre: int) -> None:
    if not 1 <= degre <= MAX_DEGREE:
        raise ValueError(f"Degré hors bornes : {degre} (attendu entre 1 et {MAX_DEGREE})")


async def _load_cards(db: AsyncSession, ids: set[UUID]) -> dict[UUID, BiblioCard]:
    """Les fiches demandees, sources et extraits charges — publiques seulement.

    Le filtre publie/public est ici et non chez l'appelant : l'export est servi
    sur une route publique, et un voisinage qui revelerait l'existence d'un
    brouillon serait une fuite silencieuse.
    """
    if not ids:
        return {}
    result = await db.execute(
        select(BiblioCard)
        .join(User, BiblioCard.user_id == User.id)
        .options(
            selectinload(BiblioCard.sources.and_(Source.deleted_at.is_(None))).selectinload(
                Source.excerpts
            ),
            selectinload(BiblioCard.user),
        )
        .where(
            BiblioCard.id.in_(ids),
            BiblioCard.status == "published",
            BiblioCard.visibility == "public",
            BiblioCard.deleted_at.is_(None),
        )
    )
    return {card.id: card for card in result.scalars().all()}


async def _cited_by(db: AsyncSession, ids: set[UUID]) -> set[UUID]:
    """Les fiches designees par les sources des fiches donnees."""
    if not ids:
        return set()
    result = await db.execute(
        select(Source.linked_card_id).where(
            Source.biblio_card_id.in_(ids),
            Source.linked_card_id.is_not(None),
            Source.deleted_at.is_(None),
        )
    )
    return {row[0] for row in result.all() if row[0]}


async def _citing(db: AsyncSession, ids: set[UUID]) -> set[UUID]:
    """Les fiches dont une source designe l'une des fiches donnees."""
    if not ids:
        return set()
    result = await db.execute(
        select(Source.biblio_card_id).where(
            Source.linked_card_id.in_(ids),
            Source.deleted_at.is_(None),
        )
    )
    return {row[0] for row in result.all() if row[0]}


async def collect_neighbourhood(
    db: AsyncSession,
    root_card: BiblioCard,
    *,
    cited: dict[int, ExportScope],
    citing: dict[int, ExportScope],
) -> Neighbourhood:
    """Les voisines de `root_card`, chaque sens parcouru pour lui-meme.

    Les deux parcours partagent l'ensemble des fiches deja vues : une fiche que
    la racine cite *et* qui la cite n'est rapportee qu'une fois, du cote ou elle
    a ete atteinte au degre le plus court. Le sens descendant est parcouru en
    premier, et departage donc a egalite — ce sont les fondations d'un propos,
    plus proches de ce que la fiche affirme que sa posterite.
    """
    voisinage = Neighbourhood()
    vues: set[UUID] = {root_card.id}

    for direction, degres, bac in (
        ("cited", cited, voisinage.cited),
        ("citing", citing, voisinage.citing),
    ):
        if not degres:
            continue
        frontiere = {root_card.id}
        for degre in range(1, max(degres) + 1):
            suivantes = await (
                _cited_by(db, frontiere) if direction == "cited" else _citing(db, frontiere)
            )
            suivantes -= vues
            if not suivantes:
                break
            fiches = await _load_cards(db, suivantes)
            # Les fiches privees ou en brouillon sont retirees du parcours mais
            # marquees vues : les reessayer au degre suivant ne les rendrait pas
            # publiques et ferait tourner le BFS pour rien.
            vues |= suivantes
            frontiere = set(fiches)
            scope = degres.get(degre)
            if scope is None:
                # Degre traverse mais non demande : on continue a marcher sans
                # rien emporter. « 2:references » sans « 1: » a un sens — on
                # veut les voisins des voisins, pas les voisins.
                continue
            for card_id in sorted(fiches, key=str):
                if len(voisinage.cited) + len(voisinage.citing) >= MAX_CARDS:
                    voisinage.truncated = True
                    return voisinage
                bac.append(NeighbourCard(fiches[card_id], degre, direction, scope))

    return voisinage
