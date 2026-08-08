<!--
  Bac à sable de `ExcerptWorkspace`.

  L'écran réel exige une fiche, une source et une session : le composant reste
  donc invisible tant qu'on n'a pas monté toute la pile, et ses régressions
  visuelles passent inaperçues. Ici on le regarde seul.
-->
<script lang="ts">
  import type { SourceExcerpt } from '$lib/api/types';
  import ExcerptWorkspace from '$lib/components/ExcerptWorkspace.svelte';

  let excerpts = $state<SourceExcerpt[]>([
    {
      id: 'a',
      text: 'La mémoire de travail retient une information brièvement.',
      title: null,
      position: 0,
      suggested_by_ai: false,
    },
    {
      id: 'b',
      text: 'Baddeley en a proposé un modèle.',
      title: null,
      position: 1,
      suggested_by_ai: true,
    },
  ]);
</script>

<div class="mx-auto max-w-2xl p-8">
  <h1 class="mb-4 text-xl font-semibold text-ink-primary">Espace d’édition des citations</h1>
  <ExcerptWorkspace sourceId="s1" {excerpts} onchange={(l) => (excerpts = l)} />
</div>
