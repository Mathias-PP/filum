<script lang="ts">
  // ====================================================================
  // Sandbox personnalisable du logo Philum
  // 4 sous-sandboxes : Référence (clair), Dark, Wordmark, N&B
  // Drag souris sur les nœuds, ajout/suppression de normaux, zoom canvas.
  // ====================================================================

  type Node = { angle: number; distance: number };

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

    // Liste de normaux (angle absolu depuis pulsar, distance)
    normals: Node[];
    normalSize: number;
    normalFill: string;
    normalRim: string;
    normalRimWidth: number;

    // Y-fork
    yforkEnabled: boolean;
    yforkAngle: number; // angle depuis pulsar
    yforkDistance: number;
    twinA: Node; // angle absolu depuis forkM
    twinB: Node;
    twinSize: number;
    twinFill: string;
    twinRim: string;
    twinRimWidth: number;

    // Parent + Lune
    parentEnabled: boolean;
    parentAngle: number;
    parentDistance: number;
    parentSize: number;
    parentFill: string;
    parentRim: string;
    parentRimWidth: number;
    luneEnabled: boolean;
    luneAngle: number; // angle absolu depuis parent
    luneDistance: number;
    luneSize: number;
    luneFill: string;
    luneRim: string;
    luneRimWidth: number;

    // Lignes
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

  const PALETTES: { name: string; apply: (c: Config) => void }[] = [
    {
      name: 'Z13 auteur-kind (défaut)',
      apply: (c) => {
        c.pulsarFill = '#1F2937';
        c.pulsarRim = '#000000';
        c.normalFill = '#FAC775';
        c.normalRim = '#EF9F27';
        c.twinFill = '#C0DD97';
        c.twinRim = '#639922';
        c.parentFill = '#B5D4F4';
        c.parentRim = '#378ADD';
        c.luneFill = '#CECBF6';
        c.luneRim = '#7F77DD';
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
        c.normalFill = '#FAC775';
        c.normalRim = '#EF9F27';
        c.twinFill = '#C0DD97';
        c.twinRim = '#639922';
        c.parentFill = '#B5D4F4';
        c.parentRim = '#378ADD';
        c.luneFill = '#CECBF6';
        c.luneRim = '#7F77DD';
        c.lineStroke = '#475569';
      },
    },
    {
      name: 'Z12 hero pastel',
      apply: (c) => {
        c.pulsarFill = '#4A6CF7';
        c.pulsarRim = '#1E40AF';
        c.normalFill = '#A6E8DA';
        c.normalRim = '#5DBDA3';
        c.twinFill = '#FBA5A5';
        c.twinRim = '#DC8585';
        c.parentFill = '#A8E4C5';
        c.parentRim = '#5BB58E';
        c.luneFill = '#FCE3A2';
        c.luneRim = '#D4B872';
        c.lineStroke = '#94A3B8';
      },
    },
    {
      name: 'Mono slate',
      apply: (c) => {
        const v = '#1F2937';
        c.pulsarFill = v;
        c.pulsarRim = v;
        c.normalFill = v;
        c.normalRim = v;
        c.twinFill = v;
        c.twinRim = v;
        c.parentFill = v;
        c.parentRim = v;
        c.luneFill = v;
        c.luneRim = v;
        c.lineStroke = v;
      },
    },
    {
      name: 'Mono hero blue',
      apply: (c) => {
        const v = '#4A6CF7';
        c.pulsarFill = v;
        c.pulsarRim = v;
        c.normalFill = v;
        c.normalRim = v;
        c.twinFill = v;
        c.twinRim = v;
        c.parentFill = v;
        c.parentRim = v;
        c.luneFill = v;
        c.luneRim = v;
        c.lineStroke = v;
      },
    },
    {
      name: 'Mono emerald',
      apply: (c) => {
        const v = '#10B981';
        c.pulsarFill = v;
        c.pulsarRim = v;
        c.normalFill = v;
        c.normalRim = v;
        c.twinFill = v;
        c.twinRim = v;
        c.parentFill = v;
        c.parentRim = v;
        c.luneFill = v;
        c.luneRim = v;
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
        c.normalFill = w;
        c.normalRim = w;
        c.twinFill = w;
        c.twinRim = w;
        c.parentFill = w;
        c.parentRim = w;
        c.luneFill = w;
        c.luneRim = w;
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
        c.normalFill = k;
        c.normalRim = k;
        c.twinFill = k;
        c.twinRim = k;
        c.parentFill = k;
        c.parentRim = k;
        c.luneFill = k;
        c.luneRim = k;
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
      // Disposition CB12 par défaut : 2 normaux NE + WSW
      normals: [
        { angle: -32, distance: 9.4 }, // NE (≈20, 7)
        { angle: 157, distance: 7.6 }, // WSW (≈5, 15)
      ],
      normalSize: 1.5,
      normalFill: '#FAC775',
      normalRim: '#EF9F27',
      normalRimWidth: 0.4,
      yforkEnabled: true,
      yforkAngle: -126,
      yforkDistance: 8.6,
      twinA: { angle: -148, distance: 5.0 },
      twinB: { angle: -104, distance: 5.0 },
      twinSize: 1.5,
      twinFill: '#C0DD97',
      twinRim: '#639922',
      twinRimWidth: 0.4,
      parentEnabled: true,
      parentAngle: 50,
      parentDistance: 7.8,
      parentSize: 1.95,
      parentFill: '#B5D4F4',
      parentRim: '#378ADD',
      parentRimWidth: 0.45,
      luneEnabled: true,
      luneAngle: 50,
      luneDistance: 4.5,
      luneSize: 0.95,
      luneFill: '#CECBF6',
      luneRim: '#7F77DD',
      luneRimWidth: 0.35,
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
    PALETTES[1].apply(c); // 3D pulsar slate + Z13 sats
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
    const lastAngle = cfg.normals.length > 0 ? cfg.normals[cfg.normals.length - 1].angle : 0;
    cfg.normals.push({ angle: lastAngle + 60, distance: 9 });
    configs = configs;
  }
  function removeNormal(i: number) {
    configs[active].normals.splice(i, 1);
    configs = configs;
  }

  // ----- Géométrie -----
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
      parent = polar(pulsar.x, pulsar.y, c.parentAngle, c.parentDistance);
      if (c.luneEnabled) {
        lune = polar(parent.x, parent.y, c.luneAngle, c.luneDistance);
      }
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

  // ----- Drag souris -----
  type DragKind = 'pulsar' | 'normal' | 'fork' | 'twinA' | 'twinB' | 'parent' | 'lune';
  let dragging = $state<{ kind: DragKind; idx?: number } | null>(null);
  let svgEl: SVGSVGElement | null = $state(null);

  function svgPoint(evt: MouseEvent | PointerEvent): { x: number; y: number } | null {
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
      const dx = p.x - cfg.pulsarX;
      const dy = p.y - cfg.pulsarY;
      cfg.normals[idx] = {
        angle: (Math.atan2(dy, dx) * 180) / Math.PI,
        distance: Math.sqrt(dx * dx + dy * dy),
      };
    } else if (kind === 'fork') {
      const dx = p.x - cfg.pulsarX;
      const dy = p.y - cfg.pulsarY;
      cfg.yforkAngle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.yforkDistance = Math.sqrt(dx * dx + dy * dy);
    } else if (kind === 'twinA' || kind === 'twinB') {
      const fork = polar(cfg.pulsarX, cfg.pulsarY, cfg.yforkAngle, cfg.yforkDistance);
      const dx = p.x - fork.x;
      const dy = p.y - fork.y;
      const node = {
        angle: (Math.atan2(dy, dx) * 180) / Math.PI,
        distance: Math.sqrt(dx * dx + dy * dy),
      };
      if (kind === 'twinA') cfg.twinA = node;
      else cfg.twinB = node;
    } else if (kind === 'parent') {
      const dx = p.x - cfg.pulsarX;
      const dy = p.y - cfg.pulsarY;
      cfg.parentAngle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.parentDistance = Math.sqrt(dx * dx + dy * dy);
    } else if (kind === 'lune') {
      const parent = polar(cfg.pulsarX, cfg.pulsarY, cfg.parentAngle, cfg.parentDistance);
      const dx = p.x - parent.x;
      const dy = p.y - parent.y;
      cfg.luneAngle = (Math.atan2(dy, dx) * 180) / Math.PI;
      cfg.luneDistance = Math.sqrt(dx * dx + dy * dy);
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
      Défaut basé sur Z13 auteur-kind. 4 sous-sandboxes (référence / dark / wordmark / N&amp;B).
      Glisse les nœuds à la souris pour les repositionner, ajoute/supprime des normaux, zoome dans
      l'aperçu.
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

            {#each g.normals as n, i (i)}
              {#if c.fondEnabled}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={c.normalSize}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={n.x}
                cy={n.y}
                r={c.normalSize}
                fill={c.normalFill}
                stroke={c.normalRimWidth > 0 ? c.normalRim : 'none'}
                stroke-width={c.normalRimWidth}
                class="draggable"
                onmousedown={startDrag('normal', i)}
              />
            {/each}

            {#if g.forkM && g.twins}
              <!-- Poignée invisible pour forkM (sinon non draggable, c'est juste un point) -->
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
              {#each g.twins as t, i (i)}
                {#if c.fondEnabled}
                  <circle
                    cx={t.x}
                    cy={t.y}
                    r={c.twinSize}
                    fill="none"
                    stroke={c.fondColor}
                    stroke-width={c.fondWidth}
                  />
                {/if}
                <circle
                  cx={t.x}
                  cy={t.y}
                  r={c.twinSize}
                  fill={c.twinFill}
                  stroke={c.twinRimWidth > 0 ? c.twinRim : 'none'}
                  stroke-width={c.twinRimWidth}
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
                  r={c.parentSize}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={g.parent.x}
                cy={g.parent.y}
                r={c.parentSize}
                fill={c.parentFill}
                stroke={c.parentRimWidth > 0 ? c.parentRim : 'none'}
                stroke-width={c.parentRimWidth}
                class="draggable"
                onmousedown={startDrag('parent')}
              />
            {/if}
            {#if g.lune}
              {#if c.fondEnabled}
                <circle
                  cx={g.lune.x}
                  cy={g.lune.y}
                  r={c.luneSize}
                  fill="none"
                  stroke={c.fondColor}
                  stroke-width={c.fondWidth}
                />
              {/if}
              <circle
                cx={g.lune.x}
                cy={g.lune.y}
                r={c.luneSize}
                fill={c.luneFill}
                stroke={c.luneRimWidth > 0 ? c.luneRim : 'none'}
                stroke-width={c.luneRimWidth}
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
                {#each g2.normals as n (n.x + '-' + n.y)}
                  <circle cx={n.x} cy={n.y} r={cfg.normalSize} fill={cfg.normalFill} />
                {/each}
                {#if g2.twins}
                  {#each g2.twins as t, j (j)}
                    <circle cx={t.x} cy={t.y} r={cfg.twinSize} fill={cfg.twinFill} />
                  {/each}
                {/if}
                {#if g2.parent}
                  <circle
                    cx={g2.parent.x}
                    cy={g2.parent.y}
                    r={cfg.parentSize}
                    fill={cfg.parentFill}
                  />
                {/if}
                {#if g2.lune}
                  <circle cx={g2.lune.x} cy={g2.lune.y} r={cfg.luneSize} fill={cfg.luneFill} />
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
        <summary>Palettes prédéfinies</summary>
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
        <p class="hint">Glisse-les directement dans l'aperçu pour les repositionner.</p>
        {#each configs[active].normals as n, i (i)}
          <div class="node-row">
            <strong>#{i + 1}</strong>
            <button type="button" class="del-btn" onclick={() => removeNormal(i)} title="Supprimer"
              >✕</button
            >
            <div class="slider">
              <label>Angle <span class="val">{n.angle.toFixed(0)}°</span></label>
              <input type="range" min="-180" max="180" step="1" bind:value={n.angle} />
            </div>
            <div class="slider">
              <label>Distance <span class="val">{n.distance.toFixed(2)}</span></label>
              <input type="range" min="2" max="15" step="0.1" bind:value={n.distance} />
            </div>
          </div>
        {/each}
        <hr class="divider" />
        <p class="hint">Style commun aux normaux :</p>
        <div class="slider">
          <label>Taille <span class="val">{configs[active].normalSize.toFixed(2)}</span></label>
          <input
            type="range"
            min="0.3"
            max="4"
            step="0.05"
            bind:value={configs[active].normalSize}
          />
        </div>
        <div class="row">
          <label>Fill</label>
          <input type="color" bind:value={configs[active].normalFill} />
          <input type="text" bind:value={configs[active].normalFill} class="hex" />
        </div>
        <div class="row">
          <label>Rim</label>
          <input type="color" bind:value={configs[active].normalRim} />
          <input type="text" bind:value={configs[active].normalRim} class="hex" />
        </div>
        <div class="slider">
          <label
            >Épaisseur rim <span class="val">{configs[active].normalRimWidth.toFixed(2)}</span
            ></label
          >
          <input
            type="range"
            min="0"
            max="2"
            step="0.05"
            bind:value={configs[active].normalRimWidth}
          />
        </div>
      </details>

      <details>
        <summary>Y-fork (paire citée)</summary>
        <div class="row">
          <label>Activé</label>
          <input type="checkbox" bind:checked={configs[active].yforkEnabled} />
        </div>
        {#if configs[active].yforkEnabled}
          <p class="hint">Glisse la jonction (petit pointillé) et chaque twin dans l'aperçu.</p>
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
          <div class="slider">
            <label
              >Twin A — angle <span class="val">{configs[active].twinA.angle.toFixed(0)}°</span
              ></label
            >
            <input
              type="range"
              min="-180"
              max="180"
              step="1"
              bind:value={configs[active].twinA.angle}
            />
          </div>
          <div class="slider">
            <label
              >Twin A — distance <span class="val">{configs[active].twinA.distance.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="1"
              max="10"
              step="0.1"
              bind:value={configs[active].twinA.distance}
            />
          </div>
          <div class="slider">
            <label
              >Twin B — angle <span class="val">{configs[active].twinB.angle.toFixed(0)}°</span
              ></label
            >
            <input
              type="range"
              min="-180"
              max="180"
              step="1"
              bind:value={configs[active].twinB.angle}
            />
          </div>
          <div class="slider">
            <label
              >Twin B — distance <span class="val">{configs[active].twinB.distance.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="1"
              max="10"
              step="0.1"
              bind:value={configs[active].twinB.distance}
            />
          </div>
          <div class="slider">
            <label
              >Taille twins <span class="val">{configs[active].twinSize.toFixed(2)}</span></label
            >
            <input
              type="range"
              min="0.3"
              max="4"
              step="0.05"
              bind:value={configs[active].twinSize}
            />
          </div>
          <div class="row">
            <label>Fill</label>
            <input type="color" bind:value={configs[active].twinFill} />
            <input type="text" bind:value={configs[active].twinFill} class="hex" />
          </div>
          <div class="row">
            <label>Rim</label>
            <input type="color" bind:value={configs[active].twinRim} />
            <input type="text" bind:value={configs[active].twinRim} class="hex" />
          </div>
          <div class="slider">
            <label
              >Épaisseur rim <span class="val">{configs[active].twinRimWidth.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              bind:value={configs[active].twinRimWidth}
            />
          </div>
        {/if}
      </details>

      <details>
        <summary>Parent + Lune</summary>
        <div class="row">
          <label>Parent activé</label>
          <input type="checkbox" bind:checked={configs[active].parentEnabled} />
        </div>
        {#if configs[active].parentEnabled}
          <div class="slider">
            <label
              >Angle parent <span class="val">{configs[active].parentAngle.toFixed(0)}°</span
              ></label
            >
            <input
              type="range"
              min="-180"
              max="180"
              step="1"
              bind:value={configs[active].parentAngle}
            />
          </div>
          <div class="slider">
            <label
              >Distance parent <span class="val">{configs[active].parentDistance.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="2"
              max="14"
              step="0.1"
              bind:value={configs[active].parentDistance}
            />
          </div>
          <div class="slider">
            <label
              >Taille parent <span class="val">{configs[active].parentSize.toFixed(2)}</span></label
            >
            <input
              type="range"
              min="0.3"
              max="5"
              step="0.05"
              bind:value={configs[active].parentSize}
            />
          </div>
          <div class="row">
            <label>Fill parent</label>
            <input type="color" bind:value={configs[active].parentFill} />
            <input type="text" bind:value={configs[active].parentFill} class="hex" />
          </div>
          <div class="row">
            <label>Rim parent</label>
            <input type="color" bind:value={configs[active].parentRim} />
            <input type="text" bind:value={configs[active].parentRim} class="hex" />
          </div>
          <div class="slider">
            <label
              >Épaisseur rim parent <span class="val"
                >{configs[active].parentRimWidth.toFixed(2)}</span
              ></label
            >
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              bind:value={configs[active].parentRimWidth}
            />
          </div>
          <div class="row">
            <label>Lune activée</label>
            <input type="checkbox" bind:checked={configs[active].luneEnabled} />
          </div>
          {#if configs[active].luneEnabled}
            <div class="slider">
              <label
                >Angle lune <span class="val">{configs[active].luneAngle.toFixed(0)}°</span></label
              >
              <input
                type="range"
                min="-180"
                max="180"
                step="1"
                bind:value={configs[active].luneAngle}
              />
            </div>
            <div class="slider">
              <label
                >Distance lune <span class="val">{configs[active].luneDistance.toFixed(2)}</span
                ></label
              >
              <input
                type="range"
                min="1"
                max="8"
                step="0.1"
                bind:value={configs[active].luneDistance}
              />
            </div>
            <div class="slider">
              <label
                >Taille lune <span class="val">{configs[active].luneSize.toFixed(2)}</span></label
              >
              <input
                type="range"
                min="0.2"
                max="3"
                step="0.05"
                bind:value={configs[active].luneSize}
              />
            </div>
            <div class="row">
              <label>Fill lune</label>
              <input type="color" bind:value={configs[active].luneFill} />
              <input type="text" bind:value={configs[active].luneFill} class="hex" />
            </div>
            <div class="row">
              <label>Rim lune</label>
              <input type="color" bind:value={configs[active].luneRim} />
              <input type="text" bind:value={configs[active].luneRim} class="hex" />
            </div>
            <div class="slider">
              <label
                >Épaisseur rim lune <span class="val"
                  >{configs[active].luneRimWidth.toFixed(2)}</span
                ></label
              >
              <input
                type="range"
                min="0"
                max="2"
                step="0.05"
                bind:value={configs[active].luneRimWidth}
              />
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
    transition: all 0.12s;
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
  .node-row {
    display: grid;
    grid-template-columns: auto auto 1fr;
    gap: 0.3rem 0.5rem;
    align-items: center;
    padding: 0.5rem;
    margin: 0.4rem 0;
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    background: rgb(var(--bg-primary));
  }
  .node-row strong {
    font-size: 0.78rem;
    color: rgb(var(--text-secondary));
  }
  .node-row .slider {
    grid-column: 1 / -1;
    margin: 0.2rem 0;
  }
  .hint {
    font-size: 0.75rem;
    color: rgb(var(--text-tertiary));
    margin: 0.3rem 0;
    font-style: italic;
  }
  .divider {
    border: none;
    border-top: 1px solid rgb(var(--border));
    margin: 0.6rem 0;
  }
</style>
