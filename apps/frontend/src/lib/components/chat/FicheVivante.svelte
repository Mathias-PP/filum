<script lang="ts">
  import { tick } from 'svelte';
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import type { Card, CardDetail, Source } from '$lib/api/types';
  import { comparerFiches, type Cible } from '$lib/agent/suiviFiche';
  import { CLASSES_VERDICT, lireVerdict } from '$lib/utils/excerpt-verdict';
  import { stanceStyle } from '$lib/utils/stance';
  import { montrerAvisRetractation, retractionBadge } from '$lib/utils/retraction';
  import { openAccessBadge } from '$lib/utils/open-access';

  interface Props {
    /** Slug de la fiche nommée en dernier par un outil, null avant. */
    slug: string | null;
    /** Nombre d'actions terminées : chaque changement relit la fiche. */
    empreinte: number;
    onfermer: () => void;
  }

  let { slug, empreinte, onfermer }: Props = $props();

  let fiche = $state<Card | null>(null);
  let sources = $state<Source[]>([]);
  let etat = $state<'vide' | 'chargement' | 'pret' | 'introuvable' | 'erreur'>('vide');
  // Ce que la dernière action a modifié : éclairé un instant.
  let sourcesRecentes = $state<Set<string>>(new Set());
  let extraitsRecents = $state<Set<string>>(new Set());
  let minuterieEclairage: ReturnType<typeof setTimeout> | undefined;

  // Suivi automatique, actif par défaut : la fiche défile jusqu'à l'élément que
  // l'agent vient d'ajouter. Sans lui, un extrait posé au bas d'une fiche de
  // quinze sources passait inaperçu. Désactivé, on navigue sans être déplacé.
  let suivi = $state(true);
  let derniereCible: Cible | null = null;
  let defilement = $state<HTMLDivElement | null>(null);

  // Graphe en tête de panneau, repliable indépendamment du panneau. Le choix
  // est retenu dans le navigateur : qui l'a replié ne veut pas le revoir à
  // chaque conversation.
  const PREFERENCE_GRAPHE = 'philum:fiche-graphe';
  let grapheOuvert = $state(lirePreferenceGraphe());
  // Composant chargé à la demande, comme sur la page publique : c'est un
  // bundle d3 que le panneau n'a pas à payer tant que le graphe est replié.
  let Graphe = $state<any>(null);

  function lirePreferenceGraphe(): boolean {
    try {
      return localStorage.getItem(PREFERENCE_GRAPHE) !== 'replie';
    } catch {
      return true;
    }
  }

  function basculerGraphe() {
    grapheOuvert = !grapheOuvert;
    try {
      localStorage.setItem(PREFERENCE_GRAPHE, grapheOuvert ? 'ouvert' : 'replie');
    } catch {
      // Préférence non retenue : le graphe se rouvrira à la prochaine visite.
    }
  }

  $effect(() => {
    if (grapheOuvert && !Graphe) {
      void import('$lib/components/SourceGraph.svelte').then((m) => (Graphe = m.default));
    }
  });

  // Les outils nomment la fiche par son slug, l'API la lit par son id.
  const ids = new Map<string, string>();
  let jeton = 0;

  async function idDe(s: string): Promise<string | null> {
    const connu = ids.get(s);
    if (connu) return connu;
    const fiches = await api.cards.list({ limit: 100 });
    for (const f of fiches) ids.set(f.slug, f.id);
    return ids.get(s) ?? null;
  }

  async function suivre(cible: Cible) {
    await tick();
    const selecteur =
      cible.kind === 'extrait' ? `[data-extrait="${cible.id}"]` : `[data-source="${cible.id}"]`;
    const element = defilement?.querySelector<HTMLElement>(selecteur);
    if (!element) return;
    const reduit = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    element.scrollIntoView({ block: 'center', behavior: reduit ? 'auto' : 'smooth' });
  }

  function basculerSuivi() {
    suivi = !suivi;
    // Reprendre le suivi recale tout de suite sur le dernier ajout, plutôt que
    // d'attendre la prochaine action de l'agent.
    if (suivi && derniereCible) void suivre(derniereCible);
  }

  async function charger(s: string) {
    const moi = ++jeton;
    if (!fiche) etat = 'chargement';
    try {
      const id = await idDe(s);
      if (moi !== jeton) return;
      if (!id) {
        etat = 'introuvable';
        return;
      }
      const [lue, liste] = await Promise.all([api.cards.get(id), api.sources.list(id)]);
      if (moi !== jeton) return;
      // Pas d'éclairage ni de défilement au premier affichage ni au changement
      // de fiche : seulement ce qu'une action vient de modifier.
      const ecart = comparerFiches(fiche?.id === lue.id ? sources : null, liste);
      fiche = lue;
      sources = liste;
      etat = 'pret';
      if (ecart.sources.size > 0 || ecart.extraits.size > 0) {
        sourcesRecentes = ecart.sources;
        extraitsRecents = ecart.extraits;
        clearTimeout(minuterieEclairage);
        minuterieEclairage = setTimeout(() => {
          sourcesRecentes = new Set();
          extraitsRecents = new Set();
        }, 2500);
      }
      if (ecart.cible) {
        derniereCible = ecart.cible;
        if (suivi) await suivre(ecart.cible);
      }
    } catch {
      // Une lecture ratée garde l'affichage précédent : la suivante rattrapera.
      if (moi === jeton) etat = fiche ? 'pret' : 'erreur';
    }
  }

  // Relit la fiche à chaque action terminée, avec un court délai : dix
  // extraits posés d'affilée ne doivent pas faire dix lectures.
  $effect(() => {
    const s = slug;
    void empreinte;
    if (!s) {
      etat = 'vide';
      return;
    }
    const minuterie = setTimeout(() => void charger(s), 600);
    return () => clearTimeout(minuterie);
  });

  $effect(() => () => clearTimeout(minuterieEclairage));

  const nbExtraits = $derived(sources.reduce((n, s) => n + s.excerpts.length, 0));
  const nbRetrouves = $derived(
    sources.reduce(
      (n, s) =>
        n +
        s.excerpts.filter((e) => e.verified_status === 'found' || e.verified_status === 'moved')
          .length,
      0
    )
  );
  const nbArchivees = $derived(sources.filter((s) => s.archive_status === 'archived').length);
  const nbLibres = $derived(sources.filter((s) => openAccessBadge(s.oa_status)?.isFree).length);
  const nbRetractees = $derived(sources.filter((s) => s.retraction_status === 'retracted').length);

  // Le graphe attend une fiche complète, telle que la page publique la reçoit.
  // Le panneau la reconstitue avec ce qu'il lit déjà : la fiche, ses sources
  // et le créateur connecté, brouillons compris.
  const ficheDetaillee = $derived.by<CardDetail | null>(() => {
    if (!fiche) return null;
    const moi = $page.data.user;
    const compter = (genre: string) => sources.filter((s) => s.author_kind === genre).length;
    const archivables = sources.filter((s) => s.url).length;
    return {
      ...fiche,
      creator: {
        slug: moi?.username ?? '',
        display_name: moi?.display_name ?? null,
        bio: null,
        avatar_url: moi?.avatar_url ?? null,
        public_key: '',
      },
      sources,
      stats: {
        total_sources: sources.length,
        chercheur: compter('chercheur'),
        media: compter('media'),
        institution_publique: compter('institution_publique'),
        individu: compter('individu'),
        archived_count: nbArchivees,
        archivable_count: archivables,
        all_archived: archivables > 0 && nbArchivees >= archivables,
      },
    };
  });
</script>

<aside
  class="flex h-full min-h-0 w-full flex-col border-l border-border bg-surface-primary lg:w-[26rem] xl:w-[30rem]"
  aria-label="Fiche en cours"
>
  <div class="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
    <p
      class="min-w-0 flex-1 truncate text-xs font-medium uppercase tracking-wider text-ink-tertiary"
    >
      Fiche en direct
    </p>
    <!-- Un œil ouvert tant que la fiche suit l'agent, barré quand on navigue
         librement : c'est le regard qu'on délègue ou qu'on reprend. -->
    <button
      type="button"
      class="shrink-0 rounded p-1 transition-colors hover:text-ink-primary"
      class:text-info={suivi}
      class:bg-info-bg={suivi}
      class:text-ink-tertiary={!suivi}
      aria-pressed={suivi}
      aria-label={suivi ? 'Arrêter de suivre les modifications' : 'Suivre les modifications'}
      title={suivi
        ? 'Suivi activé : la fiche défile jusqu’à chaque ajout de l’agent. Cliquer pour naviguer librement.'
        : 'Navigation libre : la fiche ne bouge plus. Cliquer pour suivre à nouveau les ajouts de l’agent.'}
      onclick={basculerSuivi}
    >
      {#if suivi}
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      {:else}
        <svg
          viewBox="0 0 24 24"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M3 3l18 18" />
          <path
            d="M10.6 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.2M6.6 6.6A17.5 17.5 0 0 0 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"
          />
          <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
        </svg>
      {/if}
    </button>
    {#if fiche}
      <a
        href="/dashboard/new/{fiche.id}/sources"
        class="shrink-0 text-xs text-info hover:underline"
      >
        Ouvrir l’éditeur
      </a>
    {/if}
    <button
      type="button"
      class="shrink-0 rounded px-1.5 py-0.5 text-ink-tertiary hover:bg-surface-tertiary hover:text-ink-primary"
      aria-label="Fermer la fiche"
      onclick={onfermer}
    >
      ×
    </button>
  </div>

  {#if fiche && etat === 'pret'}
    <!-- Le graphe reste en tête pendant que la liste défile : il montre la forme
         de la bibliographie qui se construit, la liste montre son détail. -->
    <section class="shrink-0 border-b border-border" aria-label="Graphe de la fiche">
      <button
        type="button"
        class="flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs text-ink-tertiary hover:text-ink-primary"
        aria-expanded={grapheOuvert}
        aria-controls="graphe-fiche-vivante"
        title={grapheOuvert ? 'Réduire le graphe' : 'Afficher le graphe'}
        onclick={basculerGraphe}
      >
        <svg
          viewBox="0 0 24 24"
          width="12"
          height="12"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
          class={grapheOuvert
            ? 'shrink-0 transition-transform'
            : 'shrink-0 -rotate-90 transition-transform'}
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
        <span class="flex-1">Graphe</span>
        {#if !grapheOuvert}
          <span>{sources.length} source{sources.length > 1 ? 's' : ''}</span>
        {/if}
      </button>
      {#if grapheOuvert}
        <div id="graphe-fiche-vivante" class="relative h-44 overflow-hidden border-t border-border">
          {#if Graphe && ficheDetaillee}
            <Graphe card={ficheDetaillee} compact />
          {:else}
            <p class="p-3 text-xs text-ink-tertiary">Chargement du graphe…</p>
          {/if}
        </div>
      {/if}
    </section>
  {/if}

  <div
    bind:this={defilement}
    class="min-h-0 flex-1 overflow-y-auto px-3 py-3"
    aria-live="polite"
    aria-busy={etat === 'chargement'}
  >
    {#if etat === 'vide'}
      <p class="text-sm text-ink-tertiary">
        La fiche s’affichera ici dès que l’agent en ouvre ou en crée une, et se mettra à jour à
        chacune de ses actions.
      </p>
    {:else if etat === 'chargement'}
      <p class="text-sm text-ink-tertiary">Lecture de la fiche…</p>
    {:else if etat === 'introuvable'}
      <p class="text-sm text-ink-tertiary">
        La fiche « {slug} » ne figure pas parmi vos fiches. Elle a peut-être été supprimée.
      </p>
    {:else if etat === 'erreur'}
      <p class="text-sm text-danger">
        La fiche n’a pas pu être lue. Elle sera relue à la prochaine action de l’agent.
      </p>
    {:else if fiche}
      <h2 class="font-serif text-lg leading-snug text-ink-primary [overflow-wrap:anywhere]">
        {fiche.title}
      </h2>
      <p class="mt-0.5 text-xs text-ink-tertiary">
        {fiche.status === 'published' ? 'Publiée' : 'Brouillon'}
        {#if fiche.status === 'published' && $page.data.user}
          ·
          <a
            href="/@{$page.data.user.username}/{fiche.slug}"
            class="text-info hover:underline"
            target="_blank"
            rel="noopener noreferrer">Voir la page publique</a
          >
        {/if}
      </p>
      <!-- Une ligne de faits comptes, pas un score : c'est ce que les lecteurs
           acceptent (repartition decrite plutot que verdict). -->
      <p class="mt-2 text-xs text-ink-secondary">
        {sources.length} source{sources.length > 1 ? 's' : ''} · {nbArchivees} archivée{nbArchivees >
        1
          ? 's'
          : ''} · {nbLibres} en accès libre · {nbRetrouves} extrait{nbRetrouves > 1 ? 's' : ''} retrouvé{nbRetrouves >
        1
          ? 's'
          : ''} sur {nbExtraits} · {nbRetractees} rétractée{nbRetractees > 1 ? 's' : ''}
      </p>

      {#if sources.length === 0}
        <p class="mt-4 text-sm text-ink-tertiary">Pas encore de source.</p>
      {:else}
        <ol class="mt-3 space-y-3">
          {#each sources as source, rang (source.id)}
            {@const eclairee = sourcesRecentes.has(source.id)}
            <li
              data-source={source.id}
              class="rounded-lg border p-2 transition-shadow duration-500"
              class:border-border={!eclairee}
              class:border-info={eclairee}
              class:ring-2={eclairee}
              class:ring-info={eclairee}
            >
              <div class="flex gap-2">
                <span class="shrink-0 text-xs text-ink-tertiary">{rang + 1}.</span>
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="min-w-0 flex-1 text-sm font-medium text-ink-primary [overflow-wrap:anywhere] hover:underline"
                >
                  {source.title || source.url}
                </a>
              </div>
              <div class="mt-1 flex flex-wrap gap-1 text-[11px]">
                {#if stanceStyle(source.stance)}
                  {@const st = stanceStyle(source.stance)!}
                  <span class="rounded px-1.5 py-0.5 {st.bgClass}" title={st.help}>{st.label}</span>
                {/if}
                {#if montrerAvisRetractation(source.retraction_status, source.category)}
                  {@const rb = retractionBadge(source.retraction_status)!}
                  <span class="rounded px-1.5 py-0.5 {rb.className}" title={rb.help}
                    >{rb.label}</span
                  >
                {/if}
                {#if openAccessBadge(source.oa_status)?.isFree}
                  {@const ob = openAccessBadge(source.oa_status)!}
                  <span class="rounded px-1.5 py-0.5 {ob.className}" title={ob.help}
                    >{ob.label}</span
                  >
                {/if}
                {#if source.archive_url}
                  <a
                    href={source.archive_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="rounded bg-surface-tertiary px-1.5 py-0.5 text-ink-secondary hover:underline"
                    >Archivée</a
                  >
                {/if}
              </div>
              {#if source.excerpts.length > 0}
                <ul class="mt-2 space-y-1.5">
                  {#each source.excerpts as extrait (extrait.id)}
                    {@const verdict = lireVerdict(extrait)}
                    {@const neuf = extraitsRecents.has(extrait.id)}
                    <li
                      data-extrait={extrait.id}
                      class="rounded text-xs transition-colors duration-500"
                      class:bg-info-bg={neuf}
                      class:px-1={neuf}
                    >
                      <p class="italic text-ink-secondary [overflow-wrap:anywhere]">
                        « {extrait.text} »
                      </p>
                      <span
                        class="mt-0.5 inline-block rounded px-1.5 py-0.5 {CLASSES_VERDICT[
                          verdict.ton
                        ]}"
                        title={verdict.detail}>{verdict.label}</span
                      >
                    </li>
                  {/each}
                </ul>
              {/if}
            </li>
          {/each}
        </ol>
      {/if}
    {/if}
  </div>
</aside>
