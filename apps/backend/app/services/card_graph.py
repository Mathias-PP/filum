"""Construction du meta-graphe : fiches reliees entre elles par leurs sources.

Une source dont l'URL pointe vers une fiche Philum publique porte
``linked_card_id``. En suivant ces liens de proche en proche on obtient un
graphe fiches <-> sources qui alimente deux vues frontend : le depliage d'un
noeud dans le graphe d'une fiche, et la vue constellation (fiches seules).

Le parcours est un BFS borne en profondeur ET en nombre de noeuds : un cycle
de fiches qui se citent mutuellement est frequent et legitime, et le nombre de
sources par fiche peut depasser la centaine.

Seules les fiches publiees ET publiques sont traversees : le graphe est servi
sur un endpoint public, il ne doit jamais reveler l'existence d'un brouillon
ou d'une fiche privee, meme a son proprietaire (qui la verrait alors
apparaitre pour les visiteurs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.biblio_card import BiblioCard
from app.models.source import Source
from app.models.user import User

# Bornes du parcours. La profondeur 1 suffit au depliage d'un noeud ; la
# constellation demande 2 a 3 sauts pour montrer un voisinage interessant.
MAX_DEPTH = 3
# Plafond de noeuds retournes. Au-dela le graphe cesse d'etre lisible et le
# cout de rendu explose cote client ; on tronque plutot que de faire ramer.
MAX_NODES = 600


def card_node_id(card_id: UUID) -> str:
    return f"card:{card_id}"


def source_node_id(source_id: UUID) -> str:
    return f"source:{source_id}"


@dataclass
class GraphNode:
    id: str
    kind: str  # "card" | "source"
    depth: int
    title: str | None = None
    url: str | None = None
    authors: str | None = None
    category: str | None = None
    slug: str | None = None
    creator_slug: str | None = None
    creator_name: str | None = None
    sources_count: int | None = None
    linked_card_id: UUID | None = None


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str  # "cites" (fiche -> source) | "is_card" (source -> fiche)


@dataclass
class CardGraph:
    root_id: str
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    truncated: bool = False


CardMeta = tuple[BiblioCard, str, str | None]


async def _load_cards(db: AsyncSession, card_ids: set[UUID]) -> dict[UUID, CardMeta]:
    """Charge (card, username, display_name) pour des fiches publiques."""
    if not card_ids:
        return {}
    result = await db.execute(
        select(BiblioCard, User.username, User.display_name)
        .join(User, BiblioCard.user_id == User.id)
        .where(
            BiblioCard.id.in_(card_ids),
            BiblioCard.status == "published",
            BiblioCard.visibility == "public",
            BiblioCard.deleted_at.is_(None),
        )
    )
    return {row[0].id: (row[0], row[1], row[2]) for row in result.all()}


async def _load_sources(db: AsyncSession, card_ids: set[UUID]) -> dict[UUID, list[Source]]:
    """Charge les sources vivantes des fiches demandees, groupees par fiche."""
    if not card_ids:
        return {}
    result = await db.execute(
        select(Source)
        .where(Source.biblio_card_id.in_(card_ids), Source.deleted_at.is_(None))
        .order_by(Source.position)
    )
    grouped: dict[UUID, list[Source]] = {cid: [] for cid in card_ids}
    for src in result.scalars().all():
        grouped.setdefault(src.biblio_card_id, []).append(src)
    return grouped


async def build_card_graph(
    db: AsyncSession,
    root_card: BiblioCard,
    *,
    depth: int = 1,
    include_sources: bool = True,
) -> CardGraph:
    """BFS borne depuis ``root_card`` en suivant ``Source.linked_card_id``.

    ``include_sources=False`` produit le graphe fiches-seules de la vue
    constellation : les sources sont traversees pour trouver les liens mais
    ne deviennent pas des noeuds, seul leur nombre est reporte sur la fiche.
    """
    depth = max(0, min(depth, MAX_DEPTH))
    graph = CardGraph(root_id=card_node_id(root_card.id))

    seen_cards: set[UUID] = {root_card.id}
    frontier: set[UUID] = {root_card.id}
    # La fiche racine est deja chargee par l'appelant ; on ne la recharge pas,
    # mais on a besoin de son auteur pour l'etiqueter.
    root_meta: CardMeta = (root_card, root_card.user.username, root_card.user.display_name)
    card_meta: dict[UUID, CardMeta] = {root_card.id: root_meta}
    card_depth: dict[UUID, int] = {root_card.id: 0}

    for level in range(depth + 1):
        sources_by_card = await _load_sources(db, frontier)
        counts = {cid: len(srcs) for cid, srcs in sources_by_card.items()}

        # Fiches referencees par les sources de la frontiere courante.
        next_ids: set[UUID] = set()
        for srcs in sources_by_card.values():
            for src in srcs:
                if src.linked_card_id and src.linked_card_id not in seen_cards:
                    next_ids.add(src.linked_card_id)

        next_meta = await _load_cards(db, next_ids) if level < depth else {}

        for card_id in frontier:
            meta = card_meta.get(card_id)
            if meta is None:
                continue
            card, username, display_name = meta
            graph.nodes.append(
                GraphNode(
                    id=card_node_id(card_id),
                    kind="card",
                    depth=card_depth[card_id],
                    title=card.title,
                    slug=card.slug,
                    creator_slug=username,
                    creator_name=display_name,
                    sources_count=counts.get(card_id, 0),
                )
            )

            for src in sources_by_card.get(card_id, []):
                # Une source dont la fiche cible est atteignable devient une
                # arete vers cette fiche. Sinon (fiche privee, depassement de
                # profondeur) elle reste une source ordinaire.
                target_card = src.linked_card_id if src.linked_card_id in next_meta else None
                if include_sources:
                    if len(graph.nodes) >= MAX_NODES:
                        graph.truncated = True
                        break
                    graph.nodes.append(
                        GraphNode(
                            id=source_node_id(src.id),
                            kind="source",
                            depth=card_depth[card_id],
                            title=src.title,
                            url=src.url,
                            authors=src.authors,
                            category=src.category,
                            linked_card_id=src.linked_card_id,
                        )
                    )
                    graph.edges.append(
                        GraphEdge(
                            source=card_node_id(card_id),
                            target=source_node_id(src.id),
                            kind="cites",
                        )
                    )
                    if target_card:
                        graph.edges.append(
                            GraphEdge(
                                source=source_node_id(src.id),
                                target=card_node_id(target_card),
                                kind="is_card",
                            )
                        )
                elif target_card:
                    # Constellation : arete directe fiche -> fiche.
                    graph.edges.append(
                        GraphEdge(
                            source=card_node_id(card_id),
                            target=card_node_id(target_card),
                            kind="is_card",
                        )
                    )

        if level >= depth or graph.truncated:
            break

        frontier = set()
        for card_id, meta in next_meta.items():
            seen_cards.add(card_id)
            card_meta[card_id] = meta
            card_depth[card_id] = level + 1
            frontier.add(card_id)
        if not frontier:
            break

    return graph
