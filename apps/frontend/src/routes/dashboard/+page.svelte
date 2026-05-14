<script lang="ts">
  import { onMount } from 'svelte';
  import { currentUser } from '$lib/stores';
  import { api } from '$lib/api';
  import { Button } from '$lib/components';
  import type { Card as CardType } from '$lib/api';

  let loading = $state(true);
  let userCards = $state<CardType[]>([]);

  async function deleteCard(id: string) {
    try {
      await api.cards.delete(id);
      userCards = userCards.filter((c) => c.id !== id);
    } catch (err) {
      console.error('Failed to delete card:', err);
    }
  }

  async function deletePublishedCard(id: string, title: string) {
    if (!confirm(`Supprimer définitivement la fiche « ${title} » ? Cette action est irréversible.`)) {
      return;
    }
    await deleteCard(id);
  }

  onMount(async () => {
    try {
      const response = await api.cards.list();
      userCards = response;
    } catch (error) {
      console.error('Failed to load cards:', error);
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>Tableau de bord - Filum</title>
</svelte:head>

<div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="flex items-center justify-between mb-8">
    <div>
      <h1 class="text-2xl font-bold text-slate-900">Tableau de bord</h1>
      <p class="text-slate-600">Gérez vos fiches bibliographiques</p>
    </div>
    <Button href="/dashboard/new">Nouvelle fiche</Button>
  </div>

  {#if loading}
    <div class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  {:else if userCards.length === 0}
    <div class="text-center py-12">
      <div
        class="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4"
      >
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>
      <h2 class="text-xl font-semibold text-slate-900 mb-2">Aucune fiche</h2>
      <p class="text-slate-600 mb-6">Commencez par créer votre première fiche bibliographique.</p>
      <Button href="/dashboard/new">Créer ma première fiche</Button>
    </div>
  {:else}
    <div class="space-y-6">
      <section>
        <h2 class="text-lg font-semibold text-slate-900 mb-4">Brouillons</h2>
        {#if userCards.filter((c) => c.status === 'draft').length === 0}
          <p class="text-slate-500">Aucun brouillon</p>
        {:else}
          <div class="grid gap-4">
            {#each userCards.filter((c) => c.status === 'draft') as card}
              <div class="card flex items-center justify-between gap-4">
                <a
                  href="/dashboard/new/{card.id}/sources"
                  class="flex-1 min-w-0 hover:opacity-80 transition-opacity"
                >
                  <h3 class="font-semibold text-slate-900 truncate">{card.title}</h3>
                  <p class="text-sm text-slate-500">
                    Créé le {new Date(card.created_at).toLocaleDateString('fr-FR')}
                  </p>
                </a>
                <div class="flex items-center gap-2 shrink-0">
                  <span class="badge bg-slate-100 text-slate-700">Brouillon</span>
                  <button
                    type="button"
                    onclick={() => deleteCard(card.id)}
                    class="text-slate-400 hover:text-red-500 transition-colors"
                    aria-label="Supprimer le brouillon"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      class="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <line x1="6" y1="6" x2="18" y2="18" />
                      <line x1="6" y1="18" x2="18" y2="6" />
                    </svg>
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <section>
        <h2 class="text-lg font-semibold text-slate-900 mb-4">Publiées</h2>
        {#if userCards.filter((c) => c.status === 'published').length === 0}
          <p class="text-slate-500">Aucune fiche publiée</p>
        {:else}
          <div class="grid gap-4">
            {#each userCards.filter((c) => c.status === 'published') as card}
              <div class="card flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div class="min-w-0">
                  <h3 class="font-semibold text-slate-900 truncate">{card.title}</h3>
                  <p class="text-sm text-slate-500">
                    Publiée le {new Date(card.published_at || card.created_at).toLocaleDateString(
                      'fr-FR'
                    )}
                  </p>
                </div>
                <div class="flex items-center gap-2 shrink-0 flex-wrap">
                  <span class="badge bg-emerald-100 text-emerald-800">Publiée</span>
                  <Button
                    href="/@{$currentUser?.username}/{card.slug}"
                    variant="secondary"
                    size="sm"
                  >
                    Voir
                  </Button>
                  <Button href="/dashboard/new/{card.id}/sources" variant="primary" size="sm">
                    Éditer
                  </Button>
                  <button
                    type="button"
                    onclick={() => deletePublishedCard(card.id, card.title)}
                    class="text-slate-400 hover:text-red-500 transition-colors p-1"
                    aria-label="Supprimer la fiche"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      class="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    >
                      <line x1="6" y1="6" x2="18" y2="18" />
                      <line x1="6" y1="18" x2="18" y2="6" />
                    </svg>
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>
