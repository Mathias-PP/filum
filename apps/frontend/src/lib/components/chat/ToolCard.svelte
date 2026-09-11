<script lang="ts">
  import { rendreOutil } from '$lib/agent/toolLabels';

  interface Props {
    name: string;
    args: Record<string, unknown>;
    result?: Record<string, unknown> | null;
  }

  let { name, args, result = null }: Props = $props();

  let ouvert = $state(false);

  const echoue = $derived(Boolean(result && 'error' in result));
  const etat = $derived(result === null ? 'En cours…' : echoue ? 'Échec' : 'Terminé');
  const raison = $derived.by(() => {
    if (!result || !('error' in result)) return null;
    const err = result.error;
    if (typeof err === 'string') return err;
    return JSON.stringify(err);
  });
  const rendu = $derived(rendreOutil(name, args, result));

  // Ce que le serveur a reellement inscrit. `add_excerpt` ne recopie pas le
  // texte du modele : il relit la page et ecrit les caracteres de la source.
  // Montrer le resultat plutot que la demande, c'est la seule facon de voir
  // la difference.
  const extrait = $derived.by(() => {
    if (!result || echoue) return null;
    const texte = result.text;
    const statut = result.verified_status;
    if (typeof texte !== 'string' || typeof statut !== 'string') return null;
    return { texte, statut };
  });

  const verdict = $derived(
    extrait?.statut === 'found'
      ? 'Retrouvé mot pour mot dans la source.'
      : extrait?.statut === 'unreadable'
        ? 'Source illisible (PDF sans texte, mur anti-bot ou paywall) : extrait non vérifié.'
        : null
  );

  // `add_source` accepte des extraits en ligne. Taire ceux qui ont été écartés
  // laisserait croire que tous sont posés.
  const bilanExtraits = $derived.by(() => {
    if (!result || echoue) return null;
    const poses = Array.isArray(result.excerpts) ? result.excerpts.length : 0;
    const refuses = Array.isArray(result.excerpts_refuses) ? result.excerpts_refuses.length : 0;
    if (poses === 0 && refuses === 0) return null;
    return { poses, refuses };
  });

  // Noms lisibles des arguments les plus courants. Le JSON brut reste
  // accessible plus bas : ce tableau sert a lire, pas a deboguer.
  const CLES: Record<string, string> = {
    url: 'Adresse',
    title: 'Titre',
    text: 'Texte',
    query: 'Recherche',
    q: 'Recherche',
    slug: 'Fiche',
    card_slug: 'Fiche',
    card_id: 'Fiche',
    source_id: 'Source',
    excerpt_id: 'Extrait',
    context: 'Mise en situation',
    annotation: 'Note du créateur',
    stance: 'Relation à la source',
    category: 'Catégorie',
    author_kind: 'Type d’auteur',
    authors: 'Auteurs',
    content_url: 'Contenu',
    path: 'Fichier',
    content: 'Contenu du fichier',
    visibility: 'Visibilité',
    provided_text: 'Texte fourni',
  };

  const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const LONGUEUR_APERCU = 280;

  function apercu(valeur: unknown): string {
    if (valeur === null || valeur === undefined || valeur === '') return '(vide)';
    if (typeof valeur === 'boolean') return valeur ? 'oui' : 'non';
    if (typeof valeur === 'number') return String(valeur);
    if (typeof valeur === 'string') {
      if (UUID_RE.test(valeur)) return `#${valeur.slice(0, 8)}`;
      if (valeur.length <= LONGUEUR_APERCU) return valeur;
      return `${valeur.slice(0, LONGUEUR_APERCU)}… (${valeur.length} caractères)`;
    }
    if (Array.isArray(valeur)) return `${valeur.length} élément${valeur.length > 1 ? 's' : ''}`;
    const brut = JSON.stringify(valeur);
    return brut.length <= LONGUEUR_APERCU ? brut : `${brut.slice(0, LONGUEUR_APERCU)}…`;
  }

  const arguments_ = $derived(
    Object.entries(args).map(([cle, valeur]) => ({
      cle: CLES[cle] ?? cle.replace(/_/g, ' '),
      valeur: apercu(valeur),
    }))
  );
</script>

<!-- `min-w-0` et coupure des mots longs a chaque niveau : une URL, un texte de
     page ou une ligne JSON de 3 000 caracteres ne doivent jamais elargir le fil. -->
<div class="min-w-0 rounded-lg border border-border bg-surface-secondary px-3 py-2 text-sm">
  <button
    type="button"
    class="flex w-full min-w-0 items-center justify-between gap-2 text-left"
    aria-expanded={ouvert}
    onclick={() => (ouvert = !ouvert)}
  >
    <span class="min-w-0 truncate text-ink-primary">
      {rendu.action}{rendu.objet ? ` ${rendu.objet}` : ''}
    </span>
    <span class="shrink-0 text-xs" class:text-danger={echoue} class:text-ink-tertiary={!echoue}>
      {etat}
    </span>
  </button>
  {#if raison}
    <p class="mt-1 text-xs text-danger [overflow-wrap:anywhere]">{raison}</p>
  {/if}
  {#if extrait}
    <blockquote
      class="mt-2 border-l-2 border-border pl-2 text-xs text-ink-secondary italic [overflow-wrap:anywhere]"
    >
      {extrait.texte}
    </blockquote>
    {#if verdict}
      <p
        class="mt-1 text-xs"
        class:text-ink-tertiary={extrait.statut === 'found'}
        class:text-warning={extrait.statut !== 'found'}
      >
        {verdict}
      </p>
    {/if}
  {/if}
  {#if bilanExtraits}
    <p class="mt-1 text-xs text-ink-tertiary">
      {bilanExtraits.poses} extrait{bilanExtraits.poses > 1 ? 's' : ''} posé{bilanExtraits.poses > 1
        ? 's'
        : ''}{bilanExtraits.refuses > 0
        ? `, ${bilanExtraits.refuses} écarté${bilanExtraits.refuses > 1 ? 's' : ''} faute d'avoir été retrouvé${bilanExtraits.refuses > 1 ? 's' : ''} dans la page.`
        : '.'}
    </p>
  {/if}
  {#if ouvert}
    {#if arguments_.length > 0}
      <dl class="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
        {#each arguments_ as a, rang (rang)}
          <dt class="text-ink-tertiary">{a.cle}</dt>
          <dd class="text-ink-secondary [overflow-wrap:anywhere]">{a.valeur}</dd>
        {/each}
      </dl>
    {:else}
      <p class="mt-2 text-xs text-ink-tertiary">Sans argument.</p>
    {/if}
    <details class="mt-2 text-xs">
      <summary class="cursor-pointer text-ink-tertiary hover:text-ink-secondary">
        Demande et réponse brutes
      </summary>
      <pre
        class="mt-1 max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded bg-surface-tertiary p-2 text-ink-secondary [overflow-wrap:anywhere]">{JSON.stringify(
          args,
          null,
          2
        )}</pre>
      {#if result}
        <pre
          class="mt-1 max-h-[40vh] overflow-y-auto whitespace-pre-wrap rounded bg-surface-tertiary p-2 text-ink-secondary [overflow-wrap:anywhere]">{JSON.stringify(
            result,
            null,
            2
          )}</pre>
      {/if}
    </details>
  {/if}
</div>
