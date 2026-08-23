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
</script>

<div class="rounded-lg border border-subtle bg-surface-secondary px-3 py-2 text-sm">
  <button
    type="button"
    class="flex w-full items-center justify-between gap-2 text-left"
    onclick={() => (ouvert = !ouvert)}
  >
    <span class="text-ink-primary">
      {rendu.action}{rendu.objet ? ` ${rendu.objet}` : ''}
      <span class="ml-1 font-mono text-[11px] text-ink-tertiary">{name}</span>
    </span>
    <span class="text-xs" class:text-danger={echoue} class:text-ink-tertiary={!echoue}>
      {etat}
    </span>
  </button>
  {#if raison}
    <p class="mt-1 text-xs text-danger">{raison}</p>
  {/if}
  {#if extrait}
    <blockquote class="mt-2 border-l-2 border-subtle pl-2 text-xs text-ink-secondary italic">
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
    <pre
      class="mt-2 overflow-x-auto rounded bg-surface-tertiary p-2 text-xs text-ink-secondary">{JSON.stringify(
        args,
        null,
        2
      )}</pre>
    {#if result}
      <pre
        class="mt-1 overflow-x-auto rounded bg-surface-tertiary p-2 text-xs text-ink-secondary">{JSON.stringify(
          result,
          null,
          2
        )}</pre>
    {/if}
  {/if}
</div>
