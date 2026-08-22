<script lang="ts">
  import { rendreOutil } from '$lib/agent/toolLabels';

  interface Props {
    name: string;
    args: Record<string, unknown>;
    result?: Record<string, unknown> | null;
  }

  let { name, args, result = null }: Props = $props();

  let ouvert = $state(false);

  const echoue = $derived(Boolean(result && 'error' in result));
  const etat = $derived(result === null ? 'En cours...' : echoue ? 'Echec' : 'Termine');
  const raison = $derived.by(() => {
    if (!result || !('error' in result)) return null;
    const err = result.error;
    if (typeof err === 'string') return err;
    return JSON.stringify(err);
  });
  const rendu = $derived(rendreOutil(name, args, result));
</script>

<div class="rounded-lg border border-subtle bg-surface-secondary px-3 py-2 text-sm">
  <button
    type="button"
    class="flex w-full items-center justify-between gap-2 text-left"
    onclick={() => (ouvert = !ouvert)}
  >
    <span class="text-ink-primary">
      {rendu.action}{rendu.objet ? ` ${rendu.objet}` : ''}
      <span class="ml-1 font-mono text-[11px] text-ink-tertiary">{name}</span>
    </span>
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
