<script lang="ts">
  import { onMount } from 'svelte';
  import { agentApi, type AgentSessionUsage } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { appliquer, depuisMessages, type ChatItem } from '$lib/agent/conversation';
  import Button from '../Button.svelte';
  import { toast } from '../Toast.svelte';
  import ApprovalCard from './ApprovalCard.svelte';
  import ToolCard from './ToolCard.svelte';
  import AgentMarkdown from './AgentMarkdown.svelte';

  interface Props {
    /** Session existante à reprendre. Absente : la première réponse en crée une. */
    sessionId?: string | null;
    /** Appelé quand le serveur annonce l'identifiant de la session créée. */
    onsession?: (id: string) => void;
  }

  let { sessionId = null, onsession }: Props = $props();

  let items = $state<ChatItem[]>([]);
  let saisie = $state('');
  let enCours = $state(false);
  let chargement = $state(Boolean(sessionId));
  let controleur: AbortController | null = null;
  let usage = $state<AgentSessionUsage | null>(null);

  onMount(async () => {
    if (!sessionId) return;
    try {
      items = depuisMessages(await agentApi.sessions.messages(sessionId));
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Conversation illisible.');
    } finally {
      chargement = false;
    }
  });

  async function envoyer(event: SubmitEvent) {
    event.preventDefault();
    const message = saisie.trim();
    if (!message || enCours) return;
    saisie = '';
    items = [...items, { kind: 'user', text: message }];
    enCours = true;
    controleur = new AbortController();
    try {
      for await (const evenement of agentApi.streamChat({
        message,
        session_id: sessionId ?? undefined,
        signal: controleur.signal,
      })) {
        if (evenement.type === 'session' && !sessionId) {
          sessionId = evenement.payload.id;
          onsession?.(sessionId);
        }
        items = appliquer(items, evenement);
      }
    } catch (e) {
      if ((e as Error)?.name !== 'AbortError') {
        items = [
          ...items,
          {
            kind: 'error',
            text: e instanceof ApiError ? e.message : "L'agent s'est interrompu.",
          },
        ];
      }
    } finally {
      enCours = false;
      controleur = null;
      if (sessionId) {
        agentApi.sessions
          .usage(sessionId)
          .then((u) => (usage = u))
          .catch(() => null);
      }
    }
  }

  function interrompre() {
    controleur?.abort();
  }

  async function repondreApprobation(requestId: string, approuve: boolean) {
    try {
      await agentApi.approve(requestId, approuve);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : "Cette demande n'attend plus de réponse.");
    }
  }
</script>

<div class="flex h-full flex-col">
  <div class="flex-1 space-y-3 overflow-y-auto px-1 py-2">
    {#if chargement}
      <p class="text-sm text-ink-tertiary">Chargement de la conversation…</p>
    {:else if items.length === 0}
      <p class="text-sm text-ink-tertiary">
        Demandez une fiche, une source à vérifier, un extrait à relire. Toute écriture vous sera
        soumise avant d'être exécutée.
      </p>
    {/if}

    {#each items as item, i (i)}
      {#if item.kind === 'user'}
        <div
          class="ml-auto max-w-[85%] rounded-lg bg-surface-tertiary px-3 py-2 text-sm text-ink-primary"
        >
          {item.text}
        </div>
      {:else if item.kind === 'assistant'}
        <div class="max-w-[85%]">
          <AgentMarkdown texte={item.text} />
        </div>
      {:else if item.kind === 'tool'}
        <ToolCard name={item.name} args={item.args} result={item.result} />
      {:else if item.kind === 'approval'}
        <ApprovalCard
          tool={item.tool}
          args={item.args}
          approved={item.approved}
          onrespond={(approuve) => repondreApprobation(item.requestId, approuve)}
        />
      {:else}
        <p class="rounded-lg bg-danger-bg border border-danger/30 px-3 py-2 text-sm text-danger">
          {item.text}
        </p>
      {/if}
    {/each}
  </div>

  {#if usage && (usage.total_prompt_tokens > 0 || usage.total_completion_tokens > 0)}
    <p class="py-1 text-right text-xs text-ink-tertiary">
      {(usage.total_prompt_tokens / 1000).toFixed(1)}k prompt · {(
        usage.total_completion_tokens / 1000
      ).toFixed(1)}k completion{usage.cost_eur != null ? ` · ~${usage.cost_eur.toFixed(2)} €` : ''}
    </p>
  {/if}

  <form class="flex gap-2 border-t border-subtle pt-3" onsubmit={envoyer}>
    <input
      bind:value={saisie}
      disabled={enCours}
      placeholder="Que doit faire l'agent ?"
      class="flex-1 rounded border border-subtle bg-surface-primary px-3 py-2 text-sm"
    />
    {#if enCours}
      <Button variant="ghost" onclick={interrompre}>Arrêter</Button>
    {:else}
      <Button type="submit">Envoyer</Button>
    {/if}
  </form>
</div>
