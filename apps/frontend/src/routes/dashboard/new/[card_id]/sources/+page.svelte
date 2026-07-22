<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { api } from '$lib/api';
  import { pendingImportFile } from '$lib/stores/import-file';
  import { Button, ConfirmDialog, ProgressSteps } from '$lib/components';
  import { AUTHOR_COLORS, authorLabel } from '$lib/utils/author-colors';
  import type {
    AuthorKind,
    Card,
    Source,
    SourceCategory,
    SourceExcerpt,
    SourceFormat,
    SuggestedExcerpt,
  } from '$lib/api';

  const wizardSteps = [
    { label: 'Informations', description: 'Titre, plateforme', clickable: true },
    { label: 'Sources', description: 'Ajouter et publier' },
  ];

  const cardId = $derived($page.params.card_id ?? '');

  function onWizardStepClick(i: number) {
    if (i === 0) goto(`/dashboard/new?card_id=${cardId}`);
  }

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
  // Date de publication de la source (par ses auteurs originaux). Format YYYY-MM-DD.
  let publishedAt = $state('');
  // Metadonnees bibliographiques etendues (repliees par defaut).
  let journal = $state('');
  let volume = $state('');
  let pages = $state('');
  let publisher = $state('');
  let doiField = $state('');
  let extraMetaOpen = $state(false);
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
        if (data.published_at) publishedAt = String(data.published_at).slice(0, 10);
        if (data.journal) journal = data.journal;
        if (data.volume) volume = data.volume;
        if (data.pages) pages = data.pages;
        if (data.publisher) publisher = data.publisher;
        if (data.doi) doiField = data.doi;
        if (data.journal || data.volume || data.pages || data.publisher || data.doi) {
          extraMetaOpen = true;
        }
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
      if (loadedCard.content_url) refsUrl = loadedCard.content_url;
    } catch (err) {
      loadError = err instanceof Error ? err.message : 'Erreur de chargement';
    }
    // Fichier déposé à l'étape « Informations » : transmis en mémoire via le
    // store (un File survit aux navigations client-side de SvelteKit).
    const dropped = get(pendingImportFile);
    if (dropped) {
      pendingFile = dropped;
      pendingImportFile.set(null);
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
    publishedAt = '';
    journal = '';
    volume = '';
    pages = '';
    publisher = '';
    doiField = '';
    extraMetaOpen = false;
    lastExtractedUrl = '';
    taxonomySuggested = false;
    editingSourceId = null;
    addError = null;
    resetExcerptState();
  }

  function startEdit(source: Source, focusId: string = 'source-title') {
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
    publishedAt = source.published_at ? String(source.published_at).slice(0, 10) : '';
    journal = source.journal ?? '';
    volume = source.volume ?? '';
    pages = source.pages ?? '';
    publisher = source.publisher ?? '';
    doiField = source.doi ?? '';
    extraMetaOpen = Boolean(journal || volume || pages || publisher || doiField);
    lastExtractedUrl = source.url;
    taxonomySuggested = false;
    addError = null;
    resetExcerptState();
    if (typeof document !== 'undefined') {
      document.getElementById(focusId)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function parentTitle(parentId: string): string | null {
    const parent = sources.find((s) => s.id === parentId);
    if (!parent) return null;
    return parent.title ?? parent.url;
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
          published_at: publishedAt ? new Date(publishedAt).toISOString() : null,
          journal: journal || null,
          volume: volume || null,
          pages: pages || null,
          publisher: publisher || null,
          doi: doiField || null,
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
          published_at: publishedAt ? new Date(publishedAt).toISOString() : undefined,
          journal: journal || undefined,
          volume: volume || undefined,
          pages: pages || undefined,
          publisher: publisher || undefined,
          doi: doiField || undefined,
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

  // ── Citations (extraits) — mode édition uniquement (nécessite un id) ──────
  let excerptText = $state('');
  let excerptError = $state<string | null>(null);
  let excerptAdding = $state(false);
  let suggesting = $state(false);
  let suggestions = $state<SuggestedExcerpt[]>([]);
  let suggestInfo = $state<string | null>(null);

  const editingSource = $derived(sources.find((s) => s.id === editingSourceId) ?? null);

  function resetExcerptState() {
    excerptText = '';
    excerptError = null;
    suggestions = [];
    suggestInfo = null;
  }

  function updateSourceExcerpts(sourceId: string, excerpts: SourceExcerpt[]) {
    sources = sources.map((s) => (s.id === sourceId ? { ...s, excerpts } : s));
  }

  async function addExcerpt(text: string, suggestedByAi = false) {
    if (!editingSourceId) return;
    const value = text.trim();
    if (!value) return;
    excerptError = null;
    excerptAdding = true;
    try {
      const created = await api.excerpts.create(editingSourceId, {
        text: value,
        suggested_by_ai: suggestedByAi,
      });
      updateSourceExcerpts(editingSourceId, [...(editingSource?.excerpts ?? []), created]);
      if (!suggestedByAi) excerptText = '';
      suggestions = suggestions.filter((sug) => sug.text !== value);
    } catch (err) {
      excerptError = err instanceof Error ? err.message : "Erreur lors de l'ajout de la citation";
    } finally {
      excerptAdding = false;
    }
  }

  async function removeExcerpt(excerptId: string) {
    if (!editingSourceId) return;
    excerptError = null;
    try {
      await api.excerpts.delete(editingSourceId, excerptId);
      updateSourceExcerpts(
        editingSourceId,
        (editingSource?.excerpts ?? []).filter((x) => x.id !== excerptId)
      );
    } catch (err) {
      excerptError = err instanceof Error ? err.message : 'Erreur lors de la suppression';
    }
  }

  async function suggestExcerpts() {
    if (!editingSourceId) return;
    excerptError = null;
    suggestInfo = null;
    suggestions = [];
    suggesting = true;
    try {
      const res = await api.excerpts.suggest(editingSourceId);
      if (!res.llm_enabled) {
        suggestInfo = "La suggestion IA n'est pas configurée sur ce serveur.";
      } else if (res.suggestions.length === 0) {
        suggestInfo = 'Aucun passage citable repéré dans le texte de cette source.';
      } else {
        suggestions = res.suggestions;
      }
    } catch (err) {
      excerptError =
        err instanceof Error ? err.message : 'Erreur lors de la suggestion de citations';
    } finally {
      suggesting = false;
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
    published_at: string | null;
    status: DraftStatus;
    error: string | null;
  };

  let multiText = $state('');
  let drafts = $state<DraftSource[]>([]);
  let multiExtracting = $state(false);
  let addingAll = $state(false);
  let importing = $state(false);
  let importError = $state<string | null>(null);
  let importSummary = $state<string | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);

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
        published_at: null,
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
        published_at: draft.published_at || undefined,
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

  // ── Import de fichier (BibTeX, CSL-JSON Zotero, Markdown Obsidian, PDF) ──
  type ImportedDraft = {
    url: string;
    title: string | null;
    authors: string | null;
    published_at: string | null;
    format: string;
    category: string;
    author_kind: string;
  };

  type ImportResponse = { sources: ImportedDraft[]; skipped: number; format_detected?: string };

  async function ingestImported(data: ImportResponse) {
    // Dedup par URL uniquement pour les refs qui EN ONT une : les no-URL
    // refs (livres S2 sans DOI, sections de bibliographie) sont
    // deja dedupees titre-par-titre cote backend, on les laisse passer.
    const known = new Set(
      [...sources.map((s) => s.url), ...drafts.map((d) => d.url)].filter(Boolean)
    );
    let added = 0;
    let duplicates = 0;
    const needExtract: string[] = [];
    for (const ref of data.sources) {
      if (ref.url && known.has(ref.url)) {
        duplicates += 1;
        continue;
      }
      if (ref.url) known.add(ref.url);
      added += 1;
      drafts.push({
        url: ref.url,
        title: ref.title ?? '',
        authors: ref.authors ?? '',
        format: formatOptions.some((o) => o.value === ref.format)
          ? (ref.format as SourceFormat)
          : 'texte',
        category: categoryOptions.some((o) => o.value === ref.category)
          ? (ref.category as SourceCategory)
          : 'page-web',
        author_kind: authorKindOptions.includes(ref.author_kind as AuthorKind)
          ? (ref.author_kind as AuthorKind)
          : 'individu',
        published_at: ref.published_at,
        status: ref.title ? 'ready' : 'extracting',
        error: null,
      });
      if (!ref.title) needExtract.push(ref.url);
    }
    const parts = [`${added} référence${added > 1 ? 's' : ''} importée${added > 1 ? 's' : ''}`];
    if (duplicates > 0) parts.push(`${duplicates} déjà présente${duplicates > 1 ? 's' : ''}`);
    if (data.skipped > 0)
      parts.push(`${data.skipped} sans lien (ignorée${data.skipped > 1 ? 's' : ''})`);
    importSummary = `${parts.join(', ')}${
      data.format_detected ? ` — format détecté : ${data.format_detected}` : ''
    }.`;
    // Les refs sans titre (URL/DOI nus) passent par l'extracteur existant.
    for (const u of needExtract) {
      const draft = drafts.find((d) => d.url === u && d.status === 'extracting');
      if (!draft) continue;
      try {
        const res = await fetch(`${EXTRACT_API}?url=${encodeURIComponent(u)}`);
        if (res.ok) {
          const meta = await res.json();
          if (meta.title) draft.title = meta.title;
          if (meta.authors) draft.authors = meta.authors;
          if (meta.format && formatOptions.some((o) => o.value === meta.format)) {
            draft.format = meta.format;
          }
          if (meta.category && categoryOptions.some((o) => o.value === meta.category)) {
            draft.category = meta.category;
          }
          if (meta.author_kind && authorKindOptions.includes(meta.author_kind)) {
            draft.author_kind = meta.author_kind;
          }
        }
      } catch {
        // extraction silencieuse : l'utilisateur complète à la main
      }
      draft.status = 'ready';
    }
  }

  async function importFile(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    await processFile(file);
  }

  async function processFile(file: File) {
    importError = null;
    importSummary = null;
    if (file.size > 5 * 1024 * 1024) {
      importError = 'Fichier trop volumineux (limite : 5 Mo).';
      return;
    }
    importing = true;
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch('/api/v1/import/parse', { method: 'POST', body: form });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        importError =
          body?.detail?.message ?? body?.error?.message ?? `Erreur d'import (${response.status})`;
        return;
      }
      await ingestImported(await response.json());
    } catch (err) {
      importError = err instanceof Error ? err.message : "Erreur lors de l'import";
    } finally {
      importing = false;
    }
  }

  // ── Bibliographie collée en texte libre (déterministe + IA) ──────────────
  let analyzingText = $state(false);

  async function analyzeText() {
    const text = multiText.trim();
    if (!text) return;
    importError = null;
    importSummary = null;
    analyzingText = true;
    try {
      const response = await fetch('/api/v1/import/paste', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        importError =
          body?.detail?.message ?? body?.error?.message ?? `Erreur d'analyse (${response.status})`;
        return;
      }
      await ingestImported(await response.json());
      multiText = '';
    } catch (err) {
      importError = err instanceof Error ? err.message : "Erreur lors de l'analyse";
    } finally {
      analyzingText = false;
    }
  }

  // ── Extraction depuis la page de contenu (URL de la fiche) ────────────────
  let refsUrl = $state('');
  let refsExtracting = $state(false);
  let refsError = $state<string | null>(null);
  let refsInfo = $state<string | null>(null);
  let overwriteDrafts = $state(false);
  let hasExtractedRefs = $state(false);
  let pendingFile = $state<File | null>(null);

  async function extractReferences() {
    const target = refsUrl.trim();
    if (!target || refsExtracting) return;
    refsError = null;
    refsInfo = null;
    importError = null;
    importSummary = null;
    refsExtracting = true;
    try {
      const res = await api.imports.fromContentUrl(target);
      const hasRefs = res.sources.length > 0;
      // Le fetch_status decrit UNIQUEMENT le fetch HTML direct : Semantic
      // Scholar / Crossref restent interrogeables meme quand la page est
      // bloquee (ScienceDirect/Elsevier). Ne surtout pas afficher une erreur
      // "site inaccessible" si on a quand meme recupere N refs par ailleurs.
      if (hasRefs) {
        if (res.fetch_status === 'unreachable' || res.fetch_status === 'not_html') {
          refsInfo = `Le site bloque l'accès direct — ${res.sources.length} référence${
            res.sources.length > 1 ? 's' : ''
          } récupérée${res.sources.length > 1 ? 's' : ''} via Semantic Scholar / Crossref.`;
        } else if (res.fetch_status === 'ok_via_wayback') {
          refsInfo =
            'Le site bloque l’accès direct : extraction faite depuis une capture Internet Archive.';
        }
        if (overwriteDrafts) drafts = [];
        await ingestImported({ sources: res.sources, skipped: res.skipped });
        hasExtractedRefs = true;
      } else if (res.fetch_status === 'unreachable') {
        refsError = 'La page n’a pas pu être récupérée (site inaccessible ou bloqué).';
      } else if (res.fetch_status === 'not_html') {
        refsError =
          'Ce lien ne pointe pas vers une page web (PDF, image…) — l’extraction ne fonctionne que sur du HTML.';
      } else {
        refsInfo = res.references_section_found
          ? 'Aucune référence exploitable trouvée sur cette page.'
          : 'Aucune section « Références » détectée sur cette page.';
      }
    } catch (err) {
      refsError = err instanceof Error ? err.message : 'Erreur lors de l’extraction';
    } finally {
      refsExtracting = false;
    }
  }

  async function analyzePendingFile() {
    if (!pendingFile || importing) return;
    await processFile(pendingFile);
    if (!importError) pendingFile = null;
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

  <ProgressSteps steps={wizardSteps} current={1} onStepClick={onWizardStepClick} class="mb-8" />

  {#if loadError}
    <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger mb-6">
      {loadError}
    </div>
  {/if}

  {#if !isEditing}
    <!-- Extraction depuis la page de contenu -->
    <div class="bg-surface-primary border border-border rounded-xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-ink-primary mb-1">
        Extraire les sources de votre contenu
      </h2>
      <p class="text-sm text-ink-tertiary mb-4">
        Philum lit la page de votre contenu (description, section références) et en extrait les
        sources citées, à valider ci-dessous avant ajout.
      </p>

      <div class="flex items-center gap-2">
        <input
          type="url"
          bind:value={refsUrl}
          placeholder="https://youtube.com/watch?v=... ou https://votre-blog.fr/article"
          class="flex-1 min-w-0 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
        />
        {#if hasExtractedRefs}
          <button
            type="button"
            onclick={extractReferences}
            disabled={refsExtracting || !refsUrl.trim()}
            class="p-2 rounded-lg border border-border-strong text-ink-secondary hover:text-ink-primary hover:bg-surface-secondary transition-colors disabled:opacity-50 shrink-0"
            title="Relancer l’extraction"
            aria-label="Relancer l’extraction"
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
              <path d="M21 12a9 9 0 1 1-3-6.7" />
              <polyline points="21 3 21 9 15 9" />
            </svg>
          </button>
        {/if}
        <Button
          type="button"
          variant="secondary"
          loading={refsExtracting}
          disabled={refsExtracting || !refsUrl.trim()}
          onclick={extractReferences}
        >
          {refsExtracting ? 'Extraction…' : 'Extraire les sources'}
        </Button>
      </div>

      <label class="flex items-center gap-2 mt-3 text-sm text-ink-secondary cursor-pointer">
        <input
          type="checkbox"
          bind:checked={overwriteDrafts}
          class="rounded border-border-strong text-info focus:ring-info"
        />
        Écraser les brouillons non ajoutés lors d’une nouvelle extraction
      </label>

      {#if refsError}
        <div
          class="mt-3 rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger"
        >
          {refsError}
        </div>
      {/if}
      {#if refsInfo}
        <div class="mt-3 rounded-lg bg-info/10 border border-info/30 px-4 py-3 text-sm text-info">
          {refsInfo}
        </div>
      {/if}

      {#if pendingFile}
        <div
          class="mt-4 flex items-center justify-between gap-3 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3"
        >
          <div class="min-w-0">
            <p class="text-sm text-ink-primary truncate">{pendingFile.name}</p>
            <p class="text-xs text-ink-tertiary">Fichier déposé à l’étape précédente</p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <Button
              type="button"
              variant="secondary"
              loading={importing}
              disabled={importing}
              onclick={analyzePendingFile}
            >
              {importing ? 'Analyse…' : 'Analyser le fichier'}
            </Button>
            <button
              type="button"
              onclick={() => (pendingFile = null)}
              class="p-1 text-ink-tertiary hover:text-danger transition-colors"
              aria-label="Retirer le fichier"
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
      {/if}
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
        {isEditing ? 'Modifier la source' : 'Ajouter des sources'}
      </h2>
      {#if isEditing}
        <button
          type="button"
          onclick={cancelEdit}
          class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
        >
          Annuler
        </button>
      {/if}
    </div>

    {#if !isEditing}
      <div class="space-y-4">
        <div class="space-y-1.5">
          <label for="multi-urls" class="block text-sm font-medium text-ink-secondary">
            Liens, DOIs ou bibliographie collée
            <span class="text-xs text-ink-tertiary font-normal block mt-0.5">
              Trois usages : (1) coller une liste d'URLs (une par ligne), (2) coller un bloc de
              bibliographie brute (l'IA découpe et structure chaque référence), (3) mixer les deux.
            </span>
          </label>
          <textarea
            id="multi-urls"
            bind:value={multiText}
            rows={8}
            placeholder={'— Une liste de liens :\nhttps://doi.org/10.1038/s41586-020-2649-2\nhttps://www.lemonde.fr/...\n\n— OU une bibliographie complète collée depuis un article, Zotero, un PDF… :\nWolfe, C. D., & Bell, M. A. (2007). The integration of cognition and emotion during infancy and early childhood: regulatory processes associated with the development of working memory. Brain and Cognition, 65(1), 3–13. https://doi.org/10.1016/j.bandc.2006.01.009\nDupont, J., & Martin, A. (2020). Titre. Journal, 12(3), 45-67.'}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary font-mono text-sm resize-y min-h-[8rem]"
          ></textarea>
        </div>
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <input
              type="file"
              accept=".bib,.bibtex,.json,.md,.markdown,.pdf,.docx,.html,.htm"
              class="hidden"
              bind:this={fileInput}
              onchange={importFile}
            />
            <Button
              type="button"
              variant="secondary"
              loading={importing}
              disabled={importing}
              onclick={() => fileInput?.click()}
            >
              {#if !importing}
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  class="w-4 h-4"
                  aria-hidden="true"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              {/if}
              {importing ? 'Import…' : 'Importer un fichier'}
            </Button>
            <p class="text-xs text-ink-tertiary mt-1">
              BibTeX, CSL-JSON (Zotero), Markdown (Obsidian), PDF, Word ou page HTML — 5 Mo max
            </p>
          </div>
          <div class="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              loading={analyzingText}
              disabled={analyzingText || multiExtracting || !multiText.trim()}
              onclick={analyzeText}
              title="L'IA découpe une bibliographie collée en références structurées — fonctionne même sans liens ni DOIs"
            >
              {analyzingText ? 'Analyse…' : 'Analyser le texte (IA)'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              loading={multiExtracting}
              disabled={multiExtracting || analyzingText || !multiText.trim()}
              onclick={extractAll}
              title="Récupère uniquement les URLs et DOIs présents dans le texte (instantané, sans IA)"
            >
              {multiExtracting ? 'Extraction…' : 'Extraire les URLs/DOIs'}
            </Button>
          </div>
        </div>

        {#if importError}
          <div
            class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger"
          >
            {importError}
          </div>
        {/if}
        {#if importSummary}
          <div class="rounded-lg bg-info/10 border border-info/30 px-4 py-3 text-sm text-info">
            {importSummary}
          </div>
        {/if}

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

      <div class="flex items-center gap-3 my-6" aria-hidden="true">
        <div class="flex-1 h-px bg-border"></div>
        <span class="text-xs uppercase tracking-wider text-ink-tertiary"
          >Ou ajouter une source à la fois</span
        >
        <div class="flex-1 h-px bg-border"></div>
      </div>
    {/if}

    <form onsubmit={submitSource} class="space-y-4">
      {#if addError}
        <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
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
            onchange={(e) => (sourceFormat = (e.target as HTMLSelectElement).value as SourceFormat)}
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

        <div class="space-y-1.5">
          <label for="source-author-kind" class="block text-sm font-medium text-ink-secondary">
            Type d'auteur <span class="text-danger">*</span>
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
          <label for="source-published-at" class="block text-sm font-medium text-ink-secondary">
            Date de publication
            <span class="text-xs text-ink-tertiary font-normal">— par les auteurs originaux</span>
          </label>
          <input
            id="source-published-at"
            type="date"
            bind:value={publishedAt}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
          />
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary resize-y min-h-[3rem]"
          ></textarea>
        </div>

        <div class="sm:col-span-2 space-y-1.5">
          <label for="source-archive-url" class="block text-sm font-medium text-ink-secondary">
            Lien archivé <span class="text-ink-tertiary font-normal">(optionnel)</span>
            <span class="text-xs text-ink-tertiary font-normal block mt-0.5">
              Laisser vide pour que Philum tente un archivage automatique via Wayback Machine.
              Sinon, coller ici un snapshot existant (ex. <code>https://web.archive.org/web/…</code
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
          <button
            type="button"
            onclick={() => (extraMetaOpen = !extraMetaOpen)}
            class="flex items-center gap-1.5 text-sm font-medium text-ink-secondary hover:text-ink-primary transition-colors"
            aria-expanded={extraMetaOpen}
            aria-controls="source-extra-meta"
          >
            <svg
              viewBox="0 0 24 24"
              class="w-4 h-4 transition-transform {extraMetaOpen ? 'rotate-180' : ''}"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
            Métadonnées bibliographiques (journal, DOI, éditeur…)
          </button>
          {#if extraMetaOpen}
            <div id="source-extra-meta" class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div class="space-y-1.5 sm:col-span-2">
                <label for="source-journal" class="block text-sm font-medium text-ink-secondary">
                  Journal / revue
                </label>
                <input
                  id="source-journal"
                  type="text"
                  bind:value={journal}
                  placeholder="Nature Neuroscience"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
                />
              </div>
              <div class="space-y-1.5">
                <label for="source-volume" class="block text-sm font-medium text-ink-secondary">
                  Volume
                </label>
                <input
                  id="source-volume"
                  type="text"
                  bind:value={volume}
                  placeholder="42"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
                />
              </div>
              <div class="space-y-1.5">
                <label for="source-pages" class="block text-sm font-medium text-ink-secondary">
                  Pages
                </label>
                <input
                  id="source-pages"
                  type="text"
                  bind:value={pages}
                  placeholder="123-145"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
                />
              </div>
              <div class="space-y-1.5">
                <label for="source-publisher" class="block text-sm font-medium text-ink-secondary">
                  Éditeur
                </label>
                <input
                  id="source-publisher"
                  type="text"
                  bind:value={publisher}
                  placeholder="Elsevier"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
                />
              </div>
              <div class="space-y-1.5">
                <label for="source-doi" class="block text-sm font-medium text-ink-secondary">
                  DOI
                </label>
                <input
                  id="source-doi"
                  type="text"
                  bind:value={doiField}
                  placeholder="10.1038/s41593-023-01234-5"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary font-mono text-sm"
                />
              </div>
            </div>
          {/if}
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

      {#if isEditing && editingSource}
        <div class="border-t border-border pt-4 space-y-3">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <h3 class="text-sm font-semibold text-ink-primary">
              Citations
              <span class="text-xs text-ink-tertiary font-normal"
                >— extraits marquants de cette source (max 10)</span
              >
            </h3>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              loading={suggesting}
              disabled={suggesting || excerptAdding}
              onclick={suggestExcerpts}
            >
              {suggesting ? 'Analyse…' : 'Suggérer des citations (IA)'}
            </Button>
          </div>

          {#if excerptError}
            <div
              class="rounded-lg bg-danger-bg border border-danger/30 px-3 py-2 text-xs text-danger"
            >
              {excerptError}
            </div>
          {/if}
          {#if suggestInfo}
            <div class="rounded-lg bg-info/10 border border-info/30 px-3 py-2 text-xs text-info">
              {suggestInfo}
            </div>
          {/if}

          {#if editingSource.excerpts.length > 0}
            <ul class="space-y-2">
              {#each editingSource.excerpts as excerpt (excerpt.id)}
                <li
                  class="flex items-start justify-between gap-2 rounded-lg border border-border bg-surface-secondary/50 px-3 py-2"
                >
                  <p class="text-sm text-ink-secondary italic min-w-0">
                    «&nbsp;{excerpt.text}&nbsp;»
                    {#if excerpt.suggested_by_ai}
                      <span class="text-xs text-ink-tertiary not-italic">(IA)</span>
                    {/if}
                  </p>
                  <button
                    type="button"
                    onclick={() => removeExcerpt(excerpt.id)}
                    class="p-1 shrink-0 text-ink-tertiary hover:text-danger transition-colors"
                    aria-label="Supprimer cette citation"
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
                </li>
              {/each}
            </ul>
          {/if}

          {#if suggestions.length > 0}
            <div class="space-y-2">
              <p class="text-xs font-medium text-ink-secondary">
                Suggestions repérées dans le texte (vérifiées mot pour mot) :
              </p>
              {#each suggestions as sug (sug.char_offset)}
                <div class="rounded-lg border border-info/30 bg-info/5 px-3 py-2 space-y-1.5">
                  <p class="text-xs text-ink-tertiary">
                    …{sug.context_before}<span class="text-ink-primary font-medium">{sug.text}</span
                    >{sug.context_after}…
                  </p>
                  <div class="flex justify-end">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={excerptAdding || editingSource.excerpts.length >= 10}
                      onclick={() => addExcerpt(sug.text, true)}
                    >
                      Ajouter
                    </Button>
                  </div>
                </div>
              {/each}
            </div>
          {/if}

          <div class="flex gap-2">
            <input
              type="text"
              bind:value={excerptText}
              maxlength={1000}
              placeholder="Ajouter une citation manuellement…"
              class="flex-1 px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-tertiary"
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={excerptAdding}
              disabled={excerptAdding || !excerptText.trim()}
              onclick={() => addExcerpt(excerptText)}
            >
              Ajouter
            </Button>
          </div>
        </div>
      {/if}

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
      <h2 class="text-lg font-semibold text-ink-primary mb-3">
        Sources ajoutées ({sources.length})
      </h2>
      <div class="space-y-2">
        {#each sources as source, sourceIndex (source.id)}
          {@const color = AUTHOR_COLORS[source.author_kind]}
          {@const isThisEditing = editingSourceId === source.id}
          <div
            class="flex items-start justify-between gap-3 bg-surface-primary border rounded-lg px-4 py-3 transition-colors {isThisEditing
              ? 'border-info/50 ring-1 ring-info/30'
              : 'border-border'}"
          >
            <div class="flex items-start gap-3 min-w-0">
              <span
                class="mt-0.5 shrink-0 inline-flex items-center justify-center min-w-[1.75rem] px-1.5 py-0.5 text-xs font-mono font-medium text-ink-tertiary bg-surface-tertiary border border-border rounded"
                aria-label="Numéro de source"
                title="Position dans la fiche"
              >
                {sourceIndex + 1}
              </span>
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
                {#if source.parent_source_id}
                  {@const parentLabel = parentTitle(source.parent_source_id)}
                  {#if parentLabel}
                    <p class="text-xs text-info truncate" title="Cette source cite : {parentLabel}">
                      ↳ cite : {parentLabel}
                    </p>
                  {/if}
                {/if}
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              {#if sources.length > 1}
                <button
                  type="button"
                  onclick={() => startEdit(source, 'source-parent')}
                  disabled={isThisEditing}
                  class="p-1.5 text-ink-tertiary hover:text-info disabled:text-info disabled:cursor-default transition-colors"
                  aria-label="Lier à une source parente"
                  title={source.parent_source_id
                    ? 'Modifier la source citée'
                    : 'Indiquer quelle source celle-ci cite'}
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
                    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                  </svg>
                </button>
              {/if}
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
