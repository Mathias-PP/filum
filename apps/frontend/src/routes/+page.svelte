<script lang="ts">
  import { Button } from '$lib/components'
</script>

<svelte:head>
  <title>Filum - Infrastructure ouverte de provenance</title>
  <meta name="description" content="Transformez votre bibliography en une fiche publique interactive avec sources archivées et signées cryptographiquement." />
</svelte:head>

<div class="relative">
  <section class="relative overflow-hidden">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32">
      <div class="text-center max-w-3xl mx-auto">
        <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 tracking-tight mb-6">
          Rendez visible la <span class="text-blue-600">provenance</span> de votre contenu
        </h1>
        <p class="text-xl text-slate-600 mb-8 text-balance">
          Filum permet aux créateurs de transformer leur bibliography en une fiche publique interactive : 
          sources organisées, archivées et signées cryptographiquement.
        </p>
        <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button href="/api/v1/auth/login" variant="primary" size="lg">
            Créer ma première fiche
          </Button>
          <Button href="/@example/filum-demo" variant="secondary" size="lg">
            Voir un exemple
          </Button>
        </div>
      </div>
    </div>
  </section>

  <section class="bg-slate-50 py-20">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <h2 class="text-3xl font-bold text-center text-slate-900 mb-12">Comment ça marche</h2>
      <div class="grid md:grid-cols-3 gap-8">
        <div class="text-center">
          <div class="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">1. Sourcer</h3>
          <p class="text-slate-600">Ajoutez vos sources : articles, études, documents. Chaque source est automatiquement archivée.</p>
        </div>
        <div class="text-center">
          <div class="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">2. Signer</h3>
          <p class="text-slate-600">Votre fiche est signée avec une clé Ed25519. Hash SHA-256 et horodatage garantissent l'authenticité.</p>
        </div>
        <div class="text-center">
          <div class="w-16 h-16 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">3. Partager</h3>
          <p class="text-slate-600">Partagez votre page publique. Graphe interactif, statistiques, export PDF. Vérifiable par tous.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="py-20">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-12">
        <h2 class="text-3xl font-bold text-slate-900 mb-4">Pour qui ?</h2>
        <p class="text-xl text-slate-600 max-w-2xl mx-auto">
          Filum s'adresse à tous les créateurs qui veulent rendre visible la qualité de leur sourçage.
        </p>
      </div>
      <div class="grid md:grid-cols-3 gap-6">
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Vulgarisateurs scientifiques</h3>
          <p class="text-slate-600">Rendez visible la rigueur de votre travail de recherche. Montrez que vos affirmations sont sourcées.</p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Journalistes</h3>
          <p class="text-slate-600">Protégez vos sources dans le temps. Prouvez votre méthodologies face aux critiques.</p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Chercheurs</h3>
          <p class="text-slate-600">Partagez vos bibliographies sous forme navigable. Facilitez la vérification par vos pairs.</p>
        </div>
      </div>
    </div>
  </section>

  <section class="bg-blue-600 text-white py-16">
    <div class="max-w-4xl mx-auto px-4 text-center">
      <h2 class="text-3xl font-bold mb-4">Prêt à commencer ?</h2>
      <p class="text-xl text-blue-100 mb-8">
        Rejoignez les créateurs qui prennent le temps de bien sourcer leur travail.
      </p>
      <Button href="/api/v1/auth/login" variant="secondary" size="lg" class="bg-white text-blue-600 hover:bg-blue-50">
        Créer ma fiche gratuitement
      </Button>
    </div>
  </section>
</div>
