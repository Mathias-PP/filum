<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
  import { currentUser } from '$lib/stores/auth';
  import { pendingImportFile } from '$lib/stores/import-file';
  import { guessPlatform } from '$lib/utils/platform-guess';
  import type {
    AuthorKind,
    CardKind,
    Platform,
    ContentType,
    SourceCategory,
    SourceFormat,
    Visibility,
  } from '$lib/api';

  // Mode édition : /dashboard/new?card_id=<id> pré-remplit le formulaire
  // depuis la fiche existante et le submit fait un PATCH au lieu d'un POST.
  const editCardId = $derived($page.url.searchParams.get('card_id'));

  const steps = $derived([
    { label: 'Informations', description: 'Nature, titre' },
    { label: 'Sources', description: 'Ajouter et publier', clickable: Boolean(editCardId) },
  ]);

  let title = $state('');
  let slug = $state('');
  let description = $state('');
  let contentUrl = $state('');
  // Auteurs du contenu documenté — pas ceux de la fiche. Sans eux, le nœud de
  // la fiche dans le graphe ne peut s'annoncer que sous le nom de son créateur
  // Philum, laissant croire qu'il est l'auteur de ce qu'elle documente.
  let contentAuthors = $state('');
  // Texte intégral du contenu documenté quand l'utilisateur en dispose et a
  // le droit de le publier. Rendu sur la fiche publique, indexable par les
  // outils MCP en aval (recherche par le sens). Vide = non publié.
  let contentText = $state('');
  let contentTextUploading = $state(false);
  let contentTextError = $state<string | null>(null);
  let contentTextConfirmedRights = $state(false);
  let contentTextFileInput = $state<HTMLInputElement | null>(null);
  let platform = $state<Platform>('other');
  let contentType = $state<ContentType>('other');
  // Ce que la fiche documente. Premier choix du formulaire : il decide quels
  // champs ont un sens. Une fiche sujet n'a ni URL, ni auteurs tiers, ni
  // plateforme, ni type de contenu, parce qu'elle ne documente aucun contenu.
  let cardKind = $state<CardKind>('contenu');
  const estContenu = $derived(cardKind === 'contenu');
  let isAuthor = $state(false);
  let visibility = $state<Visibility>('public');
  let cardFormat = $state<SourceFormat | ''>('');
  let cardCategory = $state<SourceCategory | ''>('');
  let cardAuthorKind = $state<AuthorKind | ''>('');
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
      contentAuthors = card.content_authors ?? '';
      contentText = card.content_text ?? '';
      // Sur une edition, l'utilisateur a deja fait ce choix au premier depot ;
      // on ne le fait pas repasser la case a cocher pour un texte deja publie.
      contentTextConfirmedRights = Boolean(card.content_text);
      lastSuggestedUrl = contentUrl;
      cardKind = card.card_kind;
      platform = card.platform ?? 'other';
      contentType = card.content_type ?? 'other';
      isAuthor = !card.is_seed;
      visibility = card.visibility;
      cardFormat = (card.format ?? '') as SourceFormat | '';
      cardCategory = (card.category ?? '') as SourceCategory | '';
      cardAuthorKind = (card.author_kind ?? '') as AuthorKind | '';
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
  // Ce que la suggestion n'a pas pu faire, et pourquoi. Sans ce message, un
  // refus du site et une page sans métadonnées se ressemblent : des champs
  // restés vides, sans qu'on sache s'il faut réessayer ou saisir soi-même.
  let suggestNotice = $state<string | null>(null);
  const hasFieldsToOverwrite = $derived(
    Boolean(title.trim() || description.trim() || contentAuthors.trim()) ||
      (estContenu && (platform !== 'other' || contentType !== 'other'))
  );

  // Passer une fiche en « sujet » efface tout ce qui décrivait le contenu.
  // L'URL et les auteurs se retrouvent, le texte intégral non : il vient d'un
  // copier-coller ou d'une extraction de fichier. On refuse d'enregistrer tant
  // qu'il est là, pour que sa destruction reste un geste voulu.
  const texteIntegralABandonner = $derived(!estContenu && contentText.trim().length > 0);

  // Fichier bibliographique déposé — transmis à la page Sources via le store.
  let droppedFile = $state<File | null>(null);
  let dragOver = $state(false);
  let fileInput = $state<HTMLInputElement | null>(null);

  async function uploadContentTextFile(file: File | null | undefined) {
    if (!file) return;
    if (!editCardId) {
      contentTextError =
        "Enregistrez d'abord la fiche : le fichier a besoin d'un identifiant pour y déposer son texte.";
      return;
    }
    if (!contentTextConfirmedRights) {
      contentTextError = 'Cochez la case des droits avant de déposer un fichier.';
      return;
    }
    contentTextError = null;
    contentTextUploading = true;
    try {
      const updated = await api.cards.uploadContentText(editCardId, file);
      contentText = updated.content_text ?? '';
    } catch (err) {
      contentTextError = err instanceof Error ? err.message : "L'extraction a échoué.";
    } finally {
      contentTextUploading = false;
    }
  }

  function deriveSlug(value: string) {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60);
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
    suggestNotice = null;
    try {
      const meta = await api.imports.urlMetadata(trimmed);
      if (meta.access_blocked) {
        // Certains editeurs (Nature, Elsevier, IEEE...) refusent tout fetch
        // automatique. La citation est presque toujours disponible en fichier
        // depuis la page — plus fiable que la ressaisie a la main. On oriente
        // le lecteur vers l'import fichier en aval du wizard.
        suggestNotice =
          'Ce site a refusé la lecture automatique de la page. ' +
          'Astuce : la plupart des éditeurs proposent un bouton « Cite » ou ' +
          '« Export » qui télécharge un fichier .ris ou .bib — vous pourrez ' +
          "l'importer à l'étape suivante. En attendant, saisissez le titre " +
          'et les auteurs à la main.';
      } else if (!meta.title && !meta.description && !meta.authors) {
        suggestNotice = "La page a été lue mais n'annonce ni titre ni auteurs exploitables.";
      }
      if (meta.title && (overwriteOnSuggest || !title.trim())) {
        title = meta.title;
        if (!slugManual) slug = deriveSlug(meta.title);
      }
      if (meta.description && (overwriteOnSuggest || !description.trim())) {
        description = meta.description;
      }
      if (meta.authors && (overwriteOnSuggest || !contentAuthors.trim())) {
        contentAuthors = meta.authors.slice(0, 500);
      }
      const guess = guessPlatform(trimmed);
      if (overwriteOnSuggest || platform === 'other') platform = guess.platform;
      if (overwriteOnSuggest || contentType === 'other') contentType = guess.contentType;
    } catch {
      suggestNotice = "La page n'a pas pu être jointe. Saisissez les champs à la main.";
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
      // Une fiche sujet ne documente aucun contenu : lui envoyer une URL, des
      // auteurs ou une plateforme reviendrait à inventer un contenu source, et
      // le serveur le refuse. En édition, la chaîne vide est transmise à
      // dessein : c'est elle qui efface ce qui avait été saisi.
      const champsDuContenu = !estContenu
        ? { content_text: '' }
        : editCardId
          ? {
              content_url: contentUrl || undefined,
              content_authors: contentAuthors.trim(),
              content_text: contentTextConfirmedRights ? contentText : '',
              platform,
              content_type: contentType,
              is_seed: !isAuthor,
            }
          : {
              content_url: contentUrl || undefined,
              content_authors: contentAuthors.trim() || undefined,
              content_text:
                contentTextConfirmedRights && contentText.trim() ? contentText : undefined,
              platform,
              content_type: contentType,
              is_seed: !isAuthor,
            };

      const commun = {
        title,
        description: description || undefined,
        card_kind: cardKind,
        ...champsDuContenu,
        visibility,
        format: cardFormat || null,
        category: cardCategory || null,
        author_kind: cardAuthorKind || null,
      };

      let cardId: string;
      if (editCardId) {
        // Le slug n'est pas modifiable : il porte l'URL publique de la fiche.
        await api.cards.update(editCardId, commun);
        cardId = editCardId;
      } else {
        cardId = (await api.cards.create({ ...commun, slug })).id;
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
    { value: 'revue-scientifique', label: 'Revue scientifique' },
    { value: 'other', label: 'Autre' },
  ];

  const contentTypes: { value: ContentType; label: string }[] = [
    { value: 'video', label: 'Vidéo' },
    { value: 'article', label: 'Article' },
    { value: 'post', label: 'Post' },
    { value: 'podcast', label: 'Podcast' },
    { value: 'other', label: 'Autre' },
  ];

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

  const authorKindOptions: { value: AuthorKind; label: string }[] = [
    { value: 'chercheur', label: 'Chercheur·se' },
    { value: 'media', label: 'Média' },
    { value: 'institution-publique', label: 'Institution publique' },
    { value: 'gouvernement', label: 'Gouvernement' },
    { value: 'ecole', label: 'École / université' },
    { value: 'laboratoire', label: 'Laboratoire' },
    { value: 'entreprise', label: 'Entreprise' },
    { value: 'asso', label: 'Association' },
    { value: 'individu', label: 'Individu' },
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
    {:else if estContenu}
      Collez l'URL du contenu : Philum suggère automatiquement les informations. Vous pourrez
      extraire les sources citées à l'étape suivante.
    {:else}
      Donnez la question traitée : la fiche est votre bibliographie sur ce sujet. Vous en
      rassemblerez les sources à l'étape suivante.
    {/if}
  </p>

  <ProgressSteps {steps} current={0} {onStepClick} class="mb-8" />

  <form onsubmit={handleSubmit} class="space-y-6">
    {#if error}
      <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
        {error}
      </div>
    {/if}

    <fieldset class="space-y-2">
      <legend class="block text-sm font-medium text-ink-secondary"
        >Que documente cette fiche ?</legend
      >
      <div class="grid sm:grid-cols-2 gap-2">
        <label
          class="flex items-start gap-3 border rounded-lg p-3 cursor-pointer transition-colors {estContenu
            ? 'bg-info/10 border-info'
            : 'border-border hover:bg-surface-secondary'}"
        >
          <input type="radio" bind:group={cardKind} value="contenu" class="mt-0.5" />
          <span class="text-sm">
            <span class="font-medium text-ink-primary block">Un contenu</span>
            <span class="text-xs text-ink-tertiary">
              Une vidéo, un article, un podcast, un post qui existe ailleurs. La fiche donne son
              lien et cite ses sources.
            </span>
          </span>
        </label>
        <label
          class="flex items-start gap-3 border rounded-lg p-3 cursor-pointer transition-colors {!estContenu
            ? 'bg-info/10 border-info'
            : 'border-border hover:bg-surface-secondary'}"
        >
          <input type="radio" bind:group={cardKind} value="sujet" class="mt-0.5" />
          <span class="text-sm">
            <span class="font-medium text-ink-primary block">Un sujet</span>
            <span class="text-xs text-ink-tertiary">
              Une question, sans contenu source. La fiche est votre bibliographie sur ce sujet, et
              vous en êtes l'auteur·ice.
            </span>
          </span>
        </label>
      </div>
    </fieldset>

    {#if texteIntegralABandonner}
      <div class="rounded-lg border border-warning bg-warning-subtle px-4 py-3 text-sm space-y-2">
        <p class="text-ink-primary">
          Cette fiche porte le texte intégral d'un contenu ({contentText.length.toLocaleString(
            'fr-FR'
          )} caractères). Une fiche sujet ne documente aucun contenu : ce texte sera perdu.
        </p>
        <button
          type="button"
          onclick={() => (contentText = '')}
          class="px-3 py-1.5 rounded-md border border-danger text-xs text-danger hover:bg-danger-bg transition-colors"
        >
          Effacer le texte intégral
        </button>
      </div>
    {/if}

    {#if estContenu}
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
              class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
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
        {#if suggestNotice}
          <p
            class="text-xs text-warning bg-warning-bg border border-warning/30 rounded-md px-3 py-2"
          >
            {suggestNotice}
          </p>
        {/if}
        <!--
        Ne s'affiche que lorsqu'il y a quelque chose à écraser : sur un
        formulaire vierge, cette case ne change rien et n'occupe l'attention
        que pour poser une question qui ne se pose pas encore.
      -->
        {#if hasFieldsToOverwrite}
          <label class="flex items-center gap-2 cursor-pointer text-xs text-ink-tertiary">
            <input type="checkbox" bind:checked={overwriteOnSuggest} class="rounded" />
            Écraser les champs déjà remplis lors de la suggestion
          </label>
        {/if}
      </div>
    {/if}

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
          Prêt à être analysé, cliquez sur « {editCardId
            ? 'Enregistrer et revenir aux sources'
            : 'Suivant : ajouter les sources'} » en bas de page pour lancer l'extraction.
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
          BibTeX, CSL-JSON (Zotero), Markdown (Obsidian), PDF, Word ou page HTML, 5 Mo max
        </p>
      {/if}
    </div>

    <div class="space-y-1.5">
      <label for="title" class="block text-sm font-medium text-ink-secondary">
        {estContenu ? 'Titre du contenu' : 'Question traitée'}
        <span class="text-danger">*</span>
      </label>
      <input
        id="title"
        type="text"
        value={title}
        oninput={onTitleInput}
        required
        placeholder={estContenu
          ? 'Ex: La mémoire et le cerveau, ce que dit la science'
          : 'Ex: Que sait-on des effets du sommeil sur la mémoire ?'}
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
      />
    </div>

    {#if estContenu}
      <div class="space-y-1.5">
        <label for="content-authors" class="block text-sm font-medium text-ink-secondary">
          Auteurs du contenu
        </label>
        <input
          id="content-authors"
          type="text"
          value={contentAuthors}
          oninput={(e) => (contentAuthors = (e.target as HTMLInputElement).value)}
          maxlength={500}
          placeholder="Ex: Diamond A., Ling D.S."
          class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
        />
        <p class="text-xs text-ink-tertiary">
          Qui a écrit ou réalisé le contenu documenté, pas qui publie la fiche. C'est ce nom qui
          identifie la fiche dans le graphe des sources.
        </p>
      </div>

      <details class="border border-border rounded-lg bg-surface-primary">
        <summary
          class="cursor-pointer px-4 py-3 text-sm font-medium text-ink-secondary select-none"
        >
          Texte intégral du contenu <span class="text-ink-tertiary font-normal">(optionnel)</span>
        </summary>
        <div class="px-4 pb-4 pt-2 space-y-3">
          <p class="text-xs text-ink-tertiary">
            Collez le texte du contenu ou déposez un fichier (PDF, Word, ODT, TXT, Markdown). Utile
            quand vous avez le droit de publier ce texte : votre propre article, un contenu libre de
            droit, une retranscription que vous avez faite, ou un extrait sous droit de citation.
          </p>

          <label
            class="flex items-start gap-2 rounded-md border border-warning bg-warning-subtle p-3 text-xs text-ink-primary cursor-pointer"
          >
            <input
              type="checkbox"
              bind:checked={contentTextConfirmedRights}
              class="mt-0.5 accent-warning"
            />
            <span>
              Je certifie avoir le droit de publier ce texte sur ma fiche publique (contenu propre,
              libre de droit, ou extrait dans la limite du droit de citation). Sans cette case
              cochée, le texte n'est ni envoyé ni sauvegardé.
            </span>
          </label>

          {#if contentTextConfirmedRights}
            <textarea
              bind:value={contentText}
              rows="8"
              maxlength={500000}
              placeholder="Collez ici le texte du contenu (jusqu'à 500 000 caractères)…"
              class="w-full px-3 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary font-mono text-xs focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder"
            ></textarea>

            <div class="flex items-center gap-3">
              {#if editCardId}
                <button
                  type="button"
                  onclick={() => contentTextFileInput?.click()}
                  disabled={contentTextUploading}
                  class="px-3 py-1.5 rounded-md border border-border-strong bg-surface-primary text-xs text-ink-secondary hover:bg-surface-tertiary disabled:opacity-50"
                >
                  {contentTextUploading
                    ? 'Extraction en cours…'
                    : 'Déposer un fichier (PDF, Word, ODT, TXT, MD)'}
                </button>
                <input
                  bind:this={contentTextFileInput}
                  type="file"
                  accept=".pdf,.docx,.odt,.txt,.md,.markdown"
                  class="hidden"
                  onchange={(e) => uploadContentTextFile((e.target as HTMLInputElement).files?.[0])}
                />
              {:else}
                <p class="text-xs text-ink-tertiary">
                  Le dépôt de fichier sera possible après avoir enregistré la fiche une première
                  fois (le fichier a besoin d'un identifiant où déposer son texte).
                </p>
              {/if}
              <span class="text-xs text-ink-tertiary">
                {contentText.length.toLocaleString('fr-FR')} / 500 000 caractères
              </span>
            </div>

            {#if contentTextError}
              <p class="text-xs text-danger">{contentTextError}</p>
            {/if}
          {/if}
        </div>
      </details>
    {/if}

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
          class="flex-1 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder disabled:opacity-60 disabled:cursor-not-allowed"
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
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-placeholder resize-y min-h-12"
      ></textarea>
    </div>

    {#if estContenu}
      <div class="grid grid-cols-2 gap-4">
        <div class="space-y-1.5">
          <label for="platform" class="block text-sm font-medium text-ink-secondary"
            >Plateforme</label
          >
          <select
            id="platform"
            value={platform}
            onchange={(e) => (platform = (e.target as HTMLSelectElement).value as Platform)}
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
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
            class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
          >
            {#each contentTypes as ct (ct.value)}
              <option value={ct.value}>{ct.label}</option>
            {/each}
          </select>
        </div>
      </div>
    {/if}

    <div class="grid grid-cols-3 gap-4">
      <div class="space-y-1.5">
        <label for="card-format" class="block text-sm font-medium text-ink-secondary">Format</label>
        <select
          id="card-format"
          value={cardFormat}
          onchange={(e) =>
            (cardFormat = (e.target as HTMLSelectElement).value as SourceFormat | '')}
          class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
        >
          <option value="">Non déclaré</option>
          {#each formatOptions as f (f.value)}
            <option value={f.value}>{f.label}</option>
          {/each}
        </select>
      </div>
      <div class="space-y-1.5">
        <label for="card-category" class="block text-sm font-medium text-ink-secondary"
          >Catégorie</label
        >
        <select
          id="card-category"
          value={cardCategory}
          onchange={(e) =>
            (cardCategory = (e.target as HTMLSelectElement).value as SourceCategory | '')}
          class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
        >
          <option value="">Non déclaré</option>
          {#each categoryOptions as c (c.value)}
            <option value={c.value}>{c.label}</option>
          {/each}
        </select>
      </div>
      <div class="space-y-1.5">
        <label for="card-author-kind" class="block text-sm font-medium text-ink-secondary"
          >Type d'auteur</label
        >
        <select
          id="card-author-kind"
          value={cardAuthorKind}
          onchange={(e) =>
            (cardAuthorKind = (e.target as HTMLSelectElement).value as AuthorKind | '')}
          class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-hidden focus:ring-2 focus:ring-info"
        >
          <option value="">Non déclaré</option>
          {#each authorKindOptions as a (a.value)}
            <option value={a.value}>{a.label}</option>
          {/each}
        </select>
      </div>
    </div>

    <!--
      Revendiquer n'a de sens que face à un contenu tiers. Une fiche sujet est
      écrite par son créateur Philum : il n'y a personne d'autre à qui la rendre.
    -->
    {#if estContenu}
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
    {/if}

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
      <Button
        type="submit"
        {loading}
        disabled={!title || !slug || loading || loadingCard || texteIntegralABandonner}
      >
        {#if editCardId}
          {loading ? 'Enregistrement…' : 'Enregistrer et revenir aux sources →'}
        {:else if droppedFile}
          {loading ? 'Création…' : 'Suivant : analyser le fichier →'}
        {:else}
          {loading ? 'Création…' : 'Suivant : ajouter les sources →'}
        {/if}
      </Button>
    </div>
  </form>
</div>
