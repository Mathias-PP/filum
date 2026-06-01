<script lang="ts">
  import { onMount } from 'svelte';
  import { currentUser } from '$lib/stores';
  import { api } from '$lib/api';
  import { Button, Skeleton, EmptyState, ConfirmDialog, toast } from '$lib/components';
  import type { Card as CardType } from '$lib/api';

  let loading = $state(true);
  let userCards = $state<CardType[]>([]);
  let confirmOpen = $state(false);
  let confirmTarget = $state<CardType | null>(null);

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
      toast.success(`Fiche « ${target.title} » supprimée.`);
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    } finally {
      confirmTarget = null;
    }
  }

  onMount(async () => {
    try {
      userCards = await api.cards.list();
    } catch (err) {
      toast.danger(err instanceof Error ? err.message : 'Erreur de chargement des fiches');
    } finally {
      loading = false;
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
    <Button href="/dashboard/new" variant="primary">+ Nouvelle fiche</Button>
  </div>

  {#if loading}
    <div class="space-y-3">
      {#each Array(3) as _, i (i)}
        <Skeleton variant="card" height="5rem" />
      {/each}
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
