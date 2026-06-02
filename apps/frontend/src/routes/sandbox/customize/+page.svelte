<script lang="ts">
  // ====================================================================
  // Sandbox personnalisable du logo Philum
  // Chaque nœud porte ses propres style (taille, fill, rim, rimWidth).
  // ====================================================================

  type Node = {
    angle: number;
    distance: number;
    size: number;
    fill: string;
    rim: string;
    rimWidth: number;
  };

  type Config = {
    bgColor: string;

    pulsarX: number;
    pulsarY: number;
    pulsarSize: number;
    pulsarFill: string;
    pulsarRim: string;
    pulsarRimWidth: number;
    pulsarHaloEnabled: boolean;
    pulsarHaloColor: string;
    pulsarHaloSize: number;
    pulsarHaloOpacity: number;
    pulsarGradient: boolean;
    pulsarGradientHi: string;
    pulsarGradientMid: string;
    pulsarGradientLo: string;

    normals: Node[];

    yforkEnabled: boolean;
    yforkAngle: number;
    yforkDistance: number;
    twinA: Node;
    twinB: Node;

    parentEnabled: boolean;
    parent: Node;
    luneEnabled: boolean;
    lune: Node;

    lineStroke: string;
    lineWidth: number;
    lineGradient: boolean;
    lineGradientEnd: string;
    lineDashed: boolean;
    lineDashArray: string;

    fondEnabled: boolean;
    fondColor: string;
    fondWidth: number;

    wordmarkEnabled: boolean;
    wordmarkText: string;
    wordmarkX: number;
    wordmarkY: number;
    wordmarkSize: number;
    wordmarkColor: string;
    wordmarkFont: 'serif' | 'sans';
    wordmarkWeight: number;
    wordmarkLetterSpacing: number;
  };

  // Helpers pour styliser en bulk
  function styleAll(c: Config, fn: (n: Node) => void) {
    c.normals.forEach(fn);
    fn(c.twinA);
    fn(c.twinB);
    fn(c.parent);
    fn(c.lune);
  }
  function setNormalStyle(c: Config, fill: string, rim: string) {
    c.normals.forEach((n) => {
      n.fill = fill;
      n.rim = rim;
    });
  }
  function setTwinStyle(c: Config, fill: string, rim: string) {
    c.twinA.fill = fill;
    c.twinA.rim = rim;
    c.twinB.fill = fill;
    c.twinB.rim = rim;
  }

  const PALETTES: { name: string; apply: (c: Config) => void }[] = [
    {
      name: 'Z13 auteur-kind (défaut)',
      apply: (c) => {
        c.pulsarFill = '#1F2937';
        c.pulsarRim = '#000000';
        setNormalStyle(c, '#FAC775', '#EF9F27');
        setTwinStyle(c, '#C0DD97', '#639922');
        c.parent.fill = '#B5D4F4';
        c.parent.rim = '#378ADD';
        c.lune.fill = '#CECBF6';
        c.lune.rim = '#7F77DD';
        c.lineStroke = '#475569';
      },
    },
    {
      name: 'Z13 + 3D pulsar slate',
      apply: (c) => {
        c.pulsarFill = '#1F2937';
        c.pulsarRim = '#000000';
        c.pulsarGradient = true;
        c.pulsarGradientHi = '#FFFFFF';
        c.pulsarGradientMid = '#475569';
        c.pulsarGradientLo = '#0F172A';
        setNormalStyle(c, '#FAC775', '#EF9F27');
        setTwinStyle(c, '#C0DD97', '#639922');
        c.parent.fill = '#B5D4F4';
        c.parent.rim = '#378ADD';
        c.lune.fill = '#CECBF6';
        c.lune.rim = '#7F77DD';
        c.lineStroke = '#475569';
      },
    },
    {
      name: 'Z12 hero pastel',
      apply: (c) => {
        c.pulsarFill = '#4A6CF7';
        c.pulsarRim = '#1E40AF';
        setNormalStyle(c, '#A6E8DA', '#5DBDA3');
        setTwinStyle(c, '#FBA5A5', '#DC8585');
        c.parent.fill = '#A8E4C5';
        c.parent.rim = '#5BB58E';
        c.lune.fill = '#FCE3A2';
        c.lune.rim = '#D4B872';
        c.lineStroke = '#94A3B8';
      },
    },
    {
      name: 'Mono slate',
      apply: (c) => {
        const v = '#1F2937';
        c.pulsarFill = v;
        c.pulsarRim = v;
        styleAll(c, (n) => {
          n.fill = v;
          n.rim = v;
        });
        c.lineStroke = v;
      },
    },
    {
      name: 'Mono hero blue',
      apply: (c) => {
        const v = '#4A6CF7';
        c.pulsarFill = v;
        c.pulsarRim = v;
        styleAll(c, (n) => {
          n.fill = v;
          n.rim = v;
        });
        c.lineStroke = v;
      },
    },
    {
      name: 'Mono emerald',
      apply: (c) => {
        const v = '#10B981';
        c.pulsarFill = v;
        c.pulsarRim = v;
        styleAll(c, (n) => {
          n.fill = v;
          n.rim = v;
        });
        c.lineStroke = v;
      },
    },
    {
      name: 'Dark theme',
      apply: (c) => {
        const w = '#F8FAFC';
        c.bgColor = '#0F172A';
        c.pulsarFill = w;
        c.pulsarRim = w;
        styleAll(c, (n) => {
          n.fill = w;
          n.rim = w;
        });
        c.lineStroke = w;
        c.fondColor = '#0F172A';
        c.wordmarkColor = w;
      },
    },
    {
      name: 'Noir & blanc',
      apply: (c) => {
        const k = '#000000';
        c.bgColor = '#FFFFFF';
        c.pulsarFill = k;
        c.pulsarRim = k;
        styleAll(c, (n) => {
          n.fill = k;
          n.rim = k;
        });
        c.lineStroke = k;
        c.fondColor = '#FFFFFF';
        c.wordmarkColor = k;
        c.pulsarGradient = false;
      },
    },
  ];

  function defaultConfig(): Config {
    return {
      bgColor: '#FFFFFF',
      pulsarX: 12,
      pulsarY: 12,
      pulsarSize: 2.5,
      pulsarFill: '#1F2937',
      pulsarRim: '#000000',
      pulsarRimWidth: 0.4,
      pulsarHaloEnabled: false,
      pulsarHaloColor: '#FFFFFF',
      pulsarHaloSize: 2.2,
      pulsarHaloOpacity: 0.28,
      pulsarGradient: false,
      pulsarGradientHi: '#FFFFFF',
      pulsarGradientMid: '#475569',
      pulsarGradientLo: '#0F172A',
      normals: [
        { angle: -32, distance: 9.4, size: 1.5, fill: '#FAC775', rim: '#EF9F27', rimWidth: 0.4 },
        { angle: 157, distance: 7.6, size: 1.5, fill: '#FAC775', rim: '#EF9F27', rimWidth: 0.4 },
      ],
      yforkEnabled: true,
      yforkAngle: -126,
      yforkDistance: 8.6,
      twinA: {
        angle: -148,
        distance: 5.0,
        size: 1.5,
        fill: '#C0DD97',
        rim: '#639922',
        rimWidth: 0.4,
      },
      twinB: {
        angle: -104,
        distance: 5.0,
        size: 1.5,
        fill: '#C0DD97',
        rim: '#639922',
        rimWidth: 0.4,
      },
      parentEnabled: true,
      parent: {
        angle: 50,
        distance: 7.8,
        size: 1.95,
        fill: '#B5D4F4',
        rim: '#378ADD',
        rimWidth: 0.45,
      },
      luneEnabled: true,
      lune: {
        angle: 50,
        distance: 4.5,
        size: 0.95,
        fill: '#CECBF6',
        rim: '#7F77DD',
        rimWidth: 0.35,
      },
      lineStroke: '#475569',
      lineWidth: 0.5,
      lineGradient: false,
      lineGradientEnd: '#94A3B8',
      lineDashed: false,
      lineDashArray: '0.8 0.6',
      fondEnabled: true,
      fondColor: '#FFFFFF',
      fondWidth: 1.4,
      wordmarkEnabled: false,
      wordmarkText: 'Philum',
      wordmarkX: 2.0,
      wordmarkY: 12,
      wordmarkSize: 9,
      wordmarkColor: '#1F2937',
      wordmarkFont: 'serif',
      wordmarkWeight: 500,
      wordmarkLetterSpacing: 0,
    };
  }

  function darkPreset(): Config {
    const c = defaultConfig();
    PALETTES[6].apply(c);
    return c;
  }
  function wordmarkPreset(): Config {
    const c = defaultConfig();
    PALETTES[1].apply(c);
    c.wordmarkEnabled = true;
    return c;
  }
  function bwPreset(): Config {
    const c = defaultConfig();
    PALETTES[7].apply(c);
    return c;
  }

  const SANDBOX_LABELS = [
    'Référence (clair, couleur)',
    'Dark theme',
    'Logo + nom (wordmark)',
    'Noir & blanc',
  ];

  let configs = $state<Config[]>([defaultConfig(), darkPreset(), wordmarkPreset(), bwPreset()]);
  let active = $state(0);
  let copyFromIdx = $state(0);
  let zoom = $state(1);

  let c = $derived(configs[active]);

  function applyPalette(p: { apply: (c: Config) => void }) {
    p.apply(configs[active]);
    configs = configs;
  }
  function copyFrom(srcIdx: number) {
    if (srcIdx === active) return;
    configs[active] = structuredClone($state.snapshot(configs[srcIdx])) as Config;
    configs = configs;
  }
  function resetActive() {
    const presets = [defaultConfig, darkPreset, wordmarkPreset, bwPreset];
    configs[active] = presets[active]();
    configs = configs;
  }

  function addNormal() {
    const cfg = configs[active];
    // hérite du style du dernier normal (s'il existe)
    const last = cfg.normals[cfg.normals.length - 1];
    cfg.normals.push({
      angle: last ? last.angle + 60 : 0,
      distance: last ? last.distance : 9,
      size: last ? last.size : 1.5,
      fill: last ? last.fill : '#FAC775',
      rim: last ? last.rim : '#EF9F27',
      rimWidth: last ? last.rimWidth : 0.4,
    });
    configs = configs;
  }
  function removeNormal(i: number) {
    configs[active].normals.splice(i, 1);
    configs = configs;
  }
  function applyStyleToAllNormals(from: Node) {
    configs[active].normals.forEach((n) => {
      n.size = from.size;
      n.fill = from.fill;
      n.rim = from.rim;
      n.rimWidth = from.rimWidth;
    });
    configs = configs;
  }

  function polar(cx: number, cy: number, deg: number, dist: number) {
    const r = (deg * Math.PI) / 180;
    return { x: cx + Math.cos(r) * dist, y: cy + Math.sin(r) * dist };
  }

  type Pt = { x: number; y: number };
  type Geom = {
    pulsar: Pt;
    normals: Pt[];
    forkM: Pt | null;
    twins: [Pt, Pt] | null;
    parent: Pt | null;
    lune: Pt | null;
  };

  function geomOf(c: Config): Geom {
    const pulsar: Pt = { x: c.pulsarX, y: c.pulsarY };
    const normals = c.normals.map((n) => polar(pulsar.x, pulsar.y, n.angle, n.distance));
    let forkM: Pt | null = null;
    let twins: [Pt, Pt] | null = null;
    if (c.yforkEnabled) {
      forkM = polar(pulsar.x, pulsar.y, c.yforkAngle, c.yforkDistance);
      twins = [
        polar(forkM.x, forkM.y, c.twinA.angle, c.twinA.distance),
        polar(forkM.x, forkM.y, c.twinB.angle, c.twinB.distance),
      ];
    }
    let parent: Pt | null = null;
    let lune: Pt | null = null;
    if (c.parentEnabled) {
      parent = polar(pulsar.x, pulsar.y, c.parent.angle, c.parent.distance);
      if (c.luneEnabled) lune = polar(parent.x, parent.y, c.lune.angle, c.lune.distance);
    }
    return { pulsar, normals, forkM, twins, parent, lune };
  }

  let g = $derived(geomOf(configs[active]));
  let vbW = $derived(
    configs[active].wordmarkEnabled
      ? 24 +
          configs[active].wordmarkX +
          configs[active].wordmarkText.length * configs[active].wordmarkSize * 0.55
      : 24
  );

  function exportSVG(idx: number) {
    const el = document.getElementById(`preview-svg-${idx}`);
    if (!el) return;
    const xml = new XMLSerializer().serializeToString(el);
    const blob = new Blob([xml], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `philum-logo-${SANDBOX_LABELS[idx].replace(/[^a-z0-9]/gi, '-').toLowerCase()}.svg`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // Drag souris
  type DragKind = 'pulsar' | 'normal' | 'fork' | 'twinA' | 'twinB' | 'parent' | 'lune';
  let dragging = $state<{ kind: DragKind; idx?: number } | null>(null);
  let svgEl: SVGSVGElement | null = $state(null);

  function svgPoint(evt: MouseEvent): { x: number; y: number } | null {
    if (!svgEl) return null;
    const pt = svgEl.createSVGPoint();
    pt.x = evt.clientX;
    pt.y = evt.clientY;
    const ctm = svgEl.getScreenCTM();
    if (!ctm) return null;
    const p = pt.matrixTransform(ctm.inverse());
    return { x: p.x, y: p.y };
  }

  function startDrag(kind: DragKind, idx?: number) {
    return (e: MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragging = { kind, idx };
      window.addEventListener('mousemove', onDragMove);
      window.addEventListener('mouseup', stopDrag);
    };
  }
  function onDragMove(e: MouseEvent) {
    if (!dragging) return;
    const p = svgPoint(e);
    if (!p) return;
    const cfg = configs[active];
    const { kind, idx } = dragging;
    if (kind === 'pulsar') {
      cfg.pulsarX = Math.max(0, Math.min(24, p.x));
      cfg.pulsarY = Math.max(0, Math.min(24, p.y));
    } else if (kind === 'normal' && idx !== undefined) {
      const dx = p.x - cfg.pulsarX,
        dy = p.y - cfg.pulsarY;
      cfg.normals[idx].angle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.normals[idx].distance = Math.sqrt(dx * dx + dy * dy);
    } else if (kind === 'fork') {
      const dx = p.x - cfg.pulsarX,
        dy = p.y - cfg.pulsarY;
      cfg.yforkAngle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.yforkDistance = Math.sqrt(dx * dx + dy * dy);
    } else if (kind === 'twinA' || kind === 'twinB') {
      const fork = polar(cfg.pulsarX, cfg.pulsarY, cfg.yforkAngle, cfg.yforkDistance);
      const dx = p.x - fork.x,
        dy = p.y - fork.y;
      const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const t = kind === 'twinA' ? cfg.twinA : cfg.twinB;
      t.angle = angle;
      t.distance = dist;
    } else if (kind === 'parent') {
      const dx = p.x - cfg.pulsarX,
        dy = p.y - cfg.pulsarY;
      cfg.parent.angle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.parent.distance = Math.sqrt(dx * dx + dy * dy);
    } else if (kind === 'lune') {
      const par = polar(cfg.pulsarX, cfg.pulsarY, cfg.parent.angle, cfg.parent.distance);
      const dx = p.x - par.x,
        dy = p.y - par.y;
      cfg.lune.angle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.lune.distance = Math.sqrt(dx * dx + dy * dy);
    }
    configs = configs;
  }
  function stopDrag() {
    dragging = null;
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', stopDrag);
  }
</script>

<svelte:head>
  <title>Sandbox customize — Philum</title>
</svelte:head>

<div class="page">
  <header class="hdr">
    <h1>Sandbox personnalisable du logo</h1>
    <p>
      Chaque nœud porte ses propres style (taille, fill, rim) modifiable individuellement. Glisse
      les nœuds dans l'aperçu, ajoute/supprime des normaux, zoome dans le canvas. Les palettes
      prédéfinies appliquent un style à tous les nœuds d'un coup.
    </p>
  </header>

  <nav class="tabs">
    {#each SANDBOX_LABELS as label, i (i)}
      <button type="button" class="tab" class:active={active === i} onclick={() => (active = i)}>
        {i + 1}. {label}
      </button>
    {/each}
  </nav>

  <div class="layout">
    <section class="preview">
      <div class="zoom-bar">
        <button type="button" onclick={() => (zoom = Math.max(0.3, zoom - 0.15))}>−</button>
        <input type="range" min="0.3" max="3" step="0.05" bind:value={zoom} />
        <button type="button" onclick={() => (zoom = Math.min(3, zoom + 0.15))}>+</button>
        <span class="zoom-val">{Math.round(zoom * 100)}%</span>
        <button type="button" class="zoom-reset" onclick={() => (zoom = 1)}>100%</button>
      </div>

      <div class="canvas" style="background: {c.bgColor}">
        <div class="zoom-wrap" style="transform: scale({zoom})">
          <svg
            bind:this={svgEl}
            id="preview-svg-{active}"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 {vbW} 24"
            width="100%"
            height="auto"
            preserveAspectRatio="xMidYMid meet"
          >
            {#if c.pulsarGradient || c.lineGradient}
              <defs>
                {#if c.pulsarGradient}
                  <radialGradient id="grad-p-{active}" cx="40%" cy="40%" r="60%">
                    <stop offset="0%" stop-color={c.pulsarGradientHi} />
                    <stop offset="55%" stop-color={c.pulsarGradientMid} />
                    <stop offset="100%" stop-color={c.pulsarGradientLo} />
                  </radialGradient>
                {/if}
                {#if c.lineGradient}
                  <linearGradient
                    id="grad-l-{active}"
                    x1="0"
                    y1="0"
                    x2="24"
                    y2="24"
                    gradientUnits="userSpaceOnUse"
                  >
                    <stop offset="0%" stop-color={c.lineStroke} />
                    <stop offset="100%" stop-color={c.lineGradientEnd} />
                  </linearGradient>
                {/if}
              </defs>
            {/if}

            <g
              fill="none"
              stroke={c.lineGradient ? `url(#grad-l-${active})` : c.lineStroke}
              stroke-width={c.lineWidth}
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-dasharray={c.lineDashed ? c.lineDashArray : undefined}
            >
              {#each g.normals as n (n.x + '-' + n.y)}
                <line x1={g.pulsar.x} y1={g.pulsar.y} x2={n.x} y2={n.y} />
              {/each}
              {#if g.forkM && g.twins}
                <line x1={g.pulsar.x} y1={g.pulsar.y} x2={g.forkM.x} y2={g.forkM.y} />
                <line x1={g.forkM.x} y1={g.forkM.y} x2={g.twins[0].x} y2={g.twins[0].y} />
                <line x1={g.forkM.x} y1={g.forkM.y} x2={g.twins[1].x} y2={g.twins[1].y} />
              {/if}
              {#if g.parent}
                <line x1={g.pulsar.x} y1={g.pulsar.y} x2={g.parent.x} y2={g.parent.y} />
                {#if g.lune}
                  <line x1={g.parent.x} y1={g.parent.y} x2={g.lune.x} y2={g.lune.y} />
                {/if}
              {/if}
            </g>

            {#if c.pulsarHaloEnabled}
              <circle
                cx={g.pulsar.x}
                cy={g.pulsar.y}
                r={c.pulsarSize * c.pulsarHaloSize}
                fill={c.pulsarHaloColor}
                fill-opacity={c.pulsarHaloOpacity * 0.5}
              />
              <circle
                cx={g.pulsar.x}
                cy={g.pulsar.y}
                r={c.pulsarSize * (c.pulsarHaloSize * 0.7)}
                fill={c.pulsarHaloColor}
                fill-opacity={c.pulsarHaloOpacity}
              />
            {/if}

            {#if c.fondEnabled}
              <circle
                cx={g.pulsar.x}
                cy={g.pulsar.y}
                r={c.pulsarSize}
                fill="none"
                stroke={c.fondColor}
                stroke-width={c.fondWidth}
              />
            {/if}
            <circle
              cx={g.pulsar.x}
              cy={g.pulsar.y}
              r={c.pulsarSize}
              fill={c.pulsarGradient ? `url(#grad-p-${active})` : c.pulsarFill}
              stroke={c.pulsarRimWidth > 0 ? c.pulsarRim : 'none'}
              stroke-width={c.pulsarRimWidth}
              class="draggable"
              onmousedown={startDrag('pulsar')}
            />

            {#each c.normals as n, i (i)}
              {@const pos = g.normals[i]}
              {#if c.fondEnabled}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={n.size}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={pos.x}
                cy={pos.y}
                r={n.size}
                fill={n.fill}
                stroke={n.rimWidth > 0 ? n.rim : 'none'}
                stroke-width={n.rimWidth}
                class="draggable"
                onmousedown={startDrag('normal', i)}
              />
            {/each}

            {#if g.forkM && g.twins}
              <circle
                cx={g.forkM.x}
                cy={g.forkM.y}
                r="0.7"
                fill="rgba(0,0,0,0.001)"
                stroke="rgba(99,102,241,0.4)"
                stroke-width="0.1"
                stroke-dasharray="0.2 0.2"
                class="draggable"
                onmousedown={startDrag('fork')}
              />
              {#each [c.twinA, c.twinB] as t, i (i)}
                {@const pos = g.twins[i]}
                {#if c.fondEnabled}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={t.size}
                    fill="none"
                    stroke={c.fondColor}
                    stroke-width={c.fondWidth}
                  />
                {/if}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={t.size}
                  fill={t.fill}
                  stroke={t.rimWidth > 0 ? t.rim : 'none'}
                  stroke-width={t.rimWidth}
                  class="draggable"
                  onmousedown={startDrag(i === 0 ? 'twinA' : 'twinB')}
                />
              {/each}
            {/if}

            {#if g.parent}
              {#if c.fondEnabled}
                <circle
                  cx={g.parent.x}
                  cy={g.parent.y}
                  r={c.parent.size}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={g.parent.x}
                cy={g.parent.y}
                r={c.parent.size}
                fill={c.parent.fill}
                stroke={c.parent.rimWidth > 0 ? c.parent.rim : 'none'}
                stroke-width={c.parent.rimWidth}
                class="draggable"
                onmousedown={startDrag('parent')}
              />
            {/if}
            {#if g.lune}
              {#if c.fondEnabled}
                <circle
                  cx={g.lune.x}
                  cy={g.lune.y}
                  r={c.lune.size}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={g.lune.x}
                cy={g.lune.y}
                r={c.lune.size}
                fill={c.lune.fill}
                stroke={c.lune.rimWidth > 0 ? c.lune.rim : 'none'}
                stroke-width={c.lune.rimWidth}
                class="draggable"
                onmousedown={startDrag('lune')}
              />
            {/if}

            {#if c.wordmarkEnabled}
              <text
                x={24 + c.wordmarkX}
                y={c.wordmarkY}
                fill={c.wordmarkColor}
                font-family={c.wordmarkFont === 'serif'
                  ? 'Georgia, serif'
                  : 'Inter, system-ui, sans-serif'}
                font-size={c.wordmarkSize}
                font-weight={c.wordmarkWeight}
                letter-spacing={c.wordmarkLetterSpacing}
                dominant-baseline="middle"
              >
                {c.wordmarkText}
              </text>
            {/if}
          </svg>
        </div>
      </div>

      <div class="preview-actions">
        <button type="button" onclick={() => exportSVG(active)}>⤓ Exporter SVG</button>
        <select bind:value={copyFromIdx}>
          {#each SANDBOX_LABELS as label, i (i)}
            <option value={i} disabled={i === active}>{label}</option>
          {/each}
        </select>
        <button type="button" onclick={() => copyFrom(copyFromIdx)}>⧉ Copier depuis</button>
        <button type="button" class="danger" onclick={resetActive}>↺ Reset</button>
      </div>

      <div class="minis">
        {#each configs as cfg, i (i)}
          {@const g2 = geomOf(cfg)}
          {@const vbW2 = cfg.wordmarkEnabled
            ? 24 + cfg.wordmarkX + cfg.wordmarkText.length * cfg.wordmarkSize * 0.55
            : 24}
          <button
            type="button"
            class="mini"
            class:active={active === i}
            onclick={() => (active = i)}
          >
            <div class="mini-canvas" style="background: {cfg.bgColor}">
              <svg
                viewBox="0 0 {vbW2} 24"
                width="100%"
                height="auto"
                preserveAspectRatio="xMidYMid meet"
              >
                <g
                  fill="none"
                  stroke={cfg.lineStroke}
                  stroke-width={cfg.lineWidth}
                  stroke-linecap="round"
                >
                  {#each g2.normals as n (n.x + '-' + n.y)}
                    <line x1={g2.pulsar.x} y1={g2.pulsar.y} x2={n.x} y2={n.y} />
                  {/each}
                  {#if g2.forkM && g2.twins}
                    <line x1={g2.pulsar.x} y1={g2.pulsar.y} x2={g2.forkM.x} y2={g2.forkM.y} />
                    <line x1={g2.forkM.x} y1={g2.forkM.y} x2={g2.twins[0].x} y2={g2.twins[0].y} />
                    <line x1={g2.forkM.x} y1={g2.forkM.y} x2={g2.twins[1].x} y2={g2.twins[1].y} />
                  {/if}
                  {#if g2.parent}
                    <line x1={g2.pulsar.x} y1={g2.pulsar.y} x2={g2.parent.x} y2={g2.parent.y} />
                    {#if g2.lune}
                      <line x1={g2.parent.x} y1={g2.parent.y} x2={g2.lune.x} y2={g2.lune.y} />
                    {/if}
                  {/if}
                </g>
                <circle
                  cx={g2.pulsar.x}
                  cy={g2.pulsar.y}
                  r={cfg.pulsarSize}
                  fill={cfg.pulsarFill}
                />
                {#each cfg.normals as n, j (j)}
                  {@const np = g2.normals[j]}
                  <circle cx={np.x} cy={np.y} r={n.size} fill={n.fill} />
                {/each}
                {#if g2.twins}
                  <circle
                    cx={g2.twins[0].x}
                    cy={g2.twins[0].y}
                    r={cfg.twinA.size}
                    fill={cfg.twinA.fill}
                  />
                  <circle
                    cx={g2.twins[1].x}
                    cy={g2.twins[1].y}
                    r={cfg.twinB.size}
                    fill={cfg.twinB.fill}
                  />
                {/if}
                {#if g2.parent}
                  <circle
                    cx={g2.parent.x}
                    cy={g2.parent.y}
                    r={cfg.parent.size}
                    fill={cfg.parent.fill}
                  />
                {/if}
                {#if g2.lune}
                  <circle cx={g2.lune.x} cy={g2.lune.y} r={cfg.lune.size} fill={cfg.lune.fill} />
                {/if}
                {#if cfg.wordmarkEnabled}
                  <text
                    x={24 + cfg.wordmarkX}
                    y={cfg.wordmarkY}
                    fill={cfg.wordmarkColor}
                    font-family={cfg.wordmarkFont === 'serif'
                      ? 'Georgia, serif'
                      : 'Inter, sans-serif'}
                    font-size={cfg.wordmarkSize}
                    font-weight={cfg.wordmarkWeight}
                    dominant-baseline="middle">{cfg.wordmarkText}</text
                  >
                {/if}
              </svg>
            </div>
            <span>{SANDBOX_LABELS[i]}</span>
          </button>
        {/each}
      </div>
    </section>

    <section class="controls">
      <details open>
        <summary>Palettes prédéfinies (appliquent à tous les nœuds)</summary>
        <div class="palettes">
          {#each PALETTES as p (p.name)}
            <button type="button" class="palette" onclick={() => applyPalette(p)}>{p.name}</button>
          {/each}
        </div>
      </details>

      <details open>
        <summary>Canvas + stroke fond</summary>
        <div class="row">
          <label>Fond canvas</label>
          <input type="color" bind:value={configs[active].bgColor} />
          <input type="text" bind:value={configs[active].bgColor} class="hex" />
        </div>
        <div class="row">
          <label>Stroke fond actif</label>
          <input type="checkbox" bind:checked={configs[active].fondEnabled} />
        </div>
        <div class="row">
          <label>Couleur fond stroke</label>
          <input type="color" bind:value={configs[active].fondColor} />
          <input type="text" bind:value={configs[active].fondColor} class="hex" />
        </div>
        <div class="slider">
          <label
            >Épaisseur fond <span class="val">{configs[active].fondWidth.toFixed(2)}</span></label
          >
          <input type="range" min="0" max="3" step="0.05" bind:value={configs[active].fondWidth} />
        </div>
      </details>

      <details open>
        <summary>Pulsar</summary>
        <div class="slider">
          <label>Position X <span class="val">{configs[active].pulsarX.toFixed(2)}</span></label>
          <input type="range" min="0" max="24" step="0.1" bind:value={configs[active].pulsarX} />
        </div>
        <div class="slider">
          <label>Position Y <span class="val">{configs[active].pulsarY.toFixed(2)}</span></label>
          <input type="range" min="0" max="24" step="0.1" bind:value={configs[active].pulsarY} />
        </div>
        <div class="slider">
          <label>Taille <span class="val">{configs[active].pulsarSize.toFixed(2)}</span></label>
          <input
            type="range"
            min="0.5"
            max="6"
            step="0.05"
            bind:value={configs[active].pulsarSize}
          />
        </div>
        <div class="row">
          <label>Fill</label>
          <input type="color" bind:value={configs[active].pulsarFill} />
          <input type="text" bind:value={configs[active].pulsarFill} class="hex" />
        </div>
        <div class="row">
          <label>Rim</label>
          <input type="color" bind:value={configs[active].pulsarRim} />
          <input type="text" bind:value={configs[active].pulsarRim} class="hex" />
        </div>
        <div class="slider">
          <label
            >Épaisseur rim <span class="val">{configs[active].pulsarRimWidth.toFixed(2)}</span
            ></label
          >
          <input
            type="range"
            min="0"
            max="2"
            step="0.05"
            bind:value={configs[active].pulsarRimWidth}
          />
        </div>
        <div class="row">
          <label>Gradient 3D</label>
          <input type="checkbox" bind:checked={configs[active].pulsarGradient} />
        </div>
        {#if configs[active].pulsarGradient}
          <div class="row">
            <label>Hi (lumière)</label><input
              type="color"
              bind:value={configs[active].pulsarGradientHi}
            />
          </div>
          <div class="row">
            <label>Mid</label><input type="color" bind:value={configs[active].pulsarGradientMid} />
          </div>
          <div class="row">
            <label>Lo (ombre)</label><input
              type="color"
              bind:value={configs[active].pulsarGradientLo}
            />
          </div>
        {/if}
        <div class="row">
          <label>Halo</label>
          <input type="checkbox" bind:checked={configs[active].pulsarHaloEnabled} />
        </div>
        {#if configs[active].pulsarHaloEnabled}
          <div class="row">
            <label>Halo couleur</label>
            <input type="color" bind:value={configs[active].pulsarHaloColor} />
            <input type="text" bind:value={configs[active].pulsarHaloColor} class="hex" />
          </div>
          <div class="slider">
            <label
              >Halo taille × <span class="val">{configs[active].pulsarHaloSize.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="1.1"
              max="4"
              step="0.05"
              bind:value={configs[active].pulsarHaloSize}
            />
          </div>
          <div class="slider">
            <label
              >Halo opacité <span class="val">{configs[active].pulsarHaloOpacity.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="0"
              max="1"
              step="0.02"
              bind:value={configs[active].pulsarHaloOpacity}
            />
          </div>
        {/if}
      </details>

      <details open>
        <summary>Nœuds normaux ({configs[active].normals.length})</summary>
        <div class="row">
          <button type="button" class="add-btn" onclick={addNormal}>➕ Ajouter un normal</button>
        </div>
        <p class="hint">Chaque normal a son propre style. Glisse-les dans l'aperçu.</p>
        {#each configs[active].normals as n, i (i)}
          <div class="node-row">
            <div class="node-hdr">
              <strong>Normal #{i + 1}</strong>
              <button
                type="button"
                class="bulk-btn"
                onclick={() => applyStyleToAllNormals(n)}
                title="Appliquer ce style à tous les normaux">⇶ tous</button
              >
              <button
                type="button"
                class="del-btn"
                onclick={() => removeNormal(i)}
                title="Supprimer">✕</button
              >
            </div>
            <div class="slider">
              <label>Angle <span class="val">{n.angle.toFixed(0)}°</span></label>
              <input type="range" min="-180" max="180" step="1" bind:value={n.angle} />
            </div>
            <div class="slider">
              <label>Distance <span class="val">{n.distance.toFixed(2)}</span></label>
              <input type="range" min="2" max="15" step="0.1" bind:value={n.distance} />
            </div>
            <div class="slider">
              <label>Taille <span class="val">{n.size.toFixed(2)}</span></label>
              <input type="range" min="0.3" max="4" step="0.05" bind:value={n.size} />
            </div>
            <div class="row">
              <label>Fill</label>
              <input type="color" bind:value={n.fill} />
              <input type="text" bind:value={n.fill} class="hex" />
            </div>
            <div class="row">
              <label>Rim</label>
              <input type="color" bind:value={n.rim} />
              <input type="text" bind:value={n.rim} class="hex" />
            </div>
            <div class="slider">
              <label>Épaisseur rim <span class="val">{n.rimWidth.toFixed(2)}</span></label>
              <input type="range" min="0" max="2" step="0.05" bind:value={n.rimWidth} />
            </div>
          </div>
        {/each}
      </details>

      <details>
        <summary>Y-fork (paire citée)</summary>
        <div class="row">
          <label>Activé</label>
          <input type="checkbox" bind:checked={configs[active].yforkEnabled} />
        </div>
        {#if configs[active].yforkEnabled}
          <p class="hint">Glisse la jonction (pointillé) et chaque twin dans l'aperçu.</p>
          <div class="slider">
            <label
              >Angle jonction <span class="val">{configs[active].yforkAngle.toFixed(0)}°</span
              ></label
            >
            <input
              type="range"
              min="-180"
              max="180"
              step="1"
              bind:value={configs[active].yforkAngle}
            />
          </div>
          <div class="slider">
            <label
              >Distance jonction <span class="val">{configs[active].yforkDistance.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="2"
              max="14"
              step="0.1"
              bind:value={configs[active].yforkDistance}
            />
          </div>
          {#each [{ key: 'A', t: configs[active].twinA }, { key: 'B', t: configs[active].twinB }] as tw (tw.key)}
            <div class="node-row">
              <div class="node-hdr"><strong>Twin {tw.key}</strong></div>
              <div class="slider">
                <label>Angle <span class="val">{tw.t.angle.toFixed(0)}°</span></label>
                <input type="range" min="-180" max="180" step="1" bind:value={tw.t.angle} />
              </div>
              <div class="slider">
                <label>Distance <span class="val">{tw.t.distance.toFixed(2)}</span></label>
                <input type="range" min="1" max="10" step="0.1" bind:value={tw.t.distance} />
              </div>
              <div class="slider">
                <label>Taille <span class="val">{tw.t.size.toFixed(2)}</span></label>
                <input type="range" min="0.3" max="4" step="0.05" bind:value={tw.t.size} />
              </div>
              <div class="row">
                <label>Fill</label>
                <input type="color" bind:value={tw.t.fill} />
                <input type="text" bind:value={tw.t.fill} class="hex" />
              </div>
              <div class="row">
                <label>Rim</label>
                <input type="color" bind:value={tw.t.rim} />
                <input type="text" bind:value={tw.t.rim} class="hex" />
              </div>
              <div class="slider">
                <label>Épaisseur rim <span class="val">{tw.t.rimWidth.toFixed(2)}</span></label>
                <input type="range" min="0" max="2" step="0.05" bind:value={tw.t.rimWidth} />
              </div>
            </div>
          {/each}
        {/if}
      </details>

      <details>
        <summary>Parent + Lune</summary>
        <div class="row">
          <label>Parent activé</label>
          <input type="checkbox" bind:checked={configs[active].parentEnabled} />
        </div>
        {#if configs[active].parentEnabled}
          <div class="node-row">
            <div class="node-hdr"><strong>Parent</strong></div>
            <div class="slider">
              <label
                >Angle <span class="val">{configs[active].parent.angle.toFixed(0)}°</span></label
              >
              <input
                type="range"
                min="-180"
                max="180"
                step="1"
                bind:value={configs[active].parent.angle}
              />
            </div>
            <div class="slider">
              <label
                >Distance <span class="val">{configs[active].parent.distance.toFixed(2)}</span
                ></label
              >
              <input
                type="range"
                min="2"
                max="14"
                step="0.1"
                bind:value={configs[active].parent.distance}
              />
            </div>
            <div class="slider">
              <label>Taille <span class="val">{configs[active].parent.size.toFixed(2)}</span></label
              >
              <input
                type="range"
                min="0.3"
                max="5"
                step="0.05"
                bind:value={configs[active].parent.size}
              />
            </div>
            <div class="row">
              <label>Fill</label>
              <input type="color" bind:value={configs[active].parent.fill} />
              <input type="text" bind:value={configs[active].parent.fill} class="hex" />
            </div>
            <div class="row">
              <label>Rim</label>
              <input type="color" bind:value={configs[active].parent.rim} />
              <input type="text" bind:value={configs[active].parent.rim} class="hex" />
            </div>
            <div class="slider">
              <label
                >Épaisseur rim <span class="val">{configs[active].parent.rimWidth.toFixed(2)}</span
                ></label
              >
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                bind:value={configs[active].parent.rimWidth}
              />
            </div>
          </div>
          <div class="row">
            <label>Lune activée</label>
            <input type="checkbox" bind:checked={configs[active].luneEnabled} />
          </div>
          {#if configs[active].luneEnabled}
            <div class="node-row">
              <div class="node-hdr"><strong>Lune</strong></div>
              <div class="slider">
                <label
                  >Angle (depuis parent) <span class="val"
                    >{configs[active].lune.angle.toFixed(0)}°</span
                  ></label
                >
                <input
                  type="range"
                  min="-180"
                  max="180"
                  step="1"
                  bind:value={configs[active].lune.angle}
                />
              </div>
              <div class="slider">
                <label
                  >Distance <span class="val">{configs[active].lune.distance.toFixed(2)}</span
                  ></label
                >
                <input
                  type="range"
                  min="1"
                  max="8"
                  step="0.1"
                  bind:value={configs[active].lune.distance}
                />
              </div>
              <div class="slider">
                <label>Taille <span class="val">{configs[active].lune.size.toFixed(2)}</span></label
                >
                <input
                  type="range"
                  min="0.2"
                  max="3"
                  step="0.05"
                  bind:value={configs[active].lune.size}
                />
              </div>
              <div class="row">
                <label>Fill</label>
                <input type="color" bind:value={configs[active].lune.fill} />
                <input type="text" bind:value={configs[active].lune.fill} class="hex" />
              </div>
              <div class="row">
                <label>Rim</label>
                <input type="color" bind:value={configs[active].lune.rim} />
                <input type="text" bind:value={configs[active].lune.rim} class="hex" />
              </div>
              <div class="slider">
                <label
                  >Épaisseur rim <span class="val">{configs[active].lune.rimWidth.toFixed(2)}</span
                  ></label
                >
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  bind:value={configs[active].lune.rimWidth}
                />
              </div>
            </div>
          {/if}
        {/if}
      </details>

      <details>
        <summary>Lignes</summary>
        <div class="row">
          <label>Couleur</label>
          <input type="color" bind:value={configs[active].lineStroke} />
          <input type="text" bind:value={configs[active].lineStroke} class="hex" />
        </div>
        <div class="slider">
          <label>Épaisseur <span class="val">{configs[active].lineWidth.toFixed(2)}</span></label>
          <input
            type="range"
            min="0.1"
            max="2.5"
            step="0.05"
            bind:value={configs[active].lineWidth}
          />
        </div>
        <div class="row">
          <label>Gradient</label>
          <input type="checkbox" bind:checked={configs[active].lineGradient} />
        </div>
        {#if configs[active].lineGradient}
          <div class="row">
            <label>Couleur fin gradient</label>
            <input type="color" bind:value={configs[active].lineGradientEnd} />
            <input type="text" bind:value={configs[active].lineGradientEnd} class="hex" />
          </div>
        {/if}
        <div class="row">
          <label>Pointillé</label>
          <input type="checkbox" bind:checked={configs[active].lineDashed} />
        </div>
        {#if configs[active].lineDashed}
          <div class="row">
            <label>Pattern</label>
            <input type="text" bind:value={configs[active].lineDashArray} class="hex" />
          </div>
        {/if}
      </details>

      <details>
        <summary>Wordmark (« Philum »)</summary>
        <div class="row">
          <label>Activé</label>
          <input type="checkbox" bind:checked={configs[active].wordmarkEnabled} />
        </div>
        {#if configs[active].wordmarkEnabled}
          <div class="row">
            <label>Texte</label>
            <input type="text" bind:value={configs[active].wordmarkText} class="hex" />
          </div>
          <div class="slider">
            <label>Décalage X <span class="val">{configs[active].wordmarkX.toFixed(1)}</span></label
            >
            <input
              type="range"
              min="-5"
              max="15"
              step="0.1"
              bind:value={configs[active].wordmarkX}
            />
          </div>
          <div class="slider">
            <label>Position Y <span class="val">{configs[active].wordmarkY.toFixed(1)}</span></label
            >
            <input
              type="range"
              min="0"
              max="24"
              step="0.1"
              bind:value={configs[active].wordmarkY}
            />
          </div>
          <div class="slider">
            <label>Taille <span class="val">{configs[active].wordmarkSize.toFixed(1)}</span></label>
            <input
              type="range"
              min="3"
              max="18"
              step="0.1"
              bind:value={configs[active].wordmarkSize}
            />
          </div>
          <div class="row">
            <label>Couleur</label>
            <input type="color" bind:value={configs[active].wordmarkColor} />
            <input type="text" bind:value={configs[active].wordmarkColor} class="hex" />
          </div>
          <div class="row">
            <label>Police</label>
            <select bind:value={configs[active].wordmarkFont}>
              <option value="serif">Serif (Georgia)</option>
              <option value="sans">Sans (Inter)</option>
            </select>
          </div>
          <div class="slider">
            <label>Graisse <span class="val">{configs[active].wordmarkWeight}</span></label>
            <input
              type="range"
              min="100"
              max="900"
              step="100"
              bind:value={configs[active].wordmarkWeight}
            />
          </div>
          <div class="slider">
            <label
              >Letter-spacing <span class="val"
                >{configs[active].wordmarkLetterSpacing.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="-0.5"
              max="1.5"
              step="0.05"
              bind:value={configs[active].wordmarkLetterSpacing}
            />
          </div>
        {/if}
      </details>
    </section>
  </div>
</div>

<style>
  .page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.5rem 1rem 4rem;
    font-family: Inter, system-ui, sans-serif;
    color: rgb(var(--text-primary));
  }
  .hdr h1 {
    font-size: 1.6rem;
    margin: 0 0 0.4rem;
    font-weight: 600;
  }
  .hdr p {
    font-size: 0.92rem;
    color: rgb(var(--text-secondary));
    margin: 0 0 1.2rem;
  }
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid rgb(var(--border));
    padding-bottom: 0.6rem;
  }
  .tab {
    padding: 0.5rem 0.9rem;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--bg-secondary));
    color: rgb(var(--text-secondary));
    border-radius: 8px 8px 0 0;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .tab:hover {
    background: rgb(var(--bg-tertiary));
  }
  .tab.active {
    background: rgb(var(--info));
    color: white;
    border-color: rgb(var(--info));
  }
  .layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 400px;
    gap: 1.5rem;
  }
  @media (max-width: 1024px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
  .preview {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .zoom-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.6rem;
    background: rgb(var(--bg-secondary));
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
  }
  .zoom-bar input[type='range'] {
    flex: 1;
  }
  .zoom-bar button {
    padding: 0.2rem 0.6rem;
    min-width: 32px;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--bg-primary));
    color: rgb(var(--text-primary));
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
  }
  .zoom-bar button:hover {
    background: rgb(var(--bg-tertiary));
  }
  .zoom-val {
    font-family: ui-monospace, monospace;
    font-size: 0.8rem;
    background: rgb(var(--bg-primary));
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    min-width: 50px;
    text-align: center;
    border: 1px solid rgb(var(--border));
  }
  .zoom-reset {
    font-size: 0.72rem;
  }
  .canvas {
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    padding: 2rem;
    min-height: 360px;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background-image:
      linear-gradient(
        45deg,
        rgba(0, 0, 0, 0.025) 25%,
        transparent 25%,
        transparent 75%,
        rgba(0, 0, 0, 0.025) 75%
      ),
      linear-gradient(
        45deg,
        rgba(0, 0, 0, 0.025) 25%,
        transparent 25%,
        transparent 75%,
        rgba(0, 0, 0, 0.025) 75%
      );
    background-size: 16px 16px;
    background-position:
      0 0,
      8px 8px;
  }
  .zoom-wrap {
    transform-origin: center center;
    transition: transform 0.05s linear;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .canvas svg {
    max-width: 100%;
    max-height: 320px;
    user-select: none;
  }
  .draggable {
    cursor: grab;
  }
  .draggable:active {
    cursor: grabbing;
  }
  .preview-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }
  .preview-actions button,
  .preview-actions select {
    padding: 0.45rem 0.8rem;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--bg-secondary));
    color: rgb(var(--text-primary));
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
  }
  .preview-actions button:hover {
    background: rgb(var(--bg-tertiary));
  }
  .preview-actions .danger {
    color: rgb(var(--danger));
    border-color: rgba(var(--danger), 0.4);
  }
  .minis {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.5rem;
  }
  @media (max-width: 640px) {
    .minis {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  .mini {
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    background: rgb(var(--bg-primary));
    cursor: pointer;
    padding: 0.4rem;
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    color: rgb(var(--text-secondary));
    font-size: 0.72rem;
  }
  .mini.active {
    border-color: rgb(var(--info));
    box-shadow: 0 0 0 2px rgba(var(--info), 0.2);
  }
  .mini-canvas {
    border-radius: 4px;
    aspect-ratio: 1.5 / 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0.3rem;
  }
  .controls {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    max-height: calc(100vh - 100px);
    overflow-y: auto;
    padding-right: 0.3rem;
  }
  details {
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    padding: 0.5rem 0.7rem;
    background: rgb(var(--bg-secondary));
  }
  summary {
    cursor: pointer;
    font-weight: 600;
    font-size: 0.88rem;
    padding: 0.2rem 0;
    user-select: none;
  }
  details[open] summary {
    margin-bottom: 0.5rem;
    border-bottom: 1px solid rgb(var(--border));
    padding-bottom: 0.4rem;
  }
  .row {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 0.4rem;
    align-items: center;
    margin: 0.35rem 0;
    font-size: 0.82rem;
  }
  .row label {
    color: rgb(var(--text-secondary));
  }
  .row input[type='color'] {
    width: 32px;
    height: 28px;
    padding: 0;
    border: 1px solid rgb(var(--border));
    border-radius: 4px;
    cursor: pointer;
    background: transparent;
  }
  .row input[type='checkbox'] {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }
  .row select,
  .hex {
    padding: 0.25rem 0.4rem;
    border: 1px solid rgb(var(--border));
    border-radius: 4px;
    background: rgb(var(--bg-primary));
    color: rgb(var(--text-primary));
    font-size: 0.78rem;
    font-family: ui-monospace, monospace;
    width: 88px;
  }
  .row select {
    width: auto;
    font-family: inherit;
  }
  .slider {
    margin: 0.5rem 0;
    font-size: 0.82rem;
  }
  .slider label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    color: rgb(var(--text-secondary));
    margin-bottom: 0.3rem;
  }
  .slider .val {
    font-family: ui-monospace, monospace;
    font-size: 0.78rem;
    color: rgb(var(--text-primary));
    background: rgb(var(--bg-primary));
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    border: 1px solid rgb(var(--border));
  }
  .slider input[type='range'] {
    width: 100%;
    height: 8px;
    -webkit-appearance: none;
    appearance: none;
    background: rgb(var(--bg-tertiary));
    border-radius: 4px;
    outline: none;
  }
  .slider input[type='range']::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgb(var(--info));
    cursor: pointer;
    border: 2px solid white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  }
  .slider input[type='range']::-moz-range-thumb {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: rgb(var(--info));
    cursor: pointer;
    border: 2px solid white;
  }
  .palettes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.35rem;
  }
  .palette {
    padding: 0.4rem 0.5rem;
    border: 1px solid rgb(var(--border));
    background: rgb(var(--bg-primary));
    color: rgb(var(--text-primary));
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.78rem;
    text-align: left;
    transition: all 0.1s;
  }
  .palette:hover {
    background: rgb(var(--info));
    color: white;
    border-color: rgb(var(--info));
  }
  .add-btn {
    padding: 0.4rem 0.6rem;
    border: 1px dashed rgb(var(--info));
    background: rgba(var(--info), 0.08);
    color: rgb(var(--info));
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.82rem;
    font-weight: 600;
    grid-column: 1 / -1;
  }
  .add-btn:hover {
    background: rgba(var(--info), 0.18);
  }
  .del-btn {
    padding: 0.15rem 0.45rem;
    border: 1px solid rgba(var(--danger), 0.3);
    background: transparent;
    color: rgb(var(--danger));
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
    line-height: 1;
  }
  .del-btn:hover {
    background: rgba(var(--danger), 0.1);
  }
  .bulk-btn {
    padding: 0.15rem 0.45rem;
    border: 1px solid rgba(var(--info), 0.3);
    background: transparent;
    color: rgb(var(--info));
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.72rem;
    line-height: 1;
  }
  .bulk-btn:hover {
    background: rgba(var(--info), 0.1);
  }
  .node-row {
    padding: 0.55rem;
    margin: 0.4rem 0;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    background: rgb(var(--bg-primary));
  }
  .node-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
    margin-bottom: 0.3rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px dashed rgb(var(--border));
  }
  .node-hdr strong {
    font-size: 0.8rem;
    color: rgb(var(--text-primary));
  }
  .hint {
    font-size: 0.75rem;
    color: rgb(var(--text-tertiary));
    margin: 0.3rem 0;
    font-style: italic;
  }
</style>
