<!--
  Découper soi-même le texte d'une source en extraits citables.

  Mesure du 2026-08-08, sur dix URLs dont les quatre personas de l'audit :
  cinq ne rendent aucun texte exploitable — NYT, ScienceDirect, treasury.gov et
  Cell rendent zéro caractère, YouTube 313. La suggestion automatique, qui lit
  la page, échoue donc une fois sur deux, et une capture Wayback ne rattraperait
  ni ScienceDirect ni Cell dont le texte est derrière un paywall.

  Le seul chemin qui marche à tous les coups est le texte que la personne a sous
  les yeux et colle elle-même. C'est ce que fait cet écran.

  Les bornes se déplacent de phrase en phrase plutôt que librement : une coupe
  au milieu d'une phrase produit un fragment, et un fragment cité se lit comme
  une affirmation tronquée. Le pas est donc la phrase, jamais le caractère.
-->
<script lang="ts">
  import { api } from '$lib/api/client';
  import type { Chunk, ChunkUnit } from '$lib/api/types';
  import Button from '$lib/components/Button.svelte';

  interface Props {
    sourceId: string;
    /** Places restantes : le serveur plafonne à 10 extraits par source. */
    remaining: number;
    onadd: (text: string, annotation: Annotation, ancrage: Ancrage) => Promise<void>;
    /**
     * Le texte de la source, collé ici ou tiré d'un document déposé.
     *
     * Il remonte parce qu'il ne sert pas qu'au découpage : c'est aussi contre
     * lui que la relecture peut se faire quand la page ne rend rien. Le garder
     * enfermé ici laisserait « on ne sait pas » comme seul verdict possible sur
     * les cinq sites de la mesure qui se dérobent.
     */
    sourceText?: string;
  }

  /**
   * Ce qu'on ajoute autour d'un passage sans y toucher.
   *
   * `title` repère, `context` situe : un extrait voyage seul — export, réponse
   * MCP, moteur — et « ce modèle distingue trois composantes » ne nomme ni son
   * objet ni son auteur. Les deux restent facultatifs, et `parIA` dit leur
   * origine : cette prose côtoie du verbatim, et rien ne doit laisser attribuer
   * à la source des mots qu'elle n'a pas écrits.
   */
  interface Annotation {
    title: string | null;
    context: string | null;
    parIA: boolean;
  }

  /** De quoi retrouver le passage dans une page qui aura bougé. */
  interface Ancrage {
    prefix: string;
    suffix: string;
    offset: number;
  }

  // Assez de voisinage pour départager deux occurrences d'une même phrase.
  // Doit rester égal à `CONTEXTE` dans `app/services/excerpt_anchor.py` : le
  // serveur compare ce qu'on lui envoie à ce qu'il relit lui-même.
  const CONTEXTE = 48;

  let { sourceId, remaining, onadd, sourceText = $bindable('') }: Props = $props();

  const UNITS: { value: ChunkUnit; label: string }[] = [
    { value: 'caracteres', label: 'caractères' },
    { value: 'mots', label: 'mots' },
    { value: 'tokens', label: 'tokens' },
  ];

  let unit = $state<ChunkUnit>('caracteres');
  let size = $state<number | null>(null);
  let suggestTitles = $state(false);

  let text = $state('');
  let boundaries = $state<number[]>([]);
  let titles = $state<(string | null)[]>([]);
  let contexts = $state<(string | null)[]>([]);
  // Les barres d'annotation dépliées, par bornes. Repliées par défaut : la
  // plupart des passages se passent d'intitulé, et un champ vide affiché à
  // côté de chacun se lit comme une case à remplir.
  let ouvertes = $state<Set<string>>(new Set());
  // Les morceaux dont l'annotation vient d'un modèle, par bornes.
  let parIA = $state<Set<string>>(new Set());
  let annotant = $state<string | null>(null);
  let textSource = $state<'pasted' | 'uploaded' | 'fetched' | 'none' | null>(null);
  let fileName = $state<string | null>(null);
  let survol = $state(false);
  // `null` tant qu'on n'a pas demandé : on ne préjuge pas de l'absence.
  let llmEnabled = $state<boolean | null>(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  let adding = $state<number | null>(null);
  // Les morceaux deja ajoutes, par bornes. Deplacer une borne change le
  // passage : la marque tombe alors d'elle-meme, ce qui est le bon comportement.
  let added = $state<Set<string>>(new Set());

  const cle = (c: { start: number; end: number }) => `${c.start}-${c.end}`;

  // Les fins de phrase du texte, en offsets. Miroir volontaire de la règle du
  // serveur (`app/services/chunker.py`) : déplacer une borne doit répondre à
  // l'instant, sans un aller-retour réseau par clic.
  const stops = $derived.by(() => {
    const out: number[] = [];
    const re = /(?<=[.!?…])["'»)\]]*\s+/g;
    let m: RegExpExecArray | null;
    // La borne se pose au début de la phrase suivante : le morceau qui précède
    // se termine donc sur sa ponctuation, jamais dessus.
    while ((m = re.exec(text)) !== null) out.push(m.index + m[0].length);
    return out;
  });

  const chunks = $derived.by(() => {
    const out: {
      text: string;
      start: number;
      end: number;
      title: string | null;
      context: string | null;
    }[] = [];
    for (let i = 0; i < boundaries.length - 1; i++) {
      const start = boundaries[i];
      const end = boundaries[i + 1];
      const slice = text.slice(start, end).trim();
      if (slice)
        out.push({
          text: slice,
          start,
          end,
          title: titles[i] ?? null,
          context: contexts[i] ?? null,
        });
    }
    return out;
  });

  function measure(s: string): number {
    if (unit === 'mots') return s.split(/\s+/).filter(Boolean).length;
    if (unit === 'tokens') return Math.max(1, Math.round(s.length / 4));
    return s.length;
  }

  function applyChunks(list: Chunk[], fullText: string) {
    text = fullText;
    boundaries = list.length ? [list[0].start, ...list.map((c) => c.end)] : [];
    titles = list.map((c) => c.title);
    contexts = list.map(() => null);
    ouvertes = new Set();
    parIA = new Set();
  }

  async function propose() {
    error = null;
    loading = true;
    try {
      const res = await api.excerpts.chunk(sourceId, {
        text: sourceText.trim() || undefined,
        unit,
        size: size ?? undefined,
        suggest_titles: suggestTitles,
      });
      textSource = res.text_source;
      llmEnabled = res.llm_enabled;
      if (!res.llm_enabled) suggestTitles = false;
      size = res.suggested_size;
      applyChunks(res.chunks, res.text);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Erreur lors du découpage';
    } finally {
      loading = false;
    }
  }

  /**
   * Dépose d'un document : le serveur en tire le texte, qui atterrit dans le
   * champ de collage.
   *
   * Y faire atterrir le texte n'est pas cosmétique : tout l'aval — redécouper,
   * changer d'unité, relire les extraits — travaille sur `sourceText`. Sans cela,
   * la première modification de réglage redemanderait le fichier.
   */
  async function deposer(file: File | null | undefined) {
    if (!file) return;
    error = null;
    loading = true;
    try {
      const res = await api.excerpts.chunkFile(sourceId, file, {
        unit,
        size: size ?? undefined,
        suggest_titles: suggestTitles,
      });
      fileName = file.name;
      sourceText = res.text;
      textSource = res.text_source;
      llmEnabled = res.llm_enabled;
      if (!res.llm_enabled) suggestTitles = false;
      size = res.suggested_size;
      applyChunks(res.chunks, res.text);
    } catch (err) {
      // Le serveur dit déjà quoi faire (« enregistrez en .docx », « ce PDF est
      // une image scannée ») : le remplacer par un message générique retirerait
      // la seule prochaine action disponible.
      error = err instanceof Error ? err.message : 'Ce document n’a pas pu être lu';
    } finally {
      loading = false;
    }
  }

  /** Déplace la borne `i` d'une phrase, dans la limite de ses voisines. */
  function nudge(i: number, direction: -1 | 1) {
    const current = boundaries[i];
    const candidates =
      direction === 1 ? stops.filter((s) => s > current) : stops.filter((s) => s < current);
    const target = direction === 1 ? candidates[0] : candidates[candidates.length - 1];
    if (target === undefined) return;
    if (target <= boundaries[i - 1] || target >= boundaries[i + 1]) return;
    boundaries = boundaries.map((b, j) => (j === i ? target : b));
  }

  /** Fusionne le morceau `i` avec le suivant en retirant la borne entre eux. */
  function merge(i: number) {
    boundaries = boundaries.filter((_, j) => j !== i + 1);
    titles = titles.filter((_, j) => j !== i + 1);
    contexts = contexts.filter((_, j) => j !== i + 1);
  }

  /** Coupe le morceau `i` à la fin de phrase la plus proche de son milieu. */
  function split(i: number) {
    const start = boundaries[i];
    const end = boundaries[i + 1];
    const inside = stops.filter((s) => s > start && s < end);
    if (!inside.length) return;
    const middle = (start + end) / 2;
    const at = inside.reduce((a, b) => (Math.abs(b - middle) < Math.abs(a - middle) ? b : a));
    boundaries = [...boundaries.slice(0, i + 1), at, ...boundaries.slice(i + 1)];
    titles = [...titles.slice(0, i + 1), null, ...titles.slice(i + 1)];
    contexts = [...contexts.slice(0, i + 1), null, ...contexts.slice(i + 1)];
  }

  function setTitle(i: number, value: string) {
    titles = titles.map((t, j) => (j === i ? value.trim() || null : t));
  }

  function setContext(i: number, value: string) {
    contexts = contexts.map((c, j) => (j === i ? value.trim() || null : c));
  }

  function basculer(k: string) {
    const suite = new Set(ouvertes);
    if (!suite.delete(k)) suite.add(k);
    ouvertes = suite;
  }

  /**
   * Demande au serveur un intitulé et une mise en situation pour ce morceau.
   *
   * Le texte entier part avec : sans lui, un modèle ne peut que paraphraser le
   * passage, alors que tout l'objet de la mise en situation est de dire ce que
   * le passage suppose connu. Rien n'est enregistré — les champs se relisent et
   * se corrigent avant l'ajout.
   */
  async function annoter(i: number) {
    const chunk = chunks[i];
    const k = cle(chunk);
    error = null;
    annotant = k;
    try {
      const res = await api.excerpts.annotate(sourceId, chunk.text, text);
      llmEnabled = res.llm_enabled;
      if (!res.llm_enabled) return;
      if (res.title) setTitle(i, res.title);
      if (res.context) setContext(i, res.context);
      if (res.title || res.context) parIA = new Set([...parIA, k]);
    } catch (err) {
      error = err instanceof Error ? err.message : 'Erreur lors de la suggestion';
    } finally {
      annotant = null;
    }
  }

  async function add(i: number) {
    adding = i;
    try {
      const { start, end } = chunks[i];
      await onadd(
        chunks[i].text,
        {
          title: chunks[i].title,
          context: chunks[i].context,
          parIA: parIA.has(cle(chunks[i])),
        },
        {
          prefix: text.slice(Math.max(0, start - CONTEXTE), start),
          suffix: text.slice(end, end + CONTEXTE),
          offset: start,
        }
      );
      // Le morceau reste à sa place, marqué. Il ne peut pas être retiré de la
      // liste : les bornes partitionnent le texte, et en ôter un segment
      // recollerait ses voisins — c'est ce que faisait `merge()` ici, si bien
      // que le passage ajouté restait affiché dans le morceau voisin et
      // pouvait être ajouté une seconde fois, les deux extraits se
      // chevauchant sans que rien ne le signale.
      added = new Set([...added, cle(chunks[i])]);
    } catch (err) {
      error = err instanceof Error ? err.message : "Erreur lors de l'ajout";
    } finally {
      adding = null;
    }
  }
</script>

<div class="space-y-3 rounded-lg border border-border bg-surface-secondary p-3">
  <!--
    Le champ de collage vient en premier : c'est le geste d'entree. Il etait
    sous les reglages et sous le bouton « Proposer un decoupage », si bien que
    l'ecran demandait de choisir une taille cible et de lancer le decoupage
    avant meme d'avoir de quoi decouper.
  -->
  <label class="block text-xs text-ink-secondary">
    Texte du contenu original — laissez vide pour tenter de lire la page
    <textarea
      bind:value={sourceText}
      rows="4"
      placeholder="Collez ici tout ou partie du texte de la source…"
      class="mt-1 w-full rounded-lg border border-border-strong bg-surface-primary px-3 py-2 text-sm text-ink-primary placeholder:text-ink-placeholder"
    ></textarea>
  </label>

  <!--
    Le dépôt de fichier, à côté du collage et non à sa place : un chapitre ne se
    colle pas, mais un paragraphe ne se met pas dans un fichier. Les deux gestes
    aboutissent au même endroit — le texte de la source, dans le champ ci-dessus.
  -->
  <div
    role="button"
    tabindex="0"
    class="rounded-lg border border-dashed px-3 py-2 text-xs text-ink-secondary transition-colors"
    class:border-border-strong={!survol}
    class:border-accent={survol}
    class:bg-surface-primary={survol}
    ondragover={(e) => {
      e.preventDefault();
      survol = true;
    }}
    ondragleave={() => (survol = false)}
    ondrop={(e) => {
      e.preventDefault();
      survol = false;
      deposer(e.dataTransfer?.files?.[0]);
    }}
    onclick={() => document.getElementById('chunk-file')?.click()}
    onkeydown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        document.getElementById('chunk-file')?.click();
      }
    }}
  >
    <label for="chunk-file" class="cursor-pointer">
      … ou déposez le document ici — <span class="underline">parcourir</span>
      <span class="block text-ink-placeholder"
        >PDF, Word (.docx), OpenDocument (.odt), .txt, .md</span
      >
    </label>
    <input
      id="chunk-file"
      type="file"
      accept=".pdf,.docx,.odt,.txt,.md,.markdown"
      class="sr-only"
      onchange={(e) => {
        deposer(e.currentTarget.files?.[0]);
        e.currentTarget.value = '';
      }}
    />
    {#if fileName}
      <p class="mt-1 text-ink-primary">Texte tiré de « {fileName} ».</p>
    {/if}
  </div>

  <div class="flex flex-wrap items-end gap-2">
    <label class="flex flex-col gap-1 text-xs text-ink-secondary">
      Unité
      <select
        bind:value={unit}
        class="rounded-lg border border-border-strong bg-surface-primary px-2 py-1 text-sm text-ink-primary"
      >
        {#each UNITS as u (u.value)}
          <option value={u.value}>{u.label}</option>
        {/each}
      </select>
    </label>

    <label class="flex flex-col gap-1 text-xs text-ink-secondary">
      Taille cible
      <input
        type="number"
        min="1"
        bind:value={size}
        placeholder="auto"
        class="w-24 rounded-lg border border-border-strong bg-surface-primary px-2 py-1 text-sm text-ink-primary"
      />
    </label>

    <label
      class="flex items-center gap-1.5 text-xs text-ink-secondary"
      class:opacity-50={llmEnabled === false}
      title={llmEnabled === false
        ? "Aucun modèle n'est configuré sur ce serveur : les intitulés se saisissent à la main."
        : undefined}
    >
      <input type="checkbox" bind:checked={suggestTitles} disabled={llmEnabled === false} />
      Suggérer les intitulés
    </label>

    <Button type="button" variant="secondary" size="sm" {loading} onclick={propose}>
      {size === null ? 'Proposer un découpage' : 'Redécouper'}
    </Button>

    {#if size !== null}
      <button
        type="button"
        class="text-xs text-ink-secondary underline"
        onclick={() => {
          size = null;
          propose();
        }}
      >
        taille auto
      </button>
    {/if}
  </div>

  {#if error}
    <p class="text-xs text-danger">{error}</p>
  {/if}

  {#if textSource === 'none'}
    <p class="text-xs text-ink-secondary">
      Cette page ne laisse pas lire son texte. Collez le passage ci-dessus : le découpage
      fonctionnera à l'identique.
    </p>
  {/if}

  {#if llmEnabled === false}
    <p class="text-xs text-ink-secondary">
      Aucun modèle n'est configuré sur ce serveur : les intitulés se saisissent à la main, un champ
      par morceau.
    </p>
  {/if}

  {#if chunks.length}
    <p class="text-xs text-ink-secondary">
      {chunks.length} morceau{chunks.length > 1 ? 'x' : ''} — {remaining} place{remaining > 1
        ? 's'
        : ''} restante{remaining > 1 ? 's' : ''}
    </p>

    <ul class="space-y-2">
      {#each chunks as chunk, i (chunk.start)}
        <li class="rounded-lg border border-border bg-surface-primary p-2">
          {#if chunk.title}
            <p class="mb-1 text-xs font-medium text-ink-primary">{chunk.title}</p>
          {/if}
          <p class="text-sm text-ink-primary">{chunk.text}</p>
          {#if chunk.context && !ouvertes.has(cle(chunk))}
            <!--
              La mise en situation reste visuellement distincte du passage :
              elle dit ce que la source n'a pas dit, et les confondre ferait
              lui attribuer des mots qu'elle n'a jamais écrits.
            -->
            <p class="mt-1 border-l-2 border-border pl-2 text-xs text-ink-tertiary">
              {chunk.context}
              {#if parIA.has(cle(chunk))}<span class="italic">(proposé par un modèle)</span>{/if}
            </p>
          {/if}

          {#if ouvertes.has(cle(chunk))}
            <div class="mt-2 space-y-1.5 rounded border border-border bg-surface-secondary p-2">
              <input
                type="text"
                value={chunk.title ?? ''}
                maxlength={200}
                placeholder="Intitulé — 2 à 6 mots pour retrouver ce passage"
                oninput={(e) => setTitle(i, e.currentTarget.value)}
                class="w-full rounded border border-border bg-surface-primary px-2 py-1 text-xs font-medium text-ink-primary placeholder:text-ink-placeholder"
              />
              <textarea
                value={chunk.context ?? ''}
                rows="2"
                maxlength={500}
                placeholder="Une phrase qui situe ce passage pour qui le lit hors de son document…"
                oninput={(e) => setContext(i, e.currentTarget.value)}
                class="w-full rounded border border-border bg-surface-primary px-2 py-1 text-xs text-ink-primary placeholder:text-ink-placeholder"
              ></textarea>
              <div class="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  loading={annotant === cle(chunk)}
                  disabled={annotant !== null || llmEnabled === false}
                  onclick={() => annoter(i)}
                >
                  Suggérer
                </Button>
                {#if llmEnabled === false}
                  <span class="text-xs text-ink-tertiary">
                    Aucun modèle n’est configuré sur ce serveur : ces deux champs se saisissent à la
                    main.
                  </span>
                {:else if parIA.has(cle(chunk))}
                  <span class="text-xs text-ink-tertiary italic">
                    Proposé par un modèle — à relire : cette prose voisine un verbatim.
                  </span>
                {/if}
              </div>
            </div>
          {/if}
          <div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
            <span>{measure(chunk.text)} {UNITS.find((u) => u.value === unit)?.label}</span>
            <button
              type="button"
              class="underline disabled:opacity-40"
              disabled={i + 1 >= boundaries.length - 1}
              onclick={() => nudge(i + 1, -1)}>◀ borne</button
            >
            <button
              type="button"
              class="underline disabled:opacity-40"
              disabled={i + 1 >= boundaries.length - 1}
              onclick={() => nudge(i + 1, 1)}>borne ▶</button
            >
            <button type="button" class="underline" onclick={() => split(i)}>couper</button>
            {#if i < chunks.length - 1}
              <button type="button" class="underline" onclick={() => merge(i)}>fusionner</button>
            {/if}
            <button
              type="button"
              class="underline"
              aria-expanded={ouvertes.has(cle(chunk))}
              onclick={() => basculer(cle(chunk))}
            >
              {ouvertes.has(cle(chunk)) ? 'replier' : 'annoter'}
            </button>
            {#if added.has(cle(chunk))}
              <span class="text-success">✓ ajouté</span>
            {:else}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                loading={adding === i}
                disabled={remaining <= 0 || adding !== null}
                onclick={() => add(i)}
              >
                Ajouter
              </Button>
            {/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>
