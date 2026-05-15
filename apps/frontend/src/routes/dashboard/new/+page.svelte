<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { Button, ProgressSteps } from '$lib/components';
  import type { Platform, ContentType } from '$lib/api';

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
  <title>Nouvelle fiche - Filum</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-tertiary hover:text-ink-primary transition-colors"
      >← Tableau de bord</a
    >
  </div>

  <h1 class="font-serif text-3xl text-ink-primary mb-2">Nouvelle fiche</h1>
  <p class="text-sm text-ink-secondary mb-6">Informations sur votre contenu</p>

  <ProgressSteps {steps} current={0} class="mb-8" />

  <form onsubmit={handleSubmit} class="space-y-6">
    {#if error}
      <div class="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    {/if}

    <div class="space-y-1.5">
      <label for="title" class="block text-sm font-medium text-slate-700">
        Titre du contenu <span class="text-red-500">*</span>
      </label>
      <input
        id="title"
        type="text"
        value={title}
        oninput={onTitleInput}
        required
        placeholder="Ex: La mémoire et le cerveau — ce que dit la science"
        class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400"
      />
    </div>

    <div class="space-y-1.5">
      <label for="slug" class="block text-sm font-medium text-slate-700">
        Identifiant URL <span class="text-red-500">*</span>
      </label>
      <div class="flex items-center gap-2">
        <span class="text-slate-400 text-sm shrink-0">/@vous/</span>
        <input
          id="slug"
          type="text"
          value={slug}
          oninput={onSlugInput}
          required
          pattern="[a-z0-9-]+"
          placeholder="memoire-et-cerveau"
          class="flex-1 px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400"
        />
      </div>
      <p class="text-xs text-slate-500">Lettres minuscules, chiffres et tirets uniquement.</p>
    </div>

    <div class="space-y-1.5">
      <label for="description" class="block text-sm font-medium text-slate-700">
        Description
      </label>
      <textarea
        id="description"
        value={description}
        oninput={(e) => (description = (e.target as HTMLTextAreaElement).value)}
        rows={3}
        placeholder="Résumé de votre contenu..."
        class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400 resize-none"
      ></textarea>
    </div>

    <div class="space-y-1.5">
      <label for="content-url" class="block text-sm font-medium text-slate-700">
        URL du contenu
      </label>
      <input
        id="content-url"
        type="url"
        value={contentUrl}
        oninput={(e) => (contentUrl = (e.target as HTMLInputElement).value)}
        placeholder="https://youtube.com/watch?v=..."
        class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 placeholder:text-slate-400"
      />
    </div>

    <div class="grid grid-cols-2 gap-4">
      <div class="space-y-1.5">
        <label for="platform" class="block text-sm font-medium text-slate-700">Plateforme</label>
        <select
          id="platform"
          value={platform}
          onchange={(e) => (platform = (e.target as HTMLSelectElement).value as Platform)}
          class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {#each platforms as p}
            <option value={p.value}>{p.label}</option>
          {/each}
        </select>
      </div>

      <div class="space-y-1.5">
        <label for="content-type" class="block text-sm font-medium text-slate-700"
          >Type de contenu</label
        >
        <select
          id="content-type"
          value={contentType}
          onchange={(e) => (contentType = (e.target as HTMLSelectElement).value as ContentType)}
          class="w-full px-4 py-2 rounded-lg border border-slate-300 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {#each contentTypes as ct}
            <option value={ct.value}>{ct.label}</option>
          {/each}
        </select>
      </div>
    </div>

    <div class="flex justify-end pt-4">
      <Button type="submit" {loading} disabled={!title || !slug || loading}>
        {loading ? 'Création…' : 'Suivant : ajouter les sources →'}
      </Button>
    </div>
  </form>
</div>
