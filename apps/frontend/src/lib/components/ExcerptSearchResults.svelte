<script lang="ts">
  import Skeleton from './Skeleton.svelte';
  import type { ExcerptSearchHit } from '$lib/api';

  interface Props {
    /** `null` = aucune recherche lancée, à distinguer de « rien trouvé ». */
    resultats: ExcerptSearchHit[] | null;
    question: string;
    cherche?: boolean;
    /** La recherche n'a pas pu avoir lieu. Ne se confond pas avec zéro résultat. */
    indisponible?: boolean;
    erreur?: string;
  }

  let { resultats, question, cherche = false, indisponible = false, erreur = '' }: Props = $props();

  /**
   * Le degré de proximité, en mots plutôt qu'en nombre.
   *
   * Les paliers suivent la plage réellement utile du modèle : le backend ne
   * renvoie rien sous 0.60, et le corpus de production plafonne vers 0.83.
   * Découper cette plage-là, et non l'intervalle 0..1, évite que tout soit
   * « très proche » ou que rien ne le soit.
   */
  function proximite(similarite: number): string {
    if (similarite >= 0.78) return 'très proche';
    if (similarite >= 0.68) return 'proche';
    return 'de loin';
  }
</script>

{#if cherche}
  <div class="space-y-3">
    {#each Array(3) as _, i (i)}
      <Skeleton variant="card" height="6rem" />
    {/each}
  </div>
{:else if erreur}
  <div class="rounded-lg bg-danger-bg border border-danger/30 px-4 py-4 text-sm text-danger">
    {erreur}
  </div>
{:else if indisponible}
  <!-- Le service qui compare le sens n'a pas répondu. Le dire tel quel :
       présenter une liste vide ferait conclure que le corpus est muet. -->
  <div
    class="rounded-lg border border-border bg-surface-secondary px-4 py-4 text-sm text-ink-secondary"
  >
    <p class="font-medium text-ink-primary mb-1">La recherche n’a pas pu avoir lieu.</p>
    <p>
      Le service qui compare le sens des passages ne répond pas. Vos extraits ne sont pas en cause,
      et rien n’est perdu : réessayez plus tard.
    </p>
  </div>
{:else if resultats && resultats.length === 0}
  <div class="rounded-lg border border-border bg-surface-secondary px-4 py-4 text-sm">
    <p class="text-ink-primary mb-1">Aucun extrait ne s’approche de cette question.</p>
    <p class="text-ink-secondary">
      Un extrait n’est cherchable qu’une fois indexé, ce qui se fait à son enregistrement. Les
      extraits saisis avant l’indexation le seront à leur prochaine modification.
    </p>
  </div>
{:else if resultats}
  <p class="text-sm text-ink-secondary mb-4">
    {resultats.length} extrait{resultats.length > 1 ? 's' : ''} pour «&nbsp;{question}&nbsp;»
  </p>
  <ul class="space-y-4">
    {#each resultats as hit (hit.excerpt_id)}
      <li class="hover-lift rounded-xl border border-border bg-surface-primary p-5">
        <div class="flex items-start justify-between gap-3 mb-2">
          <!-- Taille imposee : la feuille globale rend les titres en serif
               large, ce qui faisait passer l'intitule avant le passage cite.
               L'intitule est une etiquette posee par l'auteur·ice, le verbatim
               est ce qu'on est venu lire. -->
          {#if hit.title}
            <h2 class="text-base font-medium text-ink-primary">{hit.title}</h2>
          {:else}
            <h2 class="text-sm text-ink-tertiary italic">Sans intitulé</h2>
          {/if}
          <span class="shrink-0 text-xs text-ink-tertiary">{proximite(hit.similarity)}</span>
        </div>

        <blockquote class="border-l-2 border-border-strong pl-3 text-ink-primary font-serif italic">
          «&nbsp;{hit.text}&nbsp;»
        </blockquote>

        {#if hit.context}
          <!-- Hors des guillemets et sans italique : la mise en situation n'est
               pas de la source, l'y fondre lui attribuerait des mots qu'elle
               n'a pas écrits. -->
          <p class="mt-2 text-sm text-ink-secondary">{hit.context}</p>
        {/if}

        <div class="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <a
            href={hit.source_url}
            target="_blank"
            rel="noopener noreferrer"
            class="text-info hover:underline"
          >
            {hit.source_title || hit.source_url}
          </a>
          <span class="text-ink-tertiary">·</span>
          <a
            href="/dashboard/new/{hit.card_id}/sources"
            class="text-ink-secondary hover:text-ink-primary"
          >
            {hit.card_title}
          </a>
        </div>
      </li>
    {/each}
  </ul>
{/if}
