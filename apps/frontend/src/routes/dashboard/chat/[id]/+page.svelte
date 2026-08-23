<script lang="ts">
  import { page } from '$app/stores';
  import { Button } from '$lib/components';
  import { agentApi } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { toast } from '$lib/components/Toast.svelte';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

  const sessionId = $derived($page.params.id);

  let titre = $state('Agent');
  let edition = $state(false);
  let brouillon = $state('');

  $effect(() => {
    void sessionId;
    if (!sessionId) return;
    agentApi.sessions
      .get(sessionId)
      .then((s) => {
        titre = s.title || 'Agent';
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
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Renommage impossible.');
    } finally {
      edition = false;
    }
  }
</script>

<svelte:head>
  <title>{titre} · Philum</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-4 flex items-center justify-between gap-2">
    <div class="flex items-center gap-2 min-w-0">
      <Button size="sm" variant="ghost" href="/dashboard/chat" title="Retour aux conversations">
        &larr;
      </Button>
      {#if edition}
        <form
          class="flex items-center gap-1"
          onsubmit={(e) => {
            e.preventDefault();
            void renommer();
          }}
        >
          <input
            bind:value={brouillon}
            class="rounded border border-border bg-surface-primary px-2 py-1 text-sm"
            maxlength="200"
            autofocus
            onkeydown={(e) => {
              if (e.key === 'Escape') edition = false;
            }}
          />
          <Button size="sm" type="submit">OK</Button>
          <Button size="sm" variant="ghost" onclick={() => (edition = false)}>Annuler</Button>
        </form>
      {:else}
        <h1 class="truncate font-serif text-2xl text-ink-primary">{titre}</h1>
        <button
          type="button"
          class="shrink-0 text-ink-tertiary hover:text-ink-primary"
          title="Renommer"
          onclick={ouvrirEdition}
        >
          ✏
        </button>
      {/if}
    </div>
    <Button size="sm" variant="ghost" href="/dashboard/agents">Clés</Button>
  </div>
  <div>
    {#key sessionId}
      <ChatPanel {sessionId} />
    {/key}
  </div>
</div>
