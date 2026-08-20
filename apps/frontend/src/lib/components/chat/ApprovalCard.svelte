<script lang="ts">
  import Button from '../Button.svelte';

  interface Props {
    tool: string;
    args: Record<string, unknown>;
    /** `null` tant que personne n'a répondu. */
    approved?: boolean | null;
    onrespond: (approved: boolean) => void;
  }

  let { tool, args, approved = null, onrespond }: Props = $props();

  let envoi = $state(false);

  async function repondre(valeur: boolean) {
    envoi = true;
    try {
      await onrespond(valeur);
    } finally {
      envoi = false;
    }
  }
</script>

<div class="rounded-lg border border-warning/40 bg-warning-bg px-4 py-3 text-sm">
  <p class="text-ink-primary">
    L'agent veut exécuter <span class="font-mono">{tool}</span>. Cette action écrit chez vous : elle
    n'est lancée que si vous la validez.
  </p>
  <pre
    class="mt-2 overflow-x-auto rounded bg-surface-tertiary p-2 text-xs text-ink-secondary">{JSON.stringify(
      args,
      null,
      2
    )}</pre>
  {#if approved === null}
    <div class="mt-3 flex gap-2">
      <Button size="sm" loading={envoi} onclick={() => repondre(true)}>Autoriser</Button>
      <Button size="sm" variant="ghost" loading={envoi} onclick={() => repondre(false)}>
        Refuser
      </Button>
    </div>
  {:else}
    <p class="mt-2 text-xs text-ink-tertiary">
      {approved ? 'Autorisée.' : 'Refusée : rien n’a été écrit.'}
    </p>
  {/if}
</div>
