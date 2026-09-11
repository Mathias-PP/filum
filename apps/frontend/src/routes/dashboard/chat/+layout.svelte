<script lang="ts">
  import { onMount, type Snippet } from 'svelte';
  import { afterNavigate, goto } from '$app/navigation';
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

  // Choisir une conversation dans le tiroir le referme.
  afterNavigate(() => {
    conversations.tiroirOuvert = false;
  });

  function ouvrirNouvelle() {
    conversations.tiroirOuvert = false;
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

<!-- Une mise en page d'application : pleine largeur, a la hauteur exacte sous
     la barre du site (h-14 et sa bordure), sans pied de page. En colonne de
     1024 px centree, la conversation n'avait que 44 % de l'ecran.

     `minmax(0, 1fr)` et non `1fr` : `1fr` vaut `minmax(auto, 1fr)`, et la
     colonne s'etirait a la largeur de son contenu. Un resultat d'outil de
     3 000 caracteres portait la conversation a 21 736 px de large. -->
<div class="grid h-[calc(100dvh-3.5rem-1px)] overflow-hidden lg:grid-cols-[16rem_minmax(0,1fr)]">
  {#if conversations.tiroirOuvert}
    <button
      type="button"
      class="fixed inset-0 z-30 bg-black/40 lg:hidden"
      aria-label="Fermer la liste des conversations"
      onclick={() => (conversations.tiroirOuvert = false)}
    ></button>
  {/if}

  <aside
    class="min-w-0 flex-col border-r border-border bg-surface-secondary px-3 py-4 lg:static lg:z-auto lg:flex lg:min-h-0 lg:w-auto lg:max-w-none lg:shadow-none"
    class:hidden={!conversations.tiroirOuvert}
    class:flex={conversations.tiroirOuvert}
    class:fixed={conversations.tiroirOuvert}
    class:inset-y-0={conversations.tiroirOuvert}
    class:left-0={conversations.tiroirOuvert}
    class:z-40={conversations.tiroirOuvert}
    class:w-72={conversations.tiroirOuvert}
    class:shadow-xl={conversations.tiroirOuvert}
    aria-label="Conversations"
  >
    <div class="mb-3 flex items-center justify-between gap-2">
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
      <ul class="min-h-0 flex-1 space-y-1 overflow-x-hidden overflow-y-auto">
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

  <section class="flex min-h-0 min-w-0 flex-col px-4 pb-3 pt-3 sm:px-6">
    <div class="mb-2 shrink-0 lg:hidden">
      <button
        type="button"
        class="rounded border border-border px-2.5 py-1 text-xs text-ink-secondary hover:text-ink-primary"
        aria-expanded={conversations.tiroirOuvert}
        onclick={() => (conversations.tiroirOuvert = true)}
      >
        Conversations
      </button>
    </div>
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
