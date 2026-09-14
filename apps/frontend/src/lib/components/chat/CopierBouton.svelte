<script lang="ts">
  interface Props {
    texte: string;
    /** Ce que dit le bouton aux lecteurs d'écran et au survol. */
    libelle?: string;
    class?: string;
  }

  let { texte, libelle = 'Copier', class: classe = '' }: Props = $props();

  let etat = $state<'repos' | 'copie' | 'refus'>('repos');

  async function copier() {
    try {
      await navigator.clipboard.writeText(texte);
      etat = 'copie';
    } catch {
      // Presse-papiers refusé (contexte non sécurisé, permission) : le dire
      // plutôt que de laisser croire que le texte est copié.
      etat = 'refus';
    }
    setTimeout(() => (etat = 'repos'), 1500);
  }

  const annonce = $derived(
    etat === 'copie' ? 'Copié' : etat === 'refus' ? 'Copie impossible' : libelle
  );
</script>

<!-- Un symbole plutôt qu'un mot : le geste est rare, il ne doit pas prendre de place. -->
<button
  type="button"
  class="inline-flex h-6 w-6 items-center justify-center rounded text-ink-tertiary hover:bg-surface-tertiary hover:text-ink-primary {classe}"
  onclick={copier}
  title={annonce}
  aria-label={annonce}
  aria-live="polite"
>
  {#if etat === 'copie'}
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      stroke-width="1.8"
      aria-hidden="true"
    >
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  {:else if etat === 'refus'}
    <span aria-hidden="true" class="text-xs font-semibold">!</span>
  {:else}
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      stroke-width="1.4"
      aria-hidden="true"
    >
      <rect x="5.5" y="5.5" width="8" height="8" rx="1.5" />
      <path d="M10.5 3.5V3a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6.5a1 1 0 0 0 1 1h.5" />
    </svg>
  {/if}
</button>
