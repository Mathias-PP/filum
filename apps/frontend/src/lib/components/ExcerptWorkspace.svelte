<!--
  L'espace où l'on constitue les citations d'une source.

  Trois chemins y mènent, parce que ce sont trois gestes distincts : coller un
  passage qu'on a déjà isolé, verser un texte long et le découper, ou laisser
  un modèle proposer. Les deux premiers ne dépendent d'aucun serveur tiers ni
  d'aucun modèle — mesure du 2026-08-08 : cinq URLs sur dix ne rendent aucun
  texte exploitable, et la prod n'a aujourd'hui aucun modèle configuré.

  « Relire la source » relit la page telle qu'elle est aujourd'hui et cherche
  chaque citation. Les quatre verdicts restent distincts jusqu'à l'affichage :
  « illisible » n'est pas « introuvable ». Les confondre ferait passer une
  source inaccessible pour une citation inventée — l'accusation que Philum ne
  doit jamais porter à tort.
-->
<script lang="ts">
  import { api } from '$lib/api/client';
  import type {
    ExcerptCheck,
    ExcerptCheckStatus,
    SourceExcerpt,
    SuggestedExcerpt,
  } from '$lib/api/types';
  import Button from '$lib/components/Button.svelte';
  import ChunkArchitect from '$lib/components/ChunkArchitect.svelte';

  interface Props {
    sourceId: string;
    excerpts: SourceExcerpt[];
    /** Remonte la liste à jour ; le parent reste seul propriétaire de l'état. */
    onchange: (excerpts: SourceExcerpt[]) => void;
  }

  /** De quoi retrouver le passage dans une page qui aura bougé. */
  interface Ancrage {
    prefix: string;
    suffix: string;
    offset: number;
  }

  /** Le serveur plafonne à 10 citations par source. */
  const MAX = 10;

  const MODES = [
    { id: 'coller' as const, label: 'Coller un passage' },
    { id: 'decouper' as const, label: 'Découper un texte long' },
  ];

  let { sourceId, excerpts, onchange }: Props = $props();

  let mode = $state<'coller' | 'decouper'>('coller');
  let texte = $state('');
  let erreur = $state<string | null>(null);
  let ajoutEnCours = $state(false);
  let suggestions = $state<SuggestedExcerpt[]>([]);
  let infoSuggestion = $state<string | null>(null);
  let relecture = $state(false);
  /** Le sort de chaque citation à la dernière relecture, par id. */
  let verdicts = $state<Record<string, ExcerptCheck>>({});
  let infoRelecture = $state<string | null>(null);
  /**
   * Le texte de la source, collé ou tiré d'un document déposé dans l'atelier
   * de découpage. Sur les cinq sites de la mesure qui ne rendent rien, c'est
   * la seule matière contre laquelle une relecture puisse conclure.
   */
  let texteSource = $state('');

  const complet = $derived(excerpts.length >= MAX);

  /**
   * `ancrage` n'existe que pour un passage repéré dans le texte de la page.
   * Une saisie à la main n'en a pas : le serveur enregistre alors une citation
   * sans ancrage, ce qui se lit comme non vérifiable — et non comme fausse.
   */
  async function ajouter(
    contenu: string,
    parIA = false,
    ancrage: Ancrage | null = null,
    titre: string | null = null
  ) {
    const propre = contenu.trim();
    if (!propre) return;
    erreur = null;
    ajoutEnCours = true;
    try {
      const cree = await api.excerpts.create(sourceId, {
        text: propre,
        title: titre,
        suggested_by_ai: parIA,
        anchor_prefix: ancrage?.prefix ?? null,
        anchor_suffix: ancrage?.suffix ?? null,
        anchor_offset: ancrage?.offset ?? null,
      });
      onchange([...excerpts, cree]);
      if (!parIA) texte = '';
    } catch (err) {
      erreur = err instanceof Error ? err.message : "Erreur lors de l'ajout de la citation";
    } finally {
      ajoutEnCours = false;
    }
  }

  async function supprimer(excerptId: string) {
    erreur = null;
    try {
      await api.excerpts.delete(sourceId, excerptId);
      onchange(excerpts.filter((x) => x.id !== excerptId));
    } catch (err) {
      erreur = err instanceof Error ? err.message : 'Erreur lors de la suppression';
    }
  }

  async function suggerer() {
    erreur = null;
    infoSuggestion = null;
    try {
      const res = await api.excerpts.suggest(sourceId, texteSource.trim() || undefined);
      suggestions = res.suggestions;
      if (!res.llm_enabled) {
        infoSuggestion = "La suggestion IA n'est pas configurée sur ce serveur.";
      } else if (res.page_text_length === 0) {
        infoSuggestion =
          'Cette page ne laisse pas lire son texte. Passez par « Découper un texte long » : collez ce que vous avez sous les yeux, rien ne dépendra plus du site.';
      } else if (!res.suggestions.length) {
        infoSuggestion = 'Aucun passage n’a été retenu dans cette page.';
      }
    } catch (err) {
      erreur = err instanceof Error ? err.message : 'Erreur lors de la suggestion';
    }
  }

  async function relire() {
    erreur = null;
    infoRelecture = null;
    relecture = true;
    try {
      const res = await api.excerpts.verify(sourceId, texteSource.trim() || undefined);
      verdicts = Object.fromEntries(res.checks.map((c) => [c.excerpt_id, c]));
      if (res.page_text_length === 0) {
        infoRelecture =
          'Cette page ne rend aucun texte : la relecture ne dit rien sur ces citations, ni dans un sens ni dans l’autre. Passez par « Découper un texte long » et collez ou déposez le texte de la source : la relecture portera alors sur lui.';
      } else {
        const n = res.checks.filter((c) => c.status !== 'missing').length;
        const contre =
          res.text_source === 'provided'
            ? 'dans le texte que vous avez fourni'
            : 'dans la page d’aujourd’hui';
        infoRelecture = `${n} citation${n > 1 ? 's' : ''} sur ${res.checks.length} retrouvée${n > 1 ? 's' : ''} ${contre}.`;
      }
    } catch (err) {
      erreur = err instanceof Error ? err.message : 'Erreur lors de la relecture';
    } finally {
      relecture = false;
    }
  }

  /** Ce qu'on affiche à côté d'une citation une fois la page relue. */
  function verdict(status: ExcerptCheckStatus): { texte: string; classe: string; titre: string } {
    if (status === 'found')
      return {
        texte: '✓ retrouvée',
        classe: 'text-success',
        titre: 'Le passage est dans la page telle qu’elle est aujourd’hui.',
      };
    if (status === 'moved')
      return {
        texte: '≈ déplacée',
        classe: 'text-warning',
        titre: 'Le passage y est, mais la source ne porte plus tout à fait ces mots.',
      };
    if (status === 'unreadable')
      return {
        texte: '? illisible',
        classe: 'text-ink-tertiary',
        titre: 'La page n’a rendu aucun texte : on ne sait pas. Ce n’est pas « absente ».',
      };
    return {
      texte: '✕ introuvable',
      classe: 'text-danger',
      titre: 'Le passage n’a pas été retrouvé dans la page d’aujourd’hui.',
    };
  }
</script>

<div class="border-t border-border pt-4 space-y-3">
  <div class="flex items-center justify-between gap-2 flex-wrap">
    <h3 class="text-sm font-semibold text-ink-primary">
      Citations
      <span class="text-xs text-ink-tertiary font-normal">
        : extraits marquants de cette source ({excerpts.length}/{MAX})</span
      >
    </h3>
    <div class="flex items-center gap-1">
      <!--
        `secondary` et non `ghost` : en ghost, ces deux actions se lisaient
        comme du texte de navigation, pas comme des boutons — verifie au
        navigateur.
      -->
      <Button
        type="button"
        variant="secondary"
        size="sm"
        loading={relecture}
        disabled={relecture || excerpts.length === 0}
        onclick={relire}
      >
        {relecture ? 'Relecture…' : 'Relire la source'}
      </Button>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        disabled={ajoutEnCours || complet}
        onclick={suggerer}
      >
        Suggérer des citations (IA)
      </Button>
    </div>
  </div>

  {#if erreur}
    <div class="rounded-lg bg-danger-bg border border-danger/30 px-3 py-2 text-xs text-danger">
      {erreur}
    </div>
  {/if}
  {#if infoRelecture}
    <div
      class="rounded-lg bg-surface-secondary border border-border px-3 py-2 text-xs text-ink-secondary"
    >
      {infoRelecture}
    </div>
  {/if}
  {#if infoSuggestion}
    <div class="rounded-lg bg-info/10 border border-info/30 px-3 py-2 text-xs text-info">
      {infoSuggestion}
    </div>
  {/if}

  {#if excerpts.length > 0}
    <ul class="space-y-2">
      {#each excerpts as excerpt (excerpt.id)}
        <li
          class="flex items-start justify-between gap-2 rounded-lg border border-border bg-surface-secondary/50 px-3 py-2"
        >
          <p class="text-sm text-ink-secondary italic min-w-0">
            «&nbsp;{excerpt.text}&nbsp;»
            {#if excerpt.suggested_by_ai}
              <span class="text-xs text-ink-tertiary not-italic">(IA)</span>
            {/if}
            {#if verdicts[excerpt.id]}
              {@const v = verdict(verdicts[excerpt.id].status)}
              <span class="text-xs not-italic {v.classe}" title={v.titre}>{v.texte}</span>
            {/if}
          </p>
          <button
            type="button"
            onclick={() => supprimer(excerpt.id)}
            class="p-1 shrink-0 text-ink-tertiary hover:text-danger transition-colors"
            aria-label="Supprimer cette citation"
            title="Supprimer"
          >
            <svg
              viewBox="0 0 24 24"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <line x1="6" y1="6" x2="18" y2="18" />
              <line x1="6" y1="18" x2="18" y2="6" />
            </svg>
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  {#if suggestions.length > 0}
    <div class="space-y-2">
      <p class="text-xs font-medium text-ink-secondary">
        Suggestions repérées dans le texte (vérifiées mot pour mot) :
      </p>
      {#each suggestions as sug (sug.char_offset)}
        <div class="rounded-lg border border-info/30 bg-info/5 px-3 py-2 space-y-1.5">
          <p class="text-xs text-ink-tertiary">
            …{sug.context_before}<span class="text-ink-primary font-medium">{sug.text}</span
            >{sug.context_after}…
          </p>
          <div class="flex justify-end">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={ajoutEnCours || complet}
              onclick={() =>
                ajouter(sug.text, true, {
                  prefix: sug.context_before,
                  suffix: sug.context_after,
                  offset: sug.char_offset,
                })}
            >
              Ajouter
            </Button>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  <div class="flex gap-1 border-b border-border">
    {#each MODES as m (m.id)}
      <button
        type="button"
        class="px-3 py-1.5 text-xs border-b-2 -mb-px transition-colors"
        class:border-info={mode === m.id}
        class:text-ink-primary={mode === m.id}
        class:border-transparent={mode !== m.id}
        class:text-ink-tertiary={mode !== m.id}
        onclick={() => (mode = m.id)}
      >
        {m.label}
      </button>
    {/each}
  </div>

  {#if complet}
    <p class="text-xs text-ink-tertiary">
      Dix citations, c’est le maximum par source. Supprimez-en une pour en ajouter une autre.
    </p>
  {:else if mode === 'coller'}
    <div class="space-y-2">
      <textarea
        bind:value={texte}
        rows="3"
        maxlength={1000}
        placeholder="Collez ici le passage exact, tel qu'il est dans la source…"
        class="w-full px-3 py-2 rounded-lg border border-border-strong bg-surface-primary text-ink-primary text-sm focus:outline-hidden focus:ring-2 focus:ring-info placeholder:text-ink-placeholder"
      ></textarea>
      <div class="flex items-center justify-between gap-2">
        <p class="text-xs text-ink-tertiary">
          {texte.length}/1000 — « Relire la source » retrouvera ce passage tant qu’il est verbatim.
        </p>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={ajoutEnCours}
          disabled={ajoutEnCours || !texte.trim()}
          onclick={() => ajouter(texte)}
        >
          Ajouter
        </Button>
      </div>
    </div>
  {:else}
    <ChunkArchitect
      {sourceId}
      remaining={MAX - excerpts.length}
      bind:sourceText={texteSource}
      onadd={(t, titre, ancrage) => ajouter(t, false, ancrage, titre)}
    />
  {/if}
</div>
