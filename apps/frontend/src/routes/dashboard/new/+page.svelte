<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
  import { currentUser } from '$lib/stores/auth';
  import type { Platform, ContentType, Visibility } from '$lib/api';

  const steps = [
    { label: 'Informations', description: 'Titre, plateforme' },
    { label: 'Sources', description: 'Ajouter et publier' },
  ];

  let title = $state('');
  let slug = $state('');
  let description = $state('');
  let contentUrl = $state('');
  let platform = $state<Platform>('other');
  let contentType = $state<ContentType>('other');
  let isSeed = $state(false);
  let visibility = $state<Visibility>('public');
  let error = $state<string | null>(null);
  let loading = $state(false);

  function deriveSlug(value: string) {
    return value
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60);
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

  async function handleSubmit(e: Event) {
    e.preventDefault();
    error = null;
    loading = true;
    try {
      const card = await api.cards.create({
        title,
        slug,
        description: description || undefined,
        content_url: contentUrl || undefined,
        platform,
        content_type: contentType,
        is_seed: isSeed,
        visibility,
      });
      goto(`/dashboard/new/${card.id}/sources`);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Erreur lors de la création';
    } finally {
      loading = false;
    }
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
  <title>Nouvelle fiche - Philum</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
      >← Tableau de bord</a
    >
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-2">Nouvelle fiche</h1>
  <p class="text-sm text-ink-secondary mb-4">Informations sur votre contenu</p>

  <p class="text-xs text-ink-tertiary mb-6">
    Astuce : si vous avez déjà l'URL d'un article ou d'un billet avec sa bibliographie, essayez
    <a href="/dashboard/from-url" class="text-info hover:underline">Créer depuis une URL</a>
    pour extraire titre et sources automatiquement.
  </p>

  <ProgressSteps {steps} current={0} class="mb-8" />

  <form onsubmit={handleSubmit} class="space-y-6">
    {#if error}
      <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-3 text-sm text-danger">
        {error}
      </div>
    {/if}

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
          pattern="[a-z0-9-]+"
          placeholder="memoire-et-cerveau"
          class="flex-1 px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
        />
      </div>
      <p class="text-xs text-ink-tertiary">Lettres minuscules, chiffres et tirets uniquement.</p>
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
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary resize-none"
      ></textarea>
    </div>

    <div class="space-y-1.5">
      <label for="content-url" class="block text-sm font-medium text-ink-secondary">
        URL du contenu
      </label>
      <input
        id="content-url"
        type="url"
        value={contentUrl}
        oninput={(e) => (contentUrl = (e.target as HTMLInputElement).value)}
        placeholder="https://youtube.com/watch?v=..."
        class="w-full px-4 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary focus:outline-none focus:ring-2 focus:ring-info focus:border-info placeholder:text-ink-tertiary"
      />
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
          {#each platforms as p}
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
          {#each contentTypes as ct}
            <option value={ct.value}>{ct.label}</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="rounded-lg border border-border bg-surface-secondary/40 p-4">
      <label class="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          bind:checked={isSeed}
          class="mt-0.5 shrink-0"
          aria-describedby="seed-hint"
        />
        <span class="text-sm">
          <span class="font-medium text-ink-primary">
            Je ne suis pas l'auteur·ice de ce contenu
          </span>
          <span id="seed-hint" class="block text-xs text-ink-tertiary mt-0.5">
            La fiche sera marquée comme <em>non revendiquée</em> — l'auteur·ice du contenu pourra la revendiquer
            depuis la page publique et en devenir propriétaire. Vous ne pourrez pas attester cryptographiquement
            d'un contenu que vous n'avez pas créé.
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
      <Button type="submit" {loading} disabled={!title || !slug || loading}>
        {loading ? 'Création…' : 'Suivant : ajouter les sources →'}
      </Button>
    </div>
  </form>
</div>
