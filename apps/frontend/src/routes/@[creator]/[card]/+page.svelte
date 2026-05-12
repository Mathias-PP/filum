<script lang="ts">
  import { page } from '$app/stores'
  import { api } from '$lib/api'
  import { Avatar, SourceTypeBadge, Button, Card } from '$lib/components'
  import type { CardDetail, Source } from '$lib/api'

  let card = $state<CardDetail | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let expandedSource = $state<string | null>(null)

  const creatorSlug = $page.params.creator ?? ''
  const cardSlug = $page.params.card ?? ''

  $effect(() => {
    loadCard()
  })

  async function loadCard() {
    try {
      card = await api.cards.getPublic(creatorSlug, cardSlug)
    } catch (e) {
      error = 'Fiche non trouvée'
    } finally {
      loading = false
    }
  }

  function toggleSource(sourceId: string) {
    expandedSource = expandedSource === sourceId ? null : sourceId
  }

  function copyLink() {
    navigator.clipboard.writeText(window.location.href)
  }
</script>

<svelte:head>
  <title>{card?.title || 'Fiche'} - Filum</title>
</svelte:head>

<div class="min-h-screen bg-slate-50">
  {#if loading}
    <div class="flex justify-center items-center min-h-[50vh]">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    </div>
  {:else if error || !card}
    <div class="max-w-4xl mx-auto px-4 py-16 text-center">
      <h1 class="text-2xl font-bold text-slate-900 mb-4">Fiche non trouvée</h1>
      <p class="text-slate-600 mb-6">Cette fiche n'existe pas ou a été supprimée.</p>
      <Button href="/">Retour à l'accueil</Button>
    </div>
  {:else}
    <article class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <header class="mb-8">
        <p class="text-sm text-slate-500 mb-2">
          fiche bibliographique · filum.app/@{creatorSlug}/{cardSlug}
        </p>
        <h1 class="text-3xl md:text-4xl font-bold text-slate-900 mb-4 font-serif">
          {card.title}
        </h1>

        <div class="flex items-center gap-4 mb-6">
          <a href="/@{creatorSlug}" class="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <Avatar
              avatarUrl={card.creator.avatar_url}
              name={card.creator.display_name || card.creator.slug}
              size="lg"
              verified={true}
            />
            <div>
              <p class="font-medium text-slate-900">{card.creator.display_name || card.creator.slug}</p>
              <p class="text-sm text-slate-500">@{card.creator.slug}</p>
            </div>
          </a>
          <span class="badge-verified">
            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
            </svg>
            Vérifié Google
          </span>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div class="text-center p-4 bg-white rounded-lg border border-slate-200">
            <p class="text-2xl font-bold text-slate-900">{card.stats.total_sources}</p>
            <p class="text-sm text-slate-500">Sources</p>
          </div>
          <div class="text-center p-4 bg-white rounded-lg border border-slate-200">
            <p class="text-2xl font-bold text-emerald-600">{card.stats.peer_reviewed}</p>
            <p class="text-sm text-slate-500">Peer-reviewed</p>
          </div>
          <div class="text-center p-4 bg-white rounded-lg border border-slate-200">
            <p class="text-2xl font-bold text-blue-600">{card.stats.institutional}</p>
            <p class="text-sm text-slate-500">Institutionnels</p>
          </div>
          <div class="text-center p-4 bg-white rounded-lg border border-slate-200">
            <p class="text-2xl font-bold text-slate-600">{card.stats.all_archived ? '✓' : '...'}</p>
            <p class="text-sm text-slate-500">Archivés</p>
          </div>
        </div>
      </header>

      <section class="mb-8">
        <h2 class="text-xl font-semibold text-slate-900 mb-4">Sources</h2>
        <div class="space-y-3">
          {#each card.sources as source, i}
            <div class="bg-white rounded-lg border border-slate-200 overflow-hidden">
              <button
                type="button"
                class="w-full text-left p-4 hover:bg-slate-50 transition-colors"
                onclick={() => toggleSource(source.id)}
              >
                <div class="flex items-start gap-3">
                  <span class="text-slate-400 font-medium">{i + 1}.</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <h3 class="font-medium text-slate-900 truncate">{source.title || 'Sans titre'}</h3>
                      <SourceTypeBadge type={source.source_type} />
                      {#if source.is_pivot}
                        <span class="px-2 py-0.5 text-xs bg-amber-100 text-amber-800 rounded-full">Source pivot</span>
                      {/if}
                    </div>
                    {#if source.authors}
                      <p class="text-sm text-slate-500 mt-1">{source.authors}</p>
                    {/if}
                    <p class="text-sm text-blue-600 mt-1 truncate">{source.url}</p>
                  </div>
                  {#if expandedSource === source.id}
                    <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                    </svg>
                  {:else}
                    <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                    </svg>
                  {/if}
                </div>
              </button>

              {#if expandedSource === source.id}
                <div class="px-4 pb-4 border-t border-slate-100">
                  {#if source.annotation}
                    <div class="mt-4 p-3 bg-slate-50 rounded-lg text-sm text-slate-700">
                      <p class="font-medium text-slate-900 mb-1">Annotation :</p>
                      <p>{source.annotation}</p>
                    </div>
                  {/if}
                  <div class="mt-4 flex flex-wrap gap-2">
                    {#if source.archive_url}
                      <a href={source.archive_url} target="_blank" rel="noopener" class="btn-secondary text-sm">
                        <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Voir l'archive
                      </a>
                    {/if}
                    <a href={source.url} target="_blank" rel="noopener" class="btn-secondary text-sm">
                      <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                      </svg>
                      Version live
                    </a>
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </section>

      <footer class="border-t border-slate-200 pt-6">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-2">
            <button onclick={copyLink} class="btn-secondary text-sm">
              <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3" />
              </svg>
              Copier le lien
            </button>
          </div>
          <div class="text-sm text-slate-500">
            <p>Signé le {card.signed_at ? new Date(card.signed_at).toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' }) : 'N/A'}</p>
            <p class="text-xs">Vérifiable via l'API</p>
          </div>
        </div>
      </footer>
    </article>
  {/if}
</div>
