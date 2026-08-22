<script lang="ts">
  import { onMount } from 'svelte';
  import { agentApi, type WorkspaceTreeEntry } from '$lib/api/agent';
  import { ApiError } from '$lib/api';
  import { Button, ConfirmDialog, toast } from '$lib/components';

  // Etat de l'arbre : liste plate ordonnee par path. Le serveur envoie
  // `contract` (phrase de contrat) et `layer` (L0/L1/L2/L3) pour chaque
  // fichier, deduits du frontmatter YAML ou fallback conventionnel.
  let entrees = $state<WorkspaceTreeEntry[]>([]);
  let chargementArbre = $state(true);
  let chargementFichier = $state(false);
  let cheminActif = $state<string>('');
  let contenu = $state('');
  let contenuOriginal = $state('');
  let messageErr = $state('');

  let creationOuverte = $state(false);
  let nouveauChemin = $state('');
  let suppressionOuverte = $state(false);
  let cibleSuppression = $state<string | null>(null);

  const modifie = $derived(contenu !== contenuOriginal);

  // Regroupement par section ICM. On garde le vocabulaire ICM (Layer 0..3)
  // avec un titre court, sobre, non-marketing. Les fichiers utilisateurs
  // hors racines conventionnelles tombent dans "Autre".
  interface Section {
    slug: string;
    titre: string;
    aide: string;
    fichiers: WorkspaceTreeEntry[];
  }

  const sections = $derived.by<Section[]>(() => {
    const routing: WorkspaceTreeEntry[] = [];
    const references: WorkspaceTreeEntry[] = [];
    const modeles: WorkspaceTreeEntry[] = [];
    const pipeline: WorkspaceTreeEntry[] = [];
    const runs: WorkspaceTreeEntry[] = [];
    const autre: WorkspaceTreeEntry[] = [];

    for (const e of entrees) {
      if (e.type !== 'file') continue;
      if (e.layer === 'L0' || e.layer === 'L1') routing.push(e);
      else if (e.layer === 'L2') pipeline.push(e);
      else if (e.path.startsWith('_core/templates/')) modeles.push(e);
      else if (e.path.startsWith('shared/') || e.layer === 'L3') references.push(e);
      else if (e.path.startsWith('runs/')) runs.push(e);
      else autre.push(e);
    }

    const out: Section[] = [
      {
        slug: 'routing',
        titre: 'Routing (L0, L1)',
        aide: "Points d'entrée que l'agent lit d'abord pour savoir où aller.",
        fichiers: routing,
      },
      {
        slug: 'references',
        titre: 'Références (L3 factory)',
        aide: 'Règles stables lues à chaque conversation. Modifier ici change le comportement de tout agent qui inclut ces fichiers dans son contexte.',
        fichiers: references,
      },
      {
        slug: 'modeles',
        titre: 'Modèles (L3 factory)',
        aide: 'Squelettes copiés dans les runs pour démarrer une fiche, une source ou un extrait.',
        fichiers: modeles,
      },
      {
        slug: 'pipeline',
        titre: 'Pipeline (L2 contrats de stage)',
        aide: 'Contrat de chaque étape : inputs, process, outputs. Suivis en séquence pour construire une fiche du brief à la publication.',
        fichiers: pipeline,
      },
    ];
    if (runs.length > 0) {
      out.push({
        slug: 'runs',
        titre: 'Runs (L4 product)',
        aide: 'Fiches en cours de construction. Un dossier par fiche, écrasé à chaque étape.',
        fichiers: runs,
      });
    }
    if (autre.length > 0) {
      out.push({
        slug: 'autre',
        titre: 'Autre',
        aide: 'Fichiers ajoutés en dehors des racines conventionnelles ICM.',
        fichiers: autre,
      });
    }
    return out.filter((s) => s.fichiers.length > 0);
  });

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
        Configuration ICM de l'agent. Chaque fichier est lu à un moment précis d'une conversation
        pour orienter les réponses.
      </p>
    </div>
    <div class="flex gap-2">
      <Button
        size="sm"
        variant="ghost"
        onclick={reSeed}
        title="Réinsère les fichiers du template ICM qui manquent"
      >
        Restaurer template
      </Button>
      <Button size="sm" onclick={() => (creationOuverte = true)}>Nouveau fichier</Button>
    </div>
  </div>

  <div class="grid gap-4 lg:grid-cols-[22rem_1fr]">
    <aside class="space-y-4">
      {#if chargementArbre}
        <p class="p-2 text-sm text-ink-tertiary">Chargement…</p>
      {:else if sections.length === 0}
        <p
          class="rounded-lg border border-subtle bg-surface-secondary p-3 text-sm text-ink-tertiary"
        >
          Workspace vide. Cliquez « Restaurer template » pour insérer le seed ICM.
        </p>
      {:else}
        {#each sections as section (section.slug)}
          <div class="rounded-lg border border-subtle bg-surface-secondary p-3">
            <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary">
              {section.titre}
            </h2>
            <p class="mt-1 text-xs text-ink-secondary">{section.aide}</p>
            <ul class="mt-2 space-y-1.5">
              {#each section.fichiers as f (f.path)}
                <li>
                  <div class="flex items-start gap-1">
                    <button
                      type="button"
                      class="flex-1 rounded px-2 py-1 text-left hover:bg-surface-tertiary"
                      class:bg-surface-tertiary={cheminActif === f.path}
                      onclick={() => ouvrir(f.path)}
                    >
                      <span
                        class="block truncate font-mono text-xs"
                        class:font-medium={cheminActif === f.path}
                        class:text-ink-primary={cheminActif === f.path}
                        class:text-ink-secondary={cheminActif !== f.path}
                      >
                        {f.path}
                      </span>
                      {#if f.contract}
                        <span class="mt-0.5 block text-xs text-ink-tertiary">{f.contract}</span>
                      {/if}
                    </button>
                    <button
                      type="button"
                      class="px-1 text-ink-tertiary hover:text-danger"
                      title="Supprimer"
                      onclick={() => {
                        cibleSuppression = f.path;
                        suppressionOuverte = true;
                      }}
                    >
                      ×
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          </div>
        {/each}
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
