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
    onadd: (text: string, title: string | null) => Promise<void>;
  }

  let { sourceId, remaining, onadd }: Props = $props();

  const UNITS: { value: ChunkUnit; label: string }[] = [
    { value: 'caracteres', label: 'caractères' },
    { value: 'mots', label: 'mots' },
    { value: 'tokens', label: 'tokens' },
  ];

  let pasted = $state('');
  let unit = $state<ChunkUnit>('caracteres');
  let size = $state<number | null>(null);
  let suggestTitles = $state(false);

  let text = $state('');
  let boundaries = $state<number[]>([]);
  let titles = $state<(string | null)[]>([]);
  let textSource = $state<'pasted' | 'fetched' | 'none' | null>(null);
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
    const out: { text: string; start: number; end: number; title: string | null }[] = [];
    for (let i = 0; i < boundaries.length - 1; i++) {
      const start = boundaries[i];
      const end = boundaries[i + 1];
      const slice = text.slice(start, end).trim();
      if (slice) out.push({ text: slice, start, end, title: titles[i] ?? null });
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
  }

  async function propose() {
    error = null;
    loading = true;
    try {
      const res = await api.excerpts.chunk(sourceId, {
        text: pasted.trim() || undefined,
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
  }

  function setTitle(i: number, value: string) {
    titles = titles.map((t, j) => (j === i ? value.trim() || null : t));
  }

  async function add(i: number) {
    adding = i;
    try {
      await onadd(chunks[i].text, chunks[i].title);
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

<div class="space-y-3 rounded-lg border border-border-subtle bg-surface-secondary p-3">
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

  <label class="block text-xs text-ink-secondary">
    Texte du contenu original — laissez vide pour tenter de lire la page
    <textarea
      bind:value={pasted}
      rows="4"
      placeholder="Collez ici tout ou partie du texte de la source…"
      class="mt-1 w-full rounded-lg border border-border-strong bg-surface-primary px-3 py-2 text-sm text-ink-primary placeholder:text-ink-placeholder"
    ></textarea>
  </label>

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
        <li class="rounded-lg border border-border-subtle bg-surface-primary p-2">
          <input
            type="text"
            value={chunk.title ?? ''}
            maxlength={200}
            placeholder="Intitulé (facultatif)…"
            oninput={(e) => setTitle(i, e.currentTarget.value)}
            class="mb-1.5 w-full rounded border border-border-subtle bg-surface-secondary px-2 py-1 text-xs font-medium text-ink-primary placeholder:text-ink-placeholder"
          />
          <p class="text-sm text-ink-primary">{chunk.text}</p>
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
