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

  import type { CardDetail, Source } from '$lib/api';
  import { SOURCE_COLORS } from '$lib/utils/source-colors';
  import SourceDetailPanel from './SourceDetailPanel.svelte';

  interface Props {
    card: CardDetail;
    onSelect?: (source: Source | null) => void;
  }

  let { card, onSelect }: Props = $props();

  type NodeKind = 'card' | 'source' | 'junction';

  interface GraphNode {
    id: string;
    kind: NodeKind;
    label: string;
    source?: Source;
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
    kind: 'card' | 'parent' | 'sibling';
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
  let isFullscreen = $state(false);
  let selectedSource = $state<Source | null>(null);
  let panelAnchor = $state<{ x: number; y: number } | null>(null);

  const cardId = $derived(`card:${card.id}`);

  function truncate(text: string, max: number): string {
    return text.length > max ? text.slice(0, max) + '…' : text;
  }

  function authorLabel(s: Source): string {
    if (s.authors && s.authors.trim().length > 0) return truncate(s.authors, 22);
    return truncate(s.title ?? s.url, 22);
  }

  let junctionCounter = 0;
  let forks: ForkMeta[] = [];

  function buildGraph(): { nodes: GraphNode[]; links: GraphLink[] } {
    const nodes: GraphNode[] = [
      {
        id: cardId,
        kind: 'card',
        label: card.title,
        radius: 28,
        fill: '#1e293b',
        stroke: '#0f172a',
        tier: 'card',
      },
    ];
    const links: GraphLink[] = [];
    forks = [];

    const byAuthorAndParent = new Map<string, typeof card.sources>();

    for (const s of card.sources) {
      const colors = SOURCE_COLORS[s.source_type];
      const isSecondary = s.parent_source_id !== null;
      let radius = s.authority_level === 'high' ? 17 : s.authority_level === 'medium' ? 13 : 10;
      if (s.is_pivot) radius += 3;
      if (isSecondary) radius = Math.round(radius * 0.75);

      nodes.push({
        id: s.id,
        kind: 'source',
        label: s.title ?? s.url,
        source: s,
        radius,
        fill: colors.fill,
        stroke: colors.stroke,
        tier: isSecondary ? 'second' : 'first',
      });

      if (isSecondary && s.parent_source_id) {
        links.push({ source: s.id, target: s.parent_source_id, kind: 'parent' });
      } else {
        links.push({ source: cardId, target: s.id, kind: 'card' });
      }

      if (s.authors && s.authors.trim().length > 0) {
        const pid = isSecondary && s.parent_source_id ? s.parent_source_id : cardId;
        const key = `${s.authors.trim()}||${pid}`;
        if (!byAuthorAndParent.has(key)) byAuthorAndParent.set(key, []);
        byAuthorAndParent.get(key)!.push(s);
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
        radius: 0,
        fill: 'transparent',
        stroke: 'transparent',
        tier: 'junction',
      });
      const linkKind = pidStr === cardId ? 'card' : 'parent';
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
    if (s && d) setAnchorFromNode(d);
    else panelAnchor = null;
    onSelect?.(s);
  }

  function mountGraph() {
    if (!svgEl) return;
    const { nodes, links } = buildGraph();

    const cardNode = nodes[0];
    cardNode.fx = width / 2;
    cardNode.fy = height / 2;

    const svg = select(svgEl);
    svg.selectAll('*').remove();
    svg.attr('viewBox', `0 0 ${width} ${height}`);

    const root = svg.append('g').attr('class', 'graph-root');

    root
      .append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('class', 'link')
      .attr('stroke', '#94a3b8')
      .attr('stroke-opacity', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
        return d.kind === 'parent' ? 0.5 : 0.7;
      })
      .attr('stroke-width', (d) => {
        if ((d as any).forkHide) return 0;
        if (d.kind === 'sibling') return 0;
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
      .style('opacity', 0)
      .on('click', (_event, d) => {
        if (d.kind === 'source' && d.source) selectSource(d.source, d);
        else if (d.kind === 'card') selectSource(null);
        // junction: no-op
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
        if (d.kind !== 'card') {
          d.fx = null;
          d.fy = null;
        }
      });
    nodeG.call(dragHandler);

    nodeG
      .append('circle')
      .attr('r', (d) => d.radius)
      .attr('fill', (d) => d.fill)
      .attr('stroke', (d) => d.stroke)
      .attr('stroke-width', (d) => (d.kind === 'card' ? 3 : 2));

    // Creator name above card node (always visible at zoom >= 0.7)
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
      .text(card.creator.display_name ?? card.creator.slug);

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
      .text(truncate(card.title, 35));

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
      .attr('font-size', 11)
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
      .attr('font-size', 10)
      .attr('fill', '#475569')
      .style('pointer-events', 'none')
      .text((d) => (d.source ? truncate(d.source.title ?? '', 40) : ''));

    nodeG
      .append('title')
      .text((d) => (d.kind === 'card' ? card.title : (d.source?.title ?? d.source?.url ?? '')));

    nodeG
      .transition()
      .delay((_d, i) => 50 * i)
      .duration(300)
      .style('opacity', 1);

    simulation = forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        forceLink<GraphNode, GraphLink>(links)
          .id((d) => d.id)
          .distance((l) => {
            const src = typeof l.source === 'string' ? l.source : l.source.id;
            const tgt = typeof l.target === 'string' ? l.target : l.target.id;
            if (src.startsWith('junction:') || tgt.startsWith('junction:')) return 5;
            if (l.kind === 'parent') return 75;
            if (l.kind === 'sibling') return 55;
            return 160;
          })
          .strength((l) => {
            const src = typeof l.source === 'string' ? l.source : l.source.id;
            const tgt = typeof l.target === 'string' ? l.target : l.target.id;
            if (src.startsWith('junction:') || tgt.startsWith('junction:')) return 0.05;
            if (l.kind === 'sibling') return 2.0;
            return 0.55;
          })
      )
      .force('charge', forceManyBody().strength(-280))
      .force('center', forceCenter(width / 2, height / 2).strength(0.05))
      .force(
        'collide',
        forceCollide<GraphNode>().radius((d) => d.radius + 6)
      )
      .on('tick', () => {
        if (svgEl) ticked(svgEl, nodes, links);
      });

    zoomBehavior = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        root.attr('transform', event.transform.toString());
        zoomLevel = event.transform.k;
      });
    svg.call(zoomBehavior);
  }

  function resetView() {
    if (!svgEl || !zoomBehavior) return;
    select(svgEl).transition().duration(400).call(zoomBehavior.transform, zoomIdentity);
    simulation?.alpha(0.4).restart();
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

    resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const nextW = Math.max(entry.contentRect.width, 320);
        const nextH = Math.max(entry.contentRect.height, 360);
        if (Math.abs(nextW - width) < 4 && Math.abs(nextH - height) < 4) continue;
        width = nextW;
        height = nextH;
        if (simulation) {
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
  });

  onDestroy(() => {
    simulation?.stop();
    resizeObserver?.disconnect();
    if (typeof document !== 'undefined') {
      document.removeEventListener('fullscreenchange', onFullscreenChange);
    }
  });

  $effect(() => {
    if (!svgEl) return;
    const svg = select(svgEl);
    svg.selectAll<SVGGElement, GraphNode>('.node').style('opacity', (d) => {
      if (hoveredId === null) return 1;
      return d.id === hoveredId ? 1 : 0.35;
    });
    svg.selectAll<SVGLineElement, GraphLink>('.link').style('opacity', (d) => {
      if (hoveredId === null) return 1;
      const src = typeof d.source === 'string' ? d.source : d.source.id;
      const tgt = typeof d.target === 'string' ? d.target : d.target.id;
      return src === hoveredId || tgt === hoveredId ? 1 : 0.2;
    });
  });

  // Zoom thresholds for labels
  $effect(() => {
    if (!svgEl) return;
    const svg = select(svgEl);
    const showAuthor = zoomLevel >= 0.7;
    const showTitle = zoomLevel >= 1.5;
    svg
      .selectAll<SVGTextElement, GraphNode>('text.author-label, text.card-creator')
      .style('display', showAuthor ? '' : 'none');
    svg
      .selectAll<SVGTextElement, GraphNode>('text.title-label, text.card-title-label')
      .style('display', showTitle ? '' : 'none');
  });
</script>

<div bind:this={container} class="relative w-full h-full bg-white">
  <svg
    bind:this={svgEl}
    class="w-full h-full block"
    role="img"
    aria-label="Graphe interactif des sources"
  ></svg>

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
    {#each Object.entries(SOURCE_COLORS) as [_key, c] (c.label)}
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

  <SourceDetailPanel
    source={selectedSource}
    {card}
    anchor={panelAnchor}
    containerWidth={width}
    containerHeight={height}
    onClose={() => selectSource(null)}
    onSelect={(s) => selectSource(s)}
  />
</div>
