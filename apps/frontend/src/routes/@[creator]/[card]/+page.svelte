<script lang="ts">
  import { browser } from '$app/environment';
  import type { CardDetail } from '$lib/api';
  import { Avatar, SourceTypeBadge } from '$lib/components';

  interface PageData {
    card: CardDetail;
    creatorSlug: string;
    cardSlug: string;
  }

  let { data }: { data: PageData } = $props();
  const card = $derived(data.card);
  const creatorSlug = $derived(data.creatorSlug);
  const cardSlug = $derived(data.cardSlug);

  const API_BASE = import.meta.env.PUBLIC_API_BASE_URL ?? '';
  const ogImageUrl = $derived(
    `${API_BASE}/api/v1/og?title=${encodeURIComponent(card.title)}&creator=${encodeURIComponent(card.creator.display_name ?? card.creator.slug)}`
  );

  let expandedSource = $state<string | null>(null);
  let descriptionExpanded = $state(false);
  let GraphComponent = $state<any>(null);

  $effect(() => {
    if (browser && !GraphComponent) {
      import('$lib/components/SourceGraph.svelte').then((m) => {
        GraphComponent = m.default;
      });
    }
  });

  function toggleSource(sourceId: string) {
    expandedSource = expandedSource === sourceId ? null : sourceId;
  }

  function copyLink() {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(window.location.href);
    }
  }

  const publicUrl = $derived(`https://filum-eight.vercel.app/@${creatorSlug}/${cardSlug}`);

  const jsonLd = $derived.by(() => {
    const citations = card.sources.map((s) => ({
      '@type': s.source_type === 'peer-reviewed' ? 'ScholarlyArticle' : 'CreativeWork',
      name: s.title ?? s.url,
      ...(s.authors ? { author: s.authors } : {}),
      ...(s.published_at ? { datePublished: s.published_at } : {}),
      url: s.url,
      ...(s.source_type === 'peer-reviewed' ? { isAccessibleForFree: false } : {}),
    }));
    return {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: card.title,
      author: {
        '@type': 'Person',
        name: card.creator.display_name ?? card.creator.slug,
        url: `https://filum-eight.vercel.app/@${creatorSlug}`,
      },
      ...(card.published_at ? { datePublished: card.published_at } : {}),
      ...(card.description ? { description: card.description } : {}),
      publisher: {
        '@type': 'Organization',
        name: 'Filum',
        url: 'https://filum-eight.vercel.app/',
      },
      mainEntityOfPage: publicUrl,
      citation: citations,
    };
  });
</script>

<svelte:head>
  <title>{card.title} — Filum</title>
  <meta name="description" content={card.description ?? card.title} />
  <meta property="og:title" content={card.title} />
  <meta property="og:description" content={card.description ?? card.title} />
  <meta property="og:type" content="article" />
  <meta property="og:url" content={publicUrl} />
  <meta property="og:image" content={ogImageUrl} />
  <meta property="og:site_name" content="Filum" />
  <meta property="article:author" content={card.creator.display_name ?? card.creator.slug} />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content={ogImageUrl} />
  <link rel="canonical" href={publicUrl} />
  {@html `<script type="application/ld+json">${JSON.stringify(jsonLd)}<` + `/script>`}
</svelte:head>

<div class="min-h-screen bg-slate-50">
  <article>
    <header class="bg-white border-b border-slate-200">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div class="flex items-center gap-2">
          <a
            href="/@{creatorSlug}"
            class="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0"
          >
            <Avatar
              avatarUrl={card.creator.avatar_url}
              name={card.creator.display_name || card.creator.slug}
              size="sm"
            />
            <span class="text-sm font-medium text-slate-700"
              >{card.creator.display_name || card.creator.slug}</span
            >
          </a>
          <span class="text-slate-300 shrink-0">·</span>
          <div class="flex-1 min-w-0">
            <h1 class="text-sm sm:text-base font-serif text-slate-900 truncate" title={card.title}>
              {card.title}
            </h1>
            {#if card.description}
              <div class="relative">
                <p class="text-xs text-slate-500 mt-0.5 {descriptionExpanded ? '' : 'truncate'}">
                  {card.description}
                </p>
                {#if card.description.length > 100}
                  <button
                    type="button"
                    onclick={() => (descriptionExpanded = !descriptionExpanded)}
                    class="text-xs text-blue-600 hover:text-blue-800 mt-0.5"
                  >
                    {descriptionExpanded ? 'Moins' : 'Lire la suite'}
                  </button>
                {/if}
              </div>
            {/if}
          </div>
          <button
            type="button"
            onclick={copyLink}
            class="text-xs text-slate-500 hover:text-slate-900 transition-colors px-2.5 py-1 rounded-md border border-slate-200 hover:border-slate-300 shrink-0"
          >
            Partager
          </button>
        </div>
      </div>
    </header>

    <section class="bg-slate-50">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div
          class="h-[75vh] min-h-[500px] rounded-xl bg-white border border-slate-200 overflow-hidden relative"
        >
          {#if GraphComponent}
            <GraphComponent {card} />
          {:else}
            <div class="h-full flex items-center justify-center text-slate-400">
              Chargement du graphe…
            </div>
          {/if}
        </div>
        <p class="text-center text-xs sm:text-sm text-slate-500 mt-3">
          Cliquez sur un nœud pour explorer la source · glissez pour réorganiser · molette pour
          zoomer
        </p>
      </div>
    </section>

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
            <p class="text-xs sm:text-sm text-slate-500">Article scientifique</p>
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

    <section class="bg-slate-50 border-t border-slate-200">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 class="text-xl font-semibold text-slate-900 mb-4">Sources citées</h2>
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
                      <h3 class="text-base font-medium text-slate-900">
                        {source.title || 'Sans titre'}
                      </h3>
                      <SourceTypeBadge type={source.source_type} />
                      {#if source.is_pivot}
                        <span
                          class="px-2 py-0.5 text-xs bg-amber-100 text-amber-800 rounded-full"
                          title="Source structurante du raisonnement"
                        >
                          ★ Source clé
                        </span>
                      {/if}
                      {#if source.conflict_of_interest}
                        <span
                          class="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded-full"
                          title={source.conflict_of_interest}
                        >
                          Conflit d'intérêt déclaré
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
                  {#if source.excerpts && source.excerpts.length > 0}
                    <div class="mt-4">
                      <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">
                        Extraits cités
                      </p>
                      <ul class="space-y-2">
                        {#each source.excerpts as excerpt (excerpt.id)}
                          <li
                            class="bg-slate-50 border border-slate-200 rounded-md p-3 text-sm italic text-slate-700"
                          >
                            «&nbsp;{excerpt.text}&nbsp;»
                          </li>
                        {/each}
                      </ul>
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
                        Version archivée Wayback
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

    <footer class="bg-white border-t border-slate-200">
      <div
        class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-4"
      >
        <div class="text-xs text-slate-500 font-mono break-all">
          <p class="text-slate-700 font-sans font-medium not-italic mb-1">Signature Ed25519</p>
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
                  timeStyle: 'short',
                })
              : 'N/A'}
          </p>
          <p class="text-xs">Vérifiable via l'API</p>
        </div>
      </div>
    </footer>
  </article>
</div>
