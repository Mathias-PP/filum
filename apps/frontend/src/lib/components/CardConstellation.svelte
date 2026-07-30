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

  import { goto } from '$app/navigation';
  import { api } from '$lib/api';

  interface Props {
    creatorSlug: string;
    cardSlug: string;
    /** Fiche racine : mise en évidence et jamais navigable (on y est déjà). */
    rootCardId: string;
  }

  let { creatorSlug, cardSlug, rootCardId }: Props = $props();

  /**
   * Constellation : le méta-graphe fiches-seules.
   *
   * Là où le graphe des sources montre une fiche et ses références, la
   * constellation efface les sources et ne garde que les fiches Philum reliées
   * entre elles. C'est la vue de survol : elle répond à « où se situe cette
   * fiche dans le réseau ? », pas à « sur quoi s'appuie-t-elle ? ».
   */
  interface StarNode {
    id: string;
    cardId: string;
    title: string;
    slug: string;
    creatorSlug: string;
    creatorName: string;
    sourcesCount: number;
    depth: number;
    radius: number;
    isRoot: boolean;
    x?: number;
    y?: number;
    fx?: number | null;
    fy?: number | null;
  }

  interface StarLink {
    source: string | StarNode;
    target: string | StarNode;
  }

  let container: HTMLDivElement | undefined = $state();
  let svgEl: SVGSVGElement | undefined = $state();
  let width = $state(800);
  let height = $state(560);
  let simulation: Simulation<StarNode, StarLink> | undefined;
  let zoomBehavior: ZoomBehavior<SVGSVGElement, unknown> | undefined;
  let resizeObserver: ResizeObserver | undefined;
  /** Dès que l'utilisateur cadre lui-même, le recadrage automatique se retire. */
  let hasUserAdjustedView = false;
  let loading = $state(true);
  let errored = $state(false);
  let truncated = $state(false);
  let cardCount = $state(0);
  let hoveredId = $state<string | null>(null);
  let nodes: StarNode[] = [];
  let links: StarLink[] = [];

  function truncateText(text: string, max: number): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  /** Le rayon dit le poids bibliographique, pas la profondeur : une fiche très
   * sourcée est une étoile plus grosse, où qu'elle soit dans le réseau. */
  function radiusFor(sourcesCount: number, isRoot: boolean): number {
    const base = 7 + Math.sqrt(Math.max(sourcesCount, 0)) * 1.9;
    return Math.min(isRoot ? 30 : 24, isRoot ? base + 6 : base);
  }

  async function load() {
    try {
      const graph = await api.cards.getGraph(creatorSlug, cardSlug, {
        depth: 3,
        includeSources: false,
      });
      nodes = graph.nodes
        .filter((n) => n.kind === 'card')
        .map((n) => {
          const cardId = n.id.slice('card:'.length);
          const isRoot = cardId === rootCardId;
          return {
            id: n.id,
            cardId,
            title: n.title ?? 'Fiche',
            slug: n.slug ?? '',
            creatorSlug: n.creator_slug ?? '',
            creatorName: n.creator_name ?? n.creator_slug ?? '',
            sourcesCount: n.sources_count ?? 0,
            depth: n.depth,
            radius: radiusFor(n.sources_count ?? 0, isRoot),
            isRoot,
          };
        });
      const known = new Set(nodes.map((n) => n.id));
      links = graph.edges
        .filter((e) => known.has(e.source) && known.has(e.target))
        .map((e) => ({ source: e.source, target: e.target }));
      truncated = graph.truncated;
      cardCount = nodes.length;
    } catch {
      errored = true;
    } finally {
      loading = false;
    }
  }

  function ticked() {
    if (!svgEl) return;
    const svg = select(svgEl);
    svg
      .selectAll<SVGLineElement, StarLink>('.star-link')
      .attr('x1', (d) => (d.source as StarNode).x ?? 0)
      .attr('y1', (d) => (d.source as StarNode).y ?? 0)
      .attr('x2', (d) => (d.target as StarNode).x ?? 0)
      .attr('y2', (d) => (d.target as StarNode).y ?? 0);
    svg
      .selectAll<SVGGElement, StarNode>('.star')
      .attr('transform', (d) => `translate(${d.x ?? 0}, ${d.y ?? 0})`);
  }

  function fitToNodes(sim: Simulation<StarNode, StarLink> | undefined, duration = 0) {
    if (!svgEl || !zoomBehavior) return;
    // Seule la simulation qui pilote le DOM affiche peut le recadrer : un
    // recadrage venu d'un montage precedent se calculait sur d'autres noeuds
    // et laissait les etoiles hors cadre.
    if (!sim || sim !== simulation) return;
    const placed = sim.nodes();
    if (placed.length === 0) return;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const n of placed) {
      const pad = n.radius + 40;
      minX = Math.min(minX, (n.x ?? 0) - pad);
      maxX = Math.max(maxX, (n.x ?? 0) + pad);
      minY = Math.min(minY, (n.y ?? 0) - pad);
      maxY = Math.max(maxY, (n.y ?? 0) + pad);
    }
    const k = Math.min(
      2.5,
      Math.max(0.15, Math.min(width / Math.max(maxX - minX, 1), height / Math.max(maxY - minY, 1)))
    );
    const target = zoomIdentity
      .translate(width / 2 - k * ((minX + maxX) / 2), height / 2 - k * ((minY + maxY) / 2))
      .scale(k);
    const sel = select(svgEl);
    if (duration > 0) sel.transition().duration(duration).call(zoomBehavior.transform, target);
    else sel.call(zoomBehavior.transform, target);
  }

  function resetView() {
    if (!simulation) return;
    hasUserAdjustedView = false;
    // Les etoiles epinglees par un glisser doivent redevenir libres, sinon le
    // recadrage se fait sur une disposition que la simulation ne corrige plus.
    for (const n of simulation.nodes()) {
      n.fx = null;
      n.fy = null;
    }
    simulation.alpha(0.6).restart();
    fitToNodes(simulation, 400);
  }

  function mountGraph() {
    if (!svgEl || nodes.length === 0) return;
    // Une simulation laissee en vie continuerait de piloter les memes elements
    // du DOM que la nouvelle, avec ses propres noeuds.
    simulation?.stop();
    simulation = undefined;
    const svg = select(svgEl);
    // Une transition de zoom encore en vol ecraserait le cadrage du nouveau
    // graphe avec la cible calculee pour l'ancien.
    svg.interrupt();
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    // Le halo est ce qui fait « étoile » plutôt que « rond » : un dégradé
    // radial réutilisé par tous les nœuds via <use> du même gradient.
    const defs = svg.append('defs');
    const glow = defs
      .append('radialGradient')
      .attr('id', 'star-glow')
      .attr('cx', '50%')
      .attr('cy', '50%');
    glow
      .append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#a5b4fc')
      .attr('stop-opacity', 0.7);
    glow
      .append('stop')
      .attr('offset', '55%')
      .attr('stop-color', '#6366f1')
      .attr('stop-opacity', 0.18);
    glow
      .append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#6366f1')
      .attr('stop-opacity', 0);

    const root = svg.append('g').attr('class', 'constellation-root');

    root
      .append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'star-link')
      .attr('stroke', '#818cf8')
      .attr('stroke-opacity', 0.35)
      .attr('stroke-width', 1.2);

    const starG = root
      .append('g')
      .selectAll<SVGGElement, StarNode>('g')
      .data(nodes)
      .join('g')
      .attr('class', 'star')
      .style('cursor', (d) => (d.isRoot ? 'default' : 'pointer'))
      .on('mouseenter', (_e, d) => (hoveredId = d.id))
      .on('mouseleave', () => (hoveredId = null))
      .on('click', (_e, d) => {
        if (!d.isRoot && d.creatorSlug && d.slug) void goto(`/@${d.creatorSlug}/${d.slug}`);
      });

    starG.call(
      drag<SVGGElement, StarNode>()
        .on('start', (event: D3DragEvent<SVGGElement, StarNode, StarNode>, d) => {
          if (!event.active) simulation?.alphaTarget(0.2).restart();
          // Deplacer une etoile, c'est composer soi-meme la vue : sans cela le
          // recadrage automatique suivrait l'etoile et la ferait fuir sous le
          // curseur a chaque tick.
          hasUserAdjustedView = true;
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event: D3DragEvent<SVGGElement, StarNode, StarNode>, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event: D3DragEvent<SVGGElement, StarNode, StarNode>, d) => {
          if (!event.active) simulation?.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

    starG
      .append('circle')
      .attr('class', 'star-halo')
      .attr('r', (d) => d.radius * 3)
      .attr('fill', 'url(#star-glow)')
      .style('pointer-events', 'none');

    starG
      .append('circle')
      .attr('class', 'star-core')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => (d.isRoot ? '#fef3c7' : '#e0e7ff'))
      .attr('stroke', (d) => (d.isRoot ? '#f59e0b' : '#818cf8'))
      .attr('stroke-width', (d) => (d.isRoot ? 3 : 1.5));

    starG
      .append('text')
      .attr('class', 'star-creator')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => -(d.radius + 10))
      .attr('font-size', 12)
      .attr('font-weight', 600)
      .attr('fill', '#e2e8f0')
      .style('pointer-events', 'none')
      .text((d) => truncateText(d.creatorName, 24));

    starG
      .append('text')
      .attr('class', 'star-title')
      .attr('text-anchor', 'middle')
      .attr('y', (d) => d.radius + 18)
      .attr('font-size', 11)
      .attr('fill', '#94a3b8')
      .style('pointer-events', 'none')
      .text((d) => truncateText(d.title, 32));

    starG
      .append('title')
      .text(
        (d) =>
          `${d.title} — ${d.creatorName} · ${d.sourcesCount} source${d.sourcesCount > 1 ? 's' : ''}${d.isRoot ? ' (fiche affichée)' : ''}`
      );

    const sim = forceSimulation<StarNode>(nodes)
      .force(
        'link',
        forceLink<StarNode, StarLink>(links)
          .id((d) => d.id)
          .distance(170)
          .strength(0.5)
      )
      .force('charge', forceManyBody().strength(-700))
      .force('center', forceCenter(width / 2, height / 2).strength(0.08))
      .force(
        'collide',
        forceCollide<StarNode>().radius((d) => d.radius + 44)
      )
      .on('tick', () => {
        ticked();
        // Recadrer a chaque tick tant que l'utilisateur n'a pas pris la main :
        // n'attendre qu'un seuil d'alpha, un `end` ou un delai fixe revenait a
        // cadrer sur des positions que la simulation deplacait encore, et les
        // etoiles quittaient le cadre. Le cout est un recalcul de boite
        // englobante par tick, negligeable a cette echelle.
        if (!hasUserAdjustedView) fitToNodes(sim);
      });
    simulation = sim;
    // Le montage precedent a pu arreter le minuteur d3 partage : sans ce
    // redemarrage explicite, la nouvelle simulation reste figee sur les
    // positions initiales et aucun tick n'arrive jamais.
    sim.alpha(1).restart();

    zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.15, 2.5])
      .on('zoom', (event) => {
        root.attr('transform', event.transform.toString());
        if (event.sourceEvent) hasUserAdjustedView = true;
      });
    svg.call(zoomBehavior);
  }

  onMount(() => {
    if (!container) return;
    const rect = container.getBoundingClientRect();
    width = Math.max(rect.width, 320);
    height = Math.max(rect.height, 360);

    void load().then(mountGraph);

    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const nextW = Math.max(entry.contentRect.width, 320);
        const nextH = Math.max(entry.contentRect.height, 360);
        if (Math.abs(nextW - width) < 4 && Math.abs(nextH - height) < 4) continue;
        width = nextW;
        height = nextH;
        if (svgEl) select(svgEl).attr('viewBox', `0 0 ${width} ${height}`);
        simulation
          ?.force('center', forceCenter(width / 2, height / 2).strength(0.08))
          .alpha(0.3)
          .restart();
      }
    });
    resizeObserver.observe(container);
  });

  onDestroy(() => {
    simulation?.stop();
    resizeObserver?.disconnect();
  });

  // Mise en avant du voisinage direct au survol : sans cela, sur un réseau
  // dense, on ne distingue pas à quelles fiches une étoile est reliée.
  $effect(() => {
    if (!svgEl) return;
    const hovered = hoveredId;
    const svg = select(svgEl);
    const neighbors = new Set<string>();
    if (hovered) {
      neighbors.add(hovered);
      for (const l of links) {
        const s = typeof l.source === 'string' ? l.source : l.source.id;
        const t = typeof l.target === 'string' ? l.target : l.target.id;
        if (s === hovered) neighbors.add(t);
        if (t === hovered) neighbors.add(s);
      }
    }
    svg
      .selectAll<SVGGElement, StarNode>('.star')
      .style('opacity', (d) => (hovered === null || neighbors.has(d.id) ? 1 : 0.25));
    svg.selectAll<SVGLineElement, StarLink>('.star-link').attr('stroke-opacity', (d) => {
      if (hovered === null) return 0.35;
      const s = typeof d.source === 'string' ? d.source : d.source.id;
      const t = typeof d.target === 'string' ? d.target : d.target.id;
      return s === hovered || t === hovered ? 0.9 : 0.08;
    });
  });
</script>

<div bind:this={container} class="relative w-full h-full bg-slate-950">
  <!-- Une fiche seule n'est pas une constellation : l'etoile isolee parasiterait
       le message d'invite au lieu de l'illustrer. -->
  <svg
    bind:this={svgEl}
    class="w-full h-full block"
    class:invisible={loading || errored || cardCount <= 1}
    role="img"
    aria-label="Constellation des fiches reliées"
  ></svg>

  {#if loading}
    <p class="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
      Chargement de la constellation…
    </p>
  {:else if errored}
    <p class="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
      La constellation n'a pas pu être chargée.
    </p>
  {:else if cardCount <= 1}
    <div
      class="absolute inset-0 flex flex-col items-center justify-center gap-1 px-6 text-center text-sm text-slate-400"
    >
      <p class="text-slate-200">Cette fiche n'est encore reliée à aucune autre.</p>
      <p>
        Ajoutez comme source l'URL d'une fiche Philum publique : elle rejoindra la constellation.
      </p>
    </div>
  {:else}
    <div
      class="absolute bottom-3 left-3 rounded-md bg-slate-900/80 border border-slate-700 px-2.5 py-1.5 text-xs text-slate-300 backdrop-blur-sm"
    >
      {cardCount} fiches reliées · la taille dit le nombre de sources
      {#if truncated}
        <span class="block text-slate-500">Réseau partiel : trop de fiches pour tout afficher.</span
        >
      {/if}
    </div>
    <!-- Sans ce bouton, une etoile trainee hors du cadre est irrecuperable :
         le recadrage automatique s'est retire des que l'utilisateur a agi. -->
    <button
      onclick={resetView}
      class="absolute top-3 right-3 h-8 w-8 rounded-md border border-slate-700 bg-slate-900/80 text-slate-300 backdrop-blur-sm hover:bg-slate-800 flex items-center justify-center"
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
  {/if}
</div>
