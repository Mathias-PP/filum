<script lang="ts">
  interface Props {
    name: string;
    args: Record<string, unknown>;
    result?: Record<string, unknown> | null;
  }

  let { name, args, result = null }: Props = $props();

  let ouvert = $state(false);

  const echoue = $derived(Boolean(result && 'error' in result));
  const etat = $derived(result === null ? 'En cours…' : echoue ? 'Échec' : 'Terminé');
  // L'échec doit se lire sans déplier le JSON : le message d'erreur est la
  // seule chose que l'utilisateur cherche en général.
  const raison = $derived.by(() => {
    if (!result || !('error' in result)) return null;
    const err = result.error;
    if (typeof err === 'string') return err;
    return JSON.stringify(err);
  });
</script>

<div class="rounded-lg border border-subtle bg-surface-secondary px-3 py-2 text-sm">
  <button
    type="button"
    class="flex w-full items-center justify-between gap-2 text-left"
    onclick={() => (ouvert = !ouvert)}
  >
    <span class="font-mono text-ink-primary">{name}</span>
    <span class="text-xs" class:text-danger={echoue} class:text-ink-tertiary={!echoue}>
      {etat}
    </span>
  </button>
  {#if raison}
    <p class="mt-1 text-xs text-danger">{raison}</p>
  {/if}
  {#if ouvert}
    <pre
      class="mt-2 overflow-x-auto rounded bg-surface-tertiary p-2 text-xs text-ink-secondary">{JSON.stringify(
        args,
        null,
        2
      )}</pre>
    {#if result}
      <pre
        class="mt-1 overflow-x-auto rounded bg-surface-tertiary p-2 text-xs text-ink-secondary">{JSON.stringify(
          result,
          null,
          2
        )}</pre>
    {/if}
  {/if}
</div>
