<script lang="ts">
  import { untrack } from 'svelte';
  import Button from '../Button.svelte';
  import type { ReponseGuidee } from '$lib/api/agent';

  interface Props {
    genre: 'precision' | 'plan';
    question: string;
    options: string[];
    sousQuestions: string[];
    resolue: boolean;
    reponse: ReponseGuidee | null;
    onrepondre: (reponse: ReponseGuidee) => Promise<void> | void;
  }

  let { genre, question, options, sousQuestions, resolue, reponse, onrepondre }: Props = $props();

  let envoi = $state(false);
  let autre = $state('');
  // Copie de travail : le créateur corrige le plan avant de lancer la recherche.
  let plan = $state<string[]>(untrack(() => [...sousQuestions]));

  async function repondre(valeur: ReponseGuidee) {
    envoi = true;
    try {
      await onrepondre(valeur);
    } finally {
      envoi = false;
    }
  }

  function retirer(rang: number) {
    plan = plan.filter((_, i) => i !== rang);
  }

  const planPropre = $derived(plan.map((q) => q.trim()).filter(Boolean));
</script>

<div class="rounded-lg border border-info/40 bg-surface-secondary px-4 py-3 text-sm">
  <p class="font-medium text-ink-primary">{question}</p>

  {#if resolue}
    <p class="mt-2 text-xs text-ink-tertiary">
      {#if genre === 'precision'}
        {reponse?.choix
          ? `Précision retenue : ${reponse.choix}`
          : 'Sans réponse : la fiche prend l’angle le plus large.'}
      {:else}
        {reponse?.sous_questions?.length
          ? 'Plan validé, la recherche est lancée.'
          : 'Sans réponse : la recherche suit le plan proposé.'}
      {/if}
    </p>
  {:else if genre === 'precision'}
    <div class="mt-3 flex flex-wrap gap-2">
      {#each options as option, rang (rang)}
        <Button
          size="sm"
          variant="secondary"
          loading={envoi}
          onclick={() => repondre({ choix: option })}>{option}</Button
        >
      {/each}
    </div>
    <form
      class="mt-3 flex gap-2"
      onsubmit={(e) => {
        e.preventDefault();
        if (autre.trim()) void repondre({ choix: autre.trim() });
      }}
    >
      <input
        bind:value={autre}
        aria-label="Autre précision"
        placeholder="Autre précision"
        class="min-w-0 flex-1 rounded border border-border bg-surface-primary px-2 py-1 text-sm"
      />
      <Button size="sm" type="submit" disabled={!autre.trim()} loading={envoi}>Préciser</Button>
    </form>
    <p class="mt-2 text-xs text-ink-tertiary">
      Sans réponse sous 5 minutes, la fiche prend l’angle le plus large.
    </p>
  {:else}
    <ol class="mt-3 space-y-2">
      {#each plan as _, rang (rang)}
        <li class="flex items-center gap-2">
          <span class="w-5 shrink-0 text-right text-xs text-ink-tertiary">{rang + 1}.</span>
          <input
            bind:value={plan[rang]}
            aria-label={`Sous-question ${rang + 1}`}
            class="min-w-0 flex-1 rounded border border-border bg-surface-primary px-2 py-1 text-sm"
          />
          <button
            type="button"
            class="rounded px-1.5 py-0.5 text-xs text-ink-tertiary hover:bg-surface-tertiary hover:text-danger"
            aria-label={`Retirer la sous-question ${rang + 1}`}
            onclick={() => retirer(rang)}>Retirer</button
          >
        </li>
      {/each}
    </ol>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <Button size="sm" variant="ghost" onclick={() => (plan = [...plan, ''])}
        >Ajouter une sous-question</Button
      >
      <span class="flex-1"></span>
      <Button
        size="sm"
        loading={envoi}
        disabled={planPropre.length === 0}
        onclick={() => repondre({ sous_questions: planPropre })}>Lancer la recherche</Button
      >
    </div>
    <p class="mt-2 text-xs text-ink-tertiary">
      Sans réponse sous 5 minutes, la recherche suit le plan proposé.
    </p>
  {/if}
</div>
