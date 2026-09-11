<script lang="ts">
  import { analyser, type Segment } from '$lib/agent/markdown';
  import CopierBouton from './CopierBouton.svelte';

  interface Props {
    texte: string;
  }

  let { texte }: Props = $props();

  const blocs = $derived(analyser(texte));

  function estLien(segment: Segment): segment is Extract<Segment, { t: 'lien' }> {
    return segment.t === 'lien';
  }
</script>

<div class="min-w-0 space-y-1.5 text-sm leading-relaxed text-ink-primary">
  <!-- Clave par rang, pas par contenu. Deux blocs identiques, ne serait-ce que
       deux separateurs ou deux paragraphes de meme longueur, donnaient la meme
       cle : Svelte levait `each_key_duplicate`, et la levee emportait le rendu
       de toute la conversation, ecran vide et sans message d'erreur. Les blocs
       ne portent aucun etat propre et la liste est recalculee a chaque texte :
       il n'y a rien a preserver qu'une identite de contenu justifierait. -->
  {#each blocs as bloc, rang (rang)}
    {#if bloc.t === 'titre'}
      {#if bloc.niveau === 1}
        <p class="pt-1 text-base font-semibold">
          {#each bloc.segments as s}{@render segment(s)}{/each}
        </p>
      {:else}
        <p class="pt-1 text-sm font-semibold text-ink-secondary">
          {#each bloc.segments as s}{@render segment(s)}{/each}
        </p>
      {/if}
    {:else if bloc.t === 'paragraphe'}
      <p class="[overflow-wrap:anywhere]">
        {#each bloc.segments as s}{@render segment(s)}{/each}
      </p>
    {:else if bloc.t === 'liste'}
      {#if bloc.ordonnee}
        <ol class="ml-5 list-decimal space-y-0.5">
          {#each bloc.items as item}
            <li>
              {#each item as s}{@render segment(s)}{/each}
            </li>
          {/each}
        </ol>
      {:else}
        <ul class="ml-5 list-disc space-y-0.5">
          {#each bloc.items as item}
            <li>
              {#each item as s}{@render segment(s)}{/each}
            </li>
          {/each}
        </ul>
      {/if}
    {:else if bloc.t === 'citation'}
      <blockquote class="border-l-2 border-border pl-3 text-ink-secondary italic">
        {#each bloc.segments as s}{@render segment(s)}{/each}
      </blockquote>
    {:else if bloc.t === 'code'}
      <!-- Le code defile dans son cadre plutot que de revenir a la ligne : une
           ligne de code coupee change de sens. Le cadre, lui, ne deborde pas. -->
      <div class="relative">
        <pre
          class="max-h-[60vh] overflow-auto rounded bg-surface-tertiary p-2 pr-16 font-mono text-xs text-ink-secondary">{bloc.texte}</pre>
        <CopierBouton texte={bloc.texte} class="absolute right-1 top-1 bg-surface-tertiary" />
      </div>
    {:else if bloc.t === 'tableau'}
      <div class="overflow-x-auto rounded border border-border">
        <table class="w-full border-collapse text-xs">
          <thead class="bg-surface-tertiary">
            <tr>
              {#each bloc.entetes as cellule}
                <th class="border-b border-border px-2 py-1 text-left font-semibold">
                  {#each cellule as s}{@render segment(s)}{/each}
                </th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each bloc.lignes as ligne}
              <tr class="border-b border-border last:border-0">
                {#each ligne as cellule}
                  <td class="px-2 py-1 align-top">
                    {#each cellule as s}{@render segment(s)}{/each}
                  </td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {:else if bloc.t === 'separateur'}
      <hr class="border-border" />
    {/if}
  {/each}
</div>

{#snippet segment(s: Segment)}
  {#if s.t === 'texte'}
    {s.texte}
  {:else if s.t === 'code'}
    <code class="rounded bg-surface-tertiary px-1 py-0.5 font-mono text-xs">{s.code}</code>
  {:else if s.t === 'gras'}
    <strong class="font-semibold">{s.texte}</strong>
  {:else if s.t === 'italique'}
    <em>{s.texte}</em>
  {:else if estLien(s)}
    <a href={s.href} target="_blank" rel="noopener noreferrer" class="underline hover:opacity-80"
      >{s.texte}</a
    >
  {/if}
{/snippet}
