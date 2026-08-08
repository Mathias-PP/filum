<!--
  Atelier : le découpage d'une source en extraits, à l'écran.

  L'écran réel vit derrière l'authentification Google, dans un formulaire de
  création de fiche à plusieurs étapes ; l'exercer demande un compte, une fiche
  et une source. Ce qui reste alors non vérifié n'est pas la logique — sept
  tests de composant tiennent l'invariant « le texte affiché est celui de la
  source » — mais le rendu : la lisibilité des morceaux, l'état grisé de la
  case quand aucun modèle n'est configuré, ce que donnent trente morceaux les
  uns sous les autres.

  D'où cet atelier. La réponse du serveur y est simulée : le découpage lui-même
  est déjà tenu par les tests du `chunker` côté backend, et ce qu'on regarde ici
  est ce que l'écran en fait. Le basculement `llm_enabled` est exposé en
  commande, parce que c'est justement l'état qu'on ne peut pas produire à
  volonté sur un vrai serveur.
-->
<script lang="ts">
  import ChunkArchitect from '$lib/components/ChunkArchitect.svelte';

  const TEXTE =
    'La mémoire de travail retient une information le temps de s’en servir. ' +
    'Elle ne dure que quelques secondes. ' +
    'Baddeley en a proposé un modèle en 1974. ' +
    'Ce modèle distingue trois composantes. ' +
    'La boucle phonologique traite le verbal. ' +
    'Le calepin visuo-spatial traite l’image. ' +
    'L’administrateur central répartit l’attention entre les deux. ' +
    'Le tampon épisodique a été ajouté en 2000.';

  let llmEnabled = $state(false);
  let pageLisible = $state(true);
  let ajoutes = $state<{ text: string; title: string | null }[]>([]);

  /** Découpe naïve par phrases, à la seule fin de peupler l'écran. */
  function decouper(texte: string, taille: number) {
    const out: { text: string; start: number; end: number; size: number; title: null }[] = [];
    let debut = 0;
    let curseur = 0;
    const re = /(?<=[.!?…])\s+/g;
    let m: RegExpExecArray | null;
    const coupes: number[] = [];
    while ((m = re.exec(texte)) !== null) coupes.push(m.index + m[0].length);
    coupes.push(texte.length);
    for (const fin of coupes) {
      if (fin - debut < taille && fin !== texte.length) continue;
      out.push({
        text: texte.slice(debut, fin).trim(),
        start: debut,
        end: fin,
        size: fin - debut,
        title: null,
      });
      debut = fin;
      curseur = fin;
    }
    if (curseur < texte.length) {
      out.push({
        text: texte.slice(curseur).trim(),
        start: curseur,
        end: texte.length,
        size: texte.length - curseur,
        title: null,
      });
    }
    return out;
  }

  const vraiFetch = globalThis.fetch;
  globalThis.fetch = (async (entree: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entree === 'string' ? entree : entree.toString();
    if (!url.includes('/excerpts/chunk')) return vraiFetch(entree, init);
    const corps = JSON.parse((init?.body as string) ?? '{}');
    const texte = pageLisible ? corps.text?.trim() || TEXTE : (corps.text?.trim() ?? '');
    const taille = corps.size ?? 90;
    return new Response(
      JSON.stringify({
        text: texte,
        text_source: corps.text?.trim() ? 'pasted' : texte ? 'fetched' : 'none',
        unit: corps.unit ?? 'caracteres',
        suggested_size: taille,
        llm_enabled: llmEnabled,
        chunks: texte ? decouper(texte, taille) : [],
      }),
      { status: 200, headers: { 'content-type': 'application/json' } }
    );
  }) as typeof fetch;
</script>

<div class="mx-auto max-w-2xl space-y-4 p-6">
  <h1 class="text-lg font-semibold text-ink-primary">Atelier — découpage en extraits</h1>

  <div class="flex flex-wrap gap-4 text-sm text-ink-secondary">
    <label class="flex items-center gap-2">
      <input type="checkbox" bind:checked={llmEnabled} /> un modèle est configuré
    </label>
    <label class="flex items-center gap-2">
      <input type="checkbox" bind:checked={pageLisible} /> la page se laisse lire
    </label>
  </div>

  <ChunkArchitect
    sourceId="atelier"
    remaining={10}
    onadd={async (text, title) => {
      ajoutes = [...ajoutes, { text, title }];
    }}
  />

  {#if ajoutes.length}
    <div class="space-y-2">
      <h2 class="text-sm font-medium text-ink-primary">Extraits ajoutés</h2>
      <ul class="space-y-1 text-sm text-ink-secondary">
        {#each ajoutes as extrait, i (i)}
          <li class="rounded border border-border-subtle p-2">
            {#if extrait.title}<strong>{extrait.title}</strong> —{/if}
            {extrait.text}
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</div>
