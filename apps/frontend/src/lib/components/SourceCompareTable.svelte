<script lang="ts">
  /**
   * La bibliographie en tableau comparable, sans un seul appel à un modèle.
   *
   * Toutes les colonnes sont lues dans les champs déjà présents sur `Source` :
   * rien n'est généré, donc rien ne peut être halluciné. C'est le contrat qui
   * distingue ce tableau des matrices de comparaison LLM.
   *
   * La règle de rendu tient en une phrase : **aucune case n'est vide**. Une
   * information manquante s'écrit, et dit laquelle des quatre raisons
   * s'applique (cf. `compare-columns.ts`).
   */
  import type { Source } from '$lib/api/types';
  import {
    COMPARE_COLUMNS,
    compareCell,
    sortByColumn,
    type CellTone,
    type CompareColumnId,
  } from '$lib/utils/compare-columns';

  let { sources, onselect }: { sources: Source[]; onselect?: (id: string) => void } = $props();

  // `null` = ordre de la bibliographie, qui est celui voulu par l'auteur.
  // Il reste accessible : un tri n'efface pas l'ordre d'origine.
  let sortColumn = $state<CompareColumnId | null>(null);
  let sortDirection = $state<'asc' | 'desc'>('asc');

  const rows = $derived(
    sortColumn === null ? sources : sortByColumn(sources, sortColumn, sortDirection)
  );

  function toggleSort(column: CompareColumnId) {
    if (sortColumn !== column) {
      sortColumn = column;
      sortDirection = 'asc';
    } else if (sortDirection === 'asc') {
      sortDirection = 'desc';
    } else {
      // Troisième clic : retour à l'ordre de la bibliographie.
      sortColumn = null;
    }
  }

  const TONE_CLASS: Record<CellTone, string> = {
    neutral: 'text-ink-secondary',
    positive: 'text-emerald-700',
    warning: 'text-amber-800',
    danger: 'text-red-700 font-medium',
    // L'absence se lit comme une absence : grise et en italique, elle ne peut
    // pas être confondue avec une valeur.
    absent: 'text-ink-tertiary italic',
  };
</script>

<div class="overflow-x-auto rounded-lg border border-border bg-surface-primary">
  <table class="w-full text-sm border-collapse">
    <caption class="sr-only">
      Comparaison des sources citées : année, type, revue, accès, rétraction et position déclarée.
    </caption>
    <thead>
      <tr class="border-b border-border bg-surface-secondary">
        <th scope="col" class="px-3 py-2 text-left font-medium text-ink-tertiary w-8">#</th>
        <th scope="col" class="px-3 py-2 text-left font-medium text-ink-secondary min-w-[16rem]">
          Source
        </th>
        {#each COMPARE_COLUMNS as column (column.id)}
          <th
            scope="col"
            class="px-3 py-2 text-left font-medium text-ink-secondary whitespace-nowrap"
            aria-sort={sortColumn === column.id
              ? sortDirection === 'asc'
                ? 'ascending'
                : 'descending'
              : 'none'}
          >
            <button
              type="button"
              class="inline-flex items-center gap-1 hover:text-ink-primary transition-colors"
              onclick={() => toggleSort(column.id)}
              title="{column.hint} — cliquez pour trier"
            >
              {column.label}
              <span class="text-ink-tertiary" aria-hidden="true">
                {#if sortColumn === column.id}{sortDirection === 'asc' ? '↑' : '↓'}{:else}↕{/if}
              </span>
            </button>
          </th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rows as source, i (source.id)}
        <tr class="border-b border-border last:border-0 hover:bg-surface-secondary">
          <td class="px-3 py-2 text-ink-tertiary tabular-nums align-top">{i + 1}</td>
          <td class="px-3 py-2 align-top">
            <button
              type="button"
              class="text-left text-ink-primary hover:text-info transition-colors"
              onclick={() => onselect?.(source.id)}
            >
              {source.title || 'Sans titre'}
            </button>
            {#if source.authors}
              <p class="text-xs text-ink-tertiary mt-0.5">{source.authors}</p>
            {/if}
          </td>
          {#each COMPARE_COLUMNS as column (column.id)}
            {@const cell = compareCell(source, column.id)}
            <td class="px-3 py-2 align-top {TONE_CLASS[cell.tone]}" title={cell.help}>
              {cell.label}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<p class="mt-2 text-xs text-ink-tertiary">
  Aucune case n'est laissée vide : « non renseignée » (rien n'a été saisi), « sans objet » (la
  question ne se pose pas pour ce type de source), « non vérifié » (le contrôle n'a jamais tourné)
  et « non vérifiable » (le contrôle ne peut pas conclure) disent quatre choses différentes.
</p>
