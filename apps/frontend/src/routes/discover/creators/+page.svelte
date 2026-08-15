<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { EmptyState } from '$lib/components';

  let { data } = $props();

  const q = $derived($page.url.searchParams.get('q') ?? '');
  const lastPage = $derived(Math.max(1, Math.ceil(data.total / data.pageSize)));

  /** Modification de q ou de la page : passe par l'URL, comme /discover. */
  function setParam(key: string, value: string) {
    const next = new URLSearchParams($page.url.searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    goto(`?${next}`, { keepFocus: true });
  }
</script>

<svelte:head>
  <title>Créateurs · Philum</title>
  <meta name="description" content="Trouver un créateur qui publie sa bibliographie sur Philum." />
</svelte:head>

<div class="max-w-4xl mx-auto px-4 py-8">
  <nav class="mb-6 text-sm text-ink-secondary flex gap-4">
    <a href="/discover" class="hover:text-ink-primary transition-colors">Fiches</a>
    <span class="font-medium text-ink-primary">Créateurs</span>
  </nav>

  <h1 class="text-2xl font-semibold text-ink-primary mb-2">Créateurs</h1>
  <p class="text-ink-secondary mb-6">
    Les créateurs qui ont au moins une fiche publique. Recherche sur le nom, le pseudo et la
    biographie.
  </p>

  <input
    type="search"
    value={q}
    oninput={(e) => setParam('q', (e.currentTarget as HTMLInputElement).value)}
    placeholder="Chercher un créateur"
    aria-label="Chercher un créateur"
    class="w-full px-4 py-2 mb-6 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
  />

  {#if data.failed}
    <EmptyState title="La recherche n'a pas répondu" description="Réessayez dans un instant." />
  {:else if data.results.length === 0}
    <EmptyState
      title={q ? `Personne trouvé pour « ${q} »` : 'Aucun créateur pour le moment'}
      description={q ? 'Essayez un autre terme.' : 'Les premiers profils publics apparaîtront ici.'}
    />
  {:else}
    <ul class="space-y-3">
      {#each data.results as creator (creator.slug)}
        <li>
          <a
            href={creator.url}
            class="hover-lift flex items-start gap-4 p-4 rounded-lg border border-border hover:bg-surface-tertiary"
          >
            {#if creator.avatar_url}
              <img
                src={creator.avatar_url}
                alt=""
                class="w-12 h-12 rounded-full object-cover shrink-0"
              />
            {:else}
              <div
                class="w-12 h-12 rounded-full bg-surface-tertiary flex items-center justify-center text-ink-secondary text-lg font-medium shrink-0"
              >
                {(creator.display_name ?? creator.slug).charAt(0).toUpperCase()}
              </div>
            {/if}
            <div class="flex-1 min-w-0">
              <div class="flex items-baseline gap-2 flex-wrap">
                <span class="font-medium text-ink-primary truncate">
                  {creator.display_name ?? creator.slug}
                </span>
                <span class="text-sm text-ink-secondary">@{creator.slug}</span>
                {#if creator.is_verified}
                  <span
                    class="text-xs px-1.5 py-0.5 rounded bg-info/10 text-info"
                    title="Compte vérifié"
                  >
                    vérifié
                  </span>
                {/if}
              </div>
              {#if creator.bio}
                <p class="text-sm text-ink-secondary mt-1 line-clamp-2">{creator.bio}</p>
              {/if}
              <p class="text-xs text-ink-secondary mt-2">
                {creator.published_cards_count} fiche{creator.published_cards_count > 1 ? 's' : ''} publique{creator.published_cards_count >
                1
                  ? 's'
                  : ''}
              </p>
            </div>
          </a>
        </li>
      {/each}
    </ul>

    {#if lastPage > 1}
      <nav
        class="mt-8 flex items-center justify-between text-sm"
        aria-label="Pagination des créateurs"
      >
        <button
          type="button"
          disabled={data.page <= 1}
          onclick={() => setParam('page', String(Math.max(1, data.page - 1)))}
          class="px-3 py-1.5 rounded border border-border-strong disabled:opacity-40"
        >
          Précédent
        </button>
        <span class="text-ink-secondary">Page {data.page} / {lastPage}</span>
        <button
          type="button"
          disabled={data.page >= lastPage}
          onclick={() => setParam('page', String(Math.min(lastPage, data.page + 1)))}
          class="px-3 py-1.5 rounded border border-border-strong disabled:opacity-40"
        >
          Suivant
        </button>
      </nav>
    {/if}
  {/if}
</div>
