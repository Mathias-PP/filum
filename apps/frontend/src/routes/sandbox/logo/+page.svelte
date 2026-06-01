<script lang="ts">
  // Logo Philum sandbox — 10 nouvelles propositions
  // Philum ⟵ inspiré de phylum biologique (du grec phûlon, "lignée") — chaque variante mark
  // évoque l'arbre de filiation des sources, certaines aussi le fil (homophonie filum/fil).
  // Toutes en SVG 24×24, monochrome currentColor.

  let strokeWidth = $state(1.5);
  let centerRadius = $state(2.5);
  let leafRadius = $state(1.5);
  let scale = $state(160);
  // Couleur recommandée : `#4A6CF7` en monochrome (stroke + nœuds).
  // C'est le bleu déjà utilisé dans le gradient `nodeGlow` du hero SVG
  // d'origine, et il s'aligne avec le token `--info` du design system.
  // Le monochrome est plus pro pour un logo et scale mieux à petite taille
  // (favicon 16px) que le contraste trait noir / nœud bleu.
  let accentColor = $state('#4A6CF7');
  let strokeColor = $state('#4A6CF7');

  // Spiral V10 — pré-calcul (les `{@const}` ne sont pas valides hors blocs Svelte)
  const _spiralTurns = 1.8;
  const _spiralSamples = 60;
  const _spiralPts = Array.from({ length: _spiralSamples + 1 }, (_, i) => {
    const t = (i / _spiralSamples) * _spiralTurns * Math.PI * 2;
    const r = 1.0 + (t / (_spiralTurns * Math.PI * 2)) * 9.2;
    return { x: 12 + r * Math.cos(t - Math.PI / 2), y: 12 + r * Math.sin(t - Math.PI / 2) };
  });
  const spiralPath =
    'M ' + _spiralPts.map((p) => `${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(' L ');
  const spiralNodes = [0.18, 0.38, 0.58, 0.78, 0.98].map((f) => {
    const t = f * _spiralTurns * Math.PI * 2;
    const r = 1.0 + f * 9.2;
    return {
      x: 12 + r * Math.cos(t - Math.PI / 2),
      y: 12 + r * Math.sin(t - Math.PI / 2),
      size: 0.8 + f * 0.4,
    };
  });

  // Référence: logo actuel
  const currentLogo = {
    branches: [
      {
        mid: { x: 12, y: 5.5 },
        leaves: [
          { x: 9, y: 2 },
          { x: 15, y: 2 },
        ],
      },
      {
        mid: { x: 17.5, y: 9 },
        leaves: [
          { x: 18.5, y: 4.5 },
          { x: 21.5, y: 9 },
        ],
      },
      {
        mid: { x: 17.5, y: 15 },
        leaves: [
          { x: 18.5, y: 19.5 },
          { x: 21.5, y: 15 },
        ],
      },
      {
        mid: { x: 12, y: 18.5 },
        leaves: [
          { x: 9, y: 22 },
          { x: 15, y: 22 },
        ],
      },
      {
        mid: { x: 6.5, y: 15 },
        leaves: [
          { x: 5.5, y: 19.5 },
          { x: 2.5, y: 15 },
        ],
      },
      {
        mid: { x: 6.5, y: 9 },
        leaves: [
          { x: 5.5, y: 4.5 },
          { x: 2.5, y: 9 },
        ],
      },
    ],
  };
</script>

<svelte:head>
  <title>Sandbox · Logo Philum</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="page">
  <header class="bar">
    <h1>Sandbox · Logo Philum — 10 nouvelles propositions</h1>
    <p>Logo actuel à gauche en référence. 10 directions différentes ensuite.</p>
  </header>

  <div class="grid">
    <!-- RÉFÉRENCE — Logo actuel -->
    <div class="card reference">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          {#each currentLogo.branches as b, i (i)}
            <line x1="12" y1="12" x2={b.mid.x} y2={b.mid.y} />
            {#each b.leaves as l}
              <line x1={b.mid.x} y1={b.mid.y} x2={l.x} y2={l.y} />
              <circle cx={l.x} cy={l.y} r={leafRadius} fill="currentColor" stroke="none" />
            {/each}
          {/each}
        </svg>
      </div>
      <h3>Référence</h3>
      <p class="caption">Logo actuel — point de comparaison.</p>
    </div>

    <!-- V1 — Cladogramme vertical SYMÉTRIQUE (V8 + V11 : verticalité + symétrie) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="22" r={centerRadius * 1.05} fill="currentColor" stroke="none" />
          <line x1="12" y1="22" x2="12" y2="17" />
          <!-- Première bifurcation symétrique -->
          <line x1="5" y1="17" x2="19" y2="17" />
          <line x1="5" y1="17" x2="5" y2="11" />
          <line x1="19" y1="17" x2="19" y2="11" />
          <!-- Bifurcations symétriques de profondeur 2 -->
          <line x1="2" y1="11" x2="8" y2="11" />
          <line x1="2" y1="11" x2="2" y2="3" />
          <line x1="8" y1="11" x2="8" y2="3" />
          <line x1="16" y1="11" x2="22" y2="11" />
          <line x1="16" y1="11" x2="16" y2="3" />
          <line x1="22" y1="11" x2="22" y2="3" />
          {#each [2, 8, 16, 22] as x}
            <circle cx={x} cy="3" r={leafRadius * 1.05} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V1 — Cladogramme vertical symétrique</h3>
      <p class="caption">
        Cousin parfaitement symétrique de V8. Racine en bas, 4 feuilles alignées. Versions binaire
        propre.
      </p>
    </div>

    <!-- V2 — Dendrogramme horizontal asymétrique (V3 + V8 : horizontal + profondeurs variables) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="2" cy="12" r={centerRadius * 1.05} fill="currentColor" stroke="none" />
          <line x1="2" y1="12" x2="7" y2="12" />
          <line x1="7" y1="6" x2="7" y2="18" />
          <!-- Haut : bifurcation profonde -->
          <line x1="7" y1="6" x2="12" y2="6" />
          <line x1="12" y1="3" x2="12" y2="9" />
          <line x1="12" y1="3" x2="22" y2="3" />
          <line x1="12" y1="9" x2="17" y2="9" />
          <line x1="17" y1="6" x2="17" y2="12" />
          <line x1="17" y1="6" x2="22" y2="6" />
          <line x1="17" y1="12" x2="22" y2="12" />
          <!-- Bas : direct (profondeur 1, comme V3) -->
          <line x1="7" y1="18" x2="22" y2="18" />
          <line x1="7" y1="18" x2="7" y2="21" />
          <line x1="22" y1="18" x2="22" y2="21" />
          <!-- 5 feuilles aux profondeurs variables -->
          {#each [{ x: 22, y: 3 }, { x: 22, y: 6 }, { x: 22, y: 12 }, { x: 22, y: 18 }, { x: 22, y: 21 }] as p, i (i)}
            <circle cx={p.x} cy={p.y} r={leafRadius} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V2 — Cladogramme horizontal à profondeurs variables</h3>
      <p class="caption">
        V3 horizontalement, mais avec branches de profondeurs inégales (V8 idée). Suggère que
        certaines sources ont une chaîne de citations plus longue.
      </p>
    </div>

    <!-- V3 — Dendrogramme horizontal -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <!-- Racine à gauche -->
          <circle cx="2" cy="12" r={centerRadius * 1.05} fill="currentColor" stroke="none" />
          <!-- Tronc -->
          <line x1="2" y1="12" x2="7" y2="12" />
          <!-- Première bifurcation -->
          <line x1="7" y1="6" x2="7" y2="18" />
          <!-- Branches du haut -->
          <line x1="7" y1="6" x2="12" y2="6" />
          <line x1="12" y1="3" x2="12" y2="9" />
          <line x1="12" y1="3" x2="18" y2="3" />
          <line x1="12" y1="9" x2="18" y2="9" />
          <!-- Branches du bas -->
          <line x1="7" y1="18" x2="12" y2="18" />
          <line x1="12" y1="15" x2="12" y2="21" />
          <line x1="12" y1="15" x2="18" y2="15" />
          <line x1="12" y1="21" x2="18" y2="21" />
          <!-- Feuilles -->
          {#each [3, 9, 15, 21] as y, i (i)}
            <circle cx="18" cy={y} r={leafRadius} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V3 — Dendrogramme horizontal</h3>
      <p class="caption">
        Arbre phylogénétique classique. Racine à gauche, ramifications par angles droits, feuilles
        alignées à droite.
      </p>
    </div>

    <!-- V4 — Dendrogramme radial (V3 + V11 : phylogénie en disposition radiale) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- 6 radials. Sur chaque branche, après une portion droite, un Y -->
          {#each [-90, -30, 30, 90, 150, 210] as deg, i (i)}
            {@const rad = (deg * Math.PI) / 180}
            {@const mid = { x: 12 + 5.5 * Math.cos(rad), y: 12 + 5.5 * Math.sin(rad) }}
            {@const perp = { x: -Math.sin(rad), y: Math.cos(rad) }}
            {@const f1 = {
              x: mid.x + 4.5 * Math.cos(rad) - 1.6 * perp.x,
              y: mid.y + 4.5 * Math.sin(rad) - 1.6 * perp.y,
            }}
            {@const f2 = {
              x: mid.x + 4.5 * Math.cos(rad) + 1.6 * perp.x,
              y: mid.y + 4.5 * Math.sin(rad) + 1.6 * perp.y,
            }}
            <!-- Branche radiale droite -->
            <line x1="12" y1="12" x2={mid.x} y2={mid.y} />
            <!-- Trait latéral perpendiculaire (style cladogramme rectangulaire) -->
            <line
              x1={mid.x - 1.6 * perp.x}
              y1={mid.y - 1.6 * perp.y}
              x2={mid.x + 1.6 * perp.x}
              y2={mid.y + 1.6 * perp.y}
            />
            <!-- Deux feuilles -->
            <line x1={mid.x - 1.6 * perp.x} y1={mid.y - 1.6 * perp.y} x2={f1.x} y2={f1.y} />
            <line x1={mid.x + 1.6 * perp.x} y1={mid.y + 1.6 * perp.y} x2={f2.x} y2={f2.y} />
            <circle cx={f1.x} cy={f1.y} r={leafRadius * 0.95} fill="currentColor" stroke="none" />
            <circle cx={f2.x} cy={f2.y} r={leafRadius * 0.95} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V4 — Cladogramme radial</h3>
      <p class="caption">
        V3 disposé radialement (V11 layout). 6 directions, chacune avec un mini-cladogramme
        rectangulaire. Le motif phylogénétique se répète tout autour.
      </p>
    </div>

    <!-- V5 — Graphe organique asymétrique (mix forks + simples) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- Branche fork haut -->
          <line x1="12" y1="12" x2="11" y2="5" />
          <line x1="11" y1="5" x2="8" y2="2.5" />
          <line x1="11" y1="5" x2="14" y2="2" />
          <circle cx="8" cy="2.5" r={leafRadius} fill="currentColor" stroke="none" />
          <circle cx="14" cy="2" r={leafRadius} fill="currentColor" stroke="none" />
          <!-- Branche simple droite -->
          <line x1="12" y1="12" x2="21" y2="10" />
          <circle cx="21" cy="10" r={leafRadius * 1.15} fill="currentColor" stroke="none" />
          <!-- Branche fork bas-droite -->
          <line x1="12" y1="12" x2="17" y2="17.5" />
          <line x1="17" y1="17.5" x2="20" y2="20" />
          <line x1="17" y1="17.5" x2="18" y2="21.5" />
          <circle cx="20" cy="20" r={leafRadius} fill="currentColor" stroke="none" />
          <circle cx="18" cy="21.5" r={leafRadius} fill="currentColor" stroke="none" />
          <!-- Branche simple bas -->
          <line x1="12" y1="12" x2="9" y2="21" />
          <circle cx="9" cy="21" r={leafRadius * 1.15} fill="currentColor" stroke="none" />
          <!-- Branche fork gauche -->
          <line x1="12" y1="12" x2="4" y2="14" />
          <line x1="4" y1="14" x2="1.5" y2="17" />
          <line x1="4" y1="14" x2="2" y2="11" />
          <circle cx="1.5" cy="17" r={leafRadius} fill="currentColor" stroke="none" />
          <circle cx="2" cy="11" r={leafRadius} fill="currentColor" stroke="none" />
          <!-- Branche simple haut-gauche -->
          <line x1="12" y1="12" x2="4.5" y2="5" />
          <circle cx="4.5" cy="5" r={leafRadius * 1.15} fill="currentColor" stroke="none" />
        </svg>
      </div>
      <h3>V5 — Graphe organique</h3>
      <p class="caption">
        6 branches à angles libres : 3 forks (2 feuilles) + 3 simples (1 feuille). Asymétrie qui
        rappelle un vrai graphe de citations.
      </p>
    </div>

    <!-- V6 — Fork+simple à 4 axes (V11 minimaliste, ordre 2) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- 4 branches à 90° : alternance fork (horizontaux) / simple (verticaux) -->
          {#each [0, 90, 180, 270] as deg, i (i)}
            {@const rad = (deg * Math.PI) / 180}
            {@const isFork = i % 2 === 0}
            {@const branchLen = isFork ? 6.5 : 10}
            {@const mid = { x: 12 + branchLen * Math.cos(rad), y: 12 + branchLen * Math.sin(rad) }}
            <line x1="12" y1="12" x2={mid.x} y2={mid.y} />
            {#if isFork}
              {@const leafR = 10}
              {@const spread = (28 * Math.PI) / 180}
              {@const leaf1 = {
                x: 12 + leafR * Math.cos(rad - spread),
                y: 12 + leafR * Math.sin(rad - spread),
              }}
              {@const leaf2 = {
                x: 12 + leafR * Math.cos(rad + spread),
                y: 12 + leafR * Math.sin(rad + spread),
              }}
              <line x1={mid.x} y1={mid.y} x2={leaf1.x} y2={leaf1.y} />
              <line x1={mid.x} y1={mid.y} x2={leaf2.x} y2={leaf2.y} />
              <circle cx={leaf1.x} cy={leaf1.y} r={leafRadius} fill="currentColor" stroke="none" />
              <circle cx={leaf2.x} cy={leaf2.y} r={leafRadius} fill="currentColor" stroke="none" />
            {:else}
              <circle
                cx={mid.x}
                cy={mid.y}
                r={leafRadius * 1.15}
                fill="currentColor"
                stroke="none"
              />
            {/if}
          {/each}
        </svg>
      </div>
      <h3>V6 — Fork+simple à 4 axes</h3>
      <p class="caption">
        Version minimaliste de V11 : 2 forks (horizontaux) + 2 simples (verticaux). Symétrie d'ordre
        2. Plus aéré, plus moderne.
      </p>
    </div>

    <!-- V7 — Radial à profondeurs variables (V5 + V8 : mix forks + simples ET sous-feuilles) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- 6 branches dont 3 forkées + 3 simples, et 2 forks ont une SOUS-feuille
               (profondeur supplémentaire = source d'une source). -->
          {#each [{ deg: -90, kind: 'fork-deep' }, { deg: -30, kind: 'simple' }, { deg: 30, kind: 'fork' }, { deg: 90, kind: 'fork-deep' }, { deg: 150, kind: 'simple' }, { deg: 210, kind: 'fork' }] as b, i (i)}
            {@const rad = (b.deg * Math.PI) / 180}
            {@const midR = 5.5}
            {@const leafR = 9.5}
            {@const mid = { x: 12 + midR * Math.cos(rad), y: 12 + midR * Math.sin(rad) }}
            {@const simpleEnd = { x: 12 + leafR * Math.cos(rad), y: 12 + leafR * Math.sin(rad) }}
            {@const spread = (22 * Math.PI) / 180}
            {@const leaf1 = {
              x: 12 + leafR * Math.cos(rad - spread),
              y: 12 + leafR * Math.sin(rad - spread),
            }}
            {@const leaf2 = {
              x: 12 + leafR * Math.cos(rad + spread),
              y: 12 + leafR * Math.sin(rad + spread),
            }}
            {@const subSpread = (14 * Math.PI) / 180}
            {@const sub1 = {
              x: 12 + (leafR + 3) * Math.cos(rad - spread - subSpread),
              y: 12 + (leafR + 3) * Math.sin(rad - spread - subSpread),
            }}
            <line
              x1="12"
              y1="12"
              x2={b.kind === 'simple' ? simpleEnd.x : mid.x}
              y2={b.kind === 'simple' ? simpleEnd.y : mid.y}
            />
            {#if b.kind === 'simple'}
              <circle
                cx={simpleEnd.x}
                cy={simpleEnd.y}
                r={leafRadius * 1.1}
                fill="currentColor"
                stroke="none"
              />
            {:else}
              <line x1={mid.x} y1={mid.y} x2={leaf1.x} y2={leaf1.y} />
              <line x1={mid.x} y1={mid.y} x2={leaf2.x} y2={leaf2.y} />
              <circle cx={leaf1.x} cy={leaf1.y} r={leafRadius} fill="currentColor" stroke="none" />
              <circle cx={leaf2.x} cy={leaf2.y} r={leafRadius} fill="currentColor" stroke="none" />
              {#if b.kind === 'fork-deep'}
                <line x1={leaf1.x} y1={leaf1.y} x2={sub1.x} y2={sub1.y} />
                <circle
                  cx={sub1.x}
                  cy={sub1.y}
                  r={leafRadius * 0.75}
                  fill="currentColor"
                  stroke="none"
                />
              {/if}
            {/if}
          {/each}
        </svg>
      </div>
      <h3>V7 — Radial à profondeurs variables</h3>
      <p class="caption">
        Mix de V5 (forks/simples) + V8 (profondeurs variables) en disposition radiale. 2 forks
        profonds (sous-feuille), 1 fork simple, 2 simples directs.
      </p>
    </div>

    <!-- V8 — Dendrogramme vertical à profondeurs variables -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <!-- Racine -->
          <circle cx="12" cy="22" r={centerRadius * 1.05} fill="currentColor" stroke="none" />
          <line x1="12" y1="22" x2="12" y2="17" />
          <!-- Bifurcation principale -->
          <line x1="6" y1="17" x2="18" y2="17" />
          <line x1="6" y1="17" x2="6" y2="12" />
          <line x1="18" y1="17" x2="18" y2="11" />
          <!-- Gauche : bifurcation à profondeur 2 -->
          <line x1="3" y1="12" x2="9" y2="12" />
          <line x1="3" y1="12" x2="3" y2="6" />
          <line x1="9" y1="12" x2="9" y2="8" />
          <line x1="3" y1="6" x2="3" y2="2" />
          <line x1="9" y1="8" x2="9" y2="2" />
          <!-- Droite : bifurcation à profondeur asymétrique -->
          <line x1="15" y1="11" x2="21" y2="11" />
          <line x1="15" y1="11" x2="15" y2="5" />
          <line x1="21" y1="11" x2="21" y2="9" />
          <line x1="15" y1="5" x2="15" y2="2" />
          <line x1="21" y1="9" x2="18" y2="9" />
          <line x1="21" y1="9" x2="21" y2="2" />
          <line x1="18" y1="9" x2="18" y2="2" />
          <!-- Feuilles : 5 -->
          {#each [3, 9, 15, 18, 21] as x}
            <circle cx={x} cy="2" r={leafRadius * 0.95} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V8 — Dendrogramme vertical à profondeurs variables</h3>
      <p class="caption">
        Phylogénie verticale, racine en bas. Branches à profondeurs irrégulières — certaines sources
        sont citées par chaîne plus longue.
      </p>
    </div>

    <!-- V9 — Triskèle phylogénétique (V11 symétrie 3 + V8 mini-dendrogrammes verticaux) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- 3 branches symétriques (120°), chacune est un mini-cladogramme rectangulaire -->
          {#each [-90, 30, 150] as deg, i (i)}
            {@const rad = (deg * Math.PI) / 180}
            {@const tan = { x: -Math.sin(rad), y: Math.cos(rad) }}
            <!-- Branche radiale principale -->
            {@const p1 = { x: 12 + 5.5 * Math.cos(rad), y: 12 + 5.5 * Math.sin(rad) }}
            {@const p2 = { x: 12 + 8.5 * Math.cos(rad), y: 12 + 8.5 * Math.sin(rad) }}
            <line x1="12" y1="12" x2={p2.x} y2={p2.y} />
            <!-- Bifurcation perpendiculaire -->
            {@const cross1 = { x: p1.x + 2.8 * tan.x, y: p1.y + 2.8 * tan.y }}
            {@const cross2 = { x: p1.x - 2.8 * tan.x, y: p1.y - 2.8 * tan.y }}
            <line x1={cross1.x} y1={cross1.y} x2={cross2.x} y2={cross2.y} />
            <!-- Feuilles à l'extérieur -->
            {@const leaf1 = {
              x: cross1.x + 2.5 * Math.cos(rad),
              y: cross1.y + 2.5 * Math.sin(rad),
            }}
            {@const leaf2 = {
              x: cross2.x + 2.5 * Math.cos(rad),
              y: cross2.y + 2.5 * Math.sin(rad),
            }}
            <line x1={cross1.x} y1={cross1.y} x2={leaf1.x} y2={leaf1.y} />
            <line x1={cross2.x} y1={cross2.y} x2={leaf2.x} y2={leaf2.y} />
            <circle cx={p2.x} cy={p2.y} r={leafRadius} fill="currentColor" stroke="none" />
            <circle
              cx={leaf1.x}
              cy={leaf1.y}
              r={leafRadius * 0.85}
              fill="currentColor"
              stroke="none"
            />
            <circle
              cx={leaf2.x}
              cy={leaf2.y}
              r={leafRadius * 0.85}
              fill="currentColor"
              stroke="none"
            />
          {/each}
        </svg>
      </div>
      <h3>V9 — Triskèle phylogénétique</h3>
      <p class="caption">
        3 branches à 120° (symétrie de V11), chacune un mini-cladogramme rectangulaire avec 3
        feuilles. Croise la pureté géométrique du triskèle avec la rigueur du cladogramme.
      </p>
    </div>

    <!-- V11 — Fork + simple alternés (symétrie 3 fois) — refonte du V8 précédent demandé -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
          <!-- 6 branches à 60° : alternance fork / simple → symétrie d'ordre 3 -->
          {#each [-90, -30, 30, 90, 150, 210] as deg, i (i)}
            {@const rad = (deg * Math.PI) / 180}
            {@const isFork = i % 2 === 0}
            {@const branchLen = isFork ? 6 : 9.2}
            {@const mid = { x: 12 + branchLen * Math.cos(rad), y: 12 + branchLen * Math.sin(rad) }}
            <line x1="12" y1="12" x2={mid.x} y2={mid.y} />
            {#if isFork}
              {@const leafR = 9.2}
              {@const spread = (22 * Math.PI) / 180}
              {@const leaf1 = {
                x: 12 + leafR * Math.cos(rad - spread),
                y: 12 + leafR * Math.sin(rad - spread),
              }}
              {@const leaf2 = {
                x: 12 + leafR * Math.cos(rad + spread),
                y: 12 + leafR * Math.sin(rad + spread),
              }}
              <line x1={mid.x} y1={mid.y} x2={leaf1.x} y2={leaf1.y} />
              <line x1={mid.x} y1={mid.y} x2={leaf2.x} y2={leaf2.y} />
              <circle cx={leaf1.x} cy={leaf1.y} r={leafRadius} fill="currentColor" stroke="none" />
              <circle cx={leaf2.x} cy={leaf2.y} r={leafRadius} fill="currentColor" stroke="none" />
            {:else}
              <circle
                cx={mid.x}
                cy={mid.y}
                r={leafRadius * 1.15}
                fill="currentColor"
                stroke="none"
              />
            {/if}
          {/each}
        </svg>
      </div>
      <h3>V11 — Fork + simple alternés</h3>
      <p class="caption">
        3 branches forkées (2 feuilles) et 3 branches simples (1 feuille) alternées tous les 60°
        autour du centre. Symétrie d'ordre 3 parfaite. Évolution symétrique de la version
        précédente.
      </p>
    </div>

    <!-- V10 — Cladogramme horizontal symétrique compact (V3 + V11 : binaire pur) -->
    <div class="card">
      <div class="canvas">
        <svg
          viewBox="0 0 24 24"
          width={scale}
          height={scale}
          fill="none"
          stroke={strokeColor}
          stroke-width={strokeWidth}
          stroke-linecap="round"
          stroke-linejoin="round"
          style="color: {accentColor}"
        >
          <circle cx="3" cy="12" r={centerRadius * 1.1} fill="currentColor" stroke="none" />
          <line x1="3" y1="12" x2="10" y2="12" />
          <line x1="10" y1="5" x2="10" y2="19" />
          <line x1="10" y1="5" x2="15" y2="5" />
          <line x1="10" y1="19" x2="15" y2="19" />
          <line x1="15" y1="2" x2="15" y2="8" />
          <line x1="15" y1="16" x2="15" y2="22" />
          <line x1="15" y1="2" x2="21" y2="2" />
          <line x1="15" y1="8" x2="21" y2="8" />
          <line x1="15" y1="16" x2="21" y2="16" />
          <line x1="15" y1="22" x2="21" y2="22" />
          {#each [2, 8, 16, 22] as y}
            <circle cx="21" cy={y} r={leafRadius} fill="currentColor" stroke="none" />
          {/each}
        </svg>
      </div>
      <h3>V10 — Cladogramme horizontal compact</h3>
      <p class="caption">
        V3 simplifié à l'os : arbre binaire parfait à 2 niveaux, 4 feuilles symétriques. Cadre
        serré, idéal pour bandeau ou favicon.
      </p>
    </div>
  </div>

  <aside class="panel">
    <label>
      <span>Taille rendu <em>{scale}px</em></span>
      <input type="range" min="80" max="240" step="4" bind:value={scale} />
    </label>
    <label>
      <span>Épaisseur trait <em>{strokeWidth.toFixed(2)}</em></span>
      <input type="range" min="0.5" max="3" step="0.05" bind:value={strokeWidth} />
    </label>
    <label>
      <span>Rayon centre <em>{centerRadius.toFixed(2)}</em></span>
      <input type="range" min="1" max="4" step="0.1" bind:value={centerRadius} />
    </label>
    <label>
      <span>Rayon feuilles <em>{leafRadius.toFixed(2)}</em></span>
      <input type="range" min="0.6" max="2.5" step="0.05" bind:value={leafRadius} />
    </label>
    <label>
      <span>Couleur accent (nœuds)</span>
      <input type="color" bind:value={accentColor} />
    </label>
    <label>
      <span>Couleur trait</span>
      <input type="color" bind:value={strokeColor} />
    </label>
  </aside>
</div>

<style>
  .page {
    min-height: 100vh;
    background: #f6f7f9;
    color: #1a1a1a;
    padding: 1.5rem;
    font-family: 'Inter', system-ui, sans-serif;
  }
  :global(.dark) .page {
    background: #0a0a0f;
    color: #e5e7eb;
  }
  .bar h1 {
    font-size: 1.25rem;
    font-weight: 500;
    margin: 0 0 0.25rem;
  }
  .bar p {
    font-size: 0.85rem;
    color: #64748b;
    margin: 0 0 1.5rem;
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 1rem;
    max-width: 1400px;
    margin: 0 auto;
    padding-bottom: 6rem;
  }
  .card {
    background: white;
    border: 1px solid rgba(0, 0, 0, 0.08);
    border-radius: 12px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
  }
  .card.reference {
    border-color: rgba(107, 138, 255, 0.35);
    background: linear-gradient(180deg, rgba(107, 138, 255, 0.04) 0%, white 100%);
  }
  :global(.dark) .card {
    background: #14141a;
    border-color: rgba(255, 255, 255, 0.08);
  }
  :global(.dark) .card.reference {
    background: linear-gradient(180deg, rgba(107, 138, 255, 0.1) 0%, #14141a 100%);
    border-color: rgba(107, 138, 255, 0.3);
  }
  .canvas {
    width: 100%;
    aspect-ratio: 1;
    background: #fafbfc;
    border: 1px dashed rgba(0, 0, 0, 0.06);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  :global(.dark) .canvas {
    background: #0d0d12;
    border-color: rgba(255, 255, 255, 0.06);
  }
  .card h3 {
    font-size: 0.95rem;
    font-weight: 500;
    margin: 0.25rem 0 0;
    text-align: center;
  }
  .caption {
    font-size: 0.75rem;
    color: #64748b;
    line-height: 1.4;
    text-align: center;
    margin: 0;
  }
  .panel {
    position: fixed;
    bottom: 1rem;
    right: 1rem;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.7rem;
    width: 240px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
  }
  :global(.dark) .panel {
    background: rgba(20, 20, 26, 0.96);
    border-color: rgba(255, 255, 255, 0.1);
  }
  .panel label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.78rem;
  }
  .panel label span {
    display: flex;
    justify-content: space-between;
  }
  .panel label em {
    font-style: normal;
    color: #64748b;
    font-variant-numeric: tabular-nums;
  }
  .panel input[type='range'] {
    width: 100%;
    accent-color: #6b8aff;
  }
  .panel input[type='color'] {
    width: 100%;
    height: 32px;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: 6px;
    background: none;
    cursor: pointer;
  }
</style>
