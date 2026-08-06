<script lang="ts" module>
  /**
   * Encadré d'information d'un nœud « fiche » du graphe.
   *
   * Pendant du `SourceDetailPanel` : mêmes règles de placement et de fermeture,
   * pour qu'un clic sur une fiche et un clic sur une source se répondent. Le
   * contenu diffère parce qu'une fiche se lit autrement qu'une source — ses
   * auteurs sont ceux du contenu documenté, son créateur Philum est une
   * information distincte, et son intérêt tient au nombre de sources qu'elle
   * porte.
   */
  export interface CardPanelInfo {
    id: string;
    title: string;
    /** Auteurs du contenu documenté — jamais le créateur de la fiche. */
    authors: string | null;
    creatorName: string | null;
    creatorSlug: string;
    slug: string;
    description?: string | null;
    contentUrl?: string | null;
    publishedAt?: string | null;
    sourcesCount: number;
    /** Fiche consultée : inutile de proposer d'y naviguer. */
    isRoot: boolean;
  }
</script>

<script lang="ts">
  interface Anchor {
    x: number;
    y: number;
  }

  interface Props {
    info: CardPanelInfo | null;
    anchor?: Anchor | null;
    containerWidth?: number;
    containerHeight?: number;
    onClose: () => void;
    pinned?: boolean;
    onTogglePin?: (cardId: string) => void;
  }

  let {
    info,
    anchor = null,
    containerWidth = 800,
    containerHeight = 560,
    onClose,
    pinned = false,
    onTogglePin,
  }: Props = $props();

  const PANEL_WIDTH = 320;
  const PANEL_HEIGHT_EST = 320;
  const MARGIN = 12;

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && info) onClose();
  }

  function formatPublishedDate(value: string | null | undefined): string | null {
    if (!value) return null;
    try {
      return new Date(value).toLocaleDateString('fr-FR', { dateStyle: 'long' });
    } catch {
      return null;
    }
  }

  const publishedDate = $derived(formatPublishedDate(info?.publishedAt));
  const isMobile = $derived(containerWidth < 600);

  const panelStyle = $derived.by(() => {
    if (!anchor || isMobile) return '';
    const onLeftHalf = anchor.x < containerWidth / 2;
    let left = onLeftHalf ? anchor.x + 24 : anchor.x - PANEL_WIDTH - 24;
    left = Math.max(MARGIN, Math.min(containerWidth - PANEL_WIDTH - MARGIN, left));
    let top = anchor.y - PANEL_HEIGHT_EST / 2;
    top = Math.max(MARGIN, Math.min(containerHeight - PANEL_HEIGHT_EST - MARGIN, top));
    const maxHeight = Math.max(200, containerHeight - top - MARGIN);
    return `left:${left}px; top:${top}px; width:${PANEL_WIDTH}px; max-height:${maxHeight}px;`;
  });
</script>

<svelte:window onkeydown={handleKeydown} />

{#if info}
  {#if isMobile}
    <button
      type="button"
      class="absolute inset-0 z-40 bg-slate-900/30"
      aria-label="Fermer le panneau"
      onclick={onClose}
    ></button>
    <div
      class="panel-scroll absolute z-50 left-0 right-0 bottom-0 max-h-[80%] overflow-y-auto bg-white rounded-t-2xl border-t border-slate-200 shadow-2xl"
      role="dialog"
      aria-modal="true"
      aria-labelledby="card-panel-title"
    >
      {@render panelContent()}
    </div>
  {:else}
    <div
      class="panel-scroll absolute z-50 bg-white shadow-xl border border-slate-200 rounded-xl overflow-y-auto"
      style={panelStyle}
      role="dialog"
      aria-modal="false"
      aria-labelledby="card-panel-title"
    >
      {@render panelContent()}
    </div>
  {/if}
{/if}

{#snippet panelContent()}
  {#if info}
    <div class="p-4">
      <div class="flex items-start justify-between gap-2 mb-3">
        <span
          class="inline-flex items-center text-xs font-medium text-indigo-800 bg-indigo-100 px-2 py-0.5 rounded-full"
        >
          {info.isRoot ? 'Fiche consultée' : 'Fiche Philum'}
        </span>
        <button
          type="button"
          onclick={onClose}
          class="text-slate-500 hover:text-slate-900 transition-colors shrink-0"
          aria-label="Fermer"
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

      <h2 id="card-panel-title" class="text-lg font-serif text-slate-900 leading-snug">
        {info.title}
      </h2>

      <div class="mt-2 text-sm text-slate-600 space-y-0.5">
        {#if info.authors}
          <p>{info.authors}</p>
        {/if}
        {#if publishedDate}
          <p class="text-slate-500">Publié le {publishedDate}</p>
        {/if}
        <p class="text-slate-500">
          {info.sourcesCount}
          {info.sourcesCount > 1 ? 'sources citées' : 'source citée'}
        </p>
      </div>

      {#if info.description}
        <p class="mt-3 text-sm text-slate-700 leading-relaxed">{info.description}</p>
      {/if}

      <div class="mt-4 flex flex-col gap-2">
        {#if info.contentUrl}
          <a
            href={info.contentUrl}
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-800 transition-colors"
          >
            Voir le contenu
            <svg
              viewBox="0 0 24 24"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path d="M7 17L17 7" />
              <path d="M7 7h10v10" />
            </svg>
          </a>
        {/if}
        {#if !info.isRoot}
          <a
            href="/@{info.creatorSlug}/{info.slug}"
            class="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-slate-300 text-slate-700 text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            Ouvrir la fiche
          </a>
        {/if}
        {#if onTogglePin && !info.isRoot}
          <button
            type="button"
            onclick={() => onTogglePin?.(info.id)}
            class="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors {pinned
              ? 'border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
              : 'border-slate-300 text-slate-600 hover:bg-slate-50'}"
          >
            {pinned ? 'Detacher du graphe' : 'Garder sur le graphe'}
          </button>
        {/if}
      </div>

      <div class="mt-4 pt-3 border-t border-slate-200">
        <p class="text-xs text-slate-500">
          Bibliographie publiée par
          <a href="/@{info.creatorSlug}" class="text-blue-700 hover:underline">
            {info.creatorName ?? info.creatorSlug}
          </a>
        </p>
      </div>
    </div>
  {/if}
{/snippet}

<style>
  .panel-scroll {
    scrollbar-width: thin;
    scrollbar-color: rgba(100, 116, 139, 0.45) transparent;
  }
  .panel-scroll::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  .panel-scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .panel-scroll::-webkit-scrollbar-thumb {
    background-color: rgba(100, 116, 139, 0.45);
    border-radius: 4px;
  }
  .panel-scroll::-webkit-scrollbar-thumb:hover {
    background-color: rgba(71, 85, 105, 0.7);
  }
</style>
