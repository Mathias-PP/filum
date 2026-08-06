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
    ArchiveOutcome,
    AuthorKind,
    Card,
    CardSearchResult,
    Source,
    SourceCategory,
    SourceExcerpt,
    SourceFormat,
    SourceStance,
    SuggestedExcerpt,
  } from '$lib/api';
  import { STANCE_ORDER, STANCE_STYLES } from '$lib/utils/stance';

  const wizardSteps = [
    { label: 'Informations', description: 'Titre, plateforme', clickable: true },
    { label: 'Sources', description: 'Ajouter et publier' },
    { label: 'Connexions', description: 'Fiches liees', clickable: true },
  ];

  const cardId = $derived($page.params.card_id ?? '');

  function onWizardStepClick(i: number) {
    if (i === 0) goto(`/dashboard/new?card_id=${cardId}`);
    if (i === 2) goto(`/dashboard/new/${cardId}/connexions`);
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
  let linkedCardId = $state<string>('');
  let sourceTitle = $state('');
  let authors = $state('');
  let annotation = $state('');
  // '' = non déclaré. Distinct de « mentionne » : l'un est un silence, l'autre
  // une réponse. Le sélecteur ne doit donc pas avoir de valeur par défaut.
  let stance = $state<SourceStance | ''>('');
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
  // Le lien vers une autre source de la fiche est rare : replié par défaut, il
  // ne doit pas peser autant que l'URL ou le titre dans le formulaire.
  let parentLinkOpen = $state(false);
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
    stance = '';
    isPivot = false;
    parentSourceId = '';
    parentSourceQuery = '';
    linkedCardId = '';
    linkedCardQuery = '';
    linkedCardResults = [];
    linkedCardSelected = null;
    archiveUrl = '';
    publishedAt = '';
    journal = '';
    volume = '';
    pages = '';
    publisher = '';
    doiField = '';
    extraMetaOpen = false;
    parentLinkOpen = false;
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
    stance = source.stance ?? '';
    isPivot = source.is_pivot;
    parentSourceId = source.parent_source_id ?? '';
    parentSourceQuery = '';
    linkedCardId = source.linked_card_id ?? '';
    linkedCardQuery = '';
    linkedCardResults = [];
    linkedCardSelected = null;
    if (linkedCardId) void loadSelectedLinkedCard(linkedCardId);
    archiveUrl = source.archive_url ?? '';
    publishedAt = source.published_at ? String(source.published_at).slice(0, 10) : '';
    journal = source.journal ?? '';
    volume = source.volume ?? '';
    pages = source.pages ?? '';
    publisher = source.publisher ?? '';
    doiField = source.doi ?? '';
    extraMetaOpen = Boolean(journal || volume || pages || publisher || doiField);
    parentLinkOpen = Boolean(parentSourceId);
    lastExtractedUrl = source.url;
    taxonomySuggested = false;
    addError = null;
    resetExcerptState();
    if (typeof document !== 'undefined') {
      document.getElementById(focusId)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // ── Pickers de parent ────────────────────────────────────────────────────
  // Deux recherches volontairement distinctes : l'une filtre les sources déjà
  // dans la fiche (numérotées, car une fiche peut en compter des centaines),
  // l'autre interroge le serveur pour les fiches (méta-fiches).
  let parentSourceQuery = $state('');
  let linkedCardQuery = $state('');
  let linkedCardResults = $state<CardSearchResult[]>([]);
  let linkedCardLoading = $state(false);
  // Mémorise la fiche choisie : elle peut sortir des résultats quand la
  // recherche change, et on doit continuer à afficher ce qui est sélectionné.
  let linkedCardSelected = $state<CardSearchResult | null>(null);

  /** Sources de la fiche, numérotées dans l'ordre d'affichage puis filtrées. */
  const numberedSources = $derived(
    sources
      .map((s, i) => ({ source: s, number: i + 1 }))
      .filter(({ source }) => source.id !== editingSourceId)
      .filter(({ source, number }) => {
        const q = parentSourceQuery.trim().toLowerCase();
        if (!q) return true;
        return `${number} ${source.title ?? ''} ${source.url}`.toLowerCase().includes(q);
      })
  );

  async function loadSelectedLinkedCard(id: string) {
    try {
      const card = await api.cards.get(id);
      linkedCardSelected = {
        id: card.id,
        title: card.title,
        slug: card.slug,
        creator_slug: '',
        status: card.status,
        is_own: true,
      };
    } catch {
      // Fiche devenue inaccessible : on garde l'id, l'utilisateur peut le vider.
      linkedCardSelected = null;
    }
  }

  let linkedCardTimer: ReturnType<typeof setTimeout> | undefined;
  function onLinkedCardQueryInput() {
    clearTimeout(linkedCardTimer);
    linkedCardTimer = setTimeout(() => void searchLinkedCards(), 250);
  }

  async function searchLinkedCards() {
    linkedCardLoading = true;
    try {
      linkedCardResults = await api.cards.search(linkedCardQuery.trim(), 30);
    } catch {
      linkedCardResults = [];
    } finally {
      linkedCardLoading = false;
    }
  }

  function pickLinkedCard(card: CardSearchResult) {
    linkedCardId = card.id;
    linkedCardSelected = card;
    linkedCardQuery = '';
    linkedCardResults = [];
  }

  function clearLinkedCard() {
    linkedCardId = '';
    linkedCardSelected = null;
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
          stance: stance || null,
          is_pivot: isPivot,
          parent_source_id: parentSourceId || null,
          linked_card_id: linkedCardId || null,
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
          stance: stance || undefined,
          is_pivot: isPivot,
          parent_source_id: parentSourceId || undefined,
          linked_card_id: linkedCardId || undefined,
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

  // Archivage à la demande. L'archivage automatique est cadencé et peut prendre
  // des heures sur une grosse fiche : ces contrôles servent à dire ce qui presse.
  let selectedForArchive = $state<Set<string>>(new Set());
  let archiving = $state(false);
  let archiveMessage = $state<string | null>(null);

  /** Une source déjà archivée ou sans URL n'a rien à relancer. */
  function isArchivable(s: Source): boolean {
    return Boolean((s.url ?? '').trim()) && s.archive_status !== 'archived';
  }

  const archivableSources = $derived(sources.filter(isArchivable));
  const selectedCount = $derived(
    archivableSources.filter((s) => selectedForArchive.has(s.id)).length
  );

  function toggleArchiveSelection(id: string) {
    const next = new Set(selectedForArchive);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selectedForArchive = next;
  }

  function toggleAllArchiveSelection() {
    selectedForArchive =
      selectedCount === archivableSources.length
        ? new Set()
        : new Set(archivableSources.map((s) => s.id));
  }

  /**
   * Rend compte de ce qui a réellement été déclenché, poste par poste.
   *
   * Un seul compteur mentirait : « 3 » ne dirait pas si les 3 partent à
   * l'archivage ou si deux d'entre elles étaient déjà en file.
   */
  function describeOutcome(o: ArchiveOutcome): string {
    const parts: string[] = [];
    if (o.scheduled > 0) parts.push(`${o.scheduled} mise${o.scheduled > 1 ? 's' : ''} en file`);
    if (o.already_running > 0) parts.push(`${o.already_running} déjà en cours`);
    if (o.already_archived > 0)
      parts.push(`${o.already_archived} déjà archivée${o.already_archived > 1 ? 's' : ''}`);
    if (o.nothing_to_archive > 0) parts.push(`${o.nothing_to_archive} sans URL à archiver`);
    if (parts.length === 0) return 'Rien à archiver.';
    return `${parts.join(', ')}. L'archivage se fait en arrière-plan : le statut se met à jour d'ici quelques minutes.`;
  }

  async function archiveSources(ids: string[]) {
    if (ids.length === 0 || archiving) return;
    archiving = true;
    archiveMessage = null;
    try {
      archiveMessage = describeOutcome(await api.sources.archive(ids));
      selectedForArchive = new Set();
    } catch (err) {
      archiveMessage =
        err instanceof Error ? err.message : "Erreur lors du lancement de l'archivage";
    } finally {
      archiving = false;
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
          'La publication n’a pas abouti : le serveur n’a pas répondu. Vérifiez votre connexion puis réessayez. Votre brouillon et vos sources sont conservés.';
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
    // Cle stable pour {#each} : les refs sans URL (livres S2 sans DOI)
    // partagent url="" et collisionnaient sur draft.url -> Svelte 5 ne
    // rendait plus la liste des lors qu'il y en avait plusieurs.
    key: string;
    url: string;
    title: string;
    authors: string;
    format: SourceFormat;
    category: SourceCategory;
    author_kind: AuthorKind;
    published_at: string | null;
    // Metadonnees bibliographiques etendues (repliees par defaut).
    journal: string;
    volume: string;
    pages: string;
    publisher: string;
    doi: string;
    extraMetaOpen: boolean;
    status: DraftStatus;
    error: string | null;
  };

  let draftKeySeq = 0;
  function nextDraftKey(): string {
    draftKeySeq += 1;
    return `d${draftKeySeq}`;
  }

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
        key: nextDraftKey(),
        url: u,
        title: '',
        authors: '',
        format: 'texte',
        category: 'page-web',
        author_kind: 'individu',
        published_at: null,
        journal: '',
        volume: '',
        pages: '',
        publisher: '',
        doi: '',
        extraMetaOpen: false,
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
          if (data.published_at) draft.published_at = data.published_at;
          if (data.journal) draft.journal = data.journal;
          if (data.volume) draft.volume = data.volume;
          if (data.pages) draft.pages = data.pages;
          if (data.publisher) draft.publisher = data.publisher;
          if (data.doi) draft.doi = data.doi;
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
        journal: draft.journal || undefined,
        volume: draft.volume || undefined,
        pages: draft.pages || undefined,
        publisher: draft.publisher || undefined,
        doi: draft.doi || undefined,
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
    for (const { key: k } of pending) {
      const idx = drafts.findIndex((d) => d.key === k);
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
    journal?: string | null;
    volume?: string | null;
    pages?: string | null;
    publisher?: string | null;
    doi?: string | null;
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
        key: nextDraftKey(),
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
        journal: ref.journal ?? '',
        volume: ref.volume ?? '',
        pages: ref.pages ?? '',
        publisher: ref.publisher ?? '',
        doi: ref.doi ?? '',
        extraMetaOpen: Boolean(ref.journal || ref.volume || ref.pages || ref.publisher || ref.doi),
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
      data.format_detected ? ` (format détecté : ${data.format_detected})` : ''
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

      // L'extraction connaît les auteurs du contenu visé : c'est le seul moment
      // où on les obtient sans les demander. Sans eux, le nœud de la fiche dans
      // le graphe s'annonce sous le nom de son créateur, laissant croire qu'il
      // est l'auteur de ce qu'elle documente. On n'écrase jamais une saisie.
      if (res.card.authors && card && !card.content_authors) {
        try {
          card = await api.cards.update(cardId, { content_authors: res.card.authors });
        } catch {
          // Enrichissement opportuniste : son échec ne doit pas priver
          // l'utilisateur des références qui viennent d'être extraites.
        }
      }

      const hasRefs = res.sources.length > 0;
      // Le fetch_status decrit UNIQUEMENT le fetch HTML direct : Semantic
      // Scholar / Crossref restent interrogeables meme quand la page est
      // bloquee (ScienceDirect/Elsevier). Ne surtout pas afficher une erreur
      // "site inaccessible" si on a quand meme recupere N refs par ailleurs.
      if (hasRefs) {
        // Priorite au badge de confiance issu du pipeline v2 :
        // 'high'  = section References bornee -> filtrage strict
        // 'medium'= fallback body-search -> l'user est prevenu
        // 'low'   = ni oracle ni HTML -> tres rare
        const conf = res.extraction_confidence;
        const oracle = res.refs_from_oracle ?? 0;
        const enrich = res.refs_from_enrichment ?? 0;
        const dropped = res.refs_dropped_validation ?? 0;
        const detail =
          oracle && enrich
            ? ` (${oracle} sources autoritatives + ${enrich} enrichies)`
            : oracle
              ? ` (source autoritative)`
              : '';
        const noise =
          dropped > 0
            ? ` (${dropped} suggestion${dropped > 1 ? 's' : ''} bruit${dropped > 1 ? 'ées' : 'ée'} filtré${dropped > 1 ? 'es' : 'e'})`
            : '';
        if (conf === 'high') {
          refsInfo = `${res.sources.length} référence${res.sources.length > 1 ? 's' : ''} extraite${res.sources.length > 1 ? 's' : ''}${detail}. Confiance élevée${noise}.`;
        } else if (conf === 'medium') {
          // La réserve ne porte que sur les références enrichies : demander de
          // vérifier l'ensemble ferait douter de celles que l'éditeur a
          // lui-même déposées, sur lesquelles il n'y a rien à trancher.
          const toCheck = oracle
            ? `Vérifiez les ${enrich} référence${enrich > 1 ? 's' : ''} enrichie${enrich > 1 ? 's' : ''} : ${enrich > 1 ? 'ce sont' : "c'est"} ${enrich > 1 ? 'des sources' : 'une source'} retrouvée${enrich > 1 ? 's' : ''} dans le corps de la page, pas dans une bibliographie déclarée`
            : 'Vérifiez que ce sont bien des sources citées';
          refsInfo = `${res.sources.length} référence${res.sources.length > 1 ? 's' : ''} extraite${res.sources.length > 1 ? 's' : ''}${detail}. Confiance moyenne : aucune section « Références » nette n'a été détectée. ${toCheck}${noise}.`;
        } else {
          refsInfo = `${res.sources.length} référence${res.sources.length > 1 ? 's' : ''} extraite${res.sources.length > 1 ? 's' : ''}. Confiance basse : aucune validation possible, à vérifier manuellement${noise}.`;
        }
        if (res.fetch_status === 'ok_via_wayback') {
          refsInfo += ' Source récupérée depuis Internet Archive.';
        }
        if (overwriteDrafts) drafts = [];
        await ingestImported({ sources: res.sources, skipped: res.skipped });
        hasExtractedRefs = true;
      } else if (res.fetch_status === 'unreachable') {
        refsError = 'La page n’a pas pu être récupérée (site inaccessible ou bloqué).';
      } else if (res.fetch_status === 'not_html') {
        refsError =
          'Ce lien ne pointe pas vers une page web (PDF, image…) : l’extraction ne fonctionne que sur du HTML.';
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

  // ── Canal transcript YouTube ──────────────────────────────────────────────
  // Séparé des références : le texte vient d'une reconnaissance vocale, donc
  // bruité (noms propres massacrés). Chaque suggestion doit être cochée.
  const YOUTUBE_HOST_RE =
    /^(?:https?:\/\/)?(?:[\w-]+\.)*(?:youtube\.com|youtube-nocookie\.com|youtu\.be)(?:\/|$)/i;
  let transcriptLoading = $state(false);
  let transcriptError = $state<string | null>(null);
  let transcriptInfo = $state<string | null>(null);
  let transcriptSuggestions = $state<ImportedDraft[]>([]);
  let transcriptChecked = $state<boolean[]>([]);

  const isYoutubeTarget = $derived(YOUTUBE_HOST_RE.test(refsUrl.trim()));
  const transcriptCheckedCount = $derived(transcriptChecked.filter(Boolean).length);

  async function suggestFromTranscript() {
    const target = refsUrl.trim();
    if (!target || transcriptLoading) return;
    transcriptError = null;
    transcriptInfo = null;
    transcriptSuggestions = [];
    transcriptChecked = [];
    transcriptLoading = true;
    try {
      const res = await api.imports.youtubeTranscript(target);
      if (!res.available) {
        transcriptInfo = 'Aucun sous-titre exploitable sur cette vidéo.';
      } else if (res.suggestions.length === 0) {
        transcriptInfo = 'Aucun travail nommé à l’oral n’a été repéré dans la transcription.';
      } else {
        transcriptSuggestions = res.suggestions;
        transcriptChecked = res.suggestions.map(() => false);
      }
    } catch (err) {
      transcriptError = err instanceof Error ? err.message : 'Erreur lors de la transcription';
    } finally {
      transcriptLoading = false;
    }
  }

  async function addCheckedSuggestions() {
    const picked = transcriptSuggestions.filter((_, i) => transcriptChecked[i]);
    if (picked.length === 0) return;
    await ingestImported({ sources: picked, skipped: 0 });
    transcriptSuggestions = [];
    transcriptChecked = [];
    transcriptInfo = `${picked.length} suggestion${picked.length > 1 ? 's' : ''} ajoutée${picked.length > 1 ? 's' : ''} aux brouillons.`;
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
          class="flex-1 min-w-0 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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

      {#if isYoutubeTarget}
        <div class="mt-4 rounded-lg border border-border bg-surface-secondary/50 px-4 py-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="text-sm text-ink-primary">Travaux cités à l’oral</p>
              <p class="text-xs text-ink-tertiary mt-0.5">
                Lit les sous-titres de la vidéo pour repérer les études et livres nommés à l’oral.
                La transcription est automatique et donc imprécise : ces suggestions sont à vérifier
                une par une, elles ne sont jamais ajoutées d’office.
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              loading={transcriptLoading}
              disabled={transcriptLoading}
              onclick={suggestFromTranscript}
            >
              {transcriptLoading ? 'Lecture…' : 'Analyser la transcription'}
            </Button>
          </div>

          {#if transcriptError}
            <p class="mt-3 text-sm text-danger">{transcriptError}</p>
          {/if}
          {#if transcriptInfo}
            <p class="mt-3 text-sm text-ink-secondary">{transcriptInfo}</p>
          {/if}

          {#if transcriptSuggestions.length > 0}
            <ul class="mt-3 space-y-2">
              {#each transcriptSuggestions as suggestion, i (suggestion.url + suggestion.title + i)}
                <li>
                  <label class="flex items-start gap-2 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      bind:checked={transcriptChecked[i]}
                      class="mt-0.5 rounded border-border-strong text-info focus:ring-info"
                    />
                    <span class="min-w-0">
                      <span class="text-ink-primary">{suggestion.title}</span>
                      {#if suggestion.authors || suggestion.published_at}
                        <span class="text-ink-tertiary">
                          , {suggestion.authors ?? ''}{suggestion.authors && suggestion.published_at
                            ? ', '
                            : ''}{suggestion.published_at?.slice(0, 4) ?? ''}
                        </span>
                      {/if}
                    </span>
                  </label>
                </li>
              {/each}
            </ul>
            <div class="mt-3">
              <Button
                type="button"
                variant="secondary"
                disabled={transcriptCheckedCount === 0}
                onclick={addCheckedSuggestions}
              >
                Ajouter {transcriptCheckedCount} suggestion{transcriptCheckedCount > 1 ? 's' : ''}
              </Button>
            </div>
          {/if}
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

  <!-- Ajout en lot : coller ou importer -->
  {#if !isEditing}
    <div class="bg-surface-primary border border-border rounded-xl p-6 mb-6">
      <h2 class="text-lg font-semibold text-ink-primary mb-4">Ajouter des sources</h2>

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
            placeholder={'Une liste de liens :\nhttps://doi.org/10.1038/s41586-020-2649-2\nhttps://www.lemonde.fr/...\n\nOU une bibliographie complète collée depuis un article, Zotero, un PDF… :\nWolfe, C. D., & Bell, M. A. (2007). The integration of cognition and emotion during infancy and early childhood: regulatory processes associated with the development of working memory. Brain and Cognition, 65(1), 3–13. https://doi.org/10.1016/j.bandc.2006.01.009\nDupont, J., & Martin, A. (2020). Titre. Journal, 12(3), 45-67.'}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder font-mono text-sm resize-y min-h-[8rem]"
          ></textarea>
        </div>
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <input
              type="file"
              accept=".bib,.bibtex,.ris,.nbib,.enw,.json,.md,.markdown,.pdf,.docx,.html,.htm"
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
              BibTeX, CSL-JSON (Zotero), Markdown (Obsidian), PDF, Word ou page HTML, 5 Mo max
            </p>
          </div>
          <div class="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              loading={analyzingText}
              disabled={analyzingText || multiExtracting || !multiText.trim()}
              onclick={analyzeText}
              title="L'IA découpe une bibliographie collée en références structurées (fonctionne même sans liens ni DOIs)"
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
            <!--
              En tete de liste, et pas seulement en pied : sur une fiche de 131
              references, chaque brouillon est un formulaire deplie, et « Tout
              ajouter » se trouvait au bout du plus long defilement de
              l'application. L'action la plus courante doit etre la plus proche.
            -->
            <div
              class="flex items-center justify-between gap-3 rounded-lg bg-surface-secondary/50 border border-border px-4 py-3"
            >
              <p class="text-sm text-ink-secondary">
                {drafts.length} référence{drafts.length > 1 ? 's' : ''} à valider, relisez-les ou ajoutez
                tout d'un coup.
              </p>
              <Button
                type="button"
                loading={addingAll}
                disabled={addingAll || multiExtracting}
                onclick={addAllDrafts}
              >
                {addingAll ? 'Ajout en cours…' : `Tout ajouter (${drafts.length})`}
              </Button>
            </div>
            {#each drafts as draft, i (draft.key)}
              <div class="border border-border rounded-lg p-4 space-y-3 bg-surface-secondary/50">
                <div class="flex items-start justify-between gap-2">
                  <p class="text-xs text-ink-tertiary font-mono truncate min-w-0">
                    {draft.url || '(sans URL : livre, chapitre ou ref sans DOI)'}
                  </p>
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
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder disabled:opacity-60"
                  />
                  <input
                    type="text"
                    bind:value={draft.authors}
                    placeholder="Auteurs"
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder disabled:opacity-60"
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
                  <input
                    type="date"
                    bind:value={draft.published_at}
                    placeholder="Date de publication"
                    disabled={draft.status === 'extracting'}
                    class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info disabled:opacity-60"
                    title="Date de publication (par les auteurs originaux)"
                  />
                </div>

                <div class="sm:col-span-2">
                  <button
                    type="button"
                    onclick={() => (draft.extraMetaOpen = !draft.extraMetaOpen)}
                    class="flex items-center gap-1.5 text-xs font-medium text-ink-secondary hover:text-ink-primary transition-colors"
                    aria-expanded={draft.extraMetaOpen}
                  >
                    <svg
                      viewBox="0 0 24 24"
                      class="w-3.5 h-3.5 transition-transform {draft.extraMetaOpen
                        ? 'rotate-180'
                        : ''}"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                    Métadonnées étendues (journal, volume, pages, DOI, éditeur)
                  </button>
                  {#if draft.extraMetaOpen}
                    <div class="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <input
                        type="text"
                        bind:value={draft.journal}
                        placeholder="Journal / revue"
                        class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder sm:col-span-2"
                      />
                      <input
                        type="text"
                        bind:value={draft.volume}
                        placeholder="Volume"
                        class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
                      />
                      <input
                        type="text"
                        bind:value={draft.pages}
                        placeholder="Pages (ex. 123-145)"
                        class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
                      />
                      <input
                        type="text"
                        bind:value={draft.publisher}
                        placeholder="Éditeur"
                        class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
                      />
                      <input
                        type="text"
                        bind:value={draft.doi}
                        placeholder="DOI"
                        class="w-full px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder font-mono"
                      />
                    </div>
                  {/if}
                </div>

                <div class="flex justify-end">
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
    </div>
  {/if}

  <!-- Ajout ou modification d'une source unique -->
  <div
    class="bg-surface-primary border rounded-xl p-6 mb-6 {isEditing
      ? 'border-info/50 ring-1 ring-info/30'
      : 'border-border'}"
  >
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-ink-primary">
        {isEditing ? 'Modifier la source' : 'Ajouter une source à la fois'}
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
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder read-only:bg-surface-tertiary read-only:text-ink-tertiary read-only:cursor-not-allowed"
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
              <span class="text-xs text-info font-normal">(suggéré)</span>
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
              <span class="text-xs text-info font-normal">(suggéré)</span>
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
              <span class="text-xs text-info font-normal">(suggéré)</span>
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
            <span class="text-xs text-ink-tertiary font-normal">, par les auteurs originaux</span>
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder resize-y min-h-[3rem]"
          ></textarea>
        </div>

        <div class="sm:col-span-2 space-y-1.5">
          <span class="block text-sm font-medium text-ink-secondary">
            Rapport au propos <span class="text-ink-tertiary font-normal">(optionnel)</span>
            <span class="text-xs text-ink-tertiary font-normal block mt-0.5">
              Vous seul pouvez le dire : Philum ne le devine pas. Laisser vide si vous ne souhaitez
              pas vous prononcer.
            </span>
          </span>
          <div class="flex flex-wrap gap-2">
            <button
              type="button"
              onclick={() => (stance = '')}
              aria-pressed={stance === ''}
              class="px-3 py-1.5 text-sm rounded-full border transition-colors {stance === ''
                ? 'border-ink-primary bg-surface-secondary text-ink-primary'
                : 'border-border text-ink-tertiary hover:border-border-strong'}"
            >
              Non déclaré
            </button>
            {#each STANCE_ORDER as key (key)}
              <button
                type="button"
                onclick={() => (stance = key)}
                aria-pressed={stance === key}
                title={STANCE_STYLES[key].help}
                class="px-3 py-1.5 text-sm rounded-full border transition-colors {stance === key
                  ? 'border-transparent ' + STANCE_STYLES[key].bgClass
                  : 'border-border text-ink-tertiary hover:border-border-strong'}"
              >
                {STANCE_STYLES[key].label}
              </button>
            {/each}
          </div>
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder font-mono text-sm"
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
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder font-mono text-sm"
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
          <div class="sm:col-span-2">
            <button
              type="button"
              onclick={() => (parentLinkOpen = !parentLinkOpen)}
              class="flex items-center gap-1.5 text-sm font-medium text-ink-secondary hover:text-ink-primary transition-colors"
              aria-expanded={parentLinkOpen}
              aria-controls="source-parent-link"
            >
              <svg
                viewBox="0 0 24 24"
                class="w-4 h-4 transition-transform {parentLinkOpen ? 'rotate-180' : ''}"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
              Cette source en cite une autre de cette même fiche ?
            </button>
            {#if parentLinkOpen}
              <div id="source-parent-link" class="mt-3 space-y-1.5">
                <p class="text-xs text-ink-tertiary">
                  Déclare que cette source cite l'une des autres sources de la fiche. Le graphe
                  relie alors les deux par un trait en pointillés : la chaîne de citations entre vos
                  propres références devient visible.
                </p>
                <label for="source-parent" class="sr-only">Source citée par celle-ci</label>
                <input
                  type="search"
                  bind:value={parentSourceQuery}
                  placeholder="Filtrer les sources de cette fiche (numéro, titre, URL)…"
                  aria-label="Rechercher parmi les sources de cette fiche"
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
                />
                <select
                  id="source-parent"
                  bind:value={parentSourceId}
                  size={numberedSources.length > 8 ? 8 : undefined}
                  class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
                >
                  <option value="">(Aucun lien parent)</option>
                  {#each numberedSources as { source: s, number } (s.id)}
                    <option value={s.id}>{number}. {s.title ?? s.url}</option>
                  {/each}
                </select>
                {#if parentSourceQuery.trim() && numberedSources.length === 0}
                  <p class="text-xs text-ink-tertiary">Aucune source ne correspond à ce filtre.</p>
                {/if}
              </div>
            {/if}
          </div>
        {/if}

        <!--
            Méta-fiches : liste déroulante distincte, avec sa propre recherche.
            Le périmètre serveur est « mes fiches + toutes les fiches publiques »,
            donc trop large pour être chargé d'avance : la recherche est requise.
          -->
        <div class="sm:col-span-2 space-y-1.5">
          <label for="linked-card-search" class="block text-sm font-medium text-ink-secondary">
            Ce contenu source a-t-il déjà sa fiche Philum ?
            <span class="text-xs text-ink-tertiary font-normal">
              : la source devient un nœud dépliable du graphe, et les deux fiches se relient dans la
              constellation</span
            >
          </label>

          {#if linkedCardId}
            <div
              class="flex items-center justify-between gap-2 px-4 py-2 rounded-lg border border-info/40 bg-info/5"
            >
              <span class="text-sm text-ink-primary truncate">
                {linkedCardSelected?.title ?? 'Fiche sélectionnée'}
                {#if linkedCardSelected && !linkedCardSelected.is_own}
                  <span class="text-xs text-ink-tertiary">, @{linkedCardSelected.creator_slug}</span
                  >
                {/if}
              </span>
              <button
                type="button"
                onclick={clearLinkedCard}
                class="text-xs text-ink-tertiary hover:text-danger shrink-0"
              >
                Retirer
              </button>
            </div>
          {:else}
            <input
              id="linked-card-search"
              type="search"
              bind:value={linkedCardQuery}
              oninput={onLinkedCardQueryInput}
              onfocus={() => {
                if (linkedCardResults.length === 0) void searchLinkedCards();
              }}
              placeholder="Rechercher une fiche par titre…"
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info"
            />
            {#if linkedCardLoading}
              <p class="text-xs text-ink-tertiary">Recherche…</p>
            {:else if linkedCardResults.length > 0}
              <ul
                class="max-h-56 overflow-y-auto rounded-lg border border-border divide-y divide-border"
              >
                {#each linkedCardResults as result (result.id)}
                  <li>
                    <button
                      type="button"
                      onclick={() => pickLinkedCard(result)}
                      class="w-full text-left px-3 py-2 text-sm text-ink-primary hover:bg-surface-secondary"
                    >
                      <span class="block truncate">{result.title}</span>
                      <span class="block text-xs text-ink-tertiary">
                        {result.is_own ? 'Ma fiche' : `@${result.creator_slug}`}
                        {#if result.status !== 'published'}· brouillon{/if}
                      </span>
                    </button>
                  </li>
                {/each}
              </ul>
            {:else if linkedCardQuery.trim()}
              <p class="text-xs text-ink-tertiary">Aucune fiche ne correspond.</p>
            {/if}
          {/if}
        </div>
      </div>

      {#if isEditing && editingSource}
        <div class="border-t border-border pt-4 space-y-3">
          <div class="flex items-center justify-between gap-2 flex-wrap">
            <h3 class="text-sm font-semibold text-ink-primary">
              Citations
              <span class="text-xs text-ink-tertiary font-normal">
                : extraits marquants de cette source (max 10)</span
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
              class="flex-1 px-3 py-1.5 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-none focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
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

      {#if archivableSources.length > 0}
        <div
          class="flex flex-wrap items-center gap-3 mb-3 rounded-lg border border-border bg-surface-secondary px-4 py-2.5"
        >
          <label class="flex items-center gap-2 text-sm text-ink-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={selectedCount === archivableSources.length}
              indeterminate={selectedCount > 0 && selectedCount < archivableSources.length}
              onchange={toggleAllArchiveSelection}
              class="w-4 h-4 rounded border-border text-info focus:ring-info/40"
            />
            Tout sélectionner ({archivableSources.length} archivable{archivableSources.length > 1
              ? 's'
              : ''})
          </label>
          <Button
            variant="secondary"
            disabled={selectedCount === 0 || archiving}
            onclick={() => archiveSources([...selectedForArchive])}
          >
            {archiving ? 'Envoi…' : `Archiver la sélection (${selectedCount})`}
          </Button>
          <p class="text-xs text-ink-tertiary">
            L'archivage automatique passe sur toutes les sources, mais à cadence lente. Ceci désigne
            ce qui presse.
          </p>
        </div>
      {/if}

      {#if archiveMessage}
        <p class="mb-3 rounded-lg bg-info-bg border border-info/30 px-4 py-2.5 text-sm text-info">
          {archiveMessage}
        </p>
      {/if}

      <div class="space-y-2">
        {#each sources as source, sourceIndex (source.id)}
          {@const color = AUTHOR_COLORS[source.author_kind]}
          {@const isThisEditing = editingSourceId === source.id}
          {@const archivable = isArchivable(source)}
          <div
            class="flex items-start justify-between gap-3 bg-surface-primary border rounded-lg px-4 py-3 transition-colors {isThisEditing
              ? 'border-info/50 ring-1 ring-info/30'
              : 'border-border'}"
          >
            <div class="flex items-start gap-3 min-w-0">
              {#if archivableSources.length > 0}
                <input
                  type="checkbox"
                  checked={selectedForArchive.has(source.id)}
                  disabled={!archivable}
                  onchange={() => toggleArchiveSelection(source.id)}
                  class="mt-1 shrink-0 w-4 h-4 rounded border-border text-info focus:ring-info/40 disabled:opacity-30"
                  aria-label="Sélectionner pour l'archivage"
                  title={archivable
                    ? "Sélectionner pour l'archivage"
                    : source.archive_status === 'archived'
                      ? 'Déjà archivée'
                      : 'Sans URL : rien à archiver'}
                />
              {/if}
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
                {#if source.linked_card_id}
                  <p class="text-xs text-info truncate">★ reliée à une fiche Philum</p>
                {/if}
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              {#if archivable}
                <button
                  type="button"
                  onclick={() => archiveSources([source.id])}
                  disabled={archiving}
                  class="p-1.5 text-ink-tertiary hover:text-info disabled:opacity-40 disabled:cursor-default transition-colors"
                  aria-label="Archiver cette source maintenant"
                  title="Archiver cette source maintenant"
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
                    <rect x="3" y="4" width="18" height="4" rx="1" />
                    <path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8" />
                    <line x1="10" y1="12" x2="14" y2="12" />
                  </svg>
                </button>
              {/if}
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
