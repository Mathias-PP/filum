<script lang="ts">
  import { onMount } from 'svelte';
  import { agentApi } from '$lib/api/agent';
  import type {
    AgentProvider,
    AgentProviderMeta,
    AgentProviderModels,
    AgentProviderTestResult,
    ProviderKind,
  } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, EmptyState, Skeleton, toast } from '$lib/components';

  const kinds: Array<{ value: ProviderKind; label: string }> = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'gemini', label: 'Google Gemini' },
    { value: 'mistral', label: 'Mistral (France)' },
    { value: 'groq', label: 'Groq' },
    { value: 'openrouter', label: 'OpenRouter' },
    { value: 'cerebras', label: 'Cerebras' },
    { value: 'deepseek', label: 'DeepSeek' },
    { value: 'custom', label: 'Autre (URL à saisir)' },
  ];

  const MODELES_SUGGERES: Record<string, string[]> = {
    openai: ['gpt-5.6-luna', 'gpt-5.6-terra'],
    anthropic: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
    deepseek: ['deepseek-chat', 'deepseek-reasoner'],
    gemini: ['gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.1-pro'],
    groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'],
    openrouter: [],
    mistral: ['mistral-large-latest', 'mistral-small-latest', 'codestral-latest'],
    cerebras: ['llama-3.3-70b', 'llama-4-scout-17b-16e-instruct'],
    custom: [],
  };

  let loading = $state(true);
  let loadFailed = $state(false);
  let providers = $state<AgentProvider[]>([]);
  let meta = $state<AgentProviderMeta | null>(null);

  let formOpen = $state(false);
  let saving = $state(false);
  let kind = $state<ProviderKind>('openai');
  let model = $state('');
  let apiKey = $state('');
  let baseUrl = $state('');
  let displayName = $state('');
  let isDefault = $state(false);
  let formError = $state<string | null>(null);
  let editing = $state<string | null>(null);
  let modelesConnus = $state<string[]>([]);
  let modeleLibre = $state(false);
  const modelesProposes = $derived(
    modelesConnus.length > 0 ? modelesConnus : (MODELES_SUGGERES[kind] ?? [])
  );
  const modelesRecommandes = $derived<string[]>((meta?.recommended_models ?? {})[kind] ?? []);

  let testing = $state<string | null>(null);
  let results = $state<Record<string, AgentProviderTestResult>>({});

  let confirmOpen = $state(false);
  let confirmTarget = $state<AgentProvider | null>(null);

  const aucunDefaut = $derived(providers.length > 0 && !providers.some((p) => p.is_default));

  onMount(async () => {
    try {
      [providers, meta] = await Promise.all([agentApi.providers.list(), agentApi.providers.meta()]);
    } catch {
      loadFailed = true;
    } finally {
      loading = false;
    }
  });

  function resetForm() {
    editing = null;
    modelesConnus = [];
    modeleLibre = false;
    kind = 'openai';
    model = '';
    apiKey = '';
    baseUrl = '';
    displayName = '';
    isDefault = providers.length === 0;
    formError = null;
  }

  function openForm() {
    resetForm();
    formOpen = true;
  }

  function ouvrirEdition(provider: AgentProvider) {
    resetForm();
    editing = provider.id;
    kind = provider.provider;
    model = provider.model;
    baseUrl = provider.base_url;
    displayName = provider.display_name;
    isDefault = provider.is_default;
    apiKey = '';
    formOpen = true;
  }

  async function chargerModeles() {
    if (!editing) return;
    try {
      const res = await agentApi.providers.models(editing);
      modelesConnus = res.models.map((m) => (typeof m === 'string' ? m : m.id));
      if (res.source === 'repli' && res.message) toast.info(res.message);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Impossible de lister les modeles.');
    }
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    formError = null;
    saving = true;
    try {
      if (editing) {
        const modifie = await agentApi.providers.update(editing, {
          model: model.trim(),
          base_url: baseUrl.trim() || null,
          display_name: displayName.trim() || null,
          is_default: isDefault,
          ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        });
        apiKey = '';
        providers = await agentApi.providers.list();
        formOpen = false;
        toast.success(`${modifie.display_name} mis a jour.`);
      } else {
        const cree = await agentApi.providers.create({
          provider: kind,
          model: model.trim(),
          api_key: apiKey.trim(),
          base_url: baseUrl.trim() || null,
          display_name: displayName.trim() || null,
          is_default: isDefault,
        });
        apiKey = '';
        providers = await agentApi.providers.list();
        formOpen = false;
        toast.success(`${cree.display_name} enregistre.`);
      }
    } catch (e) {
      formError =
        e instanceof ApiError ? e.message : "Impossible d'enregistrer ce provider. Reessayez.";
    } finally {
      saving = false;
    }
  }

  async function definirDefaut(provider: AgentProvider) {
    try {
      await agentApi.providers.update(provider.id, { is_default: true });
      providers = await agentApi.providers.list();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Changement de défaut impossible.');
    }
  }

  async function tester(provider: AgentProvider) {
    testing = provider.id;
    try {
      results = { ...results, [provider.id]: await agentApi.providers.test(provider.id) };
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Le test de clé a échoué.');
    } finally {
      testing = null;
    }
  }

  function demanderSuppression(provider: AgentProvider) {
    confirmTarget = provider;
    confirmOpen = true;
  }

  async function supprimer() {
    if (!confirmTarget) return;
    const cible = confirmTarget;
    confirmOpen = false;
    confirmTarget = null;
    try {
      await agentApi.providers.remove(cible.id);
      providers = await agentApi.providers.list();
      toast.success(`${cible.display_name} supprimé.`);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Suppression impossible.');
    }
  }
</script>

<svelte:head>
  <title>Clés IA · Philum</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <a
    href="/dashboard/chat"
    class="mb-4 inline-block text-sm text-ink-secondary hover:text-ink-primary"
  >
    &larr; Retour à l'agent
  </a>

  <div class="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-6">
    <div>
      <h1 class="font-serif text-3xl text-ink-primary mb-1">Clés IA</h1>
      <p class="text-sm text-ink-secondary">
        Votre clé, votre modèle, votre facture. Philum ne fournit aucun accès IA et ne relit jamais
        vos clés : elles sont chiffrées et n'apparaissent plus jamais en clair.
      </p>
    </div>
    <Button onclick={openForm}>Ajouter une clé</Button>
  </div>

  {#if meta}
    <p
      class="rounded-lg border border-subtle bg-surface-secondary px-4 py-3 text-sm text-ink-secondary mb-6"
    >
      {meta.data_scope}
    </p>
  {/if}

  {#if !loading && providers.length === 0}
    <div class="rounded-lg border border-subtle bg-surface-secondary px-4 py-4 mb-6 text-sm">
      <p class="text-ink-primary font-medium mb-1">Vous n'avez pas encore de clé ?</p>
      <p class="text-ink-secondary">
        Philum n'héberge aucun modèle : vous branchez le vôtre, vous gardez la main sur vos données
        et sur la facture. Plusieurs fournisseurs délivrent une clé sans carte bancaire.
      </p>
      <ul class="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-ink-secondary">
        <li>
          <a
            class="text-accent hover:underline"
            href="https://console.mistral.ai"
            target="_blank"
            rel="noopener">Mistral (France)</a
          >
        </li>
        <li>
          <a
            class="text-accent hover:underline"
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noopener">Google AI Studio</a
          >
        </li>
        <li>
          <a
            class="text-accent hover:underline"
            href="https://console.groq.com/keys"
            target="_blank"
            rel="noopener">Groq</a
          >
        </li>
        <li>
          <a
            class="text-accent hover:underline"
            href="https://openrouter.ai/keys"
            target="_blank"
            rel="noopener">OpenRouter</a
          >
        </li>
        <li>
          <a
            class="text-accent hover:underline"
            href="https://cloud.cerebras.ai"
            target="_blank"
            rel="noopener">Cerebras</a
          >
        </li>
      </ul>
    </div>
  {/if}

  {#if formOpen}
    <form
      class="rounded-lg border border-subtle bg-surface-secondary p-4 mb-6 space-y-3"
      onsubmit={submit}
    >
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="block text-sm">
          <span class="text-ink-secondary">Fournisseur</span>
          <select
            bind:value={kind}
            disabled={editing !== null}
            class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2 disabled:opacity-50"
          >
            {#each kinds as k (k.value)}
              <option value={k.value}>{k.label}</option>
            {/each}
          </select>
        </label>
        <div class="block text-sm">
          <span class="text-ink-secondary">Modèle</span>
          {#if modeleLibre || modelesProposes.length === 0}
            <input
              bind:value={model}
              required
              placeholder="nom exact du modèle"
              class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2 font-mono"
            />
          {:else}
            <select
              bind:value={model}
              required
              class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2 font-mono"
            >
              <option value="" disabled>Choisir un modèle</option>
              {#each modelesProposes as m (m)}
                <option value={m}>{modelesRecommandes.includes(m) ? '★ ' : ''}{m}</option>
              {/each}
            </select>
          {/if}
          <div class="mt-1 flex flex-wrap gap-3 text-xs">
            <button
              type="button"
              class="text-accent hover:underline"
              onclick={() => (modeleLibre = !modeleLibre)}
            >
              {modeleLibre ? 'Choisir dans la liste' : 'Saisir un autre nom'}
            </button>
            {#if editing}
              <button type="button" class="text-accent hover:underline" onclick={chargerModeles}>
                Lister les modèles de mon compte
              </button>
            {/if}
          </div>
        </div>
      </div>

      <label class="block text-sm">
        <span class="text-ink-secondary">Clé d'API</span>
        <input
          bind:value={apiKey}
          required={editing === null}
          type="password"
          autocomplete="off"
          placeholder={kind === 'custom' ? 'ollama (ou toute valeur non vide)' : 'sk-…'}
          class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2 font-mono"
        />
        {#if editing}
          <span class="mt-1 block text-xs text-ink-tertiary">
            Laisser vide pour conserver la clé actuelle.
          </span>
        {/if}
      </label>

      {#if kind === 'custom' || editing}
        <label class="block text-sm">
          <span class="text-ink-secondary">URL de l'API</span>
          <input
            bind:value={baseUrl}
            required={kind === 'custom' && !editing}
            placeholder="https://mon-serveur.example/v1"
            class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2"
          />
        </label>
      {/if}

      <label class="block text-sm">
        <span class="text-ink-secondary">Nom affiché (optionnel)</span>
        <input
          bind:value={displayName}
          class="mt-1 w-full rounded border border-subtle bg-surface-primary px-3 py-2"
        />
      </label>

      <label class="flex items-center gap-2 text-sm text-ink-secondary">
        <input type="checkbox" bind:checked={isDefault} />
        Utiliser par défaut dans le chat
      </label>

      {#if formError}
        <p class="text-sm text-danger">{formError}</p>
      {/if}

      <div class="flex gap-2">
        <Button type="submit" loading={saving}>Enregistrer</Button>
        <Button variant="ghost" onclick={() => (formOpen = false)}>Annuler</Button>
      </div>
    </form>
  {/if}

  {#if loading}
    <div class="space-y-3">
      <Skeleton variant="card" height="4rem" />
      <Skeleton variant="card" height="4rem" />
    </div>
  {:else if loadFailed}
    <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-4 text-sm text-danger">
      Impossible de charger vos providers. Rechargez la page.
    </div>
  {:else if providers.length === 0}
    <EmptyState
      title="Aucune clé enregistrée"
      description="Le chat de l'agent a besoin d'une clé d'API pour parler à un modèle."
    />
  {:else}
    {#if aucunDefaut}
      <p class="mb-3 text-sm text-ink-secondary">
        Aucun provider n'est marqué par défaut : le chat ne saura pas lequel utiliser.
      </p>
    {/if}
    <ul class="space-y-3">
      {#each providers as provider (provider.id)}
        <li class="rounded-lg border border-subtle bg-surface-secondary px-4 py-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="min-w-0">
              <p class="font-medium text-ink-primary">
                {provider.display_name}
                {#if provider.is_default}
                  <span class="badge-soft ml-2">Par défaut</span>
                {/if}
              </p>
              <p class="text-xs text-ink-tertiary mt-0.5 font-mono break-all">
                {provider.model} · {provider.api_key_masked}
              </p>
              <p class="text-xs text-ink-tertiary font-mono break-all">{provider.base_url}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              {#if !provider.is_default}
                <Button size="sm" variant="ghost" onclick={() => definirDefaut(provider)}>
                  Par défaut
                </Button>
              {/if}
              <Button size="sm" variant="ghost" onclick={() => ouvrirEdition(provider)}>
                Modifier
              </Button>
              <Button
                size="sm"
                variant="secondary"
                loading={testing === provider.id}
                onclick={() => tester(provider)}
              >
                Tester la clé
              </Button>
              <Button size="sm" variant="ghost" onclick={() => demanderSuppression(provider)}>
                Supprimer
              </Button>
            </div>
          </div>
          {#if results[provider.id]}
            <div class="mt-2 text-sm">
              <p
                class:text-success={results[provider.id].ok}
                class:text-danger={!results[provider.id].ok}
              >
                {results[provider.id].message}
              </p>
              {#if results[provider.id].ok && results[provider.id].latency_ms != null}
                <p class="mt-1 text-xs text-ink-tertiary">
                  Latence : {results[provider.id].latency_ms} ms
                </p>
              {/if}
              {#if !results[provider.id].ok}
                <p class="mt-1 font-mono text-xs text-ink-tertiary break-all">
                  HTTP {results[provider.id].http_status ?? '?'} · {results[provider.id].url}
                </p>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<ConfirmDialog
  bind:open={confirmOpen}
  title="Supprimer ce provider ?"
  message={confirmTarget
    ? `La clé de ${confirmTarget.display_name} sera effacée. Les conversations déjà tenues restent lisibles.`
    : ''}
  confirmLabel="Supprimer"
  variant="danger"
  onConfirm={supprimer}
  onCancel={() => {
    confirmTarget = null;
  }}
/>
