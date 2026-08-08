<script lang="ts">
  import { Avatar } from '$lib/components';
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const profile = $derived(data.profile);
  const username = $derived(data.username);

  const platformLabels: Record<string, string> = {
    youtube: 'YouTube',
    instagram: 'Instagram',
    x: 'X',
    tiktok: 'TikTok',
    twitch: 'Twitch',
    site: 'Site web',
  };
</script>

<svelte:head>
  <title>{profile.display_name || username} - Philum</title>
  {#if profile.description}
    <meta name="description" content={profile.description} />
  {/if}
</svelte:head>

<div class="min-h-screen bg-surface-secondary">
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <header class="bg-white rounded-xl shadow-xs border border-border p-8 mb-8">
      <div class="flex items-start gap-6">
        <Avatar
          avatarUrl={profile.avatar_url}
          name={profile.display_name || profile.slug}
          size="xl"
          verified={true}
        />
        <div class="flex-1">
          <h1 class="text-3xl font-bold text-ink-primary mb-2">
            {profile.display_name || profile.slug}
          </h1>
          {#if profile.description}
            <p class="text-ink-secondary mb-4">{profile.description}</p>
          {/if}
          {#if profile.linked_accounts.length > 0}
            <div class="flex flex-wrap gap-2 mb-4">
              {#each profile.linked_accounts as account (account.platform + account.url)}
                <a
                  href={account.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-border bg-surface-secondary text-sm text-ink-secondary hover:text-ink-primary hover:border-ink-tertiary transition-colors"
                >
                  <span class="font-medium"
                    >{platformLabels[account.platform] ?? account.platform}</span
                  >
                  {#if account.handle}
                    <span class="text-ink-tertiary">{account.handle}</span>
                  {/if}
                  {#if account.verified}
                    <svg
                      class="w-3.5 h-3.5 text-info"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                      aria-label="Compte vérifié"
                    >
                      <path
                        fill-rule="evenodd"
                        d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z"
                        clip-rule="evenodd"
                      />
                    </svg>
                  {/if}
                </a>
              {/each}
            </div>
          {/if}
          <div class="flex flex-wrap gap-4 text-sm text-ink-tertiary">
            <span>{profile.stats.total_cards} fiches</span>
            <span>·</span>
            <span>{profile.stats.total_sources} sources</span>
            {#if profile.stats.first_published_at}
              <span>·</span>
              <span
                >Depuis {new Date(profile.stats.first_published_at).toLocaleDateString('fr-FR', {
                  month: 'short',
                  year: 'numeric',
                })}</span
              >
            {/if}
          </div>
        </div>
      </div>
    </header>

    <section>
      <h2 class="text-xl font-semibold text-ink-primary mb-4">Fiches publiées</h2>
      {#if profile.cards.length === 0}
        <p class="text-ink-tertiary">Aucune fiche publiée</p>
      {:else}
        <div class="space-y-4">
          {#each profile.cards as card}
            <a
              href="/@{username}/{card.slug}"
              class="block bg-white rounded-xl border border-border p-6 hover:shadow-md transition-shadow"
            >
              <div class="flex items-center justify-between">
                <div>
                  <h3 class="font-semibold text-ink-primary">{card.title}</h3>
                  <p class="text-sm text-ink-tertiary mt-1">
                    {card.total_sources} sources
                    {#if card.published_at}
                      · Publiée le {new Date(card.published_at).toLocaleDateString('fr-FR')}
                    {/if}
                  </p>
                </div>
                <svg
                  class="w-5 h-5 text-ink-tertiary"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </a>
          {/each}
        </div>
      {/if}
    </section>
  </div>
</div>
