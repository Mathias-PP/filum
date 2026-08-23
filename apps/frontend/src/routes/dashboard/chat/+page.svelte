<script lang="ts">
  import { onMount } from 'svelte';
  import { agentApi, type AgentSession, type AgentProvider } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, toast } from '$lib/components';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

  let sessions = $state<AgentSession[]>([]);
  let providers = $state<AgentProvider[]>([]);
  let confirmOpen = $state(false);
  let cible = $state<AgentSession | null>(null);
  let titreNouveau = $state('');

  const defaut = $derived(providers.find((p) => p.is_default) ?? null);

  onMount(async () => {
    const [s, p] = await Promise.all([
      agentApi.sessions.list().catch(() => []),
      agentApi.providers.list().catch(() => []),
    ]);
    sessions = s;
    providers = p;
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
      <div class="flex gap-1">
        <Button size="sm" variant="ghost" href="/dashboard/chat">Nouvelle</Button>
        <Button size="sm" variant="ghost" href="/dashboard/agents">Clés</Button>
      </div>
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
    {#if defaut}
      <p class="text-sm text-ink-secondary mb-4">
        Répondra avec <span class="font-mono">{defaut.model}</span> ({defaut.display_name}), votre
        clé, votre facture.
        <a href="/dashboard/agents" class="text-accent hover:underline">Changer</a>
      </p>
    {:else}
      <!-- Sans clé, le chat reste utilisable : le serveur bascule sur le mode
           gratuit ou le mode découverte. Masquer le chat ici enfermait le
           nouvel arrivant, puisque le bouton d'activation du mode gratuit vit
           dans le chat lui-même. -->
      <p class="text-sm text-ink-secondary mb-4">
        Aucune clé par défaut. Activez le mode gratuit ci-dessous pour essayer sans clé, ou
        <a href="/dashboard/agents" class="text-accent hover:underline">enregistrez la vôtre</a>
        pour choisir votre modèle et lever les quotas.
      </p>
    {/if}
    <div class="mb-3">
      <input
        bind:value={titreNouveau}
        class="w-full rounded border border-subtle bg-surface-primary px-3 py-2 text-sm"
        maxlength="200"
        placeholder="Nommer la conversation (optionnel)"
      />
    </div>
    <ChatPanel
      titreInitial={titreNouveau}
      onsession={(id) => {
        // On met à jour l'URL sans naviguer : goto() démonte ChatPanel et
        // coupe le flux SSE en cours, ce qui fait "tomber dans le vide" le
        // premier message d'une nouvelle conversation. history.replaceState()
        // change l'URL sans toucher au composant.
        history.replaceState(history.state, '', `/dashboard/chat/${id}`);
      }}
    />
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
