<script lang="ts">
  interface Props {
    texte: string;
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
</script>

<button
  type="button"
  class="rounded px-1.5 py-0.5 text-xs text-ink-tertiary hover:bg-surface-tertiary hover:text-ink-primary {classe}"
  onclick={copier}
  aria-live="polite"
>
  {etat === 'copie' ? 'Copié' : etat === 'refus' ? 'Copie impossible' : libelle}
</button>
