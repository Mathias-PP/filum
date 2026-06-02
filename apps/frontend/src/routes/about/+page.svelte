<svelte:head>
  <title>À propos — Philum</title>
  <meta
    name="description"
    content="Philum est un outil de gestion de références bibliographiques qui transforme votre bibliographie en graphe interactif et vérifiable."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-8">À propos de Philum</h1>

  <section class="prose prose-slate dark:prose-invert max-w-none">
    <p class="text-lg text-ink-secondary leading-relaxed">
      Philum est un outil de gestion de références bibliographiques qui permet aux créateur·ice·s de
      contenu de constituer, organiser et partager leurs sources de manière transparente et
      vérifiable.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">L'histoire</h2>
    <p class="text-ink-secondary leading-relaxed">
      Philum est né d'un constat simple : sur YouTube, Twitch, Twitter, dans les newsletters et les
      blogs, les créateur·ice·s citent des sources, mais ces citations sont souvent perdues dans le
      flux, difficiles à retrouver, impossibles à vérifier.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Un vidéaste cite une étude ? Elle est noyée dans la description, parfois sans lien. Un
      journaliste mentionne un rapport ? Bonne chance pour le retrouver six mois plus tard. Un
      vulgaristeur s'appuie sur une thèse ? Qui vérifie que la source existe vraiment ?
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Philum répond à ce problème en offrant un espace dédié où chaque source est documentée et
      archivée, et où chaque revendication d'un contenu original par son créateur·ice est attestée
      par signature cryptographique.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Nos valeurs</h2>
    <div class="space-y-4 not-prose">
      <div class="bg-surface-secondary rounded-xl p-5">
        <h3 class="font-semibold text-ink-primary mb-1">Transparence</h3>
        <p class="text-sm text-ink-secondary">
          Chaque source est visible, chaque citation est traçable. Rien n'est caché.
        </p>
      </div>
      <div class="bg-surface-secondary rounded-xl p-5">
        <h3 class="font-semibold text-ink-primary mb-1">Pérennité</h3>
        <p class="text-sm text-ink-secondary">
          Les sources sont archivées. Les signatures sont vérifiables. Ce qui est publié aujourd'hui
          le reste demain.
        </p>
      </div>
      <div class="bg-surface-secondary rounded-xl p-5">
        <h3 class="font-semibold text-ink-primary mb-1">Liberté</h3>
        <p class="text-sm text-ink-secondary">
          Pas de lock-in. Les données sont exportables, l'API est ouverte. Vous gardez le contrôle
          de votre travail.
        </p>
      </div>
    </div>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Pourquoi Philum ?</h2>
    <p class="text-ink-secondary leading-relaxed">
      Parce que citer ses références est un geste essentiel du travail intellectuel, mais qu'il est
      rarement mis en valeur. Philum le rend visible, vérifiable et durable : un service public pour
      la qualité de l'information en ligne.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Le nom « Philum » s'inspire du <em>phylum</em> biologique : la branche de l'arbre du vivant qui
      regroupe les espèces par parenté évolutive. Comme un phylum, une fiche Philum dessine un arbre de
      filiation : chaque affirmation reliée à ses sources, chaque source à ses origines. Le nom évoque
      aussi le fil : celui d'Ariane, celui d'une argumentation qui tisse une bibliographie cohérente.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Qui est-ce que ça concerne ?</h2>
    <p class="text-ink-secondary leading-relaxed mb-6">
      Philum s'adresse à tou·te·s les créateur·ice·s qui veulent rendre visible la qualité de leurs
      références, y compris celles et ceux qui ne se reconnaissent pas dans les catégories
      traditionnelles.
    </p>
    <div class="grid gap-6 not-prose mt-6">
      <div class="bg-surface-secondary rounded-xl p-6">
        <h3 class="text-lg font-semibold text-ink-primary mb-2">Vulgarisateurs scientifiques</h3>
        <p class="text-ink-secondary">
          Montrez la rigueur de votre travail en rendant chaque source visible et vérifiable par
          votre audience.
        </p>
      </div>
      <div class="bg-surface-secondary rounded-xl p-6">
        <h3 class="text-lg font-semibold text-ink-primary mb-2">Journalistes</h3>
        <p class="text-ink-secondary">
          Protégez vos sources dans le temps et prouvez votre méthodologie face aux critiques.
        </p>
      </div>
      <div class="bg-surface-secondary rounded-xl p-6">
        <h3 class="text-lg font-semibold text-ink-primary mb-2">Chercheurs</h3>
        <p class="text-ink-secondary">
          Partagez vos bibliographies sous forme navigable et facilitez la vérification par vos
          pairs.
        </p>
      </div>
      <div class="bg-surface-secondary rounded-xl p-6">
        <h3 class="text-lg font-semibold text-ink-primary mb-2">Créateur·ice·s de contenu</h3>
        <p class="text-ink-secondary">
          Chaque source mérite d'être citée, quel que soit votre format.
        </p>
      </div>
    </div>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Technologie</h2>
    <p class="text-ink-secondary leading-relaxed">
      Philum utilise la cryptographie Ed25519 pour signer chaque revendication de contenu original
      (vidéo, article, podcast…) par son créateur·ice, garantissant que ces attestations proviennent
      bien de la personne qu'elles désignent et qu'elles datent bien du moment indiqué. L'archivage
      des sources via Wayback Machine permet de préserver les références même si les pages
      originales disparaissent. Le tout est présenté dans un graphe interactif qui rend la
      navigation intuitive.
    </p>
    <p class="text-ink-secondary leading-relaxed">
      Pour les détails techniques complets (signature, hachage, gestion des clés), rendez-vous sur
      la page
      <a href="/security" class="text-blue-600 hover:text-blue-800 underline">Sécurité</a>.
    </p>

    <h2 class="text-2xl font-semibold text-ink-primary mt-12 mb-4">Contribuer</h2>
    <p class="text-ink-secondary leading-relaxed">
      Le projet est ouvert sur
      <a
        href="https://github.com/Mathias-PP/filum"
        class="text-blue-600 hover:text-blue-800 underline">GitHub</a
      >.
    </p>
  </section>
</div>
