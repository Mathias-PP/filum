<script lang="ts">
  import {
    drag,
    forceCenter,
    forceCollide,
    forceLink,
    forceManyBody,
    forceSimulation,
    forceX,
    forceY,
    select,
    zoom,
    zoomIdentity,
    type D3DragEvent,
    type Selection,
    type Simulation,
    type ZoomBehavior,
    type ZoomTransform,
  } from 'd3';
  import { onDestroy, onMount } from 'svelte';

  import { api } from '$lib/api';
  import type {
    AuthorKind,
    CardDetail,
    Source,
    SourceCategory,
    SourceFormat,
    SourceStance,
  } from '$lib/api';
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
  import {
    GRAPH_CAP_COMFORT,
    GRAPH_SOURCE_CAP,
    capSources,
    keySourcesOnly,
  } from '$lib/utils/graph-cap';
  import { authorSummary } from '$lib/utils/author-names';
  import { UNDATED_BAND, chronoLayout, type ChronoLayout } from '$lib/utils/graph-chrono';
  import { buildHaystack, matchesAllTerms, searchTerms } from '$lib/utils/graph-search';
  import { STANCE_ORDER, STANCE_STYLES, stanceStroke } from '$lib/utils/stance';
  import { legendLabel } from './graph-legend';
  import CardDetailPanel, { type CardPanelInfo } from './CardDetailPanel.svelte';
  import SourceDetailPanel from './SourceDetailPanel.svelte';

  interface Props {
    card: CardDetail;
    onSelect?: (source: Source | null) => void;
  }

  let { card, onSelect }: Props = $props();

  type NodeKind = 'card' | 'source' | 'junction';

  /** Arête fiche → fiche : origine, cible, rapport déclaré. */
  type CardLink = [string, string, SourceStance | null];

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
    linked_card_slug: string | null;
    linked_card_creator_slug: string | null;
    /** Rapport déclaré au propos : colore le trait qui mène à la source. */
    stance: SourceStance | null;
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
        stance: s.stance,
        is_pivot: s.is_pivot,
        archive_status: 'pending',
        archive_url: null,
        archive_timestamp: null,
        parent_source_id: null,
        linked_card_id: s.linked_card_id,
        linked_card_slug: s.linked_card_slug ?? null,
        linked_card_creator_slug: s.linked_card_creator_slug ?? null,
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
    /**
     * Demi-largeur de l'étiquette toujours visible, mesurée après rendu.
     *
     * Sert à la force de séparation : sans elle, un nom d'auteur long n'est
     * qu'un cercle de plus pour la simulation, et se pose sur son voisin.
     */
    labelHalfWidth?: number;
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
    /** Rapport déclaré par la source qui porte l'arête, s'il y en a un. */
    stance?: SourceStance | null;
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
  /** Panneau d'options, mesuré pour que le recadrage ne cache rien derrière. */
  let overlayEl = $state<HTMLDivElement | null>(null);
  /** Colonne de zoom, réservée au même titre que le panneau d'options. */
  let controlsEl = $state<HTMLDivElement | null>(null);
  let layoutNodes: GraphNode[] = [];
  let hasAutoFitted = false;
  let hasUserAdjustedView = false;
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
  let cardLinks = $state<CardLink[]>([]);
  let neighborSources = new Map<string, GraphSourceData[]>();
  let expandedCardIds = $state<string[]>([]);
  let neighborhoodTruncated = $state(false);
  /**
   * Fiches maintenues à l'écran quelle que soit la profondeur.
   *
   * Épingler est le contrepoids du repli automatique : un lecteur qui a trouvé
   * une fiche à trois sauts ne doit pas la perdre parce qu'il replie le chemin
   * qui l'y a mené.
   */
  let pinnedCardIds = $state<string[]>([]);

  function togglePin(cid: string) {
    pinnedCardIds = pinnedCardIds.includes(cid)
      ? pinnedCardIds.filter((id) => id !== cid)
      : [...pinnedCardIds, cid];
    remount();
  }
  // La légende explique un geste qu'on n'apprend qu'une fois. Elle doit donc
  // pouvoir disparaître, et rester disparue le temps de la session : la
  // rouvrir à chaque remontage la transformerait en bandeau publicitaire.
  let legendOpen = $state(true);

  /**
   * Sens de lecture du méta-graphe.
   *
   * `sortant` : ce que cette fiche cite. `entrant` : ce qui cite cette fiche.
   * `deux` : les deux, distingués par la flèche. Le défaut est `deux` parce
   * que le sens entrant est la moitié de la valeur du graphe ; c'était son
   * illisibilité, pas sa présence, qui posait problème.
   */
  type GraphDirection = 'sortant' | 'entrant' | 'deux';
  let direction = $state<GraphDirection>('deux');
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
      linked_card_slug: null,
      linked_card_creator_slug: null,
      stance: s.stance ?? null,
      full: s,
    }))
  );

  // Bornage. Une fiche de 152 références affichées d'un coup ne montre rien :
  // les nœuds se touchent et les étiquettes se recouvrent. Le graphe s'ouvre
  // sur une portion lisible et annonce ce qu'il garde en réserve — l'inverse
  // d'un masquage silencieux. Le plafond se règle : c'est au lecteur de dire
  // où passe, pour lui, la limite du lisible. `0` = aucun plafond.
  let sourceCap = $state<number>(GRAPH_SOURCE_CAP);

  // Lire une bibliographie de bout en bout n'est pas toujours la question :
  // « sur quoi cela repose-t-il d'abord ? » se répond en ne gardant que ce que
  // la créatrice ou le créateur a lui-même marqué comme clé. Aucun tri n'est
  // deviné, donc le filtre ne s'offre que si une marque existe.
  let keyOnly = $state(false);

  /** Panneau des réglages d'affichage : déplié à l'ouverture. */
  let controlsOpen = $state(true);
  /** Réglage du plafond : replié à l'ouverture, son chiffre restant lisible. */
  let capOpen = $state(false);

  /** Références d'une fiche, filtrées puis bornées. Même règle partout. */
  function cappedOf(sources: GraphSourceData[]): GraphSourceData[] {
    const scoped = keyOnly ? keySourcesOnly(sources) : sources;
    return capSources(scoped, sourceCap).kept;
  }

  /** Au moins une source porte la marque « clé », quelque part à l'écran. */
  const hasKeySources = $derived.by(() => {
    if (rootSources.some((s) => s.is_pivot)) return true;
    for (const id of expandedCardIds) {
      if ((neighborSources.get(id) ?? []).some((s) => s.is_pivot)) return true;
    }
    return false;
  });

  /** Tout ce qui est actuellement à l'écran : racine + fiches dépliées. */
  const visibleSources = $derived.by(() => {
    const all = [...cappedOf(rootSources)];
    for (const id of expandedCardIds) all.push(...cappedOf(neighborSources.get(id) ?? []));
    return all;
  });

  /** Nombre total de références disponibles, filtre et bornage ignorés. */
  const totalSources = $derived.by(() => {
    let n = rootSources.length;
    for (const id of expandedCardIds) n += (neighborSources.get(id) ?? []).length;
    return n;
  });

  /**
   * Références que le filtre en cours retient, avant bornage.
   *
   * Le plafond se règle sur cet ensemble et non sur la fiche entière : sinon
   * « 18 / 18 » s'afficherait alors que le filtre « clés » en écarte la
   * moitié, et le chiffre annoncerait une réserve qui n'est pas celle du
   * plafond.
   */
  const scopedTotal = $derived.by(() => {
    const count = (list: GraphSourceData[]) =>
      keyOnly ? keySourcesOnly(list).length : list.length;
    let n = count(rootSources);
    for (const id of expandedCardIds) n += count(neighborSources.get(id) ?? []);
    return n;
  });

  const hiddenSourcesCount = $derived(Math.max(0, scopedTotal - visibleSources.length));

  /**
   * Valeur montrée par le réglage.
   *
   * Le plafond par défaut vaut 250, mais une fiche de dix références n'en a
   * pas 250 à cacher : afficher ce chiffre laisserait croire qu'il en manque.
   */
  const capValue = $derived(Math.min(sourceCap, scopedTotal));

  // Deux axes de lecture. Le réseau dit qui dépend de qui ; il ne dit rien de
  // l'ancienneté. « Cette affirmation s'appuie sur un article de 1998 » est une
  // information que le maillage ne peut pas porter, d'où le second mode.
  let layoutMode = $state<'network' | 'chrono'>('network');
  const layoutModeOptions: { value: 'network' | 'chrono'; label: string; help: string }[] = [
    { value: 'network', label: 'Réseau', help: 'Disposer les nœuds selon leurs liens' },
    { value: 'chrono', label: 'Chronologie', help: 'Disposer les nœuds par année de publication' },
  ];

  /** Marge horizontale de la frise, pour que rien ne colle au bord du cadre. */
  const CHRONO_MARGIN = 60;
  /** Hauteur du bandeau d'années, réservée en haut du cadre. */
  const CHRONO_HEADER_HEIGHT = 24;

  /**
   * Ordonnée des panneaux flottants du haut.
   *
   * En chronologie, le bandeau d'années occupe les premiers pixels du cadre :
   * les panneaux posés à `top-3` recouvraient les graduations, c'est-à-dire la
   * seule clé de lecture de ce mode. Ils descendent donc sous le bandeau.
   */
  const overlayTop = $derived(layoutMode === 'chrono' ? CHRONO_HEADER_HEIGHT + 12 : 12);

  interface ChronoHeaderTick {
    x: number;
    label: string;
    muted: boolean;
  }

  let chronoTicks: ChronoHeaderTick[] = [];
  /** Abscisse du filet de rupture dans le repère du graphe, `null` s'il n'y en a pas. */
  let chronoBreakX: number | null = null;

  // Légende : uniquement les valeurs présentes à l'écran.
  const legendEntries = $derived.by(() => {
    const seen = new Map<string, NodeColor>();
    for (const s of visibleSources) {
      const c = sourceColor(s, colorMode);
      if (!seen.has(c.label)) seen.set(c.label, c);
    }
    return [...seen.values()];
  });

  // Légende des traits. Absente tant qu'aucune source n'a de rapport déclaré :
  // une légende qui explique une couleur invisible n'apprend rien et occupe la
  // place sur les fiches — la majorité — qui n'annotent pas leur bibliographie.
  const stanceLegend = $derived.by(() => {
    const present = new Set(visibleSources.map((s) => s.stance).filter(Boolean));
    return STANCE_ORDER.filter((k) => present.has(k)).map((k) => ({
      key: k,
      ...STANCE_STYLES[k],
    }));
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

  /**
   * Année d'un nœud, ou chaîne vide si elle est inconnue.
   *
   * Même source de vérité que la frise : un nœud fiche n'a pas de date propre,
   * il prend celle de la référence qu'il absorbe. Les deux modes doivent dater
   * un nœud à l'identique, sinon la frise contredirait l'étiquette.
   */
  function nodeYear(d: GraphNode): string {
    const raw =
      d.source?.published_at ??
      d.absorbedSource?.published_at ??
      (d.id === cardId ? card.published_at : null);
    if (!raw) return '';
    const y = new Date(raw).getFullYear();
    return Number.isNaN(y) ? '' : String(y);
  }

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

  /**
   * Référence dont un nœud tire sa couleur, `null` s'il n'en a aucune.
   *
   * Une fiche citée par une autre est aussi une référence du graphe : la
   * citation lui a donné un type d'auteur, un format et une catégorie. Rien
   * ne justifie alors de la peindre en ardoise à part, hors du code couleur
   * commun — ce qui la désigne comme fiche est son anneau, pas son fond. La
   * fiche consultée, elle, n'est citée par rien à l'écran : faute de
   * classification saisie, elle garde son indigo.
   */
  function colorSourceOf(d: GraphNode): GraphSourceData | null {
    if (d.kind === 'source') return d.source ?? null;
    if (d.kind === 'card') return d.absorbedSource ?? null;
    return null;
  }

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

  // Premier nom seul par défaut : c'est le réglage qui tient sur un graphe
  // dense sans rien affirmer de faux, « et al. » disant que la liste continue.
  let showFirstAuthor = $state(true);
  let showLastAuthor = $state(false);

  function authorLabel(s: GraphSourceData): string {
    if (s.authors && s.authors.trim().length > 0) {
      return truncate(
        authorSummary(s.authors, { first: showFirstAuthor, last: showLastAuthor }),
        30
      );
    }
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
          linked_card_slug: n.linked_card_slug ?? null,
          linked_card_creator_slug: n.linked_card_creator_slug ?? null,
          stance: (n.stance ?? null) as SourceStance | null,
        });
      }
    }
    // Arêtes fiche → fiche telles que le backend les a parcourues, dans les
    // deux sens. Les déduire des seules sources visibles ne montrerait que ce
    // que la racine cite, jamais qui la cite ni les maillons plus lointains.
    cardLinks = graph.edges
      .filter((e) => e.kind === 'is_card')
      .map((e): CardLink => [
        e.source.slice('card:'.length),
        e.target.slice('card:'.length),
        (e.stance ?? null) as SourceStance | null,
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
  const BADGE_HEIGHT = 24;
  const BADGE_FONT_SIZE = 13;

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

  function setSourceCap(cap: number) {
    // Un plafond au-delà du nombre réel de références revient à tout afficher :
    // on le ramène là plutôt que de laisser un chiffre qui promet plus que la
    // fiche ne contient.
    const clamped = Number.isFinite(cap) ? Math.max(1, Math.min(Math.round(cap), totalSources)) : 1;
    if (sourceCap === clamped) return;
    sourceCap = clamped;
    remount();
  }

  function toggleKeyOnly() {
    keyOnly = !keyOnly;
    remount();
  }

  function setLayoutMode(mode: 'network' | 'chrono') {
    if (layoutMode === mode) return;
    layoutMode = mode;
    // Les positions mémorisées viennent de l'autre disposition : les rejouer
    // ferait démarrer la frise depuis un maillage, avec un long réarrangement.
    posMemory.clear();
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
        // Plus gros qu'une référence, mais pas au point d'écraser le maillage :
        // le rapport de taille suffit à dire la hiérarchie. Le nœud suit la
        // densité comme les autres, sinon il grossit relativement sur une
        // grosse fiche, là où justement la place manque.
        radius: Math.max(15, Math.round(22 * densityScale)),
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
      cappedOf(id === card.id ? rootSources : (neighborSources.get(id) ?? []));

    // Fiches retenues à l'affichage : la racine, ses dépliées, ses épinglées,
    // et celles à un saut de l'une de ces ancres dans les deux sens.
    // Les fiches à deux sauts n'apparaissent qu'une fois leur amont déplié.
    const anchorIds = new Set<string>([card.id, ...expandedCardIds, ...pinnedCardIds]);
    const visibleCardIds = new Set<string>(anchorIds);
    for (const [from, to] of cardLinks) {
      if (anchorIds.has(from)) visibleCardIds.add(to);
      if (anchorIds.has(to)) visibleCardIds.add(from);
    }

    const cardNodeIds = new Map<string, string>([[card.id, cardId]]);
    const cardNodeByCid = new Map<string, GraphNode>();
    for (const [cid, meta] of neighborCards) {
      if (!visibleCardIds.has(cid)) continue;
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
        radius: Math.max(13, Math.round(19 * densityScale)),
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
    for (const [from, to, stance] of cardLinks) {
      const a = cardNodeIds.get(from);
      const b = cardNodeIds.get(to);
      if (!a || !b || a === b) continue;
      // `from` cite `to`. Le sens demandé se lit depuis la fiche consultée :
      // une arête qui part d'elle est sortante, une qui arrive est entrante.
      // Les arêtes entre deux voisines ne concernent aucun des deux sens
      // exclusifs : elles ne s'affichent qu'en vue complète.
      if (direction === 'sortant' && from !== card.id) continue;
      if (direction === 'entrant' && to !== card.id) continue;
      const key = `${a}|${b}`;
      if (seenCardLinks.has(key)) continue;
      seenCardLinks.add(key);
      links.push({ source: a, target: b, kind: 'meta', stance });
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
          links.push({
            source: s.id,
            target: s.parent_source_id,
            kind: 'parent',
            stance: s.stance,
          });
        } else {
          links.push({ source: ownerNodeId, target: s.id, kind: 'card', stance: s.stance });
        }

        if (s.authors && s.authors.trim().length > 0) {
          const pid = isSecondary && s.parent_source_id ? s.parent_source_id : ownerNodeId;
          const key = `${s.authors.trim()}||${pid}`;
          if (!byAuthorAndParent.has(key)) byAuthorAndParent.set(key, []);
          byAuthorAndParent.get(key)!.push(s);
        }
      }
    }

    // L'absorption ci-dessus vient de dire quelles fiches sont aussi des
    // références du graphe. Elles rejoignent maintenant le code couleur commun :
    // se lire « article scientifique » ou « institution » comme les autres nœuds
    // vaut mieux qu'un ardoise uniforme qui n'apprend rien.
    for (const node of cardNodeByCid.values()) {
      const s = colorSourceOf(node);
      if (!s) continue;
      const c = sourceColor(s, colorMode);
      node.fill = c.fill;
      node.stroke = c.stroke;
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
        links.push({ source: jxId, target: s.id, kind: linkKind, stance: s.stance });
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

  /**
   * Point d'arrivée d'une arête orientée : le bord du nœud cible, pas son
   * centre. Sans ce recul, la pointe de flèche disparaît sous le disque et le
   * sens redevient invisible.
   */
  function edgeStop(s: GraphNode, t: GraphNode): { x: number; y: number } {
    const sx = s.x ?? 0;
    const sy = s.y ?? 0;
    const tx = t.x ?? 0;
    const ty = t.y ?? 0;
    const dx = tx - sx;
    const dy = ty - sy;
    const dist = Math.hypot(dx, dy);
    if (dist === 0) return { x: tx, y: ty };
    const back = (t.radius ?? 14) + 3;
    return { x: tx - (dx / dist) * back, y: ty - (dy / dist) * back };
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
      .attr('x2', (d) => {
        const t = d.target as GraphNode;
        if (d.kind !== 'meta') return t.x ?? 0;
        return edgeStop(d.source as GraphNode, t).x;
      })
      .attr('y2', (d) => {
        const t = d.target as GraphNode;
        if (d.kind !== 'meta') return t.y ?? 0;
        return edgeStop(d.source as GraphNode, t).y;
      });

    // Jointure par identifiant, pas par position : les nœuds porteurs d'une
    // pastille sont remontés en fin de liste DOM pour rester au premier plan,
    // et un appariement par index leur donnerait alors les coordonnées d'un
    // autre nœud.
    const place = (selector: string) =>
      svg
        .selectAll<SVGGElement, GraphNode>(selector)
        .data(nodes, (d) => d.id)
        .attr('transform', (d) => `translate(${d.x ?? 0}, ${d.y ?? 0})`);
    place('.node');
    // Les étiquettes vivent dans leur propre calque : elles suivent le nœud sans
    // partager son groupe. Deux liaisons distinctes, car une sélection mêlant
    // les deux compterait deux éléments par donnée et n'en placerait qu'un.
    place('.node-label');

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
          id: d.id,
          title: m.title,
          authors: m.authors,
          creatorName: m.creatorName,
          creatorSlug: m.creatorSlug,
          slug: m.slug,
          sourcesCount: m.sourcesCount,
          isRoot: false,
        }
      : {
          id: d.id,
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

  /**
   * Repères de la frise : graduations d'années et enclos des sources sans date.
   *
   * Les traits couvrent délibérément bien plus que le cadre : la simulation
   * étale les nœuds verticalement sans borne connue à l'avance, et un repère
   * qui s'arrête avant les nœuds qu'il gradue ne repère plus rien. Les
   * années, elles, vivent dans un bandeau à part (`drawChronoHeader`).
   */
  function drawChronoAxis(
    root: Selection<SVGGElement, unknown, null, undefined>,
    chrono: ChronoLayout
  ) {
    const g = root.append('g').attr('class', 'chrono-axis').style('pointer-events', 'none');
    const span = 8000;

    if (chrono.undatedX !== null) {
      g.append('rect')
        .attr('x', CHRONO_MARGIN)
        .attr('y', -span)
        .attr('width', UNDATED_BAND)
        .attr('height', span * 2)
        .attr('fill', '#f1f5f9')
        .attr('stroke', '#e2e8f0')
        .attr('stroke-dasharray', '4 4');
    }

    // Filet de rupture : l'échelle s'interrompt ici. Sans ce signe, la colonne
    // « sans date » se lit comme la première décennie de la frise — mesuré à
    // l'usage sur une frise 1935-2021, où elle passait pour « 1940-1960 ».
    if (chrono.breakX !== null) {
      g.append('line')
        .attr('x1', chrono.breakX + CHRONO_MARGIN)
        .attr('x2', chrono.breakX + CHRONO_MARGIN)
        .attr('y1', -span)
        .attr('y2', span)
        .attr('stroke', '#cbd5e1')
        .attr('stroke-width', 1.5)
        .attr('stroke-dasharray', '2 6');
    }

    for (const t of chrono.ticks) {
      g.append('line')
        .attr('x1', t.x + CHRONO_MARGIN)
        .attr('x2', t.x + CHRONO_MARGIN)
        .attr('y1', -span)
        .attr('y2', span)
        .attr('stroke', '#e2e8f0')
        .attr('stroke-width', 1);
    }
  }

  /**
   * Bandeau des années, posé HORS du groupe zoomable et à hauteur fixe.
   *
   * Accroché au sommet du nuage de points, il sortait du cadre par le haut dès
   * que la simulation étirait la frise : les dates, qui sont la seule clé de
   * lecture de ce mode, se retrouvaient rognées. Ici elles restent lisibles
   * quel que soit le déplacement vertical, et suivent l'axe horizontalement.
   */
  function drawChronoHeader(
    svg: Selection<SVGSVGElement, unknown, null, undefined>,
    chrono: ChronoLayout
  ) {
    chronoTicks = chrono.ticks.map((t) => ({
      x: t.x + CHRONO_MARGIN,
      label: String(t.year),
      muted: false,
    }));
    if (chrono.undatedX !== null) {
      chronoTicks.push({
        x: chrono.undatedX + CHRONO_MARGIN,
        label: `sans date (${chrono.undatedCount})`,
        muted: true,
      });
    }

    const g = svg.append('g').attr('class', 'chrono-header').style('pointer-events', 'none');
    g.append('rect')
      .attr('x', 0)
      .attr('y', 0)
      .attr('width', width)
      .attr('height', CHRONO_HEADER_HEIGHT)
      // Opaque : sous un fond translucide, les nœuds qui passent derrière se
      // lisaient comme des fantômes au milieu des années.
      .attr('fill', '#ffffff');
    g.append('line')
      .attr('x1', 0)
      .attr('x2', width)
      .attr('y1', CHRONO_HEADER_HEIGHT)
      .attr('y2', CHRONO_HEADER_HEIGHT)
      .attr('stroke', '#e2e8f0');
    g.selectAll('text')
      .data(chronoTicks)
      .join('text')
      .attr('y', CHRONO_HEADER_HEIGHT - 7)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .attr('fill', (d) => (d.muted ? '#94a3b8' : '#475569'));

    // Marque de rupture d'échelle, la convention usuelle du « ⁄⁄ » : elle
    // interrompt visiblement la règle des années, pour que la colonne « sans
    // date » ne se lise pas comme sa première graduation.
    chronoBreakX = chrono.breakX === null ? null : chrono.breakX + CHRONO_MARGIN;
    if (chronoBreakX !== null) {
      const b = g.append('g').attr('class', 'chrono-break');
      b.append('rect')
        .attr('x', -7)
        .attr('y', CHRONO_HEADER_HEIGHT - 5)
        .attr('width', 14)
        .attr('height', 10)
        .attr('fill', '#ffffff');
      for (const dx of [-3, 2]) {
        b.append('line')
          .attr('x1', dx - 2)
          .attr('x2', dx + 3)
          .attr('y1', CHRONO_HEADER_HEIGHT + 4)
          .attr('y2', CHRONO_HEADER_HEIGHT - 4)
          .attr('stroke', '#94a3b8')
          .attr('stroke-width', 1.5)
          .attr('stroke-linecap', 'round');
      }
    }
    placeChronoHeader(zoomIdentity);
  }

  /** Replace les années selon le cadrage courant. Seul x suit le zoom. */
  function placeChronoHeader(transform: ZoomTransform) {
    if (!svgEl || chronoTicks.length === 0) return;
    if (chronoBreakX !== null) {
      const bx = transform.applyX(chronoBreakX);
      select(svgEl)
        .select('g.chrono-header')
        .select('g.chrono-break')
        .attr('transform', `translate(${bx},0)`)
        .style('display', bx < 0 || bx > width ? 'none' : '');
    }
    const ticks = select(svgEl)
      .select('g.chrono-header')
      .selectAll<SVGTextElement, ChronoHeaderTick>('text')
      .text((d) => d.label)
      .attr('x', (d) => transform.applyX(d.x));

    // Élagage de gauche à droite. Une graduation poussée hors cadre par la
    // navigation ne doit pas s'écraser contre le bord, et deux années trop
    // proches se chevauchaient en une bouillie de chiffres — « 20202026 » là
    // où la frise s'achevait sur l'année de la fiche. Mieux vaut une règle
    // moins graduée qu'une règle illisible.
    let lastRight = -Infinity;
    ticks.style('display', function (d) {
      const sx = transform.applyX(d.x);
      if (sx < 24 || sx > width - 24) return 'none';
      // Un onglet en arrière-plan ne mesure pas son texte : `getComputedText-
      // Length` y renvoie 0, et l'élagage laissait alors passer les
      // chevauchements jusqu'au prochain rendu. À défaut de mesure, une
      // estimation par le nombre de caractères, à cette taille de police.
      const measured = this.getComputedTextLength();
      const half = (measured > 0 ? measured : d.label.length * 6.8) / 2;
      if (sx - half < lastRight + 8) return 'none';
      lastRight = sx + half;
      return '';
    });
  }

  /**
   * Écarte les nœuds dont les étiquettes se recouvrent.
   *
   * `forceCollide` raisonne en cercles ; une étiquette est une boîte large et
   * plate. Un rayon assez grand pour dégager « NIH — National Institute of
   * Neurological… » aurait éparpillé tout le graphe. On déplace donc chaque
   * paire selon l'axe où le recouvrement est le moindre : deux étiquettes
   * larges se séparent verticalement, ce qui les empile au lieu de les
   * superposer, et laisse intacte l'abscisse dont la frise a besoin.
   */
  function separateLabels(nodes: GraphNode[], strength: number, lockX: boolean) {
    const halfWidth = (d: GraphNode) => d.labelHalfWidth ?? d.radius;
    const halfHeight = (d: GraphNode) => d.radius + 18;
    for (let i = 0; i < nodes.length; i += 1) {
      const a = nodes[i];
      if (a.kind === 'junction') continue;
      for (let j = i + 1; j < nodes.length; j += 1) {
        const b = nodes[j];
        if (b.kind === 'junction') continue;
        const dx = (b.x ?? 0) - (a.x ?? 0);
        const overlapX = halfWidth(a) + halfWidth(b) + 6 - Math.abs(dx);
        if (overlapX <= 0) continue;
        const dy = (b.y ?? 0) - (a.y ?? 0);
        const overlapY = halfHeight(a) + halfHeight(b) + 4 - Math.abs(dy);
        if (overlapY <= 0) continue;
        // En frise, l'abscisse porte la date : la déplacer ferait mentir le
        // bandeau d'années. Le dégagement s'y fait donc en hauteur seulement.
        if (lockX || overlapY <= overlapX) {
          const push = (overlapY / 2) * strength * (dy < 0 ? -1 : 1);
          a.y = (a.y ?? 0) - push;
          b.y = (b.y ?? 0) + push;
        } else {
          const push = (overlapX / 2) * strength * (dx < 0 ? -1 : 1);
          a.x = (a.x ?? 0) - push;
          b.x = (b.x ?? 0) + push;
        }
      }
    }
  }

  function forceLabelSeparation(lockX: boolean) {
    let nodes: GraphNode[] = [];
    const force = (alpha: number) => separateLabels(nodes, alpha, lockX);
    force.initialize = (n: GraphNode[]) => {
      nodes = n;
    };
    return force;
  }

  function mountGraph() {
    if (!svgEl) return;
    const { nodes, links } = buildGraph();

    // Frise. Les nœuds de jonction n'ont pas de date propre : ils restent
    // libres et suivent les liens, sinon ils tireraient leurs branches vers une
    // année qu'ils n'ont pas.
    const chrono: ChronoLayout | null =
      layoutMode === 'chrono'
        ? chronoLayout(
            nodes
              .filter((n) => n.tier !== 'junction')
              .map((n) => ({
                id: n.id,
                // Un nœud fiche n'a pas de date propre : on prend celle de la
                // référence qu'il absorbe, et la fiche racine connaît la sienne.
                published_at:
                  n.source?.published_at ??
                  n.absorbedSource?.published_at ??
                  (n.id === cardId ? card.published_at : null),
              })),
            width - CHRONO_MARGIN * 2
          )
        : null;
    const chronoX = (id: string): number | undefined => {
      const v = chrono?.x.get(id);
      return v === undefined ? undefined : v + CHRONO_MARGIN;
    };

    const cardNode = nodes[0];
    // En frise, la fiche prend sa place dans le temps comme les autres ; la
    // river au centre lui donnerait une date qu'elle n'a pas.
    cardNode.fx = chrono ? (chronoX(cardNode.id) ?? width / 2) : width / 2;
    cardNode.fy = height / 2;

    // En frise, l'abscisse EST la date. Une simple force de rappel ne suffit
    // pas : le lien qui relie une source à la fiche qui la cite tire vers
    // l'autre bout de la frise, et l'équilibre se pose à côté de l'année. Le
    // bandeau annonçait alors une date que le nœud démentait — Cajal, 1911, se
    // posait sous 1950. Chaque nœud daté est donc rivé à son année ; seuls les
    // nœuds sans date (jonctions comprises) restent libres.
    if (chrono) {
      for (const n of nodes) {
        const x = chronoX(n.id);
        if (x !== undefined) n.fx = x;
      }
    }

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
    chronoTicks = [];
    chronoBreakX = null;

    // Le graphe apparaît d'un bloc. Allumer les nœuds un à un laissait les
    // liens — dessinés d'emblée — flotter entre des extrémités encore
    // invisibles, et durait quinze secondes sur une fiche de 300 références.
    // Flèches de sens pour les arêtes fiche → fiche. Un marqueur SVG n'hérite
    // pas du stroke de son trait : on en déclare un par couleur de rapport.
    const arrowDefs = svg.append('defs');
    const ARROW_COLORS: Record<string, string> = {
      default: '#6366f1',
      appuie: STANCE_STYLES['appuie'].stroke,
      'nuance-contredit': STANCE_STYLES['nuance-contredit'].stroke,
      contexte: STANCE_STYLES['contexte'].stroke,
      mentionne: STANCE_STYLES['mentionne'].stroke,
    };
    for (const [key, color] of Object.entries(ARROW_COLORS)) {
      arrowDefs
        .append('marker')
        .attr('id', `arrow-${key}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 10)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-4L9,0L0,4')
        .attr('fill', color);
    }

    const root = svg.append('g').attr('class', 'graph-root').style('opacity', 0);
    root.transition().duration(350).style('opacity', 1);

    if (chrono) drawChronoAxis(root, chrono);

    root
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'link')
      // Le rapport déclaré prime : voir d'un coup d'œil ce qui contredit le
      // propos est le seul intérêt de l'annoter. Sans rapport, le trait garde
      // sa couleur d'origine.
      .attr('stroke', (d) =>
        d.stance ? stanceStroke(d.stance) : d.kind === 'meta' ? '#6366f1' : '#94a3b8'
      )
      .attr('stroke-opacity', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        if (d.kind === 'meta') return 0.85;
        if (d.stance) return 0.9;
        return d.kind === 'parent' ? 0.5 : 0.7;
      })
      .attr('stroke-width', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        // Un rapport déclaré se lit à la couleur du trait, pas à sa masse :
        // 2.5 px empâtait le maillage dès qu'une fiche déclarait ses rapports
        // sur la majorité de ses sources. L'écart avec un lien muet reste
        // perceptible à 1.6 px, sans que le trait devienne un objet.
        if (d.kind === 'meta') return 1.8;
        if (d.stance) return 1.6;
        return d.kind === 'parent' ? 1 : 1.2;
      })
      .attr('stroke-dasharray', (d) => (d.kind === 'parent' ? '4 3' : null))
      .attr('marker-end', (d) => {
        // Seules les arêtes fiche → fiche portent un sens interprétable par le
        // lecteur. Une source appartient à sa fiche, ce n'est pas une citation
        // orientée : lui coller une flèche suggérerait une lecture fausse.
        if (d.kind !== 'meta') return null;
        if ((d as any).forkHide) return null;
        return `url(#arrow-${d.stance ?? 'default'})`;
      })
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
          // Relâché en frise, un nœud daté retrouve son année : le déplacer à
          // la main peut réordonner la hauteur, jamais la date.
          d.fx = chronoX(d.id) ?? null;
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
    // Au premier plan : la pastille est une commande, pas une décoration. Un
    // nœud voisin dessiné après elle la recouvrait, et l'action annoncée
    // devenait injoignable là où le graphe est dense — c'est-à-dire là où
    // déplier une fiche sert le plus.
    const expandableG = nodeG.filter((d) => !!d.expandable).raise();
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
    const collapsibleG = nodeG
      .filter((d) => !!d.cardMeta && expandedCardIds.includes(d.cardMeta.id))
      .raise();
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

    // Calque des étiquettes, peint après *tous* les nœuds.
    //
    // Tant que chaque libellé vivait dans le groupe de son nœud, le nœud suivant
    // le recouvrait : « Corinne Purtill » se lisait « Corinne Purtill…ME », le
    // milieu du nom disparaissant sous une sphère voisine. Le halo blanc ne
    // pouvait rien contre ça — il dégage la lettre du fond, pas d'un objet peint
    // par-dessus. Les séparer règle le cas quel que soit l'ordre des nœuds.
    const labelG = root
      .append('g')
      .attr('class', 'labels')
      .style('pointer-events', 'none')
      .selectAll<SVGGElement, GraphNode>('g')
      .data(nodes)
      .join('g')
      .attr('class', 'node-label');

    // Auteurs du contenu au-dessus du nœud fiche (visible dès zoom >= 0.7).
    labelG
      .filter((d) => d.kind === 'card')
      .append('text')
      .attr('class', 'card-creator')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => -(d.radius + 8))
      // Un cran au-dessus du nom d'auteur d'une source (11), et soumis à la
      // même densité : en taille fixe, l'étiquette de fiche restait à 12 pendant
      // que celles des sources tombaient à 8 sur une grosse fiche — un écart de
      // moitié, là où le nœud de fiche n'a besoin que de se distinguer.
      .attr('font-size', 12 * labelScale)
      .attr('font-weight', 600)
      .attr('fill', '#0f172a')
      // Halo blanc permanent — cf. `title-label` pour le pourquoi.
      .style('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .style('pointer-events', 'none')
      .text((d) => truncate(cardLabelOf(d), 30));

    // Card title above creator (shown only at higher zoom levels)
    labelG
      .filter((d) => d.kind === 'card')
      .append('text')
      .attr('class', 'card-title-label')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => -(d.radius + 22))
      .attr('font-size', 10.5 * labelScale)
      .attr('fill', '#475569')
      .style('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
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
    labelG
      .filter((d) => d.kind === 'source')
      .append('text')
      .attr('class', 'author-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -(d.radius + 6))
      .attr('font-size', 11 * labelScale)
      .attr('font-weight', 500)
      .attr('fill', '#0f172a')
      .style('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .style('pointer-events', 'none')
      .text((d) => (d.source ? authorLabel(d.source) : ''));

    // Title (shown only at higher zoom levels)
    labelG
      .filter((d) => d.kind === 'source')
      .append('text')
      .attr('class', 'title-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => -(d.radius + 18))
      .attr('font-size', 10 * labelScale)
      .attr('fill', '#475569')
      // Halo blanc permanent : un libellé qui croise un lien devenait illisible,
      // le trait passant au milieu des lettres. `paint-order: stroke` dessine le
      // contour *sous* le remplissage, de sorte que le halo dégage la lettre
      // sans l'épaissir — et sans réordonner le DOM, ce que `ticked` interdit
      // (sa liaison de données se fait par index).
      .style('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .style('pointer-events', 'none')
      .text((d) => (d.source ? truncate(d.source.title ?? '', 40) : ''));

    // Date sous chaque nœud, au même seuil de zoom que le nom d'auteur : situer
    // une référence dans le temps compte autant que savoir qui l'a écrite, et
    // en mode réseau c'est la seule façon de le lire. « s. d. » quand la date
    // est inconnue — une place vide se confondrait avec un défaut d'affichage.
    labelG
      .filter((d) => d.kind !== 'junction')
      .append('text')
      .attr('class', 'date-label')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => d.radius + 13)
      .attr('font-size', 10 * labelScale)
      .attr('fill', (d) => (nodeYear(d) ? '#64748b' : '#cbd5e1'))
      .style('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 3)
      .attr('stroke-linejoin', 'round')
      .style('pointer-events', 'none')
      .text((d) => nodeYear(d) || 's. d.');

    // Mesure des étiquettes une fois le texte posé, avant la simulation.
    //
    // Seule l'étiquette visible au repos compte : le titre n'apparaît qu'au
    // zoom 3×, où les nœuds sont déjà loin les uns des autres à l'écran.
    labelG.each(function (d) {
      const text = this.querySelector<SVGTextElement>('text.author-label, text.card-creator');
      const width = text ? text.getComputedTextLength() : 0;
      d.labelHalfWidth = Math.max(d.radius, width / 2);
    });

    // Tooltip natif sur la fiche seule : sur une source, le titre s'affiche
    // desormais dans le graphe au survol, un second tooltip ferait doublon.
    nodeG
      .filter((d) => d.kind === 'card')
      .append('title')
      .text((d) => {
        if (!d.cardMeta) return card.title;
        if (d.expandable) {
          return `Fiche Philum : ${d.cardMeta.title}, cliquer pour déplier ses sources`;
        }
        if (d.cardMeta.sourcesCount === 0) {
          return `Fiche Philum : ${d.cardMeta.title}, aucune source`;
        }
        return `${d.cardMeta.title}, cliquer pour replier`;
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
            // Une référence appartient à sa fiche : la tenir à distance la
            // faisait lire comme un satellite lointain plutôt que comme un
            // membre de la bibliographie.
            return 65 * spacingBoost;
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
      // En frise, le recentrage combattrait l'axe : une source de 1998 serait
      // ramenée vers le milieu et mentirait sur sa date.
      .force('center', chrono ? null : forceCenter(width / 2, height / 2).strength(0.05))
      .force(
        'chronoX',
        chrono
          ? forceX<GraphNode>((d) => chronoX(d.id) ?? d.x ?? width / 2).strength((d) =>
              chronoX(d.id) === undefined ? 0 : 1
            )
          : null
      )
      // Rappel vertical faible : sans lui, la répulsion étire la frise en une
      // bande si haute qu'aucun zoom ne la rend lisible.
      .force('chronoY', chrono ? forceY<GraphNode>(height / 2).strength(0.04) : null)
      // Aplatissement à l'aspect du cadre.
      //
      // La disposition en réseau tend vers un disque, le cadre est deux fois
      // plus large que haut : le recadrage automatique était donc limité par la
      // hauteur, et perdait la moitié de la largeur en marges vides. Rapprocher
      // la nuée d'une ellipse de même aspect que le cadre laisse le zoom monter
      // d'autant, ce qui écarte les nœuds à l'écran sans les écarter dans la
      // simulation — et sans rapetisser le texte, contrairement à un simple
      // allongement des liens.
      .force(
        'flatten',
        chrono
          ? null
          : forceY<GraphNode>(height / 2).strength(Math.max(0, 0.15 * (1 - height / width)))
      )
      .force(
        'collide',
        // Le nom d'auteur est dessiné au-dessus du nœud : la marge de collision
        // doit lui laisser la place, sinon deux étiquettes se superposent.
        forceCollide<GraphNode>().radius((d) => d.radius + 8 * spacingBoost)
      )
      .force('labels', forceLabelSeparation(Boolean(chrono)))
      .on('tick', () => {
        if (svgEl) ticked(svgEl, nodes, links);
      });

    layoutNodes = nodes;

    zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        root.attr('transform', event.transform.toString());
        zoomLevel = event.transform.k;
        placeChronoHeader(event.transform);
        // `sourceEvent` n'est présent que si le zoom vient d'un geste : dès que
        // l'utilisateur cadre lui-même, le recadrage automatique se retire.
        if (event.sourceEvent) hasUserAdjustedView = true;
      });
    svg.call(zoomBehavior);

    if (chrono) drawChronoHeader(svg, chrono);

    // Disposition déroulée d'un seul coup, avant le premier rendu.
    //
    // On laissait auparavant la simulation se refroidir à l'écran, puis on
    // recadrait : le graphe s'affichait, l'utilisateur commençait à le lire, et
    // deux à trois secondes plus tard tout sautait à une autre échelle. Le
    // calcul est le même, il a simplement lieu avant que quiconque regarde. La
    // vue est ensuite posée une fois pour toutes ; les interactions (glisser un
    // nœud, déplier une fiche) relancent la simulation sans jamais recadrer.
    simulation.stop();
    const settleTicks = Math.ceil(
      Math.log(simulation.alphaMin()) / Math.log(1 - simulation.alphaDecay())
    );
    simulation.tick(settleTicks);
    // Dégagement final des étiquettes, une fois la simulation froide.
    //
    // Pendant le refroidissement la séparation s'efface avec alpha, comme
    // toute autre force — sans quoi elle continuerait de pousser un graphe déjà
    // arrêté et, en frise, éloignerait les nœuds de leur date. Elle s'achève
    // donc ici, seule, quand plus aucune force ne la contredit : c'est là
    // qu'elle peut résoudre les derniers recouvrements sans rien déranger.
    for (let i = 0; i < 60; i += 1) separateLabels(nodes, 0.4, Boolean(chrono));
    ticked(svgEl, nodes, links);
    if (!hasUserAdjustedView) {
      hasAutoFitted = true;
      fitToNodes(nodes);
    }
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
      // En largeur, c'est l'étiquette qui déborde : cadrer sur le seul rayon
      // laissait « Tonegawa Lab, MIT » se faire couper par le bord du cadre.
      const padX = Math.max(n.radius, n.labelHalfWidth ?? 0) + 12;
      const padY = n.radius + 26;
      minX = Math.min(minX, (n.x ?? 0) - padX);
      maxX = Math.max(maxX, (n.x ?? 0) + padX);
      minY = Math.min(minY, (n.y ?? 0) - padY);
      maxY = Math.max(maxY, (n.y ?? 0) + padY);
    }
    const spanX = Math.max(maxX - minX, 1);
    const spanY = Math.max(maxY - minY, 1);
    // Le bandeau d'années occupe le haut du cadre : le graphe se cale dessous,
    // sinon les nœuds les plus hauts passent derrière les dates.
    const topInset = layoutMode === 'chrono' ? CHRONO_HEADER_HEIGHT + 6 : 0;
    const usableH = Math.max(height - topInset, 1);
    // Le panneau d'options flotte sur la gauche du cadre : sans cette réserve,
    // le recadrage centrait le graphe sur toute la largeur et poussait les
    // nœuds de gauche derrière le champ de recherche. Mesuré plutôt que codé en
    // dur, parce que sa largeur change avec le repli des réglages et la langue.
    // Sur un cadre étroit la réserve est abandonnée entièrement plutôt que
    // rabotée : céder la moitié de la largeur donnerait un graphe minuscule
    // ET toujours à moitié caché. Le panneau redevient alors ce qu'il est sur
    // mobile, une couche par-dessus qu'on replie ou qu'on écarte d'un geste.
    const reserve = (el: HTMLElement | null, max: number) => {
      const w = el ? el.offsetWidth + 20 : 0;
      return w > max ? 0 : w;
    };
    const leftInset = reserve(overlayEl, width / 3);
    const rightInset = reserve(controlsEl, width / 6);
    const usableW = Math.max(width - leftInset - rightInset, 1);
    const k = Math.min(4, Math.max(0.1, Math.min(usableW / spanX, usableH / spanY)));
    fitScale = k;
    const tx = leftInset + usableW / 2 - k * ((minX + maxX) / 2);
    const ty = topInset + usableH / 2 - k * ((minY + maxY) / 2);
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
    // Le passage en plein écran ne change pas les liens : réchauffer la
    // simulation ferait dériver une disposition que l'utilisateur vient de
    // lire. Le redimensionnement qui suit se contente de recadrer.
    selectSource(null);
  }

  onMount(() => {
    if (!container) return;
    const rect = container.getBoundingClientRect();
    width = Math.max(rect.width, 320);
    height = Math.max(rect.height, 360);
    mountGraph();

    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const nextW = Math.max(entry.contentRect.width, 320);
        const nextH = Math.max(entry.contentRect.height, 360);
        if (Math.abs(nextW - width) < 4 && Math.abs(nextH - height) < 4) continue;
        width = nextW;
        height = nextH;
        // On recadre sans recalculer la disposition : relancer la simulation
        // ferait bouger tous les nœuds pour un simple changement de cadre, et
        // l'utilisateur perdrait le graphe qu'il était en train de lire.
        if (svgEl) {
          select(svgEl).attr('viewBox', `0 0 ${width} ${height}`);
          select(svgEl).select('g.chrono-header').select('rect').attr('width', width);
          select(svgEl).select('g.chrono-header').select('line').attr('x2', width);
        }
        if (!hasUserAdjustedView && layoutNodes.length > 0) fitToNodes(layoutNodes);
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
    simulation?.stop();
    resizeObserver?.disconnect();
    if (typeof document !== 'undefined') {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    }
  });

  // Changer de sens change la topologie : la simulation doit repartir, sinon
  // les nœuds retirés laissent un trou et ceux ajoutés apparaissent au centre.
  $effect(() => {
    direction;
    if (!svgEl) return;
    remount();
  });

  // Opacité des nœuds. Survol et recherche agissent tous deux dessus : traités
  // dans deux effets séparés, le dernier exécuté écraserait l'autre.
  $effect(() => {
    const matched = matchedIds;
    const hovered = hoveredId;
    if (!svgEl) return;
    const svg = select(svgEl);
    // L'étiquette s'estompe avec son nœud : laissée à pleine opacité dans son
    // calque séparé, elle aurait surnagé au-dessus d'un graphe effacé par la
    // recherche, et désigné des nœuds que la recherche venait d'écarter.
    const fade = (d: GraphNode) => {
      if (matched && !matched.has(d.id)) return 0.08;
      if (hovered !== null && d.id !== hovered) return 0.35;
      return 1;
    };
    svg.selectAll<SVGGElement, GraphNode>('.node').style('opacity', fade);
    svg.selectAll<SVGGElement, GraphNode>('.node-label').style('opacity', fade);
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
        const s = colorSourceOf(d);
        if (!s) return d.fill;
        const c = sourceColor(s, mode);
        d.fill = c.fill;
        return c.fill;
      })
      .attr('stroke', (d) => {
        const s = colorSourceOf(d);
        if (!s) return d.stroke;
        const c = sourceColor(s, mode);
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
    // Seuil haut : à 1,5× les titres apparaissaient encore alors que les nœuds
    // se touchaient, et le texte d'un nœud recouvrait celui de ses voisins. Il
    // faut être assez près pour qu'un titre ne parle que de son propre nœud.
    const showTitle = zoomLevel >= 3 * fitScale;
    const hovered = hoveredId;
    // Un résultat de recherche affiche son titre quel que soit le zoom : sans
    // lui, l'utilisateur voit un point allumé sans savoir ce qu'il a trouvé.
    const matched = matchedIds;
    svg
      .selectAll<SVGTextElement, GraphNode>('text.author-label, text.card-creator, text.date-label')
      .style('display', showAuthor ? '' : 'none');
    // Le réglage « premier / dernier auteur » se relit ici plutôt que par un
    // remontage : changer un libellé n'a pas à rejouer la simulation.
    svg
      .selectAll<SVGTextElement, GraphNode>('text.author-label')
      .text((d) => (d.source ? authorLabel(d.source) : ''));
    svg
      .selectAll<SVGTextElement, GraphNode>('text.title-label')
      .style('display', (d) => (showTitle || d.id === hovered || matched?.has(d.id) ? '' : 'none'))
      .attr('font-weight', (d) => (d.id === hovered ? 600 : null))
      .attr('fill', (d) => (d.id === hovered ? '#0f172a' : '#475569'))
      // Le halo est permanent ; le survol l'élargit seulement, parce que le
      // titre complet y est plus long et croise donc davantage de liens.
      .attr('stroke-width', (d) => (d.id === hovered ? 4 : 3))
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

  <div
    bind:this={overlayEl}
    class="absolute left-3 flex flex-col items-start gap-1.5"
    style="top: {overlayTop}px"
  >
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

    <!--
      Les réglages restent dépliés à l'ouverture : les replier par défaut
      reviendrait à cacher qu'ils existent. Le pli sert à récupérer la surface
      du graphe une fois le réglage fait, pas à protéger l'utilisateur de ses
      propres options.
    -->
    <button
      type="button"
      onclick={() => (controlsOpen = !controlsOpen)}
      class="flex items-center gap-1.5 rounded-md bg-white/95 border border-slate-200 shadow-sm px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
      aria-expanded={controlsOpen}
      aria-controls="graph-display-controls"
      title={controlsOpen ? 'Replier les options d’affichage' : 'Déplier les options d’affichage'}
    >
      <svg
        viewBox="0 0 24 24"
        class="w-3.5 h-3.5 shrink-0 text-slate-400"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round" />
        <circle cx="9" cy="7" r="2" fill="white" />
        <circle cx="15" cy="12" r="2" fill="white" />
        <circle cx="8" cy="17" r="2" fill="white" />
      </svg>
      <span>Affichage</span>
      <svg
        viewBox="0 0 24 24"
        class="w-3 h-3 shrink-0 text-slate-400 transition-transform {controlsOpen
          ? 'rotate-180'
          : ''}"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        aria-hidden="true"
      >
        <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>

    {#if controlsOpen}
      <div id="graph-display-controls" class="flex flex-col items-start gap-1.5">
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

        <div
          class="flex items-center rounded-md bg-white/95 border border-slate-200 shadow-sm overflow-hidden text-xs"
          role="group"
          aria-label="Disposition du graphe"
        >
          {#each layoutModeOptions as opt, i (opt.value)}
            <button
              type="button"
              onclick={() => setLayoutMode(opt.value)}
              class="px-2.5 py-1.5 transition-colors {i > 0
                ? 'border-l border-slate-200'
                : ''} {layoutMode === opt.value
                ? 'bg-slate-800 text-white font-medium'
                : 'text-slate-600 hover:bg-slate-50'}"
              aria-pressed={layoutMode === opt.value}
              title={opt.help}
            >
              {opt.label}
            </button>
          {/each}
        </div>

        {#if neighborCards.size > 0}
          <div
            class="flex items-center rounded-md bg-white/95 border border-slate-200 shadow-sm overflow-hidden text-xs"
            role="group"
            aria-label="Sens de citation affiché"
          >
            {#each [{ v: 'sortant', l: 'Ce que cite cette fiche' }, { v: 'entrant', l: 'Ce qui cite cette fiche' }, { v: 'deux', l: 'Les deux' }] as opt, i (opt.v)}
              <button
                type="button"
                class="px-2.5 py-1.5 transition-colors {i > 0
                  ? 'border-l border-slate-200'
                  : ''} {direction === opt.v
                  ? 'bg-slate-800 text-white font-medium'
                  : 'text-slate-600 hover:bg-slate-50'}"
                aria-pressed={direction === opt.v}
                onclick={() => (direction = opt.v as GraphDirection)}
              >
                {opt.l}
              </button>
            {/each}
          </div>
        {/if}

        <!--
      Nombre saisi librement plutôt que choisi dans une liste : la limite du
      lisible dépend de l'écran, de la fiche et de ce qu'on y cherche, et des
      paliers imposeraient des sauts que personne n'a demandés. Le curseur sert
      au réglage à vue, le champ au chiffre exact. Aucun plafond dur : une
      fiche de 800 références peut être demandée entière, on prévient seulement
      que ce sera dense. Les sources clés passent devant quel que soit le
      nombre retenu.

      Replié par défaut, à la différence des autres réglages : c'est le seul
      qui déploie une rangée entière de commandes, et il ne sert qu'une fois.
      Le chiffre reste inscrit sur le bouton, donc l'état courant se lit sans
      déplier — et le bouton lui-même dit que le réglage existe.
    -->
        {#if totalSources > 1}
          <div class="flex flex-col items-start gap-1.5">
            <button
              type="button"
              onclick={() => (capOpen = !capOpen)}
              class="flex items-center gap-1.5 rounded-md bg-white/95 border border-slate-200 shadow-sm px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
              aria-expanded={capOpen}
              aria-controls="graph-cap-panel"
              title="Régler le nombre de références affichées"
            >
              <span class="whitespace-nowrap">Nœuds</span>
              <span class="font-medium text-slate-800">{capValue}</span>
              {#if hiddenSourcesCount > 0}
                <span class="whitespace-nowrap text-slate-400">/ {scopedTotal}</span>
              {/if}
              {#if capValue > GRAPH_CAP_COMFORT}
                <span
                  class="text-amber-600"
                  title="Le graphe reste utilisable, mais il faudra zoomer pour lire les étiquettes."
                >
                  · dense
                </span>
              {/if}
              <svg
                viewBox="0 0 24 24"
                class="w-3 h-3 shrink-0 text-slate-400 transition-transform {capOpen
                  ? 'rotate-180'
                  : ''}"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
                aria-hidden="true"
              >
                <path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>

            {#if capOpen}
              <div
                id="graph-cap-panel"
                class="flex items-center gap-2 rounded-md bg-white/95 border border-slate-200 shadow-sm px-2.5 py-1.5 text-xs text-slate-600"
              >
                <input
                  id="graph-cap-range"
                  type="range"
                  min="1"
                  max={scopedTotal}
                  value={capValue}
                  oninput={(e) => setSourceCap(Number(e.currentTarget.value))}
                  class="w-24 accent-slate-700"
                  aria-label="Nombre maximum de références affichées"
                />
                <input
                  id="graph-cap"
                  type="number"
                  min="1"
                  max={scopedTotal}
                  value={capValue}
                  onchange={(e) => setSourceCap(Number(e.currentTarget.value))}
                  class="w-14 rounded border border-slate-200 px-1 py-0.5 text-center font-medium text-slate-800 focus:outline-none focus:ring-1 focus:ring-slate-400"
                  aria-label="Nombre exact de références affichées"
                  title="Nombre maximum de références affichées, les sources clés d'abord"
                />
                <button
                  type="button"
                  onclick={() => setSourceCap(scopedTotal)}
                  disabled={capValue >= scopedTotal}
                  class="whitespace-nowrap text-slate-500 hover:text-slate-800 disabled:text-slate-300 disabled:cursor-default transition-colors"
                >
                  Toutes ({scopedTotal})
                </button>
                {#if hiddenSourcesCount > 0}
                  <span class="whitespace-nowrap text-slate-400"
                    >· {hiddenSourcesCount} en réserve</span
                  >
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        <!--
      Filtre « clés » : proposé seulement si la fiche porte cette marque.
      Un bouton qui ne peut rien filtrer laisserait croire qu'aucune source
      n'est importante, alors qu'il dit seulement que rien n'a été marqué.
    -->
        {#if hasKeySources}
          <button
            type="button"
            onclick={toggleKeyOnly}
            class="flex items-center gap-1.5 rounded-md border shadow-sm px-2.5 py-1.5 text-xs transition-colors {keyOnly
              ? 'bg-slate-800 border-slate-800 text-white font-medium'
              : 'bg-white/95 border-slate-200 text-slate-600 hover:bg-slate-50'}"
            aria-pressed={keyOnly}
            title="N'afficher que les sources marquées comme clés par l'auteur·ice de la fiche"
          >
            <svg
              viewBox="0 0 24 24"
              class="w-3.5 h-3.5 shrink-0"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                d="M12 2.5l2.9 5.9 6.5.95-4.7 4.58 1.11 6.47L12 17.4l-5.81 3.06 1.11-6.47-4.7-4.58 6.5-.95z"
              />
            </svg>
            Sources clés
          </button>
        {/if}

        <!--
      Une liste de quinze auteurs recouvre les nœuds voisins. Le premier nom
      seul est le réglage par défaut ; aucun des deux boutons enfoncé rend la
      liste entière, la seule option qui ne perd rien.
    -->
        <div
          class="flex items-center rounded-md bg-white/95 border border-slate-200 shadow-sm overflow-hidden text-xs"
          role="group"
          aria-label="Noms d'auteurs affichés"
        >
          <span class="px-2.5 py-1.5 text-slate-500">Auteurs</span>
          <button
            type="button"
            onclick={() => (showFirstAuthor = !showFirstAuthor)}
            class="px-2.5 py-1.5 border-l border-slate-200 transition-colors {showFirstAuthor
              ? 'bg-slate-800 text-white font-medium'
              : 'text-slate-600 hover:bg-slate-50'}"
            aria-pressed={showFirstAuthor}
            title="N'afficher que le premier nom d'auteur"
          >
            Premier
          </button>
          <button
            type="button"
            onclick={() => (showLastAuthor = !showLastAuthor)}
            class="px-2.5 py-1.5 border-l border-slate-200 transition-colors {showLastAuthor
              ? 'bg-slate-800 text-white font-medium'
              : 'text-slate-600 hover:bg-slate-50'}"
            aria-pressed={showLastAuthor}
            title="N'afficher que le dernier nom d'auteur"
          >
            Dernier
          </button>
        </div>
      </div>
    {/if}
  </div>

  <div
    bind:this={controlsEl}
    class="absolute right-3 flex flex-col gap-1.5"
    style="top: {overlayTop}px"
  >
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
    {#if stanceLegend.length > 0}
      <span class="w-px h-3 bg-slate-200" aria-hidden="true"></span>
      {#each stanceLegend as s (s.key)}
        <span class="inline-flex items-center gap-1.5 text-slate-700" title={s.help}>
          <span class="inline-block w-3.5 h-0.5 rounded-full" style:background-color={s.stroke}
          ></span>
          {s.label}
        </span>
      {/each}
    {/if}
    {#if hiddenSourcesCount > 0}
      <span class="w-px h-3 bg-slate-200" aria-hidden="true"></span>
      <span class="text-slate-500">
        {visibleSources.length} sur {totalSources} références affichées
      </span>
    {/if}
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
      {:else if legendOpen}
        <div
          class="flex items-start gap-2 rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm"
        >
          <p class="flex-1">{legendLabel(neighborCards.size)}</p>
          <button
            type="button"
            class="shrink-0 rounded px-1 text-indigo-700 hover:bg-indigo-100 hover:text-indigo-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
            aria-label="Masquer l'aide du graphe"
            onclick={() => (legendOpen = false)}
          >
            ✕
          </button>
        </div>
      {:else}
        <button
          type="button"
          class="rounded-md border border-indigo-200 bg-indigo-50/95 px-2.5 py-1.5 text-indigo-900 backdrop-blur-sm hover:bg-indigo-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500"
          onclick={() => (legendOpen = true)}
        >
          ? Aide du graphe
        </button>
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
    pinned={selectedCard ? pinnedCardIds.includes(selectedCard.id) : false}
    onTogglePin={togglePin}
  />
</div>
