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
    brouillon = titre;
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
  <title>{titre || 'Agent'} · Philum</title>
</svelte:head>

<div class="flex h-full min-h-0 flex-col">
  <div class="mb-4 flex shrink-0 items-center gap-2 min-w-0">
    <!-- Sous `lg`, la liste est au-dessus : le retour y ramene. Au-dela, elle
         est a cote et le bouton ferait doublon. -->
    <span class="lg:hidden">
      <Button size="sm" variant="ghost" href="/dashboard/chat" title="Retour aux conversations">
        &larr;
      </Button>
    </span>
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
          class="min-w-0 flex-1 rounded border border-border bg-surface-primary px-2 py-1 text-sm"
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
      <h1 class="min-w-0 truncate font-serif text-2xl text-ink-primary">{titre}</h1>
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
