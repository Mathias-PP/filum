<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { goto } from '$app/navigation';
  import { agentApi, type AgentSession } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, Skeleton, toast } from '$lib/components';
  import {
    conversations,
    nouvelleConversation,
    rafraichirConversations,
  } from '$lib/agent/sessions.svelte';

  let { children }: { children: Snippet } = $props();

  let confirmOpen = $state(false);
  let cible = $state<AgentSession | null>(null);

  onMount(() => {
    void rafraichirConversations();
  });

  function ouvrirNouvelle() {
    nouvelleConversation();
    void goto('/dashboard/chat');
  }

  async function supprimer() {
    if (!cible) return;
    const session = cible;
    cible = null;
    try {
      await agentApi.sessions.remove(session.id);
      conversations.liste = conversations.liste.filter((s) => s.id !== session.id);
      // Supprimer la conversation affichée laissait l'écran sur un fil qui
      // n'existe plus : le prochain message aurait visé une session supprimée.
      if (session.id === conversations.active) ouvrirNouvelle();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Suppression impossible.');
    }
  }
</script>

<!-- Une seule mise en page pour la liste et pour chaque conversation : la page
     d'une conversation n'avait pas de barre laterale, on ne passait d'une
     conversation a l'autre qu'en revenant en arriere.

     `minmax(0, 1fr)` et non `1fr` : `1fr` vaut `minmax(auto, 1fr)`, et la
     colonne s'etirait a la largeur de son contenu. Un resultat d'outil de
     3 000 caracteres portait la conversation a 21 736 px de large. -->
<div
  class="max-w-5xl mx-auto grid gap-8 px-4 sm:px-6 lg:px-8 py-8 lg:h-[calc(100dvh-4rem)] lg:grid-cols-[16rem_minmax(0,1fr)]"
>
  <aside class="flex min-w-0 flex-col lg:min-h-0">
    <div class="flex items-center justify-between gap-2 mb-3">
      <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary">Conversations</h2>
      <div class="flex gap-1">
        <Button size="sm" variant="ghost" onclick={ouvrirNouvelle}>Nouvelle</Button>
        <Button size="sm" variant="ghost" href="/dashboard/agents">Clés</Button>
      </div>
    </div>
    {#if conversations.chargement}
      <div class="space-y-2">
        <Skeleton height="1.75rem" />
        <Skeleton height="1.75rem" />
        <Skeleton height="1.75rem" />
      </div>
    {:else if conversations.echec && conversations.liste.length === 0}
      <p class="text-sm text-danger">
        Vos conversations n'ont pas pu être chargées. Rechargez la page : rien n'est perdu.
      </p>
    {:else if conversations.liste.length === 0}
      <p class="text-sm text-ink-tertiary">Aucune conversation pour l'instant.</p>
    {:else}
      <!-- La liste defile pour son compte : sans borne, chaque conversation
           gardee allongeait la page et repoussait le fil de discussion. -->
      <ul class="space-y-1 lg:min-h-0 lg:flex-1 lg:overflow-x-hidden lg:overflow-y-auto">
        {#each conversations.liste as session (session.id)}
          {@const active = session.id === conversations.active}
          <li class="flex items-center gap-1">
            <a
              href="/dashboard/chat/{session.id}"
              aria-current={active ? 'page' : undefined}
              class="min-w-0 flex-1 truncate rounded px-2 py-1.5 text-sm hover:bg-surface-tertiary hover:text-ink-primary"
              class:bg-surface-tertiary={active}
              class:text-ink-primary={active}
              class:font-medium={active}
              class:text-ink-secondary={!active}
            >
              {session.title}
            </a>
            <button
              type="button"
              class="rounded px-2 py-1 leading-none text-ink-tertiary transition-colors hover:bg-danger-bg hover:text-danger"
              title="Supprimer"
              aria-label="Supprimer « {session.title} »"
              onclick={() => {
                cible = session;
                confirmOpen = true;
              }}
            >
              ×
            </button>
          </li>
        {/each}
      </ul>
    {/if}
  </aside>

  <section class="flex h-[calc(100dvh-4rem)] min-w-0 flex-col lg:h-auto lg:min-h-0">
    {@render children()}
  </section>
</div>

<ConfirmDialog
  bind:open={confirmOpen}
  title="Supprimer cette conversation ?"
  message={cible ? `« ${cible.title} » sortira de la liste.` : ''}
  confirmLabel="Supprimer"
  variant="danger"
  onConfirm={supprimer}
  onCancel={() => (cible = null)}
/>
