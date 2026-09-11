<script lang="ts">
  import { onMount, tick, type Snippet } from 'svelte';
  import { afterNavigate, goto } from '$app/navigation';
  import { agentApi, type AgentSession } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, Skeleton, toast } from '$lib/components';
  import {
    conversations,
    nouvelleConversation,
    rafraichirConversations,
  } from '$lib/agent/sessions.svelte';
  import { filtrerConversations, grouperParDate } from '$lib/agent/groupesDates';

  let { children }: { children: Snippet } = $props();

  let confirmOpen = $state(false);
  let cible = $state<AgentSession | null>(null);
  let recherche = $state('');
  // Renommage en place, depuis la liste : il n'existait que dans la page de
  // la conversation, qu'il fallait d'abord ouvrir.
  let renommage = $state<{ id: string; brouillon: string } | null>(null);
  let champRenommage = $state<HTMLInputElement | null>(null);

  const groupes = $derived(grouperParDate(filtrerConversations(conversations.liste, recherche)));

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

  // Ctrl+Maj+O ouvre une conversation, comme dans ChatGPT.
  function surTouche(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'o') {
      e.preventDefault();
      ouvrirNouvelle();
    }
  }

  async function commencerRenommage(session: AgentSession) {
    renommage = { id: session.id, brouillon: session.title };
    await tick();
    champRenommage?.select();
  }

  async function validerRenommage() {
    if (!renommage) return;
    const { id, brouillon } = renommage;
    renommage = null;
    const titre = brouillon.trim();
    const actuel = conversations.liste.find((s) => s.id === id)?.title;
    if (!titre || titre === actuel) return;
    try {
      await agentApi.sessions.update(id, { title: titre });
      await rafraichirConversations();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Renommage impossible.');
    }
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

<svelte:window onkeydown={surTouche} />

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
        <Button size="sm" variant="ghost" onclick={ouvrirNouvelle} title="Nouvelle (Ctrl+Maj+O)"
          >Nouvelle</Button
        >
      </div>
    </div>
    {#if conversations.liste.length > 0}
      <input
        type="search"
        bind:value={recherche}
        class="mb-3 w-full rounded border border-border bg-surface-primary px-2 py-1 text-sm"
        placeholder="Chercher une conversation"
        aria-label="Chercher une conversation"
      />
    {/if}
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
    {:else if groupes.length === 0}
      <p class="text-sm text-ink-tertiary">Aucun titre ne contient « {recherche.trim()} ».</p>
    {:else}
      <!-- La liste defile pour son compte : sans borne, chaque conversation
           gardee allongeait la page et repoussait le fil de discussion. -->
      <div class="min-h-0 flex-1 space-y-4 overflow-x-hidden overflow-y-auto">
        {#each groupes as groupe (groupe.libelle)}
          <section>
            <h3 class="mb-1 px-2 text-xs text-ink-tertiary">{groupe.libelle}</h3>
            <ul class="space-y-0.5">
              {#each groupe.sessions as session (session.id)}
                {@const active = session.id === conversations.active}
                <li class="group flex items-center gap-0.5">
                  {#if renommage?.id === session.id}
                    <input
                      bind:this={champRenommage}
                      bind:value={renommage.brouillon}
                      class="min-w-0 flex-1 rounded border border-info bg-surface-primary px-2 py-1 text-sm"
                      maxlength="200"
                      aria-label="Nouveau nom de la conversation"
                      onblur={validerRenommage}
                      onkeydown={(e) => {
                        if (e.key === 'Enter') e.currentTarget.blur();
                        if (e.key === 'Escape') renommage = null;
                      }}
                    />
                  {:else}
                    <a
                      href="/dashboard/chat/{session.id}"
                      aria-current={active ? 'page' : undefined}
                      class="min-w-0 flex-1 truncate rounded px-2 py-1.5 text-sm hover:bg-surface-tertiary hover:text-ink-primary"
                      class:bg-surface-tertiary={active}
                      class:text-ink-primary={active}
                      class:font-medium={active}
                      class:text-ink-secondary={!active}
                      ondblclick={(e) => {
                        e.preventDefault();
                        void commencerRenommage(session);
                      }}
                    >
                      {session.title}
                    </a>
                    <!-- Visibles au survol et au clavier : toujours affiches,
                         ils mangeaient la place des titres. -->
                    <button
                      type="button"
                      class="rounded p-1 text-ink-tertiary opacity-0 transition-opacity hover:bg-surface-tertiary hover:text-ink-primary focus:opacity-100 group-hover:opacity-100"
                      title="Renommer"
                      aria-label="Renommer « {session.title} »"
                      onclick={() => commencerRenommage(session)}
                    >
                      <svg
                        viewBox="0 0 16 16"
                        width="14"
                        height="14"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="1.5"
                        aria-hidden="true"
                      >
                        <path d="M11 2.5l2.5 2.5L6 12.5H3.5V10z" />
                      </svg>
                    </button>
                    <button
                      type="button"
                      class="rounded px-1.5 py-1 leading-none text-ink-tertiary opacity-0 transition-opacity hover:bg-danger-bg hover:text-danger focus:opacity-100 group-hover:opacity-100"
                      title="Supprimer"
                      aria-label="Supprimer « {session.title} »"
                      onclick={() => {
                        cible = session;
                        confirmOpen = true;
                      }}
                    >
                      ×
                    </button>
                  {/if}
                </li>
              {/each}
            </ul>
          </section>
        {/each}
      </div>
    {/if}
    <!-- En bas plutot qu'a cote de « Nouvelle » : dans 16 rem, le second
         bouton sortait du cadre, coupe en « Clé » (capture du 2026-09-11). -->
    <a
      href="/dashboard/agents"
      class="mt-3 shrink-0 border-t border-border px-2 pt-3 text-xs text-ink-tertiary hover:text-ink-primary"
    >
      Gérer vos clés
    </a>
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
