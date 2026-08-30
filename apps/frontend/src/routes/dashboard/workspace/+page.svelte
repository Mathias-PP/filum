<script lang="ts">
  import { onMount } from 'svelte';
  import {
    agentApi,
    type AgentDefinition,
    type AgentDefinitionRejected,
    type WorkspaceTreeEntry,
  } from '$lib/api/agent';
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

  // Les agents viennent d'un endpoint separe : le serveur seul sait quels
  // outils il expose reellement et pourquoi un fichier ne charge pas.
  let definitions = $state<AgentDefinition[]>([]);
  let rejets = $state<AgentDefinitionRejected[]>([]);

  const agentParChemin = $derived(new Map(definitions.map((a) => [a.path, a])));
  const rejetParChemin = $derived(new Map(rejets.map((r) => [r.path, r.raison])));

  // Index inverse : sous un fichier de `shared/`, savoir quels agents le lisent
  // evite de modifier une regle sans voir qui elle touche.
  const utilisePar = $derived.by(() => {
    const index = new Map<string, string[]>();
    for (const agent of definitions) {
      for (const chemin of agent.context) {
        index.set(chemin, [...(index.get(chemin) ?? []), agent.name]);
      }
    }
    return index;
  });

  let creationOuverte = $state(false);
  let nouveauChemin = $state('');
  let suppressionOuverte = $state(false);
  let cibleSuppression = $state<string | null>(null);

  const modifie = $derived(contenu !== contenuOriginal);

  // Le workspace vide et le workspace peuple appellent le meme endpoint mais
  // ne racontent pas la meme chose : « Initialiser » cree tout, « Restaurer »
  // ne recolle que les fichiers effaces sans toucher aux modifications.
  const vide = $derived(!chargementArbre && entrees.length === 0);

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
    const agents: WorkspaceTreeEntry[] = [];
    const routing: WorkspaceTreeEntry[] = [];
    const references: WorkspaceTreeEntry[] = [];
    const modeles: WorkspaceTreeEntry[] = [];
    const pipeline: WorkspaceTreeEntry[] = [];
    const runs: WorkspaceTreeEntry[] = [];
    const autre: WorkspaceTreeEntry[] = [];

    for (const e of entrees) {
      if (e.type !== 'file') continue;
      // Avant le test sur `layer` : un agent declare le sien, il finirait
      // sinon melange aux contrats de stage qui portent la meme valeur.
      if (e.path.startsWith('agents/')) agents.push(e);
      else if (e.layer === 'L0' || e.layer === 'L1') routing.push(e);
      else if (e.layer === 'L2') pipeline.push(e);
      else if (e.path.startsWith('_core/templates/')) modeles.push(e);
      else if (e.path.startsWith('shared/') || e.layer === 'L3') references.push(e);
      else if (e.path.startsWith('runs/')) runs.push(e);
      else autre.push(e);
    }

    const out: Section[] = [
      {
        slug: 'agents',
        titre: 'Agents',
        aide: "Un fichier par agent du chat : les outils qu'il peut appeler, les fichiers qu'il lit d'office et son rôle. Éditer le fichier suffit, il n'y a pas d'autre endroit où le déclarer.",
        fichiers: agents,
      },
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
      const [arbre, liste] = await Promise.all([
        agentApi.workspace.tree(),
        agentApi.definitions.list(),
      ]);
      entrees = arbre;
      definitions = liste.agents;
      rejets = liste.rejected;
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Impossible de lire le workspace.');
      entrees = [];
      definitions = [];
      rejets = [];
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

  let seedEnCours = $state(false);

  async function reSeed() {
    const etaitVide = vide;
    seedEnCours = true;
    try {
      const res = await agentApi.workspace.seed();
      if (res.seeded === 0) {
        toast.success('Aucun fichier manquant : la configuration est complète.');
      } else if (etaitVide) {
        toast.success(`Configuration initialisée : ${res.seeded} fichiers créés.`);
      } else {
        toast.success(
          `${res.seeded} fichier${res.seeded > 1 ? 's' : ''} manquant${res.seeded > 1 ? 's' : ''} restauré${res.seeded > 1 ? 's' : ''}.`
        );
      }
      await chargerArbre();
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Opération impossible.');
    } finally {
      seedEnCours = false;
    }
  }

  // Mise a jour depuis le modele livre. Le seed d'origine n'inserait que les
  // chemins absents : il protegeait les editions, mais figeait le workspace a
  // sa date de creation, et les evolutions du modele n'arrivaient jamais.
  let syncEnCours = $state(false);
  let divergents = $state<string[]>([]);
  let aAdopter = $state<Set<string>>(new Set());

  async function mettreAJour(adopt: string[] = []) {
    syncEnCours = true;
    try {
      const res = await agentApi.workspace.sync(adopt);
      const faits = [
        res.ajoutes.length && `${res.ajoutes.length} ajouté${res.ajoutes.length > 1 ? 's' : ''}`,
        res.mis_a_jour.length &&
          `${res.mis_a_jour.length} actualisé${res.mis_a_jour.length > 1 ? 's' : ''}`,
        res.adoptes.length && `${res.adoptes.length} remplacé${res.adoptes.length > 1 ? 's' : ''}`,
      ].filter(Boolean);
      toast.success(faits.length ? `${faits.join(', ')}.` : 'Le workspace est déjà à jour.');
      // Les fichiers que vous avez modifiés ne sont jamais repris d'office :
      // ils restent la pour un choix explicite, fichier par fichier.
      divergents = res.divergents;
      aAdopter = new Set();
      await chargerArbre();
      if (cheminActif) await ouvrir(cheminActif);
    } catch (e) {
      toast.danger(e instanceof ApiError ? e.message : 'Mise à jour impossible.');
    } finally {
      syncEnCours = false;
    }
  }

  function basculerAdoption(chemin: string) {
    const suivant = new Set(aAdopter);
    if (suivant.has(chemin)) suivant.delete(chemin);
    else suivant.add(chemin);
    aAdopter = suivant;
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
        variant={vide ? 'primary' : 'ghost'}
        disabled={seedEnCours || chargementArbre}
        onclick={reSeed}
        title={vide
          ? 'Crée les fichiers de configuration fournis avec Philum'
          : 'Recrée les fichiers fournis qui ont été supprimés. Vos modifications ne sont jamais écrasées.'}
      >
        {seedEnCours ? 'En cours…' : vide ? 'Initialiser la configuration' : 'Restaurer template'}
      </Button>
      {#if !vide}
        <Button
          size="sm"
          variant="ghost"
          disabled={syncEnCours || chargementArbre}
          onclick={() => void mettreAJour()}
          title="Ajoute les fichiers livrés absents et actualise ceux que vous n'avez pas modifiés. Vos modifications ne sont jamais écrasées."
        >
          {syncEnCours ? 'En cours…' : 'Mettre à jour'}
        </Button>
        <Button size="sm" onclick={() => (creationOuverte = true)}>Nouveau fichier</Button>
      {/if}
    </div>
  </div>

  {#if divergents.length > 0}
    <!-- Ces fichiers different du modele livre et portent peut-etre votre
         travail : la mise a jour les a laisses intacts. Les reprendre est un
         choix explicite, fichier par fichier. -->
    <div class="mb-4 rounded-lg border border-border bg-surface-secondary p-4">
      <p class="text-sm font-medium text-ink-primary">
        {divergents.length} fichier{divergents.length > 1 ? 's' : ''} que vous avez modifié{divergents.length >
        1
          ? 's'
          : ''}
      </p>
      <p class="mt-1 text-sm text-ink-secondary">
        Ils n'ont pas été touchés. Cochez ceux dont vous voulez la version livrée à la place de la
        vôtre : votre contenu actuel sera remplacé.
      </p>
      <ul class="mt-3 space-y-1">
        {#each divergents as chemin (chemin)}
          <li>
            <label class="flex items-center gap-2 text-sm text-ink-primary">
              <input
                type="checkbox"
                checked={aAdopter.has(chemin)}
                onchange={() => basculerAdoption(chemin)}
              />
              <span class="font-mono">{chemin}</span>
            </label>
          </li>
        {/each}
      </ul>
      <div class="mt-3">
        <Button
          size="sm"
          variant="ghost"
          disabled={syncEnCours || aAdopter.size === 0}
          onclick={() => void mettreAJour([...aAdopter])}
        >
          {syncEnCours
            ? 'En cours…'
            : `Remplacer ${aAdopter.size} fichier${aAdopter.size > 1 ? 's' : ''} par la version livrée`}
        </Button>
      </div>
    </div>
  {/if}

  <!-- Sur grand ecran, les deux colonnes tiennent dans la hauteur de la fenetre
       et defilent chacune pour leur compte. Sans cette borne, l'explorateur
       poussait la page a mesure que les fichiers s'ajoutaient : on perdait
       l'editeur de vue en cherchant un fichier, et l'inverse. Sous `lg`, la
       colonne unique reprend le flux normal. -->
  <div class="grid gap-4 lg:h-[calc(100dvh-15rem)] lg:grid-cols-[22rem_1fr]">
    <aside class="space-y-4 lg:overflow-x-hidden lg:overflow-y-auto lg:pr-1">
      {#if chargementArbre}
        <p class="p-2 text-sm text-ink-tertiary">Chargement…</p>
      {:else if sections.length === 0}
        <div class="rounded-lg border border-border bg-surface-secondary p-4">
          <p class="text-sm font-medium text-ink-primary">Aucun fichier de configuration</p>
          <p class="mt-1 text-sm text-ink-secondary">
            Philum fournit un jeu de fichiers prêts à l'emploi : règles de rédaction, garde-fous,
            contrats de chaque étape de construction d'une fiche. Ils sont à vous : modifiez-les,
            supprimez-en, ajoutez les vôtres.
          </p>
          <p class="mt-2 text-sm text-ink-tertiary">
            Utilisez « Initialiser la configuration » en haut de page.
          </p>
        </div>
      {:else}
        {#each sections as section (section.slug)}
          <div class="rounded-lg border border-border bg-surface-secondary p-3">
            <h2 class="text-xs font-medium uppercase tracking-wider text-ink-tertiary">
              {section.titre}
            </h2>
            <p class="mt-1 text-xs text-ink-secondary">{section.aide}</p>
            <ul class="mt-2 space-y-1.5">
              {#each section.fichiers as f (f.path)}
                {@const agent = agentParChemin.get(f.path)}
                {@const rejet = rejetParChemin.get(f.path)}
                {@const lecteurs = utilisePar.get(f.path)}
                <li>
                  <div class="flex items-start gap-1">
                    <button
                      type="button"
                      class="flex-1 rounded px-2 py-1 text-left hover:bg-surface-tertiary"
                      class:bg-surface-tertiary={cheminActif === f.path}
                      onclick={() => ouvrir(f.path)}
                    >
                      {#if agent}
                        <span class="flex items-center gap-1.5">
                          <span class="truncate text-xs font-medium text-ink-primary"
                            >{agent.name}</span
                          >
                          <span
                            class="shrink-0 rounded px-1 py-0.5 text-[10px] text-ink-tertiary"
                            class:bg-surface-tertiary={agent.builtin}
                            title={agent.builtin
                              ? 'Fourni avec Philum. « Restaurer template » le recrée si vous le supprimez.'
                              : 'Ajouté par vous.'}
                          >
                            {agent.builtin ? 'Livré avec Philum' : 'Personnalisé'}
                          </span>
                        </span>
                      {/if}
                      <span
                        class="block truncate font-mono text-xs"
                        class:font-medium={cheminActif === f.path && !agent}
                        class:text-ink-primary={cheminActif === f.path && !agent}
                        class:text-ink-secondary={cheminActif !== f.path || agent}
                      >
                        {f.path}
                      </span>
                      {#if f.contract}
                        <span class="mt-0.5 block text-xs text-ink-tertiary">{f.contract}</span>
                      {/if}
                      {#if agent}
                        <span class="mt-0.5 block text-xs text-ink-tertiary">
                          {agent.tools.length} outils · {agent.context.length} fichiers de contexte
                        </span>
                        {#if agent.tools_absents.length > 0}
                          <span class="mt-0.5 block text-xs text-warning">
                            Indisponible sur ce serveur : {agent.tools_absents.join(', ')}
                          </span>
                        {/if}
                      {/if}
                      {#if rejet}
                        <span class="mt-0.5 block text-xs text-danger">
                          Agent non chargé : {rejet}
                        </span>
                      {/if}
                      {#if lecteurs && lecteurs.length > 0}
                        <span class="mt-0.5 block text-xs text-ink-tertiary">
                          Lu par : {lecteurs.join(', ')}
                        </span>
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

    <section
      class="flex flex-col rounded-lg border border-border bg-surface-primary p-3 lg:min-h-0"
    >
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
          class="h-96 w-full resize-y rounded border border-border bg-surface-primary p-3 font-mono text-sm text-ink-primary lg:h-auto lg:min-h-0 lg:flex-1 lg:resize-none"
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
    <div class="w-full max-w-md rounded-lg border border-border bg-surface-primary p-4 shadow-lg">
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
          class="w-full rounded border border-border bg-surface-secondary px-3 py-2 font-mono text-sm"
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
