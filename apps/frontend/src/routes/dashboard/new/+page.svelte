<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
  import { currentUser } from '$lib/stores/auth';
  import { pendingImportFile } from '$lib/stores/import-file';
  import type { Platform, ContentType, Visibility } from '$lib/api';

  // Mode édition : /dashboard/new?card_id=<id> pré-remplit le formulaire
  // depuis la fiche existante et le submit fait un PATCH au lieu d'un POST.
  const editCardId = $derived($page.url.searchParams.get('card_id'));

  const steps = $derived([
    { label: 'Informations', description: 'Titre, plateforme' },
    { label: 'Sources', description: 'Ajouter et publier', clickable: Boolean(editCardId) },
  ]);

  let title = $state('');
  let slug = $state('');
  let description = $state('');
  let contentUrl = $state('');
  let platform = $state<Platform>('other');
  let contentType = $state<ContentType>('other');
  let isAuthor = $state(false);
  let visibility = $state<Visibility>('public');
  let error = $state<string | null>(null);
  let loading = $state(false);
  let loadingCard = $state(false);

  $effect(() => {
    if (editCardId) loadCard(editCardId);
  });

  async function loadCard(cardId: string) {
    loadingCard = true;
    error = null;
    try {
      const card = await api.cards.get(cardId);
      title = card.title;
      slug = card.slug;
      slugManual = true;
      description = card.description ?? '';
      contentUrl = card.content_url ?? '';
      lastSuggestedUrl = contentUrl;
      platform = card.platform;
      contentType = card.content_type;
      isAuthor = !card.is_seed;
      visibility = card.visibility;
    } catch (err) {
      error = err instanceof Error ? err.message : 'Impossible de charger la fiche';
    } finally {
      loadingCard = false;
    }
  }

  // Suggestion automatique des métadonnées depuis l'URL du contenu.
  let suggesting = $state(false);
  let lastSuggestedUrl = $state('');
  // On : la suggestion écrase les champs déjà remplis. Off : ne remplit
  // que les champs vides (les saisies manuelles sont préservées).
  let overwriteOnSuggest = $state(false);

  // Fichier bibliographique déposé — transmis à la page Sources via le store.
  let droppedFile = $state<File | null>(null);
  let dragOver = $state(false);
  let fileInput = $state<HTMLInputElement | null>(null);

  function deriveSlug(value: string) {
    return value
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

  async function suggestFromUrl(force = false) {
    const trimmed = contentUrl.trim();
    if (!trimmed) return;
    if (!force && trimmed === lastSuggestedUrl) return;
    try {
      new URL(trimmed);
    } catch {
      return; // URL incomplète : on attend, pas d'erreur intrusive
    }
    suggesting = true;
    lastSuggestedUrl = trimmed;
    try {
      const meta = await api.imports.urlMetadata(trimmed);
      if (meta.title && (overwriteOnSuggest || !title.trim())) {
        title = meta.title;
        if (!slugManual) slug = deriveSlug(meta.title);
      }
      if (meta.description && (overwriteOnSuggest || !description.trim())) {
        description = meta.description;
      }
      const guess = guessPlatform(trimmed);
      if (overwriteOnSuggest || platform === 'other') platform = guess.platform;
      if (overwriteOnSuggest || contentType === 'other') contentType = guess.contentType;
    } catch {
      // silencieux : l'utilisateur remplit à la main
    } finally {
      suggesting = false;
    }
  }

  function acceptFile(file: File | null | undefined) {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) {
      error = 'Fichier trop volumineux (limite : 5 Mo).';
      return;
    }
    droppedFile = file;
    error = null;
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    dragOver = false;
    acceptFile(e.dataTransfer?.files?.[0]);
  }

  function onTitleInput(e: Event) {
    title = (e.target as HTMLInputElement).value;
    if (!slugManual) slug = deriveSlug(title);
  }

  let slugManual = false;

  function onSlugInput(e: Event) {
    slugManual = true;
    slug = (e.target as HTMLInputElement).value;
  }

  async function saveAndContinue() {
    error = null;
    loading = true;
    try {
      let cardId: string;
      if (editCardId) {
        // Le slug n'est pas modifiable : il porte l'URL publique de la fiche.
        await api.cards.update(editCardId, {
          title,
          description: description || undefined,
          content_url: contentUrl || undefined,
          platform,
          content_type: contentType,
          is_seed: !isAuthor,
          visibility,
        });
        cardId = editCardId;
      } else {
        const card = await api.cards.create({
          title,
          slug,
          description: description || undefined,
          content_url: contentUrl || undefined,
          platform,
          content_type: contentType,
          is_seed: !isAuthor,
          visibility,
        });
        cardId = card.id;
      }
      pendingImportFile.set(droppedFile);
      goto(`/dashboard/new/${cardId}/sources`);
    } catch (err) {
      error =
        err instanceof Error
          ? err.message
          : editCardId
            ? 'Erreur lors de la mise à jour'
            : 'Erreur lors de la création';
    } finally {
      loading = false;
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    await saveAndContinue();
  }

  function onStepClick(i: number) {
    // Seule l'étape « Sources » est cliquable ici, et uniquement en mode
    // édition : on enregistre les modifications avant de naviguer.
    if (i === 1 && editCardId && title && !loading) saveAndContinue();
  }

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
</script>

<svelte:head>
  <title>{editCardId ? 'Modifier la fiche' : 'Nouvelle fiche'} - Philum</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
      >← Tableau de bord</a
    >
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-2">
    {editCardId ? 'Modifier la fiche' : 'Nouvelle fiche'}
  </h1>
  <p class="text-sm text-ink-secondary mb-6">
    {#if editCardId}
      Modifiez les informations de la fiche, puis cliquez sur « Sources » ou sur le bouton pour
      enregistrer et revenir aux sources.
    {:else}
      Collez l'URL du contenu — Philum suggère automatiquement les informations. Vous pourrez
      extraire les sources citées à l'étape suivante.
    {/if}
  </p>

  <ProgressSteps {steps} current={0} {onStepClick} class="mb-8" />

  <form onsubmit={handleSubmit} class="space-y-6">
    {#if error}
      <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
        {error}
      </div>
    {/if}

    <div class="space-y-1.5">
      <label for="content-url" class="block text-sm font-medium text-ink-secondary">
        URL du contenu
      </label>
      <div class="flex items-center gap-2">
        <div class="relative flex-1">
          <input
            id="content-url"
            type="url"
            value={contentUrl}
            oninput={(e) => (contentUrl = (e.target as HTMLInputElement).value)}
            onblur={() => suggestFromUrl()}
            placeholder="https://youtube.com/watch?v=… ou https://…/article"
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
          />
          {#if suggesting}
            <div
              class="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-info border-t-transparent rounded-full animate-spin"
            ></div>
          {/if}
        </div>
        <button
          type="button"
          onclick={() => suggestFromUrl(true)}
          disabled={suggesting || !contentUrl.trim()}
          class="p-2 rounded-lg border border-border-strong text-ink-secondary hover:text-info hover:border-info transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Relancer la suggestion de métadonnées"
          title="Relancer la suggestion de métadonnées"
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
      </div>
      <label class="flex items-center gap-2 cursor-pointer text-xs text-ink-tertiary">
        <input type="checkbox" bind:checked={overwriteOnSuggest} class="rounded" />
        Écraser les champs déjà remplis lors de la suggestion
      </label>
    </div>

    <div
      role="button"
      tabindex="0"
      ondragover={(e) => {
        e.preventDefault();
        dragOver = true;
      }}
      ondragleave={() => (dragOver = false)}
      ondrop={onDrop}
      onclick={() => fileInput?.click()}
      onkeydown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') fileInput?.click();
      }}
      class="rounded-lg border-2 border-dashed px-4 py-4 text-center text-sm cursor-pointer transition-colors {dragOver
        ? 'border-info bg-info/5 text-info'
        : 'border-border text-ink-tertiary hover:border-info/50'}"
    >
      <input
        type="file"
        accept=".bib,.bibtex,.json,.md,.markdown,.pdf,.docx,.html,.htm"
        class="hidden"
        bind:this={fileInput}
        onchange={(e) => acceptFile((e.target as HTMLInputElement).files?.[0])}
      />
      {#if droppedFile}
        <p class="text-ink-primary font-medium">{droppedFile.name}</p>
        <p class="text-xs mt-0.5">
          Sera analysé à l'étape Sources.
          <button
            type="button"
            class="text-danger hover:underline"
            onclick={(e) => {
              e.stopPropagation();
              droppedFile = null;
            }}
          >
            Retirer
          </button>
        </p>
      {:else}
        <p>ou déposez ici un fichier bibliographique</p>
        <p class="text-xs mt-0.5">
          BibTeX, CSL-JSON (Zotero), Markdown (Obsidian), PDF, Word ou page HTML — 5 Mo max
        </p>
      {/if}
    </div>

    <div class="space-y-1.5">
      <label for="title" class="block text-sm font-medium text-ink-secondary">
        Titre du contenu <span class="text-danger">*</span>
      </label>
      <input
        id="title"
        type="text"
        value={title}
        oninput={onTitleInput}
        required
        placeholder="Ex: La mémoire et le cerveau — ce que dit la science"
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
      />
    </div>

    <div class="space-y-1.5">
      <label for="slug" class="block text-sm font-medium text-ink-secondary">
        Identifiant URL <span class="text-danger">*</span>
      </label>
      <div class="flex items-center gap-2">
        <span class="text-ink-tertiary text-sm shrink-0">/@{$currentUser?.username ?? 'vous'}/</span
        >
        <input
          id="slug"
          type="text"
          value={slug}
          oninput={onSlugInput}
          required
          disabled={Boolean(editCardId)}
          pattern="[a-z0-9-]+"
          placeholder="memoire-et-cerveau"
          class="flex-1 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary disabled:opacity-60 disabled:cursor-not-allowed"
        />
      </div>
      <p class="text-xs text-ink-tertiary">
        {editCardId
          ? "L'identifiant URL n'est pas modifiable : il porte l'adresse publique de la fiche."
          : 'Lettres minuscules, chiffres et tirets uniquement.'}
      </p>
    </div>

    <div class="space-y-1.5">
      <label for="description" class="block text-sm font-medium text-ink-secondary">
        Description
      </label>
      <textarea
        id="description"
        value={description}
        oninput={(e) => (description = (e.target as HTMLTextAreaElement).value)}
        rows={3}
        placeholder="Résumé de votre contenu..."
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary resize-y min-h-[3rem]"
      ></textarea>
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div class="space-y-1.5">
        <label for="platform" class="block text-sm font-medium text-ink-secondary">Plateforme</label
        >
        <select
          id="platform"
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
        <label for="content-type" class="block text-sm font-medium text-ink-secondary"
          >Type de contenu</label
        >
        <select
          id="content-type"
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

    <div class="rounded-lg border border-border bg-surface-secondary/40 p-4">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          bind:checked={isAuthor}
          class="mt-0.5 shrink-0"
          aria-describedby="author-hint"
        />
        <span class="text-sm">
          <span class="font-medium text-ink-primary">
            Je suis l'auteur·ice de ce contenu et je souhaite le revendiquer
          </span>
          <span id="author-hint" class="block text-xs text-ink-tertiary mt-0.5">
            Cochez uniquement si vous pouvez prouver que vous êtes l'auteur·ice : la fiche sera
            attestée cryptographiquement en votre nom. Sinon, la fiche est créée comme
            <em>non revendiquée</em> et le ou la véritable auteur·ice pourra la revendiquer depuis la
            page publique.
          </span>
        </span>
      </label>
    </div>

    <fieldset class="space-y-2">
      <legend class="block text-sm font-medium text-ink-secondary">Visibilité</legend>
      <div class="grid sm:grid-cols-2 gap-2">
        <label
          class="flex items-start gap-3 border border-border rounded-lg p-3 cursor-pointer transition-colors {visibility ===
          'public'
            ? 'bg-info/10 border-info'
            : 'hover:bg-surface-secondary'}"
        >
          <input type="radio" bind:group={visibility} value="public" class="mt-0.5" />
          <span class="text-sm">
            <span class="font-medium text-ink-primary block">Publique</span>
            <span class="text-xs text-ink-tertiary">
              Visible par tout le monde une fois publiée.
            </span>
          </span>
        </label>
        <label
          class="flex items-start gap-3 border border-border rounded-lg p-3 cursor-pointer transition-colors {visibility ===
          'private'
            ? 'bg-info/10 border-info'
            : 'hover:bg-surface-secondary'}"
        >
          <input type="radio" bind:group={visibility} value="private" class="mt-0.5" />
          <span class="text-sm">
            <span class="font-medium text-ink-primary block">Privée</span>
            <span class="text-xs text-ink-tertiary">
              Visible uniquement par vous (connecté). Changeable plus tard.
            </span>
          </span>
        </label>
      </div>
    </fieldset>

    <div class="flex justify-end pt-4">
      <Button type="submit" {loading} disabled={!title || !slug || loading || loadingCard}>
        {#if editCardId}
          {loading ? 'Enregistrement…' : 'Enregistrer et revenir aux sources →'}
        {:else}
          {loading ? 'Création…' : 'Suivant : ajouter les sources →'}
        {/if}
      </Button>
    </div>
  </form>
</div>
