<script lang="ts">
  import {
    drag,
    forceCenter,
    forceCollide,
    forceLink,
    forceManyBody,
    forceSimulation,
    select,
    zoom,
    zoomIdentity,
    type D3DragEvent,
    type Simulation,
    type ZoomBehavior,
  } from 'd3';
  import { onDestroy, onMount } from 'svelte';

  import { api } from '$lib/api';
  import type { AuthorKind, CardDetail, Source, SourceCategory, SourceFormat } from '$lib/api';
  import {
    AUTHOR_COLORS,
    CATEGORY_COLORS,
    FORMAT_COLORS,
    authorLabel as authorKindLabel,
    categoryLabel,
    formatLabel,
    sourceColor,
    type ColorMode,
    type NodeColor,
  } from '$lib/utils/author-colors';
  import { cardNodeLabel } from '$lib/utils/card-label';
  import { buildHaystack, matchesAllTerms, searchTerms } from '$lib/utils/graph-search';
  import CardDetailPanel, { type CardPanelInfo } from './CardDetailPanel.svelte';
  import SourceDetailPanel from './SourceDetailPanel.svelte';

  interface Props {
    card: CardDetail;
    onSelect?: (source: Source | null) => void;
  }

  let { card, onSelect }: Props = $props();

  type NodeKind = 'card' | 'source' | 'junction';

  /**
   * Méta-graphe. Une source dont l'URL vise une autre fiche Philum porte
   * `linked_card_id` : cette source n'est pas rendue comme une source
   * ordinaire, elle EST la fiche visée, affichée directement comme nœud fiche
   * relié à celle qui la cite. La faire précéder d'un nœud source intercalé
   * montrerait deux fois le même contenu et faisait croire à deux références
   * distinctes. Le nœud fiche est dépliable : il révèle ses propres sources.
   * Le voisinage entier est chargé en une requête au montage, si bien que le
   * dépliage est instantané.
   */
  interface NeighborCard {
    id: string;
    title: string;
    slug: string;
    creatorSlug: string;
    creatorName: string | null;
    /** Auteurs réels du contenu documenté, remontés par le backend. */
    authors: string | null;
    sourcesCount: number;
  }

  /** Source normalisée : une source de la fiche racine ou d'une fiche voisine. */
  interface GraphSourceData {
    id: string;
    url: string;
    title: string | null;
    authors: string | null;
    format: SourceFormat;
    category: SourceCategory;
    author_kind: AuthorKind;
    is_pivot: boolean;
    published_at: string | null;
    journal: string | null;
    publisher: string | null;
    doi: string | null;
    parent_source_id: string | null;
    linked_card_id: string | null;
    /** Présente uniquement pour les sources de la fiche racine. */
    full?: Source;
  }

  /**
   * Complète une source de fiche voisine pour le panneau de détail.
   *
   * Le méta-graphe n'en renvoie que les métadonnées d'affichage : ni extraits,
   * ni archive, ni annotation. Le panneau les traite déjà comme facultatifs et
   * se réduit tout seul. Sans cette conversion, cliquer sur un tel nœud
   * ouvrait brutalement un onglet, ce qui rompt la lecture du graphe.
   */
  function toSource(s: GraphSourceData): Source {
    return (
      s.full ?? {
        id: s.id,
        url: s.url,
        title: s.title,
        authors: s.authors,
        published_at: s.published_at,
        format: s.format,
        category: s.category,
        author_kind: s.author_kind,
        annotation: null,
        is_pivot: s.is_pivot,
        archive_status: 'pending',
        archive_url: null,
        archive_timestamp: null,
        parent_source_id: null,
        linked_card_id: s.linked_card_id,
        journal: s.journal,
        publisher: s.publisher,
        doi: s.doi,
        conflict_of_interest: null,
        citations_count: null,
        subscribers_count: null,
        views_count: null,
        impact_factor: null,
        excerpts: [],
        created_at: '',
        updated_at: null,
      }
    );
  }

  interface GraphNode {
    id: string;
    kind: NodeKind;
    label: string;
    source?: GraphSourceData;
    /** Fiche portée par ce nœud (`kind === 'card'`). */
    cardMeta?: NeighborCard;
    /**
     * Référence bibliographique qui désigne cette fiche, absorbée par le nœud.
     *
     * Le nœud fiche remplace le nœud source pour ne pas montrer deux fois le
     * même contenu ; sans cette reprise, les métadonnées de la référence
     * (revue, DOI, date, extraits) devenaient inatteignables au clic.
     */
    absorbedSource?: GraphSourceData;
    /** Fiche à laquelle appartient ce nœud, pour le repli en cascade. */
    ownerCardId: string;
    /** Source dépliable : fiche visée non encore dépliée. */
    expandable?: string;
    radius: number;
    fill: string;
    stroke: string;
    tier: 'card' | 'first' | 'second' | 'junction';
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    fx?: number | null;
    fy?: number | null;
  }

  interface GraphLink {
    source: string | GraphNode;
    target: string | GraphNode;
    kind: 'card' | 'parent' | 'sibling' | 'meta';
    forkHide?: true;
  }

  interface ForkMeta {
    junctionId: string;
    parentId: string;
    childIds: string[];
  }

  let container: HTMLDivElement | undefined = $state();
  let svgEl: SVGSVGElement | undefined = $state();
  let width = $state(800);
  let height = $state(560);
  let simulation: Simulation<GraphNode, GraphLink> | undefined;
  let zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> | undefined;
  let resizeObserver: ResizeObserver | undefined;
  let hoveredId: string | null = $state(null);
  let zoomLevel = $state(1);
  // Échelle du recadrage automatique. Les seuils d'affichage des étiquettes sont
  // exprimés relativement à elle, sinon un graphe recadré à 0.3 masquerait tout.
  let fitScale = $state(1);
  let layoutNodes: GraphNode[] = [];
  let hasAutoFitted = false;
  let hasUserAdjustedView = false;
  let autoFitFallback: number | undefined;
  let isFullscreen = $state(false);
  let selectedSource = $state<Source | null>(null);
  // Une fiche et une source ne s'affichent jamais ensemble : le panneau est un
  // emplacement unique, sélectionner l'un ferme l'autre.
  let selectedCard = $state<CardPanelInfo | null>(null);
  let panelAnchor = $state<{ x: number; y: number } | null>(null);

  // Voisinage méta-graphe, chargé une seule fois puis exploré côté client.
  let neighborCards = $state(new Map<string, NeighborCard>());
  // Auteurs réels de la fiche racine : elle ne les porte pas non plus, ils
  // viennent du méta-graphe quand une autre fiche la cite.
  let rootAuthors = $state<string | null>(null);
  // Arêtes fiche → fiche du voisinage, dans les deux sens.
  let cardLinks = $state<[string, string][]>([]);
  let neighborSources = new Map<string, GraphSourceData[]>();
  let expandedCardIds = $state<string[]>([]);
  let neighborhoodTruncated = $state(false);
  // Dernières positions connues : le dépliage remonte le graphe, sans ce
  // souvenir la disposition se réorganiserait entièrement à chaque clic.
  const posMemory = new Map<string, { x: number; y: number }>();
  // Nœud source d'où chaque fiche a été dépliée : les nouvelles sources
  // apparaissent près de lui plutôt qu'au centre, ce qui donne l'impression
  // d'un déploiement plutôt que d'un remaniement.
  const expandOrigin = new Map<string, string>();

  // Axe de couleur des nœuds (ADR-020) : type d'auteur par défaut.
  let colorMode = $state<ColorMode>('author_kind');
  const colorModeOptions: { value: ColorMode; label: string }[] = [
    { value: 'author_kind', label: 'Auteur' },
    { value: 'format', label: 'Format' },
    { value: 'category', label: 'Catégorie' },
  ];

  const cardId = $derived(`card:${card.id}`);

  /** Sources de la fiche racine, normalisées comme celles des fiches voisines. */
  const rootSources = $derived(
    card.sources.map((s): GraphSourceData => ({
      id: s.id,
      url: s.url,
      title: s.title,
      authors: s.authors,
      format: s.format,
      category: s.category,
      author_kind: s.author_kind,
      is_pivot: s.is_pivot,
      published_at: s.published_at,
      journal: s.journal ?? null,
      publisher: s.publisher ?? null,
      doi: s.doi ?? null,
      parent_source_id: s.parent_source_id,
      linked_card_id: s.linked_card_id ?? null,
      full: s,
    }))
  );

  /** Tout ce qui est actuellement à l'écran : racine + fiches dépliées. */
  const visibleSources = $derived.by(() => {
    const all = [...rootSources];
    for (const id of expandedCardIds) all.push(...(neighborSources.get(id) ?? []));
    return all;
  });

  // Légende : uniquement les valeurs présentes à l'écran.
  const legendEntries = $derived.by(() => {
    const seen = new Map<string, NodeColor>();
    for (const s of visibleSources) {
      const c = sourceColor(s, colorMode);
      if (!seen.has(c.label)) seen.set(c.label, c);
    }
    return [...seen.values()];
  });

  // Densité. Sur une fiche de 152 sources, des cercles de taille fixe se
  // touchent et les noms d'auteurs se chevauchent au point d'être illisibles.
  // On rétrécit donc les nœuds et on écarte le maillage à mesure que la fiche
  // grossit : le graphe occupe plus de place, mais un zoom avant devient
  // lisible au lieu d'être saturé. Agnostique au nombre de sources.
  const densityScale = $derived(
    Math.max(0.62, Math.min(1, Math.sqrt(24 / Math.max(visibleSources.length, 1))))
  );
  // 1 sur une petite fiche, ~1.5 sur une grosse : facteur appliqué aux distances
  // de lien et au rayon de collision, pour dégager la place des étiquettes.
  const spacingBoost = $derived(1 + (1 - densityScale) * 0.8);
  // Les étiquettes se rétrécissent aussi : à taille fixe, deux noms d'auteurs
  // voisins se chevauchent dès que le maillage se resserre.
  const labelScale = $derived(Math.max(0.72, densityScale));

  function truncate(text: string, max: number): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  // --- Recherche dans le graphe ---------------------------------------------
  //
  // La recherche porte sur tout ce qui identifie une référence — titre, auteurs,
  // revue, éditeur, DOI, URL, année, et les libellés lisibles du type d'auteur /
  // format / catégorie — parce qu'on cherche avec le mot qu'on a en tête, pas
  // avec le champ où il est rangé.
  let query = $state('');
  /** `id de nœud -> texte cherchable`, reconstruit à chaque montage du graphe. */
  let searchIndex = $state.raw(new Map<string, string>());

  function haystackOf(d: GraphNode): string {
    if (d.kind === 'source' && d.source) {
      const s = d.source;
      return buildHaystack([
        s.title,
        s.authors,
        s.journal,
        s.publisher,
        s.doi,
        s.url,
        s.published_at?.slice(0, 4),
        authorKindLabel(s.author_kind),
        formatLabel(s.format),
        categoryLabel(s.category),
      ]);
    }
    if (d.kind === 'card') {
      // Le nœud racine n'a pas de `cardMeta` : ses métadonnées viennent des
      // props, et ses auteurs réels du méta-graphe quand une fiche la cite.
      const m = d.cardMeta;
      return buildHaystack([
        m?.title ?? card.title,
        m ? m.authors : (card.content_authors ?? rootAuthors),
        m?.creatorName ?? card.creator.display_name,
        m?.creatorSlug ?? card.creator.slug,
        m?.slug ?? card.slug,
      ]);
    }
    return '';
  }

  const queryTerms = $derived(searchTerms(query));

  /** Nœuds correspondant à la recherche. `null` = aucune recherche en cours. */
  const matchedIds = $derived.by(() => {
    if (queryTerms.length === 0) return null;
    const ids = new Set<string>();
    for (const [id, hay] of searchIndex) {
      if (matchesAllTerms(hay, queryTerms)) ids.add(id);
    }
    return ids;
  });

  /** Étiquette d'un nœud fiche : les auteurs du contenu, le créateur faute de mieux. */
  function cardLabelOf(d: GraphNode): string {
    return d.cardMeta
      ? cardNodeLabel({
          authors: d.cardMeta.authors,
          creatorName: d.cardMeta.creatorName,
          creatorSlug: d.cardMeta.creatorSlug,
        })
      : cardNodeLabel({
          // La fiche fait foi sur les auteurs de son contenu ; `rootAuthors`,
          // reconstitué depuis les fiches citantes, ne sert qu'à défaut.
          authors: card.content_authors ?? rootAuthors,
          creatorName: card.creator.display_name,
          creatorSlug: card.creator.slug,
        });
  }

  function authorLabel(s: GraphSourceData): string {
    if (s.authors && s.authors.trim().length > 0) return truncate(s.authors, 22);
    return truncate(s.title ?? s.url, 22);
  }

  let junctionCounter = 0;
  let forks: ForkMeta[] = [];

  /**
   * Charge le voisinage méta-graphe en une requête.
   *
   * Le backend borne le parcours en profondeur et en nombre de nœuds, donc la
   * réponse reste petite même sur une fiche très citée. L'appel est
   * inconditionnel : une fiche qui ne cite aucune autre fiche peut très bien
   * être citée par une autre, et rien dans son propre payload ne le dit.
   */
  async function loadNeighborhood() {
    let graph;
    try {
      graph = await api.cards.getGraph(card.creator.slug, card.slug, { depth: 3 });
    } catch {
      // Le méta-graphe est un bonus : son échec ne doit pas casser la vue.
      return;
    }
    const cards = new Map<string, NeighborCard>();
    const sources = new Map<string, GraphSourceData>();
    for (const n of graph.nodes) {
      if (n.kind === 'card') {
        const id = n.id.slice('card:'.length);
        cards.set(id, {
          id,
          title: n.title ?? 'Fiche',
          slug: n.slug ?? '',
          creatorSlug: n.creator_slug ?? '',
          creatorName: n.creator_name ?? null,
          authors: n.authors ?? null,
          sourcesCount: n.sources_count ?? 0,
        });
      } else {
        const id = n.id.slice('source:'.length);
        sources.set(id, {
          id,
          url: n.url ?? '',
          title: n.title ?? null,
          authors: n.authors ?? null,
          format: (n.format ?? '') in FORMAT_COLORS ? (n.format as SourceFormat) : 'texte',
          category:
            (n.category ?? '') in CATEGORY_COLORS ? (n.category as SourceCategory) : 'page-web',
          author_kind:
            (n.author_kind ?? '') in AUTHOR_COLORS ? (n.author_kind as AuthorKind) : 'individu',
          is_pivot: n.is_pivot ?? false,
          published_at: n.published_at ?? null,
          journal: n.journal ?? null,
          publisher: n.publisher ?? null,
          doi: n.doi ?? null,
          parent_source_id: null,
          linked_card_id: n.linked_card_id ?? null,
        });
      }
    }
    // Arêtes fiche → fiche telles que le backend les a parcourues, dans les
    // deux sens. Les déduire des seules sources visibles ne montrerait que ce
    // que la racine cite, jamais qui la cite ni les maillons plus lointains.
    cardLinks = graph.edges
      .filter((e) => e.kind === 'is_card')
      .map((e): [string, string] => [
        e.source.slice('card:'.length),
        e.target.slice('card:'.length),
      ]);
    // Les arêtes `cites` donnent l'appartenance source → fiche, dans l'ordre de
    // position renvoyé par le backend.
    const byCard = new Map<string, GraphSourceData[]>();
    for (const e of graph.edges) {
      if (e.kind !== 'cites') continue;
      const owner = e.source.slice('card:'.length);
      const src = sources.get(e.target.slice('source:'.length));
      if (!src) continue;
      if (!byCard.has(owner)) byCard.set(owner, []);
      byCard.get(owner)!.push(src);
    }
    // La fiche racine garde ses sources complètes, celles de l'API sont
    // appauvries (pas d'extraits, pas d'archive).
    byCard.delete(card.id);
    rootAuthors = cards.get(card.id)?.authors ?? null;
    cards.delete(card.id);
    neighborSources = byCard;
    neighborCards = cards;
    neighborhoodTruncated = graph.truncated;
  }

  // Pastilles de dépliage/repli. Un disque de rayon fixe tronquait « +306 » :
  // la pastille est une gélule dont la largeur suit le nombre affiché, et sa
  // hauteur reste la même pour que les deux actions se ressemblent. La taille
  // est aussi celle d'une cible tactile acceptable, ce qu'un disque de 8 px
  // de rayon n'était pas.
  const BADGE_HEIGHT = 18;
  const BADGE_FONT_SIZE = 11;

  function expandBadgeLabel(d: GraphNode): string {
    return `+${neighborCards.get(d.expandable ?? '')?.sourcesCount ?? 0}`;
  }

  /** Largeur d'une gélule pour un libellé, en approximant l'avance des chiffres. */
  function badgeWidth(label: string): number {
    return Math.max(BADGE_HEIGHT, label.length * BADGE_FONT_SIZE * 0.62 + 10);
  }

  /** Bord gauche de la gélule : là où se tenait le disque, à la diagonale. */
  function badgeX(d: GraphNode): number {
    return d.radius + 2 - BADGE_HEIGHT / 2;
  }

  /** Déplie la fiche visée par une source : ses propres sources apparaissent. */
  function expandCard(targetCardId: string, fromSourceId: string) {
    if (!neighborCards.has(targetCardId) || expandedCardIds.includes(targetCardId)) return;
    expandOrigin.set(targetCardId, fromSourceId);
    expandedCardIds = [...expandedCardIds, targetCardId];
    remount();
  }

  /** Replie une fiche : ses sources disparaissent, elle reste dans le graphe.
   *
   * Aucun repli en cascade : toutes les fiches du voisinage sont affichées en
   * permanence, replier l'une n'en rend aucune autre inatteignable.
   */
  function collapseCard(targetCardId: string) {
    if (!expandedCardIds.includes(targetCardId)) return;
    expandedCardIds = expandedCardIds.filter((id) => id !== targetCardId);
    remount();
  }

  function collapseAll() {
    if (expandedCardIds.length === 0) return;
    expandedCardIds = [];
    remount();
  }

  function remount() {
    selectSource(null);
    hoveredId = null;
    simulation?.stop();
    hasUserAdjustedView = false;
    hasAutoFitted = false;
    mountGraph();
  }

  function buildGraph(): { nodes: GraphNode[]; links: GraphLink[] } {
    const nodes: GraphNode[] = [
      {
        id: cardId,
        kind: 'card',
        label: card.title,
        ownerCardId: card.id,
        radius: 28,
        // La fiche consultée se distingue de ses voisines par un fond indigo
        // profond plutôt que par une étiquette : les autres nœuds fiche sont
        // ardoise, et le lecteur retrouve d'un regard d'où part sa lecture.
        fill: '#312e81',
        stroke: '#a5b4fc',
        tier: 'card',
      },
    ];
    const links: GraphLink[] = [];
    forks = [];

    const byAuthorAndParent = new Map<string, GraphSourceData[]>();
    // Fiches dont les sources sont à l'écran : la racine, plus celles qu'on a
    // dépliées. Ce sont elles qui déterminent quelles autres fiches entrent
    // dans le graphe.
    const ownerIds = [card.id, ...expandedCardIds];
    const sourcesOf = (id: string) =>
      id === card.id ? rootSources : (neighborSources.get(id) ?? []);

    // Toute fiche du voisinage est un nœud, qu'elle soit citée par la racine,
    // qu'elle la cite, ou qu'elle soit à deux sauts. Ne montrer que les fiches
    // atteignables depuis les sources affichées masquait les chaînes
    // A -> B -> C tant que B n'était pas dépliée, et tout le sens entrant.
    const cardNodeIds = new Map<string, string>([[card.id, cardId]]);
    const cardNodeByCid = new Map<string, GraphNode>();
    for (const [cid, meta] of neighborCards) {
      const nodeId = `card:${cid}`;
      cardNodeIds.set(cid, nodeId);
      const node: GraphNode = {
        id: nodeId,
        kind: 'card',
        label: meta.title,
        cardMeta: meta,
        ownerCardId: cid,
        // Une fiche dépliée est un peu plus petite que la racine : la
        // hiérarchie visuelle dit d'où part la lecture.
        expandable: expandedCardIds.includes(cid) || meta.sourcesCount === 0 ? undefined : cid,
        radius: 22,
        fill: '#1e293b',
        stroke: '#6366f1',
        tier: 'card',
      };
      cardNodeByCid.set(cid, node);
      nodes.push(node);
    }

    // Arêtes fiche → fiche : celles du backend font autorité, elles portent les
    // deux sens et les sauts que les sources visibles ne révèlent pas.
    const seenCardLinks = new Set<string>();
    for (const [from, to] of cardLinks) {
      const a = cardNodeIds.get(from);
      const b = cardNodeIds.get(to);
      if (!a || !b || a === b) continue;
      const key = `${a}|${b}`;
      if (seenCardLinks.has(key)) continue;
      seenCardLinks.add(key);
      links.push({ source: a, target: b, kind: 'meta' });
    }

    for (const ownerId of ownerIds) {
      const ownerNodeId = cardNodeIds.get(ownerId);
      if (!ownerNodeId) continue;
      for (const s of sourcesOf(ownerId)) {
        // La source EST cette fiche : elle est déjà rendue comme nœud fiche,
        // relié par l'arête ci-dessus. Un nœud source ferait doublon. Le nœud
        // fiche reprend la référence pour que son encadré reste ouvrable ; la
        // première rencontrée gagne, l'ordre des sources étant stable.
        if (s.linked_card_id && cardNodeIds.has(s.linked_card_id)) {
          const target = cardNodeByCid.get(s.linked_card_id);
          if (target && !target.absorbedSource) target.absorbedSource = s;
          continue;
        }
        const colors = sourceColor(s, colorMode);
        const isSecondary = s.parent_source_id !== null;
        let radius = 14;
        if (s.is_pivot) radius += 4;
        if (isSecondary) radius *= 0.75;
        radius = Math.max(8, Math.round(radius * densityScale));

        nodes.push({
          id: s.id,
          kind: 'source',
          label: s.title ?? s.url,
          source: s,
          ownerCardId: ownerId,
          radius,
          fill: colors.fill,
          stroke: colors.stroke,
          tier: isSecondary ? 'second' : 'first',
        });

        if (isSecondary && s.parent_source_id) {
          links.push({ source: s.id, target: s.parent_source_id, kind: 'parent' });
        } else {
          links.push({ source: ownerNodeId, target: s.id, kind: 'card' });
        }

        if (s.authors && s.authors.trim().length > 0) {
          const pid = isSecondary && s.parent_source_id ? s.parent_source_id : ownerNodeId;
          const key = `${s.authors.trim()}||${pid}`;
          if (!byAuthorAndParent.has(key)) byAuthorAndParent.set(key, []);
          byAuthorAndParent.get(key)!.push(s);
        }
      }
    }

    // Replace direct links with invisible junction + fork for Y-branch groups
    for (const [key, group] of byAuthorAndParent) {
      if (group.length < 2) continue;
      const pidStr = key.split('||')[1];
      const jxId = `junction:${++junctionCounter}`;
      nodes.push({
        id: jxId,
        kind: 'junction',
        label: '',
        ownerCardId: card.id,
        radius: 0,
        fill: 'transparent',
        stroke: 'transparent',
        tier: 'junction',
      });
      const linkKind = pidStr.startsWith('card:') ? 'card' : 'parent';
      links.push({ source: pidStr, target: jxId, kind: linkKind });
      for (const s of group) {
        const idx = links.findIndex(
          (l) =>
            (l.source === pidStr && l.target === s.id) || (l.source === s.id && l.target === pidStr)
        );
        if (idx !== -1) (links[idx] as GraphLink & { forkHide: true }).forkHide = true;
        links.push({ source: jxId, target: s.id, kind: linkKind });
      }
      forks.push({ junctionId: jxId, parentId: pidStr, childIds: group.map((s) => s.id) });
      if (group.length >= 2) {
        links.push({ source: group[0].id, target: group[1].id, kind: 'sibling' });
      }
    }

    // Index de recherche : calculé une fois par montage plutôt qu'à chaque
    // frappe, sinon 300 nœuds seraient re-normalisés à chaque caractère saisi.
    const index = new Map<string, string>();
    for (const n of nodes) {
      if (n.kind === 'junction') continue;
      index.set(n.id, haystackOf(n));
    }
    searchIndex = index;

    return { nodes, links };
  }

  function ticked(svgRoot: SVGSVGElement, nodes: GraphNode[], links: GraphLink[]) {
    const svg = select(svgRoot);

    // Pin only the junction at 60% — children are free but bound by a strong sibling link
    for (const fork of forks) {
      const jx = nodes.find((n) => n.id === fork.junctionId);
      if (!jx) continue;
      const parent = nodes.find((n) => n.id === fork.parentId);
      const children = fork.childIds
        .map((id) => nodes.find((n) => n.id === id))
        .filter(Boolean) as GraphNode[];
      if (!parent || children.length < 2) continue;

      const mx = children.reduce((s, c) => s + (c.x ?? 0), 0) / children.length;
      const my = children.reduce((s, c) => s + (c.y ?? 0), 0) / children.length;
      const px = parent.x ?? 0;
      const py = parent.y ?? 0;
      const dx = mx - px;
      const dy = my - py;

      jx.x = px + dx * 0.6;
      jx.y = py + dy * 0.6;
      jx.fx = jx.x;
      jx.fy = jx.y;
    }

    svg
      .selectAll<SVGLineElement, GraphLink>('.link')
      .data(links)
      .attr('x1', (d) => (d.source as GraphNode).x ?? 0)
      .attr('y1', (d) => (d.source as GraphNode).y ?? 0)
      .attr('x2', (d) => (d.target as GraphNode).x ?? 0)
      .attr('y2', (d) => (d.target as GraphNode).y ?? 0);

    svg
      .selectAll<SVGGElement, GraphNode>('.node')
      .data(nodes)
      .attr('transform', (d) => `translate(${d.x ?? 0}, ${d.y ?? 0})`);

    for (const n of nodes) {
      if (n.kind !== 'junction') posMemory.set(n.id, { x: n.x ?? 0, y: n.y ?? 0 });
    }
  }

  function setAnchorFromNode(d: GraphNode) {
    if (!container || !zoomBehavior) return;
    const k = zoomLevel;
    // Position in zoom-transformed coordinates ≈ container coordinates.
    // Approximation: the zoom transform maps (x,y) → (k*x + tx, k*y + ty);
    // we only need the visible point, which is what's currently rendered.
    if (svgEl) {
      const t = (svgEl as any).__zoom ?? null;
      const tx = t?.x ?? 0;
      const ty = t?.y ?? 0;
      panelAnchor = { x: (d.x ?? 0) * k + tx, y: (d.y ?? 0) * k + ty };
    } else {
      panelAnchor = { x: d.x ?? 0, y: d.y ?? 0 };
    }
  }

  function selectSource(s: Source | null, d?: GraphNode) {
    selectedSource = s;
    selectedCard = null;
    if (s && d) setAnchorFromNode(d);
    else panelAnchor = null;
    onSelect?.(s);
  }

  /** Encadré d'un nœud fiche : la racine se décrit elle-même, les autres via `cardMeta`. */
  function selectCard(d: GraphNode) {
    const m = d.cardMeta;
    selectedCard = m
      ? {
          title: m.title,
          authors: m.authors,
          creatorName: m.creatorName,
          creatorSlug: m.creatorSlug,
          slug: m.slug,
          sourcesCount: m.sourcesCount,
          isRoot: false,
        }
      : {
          title: card.title,
          authors: card.content_authors ?? rootAuthors,
          creatorName: card.creator.display_name,
          creatorSlug: card.creator.slug,
          slug: card.slug,
          description: card.description,
          contentUrl: card.content_url,
          publishedAt: card.published_at,
          sourcesCount: card.stats.total_sources,
          isRoot: true,
        };
    selectedSource = null;
    onSelect?.(null);
    setAnchorFromNode(d);
  }

  function mountGraph() {
    if (!svgEl) return;
    const { nodes, links } = buildGraph();

    const cardNode = nodes[0];
    cardNode.fx = width / 2;
    cardNode.fy = height / 2;

    // Réinjection des positions connues : après un dépliage, le graphe déjà à
    // l'écran doit rester en place et seul le nouveau rameau doit pousser.
    for (const n of nodes) {
      const known = posMemory.get(n.id);
      if (known) {
        n.x = known.x;
        n.y = known.y;
        continue;
      }
      // Nœud neuf : il naît au point d'où le dépliage a été demandé.
      const origin = posMemory.get(expandOrigin.get(n.ownerCardId) ?? '');
      if (origin) {
        n.x = origin.x + (Math.random() - 0.5) * 40;
        n.y = origin.y + (Math.random() - 0.5) * 40;
      }
    }

    const svg = select(svgEl);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Le graphe apparaît d'un bloc. Allumer les nœuds un à un laissait les
    // liens — dessinés d'emblée — flotter entre des extrémités encore
    // invisibles, et durait quinze secondes sur une fiche de 300 références.
    const root = svg.append('g').attr('class', 'graph-root').style('opacity', 0);
    root.transition().duration(350).style('opacity', 1);

    root
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'link')
      .attr('stroke', (d) => (d.kind === 'meta' ? '#6366f1' : '#94a3b8'))
      .attr('stroke-opacity', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        if (d.kind === 'meta') return 0.85;
        return d.kind === 'parent' ? 0.5 : 0.7;
      })
      .attr('stroke-width', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        if (d.kind === 'meta') return 2.5;
        return d.kind === 'parent' ? 1 : 1.5;
      })
      .attr('stroke-dasharray', (d) => (d.kind === 'parent' ? '4 3' : null))
      .style('pointer-events', (d) => {
        if ((d as any).forkHide) return 'none';
        if (d.kind === 'sibling') return 'none';
        return null;
      });

    const nodeG = root
      .append('g')
      .attr('class', 'nodes')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(nodes)
      .join('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .on('click', (_event, d) => {
        // Cliquer un nœud ouvre sa référence, qu'il soit rendu comme source ou
        // comme fiche : une référence qui fait l'objet d'une fiche reste une
        // référence, et son encadré doit rester atteignable. Déplier et replier
        // passent par les pastilles, seule action que le nœud gagne à porter.
        if (d.kind === 'source' && d.source) {
          selectSource(toSource(d.source), d);
        } else if (d.absorbedSource) {
          selectSource(toSource(d.absorbedSource), d);
        } else if (d.expandable) {
          expandCard(d.expandable, d.id);
        } else if (d.kind === 'card') {
          // Fiche racine, ou fiche voisine sans source à déplier : elle n'a pas
          // de référence propre à ouvrir, mais elle a de quoi se présenter.
          selectCard(d);
        } else {
          selectSource(null);
        }
      })
      .on('mouseenter', (_event, d) => {
        hoveredId = d.id;
      })
      .on('mouseleave', () => {
        hoveredId = null;
      });

    const dragHandler = drag<SVGGElement, GraphNode>()
      .on('start', (event: D3DragEvent<SVGGElement, GraphNode, GraphNode>, d) => {
        if (!event.active) simulation?.alphaTarget(0.25).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event: D3DragEvent<SVGGElement, GraphNode, GraphNode>, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event: D3DragEvent<SVGGElement, GraphNode, GraphNode>, d) => {
        if (!event.active) simulation?.alphaTarget(0);
        if (d.id !== cardId) {
          d.fx = null;
          d.fy = null;
        }
      });
    nodeG.call(dragHandler);

    nodeG
      .append('circle')
      .attr('class', 'node-circle')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => d.fill)
      .attr('stroke', (d) => d.stroke)
      .attr('stroke-width', (d) => (d.kind === 'card' ? 3 : 2));

    // Halo de la fiche consultée : un anneau plein, là où les fiches voisines
    // portent un anneau pointillé ou pâle. Redondant avec la couleur du fond,
    // à dessein — la distinction doit tenir même en vision des couleurs réduite.
    nodeG
      .filter((d) => d.id === cardId)
      .insert('circle', ':first-child')
      .attr('r', (d) => d.radius + 8)
      .attr('fill', 'none')
      .attr('stroke', '#a5b4fc')
      .attr('stroke-width', 2)
      .attr('stroke-opacity', 0.55);

    // Halo des fiches dépliées : elles ne sont pas des sources parmi d'autres,
    // ce sont des fiches Philum entières entrées dans le graphe. Les fiches
    // encore repliées portent l'anneau pointillé ci-dessous à la place.
    nodeG
      .filter((d) => d.kind === 'card' && !!d.cardMeta && !d.expandable)
      .insert('circle', ':first-child')
      .attr('r', (d) => d.radius + 7)
      .attr('fill', 'none')
      .attr('stroke', '#6366f1')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.35);

    // Fiche dépliable : anneau extérieur + pastille « +N ». Le nombre est
    // celui de ses sources : il annonce ce que le clic révèle.
    const expandableG = nodeG.filter((d) => !!d.expandable);
    expandableG
      .insert('circle', ':first-child')
      .attr('class', 'expand-ring')
      .attr('r', (d) => d.radius + 5)
      .attr('fill', 'none')
      .attr('stroke', '#6366f1')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6)
      .attr('stroke-dasharray', '3 3');
    expandableG
      .append('rect')
      .attr('class', 'expand-badge')
      // La gélule part du point où se tenait le disque et s'allonge vers
      // l'extérieur : la centrer ferait mordre « +306 » sur le nœud.
      .attr('x', (d) => badgeX(d))
      .attr('y', (d) => d.radius + 2 - BADGE_HEIGHT / 2)
      .attr('width', (d) => badgeWidth(expandBadgeLabel(d)))
      .attr('height', BADGE_HEIGHT)
      .attr('rx', BADGE_HEIGHT / 2)
      .attr('fill', '#6366f1')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .on('click', (event, d) => {
        // Sans arrêt de propagation, le clic remonterait au nœud et ouvrirait
        // l'encadré à la place du dépliage annoncé par la pastille.
        event.stopPropagation();
        if (d.expandable) expandCard(d.expandable, d.id);
      });
    expandableG
      .append('text')
      .attr('class', 'expand-badge-text')
      .attr('x', (d) => badgeX(d) + badgeWidth(expandBadgeLabel(d)) / 2)
      .attr('y', (d) => d.radius + 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', BADGE_FONT_SIZE)
      .attr('font-weight', 700)
      .attr('fill', '#ffffff')
      .style('pointer-events', 'none')
      .text(expandBadgeLabel);

    // Fiche dépliée : pastille « − » au même endroit, pour refermer. Le repli
    // était porté par le clic sur le nœud ; il lui fallait une prise à lui
    // depuis que ce clic ouvre l'encadré de la référence.
    const collapsibleG = nodeG.filter(
      (d) => !!d.cardMeta && expandedCardIds.includes(d.cardMeta.id)
    );
    collapsibleG
      .append('rect')
      .attr('class', 'collapse-badge')
      .attr('x', (d) => badgeX(d))
      .attr('y', (d) => d.radius + 2 - BADGE_HEIGHT / 2)
      .attr('width', BADGE_HEIGHT)
      .attr('height', BADGE_HEIGHT)
      .attr('rx', BADGE_HEIGHT / 2)
      .attr('fill', '#94a3b8')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 1.5)
      .on('click', (event, d) => {
        event.stopPropagation();
        if (d.cardMeta) collapseCard(d.cardMeta.id);
      });
    collapsibleG
      .append('text')
      .attr('class', 'collapse-badge-text')
      .attr('x', (d) => badgeX(d) + BADGE_HEIGHT / 2)
      .attr('y', (d) => d.radius + 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .attr('font-size', BADGE_FONT_SIZE + 1)
      .attr('font-weight', 700)
      .attr('fill', '#ffffff')
      .style('pointer-events', 'none')
      .text('−');

    // Auteurs du contenu au-dessus du nœud fiche (visible dès zoom >= 0.7).
    nodeG
      .filter((d) => d.kind === 'card')
      .append('text')
      .attr('class', 'card-creator')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => -(d.radius + 8))
      .attr('font-size', 12)
      .attr('font-weight', 600)
      .attr('fill', '#0f172a')
      .style('pointer-events', 'none')
      .text((d) => truncate(cardLabelOf(d), 30));

    // Card title above creator (shown only at higher zoom levels)
    nodeG
      .filter((d) => d.kind === 'card')
      .append('text')
      .attr('class', 'card-title-label')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => -(d.radius + 22))
      .attr('font-size', 10)
      .attr('fill', '#475569')
      .style('pointer-events', 'none')
      .text((d) => truncate(d.cardMeta ? d.cardMeta.title : card.title, 35));

    // Pivot star marker (now means "Source clé")
    nodeG
      .filter((d) => d.kind === 'source' && (d.source?.is_pivot ?? false))
      .append('circle')
      .attr('r', 3)
      .attr('cx', (d) => d.radius * 0.7)
      .attr('cy', (d) => -d.radius * 0.7)
      .attr('fill', '#facc15')
      .attr('stroke', '#a16207')
      .attr('stroke-width', 0.5);

    // Author label above each source node
    nodeG
      .filter((d) => d.kind === 'source')
      .append('text')
      .attr('class', 'author-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -(d.radius + 6))
      .attr('font-size', 11 * labelScale)
      .attr('font-weight', 500)
      .attr('fill', '#0f172a')
      .style('pointer-events', 'none')
      .text((d) => (d.source ? authorLabel(d.source) : ''));

    // Title (shown only at higher zoom levels)
    nodeG
      .filter((d) => d.kind === 'source')
      .append('text')
      .attr('class', 'title-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -(d.radius + 18))
      .attr('font-size', 10 * labelScale)
      .attr('fill', '#475569')
      // Halo blanc au survol : le titre passe alors au-dessus des liens et des
      // nœuds voisins sans avoir à réordonner le DOM (ce que `ticked` interdit,
      // sa liaison de données se fait par index).
      .style('paint-order', 'stroke')
      .style('pointer-events', 'none')
      .text((d) => (d.source ? truncate(d.source.title ?? '', 40) : ''));

    // Tooltip natif sur la fiche seule : sur une source, le titre s'affiche
    // desormais dans le graphe au survol, un second tooltip ferait doublon.
    nodeG
      .filter((d) => d.kind === 'card')
      .append('title')
      .text((d) => {
        if (!d.cardMeta) return card.title;
        if (d.expandable) {
          return `Fiche Philum : ${d.cardMeta.title} — cliquer pour déplier ses sources`;
        }
        if (d.cardMeta.sourcesCount === 0) {
          return `Fiche Philum : ${d.cardMeta.title} — aucune source`;
        }
        return `${d.cardMeta.title} — cliquer pour replier`;
      });

    simulation = forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance((l) => {
            const src = typeof l.source === 'string' ? l.source : l.source.id;
            const tgt = typeof l.target === 'string' ? l.target : l.target.id;
            if (src.startsWith('junction:') || tgt.startsWith('junction:')) return 5;
            // Deux fiches reliées : l'arête porte maintenant deux gros nœuds à
            // ses extrémités, il lui faut plus de place qu'à une source.
            if (l.kind === 'meta') return 150 * spacingBoost;
            if (l.kind === 'parent') return 75 * spacingBoost;
            if (l.kind === 'sibling') return 55 * spacingBoost;
            return 130 * spacingBoost;
          })
          .strength((l) => {
            const src = typeof l.source === 'string' ? l.source : l.source.id;
            const tgt = typeof l.target === 'string' ? l.target : l.target.id;
            if (src.startsWith('junction:') || tgt.startsWith('junction:')) return 0.05;
            if (l.kind === 'meta') return 0.9;
            if (l.kind === 'sibling') return 2.0;
            return 0.55;
          })
      )
      .force('charge', forceManyBody().strength(-200 * spacingBoost))
      .force('center', forceCenter(width / 2, height / 2).strength(0.05))
      .force(
        'collide',
        // Le nom d'auteur est dessiné au-dessus du nœud : la marge de collision
        // doit lui laisser la place, sinon deux étiquettes se superposent.
        forceCollide<GraphNode>().radius((d) => d.radius + 8 * spacingBoost)
      )
      .on('tick', () => {
        if (svgEl) ticked(svgEl, nodes, links);
        // Le maillage s'étale d'autant plus qu'il y a de sources : sans
        // recadrage, une fiche de 152 références déborde du cadre et oblige
        // l'utilisateur à dézoomer avant de voir quoi que ce soit. On recadre
        // dès que la disposition est stable, sans attendre l'évènement `end`
        // que la simulation peut ne jamais émettre si l'utilisateur interagit.
        if (!hasUserAdjustedView && (simulation?.alpha() ?? 1) < 0.06) {
          hasAutoFitted = true;
          fitToNodes(nodes);
        }
      });

    layoutNodes = nodes;

    zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        root.attr('transform', event.transform.toString());
        zoomLevel = event.transform.k;
        // `sourceEvent` n'est présent que si le zoom vient d'un geste : dès que
        // l'utilisateur cadre lui-même, le recadrage automatique se retire.
        if (event.sourceEvent) hasUserAdjustedView = true;
      });
    svg.call(zoomBehavior);
  }

  /** Recadre la vue pour que tous les nœuds tiennent dans le cadre. */
  function fitToNodes(nodes: GraphNode[], duration = 0) {
    if (!svgEl || !zoomBehavior || nodes.length === 0) return;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const n of nodes) {
      // La marge couvre le rayon du nœud et l'étiquette dessinée au-dessus.
      const pad = n.radius + 26;
      minX = Math.min(minX, (n.x ?? 0) - pad);
      maxX = Math.max(maxX, (n.x ?? 0) + pad);
      minY = Math.min(minY, (n.y ?? 0) - pad);
      maxY = Math.max(maxY, (n.y ?? 0) + pad);
    }
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    const k = Math.min(4, Math.max(0.1, Math.min(width / spanX, height / spanY)));
    fitScale = k;
    const tx = width / 2 - k * ((minX + maxX) / 2);
    const ty = height / 2 - k * ((minY + maxY) / 2);
    const target = zoomIdentity.translate(tx, ty).scale(k);
    const sel = select(svgEl);
    if (duration > 0) sel.transition().duration(duration).call(zoomBehavior.transform, target);
    else sel.call(zoomBehavior.transform, target);
  }

  function resetView() {
    if (!svgEl || !zoomBehavior) return;
    hasUserAdjustedView = false;
    if (layoutNodes.length > 0) fitToNodes(layoutNodes, 400);
    else select(svgEl).transition().duration(400).call(zoomBehavior.transform, zoomIdentity);
  }

  function zoomBy(factor: number) {
    if (!svgEl || !zoomBehavior) return;
    select(svgEl).transition().duration(200).call(zoomBehavior.scaleBy, factor);
  }

  async function toggleFullscreen() {
    if (!container) return;
    if (!document.fullscreenElement) {
      try {
        await container.requestFullscreen();
      } catch {
        // ignore
      }
    } else {
      try {
        await document.exitFullscreen();
      } catch {
        // ignore
      }
    }
  }

  function onFullscreenChange() {
    isFullscreen = !!document.fullscreenElement;
    simulation?.alpha(0.3).restart();
    selectSource(null);
  }

  onMount(() => {
    if (!container) return;
    const rect = container.getBoundingClientRect();
    width = Math.max(rect.width, 320);
    height = Math.max(rect.height, 360);
    mountGraph();
    // Filet : si la simulation est encore agitée passé ce délai, on recadre
    // quand même pour ne jamais laisser l'utilisateur devant un graphe tronqué.
    autoFitFallback = window.setTimeout(() => {
      if (!hasAutoFitted && layoutNodes.length > 0) {
        hasAutoFitted = true;
        fitToNodes(layoutNodes);
      }
    }, 2500);

    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const nextW = Math.max(entry.contentRect.width, 320);
        const nextH = Math.max(entry.contentRect.height, 360);
        if (Math.abs(nextW - width) < 4 && Math.abs(nextH - height) < 4) continue;
        width = nextW;
        height = nextH;
        if (simulation) {
          hasAutoFitted = false;
          simulation
            .force('center', forceCenter(width / 2, height / 2).strength(0.05))
            .alpha(0.3)
            .restart();
        }
        if (svgEl) select(svgEl).attr('viewBox', `0 0 ${width} ${height}`);
      }
    });
    resizeObserver.observe(container);
    document.addEventListener('fullscreenchange', onFullscreenChange);

    // Le voisinage arrive après coup : on ne remonte le graphe que s'il révèle
    // quelque chose de neuf, pour ne pas réanimer pour rien. Les auteurs de la
    // racine en font partie — les étiquettes sont posées impérativement par d3,
    // sans remontage le nœud garderait le nom de son créateur.
    void loadNeighborhood().then(() => {
      if (neighborCards.size > 0 || rootAuthors) mountGraph();
    });
  });

  onDestroy(() => {
    if (autoFitFallback !== undefined) clearTimeout(autoFitFallback);
    simulation?.stop();
    resizeObserver?.disconnect();
    if (typeof document !== 'undefined') {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    }
  });

  // Opacité des nœuds. Survol et recherche agissent tous deux dessus : traités
  // dans deux effets séparés, le dernier exécuté écraserait l'autre.
  $effect(() => {
    const matched = matchedIds;
    const hovered = hoveredId;
    if (!svgEl) return;
    const svg = select(svgEl);
    svg.selectAll<SVGGElement, GraphNode>('.node').style('opacity', (d) => {
      if (matched && !matched.has(d.id)) return 0.08;
      if (hovered !== null && d.id !== hovered) return 0.35;
      return 1;
    });
    svg.selectAll<SVGLineElement, GraphLink>('.link').style('opacity', (d) => {
      const src = typeof d.source === 'string' ? d.source : d.source.id;
      const tgt = typeof d.target === 'string' ? d.target : d.target.id;
      // Une arête reste visible dès qu'une de ses extrémités correspond : c'est
      // elle qui dit à quelle fiche le résultat est rattaché.
      if (matched) return matched.has(src) || matched.has(tgt) ? 0.9 : 0.05;
      if (hovered === null) return 1;
      return src === hovered || tgt === hovered ? 1 : 0.2;
    });
  });

  /** Recadre la vue sur les résultats de recherche. */
  function fitToMatches() {
    const matched = matchedIds;
    if (!matched || matched.size === 0) return;
    // Le recadrage automatique de la simulation reprendrait la main au tick
    // suivant et annulerait celui-ci.
    hasUserAdjustedView = true;
    fitToNodes(
      layoutNodes.filter((n) => matched.has(n.id)),
      400
    );
  }

  function clearQuery() {
    query = '';
    resetView();
  }

  // Recolore les nœuds au changement d'axe, sans re-monter la simulation.
  $effect(() => {
    const mode = colorMode;
    if (!svgEl) return;
    select(svgEl)
      .selectAll<SVGCircleElement, GraphNode>('circle.node-circle')
      .transition()
      .duration(250)
      .attr('fill', (d) => {
        if (d.kind !== 'source' || !d.source) return d.fill;
        const c = sourceColor(d.source, mode);
        d.fill = c.fill;
        return c.fill;
      })
      .attr('stroke', (d) => {
        if (d.kind !== 'source' || !d.source) return d.stroke;
        const c = sourceColor(d.source, mode);
        d.stroke = c.stroke;
        return c.stroke;
      });
  });

  // Seuils de zoom pour les étiquettes, et titre au survol.
  //
  // Le titre d'une source apparaît dès que la souris entre dans son nœud et
  // disparaît quand elle en sort, quel que soit le zoom. Quand le zoom affiche
  // déjà les titres, le survol le passe en version complète et en surbrillance.
  $effect(() => {
    if (!svgEl) return;
    const svg = select(svgEl);
    const showAuthor = zoomLevel >= 0.7 * fitScale;
    const showTitle = zoomLevel >= 1.5 * fitScale;
    const hovered = hoveredId;
    // Un résultat de recherche affiche son titre quel que soit le zoom : sans
    // lui, l'utilisateur voit un point allumé sans savoir ce qu'il a trouvé.
    const matched = matchedIds;
    svg
      .selectAll<SVGTextElement, GraphNode>('text.author-label, text.card-creator')
      .style('display', showAuthor ? '' : 'none');
    svg
      .selectAll<SVGTextElement, GraphNode>('text.title-label')
      .style('display', (d) => (showTitle || d.id === hovered || matched?.has(d.id) ? '' : 'none'))
      .attr('font-weight', (d) => (d.id === hovered ? 600 : null))
      .attr('fill', (d) => (d.id === hovered ? '#0f172a' : '#475569'))
      .attr('stroke', (d) => (d.id === hovered ? '#ffffff' : null))
      .attr('stroke-width', (d) => (d.id === hovered ? 3 : null))
      .text((d) => {
        if (!d.source) return '';
        if (d.id === hovered) return truncate(d.source.title ?? d.source.url, 90);
        return truncate(d.source.title ?? '', 40);
      });
    svg
      .selectAll<SVGTextElement, GraphNode>('text.card-title-label')
      .style('display', (d) => (showTitle || matched?.has(d.id) ? '' : 'none'));
  });
</script>

<div bind:this={container} class="relative w-full h-full bg-white">
  <svg
    bind:this={svgEl}
    class="w-full h-full block"
    role="img"
    aria-label="Graphe interactif des sources"
  ></svg>

  <div class="absolute top-3 left-3 flex flex-col items-start gap-1.5">
    <div
      class="flex items-center gap-1.5 rounded-md bg-white/95 border border-slate-200 shadow-sm px-2 py-1.5 text-xs"
    >
      <svg
        viewBox="0 0 24 24"
        class="w-3.5 h-3.5 shrink-0 text-slate-400"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="M20 20l-3.5-3.5" stroke-linecap="round" />
      </svg>
      <input
        bind:value={query}
        onkeydown={(e) => e.key === 'Enter' && fitToMatches()}
        type="search"
        class="w-40 sm:w-52 bg-transparent outline-none placeholder:text-slate-400 text-slate-800"
        placeholder="Titre, auteur, revue, DOI…"
        aria-label="Rechercher une référence dans le graphe"
      />
      {#if query}
        <button
          type="button"
          onclick={clearQuery}
          class="shrink-0 text-slate-400 hover:text-slate-700"
          aria-label="Effacer la recherche"
          title="Effacer la recherche"
        >
          <svg
            viewBox="0 0 24 24"
            class="w-3.5 h-3.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
          </svg>
        </button>
      {/if}
    </div>

    {#if matchedIds}
      <div
        class="flex items-center gap-2 rounded-md bg-white/95 border border-slate-200 shadow-sm px-2 py-1 text-xs text-slate-600"
        aria-live="polite"
      >
        <span>
          {matchedIds.size === 0
            ? 'Aucun résultat'
            : `${matchedIds.size} résultat${matchedIds.size > 1 ? 's' : ''}`}
        </span>
        {#if matchedIds.size > 0}
          <button
            type="button"
            onclick={fitToMatches}
            class="text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Recadrer
          </button>
        {/if}
      </div>
    {/if}

    <div
      class="flex items-center rounded-md bg-white/95 border border-slate-200 shadow-sm overflow-hidden text-xs"
      role="group"
      aria-label="Axe de couleur des nœuds"
    >
      {#each colorModeOptions as opt, i (opt.value)}
        <button
          type="button"
          onclick={() => (colorMode = opt.value)}
          class="px-2.5 py-1.5 transition-colors {i > 0
            ? 'border-l border-slate-200'
            : ''} {colorMode === opt.value
            ? 'bg-slate-800 text-white font-medium'
            : 'text-slate-600 hover:bg-slate-50'}"
          aria-pressed={colorMode === opt.value}
          title="Colorer par {opt.label.toLowerCase()}"
        >
          {opt.label}
        </button>
      {/each}
    </div>
  </div>

  <div class="absolute top-3 right-3 flex flex-col gap-1.5">
    <button
      onclick={() => zoomBy(1.25)}
      class="w-8 h-8 rounded-md bg-white/95 border border-slate-200 shadow-sm hover:bg-slate-50 flex items-center justify-center text-slate-700"
      aria-label="Zoom avant"
      title="Zoom avant"
    >
      <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    </button>
    <button
      onclick={() => zoomBy(0.8)}
      class="w-8 h-8 rounded-md bg-white/95 border border-slate-200 shadow-sm hover:bg-slate-50 flex items-center justify-center text-slate-700"
      aria-label="Zoom arrière"
      title="Zoom arrière"
    >
      <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    </button>
    <button
      onclick={resetView}
      class="w-8 h-8 rounded-md bg-white/95 border border-slate-200 shadow-sm hover:bg-slate-50 flex items-center justify-center text-slate-700"
      aria-label="Recentrer"
      title="Recentrer"
    >
      <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="3 9 3 3 9 3" />
        <polyline points="21 15 21 21 15 21" />
        <line x1="3" y1="3" x2="10" y2="10" />
        <line x1="14" y1="14" x2="21" y2="21" />
      </svg>
    </button>
    <button
      onclick={toggleFullscreen}
      class="w-8 h-8 rounded-md bg-white/95 border border-slate-200 shadow-sm hover:bg-slate-50 flex items-center justify-center text-slate-700"
      aria-label={isFullscreen ? 'Quitter le plein écran' : 'Plein écran'}
      title={isFullscreen ? 'Quitter le plein écran' : 'Plein écran'}
    >
      {#if isFullscreen}
        <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 3v6H3" />
          <path d="M15 3v6h6" />
          <path d="M9 21v-6H3" />
          <path d="M15 21v-6h6" />
        </svg>
      {:else}
        <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 9V4h5" />
          <path d="M20 9V4h-5" />
          <path d="M4 15v5h5" />
          <path d="M20 15v5h-5" />
        </svg>
      {/if}
    </button>
  </div>

  <div
    class="absolute bottom-3 left-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs bg-white/90 border border-slate-200 rounded-md px-2.5 py-1.5 backdrop-blur-sm"
  >
    {#each legendEntries as c (c.label)}
      <span class="inline-flex items-center gap-1.5 text-slate-700">
        <span
          class="inline-block w-2.5 h-2.5 rounded-full border"
          style:background-color={c.fill}
          style:border-color={c.stroke}
        ></span>
        {c.label}
      </span>
    {/each}
  </div>

  {#if neighborCards.size > 0}
    <div
      class="absolute bottom-3 right-3 max-w-[min(22rem,60%)] flex flex-col items-end gap-1.5 text-xs"
    >
      {#if expandedCardIds.length > 0}
        <div class="flex flex-wrap justify-end gap-1">
          {#each expandedCardIds as id (id)}
            {@const meta = neighborCards.get(id)}
            {#if meta}
              <button
                type="button"
                onclick={() => collapseCard(id)}
                class="inline-flex items-center gap-1 rounded-full border border-indigo-300 bg-indigo-50 px-2 py-0.5 text-indigo-800 hover:bg-indigo-100"
                title="Replier « {meta.title} »"
              >
                <span class="truncate max-w-[10rem]">{meta.title}</span>
                <span aria-hidden="true">×</span>
              </button>
            {/if}
          {/each}
          <button
            type="button"
            onclick={collapseAll}
            class="rounded-full border border-slate-300 bg-white px-2 py-0.5 text-slate-600 hover:bg-slate-50"
          >
            Tout replier
          </button>
        </div>
      {:else}
        <p
          class="rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm"
        >
          {neighborCards.size} fiche{neighborCards.size > 1 ? 's' : ''} Philum reliée{neighborCards.size >
          1
            ? 's'
            : ''} — cliquez la pastille « + » pour déplier ses sources, le nœud pour voir sa référence.
        </p>
      {/if}
      {#if neighborhoodTruncated}
        <p class="text-slate-500">Voisinage partiel : trop de fiches reliées pour tout afficher.</p>
      {/if}
    </div>
  {/if}

  <SourceDetailPanel
    source={selectedSource}
    {card}
    anchor={panelAnchor}
    containerWidth={width}
    containerHeight={height}
    onClose={() => selectSource(null)}
    onSelect={(s) => selectSource(s)}
  />

  <CardDetailPanel
    info={selectedCard}
    anchor={panelAnchor}
    containerWidth={width}
    containerHeight={height}
    onClose={() => (selectedCard = null)}
  />
</div>
