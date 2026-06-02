<script lang="ts">
  // ====================================================================
  // Philum v1 — logo canonique (design validé en /sandbox/customize)
  //
  // Composition : Pulsar-graph (graph-mark)
  //   - Pulsar central (12, 12) — nœud créateur·ice
  //   - 2 nœuds normaux : NE (20, 7) + WSW (5, 15) — sources isolées
  //   - Y-fork NW (jonction 7,5 → twins 4,2.5 et 9.5,1.5) — paire citée
  //   - Parent SE (17, 18) + lune (20.5, 20.5) — source qui en cite une autre
  //
  // Style : palette Z13 auteur-kind + stroke fond blanc V18 + dark rim fin
  //         + (variant 'color' uniquement) pulsar 3D via radial gradient.
  //
  // 4 usages possibles via les props :
  //   - variant='color' (défaut) : couleur sur fond clair
  //   - variant='dark'           : blanc sur fond sombre
  //   - variant='bw'             : noir & blanc (impression)
  //   - withWordmark             : ajoute « Philum » serif à droite
  // ====================================================================

  interface Props {
    size?: number;
    variant?: 'color' | 'dark' | 'bw';
    withWordmark?: boolean;
    className?: string;
  }

  let { size = 24, variant = 'color', withWordmark = false, className = '' }: Props = $props();

  // ID unique pour le radial gradient (évite collisions multi-Logo).
  const uid = `philum-${Math.random().toString(36).slice(2, 9)}`;

  type Palette = {
    pulsarFill: string;
    pulsarRim: string;
    pulsarGradient: [string, string, string] | null;
    pulsarHalo: string | null;
    normalFill: string;
    normalRim: string;
    twinFill: string;
    twinRim: string;
    parentFill: string;
    parentRim: string;
    luneFill: string;
    luneRim: string;
    lineStroke: string;
    fondColor: string;
    wordmarkColor: string;
  };

  const PALETTES: Record<'color' | 'dark' | 'bw', Palette> = {
    color: {
      pulsarFill: '#1F2937',
      pulsarRim: '#000000',
      pulsarGradient: ['#FFFFFF', '#475569', '#0F172A'],
      pulsarHalo: '#FFFFFF',
      normalFill: '#FAC775',
      normalRim: '#EF9F27',
      twinFill: '#C0DD97',
      twinRim: '#639922',
      parentFill: '#B5D4F4',
      parentRim: '#378ADD',
      luneFill: '#CECBF6',
      luneRim: '#7F77DD',
      lineStroke: '#475569',
      fondColor: '#FFFFFF',
      wordmarkColor: '#1F2937',
    },
    dark: {
      pulsarFill: '#F8FAFC',
      pulsarRim: '#F8FAFC',
      pulsarGradient: null,
      pulsarHalo: null,
      normalFill: '#F8FAFC',
      normalRim: '#F8FAFC',
      twinFill: '#F8FAFC',
      twinRim: '#F8FAFC',
      parentFill: '#F8FAFC',
      parentRim: '#F8FAFC',
      luneFill: '#F8FAFC',
      luneRim: '#F8FAFC',
      lineStroke: '#F8FAFC',
      fondColor: '#0F172A',
      wordmarkColor: '#F8FAFC',
    },
    bw: {
      pulsarFill: '#000000',
      pulsarRim: '#000000',
      pulsarGradient: null,
      pulsarHalo: null,
      normalFill: '#000000',
      normalRim: '#000000',
      twinFill: '#000000',
      twinRim: '#000000',
      parentFill: '#000000',
      parentRim: '#000000',
      luneFill: '#000000',
      luneRim: '#000000',
      lineStroke: '#000000',
      fondColor: '#FFFFFF',
      wordmarkColor: '#000000',
    },
  };

  let p = $derived(PALETTES[variant]);

  // Échelle globale 0.85 (laisse respirer dans le viewBox).
  const globalScale = 0.85;

  let vbW = $derived(withWordmark ? 60 : 24);
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 {vbW} 24"
  width={withWordmark ? (size * vbW) / 24 : size}
  height={size}
  fill="none"
  aria-hidden="true"
  class={className}
>
  {#if p.pulsarGradient}
    <defs>
      <radialGradient id="grad-{uid}" cx="40%" cy="40%" r="60%">
        <stop offset="0%" stop-color={p.pulsarGradient[0]} />
        <stop offset="55%" stop-color={p.pulsarGradient[1]} />
        <stop offset="100%" stop-color={p.pulsarGradient[2]} />
      </radialGradient>
    </defs>
  {/if}

  <g transform="translate(12 12) scale({globalScale}) translate(-12 -12)">
    <!-- Lignes (centres à centres) -->
    <g stroke={p.lineStroke} stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round">
      <line x1="12" y1="12" x2="20" y2="7" />
      <line x1="12" y1="12" x2="5" y2="15" />
      <line x1="12" y1="12" x2="7" y2="5" />
      <line x1="7" y1="5" x2="4" y2="2.5" />
      <line x1="7" y1="5" x2="9.5" y2="1.5" />
      <line x1="12" y1="12" x2="17" y2="18" />
      <line x1="17" y1="18" x2="20.5" y2="20.5" />
    </g>

    <!-- Halo pulsar (variant color uniquement) -->
    {#if p.pulsarHalo}
      <circle cx="12" cy="12" r="6.0" fill={p.pulsarHalo} fill-opacity="0.14" />
      <circle cx="12" cy="12" r="4.25" fill={p.pulsarHalo} fill-opacity="0.28" />
    {/if}

    <!-- Pulsar : stroke fond + cercle 3D dark rim -->
    <circle cx="12" cy="12" r="2.5" fill="none" stroke={p.fondColor} stroke-width="1.6" />
    <circle
      cx="12"
      cy="12"
      r="2.5"
      fill={p.pulsarGradient ? `url(#grad-${uid})` : p.pulsarFill}
      stroke={p.pulsarRim}
      stroke-width="0.4"
    />

    <!-- Satellites : pour chaque sphère, fond V18 + cercle coloré dark rim -->
    <!-- twin A -->
    <circle cx="4" cy="2.5" r="1.275" fill="none" stroke={p.fondColor} stroke-width="1.4" />
    <circle cx="4" cy="2.5" r="1.275" fill={p.twinFill} stroke={p.twinRim} stroke-width="0.4" />
    <!-- twin B -->
    <circle cx="9.5" cy="1.5" r="1.275" fill="none" stroke={p.fondColor} stroke-width="1.4" />
    <circle cx="9.5" cy="1.5" r="1.275" fill={p.twinFill} stroke={p.twinRim} stroke-width="0.4" />
    <!-- normal A -->
    <circle cx="20" cy="7" r="1.275" fill="none" stroke={p.fondColor} stroke-width="1.4" />
    <circle cx="20" cy="7" r="1.275" fill={p.normalFill} stroke={p.normalRim} stroke-width="0.4" />
    <!-- normal B -->
    <circle cx="5" cy="15" r="1.275" fill="none" stroke={p.fondColor} stroke-width="1.4" />
    <circle cx="5" cy="15" r="1.275" fill={p.normalFill} stroke={p.normalRim} stroke-width="0.4" />
    <!-- parent -->
    <circle cx="17" cy="18" r="1.65" fill="none" stroke={p.fondColor} stroke-width="1.5" />
    <circle cx="17" cy="18" r="1.65" fill={p.parentFill} stroke={p.parentRim} stroke-width="0.45" />
    <!-- lune -->
    <circle cx="20.5" cy="20.5" r="0.825" fill="none" stroke={p.fondColor} stroke-width="1.2" />
    <circle
      cx="20.5"
      cy="20.5"
      r="0.825"
      fill={p.luneFill}
      stroke={p.luneRim}
      stroke-width="0.35"
    />
  </g>

  {#if withWordmark}
    <text
      x="26"
      y="12.5"
      fill={p.wordmarkColor}
      font-family="Georgia, serif"
      font-size="11"
      font-weight="500"
      dominant-baseline="middle"
    >
      Philum
    </text>
  {/if}
</svg>
