<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { agentApi, type AgentProvider, type AgentSessionUsage } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { appliquer, depuisMessages, type ChatItem } from '$lib/agent/conversation';
  import Button from '../Button.svelte';
  import { toast } from '../Toast.svelte';
  import ApprovalCard from './ApprovalCard.svelte';
  import ToolCard from './ToolCard.svelte';
  import AgentMarkdown from './AgentMarkdown.svelte';

  interface Props {
    sessionId?: string | null;
    onsession?: (id: string) => void;
    /** Titre propose avant le premier message (choisi par l'utilisateur). */
    titreInitial?: string;
  }

  let { sessionId = $bindable(null), onsession, titreInitial = '' }: Props = $props();

  let items = $state<ChatItem[]>([]);
  let saisie = $state('');
  let enCours = $state(false);
  let chargement = $state(Boolean(sessionId));
  let controleur: AbortController | null = null;
  let usage = $state<AgentSessionUsage | null>(null);
  let decouverte = $state<{
    provider_public_name: string;
    remaining_today: number | null;
    retention_notice: string;
  } | null>(null);

  // Selectors provider + modele
  let cles = $state<AgentProvider[]>([]);
  let cleChoisie = $state('');
  let modeles = $state<string[]>([]);
  let modeleChoisi = $state('');

  // Autoscroll
  let fil = $state<HTMLDivElement | null>(null);
  let auBas = $state(true);

  // Derive un "fingerprint" du dernier contenu assistant pour declencher l'autoscroll
  // meme pendant le streaming token par token.
  const derniereAssistantLongueur = $derived(
    items.filter((i) => i.kind === 'assistant').at(-1)?.text.length ?? 0
  );
  const empreinte = $derived(`${items.length}-${derniereAssistantLongueur}`);

  $effect(() => {
    void empreinte; // lire la derivee pour que l'effet se rejoue
    if (auBas && fil) {
      tick().then(() => {
        if (fil) fil.scrollTop = fil.scrollHeight;
      });
    }
  });

  function surDefilement() {
    if (!fil) return;
    auBas = fil.scrollHeight - fil.scrollTop - fil.clientHeight < 80;
  }

  function ajusterHauteur(el: HTMLTextAreaElement) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 200) + 'px';
  }

  async function chargerModeles() {
    if (!cleChoisie) {
      modeles = [];
      return;
    }
    try {
      const res = await agentApi.providers.models(cleChoisie);
      modeles = res.models
        .map((m) => (typeof m === 'string' ? m : m.id))
        .filter(Boolean) as string[];
    } catch {
      modeles = [];
    }
  }

  async function changerCle() {
    modeleChoisi = '';
    await chargerModeles();
    if (sessionId && cleChoisie) {
      await agentApi.sessions.update(sessionId, { provider_id: cleChoisie }).catch(() => null);
    }
  }

  async function changerModele() {
    if (!sessionId || !modeleChoisi) return;
    // Ecrit l'override par session, ne mute jamais le provider global.
    await agentApi.sessions.update(sessionId, { model_override: modeleChoisi }).catch(() => null);
  }

  onMount(async () => {
    const taches: Promise<unknown>[] = [agentApi.providers.list().catch(() => [])];
    if (sessionId) taches.push(agentApi.sessions.messages(sessionId).catch(() => []));

    const [clesRes, messagesRes] = await Promise.allSettled(taches);
    if (clesRes.status === 'fulfilled') {
      cles = clesRes.value as AgentProvider[];
      const defaut = cles.find((p) => p.is_default);
      if (defaut) cleChoisie = defaut.id;
    }
    if (sessionId && messagesRes && messagesRes.status === 'fulfilled') {
      items = depuisMessages(
        messagesRes.value as Awaited<ReturnType<typeof agentApi.sessions.messages>>
      );
      chargement = false;
    } else if (sessionId) {
      chargement = false;
    }
    if (cleChoisie) await chargerModeles();
  });

  async function envoyer(event: SubmitEvent) {
    event.preventDefault();
    if (event.target instanceof HTMLFormElement) {
      const textarea = event.target.querySelector('textarea');
      if (textarea) textarea.style.height = 'auto';
    }
    const message = saisie.trim();
    if (!message || enCours) return;
    saisie = '';
    auBas = true;
    items = [...items, { kind: 'user', text: message }];
    enCours = true;
    controleur = new AbortController();
    try {
      for await (const evenement of agentApi.streamChat({
        message,
        session_id: sessionId ?? undefined,
        provider_id: cleChoisie || undefined,
        model_override: modeleChoisi || undefined,
        signal: controleur.signal,
      })) {
        if (evenement.type === 'session' && !sessionId) {
          sessionId = evenement.payload.id;
          if (titreInitial && sessionId) {
            await agentApi.sessions.update(sessionId, { title: titreInitial }).catch(() => null);
          }
          onsession?.(sessionId);
        }
        if (evenement.type === 'discovery_active') {
          decouverte = evenement.payload;
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
      toast.danger(e instanceof ApiError ? e.message : "Cette demande n'attend plus de reponse.");
    }
  }
</script>

<div class="flex h-[calc(100dvh-12rem)] flex-col">
  <!-- Selectors provider + modele -->
  {#if cles.length > 0}
    <div class="mb-2 flex flex-wrap gap-3 border-b border-subtle pb-2 text-sm">
      <label class="flex items-center gap-1.5">
        <span class="text-xs text-ink-tertiary">Cle</span>
        <select
          bind:value={cleChoisie}
          onchange={changerCle}
          disabled={enCours}
          class="rounded border border-subtle bg-surface-primary px-2 py-1 text-xs"
        >
          {#each cles as cle (cle.id)}
            <option value={cle.id}>{cle.display_name} ({cle.api_key_masked})</option>
          {/each}
        </select>
      </label>
      {#if modeles.length > 0}
        <label class="flex items-center gap-1.5">
          <span class="text-xs text-ink-tertiary">Modele</span>
          <select
            bind:value={modeleChoisi}
            onchange={changerModele}
            disabled={enCours}
            class="rounded border border-subtle bg-surface-primary px-2 py-1 text-xs"
          >
            <option value="">Defaut ({cles.find((c) => c.id === cleChoisie)?.model ?? ''})</option>
            {#each modeles as m (m)}
              <option value={m}>{m}</option>
            {/each}
          </select>
        </label>
      {/if}
    </div>
  {/if}

  <!-- Fil de conversation -->
  <div bind:this={fil} class="flex-1 space-y-3 overflow-y-auto px-1 py-2" onscroll={surDefilement}>
    {#if chargement}
      <p class="text-sm text-ink-tertiary">Chargement de la conversation...</p>
    {:else if items.length === 0}
      <p class="text-sm text-ink-tertiary">
        Demandez une fiche, une source a verifier, un extrait a relire.
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
        <p class="rounded-lg border border-danger/30 bg-danger-bg px-3 py-2 text-sm text-danger">
          {item.text}
        </p>
      {/if}
    {/each}
  </div>

  <!-- Bouton "nouveaux messages" quand l'utilisateur a remonte -->
  {#if !auBas && enCours}
    <button
      type="button"
      class="mx-auto mb-1 rounded-full border border-subtle bg-surface-secondary px-3 py-1 text-xs text-ink-secondary shadow-sm hover:bg-surface-tertiary"
      onclick={() => {
        auBas = true;
        if (fil) fil.scrollTop = fil.scrollHeight;
      }}
    >
      Nouveaux messages
    </button>
  {/if}

  {#if usage && (usage.total_prompt_tokens > 0 || usage.total_completion_tokens > 0)}
    <p class="py-1 text-right text-xs text-ink-tertiary">
      {(usage.total_prompt_tokens / 1000).toFixed(1)}k prompt · {(
        usage.total_completion_tokens / 1000
      ).toFixed(1)}k completion{usage.cost_eur != null
        ? ` · ~${usage.cost_eur.toFixed(2)} EUR`
        : ''}
    </p>
  {/if}

  {#if decouverte}
    <div
      class="mt-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
    >
      <span class="font-medium">Mode decouverte</span> -- vos echanges transitent par
      <span class="font-medium">{decouverte.provider_public_name}</span>.
      {decouverte.retention_notice}
      {#if decouverte.remaining_today !== null}
        <span class="ml-1 font-medium"
          >{decouverte.remaining_today} message{decouverte.remaining_today !== 1 ? 's' : ''} restant{decouverte.remaining_today !==
          1
            ? 's'
            : ''} aujourd'hui.</span
        >
      {/if}
      <a href="/dashboard/agents" class="ml-1 underline">Connecter votre cle</a>
    </div>
  {/if}

  <form class="flex gap-2 border-t border-subtle pt-3" onsubmit={envoyer}>
    <textarea
      bind:value={saisie}
      rows="1"
      placeholder="Que doit faire l'agent ?"
      class="flex-1 resize-none rounded border border-subtle bg-surface-primary px-3 py-2 text-sm"
      style="overflow-y: hidden;"
      oninput={(e) => ajusterHauteur(e.currentTarget)}
      onkeydown={(e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          if (!enCours && saisie.trim()) {
            e.currentTarget.form?.requestSubmit();
          }
        }
      }}></textarea>
    {#if enCours}
      <Button variant="ghost" onclick={interrompre}>Arreter</Button>
    {:else}
      <Button type="submit">Envoyer</Button>
    {/if}
  </form>
</div>
