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
from datetime import datetime
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
    format: str | None = None
    author_kind: str | None = None
    stance: str | None = None
    is_pivot: bool = False
    # Le panneau de detail affiche la date de publication : sans elle, une
    # source d'une fiche voisine s'ouvrirait dans un encadre amputé.
    published_at: datetime | None = None
    # Metadonnees bibliographiques : la recherche du graphe porte dessus, donc
    # une source de fiche voisine doit etre trouvable sur les memes criteres
    # qu'une source de la racine, sans quoi le filtre serait borgne.
    journal: str | None = None
    publisher: str | None = None
    doi: str | None = None
    slug: str | None = None
    creator_slug: str | None = None
    creator_name: str | None = None
    sources_count: int | None = None
    linked_card_id: UUID | None = None
    # Fiche non revendiquee : son auteur Philum declare ne pas etre l'auteur du
    # contenu decrit. L'etiqueter a son nom induirait en erreur.
    is_seed: bool = False


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str  # "cites" (fiche -> source) | "is_card" (source -> fiche)
    # Rapport declare par la source qui porte l'arete. Colore le trait : voir
    # d'un coup d'oeil ce qui appuie et ce qui contredit vaut mieux que
    # d'ouvrir trente sources une par une.
    stance: str | None = None


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


async def _load_citing_cards(
    db: AsyncSession, card_ids: set[UUID]
) -> dict[UUID, dict[UUID, str | None]]:
    """Fiches qui citent celles demandees : ``cited_id -> {citing_id: stance}``.

    Le lien entre deux fiches n'a pas d'orientation privilegiee du point de vue
    du lecteur : "qui s'appuie sur cette fiche" est aussi informatif que "sur
    quoi elle s'appuie". Les deux vues remontent donc les citations entrantes.

    Deux sources d'une meme fiche peuvent designer la meme fiche cible avec des
    rapports differents ; l'arete etant unique, le premier rapport declare
    l'emporte sur le silence.
    """
    if not card_ids:
        return {}
    result = await db.execute(
        select(Source.linked_card_id, Source.biblio_card_id, Source.stance)
        .where(Source.linked_card_id.in_(card_ids), Source.deleted_at.is_(None))
        .order_by(Source.position)
    )
    citing: dict[UUID, dict[UUID, str | None]] = {}
    for cited_id, citing_id, stance in result.all():
        edges = citing.setdefault(cited_id, {})
        if edges.get(citing_id) is None:
            edges[citing_id] = stance
    return citing


async def _load_card_authors(db: AsyncSession, card_ids: set[UUID]) -> dict[UUID, str]:
    """Auteurs reels du contenu decrit par chaque fiche : ``card_id -> authors``.

    Une fiche ne porte pas le nom des auteurs du contenu qu'elle documente ;
    seule sa fiche parente le connait, via la source qui la designe
    (``Source.linked_card_id``). On remonte donc l'information depuis la
    bibliographie de qui la cite.

    Plusieurs fiches citent souvent le meme contenu, avec des listes d'auteurs
    de qualite inegale selon la source d'extraction : « Kang » d'un cote,
    « Kang W., Hernandez S., Rahman M. » de l'autre. La plus complete gagne,
    la plus ancienne departageant a longueur egale pour que le graphe reste
    stable d'un appel a l'autre.
    """
    if not card_ids:
        return {}
    result = await db.execute(
        select(Source.linked_card_id, Source.authors)
        .where(
            Source.linked_card_id.in_(card_ids),
            Source.authors.is_not(None),
            Source.deleted_at.is_(None),
        )
        .order_by(Source.created_at)
    )
    authors: dict[UUID, str] = {}
    for card_id, value in result.all():
        if card_id is None or not value or not value.strip():
            continue
        candidate = value.strip()
        current = authors.get(card_id)
        if current is None or len(candidate) > len(current):
            authors[card_id] = candidate
    return authors


async def build_card_graph(
    db: AsyncSession,
    root_card: BiblioCard,
    *,
    depth: int = 1,
    include_sources: bool = True,
) -> CardGraph:
    """BFS borne depuis ``root_card`` en suivant ``Source.linked_card_id``.

    Le parcours suit les liens dans les deux sens : les fiches que la racine
    cite, et celles qui la citent. Une chaine A -> B -> C est donc restituee
    entiere, quel que soit le bout par lequel on entre.

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

    # Aretes fiche -> fiche de la constellation : le meme lien peut etre
    # rencontre a l'aller et au retour, on ne le compte qu'une fois. La valeur
    # est le rapport declare, un rapport l'emportant toujours sur le silence.
    card_edges: dict[tuple[UUID, UUID], str | None] = {}

    def _record_card_edge(src_id: UUID, dst_id: UUID, stance: str | None) -> None:
        if card_edges.get((src_id, dst_id)) is None:
            card_edges[(src_id, dst_id)] = stance

    for level in range(depth + 1):
        sources_by_card = await _load_sources(db, frontier)
        counts = {cid: len(srcs) for cid, srcs in sources_by_card.items()}

        # Fiches referencees par les sources de la frontiere courante.
        next_ids: set[UUID] = set()
        for srcs in sources_by_card.values():
            for src in srcs:
                if src.linked_card_id and src.linked_card_id not in seen_cards:
                    next_ids.add(src.linked_card_id)

        citing_by_card = await _load_citing_cards(db, frontier)
        for citers in citing_by_card.values():
            next_ids |= {cid for cid in citers if cid not in seen_cards}

        next_meta = await _load_cards(db, next_ids) if level < depth else {}
        # Une fiche deja visitee reste une cible valide : sans cela, deux fiches
        # qui se citent mutuellement n'auraient qu'une seule des deux aretes.
        reachable = set(next_meta) | set(card_meta)

        for cited_id, citers in citing_by_card.items():
            for citing_id, stance in citers.items():
                if citing_id in reachable:
                    _record_card_edge(citing_id, cited_id, stance)

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
                    authors=card.content_authors,
                    is_seed=bool(card.is_seed),
                )
            )

            for src in sources_by_card.get(card_id, []):
                # Une source dont la fiche cible est atteignable devient une
                # arete vers cette fiche. Sinon (fiche privee, depassement de
                # profondeur) elle reste une source ordinaire.
                target_card = src.linked_card_id if src.linked_card_id in reachable else None
                if target_card:
                    # La source qui designe une fiche EST cette fiche : la
                    # rendre en plus comme noeud source intercale afficherait
                    # deux fois le meme contenu, relie en chaine, sans rien
                    # ajouter. Le lien va donc directement de fiche a fiche.
                    _record_card_edge(card_id, target_card, src.stance)
                    continue
                if not include_sources:
                    continue
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
                        format=src.format,
                        author_kind=src.author_kind,
                        stance=src.stance,
                        is_pivot=bool(src.is_pivot),
                        published_at=src.published_at,
                        journal=src.journal,
                        publisher=src.publisher,
                        doi=src.doi,
                        linked_card_id=src.linked_card_id,
                    )
                )
                graph.edges.append(
                    GraphEdge(
                        source=card_node_id(card_id),
                        target=source_node_id(src.id),
                        kind="cites",
                        stance=src.stance,
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

    # Une arete peut avoir ete decouverte avant que sa fiche source ou cible ne
    # soit rendue : on ne garde que celles dont les deux extremites existent.
    rendered = {n.id for n in graph.nodes if n.kind == "card"}
    for src_id, dst_id in sorted(card_edges, key=lambda e: (str(e[0]), str(e[1]))):
        if card_node_id(src_id) in rendered and card_node_id(dst_id) in rendered:
            graph.edges.append(
                GraphEdge(
                    source=card_node_id(src_id),
                    target=card_node_id(dst_id),
                    kind="is_card",
                    stance=card_edges[(src_id, dst_id)],
                )
            )

    # Les fiches qui declarent les auteurs de leur contenu font foi. Pour les
    # autres, on reconstitue depuis la bibliographie de qui les cite -- ce qui
    # ne donne rien si personne ne les cite, d'ou la declaration.
    card_nodes = [n for n in graph.nodes if n.kind == "card" and not n.authors]
    if card_nodes:
        real_authors = await _load_card_authors(
            db, {UUID(n.id.removeprefix("card:")) for n in card_nodes}
        )
        for node in card_nodes:
            node.authors = real_authors.get(UUID(node.id.removeprefix("card:")))

    return graph
