<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
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

  const EXTRACT_API = `${import.meta.env.PUBLIC_API_BASE_URL ?? ''}/api/v1/sources/extract`;

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

  async function removeSource(id: string) {
    try {
      await api.sources.delete(id);
      sources = sources.filter((s) => s.id !== id);
      if (editingSourceId === id) resetForm();
    } catch (err) {
      addError = err instanceof Error ? err.message : 'Erreur lors de la suppression';
    }
  }

  async function publish() {
    publishError = null;
    publishing = true;
    try {
      await api.cards.publish(cardId);
      goto('/dashboard');
    } catch (err) {
      console.error('publish error:', err);
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        // Real network/CORS failure OR backend died mid-response (e.g. MissingGreenlet
        // before the publish endpoint's try/except wrapper). Surface a hint so it's
        // easier to diagnose than the generic "check your connection".
        publishError =
          "La requête de publication n'a pas abouti (aucune réponse du serveur). Ouvre la console (F12 → Network) pour voir le statut HTTP de POST /cards/.../publish et signale-le.";
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
</script>

<svelte:head>
  <title>Ajouter des sources - Filum</title>
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
    <div class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-6">
      {loadError}
    </div>
  {/if}

  <!-- Add / edit source form -->
  <div
    class="bg-white border rounded-xl p-6 mb-6 {isEditing
      ? 'border-blue-300 ring-1 ring-blue-200'
      : 'border-slate-200'}"
  >
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-slate-900">
        {isEditing ? 'Modifier la source' : 'Ajouter une source'}
      </h2>
      {#if isEditing}
        <button
          type="button"
          onclick={cancelEdit}
          class="text-sm text-slate-500 hover:text-slate-900 transition-colors"
        >
          Annuler
        </button>
      {/if}
    </div>

    <form onsubmit={submitSource} class="space-y-4">
      {#if addError}
        <div class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {addError}
        </div>
      {/if}

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div class="sm:col-span-2 space-y-1.5">
          <label for="source-url" class="block text-sm font-medium text-slate-700">
            URL <span class="text-red-500">*</span>
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
              class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400 read-only:bg-slate-50 read-only:text-slate-500 read-only:cursor-not-allowed"
            />
            {#if extracting}
              <div
                class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"
              ></div>
            {/if}
          </div>
          {#if isEditing}
            <p class="text-xs text-slate-500">
              L'URL d'une source ne peut pas être modifiée (préserve l'archivage Wayback).
            </p>
          {/if}
        </div>

        <div class="space-y-1.5">
          <label for="source-format" class="block text-sm font-medium text-slate-700">
            Format <span class="text-red-500">*</span>
          </label>
          <select
            id="source-format"
            value={sourceFormat}
            onchange={(e) => (sourceFormat = (e.target as HTMLSelectElement).value as SourceFormat)}
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {#each formatOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
        </div>

        <div class="space-y-1.5">
          <label for="source-category" class="block text-sm font-medium text-slate-700">
            Catégorie <span class="text-red-500">*</span>
          </label>
          <select
            id="source-category"
            value={sourceCategory}
            onchange={(e) =>
              (sourceCategory = (e.target as HTMLSelectElement).value as SourceCategory)}
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {#each categoryOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
        </div>

        <div class="sm:col-span-2 space-y-1.5">
          <label for="source-author-kind" class="block text-sm font-medium text-slate-700">
            Type d'auteur <span class="text-red-500">*</span>
            <span class="text-xs text-slate-500 font-normal">— colore le nœud dans le graphe</span>
          </label>
          <select
            id="source-author-kind"
            value={authorKind}
            onchange={(e) => (authorKind = (e.target as HTMLSelectElement).value as AuthorKind)}
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            style:border-left="4px solid {AUTHOR_COLORS[authorKind].stroke}"
          >
            {#each authorKindOptions as opt}
              <option value={opt}>{authorLabel(opt)}</option>
            {/each}
          </select>
        </div>

        <div class="space-y-1.5">
          <label for="source-title" class="block text-sm font-medium text-slate-700"> Titre </label>
          <input
            id="source-title"
            type="text"
            bind:value={sourceTitle}
            placeholder="Titre de la source"
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400"
          />
        </div>

        <div class="space-y-1.5">
          <label for="source-authors" class="block text-sm font-medium text-slate-700">
            Auteurs
          </label>
          <input
            id="source-authors"
            type="text"
            bind:value={authors}
            placeholder="Dupont J., Martin A."
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400"
          />
        </div>

        <div class="sm:col-span-2 space-y-1.5">
          <label for="source-annotation" class="block text-sm font-medium text-slate-700">
            Annotation
          </label>
          <textarea
            id="source-annotation"
            bind:value={annotation}
            rows={2}
            placeholder="Pourquoi cette source est-elle importante ?"
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400 resize-none"
          ></textarea>
        </div>

        <div class="sm:col-span-2 space-y-1.5">
          <label for="source-archive-url" class="block text-sm font-medium text-slate-700">
            Lien archivé <span class="text-slate-500 font-normal">(optionnel)</span>
            <span class="text-xs text-slate-500 font-normal block mt-0.5">
              Laisser vide pour que Filum tente un archivage automatique via Wayback Machine. Sinon,
              coller ici un snapshot existant (ex. <code>https://web.archive.org/web/…</code>) ou
              tout autre miroir d'archive.
            </span>
          </label>
          <input
            id="source-archive-url"
            type="url"
            bind:value={archiveUrl}
            placeholder="https://web.archive.org/web/2026.../https://..."
            class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400 font-mono text-sm"
          />
        </div>

        <div class="sm:col-span-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" bind:checked={isPivot} class="rounded border-slate-300" />
            <span class="text-sm text-slate-700">Source clé (★ structurante du raisonnement)</span>
          </label>
        </div>

        {#if sources.length > 0}
          <div class="sm:col-span-2 space-y-1.5">
            <label for="source-parent" class="block text-sm font-medium text-slate-700">
              Cette source en cite une autre déjà ajoutée ?
              <span class="text-xs text-slate-500 font-normal"
                >— affichée en pointillés dans le graphe</span
              >
            </label>
            <select
              id="source-parent"
              bind:value={parentSourceId}
              class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
  </div>

  <!-- Sources list -->
  {#if sources.length > 0}
    <div class="mb-8">
      <h2 class="text-lg font-semibold text-slate-900 mb-3">
        Sources ajoutées ({sources.length})
      </h2>
      <div class="space-y-2">
        {#each sources as source (source.id)}
          {@const color = AUTHOR_COLORS[source.author_kind]}
          {@const isThisEditing = editingSourceId === source.id}
          <div
            class="flex items-start justify-between gap-3 bg-white border rounded-lg px-4 py-3 transition-colors {isThisEditing
              ? 'border-blue-300 ring-1 ring-blue-200'
              : 'border-slate-200'}"
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
                <p class="text-sm font-medium text-slate-900 truncate">
                  {source.title ?? source.url}
                </p>
                {#if source.authors}
                  <p class="text-xs text-slate-500">{source.authors}</p>
                {/if}
                <p class="text-xs text-slate-400 truncate">{source.url}</p>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onclick={() => startEdit(source)}
                disabled={isThisEditing}
                class="p-1.5 text-slate-400 hover:text-blue-600 disabled:text-blue-600 disabled:cursor-default transition-colors"
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
                onclick={() => removeSource(source.id)}
                class="p-1.5 text-slate-400 hover:text-red-500 transition-colors"
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
    <div class="text-center py-8 text-slate-500 mb-8">
      <p class="text-sm">Aucune source ajoutée pour l'instant.</p>
    </div>
  {/if}

  <!-- Publish -->
  <div class="border-t border-slate-200 pt-6">
    {#if publishError}
      <div class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 mb-4">
        {publishError}
      </div>
    {/if}

    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm text-slate-600">
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
