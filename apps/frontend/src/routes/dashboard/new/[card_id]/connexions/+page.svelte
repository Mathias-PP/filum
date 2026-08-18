<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
  import type { CardConnection, CardConnections } from '$lib/api/types';

  const wizardSteps = [
    { label: 'Informations', description: 'Titre, plateforme', clickable: true },
    { label: 'Sources', description: 'Ajouter et publier', clickable: true },
    { label: 'Connexions', description: 'Fiches liées' },
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
  const rienASignaler = $derived(
    !loading &&
      !error &&
      data !== null &&
      suggestions.length === 0 &&
      confirmed.length === 0 &&
      data.incoming.length === 0
  );

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

<!--
  Wrapper `max-w-3xl mx-auto` identique aux etapes 1 et 2 du parcours :
  sans lui, `ProgressSteps` (dont chaque item est en `flex-1`) prenait toute
  la largeur de la fenetre et decalait « Informations » a l'extreme gauche
  des l'ouverture de cette page.
-->
<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
      >← Tableau de bord</a
    >
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-1">Connexions entre fiches</h1>
  <p class="text-sm text-ink-secondary mb-6">
    Quand une de vos sources pointe vers une fiche Philum publiée, un lien vers cette fiche est
    proposé automatiquement. Vous confirmez, retirez, ou laissez la proposition en attente.
  </p>

  <ProgressSteps steps={wizardSteps} current={2} onStepClick={onWizardStepClick} class="mb-8" />

  <div class="space-y-8">
    {#if loading}
      <p class="text-sm text-ink-tertiary">Chargement…</p>
    {:else if error}
      <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
        {error}
      </div>
    {:else if data}
      {#if suggestions.length > 0}
        <section class="rounded-xl border border-warning/30 bg-warning-bg p-4">
          <h2 class="mb-3 text-sm font-semibold text-warning">
            {suggestions.length} suggestion{suggestions.length > 1 ? 's' : ''} à examiner
          </h2>
          <ul class="space-y-2">
            {#each suggestions as c (c.source_id)}
              <li
                class="flex items-start gap-3 rounded-lg border border-border bg-surface-primary p-3"
              >
                <div class="flex-1 min-w-0">
                  <p class="text-sm font-medium text-ink-primary truncate">
                    {c.card_title}
                  </p>
                  <p class="text-xs text-ink-tertiary truncate">
                    Depuis votre source : {c.source_title ?? c.source_url}
                  </p>
                </div>
                <Button variant="primary" size="sm" onclick={() => confirm(c)}>Confirmer</Button>
                <Button variant="secondary" size="sm" onclick={() => remove(c)}>Retirer</Button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      {#if confirmed.length > 0}
        <section>
          <h2 class="mb-2 text-sm font-semibold text-ink-primary">Fiches que vous citez</h2>
          <ul class="divide-y divide-border rounded-xl border border-border bg-surface-primary">
            {#each confirmed as c (c.source_id)}
              <li class="flex items-center gap-3 p-3">
                <a
                  class="flex-1 min-w-0 text-sm font-medium text-info hover:underline truncate"
                  href="/@{c.card_creator_slug}/{c.card_slug}"
                >
                  {c.card_title}
                </a>
                <Button variant="ghost" size="sm" onclick={() => remove(c)}>Retirer</Button>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      {#if data.incoming.length > 0}
        <section>
          <h2 class="mb-1 text-sm font-semibold text-ink-primary">Fiches qui vous citent</h2>
          <p class="mb-3 text-xs text-ink-tertiary">
            Ces connexions appartiennent à la bibliographie d'autres créateurs — vous les voyez,
            vous ne pouvez pas les modifier.
          </p>
          <ul class="divide-y divide-border rounded-xl border border-border bg-surface-primary">
            {#each data.incoming as c (c.source_id)}
              <li class="p-3">
                <p class="text-sm font-medium text-ink-primary">{c.card_title}</p>
                <p class="text-xs text-ink-tertiary">{c.source_title ?? c.source_url}</p>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      {#if rienASignaler}
        <!--
          Etat vide explicite : sans lui, l'ecran affiche juste titre + description
          + une nav en haut, et le createur se demande a quoi sert cette etape.
          Dire ici *pourquoi* c'est vide et *quand* ca se remplira lui donne le
          moyen de continuer sans se poser la question.
        -->
        <div class="rounded-xl border border-border bg-surface-secondary p-6 text-center space-y-2">
          <p class="text-sm text-ink-secondary">Aucune connexion à signaler pour cette fiche.</p>
          <p class="text-xs text-ink-tertiary">
            Une suggestion apparaît automatiquement dès qu'une de vos sources pointe vers une fiche
            Philum déjà publiée, ou dès qu'une autre fiche cite l'une de vos sources.
          </p>
        </div>
      {/if}
    {/if}
  </div>

  {#if undo}
    <div
      class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-md bg-ink-primary px-4 py-2 text-sm text-surface-primary shadow-lg"
      role="status"
    >
      Connexion retirée vers <strong>{undo.title}</strong>.
    </div>
  {/if}
</div>
