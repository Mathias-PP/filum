<script lang="ts">
  import { page } from '$app/stores'
  import { api } from '$lib/api'
  import type { CardDetail, Source } from '$lib/api'
  import {
    Avatar,
    Button,
    SourceDetailPanel,
    SourceGraph,
    SourceTypeBadge
  } from '$lib/components'

  let card = $state<CardDetail | null>(null)
  let loading = $state(true)
  let error = $state<string | null>(null)
  let expandedSource = $state<string | null>(null)
  let selectedSource = $state<Source | null>(null)

  const creatorSlug = $page.params.creator ?? ''
  const cardSlug = $page.params.card ?? ''

  $effect(() => {
    loadCard()
  })

  async function loadCard() {
    try {
      card = await api.cards.getPublic(creatorSlug, cardSlug)
    } catch {
      error = 'Fiche non trouvée'
    } finally {
      loading = false
    }
  }

  function toggleSource(sourceId: string) {
    expandedSource = expandedSource === sourceId ? null : sourceId
  }

  function copyLink() {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href)
    }
  }
</script>

<svelte:head>
  <title>{card?.title || 'Fiche'} — Filum</title>
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
    <article>
      <!-- Slim sticky header -->
      <header class="bg-white border-b border-slate-200">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div class="flex items-center gap-3">
            <a
              href="/@{creatorSlug}"
              class="flex items-center gap-2 hover:opacity-80 transition-opacity"
            >
              <Avatar
                avatarUrl={card.creator.avatar_url}
                name={card.creator.display_name || card.creator.slug}
                size="sm"
                verified={true}
              />
              <span class="text-sm font-medium text-slate-700 hidden sm:inline"
                >{card.creator.display_name || card.creator.slug}</span
              >
            </a>
            <div class="flex-1 min-w-0">
              <h1
                class="text-base sm:text-lg font-serif text-slate-900 truncate"
                title={card.title}
              >
                {card.title}
              </h1>
            </div>
            <button
              type="button"
              onclick={copyLink}
              class="text-xs sm:text-sm text-slate-600 hover:text-slate-900 transition-colors px-3 py-1.5 rounded-md border border-slate-200 hover:border-slate-300"
            >
              Partager
            </button>
          </div>
        </div>
      </header>

      <!-- Hero: interactive graph above the fold -->
      <section class="bg-slate-50">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div
            class="h-[68vh] min-h-[460px] rounded-xl bg-white border border-slate-200 overflow-hidden relative"
          >
            <SourceGraph {card} onSelect={(s) => (selectedSource = s)} />
          </div>
          <p class="text-center text-xs sm:text-sm text-slate-500 mt-3">
            Cliquez sur un nœud pour explorer la source · glissez pour réorganiser · molette pour zoomer
          </p>
        </div>
      </section>

      <!-- Stats -->
      <section class="bg-white border-t border-b border-slate-200">
        <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            <div class="text-center p-3 sm:p-4 bg-slate-50 rounded-lg">
              <p class="text-xl sm:text-2xl font-bold text-slate-900">
                {card.stats.total_sources}
              </p>
              <p class="text-xs sm:text-sm text-slate-500">Sources</p>
            </div>
            <div class="text-center p-3 sm:p-4 bg-slate-50 rounded-lg">
              <p class="text-xl sm:text-2xl font-bold text-emerald-600">
                {card.stats.peer_reviewed}
              </p>
              <p class="text-xs sm:text-sm text-slate-500">Peer-reviewed</p>
            </div>
            <div class="text-center p-3 sm:p-4 bg-slate-50 rounded-lg">
              <p class="text-xl sm:text-2xl font-bold text-blue-600">
                {card.stats.institutional}
              </p>
              <p class="text-xs sm:text-sm text-slate-500">Institutionnels</p>
            </div>
            <div class="text-center p-3 sm:p-4 bg-slate-50 rounded-lg">
              <p class="text-xl sm:text-2xl font-bold text-slate-700">
                {card.stats.all_archived ? '✓' : '…'}
              </p>
              <p class="text-xs sm:text-sm text-slate-500">Archivés</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Description -->
      {#if card.description}
        <section class="bg-white">
          <div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <p class="text-base text-slate-700 leading-relaxed">
              {card.description}
            </p>
          </div>
        </section>
      {/if}

      <!-- Editorial list -->
      <section class="bg-slate-50 border-t border-slate-200">
        <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <h2 class="text-xl font-semibold text-slate-900 mb-4">Liste éditoriale</h2>
          <div class="space-y-3">
            {#each card.sources as source, i (source.id)}
              <div class="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <button
                  type="button"
                  class="w-full text-left p-4 hover:bg-slate-50 transition-colors"
                  onclick={() => toggleSource(source.id)}
                >
                  <div class="flex items-start gap-3">
                    <span class="text-slate-400 font-medium tabular-nums">{i + 1}.</span>
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 flex-wrap">
                        <h3 class="font-medium text-slate-900">
                          {source.title || 'Sans titre'}
                        </h3>
                        <SourceTypeBadge type={source.source_type} />
                        {#if source.is_pivot}
                          <span
                            class="px-2 py-0.5 text-xs bg-amber-100 text-amber-800 rounded-full"
                          >
                            ★ Pivot
                          </span>
                        {/if}
                      </div>
                      {#if source.authors}
                        <p class="text-sm text-slate-500 mt-1">{source.authors}</p>
                      {/if}
                      <p class="text-sm text-blue-600 mt-1 truncate">{source.url}</p>
                    </div>
                    <svg
                      class="w-5 h-5 text-slate-400 shrink-0 transition-transform {expandedSource ===
                      source.id
                        ? 'rotate-180'
                        : ''}"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
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
                        <a
                          href={source.archive_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          class="btn-secondary text-sm"
                        >
                          Voir l'archive
                        </a>
                      {/if}
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        class="btn-secondary text-sm"
                      >
                        Version live ↗
                      </a>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </section>

      <!-- Signature footer -->
      <footer class="bg-white border-t border-slate-200">
        <div
          class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-4"
        >
          <div class="text-xs text-slate-500 font-mono break-all">
            <p class="text-slate-700 font-sans font-medium not-italic mb-1">
              Signature Ed25519
            </p>
            {#if card.signature}
              {card.signature.slice(0, 32)}…{card.signature.slice(-8)}
            {:else}
              <span class="italic text-slate-400">non signée</span>
            {/if}
          </div>
          <div class="text-sm text-slate-500 text-right">
            <p>
              Signé le {card.signed_at
                ? new Date(card.signed_at).toLocaleString('fr-FR', {
                    dateStyle: 'long',
                    timeStyle: 'short'
                  })
                : 'N/A'}
            </p>
            <p class="text-xs">Vérifiable via l'API</p>
          </div>
        </div>
      </footer>
    </article>

    <SourceDetailPanel
      source={selectedSource}
      {card}
      onClose={() => (selectedSource = null)}
      onSelect={(s) => (selectedSource = s)}
    />
  {/if}
</div>
