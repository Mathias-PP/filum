<script lang="ts">
  import { onMount } from 'svelte'
  import { auth, currentUser, cards, publishedCards, draftCards } from '$lib/stores'
  import { api } from '$lib/api'
  import { Button, Card, Avatar } from '$lib/components'
  import type { Card as CardType } from '$lib/api'

  let loading = $state(true)
  let userCards = $state<CardType[]>([])

  onMount(async () => {
    try {
      const response = await api.cards.list()
      userCards = response
    } catch (error) {
      console.error('Failed to load cards:', error)
    } finally {
      loading = false
    }
  })
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
    <Button href="/dashboard/new">
      Nouvelle fiche
    </Button>
  </div>

  {#if loading}
    <div class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  {:else if userCards.length === 0}
    <div class="text-center py-12">
      <div class="w-16 h-16 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
        <svg class="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <h2 class="text-xl font-semibold text-slate-900 mb-2">Aucune fiche</h2>
      <p class="text-slate-600 mb-6">Commencez par créer votre première fiche bibliographique.</p>
      <Button href="/dashboard/new">
        Créer ma première fiche
      </Button>
    </div>
  {:else}
    <div class="space-y-6">
      <section>
        <h2 class="text-lg font-semibold text-slate-900 mb-4">Brouillons</h2>
        {#if userCards.filter(c => c.status === 'draft').length === 0}
          <p class="text-slate-500">Aucun brouillon</p>
        {:else}
          <div class="grid gap-4">
            {#each userCards.filter(c => c.status === 'draft') as card}
              <a href="/dashboard/cards/{card.id}" class="card hover:shadow-md transition-shadow">
                <div class="flex items-center justify-between">
                  <div>
                    <h3 class="font-semibold text-slate-900">{card.title}</h3>
                    <p class="text-sm text-slate-500">Créé le {new Date(card.created_at).toLocaleDateString('fr-FR')}</p>
                  </div>
                  <span class="badge bg-slate-100 text-slate-700">Brouillon</span>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      </section>

      <section>
        <h2 class="text-lg font-semibold text-slate-900 mb-4">Publiées</h2>
        {#if userCards.filter(c => c.status === 'published').length === 0}
          <p class="text-slate-500">Aucune fiche publiée</p>
        {:else}
          <div class="grid gap-4">
            {#each userCards.filter(c => c.status === 'published') as card}
              <a href="/@{$currentUser?.username}/{card.slug}" class="card hover:shadow-md transition-shadow">
                <div class="flex items-center justify-between">
                  <div>
                    <h3 class="font-semibold text-slate-900">{card.title}</h3>
                    <p class="text-sm text-slate-500">Publiée le {new Date(card.published_at || card.created_at).toLocaleDateString('fr-FR')}</p>
                  </div>
                  <span class="badge bg-emerald-100 text-emerald-800">Publiée</span>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>
