<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { Button, ConfirmDialog, ProgressSteps } from '$lib/components';
  import { AUTHOR_COLORS, authorLabel } from '$lib/utils/author-colors';
  import type { AuthorKind, Card, Source, SourceCategory, SourceFormat } from '$lib/api';

  const wizardSteps = [
    { label: 'Informations', description: 'Titre, plateforme' },
    { label: 'Sources', description: 'Ajouter et publier' },
  ];

  const cardId = $derived($page.params.card_id ?? '');

  let card = $state<Card | null>(null);
  let sources = $state<Source[]>([]);
  let loadError = $state<string | null>(null);
  let publishing = $state(false);
  let publishError = $state<string | null>(null);

  // Add-source / edit-source form (shared state)
  let url = $state('');
  let sourceFormat = $state<SourceFormat>('texte');
  let sourceCategory = $state<SourceCategory>('article-scientifique');
  let authorKind = $state<AuthorKind>('chercheur');
  let parentSourceId = $state<string>('');
  let sourceTitle = $state('');
  let authors = $state('');
  let annotation = $state('');
  let isPivot = $state(false);
  // Optional manual archive URL (e.g. a Wayback snapshot the user already has).
  // When empty, the backend auto-archives via Wayback Save Page Now.
  let archiveUrl = $state('');
  let addError = $state<string | null>(null);
  let addLoading = $state(false);
  let editingSourceId = $state<string | null>(null);
  const isEditing = $derived(editingSourceId !== null);

  // URL extraction
  let extracting = $state(false);
  let lastExtractedUrl = $state('');
  // Taxonomie suggérée par l'extracteur (Crossref ou LLM) — indicateur UI
  let taxonomySuggested = $state(false);

  // Relative — routed through the SvelteKit /api proxy for first-party cookies.
  const EXTRACT_API = '/api/v1/sources/extract';

  async function extractUrl() {
    if (!url || url === lastExtractedUrl) return;
    extracting = true;
    lastExtractedUrl = url;
    try {
      const response = await fetch(`${EXTRACT_API}?url=${encodeURIComponent(url)}`);
      if (response.ok) {
        const data = await response.json();
        if (data.title) sourceTitle = data.title;
        if (data.authors) authors = data.authors;
        // Taxonomie suggérée (validée contre les enums connus côté client)
        let suggested = false;
        if (data.format && formatOptions.some((o) => o.value === data.format)) {
          sourceFormat = data.format;
          suggested = true;
        }
        if (data.category && categoryOptions.some((o) => o.value === data.category)) {
          sourceCategory = data.category;
          suggested = true;
        }
        if (data.author_kind && authorKindOptions.includes(data.author_kind)) {
          authorKind = data.author_kind;
          suggested = true;
        }
        taxonomySuggested = suggested;
      }
    } catch {
      // silent fail — user can fill manually
    } finally {
      extracting = false;
    }
  }

  function onUrlChange(value: string) {
    url = value;
    if (value !== lastExtractedUrl) {
      sourceTitle = '';
      authors = '';
      taxonomySuggested = false;
    }
  }

  onMount(async () => {
    try {
      const [loadedCard, loadedSources] = await Promise.all([
        api.cards.get(cardId),
        api.sources.list(cardId),
      ]);
      card = loadedCard;
      sources = loadedSources;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Erreur de chargement';
    }
  });

  function resetForm() {
    url = '';
    sourceFormat = 'texte';
    sourceCategory = 'article-scientifique';
    authorKind = 'chercheur';
    sourceTitle = '';
    authors = '';
    annotation = '';
    isPivot = false;
    parentSourceId = '';
    archiveUrl = '';
    lastExtractedUrl = '';
    taxonomySuggested = false;
    editingSourceId = null;
    addError = null;
  }

  function startEdit(source: Source) {
    editingSourceId = source.id;
    url = source.url;
    sourceFormat = source.format;
    sourceCategory = source.category;
    authorKind = source.author_kind;
    sourceTitle = source.title ?? '';
    authors = source.authors ?? '';
    annotation = source.annotation ?? '';
    isPivot = source.is_pivot;
    parentSourceId = source.parent_source_id ?? '';
    archiveUrl = source.archive_url ?? '';
    lastExtractedUrl = source.url;
    taxonomySuggested = false;
    addError = null;
    if (typeof document !== 'undefined') {
      document
        .getElementById('source-title')
        ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function cancelEdit() {
    resetForm();
  }

  async function submitSource(e: Event) {
    e.preventDefault();
    addError = null;
    addLoading = true;
    try {
      if (editingSourceId) {
        const updated = await api.sources.update(editingSourceId, {
          format: sourceFormat,
          category: sourceCategory,
          author_kind: authorKind,
          title: sourceTitle || undefined,
          authors: authors || undefined,
          annotation: annotation || undefined,
          is_pivot: isPivot,
          parent_source_id: parentSourceId || null,
          archive_url: archiveUrl.trim() || null,
        });
        sources = sources.map((s) => (s.id === updated.id ? updated : s));
        resetForm();
      } else {
        const s = await api.sources.create(cardId, {
          url,
          format: sourceFormat,
          category: sourceCategory,
          author_kind: authorKind,
          title: sourceTitle || undefined,
          authors: authors || undefined,
          annotation: annotation || undefined,
          is_pivot: isPivot,
          parent_source_id: parentSourceId || undefined,
          archive_url: archiveUrl.trim() || null,
        });
        sources = [...sources, s];
        resetForm();
      }
    } catch (err) {
      addError =
        err instanceof Error
          ? err.message
          : editingSourceId
            ? 'Erreur lors de la modification'
            : "Erreur lors de l'ajout";
    } finally {
      addLoading = false;
    }
  }

  let confirmDeleteId = $state<string | null>(null);

  async function removeSource(id: string) {
    try {
      await api.sources.delete(id);
      sources = sources.filter((s) => s.id !== id);
      if (editingSourceId === id) resetForm();
    } catch (err) {
      addError = err instanceof Error ? err.message : 'Erreur lors de la suppression';
    } finally {
      confirmDeleteId = null;
    }
  }

  async function publish() {
    publishError = null;
    publishing = true;
    try {
      const res = await api.cards.publish(cardId);
      // Land on the freshly published public page rather than back on the
      // dashboard — the user gets to see (and share) the result immediately.
      let publicPath = '/dashboard';
      try {
        publicPath = new URL(res.public_url).pathname;
      } catch {
        // keep dashboard fallback
      }
      goto(publicPath);
    } catch (err) {
      console.error('publish error:', err);
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        publishError =
          'La publication n’a pas abouti : le serveur n’a pas répondu. Vérifiez votre connexion puis réessayez — votre brouillon et vos sources sont conservés.';
      } else {
        publishError = err instanceof Error ? err.message : 'Erreur lors de la publication';
      }
    } finally {
      publishing = false;
    }
  }

  const formatOptions: { value: SourceFormat; label: string }[] = [
    { value: 'texte', label: 'Texte' },
    { value: 'video', label: 'Vidéo' },
    { value: 'image', label: 'Image' },
    { value: 'audio', label: 'Audio' },
    { value: 'data', label: 'Données' },
  ];

  const categoryOptions: { value: SourceCategory; label: string }[] = [
    { value: 'article-scientifique', label: 'Article scientifique' },
    { value: 'preprint', label: 'Préprint' },
    { value: 'article-presse', label: 'Article de presse' },
    { value: 'communique', label: 'Communiqué' },
    { value: 'documentaire', label: 'Documentaire' },
    { value: 'interview', label: 'Interview' },
    { value: 'podcast', label: 'Podcast' },
    { value: 'blog', label: 'Blog' },
    { value: 'post-social', label: 'Post réseaux sociaux' },
    { value: 'livre', label: 'Livre' },
    { value: 'page-web', label: 'Page web' },
    { value: 'notes', label: 'Notes' },
  ];

  const authorKindOptions: AuthorKind[] = [
    'chercheur',
    'media',
    'institution-publique',
    'gouvernement',
    'ecole',
    'laboratoire',
    'entreprise',
    'asso',
    'individu',
  ];

  // ── Mode multi-liens ──────────────────────────────────────────────────
  type DraftStatus = 'extracting' | 'ready' | 'adding' | 'error';
  type DraftSource = {
    url: string;
    title: string;
    authors: string;
    format: SourceFormat;
    category: SourceCategory;
    author_kind: AuthorKind;
    status: DraftStatus;
    error: string | null;
  };

  let multiMode = $state(false);
  let multiText = $state('');
  let drafts = $state<DraftSource[]>([]);
  let multiExtracting = $state(false);
  let addingAll = $state(false);

  function parseUrls(text: string): string[] {
    const seen = new Set<string>();
    const urls: string[] = [];
    for (const token of text.split(/\s+/)) {
      if (!token) continue;
      try {
        const u = new URL(token);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') continue;
        if (seen.has(u.href)) continue;
        seen.add(u.href);
        urls.push(u.href);
      } catch {
        // token non-URL : ignoré
      }
    }
    return urls;
  }

  async function extractAll() {
    const known = new Set([...sources.map((s) => s.url), ...drafts.map((d) => d.url)]);
    const urls = parseUrls(multiText).filter((u) => !known.has(u));
    if (urls.length === 0) {
      multiText = '';
      return;
    }
    multiExtracting = true;
    for (const u of urls) {
      drafts.push({
        url: u,
        title: '',
        authors: '',
        format: 'texte',
        category: 'page-web',
        author_kind: 'individu',
        status: 'extracting',
        error: null,
      });
      // Mutations via le proxy $state (pas l'objet brut) pour la réactivité.
      const draft = drafts[drafts.length - 1];
      try {
        const response = await fetch(`${EXTRACT_API}?url=${encodeURIComponent(u)}`);
        if (response.ok) {
          const data = await response.json();
          if (data.title) draft.title = data.title;
          if (data.authors) draft.authors = data.authors;
          if (data.format && formatOptions.some((o) => o.value === data.format)) {
            draft.format = data.format;
          }
          if (data.category && categoryOptions.some((o) => o.value === data.category)) {
            draft.category = data.category;
          }
          if (data.author_kind && authorKindOptions.includes(data.author_kind)) {
            draft.author_kind = data.author_kind;
          }
        }
      } catch {
        // extraction silencieuse : l'utilisateur complète à la main
      }
      draft.status = 'ready';
    }
    multiExtracting = false;
    multiText = '';
  }

  async function addDraft(index: number) {
    const draft = drafts[index];
    if (!draft || draft.status === 'adding' || draft.status === 'extracting') return;
    draft.status = 'adding';
    draft.error = null;
    try {
      const s = await api.sources.create(cardId, {
        url: draft.url,
        format: draft.format,
        category: draft.category,
        author_kind: draft.author_kind,
        title: draft.title || undefined,
        authors: draft.authors || undefined,
      });
      sources = [...sources, s];
      drafts.splice(index, 1);
    } catch (err) {
      draft.status = 'error';
      draft.error = err instanceof Error ? err.message : "Erreur lors de l'ajout";
    }
  }

  async function addAllDrafts() {
    addingAll = true;
    // Itération par URL : les index bougent quand un draft ajouté est retiré.
    const pending = drafts.filter((d) => d.status === 'ready' || d.status === 'error');
    for (const { url: u } of pending) {
      const idx = drafts.findIndex((d) => d.url === u);
      if (idx !== -1) await addDraft(idx);
    }
    addingAll = false;
  }

  function removeDraft(index: number) {
    drafts.splice(index, 1);
  }
</script>

<svelte:head>
  <title>Ajouter des sources - Philum</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
      >← Tableau de bord</a
    >
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-1">
    {card?.title ?? 'Chargement...'}
  </h1>
  <p class="text-sm text-ink-secondary mb-6">Ajoutez vos sources, puis publiez la fiche.</p>

  <ProgressSteps steps={wizardSteps} current={1} class="mb-8" />

  {#if loadError}
    <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger mb-6">
      {loadError}
    </div>
  {/if}

  <!-- Add / edit source form -->
  <div
    class="bg-surface-primary border rounded-xl p-6 mb-6 {isEditing
      ? 'border-info/50 ring-1 ring-info/30'
      : 'border-border'}"
  >
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-ink-primary">
        {isEditing
          ? 'Modifier la source'
          : multiMode
            ? 'Ajouter plusieurs sources'
            : 'Ajouter une source'}
      </h2>
      {#if isEditing}
        <button
          type="button"
          onclick={cancelEdit}
          class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
        >
          Annuler
        </button>
      {:else}
        <div class="flex rounded-lg border border-border-strong overflow-hidden text-sm">
          <button
            type="button"
            onclick={() => (multiMode = false)}
            class="px-3 py-1.5 transition-colors {multiMode
              ? 'bg-surface-primary text-ink-tertiary hover:text-ink-primary'
              : 'bg-info/10 text-info font-medium'}"
          >
            Une source
          </button>
          <button
            type="button"
            onclick={() => (multiMode = true)}
            class="px-3 py-1.5 border-l border-border-strong transition-colors {multiMode
              ? 'bg-info/10 text-info font-medium'
              : 'bg-surface-primary text-ink-tertiary hover:text-ink-primary'}"
          >
            Multi-liens
          </button>
        </div>
      {/if}
    </div>

    {#if multiMode && !isEditing}
      <div class="space-y-4">
        <div class="space-y-1.5">
          <label for="multi-urls" class="block text-sm font-medium text-ink-secondary">
            Liens
            <span class="text-xs text-ink-tertiary font-normal"
              >— un par ligne ou séparés par des espaces</span
            >
          </label>
          <textarea
            id="multi-urls"
            bind:value={multiText}
            rows={4}
            placeholder={'https://doi.org/10.1038/...\nhttps://www.lemonde.fr/...\nhttps://youtube.com/watch?v=...'}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary font-mono text-sm resize-none"
          ></textarea>
        </div>
        <div class="flex justify-end">
          <Button
            type="button"
            variant="secondary"
            loading={multiExtracting}
            disabled={multiExtracting || !multiText.trim()}
            onclick={extractAll}
          >
            {multiExtracting ? 'Analyse…' : 'Analyser les liens'}
          </Button>
        </div>

        {#if drafts.length > 0}
          <div class="space-y-3 border-t border-border pt-4">
            {#each drafts as draft, i (draft.url)}
              <div class="border border-border rounded-lg p-4 space-y-3 bg-surface-secondary/50">
                <div class="flex items-start justify-between gap-2">
                  <p class="text-xs text-ink-tertiary font-mono truncate min-w-0">{draft.url}</p>
                  <div class="flex items-center gap-2 shrink-0">
                    {#if draft.status === 'extracting'}
                      <div
                        class="w-4 h-4 border-2 border-info border-t-transparent rounded-full animate-spin"
                      ></div>
                    {/if}
                    <button
                      type="button"
                      onclick={() => removeDraft(i)}
                      class="p-1 text-ink-tertiary hover:text-danger transition-colors"
                      aria-label="Retirer ce lien"
                      title="Retirer"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        class="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <line x1="6" y1="6" x2="18" y2="18" />
                        <line x1="6" y1="18" x2="18" y2="6" />
                      </svg>
                    </button>
                  </div>
                </div>

                {#if draft.error}
                  <div
                    class="rounded-lg bg-danger-bg border border-danger/30 px-3 py-2 text-xs text-danger"
                  >
                    {draft.error}
                  </div>
                {/if}

                <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <input
                    type="text"
                    bind:value={draft.title}
                    placeholder="Titre"
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-tertiary disabled:opacity-60"
                  />
                  <input
                    type="text"
                    bind:value={draft.authors}
                    placeholder="Auteurs"
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-tertiary disabled:opacity-60"
                  />
                  <select
                    bind:value={draft.format}
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info disabled:opacity-60"
                  >
                    {#each formatOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                  <select
                    bind:value={draft.category}
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info disabled:opacity-60"
                  >
                    {#each categoryOptions as opt}
                      <option value={opt.value}>{opt.label}</option>
                    {/each}
                  </select>
                  <select
                    bind:value={draft.author_kind}
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info disabled:opacity-60"
                    style:border-left="4px solid {AUTHOR_COLORS[draft.author_kind].stroke}"
                  >
                    {#each authorKindOptions as opt}
                      <option value={opt}>{authorLabel(opt)}</option>
                    {/each}
                  </select>
                  <div class="flex justify-end items-end">
                    <Button
                      type="button"
                      variant="secondary"
                      loading={draft.status === 'adding'}
                      disabled={draft.status === 'adding' || draft.status === 'extracting'}
                      onclick={() => addDraft(i)}
                    >
                      {draft.status === 'adding' ? 'Ajout…' : 'Ajouter'}
                    </Button>
                  </div>
                </div>
              </div>
            {/each}

            <div class="flex justify-end pt-1">
              <Button
                type="button"
                loading={addingAll}
                disabled={addingAll || multiExtracting || drafts.length === 0}
                onclick={addAllDrafts}
              >
                {addingAll ? 'Ajout en cours…' : `Tout ajouter (${drafts.length})`}
              </Button>
            </div>
          </div>
        {/if}
      </div>
    {:else}
      <form onsubmit={submitSource} class="space-y-4">
        {#if addError}
          <div
            class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger"
          >
            {addError}
          </div>
        {/if}

        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div class="sm:col-span-2 space-y-1.5">
            <label for="source-url" class="block text-sm font-medium text-ink-secondary">
              URL <span class="text-danger">*</span>
            </label>
            <div class="relative">
              <input
                id="source-url"
                type="url"
                value={url}
                oninput={(e) => onUrlChange((e.target as HTMLInputElement).value)}
                onblur={extractUrl}
                required
                readonly={isEditing}
                placeholder="https://doi.org/..."
                class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary read-only:bg-surface-tertiary read-only:text-ink-tertiary read-only:cursor-not-allowed"
              />
              {#if extracting}
                <div
                  class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-info border-t-transparent rounded-full animate-spin"
                ></div>
              {/if}
            </div>
            {#if isEditing}
              <p class="text-xs text-ink-tertiary">
                L'URL d'une source ne peut pas être modifiée (préserve l'archivage Wayback).
              </p>
            {/if}
          </div>

          <div class="space-y-1.5">
            <label for="source-format" class="block text-sm font-medium text-ink-secondary">
              Format <span class="text-danger">*</span>
              {#if taxonomySuggested}
                <span class="text-xs text-info font-normal">— suggéré</span>
              {/if}
            </label>
            <select
              id="source-format"
              value={sourceFormat}
              onchange={(e) =>
                (sourceFormat = (e.target as HTMLSelectElement).value as SourceFormat)}
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
            >
              {#each formatOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="source-category" class="block text-sm font-medium text-ink-secondary">
              Catégorie <span class="text-danger">*</span>
              {#if taxonomySuggested}
                <span class="text-xs text-info font-normal">— suggéré</span>
              {/if}
            </label>
            <select
              id="source-category"
              value={sourceCategory}
              onchange={(e) =>
                (sourceCategory = (e.target as HTMLSelectElement).value as SourceCategory)}
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
            >
              {#each categoryOptions as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
          </div>

          <div class="sm:col-span-2 space-y-1.5">
            <label for="source-author-kind" class="block text-sm font-medium text-ink-secondary">
              Type d'auteur <span class="text-danger">*</span>
              <span class="text-xs text-ink-tertiary font-normal"
                >— colore le nœud dans le graphe</span
              >
              {#if taxonomySuggested}
                <span class="text-xs text-info font-normal">— suggéré</span>
              {/if}
            </label>
            <select
              id="source-author-kind"
              value={authorKind}
              onchange={(e) => (authorKind = (e.target as HTMLSelectElement).value as AuthorKind)}
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
              style:border-left="4px solid {AUTHOR_COLORS[authorKind].stroke}"
            >
              {#each authorKindOptions as opt}
                <option value={opt}>{authorLabel(opt)}</option>
              {/each}
            </select>
          </div>

          <div class="space-y-1.5">
            <label for="source-title" class="block text-sm font-medium text-ink-secondary">
              Titre
            </label>
            <input
              id="source-title"
              type="text"
              bind:value={sourceTitle}
              placeholder="Titre de la source"
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
            />
          </div>

          <div class="space-y-1.5">
            <label for="source-authors" class="block text-sm font-medium text-ink-secondary">
              Auteurs
            </label>
            <input
              id="source-authors"
              type="text"
              bind:value={authors}
              placeholder="Dupont J., Martin A."
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
            />
          </div>

          <div class="sm:col-span-2 space-y-1.5">
            <label for="source-annotation" class="block text-sm font-medium text-ink-secondary">
              Annotation
            </label>
            <textarea
              id="source-annotation"
              bind:value={annotation}
              rows={2}
              placeholder="Pourquoi cette source est-elle importante ?"
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary resize-none"
            ></textarea>
          </div>

          <div class="sm:col-span-2 space-y-1.5">
            <label for="source-archive-url" class="block text-sm font-medium text-ink-secondary">
              Lien archivé <span class="text-ink-tertiary font-normal">(optionnel)</span>
              <span class="text-xs text-ink-tertiary font-normal block mt-0.5">
                Laisser vide pour que Philum tente un archivage automatique via Wayback Machine.
                Sinon, coller ici un snapshot existant (ex. <code
                  >https://web.archive.org/web/…</code
                >) ou tout autre miroir d'archive.
              </span>
            </label>
            <input
              id="source-archive-url"
              type="url"
              bind:value={archiveUrl}
              placeholder="https://web.archive.org/web/2026.../https://..."
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary font-mono text-sm"
            />
          </div>

          <div class="sm:col-span-2">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" bind:checked={isPivot} class="rounded border-border-strong" />
              <span class="text-sm text-ink-secondary"
                >Source clé (★ structurante du raisonnement)</span
              >
            </label>
          </div>

          {#if sources.length > 0}
            <div class="sm:col-span-2 space-y-1.5">
              <label for="source-parent" class="block text-sm font-medium text-ink-secondary">
                Cette source en cite une autre déjà ajoutée ?
                <span class="text-xs text-ink-tertiary font-normal"
                  >— affichée en pointillés dans le graphe</span
                >
              </label>
              <select
                id="source-parent"
                bind:value={parentSourceId}
                class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
              >
                <option value="">— Aucun lien parent —</option>
                {#each sources.filter((s) => s.id !== editingSourceId) as s}
                  <option value={s.id}>{s.title ?? s.url}</option>
                {/each}
              </select>
            </div>
          {/if}
        </div>

        <div class="flex justify-end gap-2">
          {#if isEditing}
            <Button type="button" variant="ghost" onclick={cancelEdit} disabled={addLoading}>
              Annuler
            </Button>
          {/if}
          <Button
            type="submit"
            variant={isEditing ? 'primary' : 'secondary'}
            loading={addLoading}
            disabled={!url || addLoading}
          >
            {#if addLoading}
              {isEditing ? 'Enregistrement…' : 'Ajout…'}
            {:else if isEditing}
              Enregistrer les modifications
            {:else}
              Ajouter
            {/if}
          </Button>
        </div>
      </form>
    {/if}
  </div>

  <!-- Sources list -->
  {#if sources.length > 0}
    <div class="mb-8">
      <h2 class="text-lg font-semibold text-ink-primary mb-3">
        Sources ajoutées ({sources.length})
      </h2>
      <div class="space-y-2">
        {#each sources as source (source.id)}
          {@const color = AUTHOR_COLORS[source.author_kind]}
          {@const isThisEditing = editingSourceId === source.id}
          <div
            class="flex items-start justify-between gap-3 bg-surface-primary border rounded-lg px-4 py-3 transition-colors {isThisEditing
              ? 'border-info/50 ring-1 ring-info/30'
              : 'border-border'}"
          >
            <div class="flex items-start gap-3 min-w-0">
              <span
                class="mt-0.5 shrink-0 inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full"
                style:background-color={color.fill}
                style:color={color.text}
              >
                {color.label}
              </span>
              <div class="min-w-0">
                <p class="text-sm font-medium text-ink-primary truncate">
                  {source.title ?? source.url}
                </p>
                {#if source.authors}
                  <p class="text-xs text-ink-tertiary">{source.authors}</p>
                {/if}
                <p class="text-xs text-ink-tertiary truncate">{source.url}</p>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onclick={() => startEdit(source)}
                disabled={isThisEditing}
                class="p-1.5 text-ink-tertiary hover:text-info disabled:text-info disabled:cursor-default transition-colors"
                aria-label="Modifier la source"
                title="Modifier"
              >
                <svg
                  viewBox="0 0 24 24"
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M12 20h9" />
                  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
              </button>
              <button
                type="button"
                onclick={() => (confirmDeleteId = source.id)}
                class="p-1.5 text-ink-tertiary hover:text-danger transition-colors"
                aria-label="Supprimer la source"
                title="Supprimer"
              >
                <svg
                  viewBox="0 0 24 24"
                  class="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <line x1="6" y1="6" x2="18" y2="18" />
                  <line x1="6" y1="18" x2="18" y2="6" />
                </svg>
              </button>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {:else}
    <div class="text-center py-8 text-ink-tertiary mb-8">
      <p class="text-sm">Aucune source ajoutée pour l'instant.</p>
    </div>
  {/if}

  <!-- Publish -->
  <div class="border-t border-border pt-6">
    {#if publishError}
      <div
        class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger mb-4"
      >
        {publishError}
      </div>
    {/if}

    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm text-ink-secondary">
          {sources.length === 0
            ? 'Ajoutez au moins une source avant de publier.'
            : `${sources.length} source${sources.length > 1 ? 's' : ''} prête${sources.length > 1 ? 's' : ''}.`}
        </p>
      </div>
      <div class="flex gap-3">
        <Button variant="ghost" href="/dashboard">Enregistrer en brouillon</Button>
        <Button
          onclick={publish}
          loading={publishing}
          disabled={sources.length === 0 || publishing}
        >
          {publishing ? 'Publication…' : 'Publier la fiche'}
        </Button>
      </div>
    </div>
  </div>
</div>

<ConfirmDialog
  open={confirmDeleteId !== null}
  title="Supprimer cette source ?"
  message="La source sera retirée de la fiche. Cette action est définitive."
  confirmLabel="Supprimer"
  variant="danger"
  onConfirm={() => (confirmDeleteId ? removeSource(confirmDeleteId) : undefined)}
  onCancel={() => (confirmDeleteId = null)}
/>
