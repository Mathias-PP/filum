<script lang="ts">
  // Logo Philum en noir & blanc animé : les satellites tournent autour du
  // pulsar central. Sert d'indicateur de travail pendant que l'agent réfléchit
  // ou exécute un outil. Utilise SMIL (<animateTransform>) plutôt que du CSS
  // parce que la rotation SVG autour d'un point donné se fait de façon fiable
  // via l'attribut transform="rotate(deg cx cy)".

  interface Props {
    size?: number;
    /** Vitesse en secondes pour un tour complet. */
    speed?: number;
  }

  let { size = 24, speed = 3 }: Props = $props();
</script>

<svg
  xmlns="http://www.w3.org/2000/svg"
  viewBox="0 0 24 24"
  width={size}
  height={size}
  fill="none"
  aria-label="L'agent Philum réfléchit"
  role="img"
>
  <!-- Pulsar central : immobile. `currentColor` pour hériter du texte
       ambiant (noir sur fond blanc, blanc sur fond noir sans surcharge). -->
  <circle cx="12" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="0.4" />
  <circle cx="12" cy="12" r="2.5" fill="currentColor" opacity="0.85" />

  <!-- Deux groupes de satellites en sens inverse : rappelle un graphe qui
       vit plutôt qu'une roue qui tourne. -->
  <g>
    <animateTransform
      attributeName="transform"
      type="rotate"
      from="0 12 12"
      to="360 12 12"
      dur="{speed}s"
      repeatCount="indefinite"
    />
    <g stroke="currentColor" stroke-width="0.35" stroke-linecap="round" opacity="0.55">
      <line x1="12" y1="12" x2="20" y2="7" />
      <line x1="12" y1="12" x2="7" y2="5" />
      <line x1="7" y1="5" x2="4" y2="2.5" />
      <line x1="7" y1="5" x2="9.5" y2="1.5" />
    </g>
    <circle cx="20" cy="7" r="1.275" fill="currentColor" />
    <circle cx="4" cy="2.5" r="1.275" fill="currentColor" />
    <circle cx="9.5" cy="1.5" r="1.275" fill="currentColor" />
  </g>

  <g>
    <animateTransform
      attributeName="transform"
      type="rotate"
      from="360 12 12"
      to="0 12 12"
      dur="{speed * 1.3}s"
      repeatCount="indefinite"
    />
    <g stroke="currentColor" stroke-width="0.35" stroke-linecap="round" opacity="0.55">
      <line x1="12" y1="12" x2="5" y2="15" />
      <line x1="12" y1="12" x2="17" y2="18" />
      <line x1="17" y1="18" x2="20.5" y2="20.5" />
    </g>
    <circle cx="5" cy="15" r="1.275" fill="currentColor" />
    <circle cx="17" cy="18" r="1.65" fill="currentColor" />
    <circle cx="20.5" cy="20.5" r="0.825" fill="currentColor" />
  </g>
</svg>
