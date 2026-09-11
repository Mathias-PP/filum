<script lang="ts">
  import ToolCard from './ToolCard.svelte';
  import { rendreGroupe } from '$lib/agent/toolLabels';
  import { etatGroupe, resumerActivite, type BlocActivite } from '$lib/agent/activite';

  interface Props {
    bloc: BlocActivite;
    /** Le tour de ce bloc est-il celui qui se déroule maintenant ? */
    enDirect?: boolean;
  }

  let { bloc, enDirect = false }: Props = $props();

  // Ouvert pendant que l'agent travaille, pour voir ce qu'il fait ; replié
  // une fois le tour fini, pour que le fil se relise. Un clic l'emporte sur
  // ce défaut dans les deux sens.
  let choix = $state<boolean | null>(null);
  const ouvert = $derived(choix ?? (enDirect || bloc.enCours > 0));
  const resume = $derived(resumerActivite(bloc));
</script>

<div class="min-w-0 rounded-lg border border-border bg-surface-secondary text-sm">
  <button
    type="button"
    class="flex w-full min-w-0 items-center gap-2 px-3 py-2 text-left"
    aria-expanded={ouvert}
    onclick={() => (choix = !ouvert)}
  >
    <span aria-hidden="true" class="w-3 shrink-0 text-ink-tertiary">{ouvert ? '▾' : '▸'}</span>
    <span class="min-w-0 flex-1 truncate text-ink-secondary">{resume}</span>
    {#if bloc.enCours > 0}
      <span class="shrink-0 text-xs text-ink-tertiary">En cours…</span>
    {:else if bloc.echecs > 0}
      <span class="shrink-0 text-xs text-danger">
        {bloc.echecs} échec{bloc.echecs > 1 ? 's' : ''}
      </span>
    {:else}
      <span class="shrink-0 text-xs text-ink-tertiary">Terminé</span>
    {/if}
  </button>
  {#if ouvert}
    <div class="space-y-1.5 border-t border-border p-2">
      {#each bloc.groupes as groupe, rang (rang)}
        {#if groupe.entrees.length === 1}
          {@const seul = groupe.entrees[0]}
          <ToolCard name={seul.name} args={seul.args} result={seul.result} />
        {:else}
          {@const etat = etatGroupe(groupe)}
          <!-- Les appels repetes d'un meme outil restent replies : on lit
               « Supprime 10 extraits », on ouvre si l'on veut chacun. -->
          <details class="min-w-0 rounded-lg border border-border bg-surface-primary">
            <summary class="flex cursor-pointer items-center gap-2 px-3 py-2 text-ink-primary">
              <span class="min-w-0 flex-1 truncate">
                {rendreGroupe(groupe.name, groupe.entrees.length)}
              </span>
              {#if etat.enCours > 0}
                <span class="shrink-0 text-xs text-ink-tertiary">En cours…</span>
              {:else if etat.echecs > 0}
                <span class="shrink-0 text-xs text-danger">
                  {etat.echecs} échec{etat.echecs > 1 ? 's' : ''}
                </span>
              {/if}
            </summary>
            <div class="space-y-1 border-t border-border p-1.5">
              {#each groupe.entrees as appel (appel.id)}
                <ToolCard name={appel.name} args={appel.args} result={appel.result} />
              {/each}
            </div>
          </details>
        {/if}
      {/each}
    </div>
  {/if}
</div>
