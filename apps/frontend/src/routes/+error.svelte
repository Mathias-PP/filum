<script lang="ts">
  import { page } from '$app/stores';
  import { Button } from '$lib/components';

  const status = $derived($page.status);
  const message = $derived($page.error?.message ?? '');
  const isNotFound = $derived(status === 404);
</script>

<svelte:head>
  <title>{isNotFound ? 'Page introuvable' : 'Erreur'} — Philum</title>
</svelte:head>

<div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-20 text-center">
  <p class="text-7xl font-bold text-blue-600 mb-4">{status}</p>
  <h1 class="text-3xl font-bold text-ink-primary mb-4">
    {#if isNotFound}
      Cette page n'existe pas
    {:else}
      Une erreur est survenue
    {/if}
  </h1>
  <p class="text-ink-secondary mb-8">
    {#if isNotFound}
      Le lien que vous avez suivi est peut-être périmé, ou la fiche a été supprimée.
    {:else if message}
      {message}
    {:else}
      Réessayez dans un instant. Si le problème persiste, signalez-le sur GitHub.
    {/if}
  </p>
  <div class="flex flex-col sm:flex-row items-center justify-center gap-3">
    <Button href="/" variant="primary">Retour à l'accueil</Button>
    {#if isNotFound}
      <Button href="/@example/memoire-et-cerveau" variant="secondary">Voir la fiche démo</Button>
    {:else}
      <Button href="https://github.com/Mathias-PP/filum/issues" variant="secondary">
        Signaler un problème
      </Button>
    {/if}
  </div>
</div>
