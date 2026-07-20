<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth, currentUser } from '$lib/stores';
  import { api, ApiError } from '$lib/api';
  import { Button, Skeleton, EmptyState, ConfirmDialog, toast } from '$lib/components';
  import type { Card as CardType, LinkedAccountIn, LinkedPlatform } from '$lib/api';

  let loading = $state(true);
  let loadFailed = $state(false);
  let userCards = $state<CardType[]>([]);
  let deletedCards = $state<CardType[]>([]);
  let showTrash = $state(false);
  let confirmOpen = $state(false);
  let confirmTarget = $state<CardType | null>(null);

  let accounts = $state<LinkedAccountIn[]>([]);
  let accountsLoaded = $state(false);
  let accountsSaving = $state(false);
  let accountsDirty = $state(false);

  const platformOptions: Array<{ value: LinkedPlatform; label: string }> = [
    { value: 'youtube', label: 'YouTube' },
    { value: 'instagram', label: 'Instagram' },
    { value: 'x', label: 'X' },
    { value: 'tiktok', label: 'TikTok' },
    { value: 'twitch', label: 'Twitch' },
    { value: 'site', label: 'Site web' },
  ];

  function addAccountRow() {
    accounts = [...accounts, { platform: 'youtube', url: '', handle: '' }];
    accountsDirty = true;
  }

  function removeAccountRow(index: number) {
    accounts = accounts.filter((_, i) => i !== index);
    accountsDirty = true;
  }

  async function saveAccounts() {
    accountsSaving = true;
    try {
      const payload = accounts
        .filter((a) => a.url.trim().length > 0)
        .map((a) => ({
          platform: a.platform,
          url: a.url.trim(),
          handle: a.handle?.trim() || null,
        }));
      const saved = await api.users.setLinkedAccounts(payload);
      accounts = saved.map((a) => ({ platform: a.platform, url: a.url, handle: a.handle ?? '' }));
      accountsDirty = false;
      toast.success('Plateformes enregistrées.');
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    } finally {
      accountsSaving = false;
    }
  }

  const drafts = $derived(userCards.filter((c) => c.status === 'draft'));
  const published = $derived(userCards.filter((c) => c.status === 'published'));
  const total = $derived(userCards.length);

  function askDelete(card: CardType) {
    confirmTarget = card;
    confirmOpen = true;
  }

  async function confirmDelete() {
    if (!confirmTarget) return;
    const target = confirmTarget;
    try {
      await api.cards.delete(target.id);
      userCards = userCards.filter((c) => c.id !== target.id);
      // La fiche rejoint la corbeille : recharger la liste si elle est ouverte.
      if (showTrash) await loadTrash();
      toast.success(`Fiche « ${target.title} » supprimée. Restaurable depuis la corbeille.`);
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      confirmTarget = null;
    }
  }

  async function loadTrash() {
    try {
      deletedCards = await api.cards.listDeleted();
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : 'Erreur de chargement de la corbeille');
    }
  }

  async function toggleTrash() {
    showTrash = !showTrash;
    if (showTrash && deletedCards.length === 0) await loadTrash();
  }

  async function restoreCard(card: CardType) {
    try {
      const restored = await api.cards.restore(card.id);
      deletedCards = deletedCards.filter((c) => c.id !== card.id);
      userCards = [restored, ...userCards];
      toast.success(`Fiche « ${card.title} » restaurée.`);
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : 'Erreur lors de la restauration');
    }
  }

  onMount(async () => {
    try {
      userCards = await api.cards.list();
    } catch (err) {
      // Session expirée : sans cette redirection, le dashboard affichait
      // "Aucune fiche" — les créateurs croyaient leurs fiches supprimées.
      if (err instanceof ApiError && err.status === 401) {
        auth.reset();
        toast.danger('Votre session a expiré. Reconnectez-vous pour retrouver vos fiches.');
        goto('/');
        return;
      }
      loadFailed = true;
      toast.danger(err instanceof Error ? err.message : 'Erreur de chargement des fiches');
    } finally {
      loading = false;
    }
    try {
      const existing = await api.users.getLinkedAccounts();
      accounts = existing.map((a) => ({
        platform: a.platform,
        url: a.url,
        handle: a.handle ?? '',
      }));
    } catch {
      // Section non bloquante : le dashboard reste utilisable sans.
    } finally {
      accountsLoaded = true;
    }
  });

  function formatDate(iso: string) {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  }
</script>

<svelte:head>
  <title>Tableau de bord — Philum</title>
</svelte:head>

<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
    <div>
      <h1 class="font-serif text-3xl text-ink-primary mb-1">Tableau de bord</h1>
      <p class="text-sm text-ink-secondary">
        {#if loading}
          Chargement de vos fiches…
        {:else}
          {total} fiche{total > 1 ? 's' : ''} · {drafts.length} brouillon{drafts.length > 1
            ? 's'
            : ''} · {published.length} publiée{published.length > 1 ? 's' : ''}
        {/if}
      </p>
    </div>
    <div class="flex flex-wrap gap-2">
      <Button href="/dashboard/from-url" variant="secondary">
        <span class="inline-flex items-center gap-1.5">
          <svg
            class="w-4 h-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
            />
          </svg>
          Depuis une URL
        </span>
      </Button>
      <Button href="/dashboard/new" variant="primary">+ Nouvelle fiche</Button>
    </div>
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each Array(3) as _, i (i)}
        <Skeleton variant="card" height="5rem" />
      {/each}
    </div>
  {:else if loadFailed}
    <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-4 text-sm text-danger">
      <p class="font-medium mb-1">Impossible de charger vos fiches.</p>
      <p>
        Vos fiches ne sont pas perdues — c'est un problème de connexion au serveur. Rechargez la
        page dans quelques instants.
      </p>
    </div>
  {:else if userCards.length === 0}
    <EmptyState
      title="Aucune fiche"
      description="Commencez par créer votre première fiche bibliographique. Vous pourrez y ajouter des sources, les archiver et publier une page interactive."
    >
      {#snippet icon()}
        <svg
          class="w-12 h-12"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      {/snippet}
      {#snippet action()}
        <Button href="/dashboard/new" variant="primary">Créer ma première fiche</Button>
      {/snippet}
    </EmptyState>
  {:else}
    <div class="space-y-8">
      {#if drafts.length > 0}
        <section>
          <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary mb-3">
            Brouillons ({drafts.length})
          </h2>
          <ul class="space-y-2">
            {#each drafts as card (card.id)}
              <li class="card-row group">
                <a
                  href="/dashboard/new/{card.id}/sources"
                  class="flex-1 min-w-0 transition-colors hover:text-info"
                >
                  <p class="font-medium text-ink-primary truncate group-hover:text-info">
                    {card.title}
                  </p>
                  <p class="text-xs text-ink-tertiary mt-0.5">
                    Créé le {formatDate(card.created_at)}
                  </p>
                </a>
                <div class="card-row-actions">
                  {#if card.is_seed}
                    <span
                      class="badge-soft"
                      title="Fiche créée pour un contenu dont vous n'êtes pas l'auteur·ice"
                      >Non revendiquée</span
                    >
                  {/if}
                  <span class="badge-soft">Brouillon</span>
                  <button
                    type="button"
                    class="action-icon"
                    onclick={(e) => {
                      e.preventDefault();
                      askDelete(card);
                    }}
                    aria-label="Supprimer le brouillon"
                    title="Supprimer"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      class="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      aria-hidden="true"
                    >
                      <line x1="6" y1="6" x2="18" y2="18" />
                      <line x1="6" y1="18" x2="18" y2="6" />
                    </svg>
                  </button>
                </div>
              </li>
            {/each}
          </ul>
        </section>
      {/if}

      {#if published.length > 0}
        <section>
          <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary mb-3">
            Publiées ({published.length})
          </h2>
          <ul class="space-y-2">
            {#each published as card (card.id)}
              <li class="card-row group">
                <div class="flex-1 min-w-0">
                  <p class="font-medium text-ink-primary truncate">{card.title}</p>
                  <p class="text-xs text-ink-tertiary mt-0.5">
                    Publiée le {formatDate(card.published_at || card.created_at)}
                  </p>
                </div>
                <div class="card-row-actions">
                  {#if card.is_seed}
                    <span
                      class="badge-soft"
                      title="Fiche créée pour un contenu dont vous n'êtes pas l'auteur·ice"
                      >Non revendiquée</span
                    >
                  {/if}
                  <span class="badge-published">Publiée</span>
                  <Button
                    href="/@{$currentUser?.username}/{card.slug}"
                    variant="secondary"
                    size="sm"
                  >
                    Voir
                  </Button>
                  <Button href="/dashboard/new/{card.id}/sources" variant="ghost" size="sm">
                    Éditer
                  </Button>
                  <button
                    type="button"
                    class="action-icon"
                    onclick={() => askDelete(card)}
                    aria-label="Supprimer la fiche"
                    title="Supprimer"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      class="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      aria-hidden="true"
                    >
                      <line x1="6" y1="6" x2="18" y2="18" />
                      <line x1="6" y1="18" x2="18" y2="6" />
                    </svg>
                  </button>
                </div>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
    </div>
  {/if}

  <section class="mt-10">
    <button
      type="button"
      onclick={toggleTrash}
      class="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-ink-tertiary hover:text-ink-primary transition-colors mb-3"
    >
      <svg
        viewBox="0 0 20 20"
        class="w-3.5 h-3.5 transition-transform"
        style:transform={showTrash ? 'rotate(90deg)' : 'rotate(0)'}
        fill="currentColor"
        aria-hidden="true"
      >
        <path
          fill-rule="evenodd"
          d="M7.293 4.707a1 1 0 011.414 0l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414-1.414L10.586 10 7.293 6.707a1 1 0 010-1.414z"
          clip-rule="evenodd"
        />
      </svg>
      Corbeille{deletedCards.length > 0 ? ` (${deletedCards.length})` : ''}
    </button>

    {#if showTrash}
      {#if deletedCards.length === 0}
        <p class="text-sm text-ink-tertiary italic">
          Aucune fiche supprimée. Les fiches supprimées atterrissent ici et sont restaurables tant
          qu'elles n'ont pas été purgées.
        </p>
      {:else}
        <ul class="space-y-2">
          {#each deletedCards as card (card.id)}
            <li class="card-row group opacity-70">
              <div class="flex-1 min-w-0">
                <p class="font-medium text-ink-primary truncate">{card.title}</p>
                <p class="text-xs text-ink-tertiary mt-0.5">
                  Supprimée · statut d'origine : {card.status === 'published'
                    ? 'publiée'
                    : 'brouillon'}
                </p>
              </div>
              <div class="card-row-actions">
                <Button variant="secondary" size="sm" onclick={() => restoreCard(card)}>
                  Restaurer
                </Button>
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    {/if}
  </section>

  <section class="mt-12">
    <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary mb-1">
      Mes plateformes
    </h2>
    <p class="text-sm text-ink-secondary mb-4">
      Liez vos comptes (YouTube, X, TikTok…) : ils apparaîtront sur votre profil public.
    </p>
    {#if !accountsLoaded}
      <Skeleton variant="card" height="3rem" />
    {:else}
      <div class="space-y-2">
        {#each accounts as account, i (i)}
          <div class="account-row">
            <select
              class="account-input w-32 flex-shrink-0"
              bind:value={account.platform}
              onchange={() => (accountsDirty = true)}
              aria-label="Plateforme"
            >
              {#each platformOptions as opt (opt.value)}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
            <input
              type="url"
              class="account-input flex-1 min-w-0"
              placeholder="https://youtube.com/@machaine"
              bind:value={account.url}
              oninput={() => (accountsDirty = true)}
              aria-label="URL du compte"
            />
            <input
              type="text"
              class="account-input w-36 flex-shrink-0 hidden sm:block"
              placeholder="@handle (optionnel)"
              bind:value={account.handle}
              oninput={() => (accountsDirty = true)}
              aria-label="Handle"
            />
            <button
              type="button"
              class="action-icon"
              onclick={() => removeAccountRow(i)}
              aria-label="Retirer cette plateforme"
              title="Retirer"
            >
              <svg
                viewBox="0 0 24 24"
                class="w-4 h-4"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                aria-hidden="true"
              >
                <line x1="6" y1="6" x2="18" y2="18" />
                <line x1="6" y1="18" x2="18" y2="6" />
              </svg>
            </button>
          </div>
        {/each}
        <div class="flex items-center gap-2 pt-1">
          <Button
            variant="secondary"
            size="sm"
            onclick={addAccountRow}
            disabled={accounts.length >= 12}
          >
            + Ajouter une plateforme
          </Button>
          {#if accountsDirty}
            <Button variant="primary" size="sm" onclick={saveAccounts} loading={accountsSaving}>
              Enregistrer
            </Button>
          {/if}
        </div>
      </div>
    {/if}
  </section>
</div>

<ConfirmDialog
  bind:open={confirmOpen}
  title="Supprimer la fiche ?"
  message={confirmTarget
    ? `« ${confirmTarget.title} » sera supprimée définitivement. Cette action est irréversible.`
    : ''}
  confirmLabel="Supprimer"
  variant="danger"
  onConfirm={confirmDelete}
/>

<style>
  .card-row {
    background: rgb(var(--bg-primary));
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    padding: 0.875rem 1rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    transition: border-color 150ms ease;
  }
  .card-row:hover {
    border-color: rgb(var(--border-strong));
  }
  .card-row-actions {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    flex-shrink: 0;
  }
  .badge-soft {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    background: rgb(var(--bg-tertiary));
    color: rgb(var(--text-secondary));
  }
  .badge-published {
    display: inline-flex;
    align-items: center;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    background: rgb(var(--success-bg));
    color: rgb(var(--success));
  }
  .account-row {
    background: rgb(var(--bg-primary));
    border: 1px solid rgb(var(--border));
    border-radius: 8px;
    padding: 0.5rem 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .account-input {
    border: 1px solid rgb(var(--border));
    border-radius: 6px;
    padding: 0.375rem 0.5rem;
    font-size: 0.875rem;
    background: rgb(var(--bg-primary));
    color: rgb(var(--text-primary));
  }
  .account-input:focus {
    outline: none;
    border-color: rgb(var(--border-strong));
  }
  .action-icon {
    padding: 0.375rem;
    color: rgb(var(--text-tertiary));
    border-radius: 4px;
    transition:
      color 150ms ease,
      background 150ms ease;
    background: transparent;
    border: none;
    cursor: pointer;
  }
  .action-icon:hover {
    color: rgb(var(--danger));
    background: rgb(var(--danger-bg));
  }
</style>
