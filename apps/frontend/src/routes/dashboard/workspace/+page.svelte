<script lang="ts">
  import { onMount } from 'svelte';
  import { agentApi, type WorkspaceTreeEntry } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, toast } from '$lib/components';

  // Etat de l'arbre : liste plate ordonnee par path, aplatie pour l'affichage.
  // Le serveur renvoie deja fichiers et dossiers ; on utilise le path pour
  // deriver la profondeur (indentation).
  let entrees = $state<WorkspaceTreeEntry[]>([]);
  let chargementArbre = $state(true);
  let chargementFichier = $state(false);
  let cheminActif = $state<string>('');
  let contenu = $state('');
  let contenuOriginal = $state('');
  let messageErr = $state('');

  // Nouveau fichier
  let creationOuverte = $state(false);
  let nouveauChemin = $state('');

  // Suppression
  let suppressionOuverte = $state(false);
  let cibleSuppression = $state<string | null>(null);

  const modifie = $derived(contenu !== contenuOriginal);

  async function chargerArbre() {
    chargementArbre = true;
    try {
      entrees = await agentApi.workspace.tree();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Impossible de lire le workspace.');
      entrees = [];
    } finally {
      chargementArbre = false;
    }
  }

  async function ouvrir(path: string) {
    if (path === cheminActif) return;
    if (modifie) {
      const ok = confirm(`Perdre les modifications de ${cheminActif} ?`);
      if (!ok) return;
    }
    chargementFichier = true;
    messageErr = '';
    try {
      const fichier = await agentApi.workspace.read(path);
      cheminActif = path;
      contenu = fichier.content;
      contenuOriginal = fichier.content;
    } catch (e) {
      messageErr = e instanceof ApiError ? e.message : 'Lecture impossible.';
    } finally {
      chargementFichier = false;
    }
  }

  async function enregistrer() {
    if (!cheminActif || !modifie) return;
    messageErr = '';
    try {
      await agentApi.workspace.write(cheminActif, contenu);
      contenuOriginal = contenu;
      toast.success(`« ${cheminActif} » enregistré.`);
      // Rafraichir l'arbre pour recuperer sha256/updated_at a jour.
      void chargerArbre();
    } catch (e) {
      messageErr = e instanceof ApiError ? e.message : 'Écriture impossible.';
    }
  }

  async function creer() {
    const chemin = nouveauChemin.trim();
    if (!chemin) return;
    try {
      await agentApi.workspace.write(chemin, '');
      creationOuverte = false;
      nouveauChemin = '';
      await chargerArbre();
      await ouvrir(chemin);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Création impossible.');
    }
  }

  async function supprimer() {
    if (!cibleSuppression) return;
    const chemin = cibleSuppression;
    cibleSuppression = null;
    try {
      await agentApi.workspace.remove(chemin);
      if (cheminActif === chemin) {
        cheminActif = '';
        contenu = '';
        contenuOriginal = '';
      }
      await chargerArbre();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Suppression impossible.');
    }
  }

  async function reSeed() {
    try {
      const res = await agentApi.workspace.seed();
      toast.success(`${res.seeded} fichier${res.seeded > 1 ? 's' : ''} réinitialisé(s).`);
      await chargerArbre();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Seed impossible.');
    }
  }

  function profondeur(path: string): number {
    return Math.max(0, path.split('/').length - 1);
  }

  function nomCourt(path: string): string {
    const parts = path.split('/');
    return parts[parts.length - 1] || path;
  }

  onMount(() => {
    void chargerArbre();
  });
</script>

<svelte:head>
  <title>Workspace · Philum</title>
</svelte:head>

<div class="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
  <div class="mb-4 flex items-center justify-between gap-2">
    <div>
      <h1 class="font-serif text-2xl text-ink-primary">Workspace</h1>
      <p class="mt-1 text-sm text-ink-secondary">
        Fichiers Markdown lus par l'agent avant chaque conversation. Servent de contexte éditorial
        partagé.
      </p>
    </div>
    <div class="flex gap-2">
      <Button
        size="sm"
        variant="ghost"
        onclick={reSeed}
        title="Restaurer les fichiers manquants du template"
      >
        Restaurer template
      </Button>
      <Button size="sm" onclick={() => (creationOuverte = true)}>Nouveau fichier</Button>
    </div>
  </div>

  <div class="grid gap-4 lg:grid-cols-[18rem_1fr]">
    <aside class="rounded-lg border border-subtle bg-surface-secondary p-2">
      {#if chargementArbre}
        <p class="p-2 text-sm text-ink-tertiary">Chargement…</p>
      {:else if entrees.length === 0}
        <p class="p-2 text-sm text-ink-tertiary">Workspace vide.</p>
      {:else}
        <ul class="space-y-0.5 text-sm">
          {#each entrees as e (e.path)}
            {#if e.type === 'directory'}
              <li
                class="px-2 py-1 text-xs uppercase tracking-wider text-ink-tertiary"
                style="padding-left: {profondeur(e.path) * 0.75 + 0.5}rem;"
              >
                {nomCourt(e.path)}/
              </li>
            {:else}
              <li class="flex items-center gap-1">
                <button
                  type="button"
                  class="flex-1 truncate rounded px-2 py-1 text-left hover:bg-surface-tertiary"
                  class:bg-surface-tertiary={cheminActif === e.path}
                  class:font-medium={cheminActif === e.path}
                  style="padding-left: {profondeur(e.path) * 0.75 + 0.5}rem;"
                  onclick={() => ouvrir(e.path)}
                >
                  {nomCourt(e.path)}
                </button>
                <button
                  type="button"
                  class="px-1 text-ink-tertiary hover:text-danger"
                  title="Supprimer"
                  onclick={() => {
                    cibleSuppression = e.path;
                    suppressionOuverte = true;
                  }}
                >
                  ×
                </button>
              </li>
            {/if}
          {/each}
        </ul>
      {/if}
    </aside>

    <section class="rounded-lg border border-subtle bg-surface-primary p-3">
      {#if !cheminActif}
        <p class="text-sm text-ink-tertiary">Choisissez un fichier à gauche pour l'éditer.</p>
      {:else if chargementFichier}
        <p class="text-sm text-ink-tertiary">Chargement…</p>
      {:else}
        <div class="mb-2 flex items-center justify-between gap-2">
          <span class="font-mono text-xs text-ink-secondary">{cheminActif}</span>
          <div class="flex gap-2">
            {#if modifie}
              <span class="text-xs text-amber-600">Modifié</span>
            {/if}
            <Button size="sm" disabled={!modifie} onclick={enregistrer}>Enregistrer</Button>
          </div>
        </div>
        <textarea
          bind:value={contenu}
          spellcheck="false"
          class="min-h-[24rem] w-full resize-y rounded border border-subtle bg-surface-primary p-3 font-mono text-sm text-ink-primary"
        ></textarea>
        {#if messageErr}
          <p class="mt-2 text-xs text-danger">{messageErr}</p>
        {/if}
      {/if}
    </section>
  </div>
</div>

<!-- Modale de creation : simple form ; le path est libre, le serveur valide -->
{#if creationOuverte}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    role="dialog"
    aria-modal="true"
  >
    <div class="w-full max-w-md rounded-lg border border-subtle bg-surface-primary p-4 shadow-lg">
      <h2 class="mb-2 font-serif text-lg text-ink-primary">Nouveau fichier</h2>
      <p class="mb-3 text-xs text-ink-tertiary">
        Chemin relatif au workspace (ex. <code>shared/style.md</code>). Le fichier est créé vide.
      </p>
      <form
        onsubmit={(e) => {
          e.preventDefault();
          void creer();
        }}
      >
        <!-- svelte-ignore a11y_autofocus -->
        <input
          bind:value={nouveauChemin}
          class="w-full rounded border border-subtle bg-surface-secondary px-3 py-2 font-mono text-sm"
          placeholder="shared/mon-fichier.md"
          autofocus
        />
        <div class="mt-3 flex justify-end gap-2">
          <Button
            size="sm"
            variant="ghost"
            onclick={() => {
              creationOuverte = false;
              nouveauChemin = '';
            }}>Annuler</Button
          >
          <Button size="sm" type="submit">Créer</Button>
        </div>
      </form>
    </div>
  </div>
{/if}

<ConfirmDialog
  bind:open={suppressionOuverte}
  title="Supprimer ce fichier ?"
  message={cibleSuppression ? `« ${cibleSuppression} » sera perdu.` : ''}
  confirmLabel="Supprimer"
  variant="danger"
  onConfirm={supprimer}
  onCancel={() => (cibleSuppression = null)}
/>
