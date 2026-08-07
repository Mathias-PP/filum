<script lang="ts">
  import { page } from '$app/stores';
  import { EmptyState } from '$lib/components';

  let { data } = $props();

  // Le feed groupe visuellement par jour : une frise dense de dates seches
  // rend l'ordre lisible d'un coup, sans compter des chiffres imaginaires.
  function fmtDate(iso: string): string {
    return new Date(iso).toLocaleDateString('fr-FR', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  }

  function fmtTime(iso: string): string {
    return new Date(iso).toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // Grouper par date : le feed doit se lire sans avoir a comparer des
  // horodatages a la seconde. Le jour est la maille naturelle d'une trace.
  const groups = $derived.by(() => {
    const byDay = new Map<string, typeof data.entries>();
    for (const e of data.entries) {
      const day = e.occurred_at.slice(0, 10);
      if (!byDay.has(day)) byDay.set(day, []);
      byDay.get(day)!.push(e);
    }
    return Array.from(byDay.entries());
  });
</script>

<svelte:head>
  <title>Le feed · Philum</title>
  <meta
    name="description"
    content="Registre chronologique des fiches publiées sur Philum. Une trace, jamais un fil algorithmique."
  />
  <link rel="canonical" href="{$page.url.origin}/feed" />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 py-8">
  <h1 class="text-2xl font-semibold text-ink-primary mb-2">Le feed</h1>
  <p class="text-ink-secondary mb-8 max-w-2xl">
    Chaque entrée note qu'une fiche a été publiée à une date. Ordre strictement chronologique
    inverse, jamais algorithmique. Pas de compteurs, pas de recommandations : ce n'est pas un réseau
    social, c'est un registre.
  </p>

  {#if data.failed}
    <EmptyState title="Le feed n'a pas répondu" description="Réessayez dans un instant." />
  {:else if data.entries.length === 0}
    <EmptyState
      title="Aucune fiche publiée pour le moment"
      description="Les premières entrées apparaîtront ici."
    />
  {:else}
    <ol class="space-y-8">
      {#each groups as [day, entries] (day)}
        <li>
          <h2
            class="text-sm font-medium text-ink-tertiary uppercase tracking-wide mb-3 pb-1 border-b border-border-subtle"
          >
            {fmtDate(day)}
          </h2>
          <ul class="space-y-3">
            {#each entries as entry (entry.id)}
              <li class="flex gap-3">
                <time
                  class="text-xs font-mono text-ink-tertiary pt-1 w-12 flex-shrink-0"
                  datetime={entry.occurred_at}
                >
                  {fmtTime(entry.occurred_at)}
                </time>
                <div class="flex-1 min-w-0">
                  <a
                    href={new URL(entry.card_url).pathname}
                    class="text-ink-primary hover:text-info transition-colors font-medium"
                  >
                    {entry.card_title}
                  </a>
                  <p class="text-sm text-ink-secondary mt-0.5">
                    par
                    <a
                      href="/@{entry.creator_slug}"
                      class="hover:text-ink-primary transition-colors"
                    >
                      {entry.creator_display_name ?? entry.creator_slug}
                    </a>
                  </p>
                  {#if entry.card_description}
                    <p class="text-sm text-ink-secondary mt-1 line-clamp-2">
                      {entry.card_description}
                    </p>
                  {/if}
                </div>
              </li>
            {/each}
          </ul>
        </li>
      {/each}
    </ol>

    {#if data.nextBefore}
      <nav class="mt-8 flex justify-center">
        <a
          href="?before={encodeURIComponent(data.nextBefore)}"
          class="px-4 py-2 rounded-lg border border-border-strong text-sm text-ink-secondary hover:text-ink-primary hover:border-ink-primary transition-colors"
        >
          Entrées plus anciennes →
        </a>
      </nav>
    {/if}
  {/if}
</div>
