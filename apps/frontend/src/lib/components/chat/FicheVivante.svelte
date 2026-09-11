<script lang="ts">
  import { page } from '$app/stores';
  import { api } from '$lib/api';
  import type { Card, Source } from '$lib/api/types';
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
  // Sources modifiées par la dernière action : elles s'éclairent un instant.
  let recentes = $state<Set<string>>(new Set());

  // Les outils nomment la fiche par son slug, l'API la lit par son id.
  const ids = new Map<string, string>();
  let signatures = new Map<string, string>();
  let jeton = 0;

  async function idDe(s: string): Promise<string | null> {
    const connu = ids.get(s);
    if (connu) return connu;
    const fiches = await api.cards.list({ limit: 100 });
    for (const f of fiches) ids.set(f.slug, f.id);
    return ids.get(s) ?? null;
  }

  function signature(s: Source): string {
    return JSON.stringify([
      s.title,
      s.stance,
      s.retraction_status,
      s.oa_status,
      s.archive_status,
      s.annotation,
      s.excerpts.map((e) => [e.id, e.text, e.context, e.verified_status]),
    ]);
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
      const changees = new Set<string>();
      const nouvelles = new Map<string, string>();
      for (const source of liste) {
        const sig = signature(source);
        nouvelles.set(source.id, sig);
        // Pas d'éclairage au premier affichage ni au changement de fiche :
        // seulement ce qu'une action vient de modifier.
        if (fiche?.id === lue.id && signatures.get(source.id) !== sig) changees.add(source.id);
      }
      signatures = nouvelles;
      fiche = lue;
      sources = liste;
      etat = 'pret';
      if (changees.size > 0) {
        recentes = changees;
        setTimeout(() => {
          if (moi === jeton) recentes = new Set();
        }, 2500);
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

  <div
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
            {@const eclairee = recentes.has(source.id)}
            <li
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
                    <li class="text-xs">
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
