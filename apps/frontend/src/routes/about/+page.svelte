<svelte:head>
  <title>À propos — Filum</title>
  <meta
    name="description"
    content="Filum est un outil de gestion de références bibliographiques qui transforme votre bibliographie en graphe interactif et vérifiable."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-slate-900 mb-8">À propos de Filum</h1>

  <section class="prose prose-slate max-w-none">
    <p class="text-lg text-slate-600 leading-relaxed">
      Filum est un outil de gestion de références bibliographiques qui permet aux créateurs de
      contenu — vulgarisateurs scientifiques, journalistes, chercheurs — de constituer, organiser et
      partager leurs sources de manière transparente et vérifiable.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Pourquoi Filum ?</h2>
    <p class="text-slate-600 leading-relaxed">
      Dans un monde où l'information circule à grande vitesse, la qualité du sourçage est devenue un
      enjeu central. Filum permet de rendre visible le travail de recherche derrière chaque
      publication, en offrant un espace dédié où chaque source est documentée, archivée et liée à
      une fiche de lecture.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Comment ça marche</h2>
    <ol class="list-decimal pl-6 space-y-4 text-slate-600">
      <li>
        <strong class="text-slate-900">Sourcer</strong> — Ajoutez vos sources (articles, études, documents)
        à une fiche de lecture. Chaque source peut être annotée et accompagnée d'extraits.
      </li>
      <li>
        <strong class="text-slate-900">Signer</strong> — La fiche est signée cryptographiquement avec
        une clé Ed25519. Le hash SHA-256 et l'horodatage garantissent l'intégrité et l'authenticité.
      </li>
      <li>
        <strong class="text-slate-900">Partager</strong> — Publiez votre fiche et partagez la page publique.
        Le graphe interactif permet à chacun d'explorer vos sources et de vérifier votre travail.
      </li>
    </ol>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Qui est-ce que ça concerne ?</h2>
    <div class="grid gap-6 not-prose mt-6">
      <div class="bg-slate-50 rounded-xl p-6">
        <h3 class="text-lg font-semibold text-slate-900 mb-2">Vulgarisateurs scientifiques</h3>
        <p class="text-slate-600">
          Montrez la rigueur de votre travail en rendant chaque source visible et vérifiable par
          votre audience.
        </p>
      </div>
      <div class="bg-slate-50 rounded-xl p-6">
        <h3 class="text-lg font-semibold text-slate-900 mb-2">Journalistes</h3>
        <p class="text-slate-600">
          Protégez vos sources dans le temps et prouvez votre méthodologie face aux critiques.
        </p>
      </div>
      <div class="bg-slate-50 rounded-xl p-6">
        <h3 class="text-lg font-semibold text-slate-900 mb-2">Chercheurs</h3>
        <p class="text-slate-600">
          Partagez vos bibliographies sous forme navigable et facilitez la vérification par vos
          pairs.
        </p>
      </div>
    </div>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Technologie</h2>
    <p class="text-slate-600 leading-relaxed">
      Filum utilise la cryptographie Ed25519 pour signer chaque fiche, garantissant ainsi que le
      contenu n'a pas été altéré depuis sa publication. L'archivage des sources via Wayback Machine
      permet de préserver les références même si les pages originales disparaissent.
    </p>

    <h2 class="text-2xl font-semibold text-slate-900 mt-12 mb-4">Contact</h2>
    <p class="text-slate-600 leading-relaxed">
      Une question, une suggestion ? Écrivez-nous à
      <a href="mailto:mathias@filum.app" class="text-blue-600 hover:text-blue-800 underline"
        >mathias@filum.app</a
      >.
    </p>
  </section>
</div>
