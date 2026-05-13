<script lang="ts">
  interface Props {
    size?: number
    className?: string
  }

  let { size = 24, className = '' }: Props = $props()
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
  <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />

  <!-- Branche 1 – haut -->
  <line x1="12" y1="12" x2="12" y2="5.5" />
  <line x1="12" y1="5.5" x2="9" y2="2" />
  <line x1="12" y1="5.5" x2="15" y2="2" />
  <circle cx="9" cy="2" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="15" cy="2" r="1.5" fill="currentColor" stroke="none" />

  <!-- Branche 2 – haut-droit -->
  <line x1="12" y1="12" x2="17.5" y2="9" />
  <line x1="17.5" y1="9" x2="18.5" y2="4.5" />
  <line x1="17.5" y1="9" x2="21.5" y2="9" />
  <circle cx="18.5" cy="4.5" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="21.5" cy="9" r="1.5" fill="currentColor" stroke="none" />

  <!-- Branche 3 – bas-droit -->
  <line x1="12" y1="12" x2="17.5" y2="15" />
  <line x1="17.5" y1="15" x2="18.5" y2="19.5" />
  <line x1="17.5" y1="15" x2="21.5" y2="15" />
  <circle cx="18.5" cy="19.5" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="21.5" cy="15" r="1.5" fill="currentColor" stroke="none" />

  <!-- Branche 4 – bas -->
  <line x1="12" y1="12" x2="12" y2="18.5" />
  <line x1="12" y1="18.5" x2="9" y2="22" />
  <line x1="12" y1="18.5" x2="15" y2="22" />
  <circle cx="9" cy="22" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="15" cy="22" r="1.5" fill="currentColor" stroke="none" />

  <!-- Branche 5 – bas-gauche -->
  <line x1="12" y1="12" x2="6.5" y2="15" />
  <line x1="6.5" y1="15" x2="5.5" y2="19.5" />
  <line x1="6.5" y1="15" x2="2.5" y2="15" />
  <circle cx="5.5" cy="19.5" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="2.5" cy="15" r="1.5" fill="currentColor" stroke="none" />

  <!-- Branche 6 – haut-gauche -->
  <line x1="12" y1="12" x2="6.5" y2="9" />
  <line x1="6.5" y1="9" x2="5.5" y2="4.5" />
  <line x1="6.5" y1="9" x2="2.5" y2="9" />
  <circle cx="5.5" cy="4.5" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="2.5" cy="9" r="1.5" fill="currentColor" stroke="none" />
</svg>
