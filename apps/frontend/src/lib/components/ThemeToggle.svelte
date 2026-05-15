<script lang="ts">
  import { theme } from '$lib/stores';
</script>

<button
  type="button"
  onclick={(e) => {
    e.stopPropagation();
    theme.toggle();
  }}
  class="p-2 rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-tertiary transition-colors"
  aria-label={$theme === 'dark' ? 'Activer le thème clair' : 'Activer le thème sombre'}
  title={$theme === 'dark' ? 'Activer le thème clair' : 'Activer le thème sombre'}
>
  {#if $theme === 'dark'}
    <!-- Sun icon (currently dark, click to go light) -->
    <svg
      class="w-4 h-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  {:else}
    <!-- Moon icon (currently light, click to go dark) -->
    <svg
      class="w-4 h-4"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  {/if}
</button>
