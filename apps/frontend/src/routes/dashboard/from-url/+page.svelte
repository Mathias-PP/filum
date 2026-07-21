<script lang="ts">
  import { goto } from '$app/navigation';
  import { onDestroy } from 'svelte';
  import { api, ApiError } from '$lib/api';
  import { Button, ProgressSteps, toast } from '$lib/components';
  import { currentUser } from '$lib/stores/auth';
  import type { ContentType, ImportFromUrlResponse, ImportedSourceDraft, Platform } from '$lib/api';

  // Étape 1 : URL saisie → appel /import/from-content-url → preview.
  // Étape 2 : preview éditable (titre, description, sources cochées) → création
  //           en base : POST /cards puis N × POST /sources → redirection vers
  //           /dashboard/new/{card_id}/sources.

  const steps = [
    { label: 'URL', description: 'Coller le lien' },
    { label: 'Aperçu', description: 'Vérifier et créer' },
  ];

  let url = $state('');
  let analyzing = $state(false);
  let analyzeError = $state<string | null>(null);
  let result = $state<ImportFromUrlResponse | null>(null);

  // Preview éditable
  let title = $state('');
  let description = $state('');
  let contentUrl = $state('');
  let platform = $state<Platform>('other');
  let contentType = $state<ContentType>('other');
  let slug = $state('');
  let slugManual = $state(false);
  // Par défaut coché sur /from-url : l'utilisateur crée souvent des fiches
  // depuis une URL trouvée sur le web sans être l'auteur du contenu.
  let isSeed = $state(true);
  // Un booléen par index — les sources sont cochées par défaut.
  let selected = $state<boolean[]>([]);
  let sources = $state<ImportedSourceDraft[]>([]);

  let creating = $state(false);
  let createError = $state<string | null>(null);
  // Progression pendant la création séquentielle des sources.
  let createProgress = $state<{ done: number; total: number } | null>(null);

  const platforms: { value: Platform; label: string }[] = [
    { value: 'youtube', label: 'YouTube' },
    { value: 'podcast', label: 'Podcast' },
    { value: 'blog', label: 'Blog' },
    { value: 'x', label: 'X (Twitter)' },
    { value: 'bluesky', label: 'Bluesky' },
    { value: 'other', label: 'Autre' },
  ];

  const contentTypes: { value: ContentType; label: string }[] = [
    { value: 'video', label: 'Vidéo' },
    { value: 'article', label: 'Article' },
    { value: 'post', label: 'Post' },
    { value: 'podcast', label: 'Podcast' },
    { value: 'other', label: 'Autre' },
  ];

  function deriveSlug(v: string) {
    return v
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60);
  }

  function guessPlatform(u: string): { platform: Platform; contentType: ContentType } {
    let host = '';
    try {
      host = new URL(u).hostname.replace(/^www\./, '').toLowerCase();
    } catch {
      return { platform: 'other', contentType: 'article' };
    }
    if (host.includes('youtube.com') || host === 'youtu.be')
      return { platform: 'youtube', contentType: 'video' };
    if (host.includes('twitter.com') || host === 'x.com')
      return { platform: 'x', contentType: 'post' };
    if (host.includes('bsky.app')) return { platform: 'bluesky', contentType: 'post' };
    if (host.includes('substack.com') || host.includes('medium.com'))
      return { platform: 'blog', contentType: 'article' };
    return { platform: 'other', contentType: 'article' };
  }

  function onTitleInput(e: Event) {
    title = (e.target as HTMLInputElement).value;
    if (!slugManual) slug = deriveSlug(title);
  }

  function onSlugInput(e: Event) {
    slugManual = true;
    slug = (e.target as HTMLInputElement).value;
  }

  async function analyze(e: Event) {
    e.preventDefault();
    analyzeError = null;
    const trimmed = url.trim();
    if (!trimmed) return;
    // Validation basique — le backend a la validation robuste (SSRF, schéma).
    try {
      new URL(trimmed);
    } catch {
      analyzeError = 'URL invalide. Elle doit commencer par https:// ou http://';
      return;
    }
    analyzing = true;
    try {
      const res = await api.imports.fromContentUrl(trimmed);
      result = res;
      // Préremplissage éditable.
      title = res.card.title ?? '';
      description = res.card.description ?? '';
      contentUrl = res.card.content_url;
      // Slug uniquement si on a un titre — deriveSlug(URL) produit un slug
      // moche du genre `https-www-frontiersin-org-…`, mieux vaut vide.
      slug = title ? deriveSlug(title) : '';
      slugManual = false;
      const guess = guessPlatform(res.card.content_url);
      platform = guess.platform;
      contentType = guess.contentType;
      sources = res.sources;
      selected = res.sources.map(() => true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) analyzeError = 'Veuillez vous connecter.';
        else if (err.status === 422) analyzeError = err.message || 'URL non acceptée.';
        else if (err.status === 429)
          analyzeError = 'Trop de requêtes en peu de temps. Réessayez dans une minute.';
        else analyzeError = err.message || "Impossible d'analyser cette URL.";
      } else {
        analyzeError = err instanceof Error ? err.message : "Erreur lors de l'analyse";
      }
    } finally {
      analyzing = false;
    }
  }

  function toggleAll(v: boolean) {
    selected = selected.map(() => v);
  }

  const selectedCount = $derived(selected.filter(Boolean).length);
  // Nombre de sources qui seront REELLEMENT envoyees (selectionnees + URL non vide)
  const selectedWithUrl = $derived(
    sources.filter((s, i) => selected[i] && s.url && s.url.trim().length > 0).length
  );
  const selectedWithoutUrl = $derived(selectedCount - selectedWithUrl);
  // Refs extraites sans URL (draft éditable, indépendamment de la sélection).
  const sourcesWithoutUrl = $derived(sources.filter((s) => !s.url || !s.url.trim()).length);

  async function createCard(e: Event) {
    e.preventDefault();
    createError = null;
    if (!title.trim() || !slug.trim()) {
      createError = 'Le titre et le slug sont obligatoires.';
      return;
    }
    creating = true;
    try {
      const card = await api.cards.create({
        title: title.trim(),
        slug: slug.trim(),
        description: description.trim() || undefined,
        content_url: contentUrl.trim() || undefined,
        platform,
        content_type: contentType,
        is_seed: isSeed,
      });
      // Sources sélectionnées avec URL renseignée (les refs sans URL restantes
      // sont ignorées silencieusement — l'utilisateur a été prévenu dans la UI).
      const toCreate = sources
        .filter((_, i) => selected[i])
        .filter((s) => s.url && s.url.trim().length > 0);
      const skippedNoUrl = sources.filter((_, i) => selected[i]).length - toCreate.length;

      if (toCreate.length > 0) {
        createProgress = { done: 0, total: toCreate.length };
        // Batch endpoint : 1 requête pour N sources, atomique, envoie
        // title/authors/published_at/category sans risque de perte partielle.
        try {
          const batch = await api.sources.createBatch(
            card.id,
            toCreate.map((s) => ({
              url: s.url,
              title: s.title ?? undefined,
              authors: s.authors ?? undefined,
              published_at: s.published_at ?? undefined,
              format: s.format,
              category: s.category,
              author_kind: s.author_kind,
            }))
          );
          createProgress = { done: toCreate.length, total: toCreate.length };
          const ok = batch.created.length;
          const failed = batch.failed.length;
          const parts = [`${ok} source${ok > 1 ? 's' : ''} ajoutée${ok > 1 ? 's' : ''}`];
          if (failed > 0) parts.push(`${failed} en erreur`);
          if (skippedNoUrl > 0)
            parts.push(`${skippedNoUrl} sans URL ignorée${skippedNoUrl > 1 ? 's' : ''}`);
          if (failed > 0 || skippedNoUrl > 0) {
            toast.danger(parts.join(', ') + '.');
          } else {
            toast.success(parts.join(', ') + '.');
          }
        } catch (err) {
          toast.danger(
            err instanceof Error
              ? `Batch échoué : ${err.message}. Fiche créée sans sources.`
              : 'Batch échoué. Fiche créée sans sources.'
          );
        }
      } else if (skippedNoUrl > 0) {
        toast.danger(
          `${skippedNoUrl} source${skippedNoUrl > 1 ? 's' : ''} sans URL ignorée${skippedNoUrl > 1 ? 's' : ''}. Renseignez les URLs pour les inclure.`
        );
      }
      goto(`/dashboard/new/${card.id}/sources`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        createError = `Ce slug est déjà utilisé. Choisissez-en un autre.`;
      } else {
        createError = err instanceof Error ? err.message : 'Erreur lors de la création';
      }
    } finally {
      creating = false;
      createProgress = null;
    }
  }

  // Avertissement navigateur si l'utilisateur essaie de fermer/rafraichir
  // pendant la création séquentielle des sources (F5 = fiche créée mais
  // moitié des sources manquantes).
  function beforeUnloadHandler(e: BeforeUnloadEvent) {
    if (creating && createProgress && createProgress.done < createProgress.total) {
      e.preventDefault();
      // Chrome ignore la string mais respecte le preventDefault + returnValue.
      e.returnValue = '';
    }
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', beforeUnloadHandler);
    onDestroy(() => window.removeEventListener('beforeunload', beforeUnloadHandler));
  }

  function reset() {
    result = null;
    sources = [];
    selected = [];
    title = '';
    description = '';
    contentUrl = '';
    slug = '';
    slugManual = false;
    analyzeError = null;
    createError = null;
  }
</script>

<svelte:head>
  <title>Fiche depuis une URL — Philum</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors">
      ← Tableau de bord
    </a>
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-2">Créer une fiche depuis une URL</h1>
  <p class="text-sm text-ink-secondary mb-6">
    Collez le lien d'un article, un billet ou une page contenant une bibliographie. Philum extrait
    automatiquement le titre du contenu et les sources qu'il cite.
  </p>

  <ProgressSteps {steps} current={result ? 1 : 0} class="mb-8" />

  {#if !result}
    <form onsubmit={analyze} class="space-y-4">
      {#if analyzeError}
        <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
          {analyzeError}
        </div>
      {/if}

      <div class="space-y-1.5">
        <label for="src-url" class="block text-sm font-medium text-ink-secondary">
          URL du contenu <span class="text-danger">*</span>
        </label>
        <input
          id="src-url"
          type="url"
          bind:value={url}
          required
          placeholder="https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2018.01561/full"
          class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary font-mono text-sm"
        />
        <p class="text-xs text-ink-tertiary">
          Fonctionne mieux sur les pages avec une section « References » (articles scientifiques,
          billets de blog avec bibliographie).
        </p>
      </div>

      <div class="flex justify-end pt-2">
        <Button type="submit" loading={analyzing} disabled={analyzing || !url.trim()}>
          {analyzing ? 'Analyse…' : 'Analyser'}
        </Button>
      </div>
    </form>
  {:else}
    <form onsubmit={createCard} class="space-y-6">
      {#if createError}
        <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
          {createError}
        </div>
      {/if}

      <!-- Bandeau info sur l'extraction (statut fetch + statut sources) -->
      {#if result.fetch_status === 'unreachable'}
        <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
          ⚠ Page injoignable (timeout, erreur HTTP, ou blocage anti-bot). Vous pouvez quand même
          créer la fiche vide et ajouter les sources à la main.
        </div>
      {:else if result.fetch_status === 'not_html'}
        <div class="rounded-lg bg-info/10 border border-info/30 px-4 py-3 text-sm text-info">
          ⓘ Ce n'est pas une page HTML (PDF, image, API JSON…). Aucune bibliographie extraite ; la
          fiche sera créée avec cette URL comme contenu, à vous d'ajouter les sources.
        </div>
      {:else}
        <div
          class="rounded-lg px-4 py-3 text-sm border {result.references_section_found
            ? 'bg-success-bg border-success/30 text-success'
            : 'bg-info/10 border-info/30 text-info'}"
        >
          {#if result.references_section_found}
            ✓ Section « References » détectée sur la page.
          {:else}
            ⚠ Aucune section de références isolée — l'IA a analysé la page entière. Vérifiez les
            sources extraites.
          {/if}
          {sources.length} source{sources.length > 1 ? 's' : ''} extraite{sources.length > 1
            ? 's'
            : ''}{#if sourcesWithoutUrl > 0}, dont {sourcesWithoutUrl} sans URL à compléter à la main{/if}{#if result.skipped > 0}.
            {result.skipped} référence{result.skipped > 1 ? 's' : ''} sans metadata utile ignorée{result.skipped >
            1
              ? 's'
              : ''}{/if}.
        </div>
      {/if}

      <!-- Preview éditable de la fiche -->
      <fieldset class="space-y-4">
        <legend class="text-xs font-medium uppercase tracking-wider text-ink-tertiary mb-2">
          Fiche
        </legend>

        <div class="space-y-1.5">
          <label for="preview-title" class="block text-sm font-medium text-ink-secondary">
            Titre du contenu <span class="text-danger">*</span>
          </label>
          <input
            id="preview-title"
            type="text"
            value={title}
            oninput={onTitleInput}
            required
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info"
          />
        </div>

        <div class="space-y-1.5">
          <label for="preview-slug" class="block text-sm font-medium text-ink-secondary">
            Identifiant URL <span class="text-danger">*</span>
          </label>
          <div class="flex items-center gap-2">
            <span class="text-ink-tertiary text-sm shrink-0"
              >/@{$currentUser?.username ?? 'vous'}/</span
            >
            <input
              id="preview-slug"
              type="text"
              value={slug}
              oninput={onSlugInput}
              required
              pattern="[a-z0-9-]+"
              class="flex-1 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info"
            />
          </div>
        </div>

        <div class="space-y-1.5">
          <label for="preview-desc" class="block text-sm font-medium text-ink-secondary">
            Description
          </label>
          <textarea
            id="preview-desc"
            value={description}
            oninput={(e) => (description = (e.target as HTMLTextAreaElement).value)}
            rows={3}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info resize-none"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label for="preview-platform" class="block text-sm font-medium text-ink-secondary">
              Plateforme
            </label>
            <select
              id="preview-platform"
              value={platform}
              onchange={(e) => (platform = (e.target as HTMLSelectElement).value as Platform)}
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
            >
              {#each platforms as p (p.value)}
                <option value={p.value}>{p.label}</option>
              {/each}
            </select>
          </div>
          <div class="space-y-1.5">
            <label for="preview-ct" class="block text-sm font-medium text-ink-secondary">
              Type de contenu
            </label>
            <select
              id="preview-ct"
              value={contentType}
              onchange={(e) => (contentType = (e.target as HTMLSelectElement).value as ContentType)}
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info"
            >
              {#each contentTypes as ct (ct.value)}
                <option value={ct.value}>{ct.label}</option>
              {/each}
            </select>
          </div>
        </div>

        <label class="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            bind:checked={isSeed}
            class="mt-0.5 shrink-0"
            aria-describedby="seed-hint-from-url"
          />
          <span class="text-sm">
            <span class="font-medium text-ink-primary">
              Je ne suis pas l'auteur·ice de ce contenu
            </span>
            <span id="seed-hint-from-url" class="block text-xs text-ink-tertiary mt-0.5">
              Coché par défaut ici : quand on colle l'URL d'un article/vidéo trouvé sur le web,
              c'est en général pour référencer le travail de quelqu'un d'autre. L'auteur·ice pourra
              revendiquer la fiche depuis sa page publique.
            </span>
          </span>
        </label>
      </fieldset>

      <!-- Sources extraites -->
      <fieldset class="space-y-3">
        <div class="flex items-center justify-between gap-3 flex-wrap">
          <legend class="text-xs font-medium uppercase tracking-wider text-ink-tertiary">
            Sources extraites ({selectedCount}/{sources.length} sélectionnée{selectedCount > 1
              ? 's'
              : ''})
          </legend>
          {#if sources.length > 0}
            <div class="flex gap-2 text-xs">
              <button
                type="button"
                class="text-info hover:underline"
                onclick={() => toggleAll(true)}
              >
                Tout cocher
              </button>
              <span class="text-ink-tertiary">·</span>
              <button
                type="button"
                class="text-ink-tertiary hover:underline"
                onclick={() => toggleAll(false)}
              >
                Tout décocher
              </button>
            </div>
          {/if}
        </div>

        {#if sources.length === 0}
          <div
            class="rounded-lg bg-surface-secondary border border-border px-4 py-3 text-sm text-ink-secondary space-y-1"
          >
            <p class="font-medium text-ink-primary">Aucune source détectée sur cette page.</p>
            <p class="text-xs">
              Cas typiques : vidéo/podcast/post social sans description structurée, article sans
              bibliographie citée, page bloquée par un anti-bot. Vous pouvez quand même créer la
              fiche et ajouter les sources à la main à l'étape suivante.
            </p>
          </div>
        {:else}
          <ul class="space-y-2">
            {#each sources as src, i (i)}
              {@const hasUrl = src.url && src.url.trim().length > 0}
              <li
                class="rounded-lg border {hasUrl
                  ? 'border-border bg-surface-secondary/40'
                  : 'border-warning/40 bg-warning-bg/40'} p-3 flex items-start gap-3"
              >
                <input
                  type="checkbox"
                  id="src-{i}"
                  bind:checked={selected[i]}
                  class="mt-1 shrink-0"
                  aria-label="Inclure cette source"
                />
                <div class="flex-1 min-w-0">
                  <span
                    class="inline-flex items-center text-[0.65rem] font-mono text-ink-tertiary mr-2"
                  >
                    #{i + 1}
                  </span>
                  {#if hasUrl}
                    <label for="src-{i}" class="cursor-pointer">
                      <p class="inline text-xs text-ink-tertiary font-mono truncate">
                        {src.url}
                      </p>
                    </label>
                  {:else}
                    <input
                      type="url"
                      bind:value={sources[i].url}
                      placeholder="URL de cette référence (ISBN, WorldCat, éditeur…)"
                      class="mt-1 w-full text-xs font-mono px-2 py-1 rounded border border-warning/60 bg-surface-primary text-ink-primary focus:outline-none focus:ring-1 focus:ring-warning"
                      aria-label="Renseigner l'URL manquante"
                    />
                    <p class="text-[0.65rem] text-warning mt-0.5">
                      Cette référence n'a pas d'URL/DOI extractible. Renseignez-en une pour
                      l'inclure, ou décochez.
                    </p>
                  {/if}
                  {#if src.title}
                    <p class="text-sm font-medium text-ink-primary mt-1">{src.title}</p>
                  {/if}
                  {#if src.authors}
                    <p class="text-xs text-ink-secondary mt-0.5">{src.authors}</p>
                  {/if}
                  <p class="text-[0.65rem] text-ink-tertiary uppercase tracking-wider mt-1">
                    {src.category} · {src.author_kind}
                  </p>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </fieldset>

      <div class="flex justify-between pt-4 gap-3">
        <Button type="button" variant="ghost" onclick={reset} disabled={creating}>
          ← Autre URL
        </Button>
        <Button type="submit" loading={creating} disabled={creating || !title.trim() || !slug}>
          {#if creating && createProgress}
            Ajout des sources : {createProgress.done} / {createProgress.total}…
          {:else if creating}
            Création de la fiche…
          {:else if selectedWithUrl > 0}
            Créer la fiche ({selectedWithUrl} source{selectedWithUrl > 1 ? 's' : ''})
          {:else}
            Créer la fiche sans source
          {/if}
        </Button>
      </div>
      {#if selectedWithoutUrl > 0 && !creating}
        <p class="text-xs text-warning text-right">
          ⚠ {selectedWithoutUrl} source{selectedWithoutUrl > 1 ? 's' : ''} sélectionnée{selectedWithoutUrl >
          1
            ? 's'
            : ''} sans URL — ignorée{selectedWithoutUrl > 1 ? 's' : ''} à la création. Renseignez l'URL
          manquante ou décochez.
        </p>
      {/if}
      {#if creating && createProgress && createProgress.total > 3}
        <p class="text-xs text-ink-tertiary text-right">
          Ne fermez pas la page — l'archivage Wayback est déclenché en arrière-plan.
        </p>
      {/if}
    </form>
  {/if}
</div>
