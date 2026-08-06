<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api } from '$lib/api';
  import { ProgressSteps } from '$lib/components';
  import type { CardConnection, CardConnections } from '$lib/api/types';

  const wizardSteps = [
    { label: 'Informations', description: 'Titre, plateforme', clickable: true },
    { label: 'Sources', description: 'Ajouter et publier', clickable: true },
    { label: 'Connexions', description: 'Fiches liees' },
  ];

  function onWizardStepClick(i: number) {
    if (i === 0) goto(`/dashboard/new?card_id=${cardId}`);
    if (i === 1) goto(`/dashboard/new/${cardId}/sources`);
  }

  const cardId = $derived(page.params.card_id ?? '');

  let data = $state<CardConnections | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  let undo = $state<{ sourceId: string; title: string } | null>(null);

  const suggestions = $derived(data?.outgoing.filter((c) => !c.confirmed) ?? []);
  const confirmed = $derived(data?.outgoing.filter((c) => c.confirmed) ?? []);

  async function load() {
    loading = true;
    error = null;
    try {
      data = await api.cards.connections(cardId);
    } catch {
      error = 'Impossible de charger les connexions de cette fiche.';
    } finally {
      loading = false;
    }
  }

  async function confirm(c: CardConnection) {
    await api.cards.confirmConnection(cardId, c.source_id);
    await load();
  }

  async function remove(c: CardConnection) {
    await api.cards.removeConnection(cardId, c.source_id);
    undo = { sourceId: c.source_id, title: c.card_title };
    setTimeout(() => {
      if (undo?.sourceId === c.source_id) undo = null;
    }, 8000);
    await load();
  }

  $effect(() => {
    if (cardId) void load();
  });
</script>

<svelte:head><title>Connexions de la fiche · Philum</title></svelte:head>

<ProgressSteps
  steps={wizardSteps}
  current={2}
  onStepClick={onWizardStepClick}
  class="mb-8 px-4 pt-6"
/>

<section class="mx-auto max-w-3xl space-y-8 px-4 py-8">
  <header class="space-y-2">
    <h1 class="text-2xl font-semibold text-slate-900">Connexions entre fiches</h1>
    <p class="text-slate-600">
      Une connexion relie cette fiche a une autre fiche Philum. Certaines ont ete proposees
      automatiquement parce que la reference designe le meme contenu ; a vous de les confirmer.
    </p>
  </header>

  {#if loading}
    <p class="text-slate-500">Chargement...</p>
  {:else if error}
    <p class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">{error}</p>
  {:else if data}
    {#if suggestions.length > 0}
      <div class="rounded-lg border border-amber-300 bg-amber-50 p-4">
        <h2 class="mb-3 font-medium text-amber-900">
          {suggestions.length} connexion{suggestions.length > 1 ? 's' : ''} a verifier
        </h2>
        <ul class="space-y-3">
          {#each suggestions as c (c.source_id)}
            <li class="flex items-start gap-3 rounded-md bg-white p-3">
              <div class="flex-1">
                <p class="font-medium text-slate-900">{c.card_title}</p>
                <p class="text-sm text-slate-600">
                  Proposee depuis votre reference : {c.source_title ?? c.source_url}
                </p>
              </div>
              <button
                type="button"
                class="rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-emerald-500"
                onclick={() => confirm(c)}
              >
                Confirmer
              </button>
              <button
                type="button"
                class="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400"
                onclick={() => remove(c)}
              >
                Retirer
              </button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    <div>
      <h2 class="mb-3 font-medium text-slate-900">Fiches que vous citez</h2>
      {#if confirmed.length === 0}
        <p class="text-slate-500">Aucune connexion confirmee pour le moment.</p>
      {:else}
        <ul class="divide-y divide-slate-200 rounded-lg border border-slate-200">
          {#each confirmed as c (c.source_id)}
            <li class="flex items-center gap-3 p-3">
              <a
                class="flex-1 font-medium text-indigo-700 hover:underline"
                href="/@{c.card_creator_slug}/{c.card_slug}"
              >
                {c.card_title}
              </a>
              <button
                type="button"
                class="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-slate-400"
                onclick={() => remove(c)}
              >
                Retirer
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>

    <div>
      <h2 class="mb-1 font-medium text-slate-900">Fiches qui vous citent</h2>
      <p class="mb-3 text-sm text-slate-600">
        Ces connexions appartiennent a la bibliographie d'autres createurs. Vous les voyez, vous ne
        pouvez pas les modifier.
      </p>
      {#if data.incoming.length === 0}
        <p class="text-slate-500">Personne ne cite encore cette fiche.</p>
      {:else}
        <ul class="divide-y divide-slate-200 rounded-lg border border-slate-200">
          {#each data.incoming as c (c.source_id)}
            <li class="p-3">
              <p class="font-medium text-slate-900">{c.card_title}</p>
              <p class="text-sm text-slate-600">{c.source_title ?? c.source_url}</p>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}

  {#if undo}
    <div
      class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-md bg-slate-900 px-4 py-2 text-sm text-white shadow-lg"
      role="status"
    >
      Connexion retiree vers <strong>{undo.title}</strong>.
    </div>
  {/if}
</section>
