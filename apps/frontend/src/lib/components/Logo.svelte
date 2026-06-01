<script lang="ts">
  // Philum logo — V11 design (validated in /sandbox/logo).
  // Structure: 6 branches around a central node, alternating fork (2 leaves)
  // and simple (1 leaf), at 60° intervals — perfect 3-fold rotational symmetry.
  // - 3 forks at angles -90°, 30°, 150°: junction at distance 6, leaves at
  //   distance 9.2 with ±22° spread from the radial axis.
  // - 3 simples at angles -30°, 90°, 210°: leaf directly at distance 9.2.
  // Coordinates pre-computed (24×24 viewBox, center at 12,12).

  interface Props {
    size?: number;
    className?: string;
  }

  let { size = 24, className = '' }: Props = $props();
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.5"
  stroke-linecap="round"
  stroke-linejoin="round"
  class={className}
  aria-hidden="true"
>
  <!-- Central node -->
  <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />

  <!-- Fork — top (-90°) -->
  <line x1="12" y1="12" x2="12" y2="6" />
  <line x1="12" y1="6" x2="8.554" y2="3.47" />
  <line x1="12" y1="6" x2="15.446" y2="3.47" />
  <circle cx="8.554" cy="3.47" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="15.446" cy="3.47" r="1.5" fill="currentColor" stroke="none" />

  <!-- Simple — top-right (-30°) -->
  <line x1="12" y1="12" x2="19.967" y2="7.4" />
  <circle cx="19.967" cy="7.4" r="1.73" fill="currentColor" stroke="none" />

  <!-- Fork — bottom-right (30°) -->
  <line x1="12" y1="12" x2="17.196" y2="15" />
  <line x1="17.196" y1="15" x2="21.11" y2="13.28" />
  <line x1="17.196" y1="15" x2="17.664" y2="19.25" />
  <circle cx="21.11" cy="13.28" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="17.664" cy="19.25" r="1.5" fill="currentColor" stroke="none" />

  <!-- Simple — bottom (90°) -->
  <line x1="12" y1="12" x2="12" y2="21.2" />
  <circle cx="12" cy="21.2" r="1.73" fill="currentColor" stroke="none" />

  <!-- Fork — bottom-left (150°) -->
  <line x1="12" y1="12" x2="6.804" y2="15" />
  <line x1="6.804" y1="15" x2="6.336" y2="19.25" />
  <line x1="6.804" y1="15" x2="2.89" y2="13.28" />
  <circle cx="6.336" cy="19.25" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="2.89" cy="13.28" r="1.5" fill="currentColor" stroke="none" />

  <!-- Simple — top-left (210°) -->
  <line x1="12" y1="12" x2="4.033" y2="7.4" />
  <circle cx="4.033" cy="7.4" r="1.73" fill="currentColor" stroke="none" />
</svg>
