<script lang="ts">
  // Logo Filum sandbox — 10 nouvelles propositions
  // Filum = "fil" en latin (étymologie volontairement exploitée dans certaines variantes).
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

  // --- Système de couleurs étendu pour le panel "Pulsar-graph 20 variations".
  // Chaque élément topologique du mark peut être coloré indépendamment :
  // pulsar central, twins du Y-fork, parent (porte la lune), lune, halo
  // (effets 3D), et fond du canvas. Le trait reste contrôlé par strokeColor.
  let pulsarColor = $state('#4A6CF7');
  let twinColor = $state('#4A6CF7');
  let parentColor = $state('#4A6CF7');
  let luneColor = $state('#4A6CF7');
  let haloColor = $state('#6B8AFF');
  let canvasBg = $state('#fafbfc');

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
  <title>Sandbox · Logo Filum</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="page">
  <header class="bar">
    <h1>Sandbox · Logo Filum — 10 nouvelles propositions</h1>
    <p>Logo actuel à gauche en référence. 10 directions différentes ensuite.</p>
  </header>

  <section class="section-block">
    <h2 class="section-title">Pulsar-graph — 40 propositions couleur expertes · 2026-05-28</h2>
    <p class="section-lead">
      Quarante propositions <strong>couleurs fixées par variation</strong> — pas paramétrables, chacune
      incarne une direction de marque précise. Mixes demandés (V1, V2, V4, V9, V10, V11, V12, V18) combinés
      à six familles de palette et à neuf effets nouveaux différents de ceux des V06-V08-V17-V18 (drop-shadow,
      line weight variable, dashed, diffraction X-spikes, ring orbital, hollow/filled mix, gradient sur
      les lignes, frosted blur, multi-stroke).
    </p>
    <details class="design-rationale">
      <summary>Mon avis sur les choix de couleur (en tant que designer logo)</summary>
      <p>
        Filum vend de la <em>rigueur</em> et de la <em>traçabilité</em>, pas de l'effervescence
        SaaS. Les meilleurs marks dans cet espace (ORCID, Crossref, Wikipedia, JSTOR) sont soit
        monochromes soit bi-chromes, jamais maximalistes.
      </p>
      <ul>
        <li>
          <strong>Editorial Indigo</strong> (#4A6CF7 mono) — recommandation #1. Coherence parfaite avec
          l'accent existant du design system, fonctionne en favicon 16 px, fonctionne sans accroc en darkmode.
          C'est le choix le moins risqué.
        </li>
        <li>
          <strong>Editorial Duo</strong> (#1A1A1A + #4A6CF7) — recommandation #2. La couleur souligne
          ce qui compte : le pulsar reste noir (autorité scolaire) ou les twins en bleu (citation). Hiérarchie
          immédiate.
        </li>
        <li>
          <strong>Astronomical Pair</strong> (#3454D1 indigo + #F4A261 amber) — recommandé pour le lockup
          avec wordmark, plus chaleureux. Bleu-orange est un classique astronomique qui parle à la cible
          vulgarisateurs scientifiques.
        </li>
        <li>
          <strong>Hero Echo</strong> (palette intégrale du nouveau hero : cobalt, coral, amber, emerald,
          violet, gold, cyan, jade) — uniquement pour les usages premium / hero, JAMAIS en favicon. Six
          couleurs sur un mark 24 px se voient mal.
        </li>
        <li>
          <strong>Verified Stamp</strong> (#059669 vert d'attestation + slate) — alternative intéressante
          car raconte « vérifié », mais risque de connotation « bio » / écologie. Présentée pour explorer.
        </li>
        <li>
          <strong>Manuscript Sepia</strong> (#8B4513 + #D2B48C) — direction archives / parchemin. Très
          marquée éditoriale ancienne. Présentée mais peu probable comme choix final (trop niche).
        </li>
      </ul>
      <p>
        <strong>Ma top-3 finale</strong> : W19 (V11 + V18 z-layered en Editorial Indigo), W03 (V12 minimaliste
        Editorial Duo), W08 (V11 en Hero Echo pour usage premium).
      </p>
    </details>
    <div class="grid grid--dense">
      <!-- W01 — V1 centré · Editorial Indigo (mono) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W01 · V1</div>
        <h3>Centré · Editorial Indigo</h3>
        <p class="caption">Mono #4A6CF7. La référence sûre, alignée design system.</p>
      </div>

      <!-- W02 — V1 + Editorial Duo (noir pulsar + indigo accents) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W02 · V1</div>
        <h3>Centré · Editorial Duo</h3>
        <p class="caption">Pulsar noir (autorité), leaves indigo. Hiérarchie en 2 couleurs.</p>
      </div>

      <!-- W03 — V12 lune solo · Editorial Duo (la top-3 personnelle) -->
      <div class="card highlight">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#1A1A1A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W03 · V12 ⭐</div>
        <h3>Lune solo · Editorial Duo</h3>
        <p class="caption">Minimalisme absolu : trois nœuds, un seul accent bleu sur la lune.</p>
      </div>

      <!-- W04 — V12 · Astronomical Pair -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#3454D1"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#3454D1" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#3454D1" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#F4A261" stroke="none" />
          </svg>
        </div>
        <div class="num">W04 · V12</div>
        <h3>Lune solo · Astronomical</h3>
        <p class="caption">Indigo profond + ambre chaud sur la lune. Astronomique classique.</p>
      </div>

      <!-- W05 — V11 · Editorial Indigo (mono full) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W05 · V11</div>
        <h3>Constellation + lune · Indigo</h3>
        <p class="caption">3 sources directes + 1 parent-lune. Mono indigo, lecture neutre.</p>
      </div>

      <!-- W06 — V11 · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#1A1A1A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W06 · V11</div>
        <h3>V11 · Editorial Duo</h3>
        <p class="caption">Pulsar+parent noirs, leaves+lune indigo. Hiérarchie deux plans.</p>
      </div>

      <!-- W07 — V11 · Astronomical Pair -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#3454D1"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#3454D1" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#F4A261" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#3454D1" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#F4A261" stroke="none" />
          </svg>
        </div>
        <div class="num">W07 · V11</div>
        <h3>V11 · Astronomical Pair</h3>
        <p class="caption">Pulsar+parent indigo (axe primaire), leaves+lune ambre (satellites).</p>
      </div>

      <!-- W08 — V11 · Hero Echo (la top-3 personnelle, premium) -->
      <div class="card highlight">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#5B7FFF"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6, c: '#52E0C4' }, { x: 19, y: 4, c: '#F87171' }, { x: 4, y: 16, c: '#FCD34D' }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius * 1.1} fill="#FFFFFF" stroke="none" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            {#each [{ x: 5, y: 6, c: '#52E0C4' }, { x: 19, y: 4, c: '#F87171' }, { x: 4, y: 16, c: '#FCD34D' }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={p.c} stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#6EE7B7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#C4B5FD" stroke="none" />
          </svg>
        </div>
        <div class="num">W08 · V11 ⭐</div>
        <h3>V11 · Hero Echo (premium)</h3>
        <p class="caption">
          Palette intégrale du hero, sur fond sombre. Usage premium / lockup hero.
        </p>
      </div>

      <!-- W09 — V10 · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W09 · V10</div>
        <h3>Constellation + Y-fork · Indigo</h3>
        <p class="caption">3 sources directes + un Y-fork. Mono indigo, équilibré.</p>
      </div>

      <!-- W10 — V10 · Editorial Duo (Y-fork twins accentués) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#1A1A1A" stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W10 · V10</div>
        <h3>V10 · Editorial Duo</h3>
        <p class="caption">
          Tout noir sauf les twins du Y-fork en indigo : la « paire citée » saillit.
        </p>
      </div>

      <!-- W11 — V10 · twins Hero Echo (palette colorée sur les twins) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1F2937"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#F87171" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#FCD34D" stroke="none" />
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#1F2937" stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W11 · V10</div>
        <h3>V10 · twins Hero Echo</h3>
        <p class="caption">
          Twins en coral + amber (hero), reste sobre. Y-fork comme accent éditorial.
        </p>
      </div>

      <!-- W12 — V9 · Editorial Indigo (constellation mono) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W12 · V9</div>
        <h3>Constellation · Indigo</h3>
        <p class="caption">
          6 nœuds réguliers, pulsar central. Lecture « étoile + planètes » pure.
        </p>
      </div>

      <!-- W13 — V9 · Editorial Duo (hub noir, satellites bleus) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W13 · V9</div>
        <h3>V9 · Editorial Duo</h3>
        <p class="caption">Hub noir, satellites bleus. Très lisible, structure claire.</p>
      </div>

      <!-- W14 — V9 · Hero Echo (maximaliste) -->
      <div class="card">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6, c: '#5B7FFF' }, { x: 19, y: 4, c: '#F87171' }, { x: 21, y: 13, c: '#FCD34D' }, { x: 17, y: 21, c: '#6EE7B7' }, { x: 5, y: 19, c: '#C4B5FD' }, { x: 3, y: 12, c: '#52E0C4' }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <circle cx="12" cy="12" r={centerRadius * 1.1} fill="#FFFFFF" stroke="none" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            {#each [{ x: 5, y: 6, c: '#5B7FFF' }, { x: 19, y: 4, c: '#F87171' }, { x: 21, y: 13, c: '#FCD34D' }, { x: 17, y: 21, c: '#6EE7B7' }, { x: 5, y: 19, c: '#C4B5FD' }, { x: 3, y: 12, c: '#52E0C4' }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={p.c} stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">W14 · V9</div>
        <h3>V9 · Hero Echo maximaliste</h3>
        <p class="caption">
          6 couleurs hero distinctes sur fond sombre. Démo de richesse, à éviter en favicon.
        </p>
      </div>

      <!-- W15 — V2 BL · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="19" x2="11" y2="11" />
            <line x1="11" y1="11" x2="9" y2="5" />
            <line x1="11" y1="11" x2="17" y2="7" />
            <line x1="5" y1="19" x2="14" y2="20" />
            <line x1="14" y1="20" x2="18" y2="22" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
            <circle cx="9" cy="5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="7" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="14" cy="20" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="22" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W15 · V2</div>
        <h3>BL · Editorial Indigo</h3>
        <p class="caption">Pulsar coin SO, ascension NE. Mono indigo, dynamique diagonale.</p>
      </div>

      <!-- W16 — V2 BL · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="19" x2="11" y2="11" />
            <line x1="11" y1="11" x2="9" y2="5" />
            <line x1="11" y1="11" x2="17" y2="7" />
            <line x1="5" y1="19" x2="14" y2="20" />
            <line x1="14" y1="20" x2="18" y2="22" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#1A1A1A" stroke="none" />
            <circle cx="9" cy="5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="7" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="14" cy="20" r={leafRadius * 1.1} fill="#1A1A1A" stroke="none" />
            <circle cx="18" cy="22" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W16 · V2</div>
        <h3>BL · Editorial Duo</h3>
        <p class="caption">
          Pulsar noir BL ancré, leaves+lune indigo. Composition asymétrique nette.
        </p>
      </div>

      <!-- W17 — V4 TL · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="5" x2="13" y2="11" />
            <line x1="13" y1="11" x2="13" y2="18" />
            <line x1="13" y1="11" x2="20" y2="14" />
            <line x1="5" y1="5" x2="14" y2="3" />
            <line x1="14" y1="3" x2="20" y2="2" />
            <circle cx="5" cy="5" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
            <circle cx="13" cy="18" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="20" cy="14" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="14" cy="3" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20" cy="2" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W17 · V4</div>
        <h3>TL · Editorial Indigo</h3>
        <p class="caption">Pulsar coin NO. Mono indigo, lecture haut-vers-bas.</p>
      </div>

      <!-- W18 — V4 TL · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="5" x2="13" y2="11" />
            <line x1="13" y1="11" x2="13" y2="18" />
            <line x1="13" y1="11" x2="20" y2="14" />
            <line x1="5" y1="5" x2="14" y2="3" />
            <line x1="14" y1="3" x2="20" y2="2" />
            <circle cx="5" cy="5" r={centerRadius * 1.05} fill="#1A1A1A" stroke="none" />
            <circle cx="13" cy="18" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="20" cy="14" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="14" cy="3" r={leafRadius * 1.1} fill="#1A1A1A" stroke="none" />
            <circle cx="20" cy="2" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W18 · V4</div>
        <h3>TL · Editorial Duo</h3>
        <p class="caption">Pulsar noir coin NO + accents indigo. Format presse / éditorial.</p>
      </div>

      <!-- W19 — V11 + V18 z-layered · Editorial Indigo (top-3 personnelle) -->
      <div class="card highlight">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
            <circle
              cx="18"
              cy="18"
              r={leafRadius * 1.2}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.1}
            />
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.65}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.7}
            />
          </svg>
        </div>
        <div class="num">W19 · V11+V18 ⭐</div>
        <h3>V11 z-layered · Indigo</h3>
        <p class="caption">
          Constellation+lune avec stroke-fond autour de chaque sphère → 3D plat élégant.
        </p>
      </div>

      <!-- W20 — V11 + V18 · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
            <circle
              cx="18"
              cy="18"
              r={leafRadius * 1.2}
              fill="#1A1A1A"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.1}
            />
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.65}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.7}
            />
          </svg>
        </div>
        <div class="num">W20 · V11+V18</div>
        <h3>V11 z-layered · Duo</h3>
        <p class="caption">Z-layered en bichromie. Pulsar noir ancré, satellites bleus pop.</p>
      </div>

      <!-- W21 — V12 + V18 · Editorial Duo (minimalisme 3D) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle
              cx="18"
              cy="18"
              r={leafRadius * 1.3}
              fill="#1A1A1A"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.2}
            />
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.7}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.8}
            />
          </svg>
        </div>
        <div class="num">W21 · V12+V18</div>
        <h3>V12 z-layered · Duo</h3>
        <p class="caption">
          Lune solo z-layered. Trois plans visuels distincts, lecture immédiate.
        </p>
      </div>

      <!-- W22 — V10 + V18 · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle
              cx="4"
              cy="2.5"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            <circle
              cx="9.5"
              cy="1.5"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
          </svg>
        </div>
        <div class="num">W22 · V10+V18</div>
        <h3>V10 z-layered · Indigo</h3>
        <p class="caption">Constellation + Y-fork en z-layered. Tous les nœuds détachés du fond.</p>
      </div>

      <!-- W23 — V11 + drop shadow · Editorial Indigo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="w23-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.4"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#w23-shadow)">
              {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="18" y2="18" />
              <line x1="18" y1="18" x2="20.5" y2="20.5" />
              <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
              {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
                <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              {/each}
              <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
              <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            </g>
          </svg>
        </div>
        <div class="num">W23 · effet drop-shadow</div>
        <h3>V11 + soft shadow</h3>
        <p class="caption">
          Ombre douce sous chaque élément. Sensation de matérialité, papier-collé.
        </p>
      </div>

      <!-- W24 — V11 + drop shadow · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="w24-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.4"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#w24-shadow)">
              {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="18" y2="18" />
              <line x1="18" y1="18" x2="20.5" y2="20.5" />
              <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
              {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
                <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              {/each}
              <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#1A1A1A" stroke="none" />
              <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            </g>
          </svg>
        </div>
        <div class="num">W24 · effet drop-shadow</div>
        <h3>V11 + shadow · Duo</h3>
        <p class="caption">Ombre douce + bichromie. Editorial press style.</p>
      </div>

      <!-- W25 — V1 + variable line weight · Indigo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" stroke-width={strokeWidth * 1.7} />
            <line x1="7" y1="5" x2="4" y2="2.5" stroke-width={strokeWidth * 0.8} />
            <line x1="7" y1="5" x2="9.5" y2="1.5" stroke-width={strokeWidth * 0.8} />
            <line x1="12" y1="12" x2="18" y2="18" stroke-width={strokeWidth * 1.7} />
            <line x1="18" y1="18" x2="20.5" y2="20.5" stroke-width={strokeWidth * 0.8} />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W25 · effet line-weight</div>
        <h3>V1 · variable weight</h3>
        <p class="caption">
          Traits épais près du pulsar, fins vers les feuilles. Hiérarchie subtile.
        </p>
      </div>

      <!-- W26 — V11 + variable weight · Astronomical -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#3454D1"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} stroke-width={strokeWidth * 1.4} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" stroke-width={strokeWidth * 1.6} />
            <line x1="18" y1="18" x2="20.5" y2="20.5" stroke-width={strokeWidth * 0.7} />
            <circle cx="12" cy="12" r={centerRadius} fill="#3454D1" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#F4A261" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#3454D1" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#F4A261" stroke="none" />
          </svg>
        </div>
        <div class="num">W26 · line-weight + Astro</div>
        <h3>V11 · weight + astro</h3>
        <p class="caption">Hiérarchie épaisseur + bi-chromie astronomique. Riche sans saturer.</p>
      </div>

      <!-- W27 — V12 + dashed lines · Duo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-dasharray="1.6 1.2"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#1A1A1A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W27 · effet dashed</div>
        <h3>V12 dashed · Duo</h3>
        <p class="caption">Lignes pointillées : suggère « lien probable », « citation inférée ».</p>
      </div>

      <!-- W28 — V11 + dashed · Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-dasharray="1.6 1.2"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W28 · effet dashed</div>
        <h3>V11 dashed · Indigo</h3>
        <p class="caption">Toutes les connexions pointillées. Plus léger, aérien.</p>
      </div>

      <!-- W29 — V12 + diffraction X-spikes · Indigo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <line
              x1="12"
              y1="7"
              x2="12"
              y2="17"
              stroke-width={strokeWidth * 0.5}
              stroke-opacity="0.8"
            />
            <line
              x1="7"
              y1="12"
              x2="17"
              y2="12"
              stroke-width={strokeWidth * 0.5}
              stroke-opacity="0.8"
            />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W29 · effet X-spikes</div>
        <h3>V12 + diffraction</h3>
        <p class="caption">Pulsar avec 4 petits spikes (X). Étoile lointaine, télescope astro.</p>
      </div>

      <!-- W30 — V11 + diffraction X-spikes · Astronomical -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#3454D1"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <line
              x1="12"
              y1="6"
              x2="12"
              y2="18"
              stroke="#F4A261"
              stroke-width={strokeWidth * 0.5}
              stroke-opacity="0.9"
            />
            <line
              x1="6"
              y1="12"
              x2="18"
              y2="12"
              stroke="#F4A261"
              stroke-width={strokeWidth * 0.5}
              stroke-opacity="0.9"
            />
            <circle cx="12" cy="12" r={centerRadius} fill="#3454D1" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#F4A261" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#3454D1" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#F4A261" stroke="none" />
          </svg>
        </div>
        <div class="num">W30 · X-spikes + Astro</div>
        <h3>V11 + X-spikes ambrés</h3>
        <p class="caption">Spikes en ambre sur pulsar indigo. Lecture stellaire pleine.</p>
      </div>

      <!-- W31 — V12 + orbital ring · Editorial Duo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <ellipse
              cx="18"
              cy="18"
              rx={leafRadius * 2.6}
              ry={leafRadius * 1.4}
              transform="rotate(45 18 18)"
              stroke="#4A6CF7"
              stroke-width={strokeWidth * 0.5}
              fill="none"
              stroke-dasharray="1.2 0.8"
            />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#1A1A1A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W31 · effet orbital ring</div>
        <h3>V12 + ring orbital</h3>
        <p class="caption">
          Ellipse pointillée autour du parent : l'orbite de la lune matérialisée.
        </p>
      </div>

      <!-- W32 — V11 + orbital rings autour du pulsar · Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle
              cx="12"
              cy="12"
              r="9"
              stroke="#4A6CF7"
              stroke-width={strokeWidth * 0.3}
              stroke-opacity="0.4"
              stroke-dasharray="0.8 0.8"
              fill="none"
            />
            <circle
              cx="12"
              cy="12"
              r="6.2"
              stroke="#4A6CF7"
              stroke-width={strokeWidth * 0.3}
              stroke-opacity="0.4"
              stroke-dasharray="0.8 0.8"
              fill="none"
            />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W32 · orbital rings</div>
        <h3>V11 + orbites concentriques</h3>
        <p class="caption">Deux cercles pointillés très fins : les orbites des satellites.</p>
      </div>

      <!-- W33 — V12 + hollow parent · Indigo (effet NOUVEAU : mix filled/hollow) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle
              cx="18"
              cy="18"
              r={leafRadius * 1.25}
              fill="#fafbfc"
              stroke="#4A6CF7"
              stroke-width={strokeWidth * 1.3}
            />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W33 · effet hollow</div>
        <h3>V12 · parent hollow</h3>
        <p class="caption">
          Le parent est un anneau, pulsar et lune pleins. Plans visuels différenciés.
        </p>
      </div>

      <!-- W34 — V11 + regular nodes hollow · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1A1A1A" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#fafbfc"
                stroke="#1A1A1A"
                stroke-width={strokeWidth}
              />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#1A1A1A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W34 · effet hollow mix</div>
        <h3>V11 · réguliers hollow</h3>
        <p class="caption">Réguliers en anneaux noirs, pulsar+parent pleins. Hiérarchie 3 plans.</p>
      </div>

      <!-- W35 — V11 + gradient on lines · Hero Echo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <linearGradient
                id="w35-line-1"
                x1="12"
                y1="12"
                x2="5"
                y2="6"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#5B7FFF" />
                <stop offset="100%" stop-color="#52E0C4" />
              </linearGradient>
              <linearGradient
                id="w35-line-2"
                x1="12"
                y1="12"
                x2="19"
                y2="4"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#5B7FFF" />
                <stop offset="100%" stop-color="#F87171" />
              </linearGradient>
              <linearGradient
                id="w35-line-3"
                x1="12"
                y1="12"
                x2="4"
                y2="16"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#5B7FFF" />
                <stop offset="100%" stop-color="#FCD34D" />
              </linearGradient>
              <linearGradient
                id="w35-line-4"
                x1="12"
                y1="12"
                x2="18"
                y2="18"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#5B7FFF" />
                <stop offset="100%" stop-color="#6EE7B7" />
              </linearGradient>
            </defs>
            <line x1="12" y1="12" x2="5" y2="6" stroke="url(#w35-line-1)" />
            <line x1="12" y1="12" x2="19" y2="4" stroke="url(#w35-line-2)" />
            <line x1="12" y1="12" x2="4" y2="16" stroke="url(#w35-line-3)" />
            <line x1="12" y1="12" x2="18" y2="18" stroke="url(#w35-line-4)" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" stroke="#C4B5FD" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            <circle cx="5" cy="6" r={leafRadius * 0.85} fill="#52E0C4" stroke="none" />
            <circle cx="19" cy="4" r={leafRadius * 0.85} fill="#F87171" stroke="none" />
            <circle cx="4" cy="16" r={leafRadius * 0.85} fill="#FCD34D" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#6EE7B7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#C4B5FD" stroke="none" />
          </svg>
        </div>
        <div class="num">W35 · effet gradient lines</div>
        <h3>V11 · gradient lines Hero</h3>
        <p class="caption">
          Chaque ligne transitionne du bleu pulsar à la couleur de sa feuille. Spectacle.
        </p>
      </div>

      <!-- W36 — V12 + gradient line · Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <linearGradient
                id="w36-line"
                x1="12"
                y1="12"
                x2="20.5"
                y2="20.5"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#A0B0E8" />
              </linearGradient>
            </defs>
            <line x1="12" y1="12" x2="20.5" y2="20.5" stroke="url(#w36-line)" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#A0B0E8" stroke="none" />
          </svg>
        </div>
        <div class="num">W36 · gradient line solo</div>
        <h3>V12 · gradient fade</h3>
        <p class="caption">Une seule ligne en gradient : densité bleue qui décroît vers la lune.</p>
      </div>

      <!-- W37 — V12 + frosted blur backdrop · Hero echo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="w37-blur" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="2.5" />
              </filter>
            </defs>
            <circle
              cx="12"
              cy="12"
              r="6"
              fill="#5B7FFF"
              fill-opacity="0.4"
              filter="url(#w37-blur)"
            />
            <line x1="12" y1="12" x2="18" y2="18" stroke="#FFFFFF" stroke-opacity="0.6" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" stroke="#FFFFFF" stroke-opacity="0.6" />
            <circle cx="12" cy="12" r={centerRadius * 1.15} fill="#FFFFFF" stroke="none" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#6EE7B7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#C4B5FD" stroke="none" />
          </svg>
        </div>
        <div class="num">W37 · effet frosted blur</div>
        <h3>V12 · backdrop blur</h3>
        <p class="caption">
          Halo flouté derrière le pulsar (filter blur). 3D atmosphérique premium.
        </p>
      </div>

      <!-- W38 — V11 + multi-stroke parallel · Indigo (effet NOUVEAU) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ a: { x: 5, y: 6 }, b: { x: 12, y: 12 } }, { a: { x: 19, y: 4 }, b: { x: 12, y: 12 } }, { a: { x: 4, y: 16 }, b: { x: 12, y: 12 } }, { a: { x: 12, y: 12 }, b: { x: 18, y: 18 } }, { a: { x: 18, y: 18 }, b: { x: 20.5, y: 20.5 } }] as ln, i (i)}
              <line
                x1={ln.a.x}
                y1={ln.a.y}
                x2={ln.b.x}
                y2={ln.b.y}
                stroke-width={strokeWidth * 2.4}
              />
              <line
                x1={ln.a.x}
                y1={ln.a.y}
                x2={ln.b.x}
                y2={ln.b.y}
                stroke="#fafbfc"
                stroke-width={strokeWidth * 1.1}
              />
            {/each}
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">W38 · effet multi-stroke</div>
        <h3>V11 · lignes doubles</h3>
        <p class="caption">Lignes en double trait (creux au milieu). Métro-cartographique.</p>
      </div>

      <!-- W39 — V12 · Manuscript Sepia (palette NOUVELLE) -->
      <div class="card">
        <div class="canvas" style="background: #f5ead0">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#5C4033"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5C4033" stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill="#8B4513" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill="#D2B48C" stroke="none" />
          </svg>
        </div>
        <div class="num">W39 · Manuscript Sepia</div>
        <h3>V12 · Parchemin</h3>
        <p class="caption">
          Bruns sépia sur fond parchemin. Direction archives anciennes / scriptorium.
        </p>
      </div>

      <!-- W40 — V11 + V18 + drop shadow + Hero Echo : combinatoire maximaliste -->
      <div class="card">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="w40-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.5"
                  stdDeviation="0.4"
                  flood-color="#000"
                  flood-opacity="0.55"
                />
              </filter>
            </defs>
            <g filter="url(#w40-shadow)">
              {#each [{ x: 5, y: 6, c: '#52E0C4' }, { x: 19, y: 4, c: '#F87171' }, { x: 4, y: 16, c: '#FCD34D' }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="18" y2="18" />
              <line x1="18" y1="18" x2="20.5" y2="20.5" />
              <circle cx="12" cy="12" r={centerRadius * 1.1} fill="#FFFFFF" stroke="none" />
              <circle
                cx="12"
                cy="12"
                r={centerRadius}
                fill="#5B7FFF"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.8}
              />
              {#each [{ x: 5, y: 6, c: '#52E0C4' }, { x: 19, y: 4, c: '#F87171' }, { x: 4, y: 16, c: '#FCD34D' }] as p, i (i)}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={leafRadius * 0.95}
                  fill={p.c}
                  stroke="#0d0d12"
                  stroke-width={strokeWidth * 0.7}
                />
              {/each}
              <circle
                cx="18"
                cy="18"
                r={leafRadius * 1.2}
                fill="#6EE7B7"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.9}
              />
              <circle
                cx="20.5"
                cy="20.5"
                r={leafRadius * 0.65}
                fill="#C4B5FD"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.6}
              />
            </g>
          </svg>
        </div>
        <div class="num">W40 · combo maximal</div>
        <h3>V11 + V18 + shadow + Hero</h3>
        <p class="caption">
          Z-layered + drop shadow + palette hero complète. La version « hero of hero ».
        </p>
      </div>
    </div>
  </section>

  <section class="section-block">
    <h2 class="section-title">
      Mixes W22 + W23 + W15 · 2026-05-28 <span class="ref-tag">8 propositions</span>
    </h2>
    <p class="section-lead">
      Croisements ciblés des trois ingrédients <strong>W15</strong> (placement BL / coin SO),
      <strong>W22</strong> (V10 z-layered) et <strong>W23</strong> (V11 + drop-shadow). Couleur fixée
      principalement Editorial Indigo ; deux variantes en Editorial Duo pour donner du contraste de marque.
    </p>
    <div class="grid grid--dense">
      <!-- X01 — V11 BL + z-layered + drop-shadow · Editorial Indigo (TRIPLE COMBO) -->
      <div class="card highlight">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="x01-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.45"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#x01-shadow)">
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <line x1="5" y1="19" x2={p.x} y2={p.y} />
              {/each}
              <line x1="5" y1="19" x2="14" y2="20" />
              <line x1="14" y1="20" x2="18" y2="22" />
              <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={leafRadius * 0.95}
                  fill="#4A6CF7"
                  stroke="#fafbfc"
                  stroke-width={strokeWidth * 0.9}
                />
              {/each}
              <circle
                cx="14"
                cy="20"
                r={leafRadius * 1.2}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 1.1}
              />
              <circle
                cx="18"
                cy="22"
                r={leafRadius * 0.65}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.7}
              />
            </g>
          </svg>
        </div>
        <div class="num">X01 · W15+W22+W23 ⭐</div>
        <h3>V11 BL · z-layered · shadow</h3>
        <p class="caption">
          Triple combo : placement BL + z-layered + drop-shadow. Mono indigo, sophistication
          maximum.
        </p>
      </div>

      <!-- X02 — V11 BL + drop-shadow · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="x02-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.4"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#x02-shadow)">
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <line x1="5" y1="19" x2={p.x} y2={p.y} />
              {/each}
              <line x1="5" y1="19" x2="14" y2="20" />
              <line x1="14" y1="20" x2="18" y2="22" />
              <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              {/each}
              <circle cx="14" cy="20" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
              <circle cx="18" cy="22" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            </g>
          </svg>
        </div>
        <div class="num">X02 · W15+W23</div>
        <h3>V11 BL · shadow only</h3>
        <p class="caption">Placement BL + ombre douce. Plus organique, sans z-layered.</p>
      </div>

      <!-- X03 — V11 BL + z-layered · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
              <line x1="5" y1="19" x2={p.x} y2={p.y} />
            {/each}
            <line x1="5" y1="19" x2="14" y2="20" />
            <line x1="14" y1="20" x2="18" y2="22" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
            <circle
              cx="14"
              cy="20"
              r={leafRadius * 1.2}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.1}
            />
            <circle
              cx="18"
              cy="22"
              r={leafRadius * 0.65}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.7}
            />
          </svg>
        </div>
        <div class="num">X03 · W15+W22</div>
        <h3>V11 BL · z-layered only</h3>
        <p class="caption">Placement BL + z-layered. Sans shadow → plus net, plus graphique.</p>
      </div>

      <!-- X04 — V10 BL + z-layered · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
              <line x1="5" y1="19" x2={p.x} y2={p.y} />
            {/each}
            <line x1="5" y1="19" x2="11" y2="11" />
            <line x1="11" y1="11" x2="9" y2="4" />
            <line x1="11" y1="11" x2="16" y2="5" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
            <circle
              cx="9"
              cy="4"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            <circle
              cx="16"
              cy="5"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
          </svg>
        </div>
        <div class="num">X04 · W15+W22 (V10)</div>
        <h3>V10 BL · z-layered</h3>
        <p class="caption">
          V10 (constellation + Y-fork) en BL, tout z-layered. Composition dense.
        </p>
      </div>

      <!-- X05 — V10 BL + drop-shadow · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="x05-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.4"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#x05-shadow)">
              {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
                <line x1="5" y1="19" x2={p.x} y2={p.y} />
              {/each}
              <line x1="5" y1="19" x2="11" y2="11" />
              <line x1="11" y1="11" x2="9" y2="4" />
              <line x1="11" y1="11" x2="16" y2="5" />
              <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
              <circle cx="9" cy="4" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              <circle cx="16" cy="5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
                <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              {/each}
            </g>
          </svg>
        </div>
        <div class="num">X05 · W15+W23 (V10)</div>
        <h3>V10 BL · shadow</h3>
        <p class="caption">V10 en BL avec drop-shadow uniquement. Lecture organique.</p>
      </div>

      <!-- X06 — V10 BL + z-layered + drop-shadow · Editorial Indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="x06-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.45"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#x06-shadow)">
              {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
                <line x1="5" y1="19" x2={p.x} y2={p.y} />
              {/each}
              <line x1="5" y1="19" x2="11" y2="11" />
              <line x1="11" y1="11" x2="9" y2="4" />
              <line x1="11" y1="11" x2="16" y2="5" />
              <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#4A6CF7" stroke="none" />
              <circle
                cx="9"
                cy="4"
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
              <circle
                cx="16"
                cy="5"
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
              {#each [{ x: 19, y: 3 }, { x: 22, y: 13 }, { x: 4, y: 11 }] as p, i (i)}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={leafRadius * 0.95}
                  fill="#4A6CF7"
                  stroke="#fafbfc"
                  stroke-width={strokeWidth * 0.9}
                />
              {/each}
            </g>
          </svg>
        </div>
        <div class="num">X06 · W15+W22+W23 (V10)</div>
        <h3>V10 BL · z + shadow</h3>
        <p class="caption">
          V10 triple combo. 3 sources + Y-fork en BL avec les deux effets cumulés.
        </p>
      </div>

      <!-- X07 — V11 BL + z-layered + drop-shadow · Editorial Duo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="x07-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.6"
                  stdDeviation="0.45"
                  flood-color="#1A1A1A"
                  flood-opacity="0.25"
                />
              </filter>
            </defs>
            <g filter="url(#x07-shadow)">
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <line x1="5" y1="19" x2={p.x} y2={p.y} />
              {/each}
              <line x1="5" y1="19" x2="14" y2="20" />
              <line x1="14" y1="20" x2="18" y2="22" />
              <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#1A1A1A" stroke="none" />
              {#each [{ x: 10, y: 4 }, { x: 19, y: 3 }, { x: 4, y: 11 }] as p, i (i)}
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={leafRadius * 0.95}
                  fill="#4A6CF7"
                  stroke="#fafbfc"
                  stroke-width={strokeWidth * 0.9}
                />
              {/each}
              <circle
                cx="14"
                cy="20"
                r={leafRadius * 1.2}
                fill="#1A1A1A"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 1.1}
              />
              <circle
                cx="18"
                cy="22"
                r={leafRadius * 0.65}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.7}
              />
            </g>
          </svg>
        </div>
        <div class="num">X07 · triple combo · Duo</div>
        <h3>V11 BL · z + shadow · Duo</h3>
        <p class="caption">Triple combo en bi-chromie : pulsar+parent noirs, satellites bleus.</p>
      </div>

      <!-- X08 — V10+V11 hybride BL + z-layered · Editorial Duo (topologie complète) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#1A1A1A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 4, y: 11 }, { x: 22, y: 13 }] as p, i (i)}
              <line x1="5" y1="19" x2={p.x} y2={p.y} />
            {/each}
            <line x1="5" y1="19" x2="11" y2="11" />
            <line x1="11" y1="11" x2="9" y2="4" />
            <line x1="11" y1="11" x2="17" y2="5" />
            <line x1="5" y1="19" x2="14" y2="20" />
            <line x1="14" y1="20" x2="18" y2="22" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill="#1A1A1A" stroke="none" />
            <circle
              cx="9"
              cy="4"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            <circle
              cx="17"
              cy="5"
              r={leafRadius * 0.95}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.9}
            />
            {#each [{ x: 4, y: 11 }, { x: 22, y: 13 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#1A1A1A"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
            <circle
              cx="14"
              cy="20"
              r={leafRadius * 1.2}
              fill="#1A1A1A"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.1}
            />
            <circle
              cx="18"
              cy="22"
              r={leafRadius * 0.65}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.7}
            />
          </svg>
        </div>
        <div class="num">X08 · V10+V11+V18 BL · Duo</div>
        <h3>Topologie complète BL · Duo</h3>
        <p class="caption">
          2 sources directes + Y-fork + parent-lune, BL z-layered bi-chromie. Narration produit
          complète.
        </p>
      </div>
    </div>
  </section>

  <section class="section-block">
    <h2 class="section-title">Pulsar-graph — 20 variations · 2026-05-28</h2>
    <p class="section-lead">
      Vingt déclinaisons du mark <strong>#01 (Pulsar-graph)</strong>. Système de couleurs étendu :
      chaque élément topologique (pulsar, twins du Y-fork, parent, lune, halo, fond) est
      indépendamment colorable via le panneau en bas à droite. Variations couvertes : placement du
      pulsar (centré, coins, bord), niveau de sophistication (minimal plat, halo, gradient radial,
      chromosphère, z-layered 3D), topologie (Y-fork seul, lune seule, multi-Y-fork, bilatéral,
      constellation, hybrides), et un lockup mark+wordmark.
    </p>
    <div class="grid grid--dense">
      <!-- V01 — Centré classique -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V01</div>
        <h3>Centré · classique</h3>
        <p class="caption">
          Pulsar centré, Y-fork NW, parent-lune SE. Lecture canonique du graphe.
        </p>
      </div>

      <!-- V02 — Bottom-left compact -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="19" x2="11" y2="11" />
            <line x1="11" y1="11" x2="9" y2="5" />
            <line x1="11" y1="11" x2="17" y2="7" />
            <line x1="5" y1="19" x2="14" y2="20" />
            <line x1="14" y1="20" x2="18" y2="22" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill={pulsarColor} stroke="none" />
            <circle cx="9" cy="5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="17" cy="7" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="14" cy="20" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="18" cy="22" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V02</div>
        <h3>Bottom-left</h3>
        <p class="caption">Pulsar ancré au coin SO. Y-fork qui s'élève en diagonale NE.</p>
      </div>

      <!-- V03 — Top-right -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="19" y1="5" x2="13" y2="13" />
            <line x1="13" y1="13" x2="15" y2="19" />
            <line x1="13" y1="13" x2="7" y2="17" />
            <line x1="19" y1="5" x2="10" y2="4" />
            <line x1="10" y1="4" x2="6" y2="2" />
            <circle cx="19" cy="5" r={centerRadius * 1.05} fill={pulsarColor} stroke="none" />
            <circle cx="15" cy="19" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="7" cy="17" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="10" cy="4" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="6" cy="2" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V03</div>
        <h3>Top-right</h3>
        <p class="caption">Pulsar coin NE. Mêmes éléments en orientation inverse — versatile.</p>
      </div>

      <!-- V04 — Top-left -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="5" x2="13" y2="11" />
            <line x1="13" y1="11" x2="13" y2="18" />
            <line x1="13" y1="11" x2="20" y2="14" />
            <line x1="5" y1="5" x2="14" y2="3" />
            <line x1="14" y1="3" x2="20" y2="2" />
            <circle cx="5" cy="5" r={centerRadius * 1.05} fill={pulsarColor} stroke="none" />
            <circle cx="13" cy="18" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="20" cy="14" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="14" cy="3" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20" cy="2" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V04</div>
        <h3>Top-left</h3>
        <p class="caption">Pulsar coin NO. Y-fork descend en SE, parent file vers E.</p>
      </div>

      <!-- V05 — Bottom-right -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="19" y1="19" x2="13" y2="13" />
            <line x1="13" y1="13" x2="7" y2="14" />
            <line x1="13" y1="13" x2="9" y2="6" />
            <line x1="19" y1="19" x2="10" y2="20" />
            <line x1="10" y1="20" x2="5" y2="22" />
            <circle cx="19" cy="19" r={centerRadius * 1.05} fill={pulsarColor} stroke="none" />
            <circle cx="7" cy="14" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9" cy="6" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="10" cy="20" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="5" cy="22" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V05</div>
        <h3>Bottom-right</h3>
        <p class="caption">Pulsar coin SE, ouverture vers le NO. Composition asymétrique stable.</p>
      </div>

      <!-- V06 — Halo (3D léger) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <!-- Halo translucide autour du pulsar (effet 3D) -->
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 2.4}
              fill={haloColor}
              fill-opacity="0.18"
              stroke="none"
            />
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 1.6}
              fill={haloColor}
              fill-opacity="0.28"
              stroke="none"
            />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V06</div>
        <h3>Halo (3D léger)</h3>
        <p class="caption">
          Deux couches halo translucide autour du pulsar — sensation de profondeur sans gradient.
        </p>
      </div>

      <!-- V07 — Gradient radial (3D sphère) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <radialGradient id="v07-pulsar" cx="40%" cy="40%" r="60%">
                <stop offset="0%" stop-color="white" stop-opacity="0.85" />
                <stop offset="40%" stop-color={pulsarColor} />
                <stop offset="100%" stop-color={pulsarColor} stop-opacity="0.55" />
              </radialGradient>
            </defs>
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius * 1.15} fill="url(#v07-pulsar)" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V07</div>
        <h3>Gradient radial</h3>
        <p class="caption">
          Pulsar rendu comme une sphère par gradient radial (highlight, mid, falloff). 3D plat-2.5D.
        </p>
      </div>

      <!-- V08 — Chromosphère ring (3D type étoile) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <!-- Anneau chromosphère extérieur (très fin, couleur halo) -->
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 1.4}
              fill="none"
              stroke={haloColor}
              stroke-width={strokeWidth * 0.4}
              stroke-opacity="0.7"
            />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V08</div>
        <h3>Chromosphère</h3>
        <p class="caption">
          Pulsar + anneau chromosphère fin (lecture « étoile »). Reprend l'effet du hero pulsar.
        </p>
      </div>

      <!-- V09 — Constellation pure -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 21, y: 13 }, { x: 17, y: 21 }, { x: 5, y: 19 }, { x: 3, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">V09</div>
        <h3>Constellation (6 nœuds)</h3>
        <p class="caption">
          Pulsar + 6 nœuds réguliers en orbite. Pas de lune ni Y-fork, lecture plus « étoile +
          planètes ».
        </p>
      </div>

      <!-- V10 — Constellation + Y-fork accent -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- 3 nœuds réguliers -->
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <!-- Y-fork (NW) -->
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            {#each [{ x: 19, y: 13 }, { x: 17, y: 21 }, { x: 4, y: 14 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">V10</div>
        <h3>Constellation + Y-fork</h3>
        <p class="caption">
          3 sources directes + un Y-fork (deux sources liées). Représente une mini-bibliographie
          hybride.
        </p>
      </div>

      <!-- V11 — Constellation + lune -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            {#each [{ x: 5, y: 6 }, { x: 19, y: 4 }, { x: 4, y: 16 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V11</div>
        <h3>Constellation + lune</h3>
        <p class="caption">
          3 sources directes + un parent-lune. Le système parent-lune raconte « une source citant
          une autre ».
        </p>
      </div>

      <!-- V12 — Lune seule, sober -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.2} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.6} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V12</div>
        <h3>Lune seule</h3>
        <p class="caption">
          Pulsar + un parent + sa lune. Mark minimal qui raconte juste « une source citée par une
          autre ».
        </p>
      </div>

      <!-- V13 — Y-fork seul, dramatique -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="20" x2="12" y2="11" />
            <line x1="12" y1="11" x2="6" y2="4" />
            <line x1="12" y1="11" x2="18" y2="4" />
            <circle cx="12" cy="20" r={centerRadius * 1.1} fill={pulsarColor} stroke="none" />
            <circle cx="6" cy="4" r={leafRadius * 1} fill={twinColor} stroke="none" />
            <circle cx="18" cy="4" r={leafRadius * 1} fill={twinColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V13</div>
        <h3>Y-fork pur</h3>
        <p class="caption">
          Pulsar en bas + grand Y-fork symétrique. La fourchette de citation comme métaphore unique.
        </p>
      </div>

      <!-- V14 — Double Y-fork -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- Y-fork NO -->
            <line x1="12" y1="12" x2="7" y2="6" />
            <line x1="7" y1="6" x2="4" y2="3" />
            <line x1="7" y1="6" x2="9" y2="2" />
            <!-- Y-fork SE -->
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20" y2="21" />
            <line x1="17" y1="18" x2="15" y2="22" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="3" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="20" cy="21" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="15" cy="22" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V14</div>
        <h3>Double Y-fork</h3>
        <p class="caption">
          Pulsar central + deux Y-forks diamétralement opposés. Deux paires citées, symétrie en
          miroir.
        </p>
      </div>

      <!-- V15 — Double lune -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="6" y2="6" />
            <line x1="6" y1="6" x2="3" y2="4" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="21" y2="20" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="6" cy="6" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="3" cy="4" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="21" cy="20" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V15</div>
        <h3>Double lune</h3>
        <p class="caption">
          Deux systèmes parent-lune symétriques. Évoque deux chaînes de citation distinctes.
        </p>
      </div>

      <!-- V16 — Compose diagonal (BL + TR) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="5" y1="19" x2="13" y2="11" />
            <line x1="13" y1="11" x2="19" y2="6" />
            <line x1="19" y1="6" x2="22" y2="2" />
            <line x1="19" y1="6" x2="16" y2="2" />
            <line x1="13" y1="11" x2="9" y2="14" />
            <line x1="9" y1="14" x2="6" y2="15" />
            <circle cx="5" cy="19" r={centerRadius * 1.05} fill={pulsarColor} stroke="none" />
            <circle cx="22" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="16" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9" cy="14" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="6" cy="15" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V16</div>
        <h3>Compose diagonale</h3>
        <p class="caption">Pulsar BL, Y-fork TR. Axe diagonal lisible immédiatement, dynamique.</p>
      </div>

      <!-- V17 — Outlined pulsar (no fill) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <!-- Pulsar = ring, pas filled -->
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 1.15}
              fill={canvasBg}
              stroke={pulsarColor}
              stroke-width={strokeWidth * 1.4}
            />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V17</div>
        <h3>Pulsar évidé</h3>
        <p class="caption">Pulsar = anneau (pas filled). Plus architectural, contraste inversé.</p>
      </div>

      <!-- V18 — Z-layered (3D overlap) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- Lignes en arrière-plan -->
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <!-- Pulsar -->
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <!-- Parent — outlined avec couleur du fond pour fake depth -->
            <circle
              cx="18"
              cy="18"
              r={leafRadius * 1.3}
              fill={parentColor}
              stroke={canvasBg}
              stroke-width={strokeWidth * 1.2}
            />
            <!-- Lune par-dessus le parent -->
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.65}
              fill={luneColor}
              stroke={canvasBg}
              stroke-width={strokeWidth * 0.8}
            />
            <!-- Twins avec stroke -->
            <circle
              cx="4"
              cy="2.5"
              r={leafRadius * 0.95}
              fill={twinColor}
              stroke={canvasBg}
              stroke-width={strokeWidth * 0.8}
            />
            <circle
              cx="9.5"
              cy="1.5"
              r={leafRadius * 0.95}
              fill={twinColor}
              stroke={canvasBg}
              stroke-width={strokeWidth * 0.8}
            />
          </svg>
        </div>
        <div class="num">V18</div>
        <h3>Z-layered (3D overlap)</h3>
        <p class="caption">
          Stroke fond autour de chaque sphère → effet de profondeur, faux ordering 3D des plans.
        </p>
      </div>

      <!-- V19 — Mark + wordmark lockup -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 90 24"
            width={scale * 1.7}
            height={scale * 0.45}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            style="max-width: 100%; height: auto;"
          >
            <!-- Mark à gauche (pulsar-graph compact) -->
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
            <!-- Wordmark à droite -->
            <text
              x="30"
              y="16.5"
              fill={pulsarColor}
              stroke="none"
              font-family="'Source Serif 4', 'Crimson Pro', Georgia, serif"
              font-size="14"
              font-weight="500"
              font-style="italic"
              letter-spacing="0.5">filum</text
            >
          </svg>
        </div>
        <div class="num">V19</div>
        <h3>Mark + wordmark</h3>
        <p class="caption">
          Lockup horizontal : mark compact à gauche, « filum » en italique serif à droite. Format
          header.
        </p>
      </div>

      <!-- V20 — Symmetric chevron (bilateral) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- Bras gauche : Y-fork mirror -->
            <line x1="12" y1="18" x2="6" y2="11" />
            <line x1="6" y1="11" x2="3" y2="6" />
            <line x1="6" y1="11" x2="8" y2="4" />
            <!-- Bras droit : Y-fork mirror -->
            <line x1="12" y1="18" x2="18" y2="11" />
            <line x1="18" y1="11" x2="21" y2="6" />
            <line x1="18" y1="11" x2="16" y2="4" />
            <!-- Pulsar en bas -->
            <circle cx="12" cy="18" r={centerRadius * 1.1} fill={pulsarColor} stroke="none" />
            <!-- 4 twins -->
            <circle cx="3" cy="6" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="8" cy="4" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="21" cy="6" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="16" cy="4" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
          </svg>
        </div>
        <div class="num">V20</div>
        <h3>Chevron bilatéral</h3>
        <p class="caption">
          Pulsar bas-centre, deux Y-forks miroirs en éventail. Très symétrique, lecture héraldique.
        </p>
      </div>
    </div>
  </section>

  <section class="section-block">
    <h2 class="section-title">Mixes V09 × V10 × V11 — 5 hybrides topologiques · 2026-05-28</h2>
    <p class="section-lead">
      Cinq propositions qui combinent les trois topologies disponibles dans la grille précédente : <strong
        >V09</strong
      >
      (constellation 6 nœuds), <strong>V10</strong>
      (constellation + Y-fork), <strong>V11</strong> (constellation + parent-lune). Chaque mix raconte
      une bibliographie de structure différente. Couleurs paramétrables via le même panneau (pulsar, twins,
      parent, lune, fond) que les 20 variations.
    </p>
    <div class="grid grid--dense">
      <!-- Y01 — V10 + V11 : 2 régulières + Y-fork + parent-lune (canonique) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- 2 régulières -->
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <!-- Y-fork au-dessus -->
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <!-- Parent-lune en SE -->
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">Y01 · V10+V11</div>
        <h3>Canonique (toutes les topos)</h3>
        <p class="caption">
          2 sources directes + 1 Y-fork (paire citée) + 1 parent-lune (chaîne). Le récit produit
          complet en un mark.
        </p>
      </div>

      <!-- Y02 — V09 + V11 : 4 régulières + parent-lune (densité de sources directes) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 4, y: 5 }, { x: 20, y: 4 }, { x: 4, y: 19 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="16" y2="18" />
            <line x1="16" y1="18" x2="20" y2="21" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            {#each [{ x: 4, y: 5 }, { x: 20, y: 4 }, { x: 4, y: 19 }, { x: 21, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
            <circle cx="16" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20" cy="21" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">Y02 · V09+V11</div>
        <h3>Constellation dense + lune</h3>
        <p class="caption">
          4 sources directes (constellation pleine) + 1 chaîne parent-lune. Évoque une fiche bien
          sourcée avec un point d'attestation indirect.
        </p>
      </div>

      <!-- Y03 — V09 + V10 : 4 régulières + Y-fork (densité + paire citée) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }, { x: 4, y: 19 }, { x: 20, y: 19 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="12" y2="5" />
            <line x1="12" y1="5" x2="7" y2="2" />
            <line x1="12" y1="5" x2="17" y2="2" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="7" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="17" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }, { x: 4, y: 19 }, { x: 20, y: 19 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
          </svg>
        </div>
        <div class="num">Y03 · V09+V10</div>
        <h3>Constellation dense + Y-fork</h3>
        <p class="caption">
          4 sources directes + 1 Y-fork au-dessus (paire citée ensemble). Bibliographie dense avec
          une référence groupée saillante.
        </p>
      </div>

      <!-- Y04 — V09 + V10 + V11 : 3 régulières + Y-fork + parent-lune (maximaliste) -->
      <div class="card highlight">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 6 }, { x: 4, y: 19 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="12" y2="5" />
            <line x1="12" y1="5" x2="8" y2="1.5" />
            <line x1="12" y1="5" x2="16" y2="1.5" />
            <line x1="12" y1="12" x2="18" y2="18" />
            <line x1="18" y1="18" x2="21" y2="21" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="8" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="16" cy="1.5" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            {#each [{ x: 3, y: 12 }, { x: 21, y: 6 }, { x: 4, y: 19 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            {/each}
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="21" cy="21" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">Y04 · V09+V10+V11 ⭐</div>
        <h3>Maximaliste — 3 topos</h3>
        <p class="caption">
          3 sources directes + 1 Y-fork (paire citée) + 1 parent-lune (chaîne). Toutes les
          structures topologiques de Filum représentées en un seul mark. Le candidat le plus
          descriptif.
        </p>
      </div>

      <!-- Y05 — V10 × 2 + V11 : 2 Y-forks symétriques + parent-lune (citation-heavy) -->
      <div class="card">
        <div class="canvas" style="background: {canvasBg}">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <!-- Y-fork supérieur-gauche -->
            <line x1="12" y1="12" x2="7" y2="6" />
            <line x1="7" y1="6" x2="3" y2="3" />
            <line x1="7" y1="6" x2="9" y2="1" />
            <!-- Y-fork supérieur-droit -->
            <line x1="12" y1="12" x2="18" y2="7" />
            <line x1="18" y1="7" x2="22" y2="4" />
            <line x1="18" y1="7" x2="16" y2="2" />
            <!-- 1 régulière à gauche -->
            <line x1="12" y1="12" x2="3" y2="15" />
            <!-- Parent-lune en SE -->
            <line x1="12" y1="12" x2="17" y2="19" />
            <line x1="17" y1="19" x2="20" y2="22" />
            <circle cx="12" cy="12" r={centerRadius} fill={pulsarColor} stroke="none" />
            <circle cx="3" cy="3" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="9" cy="1" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="22" cy="4" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="16" cy="2" r={leafRadius * 0.85} fill={twinColor} stroke="none" />
            <circle cx="3" cy="15" r={leafRadius * 0.85} fill={accentColor} stroke="none" />
            <circle cx="17" cy="19" r={leafRadius * 1.1} fill={parentColor} stroke="none" />
            <circle cx="20" cy="22" r={leafRadius * 0.55} fill={luneColor} stroke="none" />
          </svg>
        </div>
        <div class="num">Y05 · V10×2 + V11</div>
        <h3>Citation-heavy (2 Y-forks + lune)</h3>
        <p class="caption">
          2 Y-forks symétriques en haut + 1 source directe + parent-lune en SE. Une bibliographie
          riche en citations groupées : deux paires + une chaîne.
        </p>
      </div>
    </div>
  </section>

  <section class="section-block">
    <h2 class="section-title">
      Y01 — 30 déclinaisons · 2026-05-28 <span class="ref-tag"
        >10 dispositions · 10 couleurs · 10 effets</span
      >
    </h2>
    <p class="section-lead">
      Trente versions du Y01 (canonique <strong>V10+V11</strong>) organisées en 3 batches :
      <strong>Z01-Z10</strong> dispositions de nœuds variées (avec un nœud en plus ou en moins),
      <strong>Z11-Z20</strong> meilleures combinaisons de couleurs (hero, palette auteur-kind réelle
      de la démo, sober editorial, dégradés), <strong>Z21-Z30</strong> designs moins classiques (effets
      3D, halo, pulsar évidé, wordmark, gradients, etc.).
    </p>

    <h3 class="section-subtitle">Batch A — Z01-Z10 · Dispositions de nœuds</h3>
    <div class="grid grid--dense">
      <!-- Z01 — Miroir vertical (Y-fork bas, parent-lune NE) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="19" />
            <line x1="7" y1="19" x2="4" y2="21.5" />
            <line x1="7" y1="19" x2="9.5" y2="22.5" />
            <line x1="12" y1="12" x2="17" y2="6" />
            <line x1="17" y1="6" x2="20.5" y2="3.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="21.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="22.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="17" cy="6" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="3.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z01</div>
        <h3>Miroir vertical</h3>
        <p class="caption">Y-fork en bas, parent-lune en NE. Lecture inversée du canonique.</p>
      </div>

      <!-- Z02 — Rotation 90° (réguliers haut/bas, Y-fork droite, lune SW) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 12, y: 3 }, { x: 12, y: 21 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="19" y2="7" />
            <line x1="19" y1="7" x2="22" y2="4" />
            <line x1="19" y1="7" x2="22.5" y2="9.5" />
            <line x1="12" y1="12" x2="6" y2="17" />
            <line x1="6" y1="17" x2="3.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="22" cy="4" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="22.5" cy="9.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 12, y: 3 }, { x: 12, y: 21 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="6" cy="17" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="3.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z02</div>
        <h3>Rotation 90° (axe vertical)</h3>
        <p class="caption">Réguliers haut/bas, Y-fork droite, parent-lune SW. Composition rotée.</p>
      </div>

      <!-- Z03 — Y01 - 1 régulier (5 nœuds) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="3" y2="12" />
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z03</div>
        <h3>Allégé (−1 régulier)</h3>
        <p class="caption">
          5 nœuds. Pulsar + 1 régulier W + Y-fork NE + parent-lune SE. Plus aéré.
        </p>
      </div>

      <!-- Z04 — Y01 + 1 régulier (7 nœuds) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }, { x: 12, y: 22 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }, { x: 12, y: 22 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z04</div>
        <h3>Dense (+1 régulier)</h3>
        <p class="caption">7 nœuds. Y01 + 1 régulier en S. Bibliographie plus fournie.</p>
      </div>

      <!-- Z05 — Parent-lune SW + Y-fork NE + 2 régulières -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 22, y: 13 }, { x: 4, y: 4 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="17" y2="5" />
            <line x1="17" y1="5" x2="20" y2="2" />
            <line x1="17" y1="5" x2="20.5" y2="8" />
            <line x1="12" y1="12" x2="7" y2="18" />
            <line x1="7" y1="18" x2="3.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="20" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="8" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 22, y: 13 }, { x: 4, y: 4 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="7" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="3.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z05</div>
        <h3>Pivoté (Y-fork NE, lune SW)</h3>
        <p class="caption">
          6 nœuds. Topologie Y01 mais Y-fork en haut-droite, parent-lune en bas-gauche.
        </p>
      </div>

      <!-- Z06 — Axe horizontal (Y-fork W, parent-lune E, réguliers N/S) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 12, y: 3 }, { x: 12, y: 21 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="5" y2="12" />
            <line x1="5" y1="12" x2="2" y2="9" />
            <line x1="5" y1="12" x2="2" y2="15" />
            <line x1="12" y1="12" x2="19" y2="14" />
            <line x1="19" y1="14" x2="22.5" y2="16" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="2" cy="9" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="2" cy="15" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 12, y: 3 }, { x: 12, y: 21 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="19" cy="14" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="22.5" cy="16" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z06</div>
        <h3>Axe horizontal</h3>
        <p class="caption">
          Y-fork à l'ouest, parent-lune à l'est, réguliers nord/sud. Symétrie horizontale.
        </p>
      </div>

      <!-- Z07 — Compact bas (pulsar BL placement, tout au-dessus à droite) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 4, y: 14 }, { x: 22, y: 18 }] as p, i (i)}
              <line x1="6" y1="20" x2={p.x} y2={p.y} />
            {/each}
            <line x1="6" y1="20" x2="11" y2="11" />
            <line x1="11" y1="11" x2="8" y2="5" />
            <line x1="11" y1="11" x2="16" y2="6" />
            <line x1="6" y1="20" x2="17" y2="16" />
            <line x1="17" y1="16" x2="22" y2="12" />
            <circle cx="6" cy="20" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="8" cy="5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="16" cy="6" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 4, y: 14 }, { x: 22, y: 18 }] as p, i (i)}
              <circle cx={p.x} cy={p.y} r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            {/each}
            <circle cx="17" cy="16" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="22" cy="12" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z07</div>
        <h3>Pulsar BL · graphe NE</h3>
        <p class="caption">
          Pulsar coin SO, tout le graphe au-dessus. Composition diagonale ascendante.
        </p>
      </div>

      <!-- Z08 — Vertical stack (Y-fork tout en haut, pulsar milieu-haut, parent-lune en bas) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="10" x2="3" y2="12" />
            <line x1="12" y1="10" x2="21" y2="12" />
            <line x1="12" y1="10" x2="12" y2="5" />
            <line x1="12" y1="5" x2="8" y2="2" />
            <line x1="12" y1="5" x2="16" y2="2" />
            <line x1="12" y1="10" x2="12" y2="17" />
            <line x1="12" y1="17" x2="12" y2="22" />
            <circle cx="12" cy="10" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="8" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="16" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="12" cy="17" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="12" cy="22" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z08</div>
        <h3>Stack vertical</h3>
        <p class="caption">
          Y-fork tout en haut, pulsar+régulières au milieu, parent-lune en bas. Lecture verticale
          stricte.
        </p>
      </div>

      <!-- Z09 — Triangle symétrique (Y-fork sommet, parent-lune SE, régulier SW) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="14" x2="12" y2="6" />
            <line x1="12" y1="6" x2="6" y2="2" />
            <line x1="12" y1="6" x2="18" y2="2" />
            <line x1="12" y1="14" x2="18" y2="20" />
            <line x1="18" y1="20" x2="22" y2="22.5" />
            <line x1="12" y1="14" x2="6" y2="20" />
            <circle cx="12" cy="14" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="6" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="18" cy="20" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="22" cy="22.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            <circle cx="6" cy="20" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z09</div>
        <h3>Triangle symétrique</h3>
        <p class="caption">
          Y-fork au sommet, parent-lune SE, régulier SW. Composition triangulaire équilibrée.
        </p>
      </div>

      <!-- Z10 — Double Y-fork + lune unique (3 paires citées + 1 chaîne) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="12" x2="6" y2="6" />
            <line x1="6" y1="6" x2="3" y2="3" />
            <line x1="6" y1="6" x2="8" y2="2" />
            <line x1="12" y1="12" x2="18" y2="6" />
            <line x1="18" y1="6" x2="21" y2="3" />
            <line x1="18" y1="6" x2="16" y2="2" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="3" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="8" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="3" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="16" cy="2" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z10</div>
        <h3>Double Y-fork + lune</h3>
        <p class="caption">
          Deux Y-forks au-dessus + parent-lune SE. 7 nœuds — bibliographie à deux paires citées.
        </p>
      </div>
    </div>

    <h3 class="section-subtitle">Batch B — Z11-Z20 · Combinaisons de couleurs</h3>
    <div class="grid grid--dense">
      <!-- Z11 — Hero echo full (cobalt + coral + amber + emerald + violet) -->
      <div class="card">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius * 1.1} fill="#FFFFFF" stroke="none" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#F87171" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#FCD34D" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#52E0C4" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#FFD969" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#6EE7B7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#C4B5FD" stroke="none" />
          </svg>
        </div>
        <div class="num">Z11 · Hero Echo full</div>
        <h3>Palette hero intégrale</h3>
        <p class="caption">
          Pulsar bleu naine + coral/amber/cyan/gold + emerald/violet. Maximaliste hero.
        </p>
      </div>

      <!-- Z12 — Hero echo soft (mêmes teintes mais plus pastel, fond clair) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#94A3B8"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#FBA5A5" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#FCE3A2" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#A6E8DA" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#FDDB94" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#A8E4C5" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#D4CAFD" stroke="none" />
          </svg>
        </div>
        <div class="num">Z12 · Hero Echo pastel</div>
        <h3>Hero soft (fond clair)</h3>
        <p class="caption">
          Palette hero éclaircie, pulsar indigo profond. Vibe scolaire / éditorial sain.
        </p>
      </div>

      <!-- Z13 — Démo auteur-kind RÉEL (chercheur, media, institution, individu, etc.) -->
      <div class="card highlight">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1F2937" stroke="none" />
            <!-- twins = chercheur (vert) + media (ambre) -->
            <circle
              cx="4"
              cy="2.5"
              r={leafRadius * 0.9}
              fill="#C0DD97"
              stroke="#639922"
              stroke-width={strokeWidth * 0.5}
            />
            <circle
              cx="9.5"
              cy="1.5"
              r={leafRadius * 0.9}
              fill="#FAC775"
              stroke="#EF9F27"
              stroke-width={strokeWidth * 0.5}
            />
            <!-- régulières = laboratoire (sky) + gouvernement (rose) -->
            <circle
              cx="3"
              cy="12"
              r={leafRadius * 0.9}
              fill="#BAE6FD"
              stroke="#0EA5E9"
              stroke-width={strokeWidth * 0.5}
            />
            <circle
              cx="21"
              cy="12"
              r={leafRadius * 0.9}
              fill="#F2A7BE"
              stroke="#D4456E"
              stroke-width={strokeWidth * 0.5}
            />
            <!-- parent = institution-publique (bleu) -->
            <circle
              cx="17"
              cy="18"
              r={leafRadius * 1.2}
              fill="#B5D4F4"
              stroke="#378ADD"
              stroke-width={strokeWidth * 0.6}
            />
            <!-- lune = individu (violet) -->
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.6}
              fill="#CECBF6"
              stroke="#7F77DD"
              stroke-width={strokeWidth * 0.4}
            />
          </svg>
        </div>
        <div class="num">Z13 · Démo auteur-kind ⭐</div>
        <h3>Palette auteur-kind RÉELLE</h3>
        <p class="caption">
          Couleurs exactes du graphe démo (ADR-020) : chercheur vert + média ambre + labo sky + gouv
          rose + institution bleu + individu violet. Pulsar slate. Cohérence produit absolue.
        </p>
      </div>

      <!-- Z14 — Démo auteur-kind tous chercheurs (mono palette vert) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#639922"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#173404" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#C0DD97" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#C0DD97" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#C0DD97" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#C0DD97" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#639922" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#173404" stroke="none" />
          </svg>
        </div>
        <div class="num">Z14 · mono chercheur</div>
        <h3>Tout chercheur (mono vert)</h3>
        <p class="caption">
          Palette « toutes sources scientifiques » : 3 niveaux de vert (fill, stroke, text).
          Identité forte vulgarisateurs sci.
        </p>
      </div>

      <!-- Z15 — Sober bold : pulsar noir saturé + accents indigo -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#0F172A"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius * 1.15} fill="#0F172A" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#3B82F6" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#3B82F6" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#0F172A" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#0F172A" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#0F172A" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#3B82F6" stroke="none" />
          </svg>
        </div>
        <div class="num">Z15 · Sober bold</div>
        <h3>Pulsar noir + accents bleu</h3>
        <p class="caption">
          Le pulsar et les régulières en noir saturé, twins Y-fork + lune en indigo bright.
          Bichromie autoritaire.
        </p>
      </div>

      <!-- Z16 — Astronomical + emerald accent -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#3454D1"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#3454D1" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#F4A261" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#F4A261" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#3454D1" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#3454D1" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4CAF80" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#E76F51" stroke="none" />
          </svg>
        </div>
        <div class="num">Z16 · Astro + emerald</div>
        <h3>Astronomical + 2 accents</h3>
        <p class="caption">
          Indigo + amber Y-fork + emerald parent + coral lune. Quadrichromie naturelle.
        </p>
      </div>

      <!-- Z17 — Inverse contrast (fond sombre, accents pastel) -->
      <div class="card">
        <div class="canvas" style="background: #1F2937">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#94A3B8"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#FFFFFF" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#A6E8DA" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#FCE3A2" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#FBA5A5" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#D4CAFD" stroke="none" />
          </svg>
        </div>
        <div class="num">Z17 · Dark mode pastel</div>
        <h3>Sombre + accents pastel</h3>
        <p class="caption">
          Pulsar blanc sur fond slate sombre, accents pastel multi-couleur. Dark mode dashboard.
        </p>
      </div>

      <!-- Z18 — Dégradé monochrome (4 saturations indigo) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#94A3B8"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <!-- Dégradé : pulsar foncé → lune clair -->
            <circle cx="12" cy="12" r={centerRadius} fill="#1E3A8A" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#3B82F6" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#3B82F6" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#60A5FA" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#60A5FA" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#93C5FD" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#BFDBFE" stroke="none" />
          </svg>
        </div>
        <div class="num">Z18 · Dégradé saturation</div>
        <h3>Dégradé monochrome bleu</h3>
        <p class="caption">
          4 saturations d'indigo (foncé pulsar → clair lune). Hiérarchie par luminosité.
        </p>
      </div>

      <!-- Z19 — Filum brand bleu + accent coral chaud (warm/cool tension) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <!-- Coral accent SEULEMENT sur la lune -->
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.65} fill="#F87171" stroke="none" />
          </svg>
        </div>
        <div class="num">Z19 · Filum + 1 accent</div>
        <h3>Mono indigo + lune coral</h3>
        <p class="caption">
          Tout indigo de marque + UN seul point coral sur la lune. Le détail qui chante.
        </p>
      </div>

      <!-- Z20 — Quadrichromie pondérée (chaque rôle = couleur distincte mais sourde) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#1E3A8A" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#D97706" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#D97706" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#475569" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#475569" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#047857" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#7C3AED" stroke="none" />
          </svg>
        </div>
        <div class="num">Z20 · Quadrichromie rôles</div>
        <h3>4 couleurs = 4 types</h3>
        <p class="caption">
          Indigo (pulsar) + amber (twins) + slate (réguliers) + emerald (parent) + violet (lune).
          Chaque rôle = sa teinte.
        </p>
      </div>
    </div>

    <h3 class="section-subtitle">Batch C — Z21-Z30 · Designs moins classiques</h3>
    <div class="grid grid--dense">
      <!-- Z21 — Pulsar gradient radial (3D sphère) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <radialGradient id="z21-pulsar" cx="40%" cy="40%" r="60%">
                <stop offset="0%" stop-color="white" stop-opacity="0.9" />
                <stop offset="45%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#1E3A8A" />
              </radialGradient>
            </defs>
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius * 1.2} fill="url(#z21-pulsar)" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z21 · gradient radial</div>
        <h3>Pulsar sphère 3D</h3>
        <p class="caption">
          Pulsar rendu comme une sphère via gradient (highlight, mid, falloff foncé). Effet 2.5D
          propre.
        </p>
      </div>

      <!-- Z22 — Halo translucide multicouche -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 3}
              fill="#6B8AFF"
              fill-opacity="0.08"
              stroke="none"
            />
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 2}
              fill="#6B8AFF"
              fill-opacity="0.16"
              stroke="none"
            />
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 1.4}
              fill="#6B8AFF"
              fill-opacity="0.28"
              stroke="none"
            />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z22 · halo multicouche</div>
        <h3>Halo 3D autour pulsar</h3>
        <p class="caption">
          3 couches translucides autour du pulsar (8%, 16%, 28%). Atmosphère stellaire douce.
        </p>
      </div>

      <!-- Z23 — Pulsar évidé (anneau) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 1.2}
              fill="#fafbfc"
              stroke="#4A6CF7"
              stroke-width={strokeWidth * 1.4}
            />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
          </svg>
        </div>
        <div class="num">Z23 · pulsar évidé</div>
        <h3>Pulsar anneau (hollow)</h3>
        <p class="caption">Pulsar non rempli, anneau. Plus architectural, contraste inversé.</p>
      </div>

      <!-- Z24 — Mark + wordmark horizontal (lockup header) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 80 24"
            width={scale * 1.6}
            height={scale * 0.5}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
            style="max-width: 100%; height: auto;"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            <text
              x="32"
              y="16.5"
              fill="#1A1A1A"
              stroke="none"
              font-family="'Source Serif 4', 'Crimson Pro', Georgia, serif"
              font-size="13"
              font-weight="500"
              font-style="italic"
              letter-spacing="0.5"
            >
              filum
            </text>
          </svg>
        </div>
        <div class="num">Z24 · lockup horizontal</div>
        <h3>Mark + wordmark serif italique</h3>
        <p class="caption">
          Y01 + « filum » serif italique à droite. Format header / favicon-plus-wordmark.
        </p>
      </div>

      <!-- Z25 — Mark + wordmark vertical -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 36"
            width={scale * 0.7}
            height={scale * 1.05}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            <text
              x="12"
              y="32"
              text-anchor="middle"
              fill="#1A1A1A"
              stroke="none"
              font-family="'Source Serif 4', Georgia, serif"
              font-size="6"
              font-weight="500"
              letter-spacing="1.2"
            >
              FILUM
            </text>
          </svg>
        </div>
        <div class="num">Z25 · lockup vertical</div>
        <h3>Mark + wordmark stacked</h3>
        <p class="caption">
          Mark au-dessus, « FILUM » all-caps lettrispacé en dessous. Format carte de visite / sceau.
        </p>
      </div>

      <!-- Z26 — Frosted blur backdrop (glow atmosphérique) -->
      <div class="card">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="z26-blur" x="-100%" y="-100%" width="300%" height="300%">
                <feGaussianBlur stdDeviation="2.5" />
              </filter>
            </defs>
            <circle
              cx="12"
              cy="12"
              r="6"
              fill="#5B7FFF"
              fill-opacity="0.45"
              filter="url(#z26-blur)"
            />
            <g stroke="#FFFFFF" stroke-opacity="0.55">
              {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="7" y2="5" />
              <line x1="7" y1="5" x2="4" y2="2.5" />
              <line x1="7" y1="5" x2="9.5" y2="1.5" />
              <line x1="12" y1="12" x2="17" y2="18" />
              <line x1="17" y1="18" x2="20.5" y2="20.5" />
            </g>
            <circle cx="12" cy="12" r={centerRadius * 1.15} fill="#FFFFFF" stroke="none" />
            <circle cx="12" cy="12" r={centerRadius} fill="#5B7FFF" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#A0B0E8" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#A0B0E8" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#FFFFFF" stroke="none" />
          </svg>
        </div>
        <div class="num">Z26 · frosted blur</div>
        <h3>Halo flouté + dark</h3>
        <p class="caption">
          Backdrop blur (filter Gaussian) derrière le pulsar. Premium atmosphérique dashboard.
        </p>
      </div>

      <!-- Z27 — Z-layered (stroke fond autour de chaque sphère) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <line x1="12" y1="12" x2={p.x} y2={p.y} />
            {/each}
            <line x1="12" y1="12" x2="7" y2="5" />
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <line x1="12" y1="12" x2="17" y2="18" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            {#each [{ x: 4, y: 2.5 }, { x: 9.5, y: 1.5 }, { x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
              <circle
                cx={p.x}
                cy={p.y}
                r={leafRadius * 0.95}
                fill="#4A6CF7"
                stroke="#fafbfc"
                stroke-width={strokeWidth * 0.9}
              />
            {/each}
            <circle
              cx="17"
              cy="18"
              r={leafRadius * 1.2}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 1.1}
            />
            <circle
              cx="20.5"
              cy="20.5"
              r={leafRadius * 0.65}
              fill="#4A6CF7"
              stroke="#fafbfc"
              stroke-width={strokeWidth * 0.7}
            />
          </svg>
        </div>
        <div class="num">Z27 · z-layered</div>
        <h3>Stroke fond 3D plat</h3>
        <p class="caption">
          Chaque sphère détachée du fond via stroke blanc. Faux ordering 3D, lecture sophistiquée.
        </p>
      </div>

      <!-- Z28 — Drop-shadow soft -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#4A6CF7"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="z28-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.7"
                  stdDeviation="0.45"
                  flood-color="#1A1A1A"
                  flood-opacity="0.22"
                />
              </filter>
            </defs>
            <g filter="url(#z28-shadow)">
              {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="7" y2="5" />
              <line x1="7" y1="5" x2="4" y2="2.5" />
              <line x1="7" y1="5" x2="9.5" y2="1.5" />
              <line x1="12" y1="12" x2="17" y2="18" />
              <line x1="17" y1="18" x2="20.5" y2="20.5" />
              <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
              <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#4A6CF7" stroke="none" />
              <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#4A6CF7" stroke="none" />
              <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#4A6CF7" stroke="none" />
            </g>
          </svg>
        </div>
        <div class="num">Z28 · drop-shadow</div>
        <h3>Ombre douce</h3>
        <p class="caption">
          Y01 avec ombre douce sous chaque élément. Sensation papier-collé matérielle.
        </p>
      </div>

      <!-- Z29 — Lignes en gradient (chaque ligne fade vers la feuille) -->
      <div class="card">
        <div class="canvas" style="background: #fafbfc">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <linearGradient
                id="z29-l1"
                x1="12"
                y1="12"
                x2="3"
                y2="12"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#F87171" />
              </linearGradient>
              <linearGradient
                id="z29-l2"
                x1="12"
                y1="12"
                x2="21"
                y2="12"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#FCD34D" />
              </linearGradient>
              <linearGradient
                id="z29-l3"
                x1="12"
                y1="12"
                x2="7"
                y2="5"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#52E0C4" />
              </linearGradient>
              <linearGradient
                id="z29-l4"
                x1="12"
                y1="12"
                x2="17"
                y2="18"
                gradientUnits="userSpaceOnUse"
              >
                <stop offset="0%" stop-color="#4A6CF7" />
                <stop offset="100%" stop-color="#6EE7B7" />
              </linearGradient>
            </defs>
            <line x1="12" y1="12" x2="3" y2="12" stroke="url(#z29-l1)" />
            <line x1="12" y1="12" x2="21" y2="12" stroke="url(#z29-l2)" />
            <line x1="12" y1="12" x2="7" y2="5" stroke="url(#z29-l3)" />
            <line x1="7" y1="5" x2="4" y2="2.5" stroke="#52E0C4" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" stroke="#52E0C4" />
            <line x1="12" y1="12" x2="17" y2="18" stroke="url(#z29-l4)" />
            <line x1="17" y1="18" x2="20.5" y2="20.5" stroke="#C4B5FD" />
            <circle cx="12" cy="12" r={centerRadius} fill="#4A6CF7" stroke="none" />
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="#52E0C4" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="#52E0C4" stroke="none" />
            <circle cx="3" cy="12" r={leafRadius * 0.85} fill="#F87171" stroke="none" />
            <circle cx="21" cy="12" r={leafRadius * 0.85} fill="#FCD34D" stroke="none" />
            <circle cx="17" cy="18" r={leafRadius * 1.1} fill="#6EE7B7" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="#C4B5FD" stroke="none" />
          </svg>
        </div>
        <div class="num">Z29 · gradient lines</div>
        <h3>Lignes color-fade</h3>
        <p class="caption">
          Chaque ligne transitionne du pulsar bleu à la couleur de sa feuille. Spectacle hero.
        </p>
      </div>

      <!-- Z30 — Maximaliste : combo de tous les effets (z + shadow + halo + hero) -->
      <div class="card highlight">
        <div class="canvas" style="background: #0d0d12">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke="#475569"
            stroke-width={strokeWidth}
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <defs>
              <filter id="z30-shadow" x="-30%" y="-30%" width="160%" height="160%">
                <feDropShadow
                  dx="0"
                  dy="0.5"
                  stdDeviation="0.4"
                  flood-color="#000"
                  flood-opacity="0.55"
                />
              </filter>
              <radialGradient id="z30-pulsar" cx="40%" cy="40%" r="60%">
                <stop offset="0%" stop-color="white" stop-opacity="0.95" />
                <stop offset="55%" stop-color="#5B7FFF" />
                <stop offset="100%" stop-color="#2542A8" />
              </radialGradient>
            </defs>
            <!-- Halo derrière -->
            <circle
              cx="12"
              cy="12"
              r={centerRadius * 2.5}
              fill="#5B7FFF"
              fill-opacity="0.18"
              stroke="none"
            />
            <g filter="url(#z30-shadow)">
              {#each [{ x: 3, y: 12 }, { x: 21, y: 12 }] as p, i (i)}
                <line x1="12" y1="12" x2={p.x} y2={p.y} />
              {/each}
              <line x1="12" y1="12" x2="7" y2="5" />
              <line x1="7" y1="5" x2="4" y2="2.5" />
              <line x1="7" y1="5" x2="9.5" y2="1.5" />
              <line x1="12" y1="12" x2="17" y2="18" />
              <line x1="17" y1="18" x2="20.5" y2="20.5" />
              <circle
                cx="12"
                cy="12"
                r={centerRadius * 1.25}
                fill="url(#z30-pulsar)"
                stroke="none"
              />
              <circle
                cx="4"
                cy="2.5"
                r={leafRadius * 0.95}
                fill="#F87171"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.7}
              />
              <circle
                cx="9.5"
                cy="1.5"
                r={leafRadius * 0.95}
                fill="#FCD34D"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.7}
              />
              <circle
                cx="3"
                cy="12"
                r={leafRadius * 0.95}
                fill="#52E0C4"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.7}
              />
              <circle
                cx="21"
                cy="12"
                r={leafRadius * 0.95}
                fill="#FFD969"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.7}
              />
              <circle
                cx="17"
                cy="18"
                r={leafRadius * 1.2}
                fill="#6EE7B7"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.9}
              />
              <circle
                cx="20.5"
                cy="20.5"
                r={leafRadius * 0.65}
                fill="#C4B5FD"
                stroke="#0d0d12"
                stroke-width={strokeWidth * 0.6}
              />
            </g>
          </svg>
        </div>
        <div class="num">Z30 · maximalist ⭐</div>
        <h3>Combo tout-en-un</h3>
        <p class="caption">
          Gradient radial pulsar + halo + z-layered + drop-shadow + palette hero. La version « hero
          of hero ».
        </p>
      </div>
    </div>
  </section>

  <section class="section-block">
    <h2 class="section-title">Nouvelles directions · 2026-05-28</h2>
    <p class="section-lead">
      Six marks distincts dans des styles modernes — au-delà de la famille arboricole. Le <strong
        >#01</strong
      > reprend explicitement la topologie du nouveau hero (pulsar central, lune autour d'un parent, Y-fork
      qui se divise vers deux sources). Les cinq autres explorent monogramme typographique, geste continu,
      sceau certifié et axe diagonal de filiation. Tous monochromes, SVG 24×24, dimensionnables.
    </p>
    <div class="grid">
      <!-- 01 — PULSAR-GRAPH (écho hero : lune + Y-fork) -->
      <div class="card highlight">
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
            <!-- Trunk pulsar → point M virtuel (Y-fork) -->
            <line x1="12" y1="12" x2="7" y2="5" />
            <!-- Y-fork : deux branches qui partent de M vers les twins -->
            <line x1="7" y1="5" x2="4" y2="2.5" />
            <line x1="7" y1="5" x2="9.5" y2="1.5" />
            <!-- Connexion parent → pulsar -->
            <line x1="12" y1="12" x2="18" y2="18" />
            <!-- Connexion lune → parent -->
            <line x1="18" y1="18" x2="20.5" y2="20.5" />
            <!-- Pulsar central -->
            <circle cx="12" cy="12" r={centerRadius} fill="currentColor" stroke="none" />
            <!-- Twins du Y-fork -->
            <circle cx="4" cy="2.5" r={leafRadius * 0.85} fill="currentColor" stroke="none" />
            <circle cx="9.5" cy="1.5" r={leafRadius * 0.85} fill="currentColor" stroke="none" />
            <!-- Parent + lune (lune plus petite) -->
            <circle cx="18" cy="18" r={leafRadius * 1.1} fill="currentColor" stroke="none" />
            <circle cx="20.5" cy="20.5" r={leafRadius * 0.55} fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">01</div>
        <h3>Pulsar-graph</h3>
        <p class="caption">
          Écho direct du nouveau hero. Pulsar central, Y-fork de citation (un lien qui se divise
          vers deux sources), parent avec lune en mini-orbite. La topologie du graphe
          bibliographique en miniature — raconte le produit en un coup d'œil.
        </p>
      </div>

      <!-- 02 — F MONOGRAMME À POINT (typographique, autoritaire) -->
      <div class="card">
        <div class="canvas">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth * 1.5}
            stroke-linecap="square"
            stroke-linejoin="miter"
            style="color: {accentColor}"
          >
            <!-- Vertical stem -->
            <line x1="6" y1="3" x2="6" y2="21" />
            <!-- Top horizontal -->
            <line x1="6" y1="3" x2="17" y2="3" />
            <!-- Middle horizontal terminé par le point de citation -->
            <line x1="6" y1="11" x2="13" y2="11" />
            <circle cx="13" cy="11" r="1.4" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">02</div>
        <h3>F monogramme à point</h3>
        <p class="caption">
          Lettre F autoritaire, stem épais, terminaisons droites. Le point en bout de trait médian
          symbolise la citation : la lettre s'arrête sur une source précise. Très robuste en favicon
          16 px.
        </p>
      </div>

      <!-- 03 — FILAMENT (geste continu) -->
      <div class="card">
        <div class="canvas">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth * 1.4}
            stroke-linecap="round"
            stroke-linejoin="round"
            style="color: {accentColor}"
          >
            <!-- Un seul trait : arc montant à gauche, descente verticale, sortie horizontale -->
            <path d="M 4 19 Q 4 6 11 5 L 11 19 L 21 19" />
            <!-- Petit nœud terminal -->
            <circle cx="21" cy="19" r="1.1" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">03</div>
        <h3>Filament (geste continu)</h3>
        <p class="caption">
          Un seul trait, dessiné comme un fil aiguillé : montée courbe à gauche, descente droite,
          sortie horizontale, point d'attache à la fin. Évoque le « filum » originel (fil en latin),
          étymologie du nom. Élégant, manuscrit.
        </p>
      </div>

      <!-- 04 — « i » PULSAR (typo + symbole) -->
      <div class="card">
        <div class="canvas">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth * 1.3}
            stroke-linecap="round"
            stroke-linejoin="round"
            style="color: {accentColor}"
          >
            <!-- Lowercase i stem -->
            <line x1="12" y1="11" x2="12" y2="20" />
            <!-- Antennes de filiation (deux fins traits au-dessus du titre) -->
            <line x1="11" y1="3.2" x2="9.4" y2="1" stroke-width={strokeWidth * 0.8} />
            <line x1="13" y1="3.2" x2="14.6" y2="1" stroke-width={strokeWidth * 0.8} />
            <!-- Tittle surdimensionné = pulsar -->
            <circle cx="12" cy="5.5" r="2.3" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">04</div>
        <h3>« i » pulsar</h3>
        <p class="caption">
          Lettre « i » lowercase, le point du i remplacé par le pulsar surdimensionné, et deux fines
          antennes au-dessus suggérant la filiation des sources. Se lit comme un fragment de « filum
          » — wordmark friendly, hybride typo/symbole.
        </p>
      </div>

      <!-- 05 — SCEAU CERTIFIÉ -->
      <div class="card">
        <div class="canvas">
          <svg
            viewBox="0 0 24 24"
            width={scale}
            height={scale}
            fill="none"
            stroke={strokeColor}
            stroke-width={strokeWidth * 1.4}
            stroke-linecap="round"
            stroke-linejoin="round"
            style="color: {accentColor}"
          >
            <!-- Cadre carré arrondi -->
            <rect x="3" y="3" width="18" height="18" rx="3.5" />
            <!-- Cercle concentrique interne -->
            <circle cx="12" cy="12" r="5.5" stroke-width={strokeWidth * 0.9} />
            <!-- Point central -->
            <circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">05</div>
        <h3>Sceau certifié</h3>
        <p class="caption">
          Cadre carré arrondi + cercle concentrique + point central. Esthétique d'un tampon officiel
          ou d'un sceau d'attestation. Bonne silhouette en favicon — reconnaissable dès 12 px.
          Aligné avec le sens « attestation » du produit.
        </p>
      </div>

      <!-- 06 — AXE DE FILIATION (diagonale) -->
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
            <!-- Diagonale -->
            <line x1="4" y1="20" x2="20" y2="4" />
            <!-- Source (extrémité bas-gauche) -->
            <circle cx="4" cy="20" r="1.6" fill="currentColor" stroke="none" />
            <!-- Attestation centrale (le plus gros) -->
            <circle cx="12" cy="12" r={centerRadius * 0.9} fill="currentColor" stroke="none" />
            <!-- Citation (extrémité haut-droite) -->
            <circle cx="20" cy="4" r="1.6" fill="currentColor" stroke="none" />
          </svg>
        </div>
        <div class="num">06</div>
        <h3>Axe de filiation</h3>
        <p class="caption">
          Trois nœuds alignés sur une diagonale : source → attestation centrale → citation. La
          filiation comme un axe net, sans détour. Géométrie minimale, très lisible à toutes les
          tailles, lecture instantanée.
        </p>
      </div>
    </div>
  </section>

  <section class="section-block legacy">
    <h2 class="section-title">
      Variations arboricoles · 2026-05-22 <span class="ref-tag">référence</span>
    </h2>
    <p class="section-lead">
      Famille phylogénétique itérée précédemment (V1–V11). Conservées pour comparaison.
    </p>
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
              {@const mid = {
                x: 12 + branchLen * Math.cos(rad),
                y: 12 + branchLen * Math.sin(rad),
              }}
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
                <circle
                  cx={leaf1.x}
                  cy={leaf1.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
                <circle
                  cx={leaf2.x}
                  cy={leaf2.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
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
          Version minimaliste de V11 : 2 forks (horizontaux) + 2 simples (verticaux). Symétrie
          d'ordre 2. Plus aéré, plus moderne.
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
                <circle
                  cx={leaf1.x}
                  cy={leaf1.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
                <circle
                  cx={leaf2.x}
                  cy={leaf2.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
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
          Phylogénie verticale, racine en bas. Branches à profondeurs irrégulières — certaines
          sources sont citées par chaîne plus longue.
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
              {@const mid = {
                x: 12 + branchLen * Math.cos(rad),
                y: 12 + branchLen * Math.sin(rad),
              }}
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
                <circle
                  cx={leaf1.x}
                  cy={leaf1.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
                <circle
                  cx={leaf2.x}
                  cy={leaf2.y}
                  r={leafRadius}
                  fill="currentColor"
                  stroke="none"
                />
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
  </section>

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

    <div class="panel-sep">Pulsar-graph — couleurs avancées</div>
    <label>
      <span>Pulsar</span>
      <input type="color" bind:value={pulsarColor} />
    </label>
    <label>
      <span>Twins (Y-fork)</span>
      <input type="color" bind:value={twinColor} />
    </label>
    <label>
      <span>Parent (porte la lune)</span>
      <input type="color" bind:value={parentColor} />
    </label>
    <label>
      <span>Lune</span>
      <input type="color" bind:value={luneColor} />
    </label>
    <label>
      <span>Halo (3D)</span>
      <input type="color" bind:value={haloColor} />
    </label>
    <label>
      <span>Fond canvas</span>
      <input type="color" bind:value={canvasBg} />
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

  /* --- Panel de prototypes — section headers --- */
  .section-block {
    margin: 0 0 3rem;
  }
  .section-block.legacy {
    margin-top: 4rem;
    padding-top: 2.5rem;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
  }
  :global(.dark) .section-block.legacy {
    border-top-color: rgba(255, 255, 255, 0.08);
  }
  .section-title {
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0 0 0.5rem;
    color: #475569;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }
  :global(.dark) .section-title {
    color: #cbd5e1;
  }
  .ref-tag {
    font-size: 0.6rem;
    letter-spacing: 0.12em;
    padding: 0.1rem 0.45rem;
    border: 1px solid rgba(0, 0, 0, 0.15);
    border-radius: 999px;
    color: #64748b;
    font-weight: 400;
  }
  :global(.dark) .ref-tag {
    border-color: rgba(255, 255, 255, 0.18);
    color: #94a3b8;
  }
  .section-lead {
    font-size: 0.85rem;
    line-height: 1.55;
    color: #475569;
    max-width: 68ch;
    margin: 0 0 1.5rem;
  }
  :global(.dark) .section-lead {
    color: #94a3b8;
  }
  .section-lead strong {
    font-weight: 600;
    color: #0f172a;
  }
  :global(.dark) .section-lead strong {
    color: #e2e8f0;
  }

  /* --- Carte numérotée style "panel pro" --- */
  .num {
    font-size: 0.62rem;
    letter-spacing: 0.22em;
    font-variant-numeric: tabular-nums;
    color: #94a3b8;
    text-align: center;
    margin: 0.6rem 0 -0.1rem;
    text-transform: uppercase;
  }
  .card.highlight {
    border-color: #4a6cf7;
    box-shadow:
      0 0 0 1px rgba(74, 108, 247, 0.15),
      0 6px 16px rgba(74, 108, 247, 0.08);
  }
  :global(.dark) .card.highlight {
    border-color: rgba(107, 138, 255, 0.5);
    box-shadow:
      0 0 0 1px rgba(107, 138, 255, 0.25),
      0 6px 16px rgba(74, 108, 247, 0.12);
  }

  /* Sous-titre de section (Batch A / B / C) */
  .section-subtitle {
    font-size: 0.78rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 1.6rem 0 0.6rem;
    color: #475569;
  }
  :global(.dark) .section-subtitle {
    color: #cbd5e1;
  }

  /* Grille plus dense pour le panel 20-variations (cartes plus compactes) */
  .grid--dense {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 0.85rem;
  }

  /* Bloc « rationale design » repliable */
  .design-rationale {
    margin: 0 0 1.5rem;
    padding: 0.85rem 1rem;
    background: rgba(74, 108, 247, 0.04);
    border: 1px solid rgba(74, 108, 247, 0.18);
    border-radius: 8px;
    font-size: 0.82rem;
    color: #334155;
    line-height: 1.5;
  }
  :global(.dark) .design-rationale {
    background: rgba(107, 138, 255, 0.06);
    border-color: rgba(107, 138, 255, 0.18);
    color: #cbd5e1;
  }
  .design-rationale > summary {
    cursor: pointer;
    font-weight: 500;
    font-size: 0.78rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #4a6cf7;
    list-style: none;
  }
  .design-rationale > summary::-webkit-details-marker {
    display: none;
  }
  .design-rationale > summary::before {
    content: '▸ ';
    display: inline-block;
    transition: transform 0.15s ease;
  }
  .design-rationale[open] > summary::before {
    transform: rotate(90deg);
  }
  .design-rationale p,
  .design-rationale ul {
    margin: 0.6rem 0 0;
  }
  .design-rationale ul {
    padding-left: 1.2rem;
  }
  .design-rationale li {
    margin: 0.3rem 0;
  }
  .design-rationale strong {
    color: #0f172a;
  }
  :global(.dark) .design-rationale strong {
    color: #f1f5f9;
  }

  /* Séparateur dans le panneau de contrôle */
  .panel-sep {
    font-size: 0.62rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: #94a3b8;
    padding-top: 0.5rem;
    margin-top: 0.3rem;
    border-top: 1px solid rgba(0, 0, 0, 0.08);
  }
  :global(.dark) .panel-sep {
    border-top-color: rgba(255, 255, 255, 0.08);
    color: #94a3b8;
  }
</style>
