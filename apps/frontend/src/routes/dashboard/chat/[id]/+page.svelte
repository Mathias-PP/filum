<script lang="ts">
  import { page } from '$app/stores';
  import { Button } from '$lib/components';
  import { agentApi } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { toast } from '$lib/components/Toast.svelte';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';
  import { conversations, rafraichirConversations } from '$lib/agent/sessions.svelte';

  const sessionId = $derived($page.params.id);

  let titre = $state('');
  let edition = $state(false);
  let brouillon = $state('');
  // Un renommage fait depuis la liste doit se voir ici aussi.
  const titreAffiche = $derived(
    conversations.liste.find((s) => s.id === sessionId)?.title ?? titre
  );

  $effect(() => {
    conversations.active = sessionId ?? null;
    if (!sessionId) return;
    agentApi.sessions
      .get(sessionId)
      .then((s) => {
        titre = s.title || 'Nouvelle conversation';
      })
      .catch(() => null);
  });

  function ouvrirEdition() {
    brouillon = titreAffiche;
    edition = true;
  }

  async function renommer() {
    if (!brouillon.trim() || !sessionId) {
      edition = false;
      return;
    }
    try {
      await agentApi.sessions.update(sessionId, { title: brouillon.trim() });
      titre = brouillon.trim();
      await rafraichirConversations();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Renommage impossible.');
    } finally {
      edition = false;
    }
  }
</script>

<svelte:head>
  <title>{titreAffiche || 'Agent'} · Philum</title>
</svelte:head>

<div class="flex h-full min-h-0 flex-col">
  <div class="mx-auto flex w-full max-w-4xl shrink-0 items-center gap-2 pb-2">
    {#if edition}
      <form
        class="flex min-w-0 flex-1 items-center gap-1"
        onsubmit={(e) => {
          e.preventDefault();
          void renommer();
        }}
      >
        <!-- svelte-ignore a11y_autofocus -->
        <input
          bind:value={brouillon}
          class="min-w-0 flex-1 rounded border border-border bg-surface-primary px-2 py-1 font-serif text-xl"
          maxlength="200"
          aria-label="Nom de la conversation"
          autofocus
          onkeydown={(e) => {
            if (e.key === 'Escape') edition = false;
          }}
        />
        <Button size="sm" type="submit">OK</Button>
        <Button size="sm" variant="ghost" onclick={() => (edition = false)}>Annuler</Button>
      </form>
    {:else}
      <!-- Cliquer le titre le renomme, comme dans la liste de Claude et de
           ChatGPT ; le bouton reste pour qui ne le devine pas. -->
      <button
        type="button"
        class="min-w-0 truncate py-1 text-left font-serif text-xl text-ink-primary"
        title="Renommer"
        onclick={ouvrirEdition}
      >
        {titreAffiche}
      </button>
      <button
        type="button"
        class="shrink-0 rounded px-1.5 py-0.5 text-xs text-ink-tertiary hover:bg-surface-tertiary hover:text-ink-primary"
        onclick={ouvrirEdition}
      >
        Renommer
      </button>
    {/if}
  </div>
  <div class="min-h-0 flex-1">
    {#key sessionId}
      <ChatPanel {sessionId} />
    {/key}
  </div>
</div>
