<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { EmptyState } from '$lib/components';
  import { PAGE_SIZE, type DiscoverResult } from './shared';

  let { data } = $props();

  const PLATFORM_LABELS: Record<string, string> = {
    youtube: 'YouTube',
    podcast: 'Podcast',
    blog: 'Blog',
    x: 'X',
    bluesky: 'Bluesky',
    'revue-scientifique': 'Revue scientifique',
    other: 'Autre',
  };
  const TYPE_LABELS: Record<string, string> = {
    video: 'Vidéo',
    article: 'Article',
    post: 'Publication',
    podcast: 'Podcast',
    other: 'Autre',
  };

  const SORTS = [
    { value: 'recent', label: 'Plus récentes' },
    { value: 'sources', label: 'Mieux sourcées' },
    { value: 'title', label: 'Alphabétique' },
  ];

  const KIND_LABELS: Record<string, string> = {
    contenu: 'Fiches de contenu',
    sujet: 'Fiches de sujet',
  };

  const params = $derived($page.url.searchParams);
  const q = $derived(params.get('q') ?? '');
  const activeKind = $derived(params.get('card_kind') ?? '');
  const activePlatform = $derived(params.get('platform') ?? '');

  /**
   * Etat local decouple de l'URL pour la barre de recherche.
   *
   * Sans lui, l'input etait pilote par `value={q}` derive de l'URL. Chaque
   * frappe declenchait apres 300 ms un `goto()` qui rechangeait l'URL, ce
   * qui reevaluait `q` et faisait re-render l'input avec l'ancienne valeur
   * pendant que l'utilisateur continuait a taper. Resultat mesure :
   * « memory » tape lettre par lettre ressortait « memry » ou « momery »
   * selon la latence.
   *
   * Ici on separe : l'input suit l'etat local (source unique cote clavier)
   * et pousse vers l'URL avec debounce ; l'URL ne pousse en retour que
   * quand elle change *sans* que ce soit nous (retour navigateur, clic sur
   * un lien filtre, « Tout effacer »).
   */
  let inputValue = $state('');
  let lastLocalEdit = 0;

  $effect(() => {
    // params est reactive : `goto` la change, ce qui declenche cet effect.
    // On ne re-pousse dans inputValue que si l'utilisateur n'a pas tape
    // depuis 500 ms : au-dela, une navigation externe (retour, filtre,
    // reset) fait autorite ; en deca, c'est notre propre setParam et on
    // laisse la saisie en cours tranquille.
    const urlQ = params.get('q') ?? '';
    if (Date.now() - lastLocalEdit > 500 && inputValue !== urlQ) {
      inputValue = urlQ;
    }
  });
  const activeType = $derived(params.get('content_type') ?? '');
  const activeCreator = $derived(params.get('creator') ?? '');
  const sort = $derived(params.get('sort') ?? 'recent');
  const after = $derived(params.get('published_after') ?? '');
  const before = $derived(params.get('published_before') ?? '');

  const activeCount = $derived(
    [activeKind, activePlatform, activeType, activeCreator, after, before].filter(Boolean).length
  );
  const lastPage = $derived(Math.max(1, Math.ceil(data.total / PAGE_SIZE)));

  /** Toute modification de filtre passe par l'URL : un seul état, partageable. */
  function setParam(key: string, value: string) {
    const next = new URLSearchParams($page.url.searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    // Changer un filtre ramène en page 1 : rester en page 4 d'un résultat qui
    // n'en compte plus qu'une afficherait un vide trompeur.
    if (key !== 'page') next.delete('page');
    goto(`/discover${next.toString() ? `?${next}` : ''}`, {
      keepFocus: true,
      noScroll: key === 'page' ? false : true,
    });
  }

  // Debounce de la frappe : sans lui, chaque lettre déclenche une requête.
  let searchTimer: ReturnType<typeof setTimeout>;
  function onSearchInput(e: Event) {
    inputValue = (e.currentTarget as HTMLInputElement).value;
    lastLocalEdit = Date.now();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => setParam('q', inputValue.trim()), 300);
  }

  function toggle(key: string, value: string, current: string) {
    setParam(key, current === value ? '' : value);
  }

  function clearAll() {
    // Force la reprise en main par l'URL malgre le garde-temps 500 ms :
    // sans ce reset explicite, cliquer « Tout effacer » juste apres avoir
    // tape ne viderait pas l'input.
    inputValue = '';
    lastLocalEdit = 0;
    goto('/discover');
  }

  function formatDate(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  function hostOf(url: string | null): string {
    if (!url) return '';
    try {
      return new URL(url).hostname.replace(/^www\./, '');
    } catch {
      return '';
    }
  }

  function excerpt(r: DiscoverResult): string {
    if (!r.description) return '';
    return r.description.length > 220 ? `${r.description.slice(0, 217)}…` : r.description;
  }
</script>

<svelte:head>
  <title>Explorer les fiches | Philum</title>
  <meta
    name="description"
    content="Parcourez les bibliographies publiques de Philum : cherchez par titre, par auteur du contenu ou par créateur, filtrez par plateforme et par date."
  />
  <link rel="canonical" href="{$page.url.origin}/discover" />
</svelte:head>

<div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
  <p class="page-overline">Explorer</p>
  <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-3">Les fiches publiques</h1>
  <p class="text-lg text-ink-secondary mb-4 max-w-3xl">
    Chaque fiche relie un contenu à la bibliographie que son auteur a réellement consultée. Cherchez
    par titre, par auteur du contenu ou par créateur de la fiche.
  </p>

  <nav class="mb-6 text-sm flex gap-4" aria-label="Onglets d'exploration">
    <span class="font-medium text-ink-primary">Fiches</span>
    <a
      href="/discover/creators"
      class="text-ink-secondary hover:text-ink-primary transition-colors"
    >
      Créateurs →
    </a>
  </nav>

  <search class="mb-6">
    <label for="discover-q" class="sr-only">Rechercher une fiche</label>
    <div class="relative">
      <svg
        class="absolute left-3.5 top-1/2 -translate-y-1/2 w-5 h-5 text-ink-tertiary pointer-events-none"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" />
      </svg>
      <input
        id="discover-q"
        type="search"
        value={inputValue}
        oninput={onSearchInput}
        placeholder="Titre, auteur du contenu, créateur…"
        class="form-input w-full pl-11 pr-4 py-3 rounded-xl bg-surface-primary border border-border text-ink-primary placeholder:text-ink-placeholder focus:border-primary-500 focus:ring-1 focus:ring-primary-500"
      />
    </div>
  </search>

  <div class="flex flex-wrap items-center gap-2 mb-3">
    <!--
      La nature vient en premier : elle decide si les facettes suivantes ont un
      sens. Une fiche sujet n'a ni plateforme ni type de contenu.
    -->
    {#each data.facets.card_kinds as f (f.value)}
      <button
        type="button"
        onclick={() => toggle('card_kind', f.value, activeKind)}
        aria-pressed={activeKind === f.value}
        class="px-3 py-1.5 text-sm rounded-full border transition-colors {activeKind === f.value
          ? 'bg-primary-600 border-primary-600 text-white'
          : 'bg-surface-primary border-border text-ink-secondary hover:border-border-strong hover:text-ink-primary'}"
      >
        {KIND_LABELS[f.value] ?? f.value}
        <span class="opacity-70 tabular-nums">{f.count}</span>
      </button>
    {/each}
    {#if data.facets.card_kinds.length > 0}
      <span class="w-px h-5 bg-border mx-1" aria-hidden="true"></span>
    {/if}
    {#each data.facets.platforms as f (f.value)}
      <button
        type="button"
        onclick={() => toggle('platform', f.value, activePlatform)}
        aria-pressed={activePlatform === f.value}
        class="px-3 py-1.5 text-sm rounded-full border transition-colors {activePlatform === f.value
          ? 'bg-primary-600 border-primary-600 text-white'
          : 'bg-surface-primary border-border text-ink-secondary hover:border-border-strong hover:text-ink-primary'}"
      >
        {PLATFORM_LABELS[f.value] ?? f.value}
        <span class="opacity-70 tabular-nums">{f.count}</span>
      </button>
    {/each}
    <span class="w-px h-5 bg-border mx-1" aria-hidden="true"></span>
    {#each data.facets.content_types as f (f.value)}
      <button
        type="button"
        onclick={() => toggle('content_type', f.value, activeType)}
        aria-pressed={activeType === f.value}
        class="px-3 py-1.5 text-sm rounded-full border transition-colors {activeType === f.value
          ? 'bg-primary-600 border-primary-600 text-white'
          : 'bg-surface-primary border-border text-ink-secondary hover:border-border-strong hover:text-ink-primary'}"
      >
        {TYPE_LABELS[f.value] ?? f.value}
        <span class="opacity-70 tabular-nums">{f.count}</span>
      </button>
    {/each}
  </div>

  <div class="flex flex-wrap items-end gap-4 mb-6 pb-6 border-b border-border">
    <div>
      <label for="f-creator" class="block text-xs font-medium text-ink-tertiary mb-1"
        >Créateur de la fiche</label
      >
      <select
        id="f-creator"
        value={activeCreator}
        onchange={(e) => setParam('creator', e.currentTarget.value)}
        class="form-select text-sm rounded-lg bg-surface-primary border-border text-ink-primary py-1.5"
      >
        <option value="">Tous</option>
        {#each data.facets.creators as c (c.value)}
          <option value={c.value}>@{c.value} ({c.count})</option>
        {/each}
      </select>
    </div>
    <div>
      <label for="f-after" class="block text-xs font-medium text-ink-tertiary mb-1"
        >Publiée après</label
      >
      <input
        id="f-after"
        type="date"
        value={after}
        onchange={(e) => setParam('published_after', e.currentTarget.value)}
        class="form-input text-sm rounded-lg bg-surface-primary border-border text-ink-primary py-1.5"
      />
    </div>
    <div>
      <label for="f-before" class="block text-xs font-medium text-ink-tertiary mb-1"
        >Publiée avant</label
      >
      <input
        id="f-before"
        type="date"
        value={before}
        onchange={(e) => setParam('published_before', e.currentTarget.value)}
        class="form-input text-sm rounded-lg bg-surface-primary border-border text-ink-primary py-1.5"
      />
    </div>
    <div>
      <label for="f-sort" class="block text-xs font-medium text-ink-tertiary mb-1">Trier par</label>
      <select
        id="f-sort"
        value={sort}
        onchange={(e) => setParam('sort', e.currentTarget.value)}
        class="form-select text-sm rounded-lg bg-surface-primary border-border text-ink-primary py-1.5"
      >
        {#each SORTS as s (s.value)}
          <option value={s.value}>{s.label}</option>
        {/each}
      </select>
    </div>
    {#if activeCount > 0 || q}
      <button
        type="button"
        onclick={clearAll}
        class="text-sm text-ink-secondary hover:text-ink-primary underline underline-offset-4 py-1.5"
      >
        Tout effacer
      </button>
    {/if}
  </div>

  <p class="text-sm text-ink-secondary mb-6" aria-live="polite">
    {#if data.failed}
      Le service de recherche est momentanément indisponible.
    {:else if data.total === 0}
      Aucune fiche ne correspond.
    {:else}
      <strong class="text-ink-primary tabular-nums">{data.total}</strong>
      {data.total > 1 ? 'fiches' : 'fiche'}
    {/if}
  </p>

  {#if data.total === 0 && !data.failed}
    <EmptyState
      title="Aucune fiche ne correspond"
      description="Essayez des termes plus larges, ou retirez un filtre."
    />
  {:else}
    <ul class="grid gap-4 sm:grid-cols-2">
      {#each data.results as r (r.id)}
        <li>
          <a
            href="/@{r.creator_slug}/{r.slug}"
            class="hover-lift block h-full bg-surface-primary border border-border rounded-xl p-5"
          >
            <div class="flex items-center gap-2 text-xs text-ink-tertiary mb-2">
              <span>
                {#if r.card_kind === 'sujet'}
                  Sujet
                {:else}
                  {PLATFORM_LABELS[r.platform ?? ''] ?? r.platform}
                {/if}
              </span>
              {#if r.published_at}
                <span aria-hidden="true">·</span>
                <time datetime={r.published_at}>{formatDate(r.published_at)}</time>
              {/if}
            </div>
            <h2 class="text-lg font-semibold text-ink-primary mb-1.5 leading-snug">{r.title}</h2>
            <!-- Sur une fiche sujet, ces deux champs sont vides par nature :
                 la ligne ne laisserait qu'une marge sans texte. -->
            {#if r.content_authors || hostOf(r.content_url)}
              <p class="text-sm text-ink-secondary mb-3">
                {#if r.content_authors}<span class="text-ink-primary">{r.content_authors}</span
                  >{/if}
                {#if r.content_authors && hostOf(r.content_url)}<span aria-hidden="true">
                    ·
                  </span>{/if}
                {#if hostOf(r.content_url)}{hostOf(r.content_url)}{/if}
              </p>
            {/if}
            {#if excerpt(r)}
              <p class="text-sm text-ink-secondary mb-4">{excerpt(r)}</p>
            {/if}
            <div class="flex items-center justify-between text-xs text-ink-tertiary">
              <span>par @{r.creator_slug}</span>
              <span class="tabular-nums"
                >{r.source_count}
                {r.source_count > 1 ? 'sources' : 'source'}</span
              >
            </div>
          </a>
        </li>
      {/each}
    </ul>

    {#if lastPage > 1}
      <nav class="flex items-center justify-center gap-4 mt-10" aria-label="Pagination">
        <button
          type="button"
          disabled={data.page <= 1}
          onclick={() => setParam('page', String(data.page - 1))}
          class="px-4 py-2 text-sm rounded-lg border border-border text-ink-secondary hover:text-ink-primary hover:border-border-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Précédent
        </button>
        <span class="text-sm text-ink-secondary tabular-nums">
          Page {data.page} sur {lastPage}
        </span>
        <button
          type="button"
          disabled={data.page >= lastPage}
          onclick={() => setParam('page', String(data.page + 1))}
          class="px-4 py-2 text-sm rounded-lg border border-border text-ink-secondary hover:text-ink-primary hover:border-border-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Suivant
        </button>
      </nav>
    {/if}
  {/if}
</div>
