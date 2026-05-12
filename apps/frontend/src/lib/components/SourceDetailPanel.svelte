<script lang="ts">
  import type { CardDetail, Source } from '$lib/api'
  import { SOURCE_COLORS } from '$lib/utils/source-colors'
  import SourceTypeBadge from './SourceTypeBadge.svelte'

  interface Props {
    source: Source | null
    card: CardDetail
    onClose: () => void
    onSelect: (source: Source) => void
  }

  let { source, card, onClose, onSelect }: Props = $props()

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && source) {
      onClose()
    }
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

  const authorityLabel: Record<string, string> = {
    high: 'Autorité élevée',
    medium: 'Autorité moyenne',
    low: 'Autorité faible'
  }

  const parent = $derived(parentOf(source))
  const publishedDate = $derived(formatPublishedDate(source?.published_at ?? null))
</script>

<svelte:window onkeydown={handleKeydown} />

{#if source}
  <!-- Overlay (click closes on mobile, no-op on desktop because pointer-events-none on md+) -->
  <button
    type="button"
    class="fixed inset-0 z-40 bg-slate-900/30 md:bg-transparent md:pointer-events-none"
    aria-label="Fermer le panneau"
    onclick={onClose}
  ></button>

  <div
    class="fixed z-50 bg-white shadow-2xl border-slate-200 overflow-y-auto
      inset-x-0 bottom-0 max-h-[85vh] rounded-t-2xl border-t
      md:inset-y-0 md:right-0 md:left-auto md:bottom-auto md:max-h-none md:w-full md:max-w-md md:rounded-none md:border-l md:border-t-0
      animate-in"
    role="dialog"
    aria-modal="true"
    aria-labelledby="source-panel-title"
  >
    <div class="p-6">
      <div class="flex items-start justify-between gap-3 mb-4">
        <div class="flex items-center gap-2">
          <SourceTypeBadge type={source.source_type} size="md" />
          <span
            class="inline-flex items-center text-xs text-slate-600 px-2 py-0.5 rounded-full border border-slate-200"
          >
            {authorityLabel[source.authority_level] ?? source.authority_level}
          </span>
          {#if source.is_pivot}
            <span
              class="inline-flex items-center text-xs text-amber-800 bg-amber-100 px-2 py-0.5 rounded-full"
              title="Source pivot du raisonnement"
            >
              ★ Pivot
            </span>
          {/if}
        </div>
        <button
          type="button"
          onclick={onClose}
          class="text-slate-500 hover:text-slate-900 transition-colors"
          aria-label="Fermer"
        >
          <svg viewBox="0 0 24 24" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="6" y1="6" x2="18" y2="18" />
            <line x1="6" y1="18" x2="18" y2="6" />
          </svg>
        </button>
      </div>

      <h2 id="source-panel-title" class="text-2xl font-serif text-slate-900 leading-tight">
        {source.title ?? source.url}
      </h2>

      <div class="mt-3 text-sm text-slate-600 space-y-0.5">
        {#if source.authors}
          <p>{source.authors}</p>
        {/if}
        {#if publishedDate}
          <p class="text-slate-500">Publié le {publishedDate}</p>
        {/if}
      </div>

      {#if source.annotation}
        <p
          class="mt-5 text-sm text-slate-700 italic leading-relaxed border-l-2 pl-3"
          style:border-color={SOURCE_COLORS[source.source_type].stroke}
        >
          {source.annotation}
        </p>
      {/if}

      <div class="mt-6 flex flex-col gap-2">
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
        >
          Voir la source
          <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M7 17L17 7" />
            <path d="M7 7h10v10" />
          </svg>
        </a>
        {#if source.archive_url}
          <a
            href={source.archive_url}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            Voir l'archive (Wayback)
          </a>
        {/if}
      </div>

      {#if parent}
        <div class="mt-6 pt-4 border-t border-slate-200">
          <p class="text-xs uppercase tracking-wide text-slate-500 mb-1">
            Cite cette source
          </p>
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
  </div>
{/if}
