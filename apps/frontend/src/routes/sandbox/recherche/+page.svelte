<!--
  Bac à sable de `ExcerptSearchResults`.

  L'écran réel exige une session, des extraits déjà indexés et un service
  d'embeddings qui répond : trois conditions qu'aucune machine de
  développement ne réunit. Ses quatre états seraient donc invisibles jusqu'en
  production. Ici on les regarde tous les quatre, côte à côte.
-->
<script lang="ts">
  import ExcerptSearchResults from '$lib/components/ExcerptSearchResults.svelte';
  import type { ExcerptSearchHit } from '$lib/api/types';

  const hits: ExcerptSearchHit[] = [
    {
      excerpt_id: 'a',
      text: 'Le sommeil lent profond rejoue les séquences d’activation enregistrées pendant l’éveil.',
      title: 'Le rejeu pendant le sommeil',
      context: 'Les auteurs décrivent ici ce qu’ils observent chez le rat, pas chez l’humain.',
      source_id: 's1',
      source_title: 'Replay of neuronal firing sequences',
      source_url: 'https://example.org/replay',
      card_id: 'c1',
      card_slug: 'memoire-et-cerveau',
      card_title: 'Mémoire et cerveau',
      similarity: 0.81,
    },
    {
      excerpt_id: 'b',
      text: 'Une nuit blanche suffit à effacer le bénéfice d’une journée d’apprentissage.',
      title: null,
      context: null,
      source_id: 's2',
      source_title: null,
      source_url: 'https://example.org/sleep-deprivation',
      card_id: 'c1',
      card_slug: 'memoire-et-cerveau',
      card_title: 'Mémoire et cerveau',
      similarity: 0.71,
    },
    {
      excerpt_id: 'c',
      text: 'La consolidation ne se réduit pas à une répétition passive.',
      title: 'Contre l’image du magnétophone',
      context: null,
      source_id: 's3',
      source_title: 'Systems consolidation revisited',
      source_url: 'https://example.org/consolidation',
      card_id: 'c2',
      card_slug: 'apprentissage',
      card_title: 'Apprentissage',
      similarity: 0.62,
    },
  ];
</script>

<div class="mx-auto max-w-3xl space-y-12 p-8">
  <section>
    <h2 class="mb-3 font-serif text-xl text-ink-primary">Des résultats</h2>
    <ExcerptSearchResults resultats={hits} question="sommeil et mémoire" />
  </section>

  <section>
    <h2 class="mb-3 font-serif text-xl text-ink-primary">Recherche en cours</h2>
    <ExcerptSearchResults resultats={null} question="" cherche />
  </section>

  <section>
    <h2 class="mb-3 font-serif text-xl text-ink-primary">Rien trouvé</h2>
    <ExcerptSearchResults resultats={[]} question="la reproduction des méduses" />
  </section>

  <section>
    <h2 class="mb-3 font-serif text-xl text-ink-primary">Recherche indisponible</h2>
    <ExcerptSearchResults resultats={[]} question="sommeil et mémoire" indisponible />
  </section>

  <section>
    <h2 class="mb-3 font-serif text-xl text-ink-primary">Erreur</h2>
    <ExcerptSearchResults
      resultats={null}
      question="sommeil et mémoire"
      erreur="La recherche n’a pas abouti. Réessayez dans quelques instants."
    />
  </section>
</div>
