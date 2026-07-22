<script lang="ts">
  import { browser } from '$app/environment';
  import type { CardDetail } from '$lib/api';
  import {
    Avatar,
    AuthorKindBadge,
    FormatBadge,
    CategoryBadge,
    Button,
    ClaimBanner,
    Skeleton,
  } from '$lib/components';
  import {
    AUTHOR_COLORS,
    CATEGORY_COLORS,
    authorLabel,
    categoryLabel,
  } from '$lib/utils/author-colors';
  import { slide } from 'svelte/transition';
  import { page } from '$app/stores';
  import { currentUser } from '$lib/stores/auth';

  interface PageData {
    card: CardDetail;
    creatorSlug: string;
    cardSlug: string;
  }

  let { data }: { data: PageData } = $props();
  const card = $derived(data.card);
  const creatorSlug = $derived(data.creatorSlug);
  const cardSlug = $derived(data.cardSlug);

  // Valeur majoritaire (et son %) parmi les sources — affichée dans les
  // indicateurs à la place des anciens compteurs fixes Chercheurs/Institutions.
  function majority<K extends string>(keys: K[]): { key: K; pct: number } | null {
    if (keys.length === 0) return null;
    const counts = new Map<K, number>();
    for (const k of keys) counts.set(k, (counts.get(k) ?? 0) + 1);
    let bestKey = keys[0];
    let bestCount = 0;
    for (const [k, n] of counts) {
      if (n > bestCount) {
        bestKey = k;
        bestCount = n;
      }
    }
    return { key: bestKey, pct: Math.round((bestCount / keys.length) * 100) };
  }

  const majorityAuthor = $derived(majority(card.sources.map((s) => s.author_kind)));
  const majorityCategory = $derived(majority(card.sources.map((s) => s.category)));

  // Relative — routed through the SvelteKit /api proxy for first-party cookies.
  const API_BASE = '';
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

  let exportOpen = $state(false);
  const exportBase = $derived(`${API_BASE}/api/v1/@${creatorSlug}/${cardSlug}/export`);
  const exportFormats = [
    { format: 'json', label: 'JSON' },
    { format: 'csv', label: 'CSV' },
    { format: 'xlsx', label: 'Excel (.xlsx)' },
    { format: 'docx', label: 'Word (.docx)' },
    { format: 'bibtex', label: 'BibTeX (.bib)' },
    { format: 'csl', label: 'CSL-JSON (Zotero)' },
    { format: 'apa', label: 'APA (texte)' },
    { format: 'markdown', label: 'Markdown / Obsidian' },
  ];

  function printCard() {
    exportOpen = false;
    if (typeof window !== 'undefined') window.print();
  }

  const siteOrigin = $derived($page.url.origin);
  const publicUrl = $derived(`${siteOrigin}/@${creatorSlug}/${cardSlug}`);
  const isOwner = $derived($currentUser?.username === creatorSlug);

  const jsonLd = $derived.by(() => {
    const citations = card.sources.map((s) => ({
      '@type': s.category === 'article-scientifique' ? 'ScholarlyArticle' : 'CreativeWork',
      name: s.title ?? s.url,
      ...(s.authors ? { author: s.authors } : {}),
      ...(s.published_at ? { datePublished: s.published_at } : {}),
      url: s.url,
      ...(s.category === 'article-scientifique' ? { isAccessibleForFree: false } : {}),
    }));
    return {
      '@context': 'https://schema.org',
      '@type': 'Article',
      headline: card.title,
      author: {
        '@type': 'Person',
        name: card.creator.display_name ?? card.creator.slug,
        url: `${siteOrigin}/@${creatorSlug}`,
      },
      ...(card.published_at ? { datePublished: card.published_at } : {}),
      ...(card.description ? { description: card.description } : {}),
      publisher: {
        '@type': 'Organization',
        name: 'Philum',
        url: `${siteOrigin}/`,
      },
      mainEntityOfPage: publicUrl,
      citation: citations,
    };
  });
</script>

<svelte:head>
  <title>{card.title} — Philum</title>
  <meta name="description" content={card.description ?? card.title} />
  <meta property="og:title" content={card.title} />
  <meta property="og:description" content={card.description ?? card.title} />
  <meta property="og:type" content="article" />
  <meta property="og:url" content={publicUrl} />
  <meta property="og:image" content={ogImageUrl} />
  <meta property="og:site_name" content="Philum" />
  <meta property="article:author" content={card.creator.display_name ?? card.creator.slug} />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:image" content={ogImageUrl} />
  <link rel="canonical" href={publicUrl} />
  {@html `<script type="application/ld+json">${JSON.stringify(jsonLd)}<` + `/script>`}
</svelte:head>

<div class="min-h-screen bg-surface-secondary">
  <article>
    <header class="bg-surface-primary border-b border-border">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
        <div class="flex items-center gap-2">
          {#if isOwner}
            <a
              href="/dashboard"
              class="flex items-center gap-1 text-xs sm:text-sm text-ink-tertiary hover:text-ink-primary transition-colors shrink-0 mr-1 sm:mr-2 px-2 py-1 rounded-md hover:bg-surface-tertiary"
              title="Retour à votre tableau de bord"
            >
              <svg
                viewBox="0 0 24 24"
                class="w-3.5 h-3.5"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <line x1="19" y1="12" x2="5" y2="12" />
                <polyline points="12 19 5 12 12 5" />
              </svg>
              <span class="hidden sm:inline">Tableau de bord</span>
            </a>
          {/if}
          <a
            href="/@{creatorSlug}"
            class="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0"
          >
            <Avatar
              avatarUrl={card.creator.avatar_url}
              name={card.creator.display_name || card.creator.slug}
              size="sm"
            />
            <span class="text-sm font-medium text-ink-secondary"
              >{card.creator.display_name || card.creator.slug}</span
            >
          </a>
          <span class="text-ink-tertiary shrink-0">·</span>
          <div class="flex-1 min-w-0">
            <h1
              class="text-sm sm:text-base font-serif text-ink-primary truncate"
              title={card.title}
            >
              {card.title}
            </h1>
            {#if card.description}
              <div class="relative">
                <p class="text-xs text-ink-tertiary mt-0.5 {descriptionExpanded ? '' : 'truncate'}">
                  {card.description}
                </p>
                {#if card.description.length > 100}
                  <button
                    type="button"
                    onclick={() => (descriptionExpanded = !descriptionExpanded)}
                    class="text-xs text-info hover:opacity-80 mt-0.5"
                  >
                    {descriptionExpanded ? 'Moins' : 'Lire la suite'}
                  </button>
                {/if}
              </div>
            {/if}
          </div>
          <div class="relative shrink-0 print:hidden">
            <button
              type="button"
              onclick={() => (exportOpen = !exportOpen)}
              class="text-xs text-ink-tertiary hover:text-ink-primary transition-colors px-2.5 py-1 rounded-md border border-border hover:border-border-strong"
              aria-haspopup="menu"
              aria-expanded={exportOpen}
            >
              Exporter
            </button>
            {#if exportOpen}
              <div
                class="absolute right-0 top-full mt-1 z-30 w-48 rounded-md border border-border bg-surface-primary shadow-lg py-1"
                role="menu"
              >
                {#each exportFormats as fmt (fmt.format)}
                  <a
                    href="{exportBase}?format={fmt.format}"
                    download
                    onclick={() => (exportOpen = false)}
                    class="block px-3 py-1.5 text-xs text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary"
                    role="menuitem"
                  >
                    {fmt.label}
                  </a>
                {/each}
                <button
                  type="button"
                  onclick={printCard}
                  class="block w-full text-left px-3 py-1.5 text-xs text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary"
                  role="menuitem"
                >
                  PDF (imprimer)
                </button>
              </div>
            {/if}
          </div>
          <button
            type="button"
            onclick={copyLink}
            class="text-xs text-ink-tertiary hover:text-ink-primary transition-colors px-2.5 py-1 rounded-md border border-border hover:border-border-strong shrink-0 print:hidden"
          >
            Partager
          </button>
        </div>
      </div>
    </header>

    {#if card.is_seed}
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <ClaimBanner
          cardId={card.id}
          creatorName={card.creator.display_name ?? card.creator.slug}
        />
      </div>
    {/if}

    <section class="bg-surface-secondary">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div
          class="h-[75vh] min-h-[500px] rounded-xl bg-surface-primary border border-border overflow-hidden relative"
        >
          {#if GraphComponent}
            <!-- Re-mount the d3 simulation when navigating between cards:
                 the graph builds its nodes once on mount and doesn't react
                 to a card prop swap. -->
            {#key card.id}
              <GraphComponent {card} />
            {/key}
          {:else}
            <div class="absolute inset-0 p-6 flex flex-col items-center justify-center gap-4">
              <Skeleton variant="graph" height="100%" class="absolute inset-0 opacity-50" />
              <p class="relative text-sm text-ink-tertiary">Chargement du graphe…</p>
            </div>
          {/if}
        </div>
        <p class="text-center text-xs sm:text-sm text-ink-tertiary mt-3">
          Cliquez sur un nœud pour explorer la source · glissez pour réorganiser · molette pour
          zoomer
        </p>
      </div>
    </section>

    <section class="bg-surface-primary border-t border-b border-border">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
          <div class="text-center p-3 sm:p-4 bg-surface-secondary rounded-lg">
            <p class="text-xl sm:text-2xl font-bold text-ink-primary">
              {card.stats.total_sources}
            </p>
            <p class="text-xs sm:text-sm text-ink-tertiary">Sources</p>
          </div>
          <div class="text-center p-3 sm:p-4 bg-surface-secondary rounded-lg">
            {#if majorityAuthor}
              <p
                class="text-xl sm:text-2xl font-bold"
                style="color: {AUTHOR_COLORS[majorityAuthor.key].stroke}"
              >
                {majorityAuthor.pct}&nbsp;%
              </p>
              <p class="text-xs sm:text-sm text-ink-tertiary">
                {authorLabel(majorityAuthor.key)}
              </p>
            {:else}
              <p class="text-xl sm:text-2xl font-bold text-ink-tertiary">—</p>
              <p class="text-xs sm:text-sm text-ink-tertiary">Type d'auteur</p>
            {/if}
          </div>
          <div class="text-center p-3 sm:p-4 bg-surface-secondary rounded-lg">
            {#if majorityCategory}
              <p
                class="text-xl sm:text-2xl font-bold"
                style="color: {CATEGORY_COLORS[majorityCategory.key].stroke}"
              >
                {majorityCategory.pct}&nbsp;%
              </p>
              <p class="text-xs sm:text-sm text-ink-tertiary">
                {categoryLabel(majorityCategory.key)}
              </p>
            {:else}
              <p class="text-xl sm:text-2xl font-bold text-ink-tertiary">—</p>
              <p class="text-xs sm:text-sm text-ink-tertiary">Catégorie</p>
            {/if}
          </div>
          <div class="text-center p-3 sm:p-4 bg-surface-secondary rounded-lg">
            <p class="text-xl sm:text-2xl font-bold text-ink-secondary">
              {card.stats.all_archived
                ? '✓'
                : `${card.stats.archived_count}/${card.stats.total_sources}`}
            </p>
            <p class="text-xs sm:text-sm text-ink-tertiary">Archivées</p>
          </div>
        </div>
      </div>
    </section>

    <section class="bg-surface-secondary border-t border-border">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <h2 class="text-xl font-semibold text-ink-primary mb-4">Sources citées</h2>
        <div class="space-y-3">
          {#each card.sources as source, i (source.id)}
            <div class="bg-surface-primary rounded-lg border border-border overflow-hidden">
              <button
                type="button"
                class="w-full text-left p-4 hover:bg-surface-secondary transition-colors"
                onclick={() => toggleSource(source.id)}
              >
                <div class="flex items-start gap-3">
                  <span class="text-ink-tertiary font-medium tabular-nums">{i + 1}.</span>
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 flex-wrap">
                      <h3 class="text-base font-medium text-ink-primary">
                        {source.title || 'Sans titre'}
                      </h3>
                      <AuthorKindBadge kind={source.author_kind} />
                      <FormatBadge format={source.format} />
                      <CategoryBadge category={source.category} />
                      {#if source.is_pivot}
                        <span
                          class="px-2 py-0.5 text-xs bg-amber-100 text-amber-800 rounded-full"
                          title="Source structurante du raisonnement"
                        >
                          ★ Source clé
                        </span>
                      {/if}
                      {#if source.linked_card_id}
                        <span
                          class="px-2 py-0.5 text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full"
                          title="Cette source est elle-même une fiche Philum avec ses propres sources"
                        >
                          Fiche Philum{#if source.linked_card_sources_count != null}&nbsp;· {source.linked_card_sources_count}
                            source{source.linked_card_sources_count > 1 ? 's' : ''}{/if}
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
                    {#if source.authors || source.published_at}
                      <p class="text-sm text-ink-tertiary mt-1">
                        {#if source.authors}{source.authors}{/if}{#if source.authors && source.published_at}
                          &nbsp;·
                        {/if}{#if source.published_at}
                          <time datetime={source.published_at}>
                            {new Date(source.published_at).getFullYear()}
                          </time>
                        {/if}
                      </p>
                    {/if}
                    {#if source.journal}
                      <p class="text-sm text-ink-tertiary italic mt-0.5">
                        {source.journal}{#if source.volume}, {source.volume}{/if}{#if source.pages}, {source.pages}{/if}
                      </p>
                    {/if}
                    <p class="text-sm text-info mt-1 truncate">{source.url}</p>
                  </div>
                  <svg
                    class="w-5 h-5 text-ink-tertiary shrink-0 transition-transform {expandedSource ===
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
                <div class="px-4 pb-4 border-t border-border" transition:slide={{ duration: 200 }}>
                  {#if source.annotation}
                    <div
                      class="mt-4 p-3 bg-surface-secondary rounded-lg text-sm text-ink-secondary"
                    >
                      <p class="font-medium text-ink-primary mb-1">Annotation :</p>
                      <p>{source.annotation}</p>
                    </div>
                  {/if}
                  {#if source.excerpts && source.excerpts.length > 0}
                    <div class="mt-4">
                      <p class="text-xs uppercase tracking-wide text-ink-tertiary mb-2">
                        Extraits cités
                      </p>
                      <ul class="space-y-2">
                        {#each source.excerpts as excerpt (excerpt.id)}
                          <li
                            class="bg-surface-secondary border border-border rounded-md p-3 text-sm italic text-ink-secondary"
                          >
                            «&nbsp;{excerpt.text}&nbsp;»
                          </li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                  <div class="mt-4 flex flex-wrap gap-2">
                    {#if source.archive_url}
                      <Button
                        href={source.archive_url}
                        target="_blank"
                        variant="secondary"
                        size="sm"
                      >
                        Version archivée Wayback
                      </Button>
                    {/if}
                    {#if source.linked_card_id}
                      <Button href={source.url} variant="primary" size="sm">
                        Explorer la fiche Philum →
                      </Button>
                    {:else}
                      <Button href={source.url} target="_blank" variant="secondary" size="sm">
                        Version live ↗
                      </Button>
                    {/if}
                  </div>
                </div>
              {/if}
            </div>
          {/each}
        </div>
      </div>
    </section>

    <footer class="bg-surface-primary border-t border-border">
      <div
        class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-wrap items-center justify-between gap-4"
      >
        <div class="text-sm text-ink-tertiary">
          <p class="text-ink-secondary font-medium mb-1">Contenu revendiqué par son créateur·ice</p>
          <p class="text-xs">
            L'URL du contenu original est attestée par signature Ed25519. <a
              href="/security"
              class="text-info hover:opacity-80 underline">En savoir plus</a
            >
          </p>
        </div>
        <div class="text-sm text-ink-tertiary text-right">
          {#if card.published_at}
            <p>
              Publiée le {new Date(card.published_at).toLocaleString('fr-FR', {
                dateStyle: 'long',
                timeStyle: 'short',
              })}
            </p>
          {/if}
        </div>
      </div>
    </footer>
  </article>
</div>
