<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { agentApi, type AgentSession } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, toast } from '$lib/components';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

  let sessions = $state<AgentSession[]>([]);
  let confirmOpen = $state(false);
  let cible = $state<AgentSession | null>(null);

  onMount(async () => {
    try {
      sessions = await agentApi.sessions.list();
    } catch {
      // Une conversation qu'on n'arrive pas à lister n'empêche pas d'en ouvrir une.
    }
  });

  async function supprimer() {
    if (!cible) return;
    const session = cible;
    cible = null;
    try {
      await agentApi.sessions.remove(session.id);
      sessions = sessions.filter((s) => s.id !== session.id);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Suppression impossible.');
    }
  }
</script>

<svelte:head>
  <title>Agent · Philum</title>
</svelte:head>

<div class="max-w-5xl mx-auto grid gap-8 px-4 sm:px-6 lg:px-8 py-8 lg:grid-cols-[16rem_1fr]">
  <aside>
    <div class="flex items-center justify-between gap-2 mb-3">
      <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary">Conversations</h2>
      <Button size="sm" variant="ghost" href="/dashboard/agents">Providers</Button>
    </div>
    {#if sessions.length === 0}
      <p class="text-sm text-ink-tertiary">Aucune conversation pour l'instant.</p>
    {:else}
      <ul class="space-y-1">
        {#each sessions as session (session.id)}
          <li class="flex items-center gap-1">
            <a
              href="/dashboard/chat/{session.id}"
              class="flex-1 truncate rounded px-2 py-1.5 text-sm text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary"
            >
              {session.title}
            </a>
            <button
              type="button"
              class="action-icon"
              title="Supprimer"
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

  <section class="min-h-[60vh]">
    <h1 class="font-serif text-3xl text-ink-primary mb-1">Agent</h1>
    <p class="text-sm text-ink-secondary mb-4">
      L'agent utilise la clé du provider marqué par défaut. Il lit et écrit vos fiches avec votre
      compte, jamais celui d'un autre.
    </p>
    <ChatPanel onsession={(id) => goto(`/dashboard/chat/${id}`, { replaceState: true })} />
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
