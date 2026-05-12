<script lang="ts">
  import { page } from '$app/stores'
  import { api } from '$lib/api'
  import { Avatar, Button, Card } from '$lib/components'
  import type { UserProfile } from '$lib/api'

  let profile = $state<UserProfile | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)

  const username = $page.params.username ?? ''

  $effect(() => {
    loadProfile()
  })

  async function loadProfile() {
    try {
      profile = await api.users.getProfile(username)
    } catch (e) {
      error = 'Utilisateur non trouvé'
    } finally {
      loading = false
    }
  }
</script>

<svelte:head>
  <title>{profile?.display_name || username} - Filum</title>
</svelte:head>

<div class="min-h-screen bg-slate-50">
  {#if loading}
    <div class="flex justify-center items-center min-h-[50vh]">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  {:else if error || !profile}
    <div class="max-w-4xl mx-auto px-4 py-16 text-center">
      <h1 class="text-2xl font-bold text-slate-900 mb-4">Utilisateur non trouvé</h1>
      <p class="text-slate-600 mb-6">Ce profil n'existe pas.</p>
      <Button href="/">Retour à l'accueil</Button>
    </div>
  {:else}
    <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <header class="bg-white rounded-xl shadow-sm border border-slate-200 p-8 mb-8">
        <div class="flex items-start gap-6">
          <Avatar
            avatarUrl={profile.avatar_url}
            name={profile.display_name || profile.slug}
            size="xl"
            verified={true}
          />
          <div class="flex-1">
            <h1 class="text-3xl font-bold text-slate-900 mb-2">
              {profile.display_name || profile.slug}
            </h1>
            {#if profile.description}
              <p class="text-slate-600 mb-4">{profile.description}</p>
            {/if}
            <div class="flex flex-wrap gap-4 text-sm text-slate-500">
              <span>{profile.stats.total_cards} fiches</span>
              <span>·</span>
              <span>{profile.stats.total_sources} sources</span>
              {#if profile.stats.first_published_at}
                <span>·</span>
                <span>Depuis {new Date(profile.stats.first_published_at).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}</span>
              {/if}
            </div>
          </div>
        </div>
      </header>

      <section>
        <h2 class="text-xl font-semibold text-slate-900 mb-4">Fiches publiées</h2>
        {#if profile.cards.length === 0}
          <p class="text-slate-500">Aucune fiche publiée</p>
        {:else}
          <div class="space-y-4">
            {#each profile.cards as card}
              <a href="/@{username}/{card.slug}" class="block bg-white rounded-xl border border-slate-200 p-6 hover:shadow-md transition-shadow">
                <div class="flex items-center justify-between">
                  <div>
                    <h3 class="font-semibold text-slate-900">{card.title}</h3>
                    <p class="text-sm text-slate-500 mt-1">
                      {card.total_sources} sources
                      {#if card.published_at}
                        · Publiée le {new Date(card.published_at).toLocaleDateString('fr-FR')}
                      {/if}
                    </p>
                  </div>
                  <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </a>
            {/each}
          </div>
        {/if}
      </section>
    </div>
  {/if}
</div>
