<script lang="ts">
  import type { CardDetail, Source } from '$lib/api'
  import { SOURCE_COLORS } from '$lib/utils/source-colors'
  import SourceTypeBadge from './SourceTypeBadge.svelte'

  interface Anchor {
    x: number
    y: number
  }

  interface Props {
    source: Source | null
    card: CardDetail
    anchor?: Anchor | null
    containerWidth?: number
    containerHeight?: number
    onClose: () => void
    onSelect: (source: Source) => void
  }

  let {
    source,
    card,
    anchor = null,
    containerWidth = 800,
    containerHeight = 560,
    onClose,
    onSelect
  }: Props = $props()

  const PANEL_WIDTH = 320
  const PANEL_HEIGHT_EST = 420
  const MARGIN = 12

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && source) onClose()
  }

  function parentOf(s: Source | null): Source | null {
    if (!s || !s.parent_source_id) return null
    return card.sources.find((x) => x.id === s.parent_source_id) ?? null
  }

  function formatPublishedDate(value: string | null): string | null {
    if (!value) return null
    try {
      return new Date(value).toLocaleDateString('fr-FR', { dateStyle: 'long' })
    } catch {
      return null
    }
  }

  function formatCount(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`
    if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}k`
    return n.toLocaleString('fr-FR')
  }

  const parent = $derived(parentOf(source))
  const publishedDate = $derived(formatPublishedDate(source?.published_at ?? null))
  const isMobile = $derived(containerWidth < 600)

  const panelStyle = $derived.by(() => {
    if (!anchor || isMobile) return ''
    const onLeftHalf = anchor.x < containerWidth / 2
    let left = onLeftHalf ? anchor.x + 24 : anchor.x - PANEL_WIDTH - 24
    left = Math.max(MARGIN, Math.min(containerWidth - PANEL_WIDTH - MARGIN, left))
    let top = anchor.y - PANEL_HEIGHT_EST / 2
    top = Math.max(MARGIN, Math.min(containerHeight - PANEL_HEIGHT_EST - MARGIN, top))
    return `left:${left}px; top:${top}px; width:${PANEL_WIDTH}px;`
  })
</script>

<svelte:window onkeydown={handleKeydown} />

{#if source}
  {#if isMobile}
    <button
      type="button"
      class="absolute inset-0 z-40 bg-slate-900/30"
      aria-label="Fermer le panneau"
      onclick={onClose}
    ></button>
    <div
      class="absolute z-50 left-0 right-0 bottom-0 max-h-[80%] overflow-y-auto bg-white rounded-t-2xl border-t border-slate-200 shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="source-panel-title"
    >
      {@render panelContent()}
    </div>
  {:else}
    <div
      class="absolute z-50 bg-white shadow-xl border border-slate-200 rounded-xl overflow-y-auto max-h-[85%]"
      style={panelStyle}
      role="dialog"
      aria-modal="false"
      aria-labelledby="source-panel-title"
    >
      {@render panelContent()}
    </div>
  {/if}
{/if}

{#snippet panelContent()}
  {#if source}
    <div class="p-4">
      <div class="flex items-start justify-between gap-2 mb-3">
        <div class="flex items-center gap-1.5 flex-wrap">
          <SourceTypeBadge type={source.source_type} size="sm" />
          {#if source.is_pivot}
            <span
              class="inline-flex items-center text-xs text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full"
              title="Source structurante du raisonnement"
            >
              ★ Source clé
            </span>
          {/if}

        </div>
        <button
          type="button"
          onclick={onClose}
          class="text-slate-500 hover:text-slate-900 transition-colors shrink-0"
          aria-label="Fermer"
        >
          <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="6" y1="6" x2="18" y2="18" />
            <line x1="6" y1="18" x2="18" y2="6" />
          </svg>
        </button>
      </div>

      <h2 id="source-panel-title" class="text-lg font-serif text-slate-900 leading-snug">
        {source.title ?? source.url}
      </h2>

      <div class="mt-2 text-sm text-slate-600 space-y-0.5">
        {#if source.authors}
          <p>{source.authors}</p>
        {/if}
        {#if publishedDate}
          <p class="text-slate-500">Publié le {publishedDate}</p>
        {/if}
      </div>

      <!-- Structured indicators -->
      {#if source.citations_count || source.impact_factor || source.subscribers_count || source.views_count}
        <div class="mt-3 flex flex-wrap gap-1.5">
          {#if source.citations_count}
            <span class="inline-flex items-center text-xs text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
              {formatCount(source.citations_count)} citations
            </span>
          {/if}
          {#if source.impact_factor}
            <span class="inline-flex items-center text-xs text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
              Impact factor {source.impact_factor.toFixed(1)}
            </span>
          {/if}
          {#if source.subscribers_count}
            <span class="inline-flex items-center text-xs text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
              {formatCount(source.subscribers_count)} abonnés
            </span>
          {/if}
          {#if source.views_count}
            <span class="inline-flex items-center text-xs text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
              {formatCount(source.views_count)} vues
            </span>
          {/if}
        </div>
      {/if}

      {#if source.annotation}
        <p
          class="mt-4 text-sm text-slate-700 italic leading-relaxed border-l-2 pl-3"
          style:border-color={SOURCE_COLORS[source.source_type].stroke}
        >
          {source.annotation}
        </p>
      {/if}

      {#if source.excerpts && source.excerpts.length > 0}
        <div class="mt-4">
          <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">Extraits cités</p>
          <div class="flex gap-2 overflow-x-auto snap-x pb-1 -mx-1 px-1">
            {#each source.excerpts as excerpt (excerpt.id)}
              <div
                class="relative shrink-0 snap-start w-64 max-h-32 overflow-y-auto bg-slate-50 border border-slate-200 rounded-md p-3 text-sm text-slate-700 italic"
              >
                {#if excerpt.suggested_by_ai}
                  <span
                    class="absolute top-1 right-2 text-xs text-slate-400"
                    title="Extrait suggéré par IA"
                  >
                    ✨
                  </span>
                {/if}
                «&nbsp;{excerpt.text}&nbsp;»
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="mt-4 flex flex-col gap-2">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
        >
          Voir la source
          <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M7 17L17 7" />
            <path d="M7 7h10v10" />
          </svg>
        </a>
        {#if source.archive_url}
          <div class="flex flex-col gap-0.5">
            <a
              href={source.archive_url}
              target="_blank"
              rel="noopener noreferrer"
              class="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
            >
              Voir l'archive
            </a>
            <span class="text-xs text-slate-500 text-center">Snapshot horodaté</span>
          </div>
        {/if}
      </div>

      {#if parent}
        <div class="mt-4 pt-3 border-t border-slate-200">
          <p class="text-xs uppercase tracking-wide text-slate-500 mb-1">Cite cette source</p>
          <button
            type="button"
            class="text-left text-sm text-blue-700 hover:underline"
            onclick={() => onSelect(parent)}
          >
            {parent.title ?? parent.url}
          </button>
        </div>
      {/if}
    </div>
  {/if}
{/snippet}
