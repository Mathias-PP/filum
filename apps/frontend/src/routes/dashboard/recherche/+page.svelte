<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/stores';
  import { api, ApiError } from '$lib/api';
  import { Button, ExcerptSearchResults } from '$lib/components';
  import type { ExcerptSearchHit } from '$lib/api';

  let question = $state('');
  let cherche = $state(false);
  // null = aucune recherche lancée. À distinguer de « recherche faite, rien
  // trouvé » : les deux écrans ne disent pas la même chose.
  let resultats = $state<ExcerptSearchHit[] | null>(null);
  let questionPosee = $state('');
  let indisponible = $state(false);
  let erreur = $state('');

  // Dernière question envoyée au serveur. Volontairement hors `$state` : elle
  // ne sert qu'à empêcher l'effet ci-dessous de relancer une recherche qu'on
  // vient de lancer soi-même, et la rendre réactive rappellerait l'effet.
  let derniereLancee = '';

  async function lancer(q: string) {
    cherche = true;
    erreur = '';
    indisponible = false;
    try {
      const reponse = await api.excerpts.search(q);
      questionPosee = q;
      indisponible = !reponse.available;
      resultats = reponse.results;
    } catch (e) {
      erreur =
        e instanceof ApiError
          ? e.message
          : 'La recherche n’a pas abouti. Réessayez dans quelques instants.';
      resultats = null;
    } finally {
      cherche = false;
    }
  }

  // L'URL porte la question, comme sur /discover : un résultat se recharge, se
  // partage et se retrouve par le bouton Retour. Sans cela, une recherche
  // coûteuse à formuler disparaissait au premier rafraîchissement.
  $effect(() => {
    const q = $page.url.searchParams.get('q')?.trim() ?? '';
    if (q === derniereLancee) return;
    derniereLancee = q;
    question = q;
    if (!q) {
      resultats = null;
      questionPosee = '';
      return;
    }
    void lancer(q);
  });

  async function chercher(event: SubmitEvent) {
    event.preventDefault();
    const q = question.trim();
    if (!q || cherche) return;

    // Reposer la même question ne change pas l'URL, donc ne réveille pas
    // l'effet : on relance ici, sinon le bouton resterait sans effet.
    if (q === derniereLancee) {
      await lancer(q);
      return;
    }
    derniereLancee = q;
    await goto(`?q=${encodeURIComponent(q)}`, { keepFocus: true });
    await lancer(q);
  }
</script>

<svelte:head>
  <title>Chercher dans mes extraits | Philum</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-6">
    <a href="/dashboard" class="text-sm text-ink-secondary hover:text-ink-primary"
      >&larr; Tableau de bord</a
    >
    <h1 class="font-serif text-3xl text-ink-primary mt-2 mb-1">Chercher dans mes extraits</h1>
    <p class="text-sm text-ink-secondary">
      La recherche compare le sens, pas les mots : décrivez ce que le passage disait, sans avoir à
      le citer. Elle porte sur vos extraits, toutes fiches confondues.
    </p>
  </div>

  <form onsubmit={chercher} class="flex flex-col sm:flex-row gap-2 mb-8">
    <input
      type="search"
      bind:value={question}
      maxlength="500"
      placeholder="Par exemple : l’effet du sommeil sur la consolidation des souvenirs"
      aria-label="Ce que vous cherchez"
      class="flex-1 rounded-lg border border-border bg-surface-primary px-3 py-2 text-ink-primary placeholder:text-ink-tertiary focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-info"
    />
    <Button type="submit" variant="primary" disabled={cherche || question.trim().length === 0}>
      {cherche ? 'Recherche…' : 'Chercher'}
    </Button>
  </form>

  <ExcerptSearchResults {resultats} question={questionPosee} {cherche} {indisponible} {erreur} />
</div>
