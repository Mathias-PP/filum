<svelte:head>
  <title>Fonctionnalités — Filum</title>
  <meta
    name="description"
    content="Découvrez toutes les fonctionnalités de Filum : graphe interactif, signature cryptographique, archivage, extraction automatique et plus."
  />
</svelte:head>

<div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-slate-900 mb-4">Fonctionnalités</h1>
  <p class="text-xl text-slate-600 mb-12 max-w-3xl">
    Filum est conçu pour les créateur·ice·s qui veulent rendre visible la qualité de leur sourçage.
    Voici ce que la plateforme offre aujourd'hui et ce qui est en préparation.
  </p>

  <h2 class="text-2xl font-semibold text-slate-900 mb-6">Disponibles aujourd'hui</h2>
  <div class="grid md:grid-cols-2 gap-6 mb-16">
    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Graphe interactif</h3>
      <p class="text-slate-600 text-sm">
        Visualisez vos sources sous forme de graphe dynamique. Chaque nœud représente une source,
        les pivots sont mis en avant. Exploration intuitive : cliquez, glissez, zoomez.
      </p>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
          /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Signature cryptographique</h3>
      <p class="text-slate-600 text-sm">
        Chaque fiche publiée est signée avec une clé Ed25519. Le hash SHA-256 et l'horodatage
        garantissent l'intégrité et l'authenticité du contenu. Vérifiable par n'importe qui.
      </p>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-purple-100 text-purple-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Archivage automatique</h3>
      <p class="text-slate-600 text-sm">
        Chaque source est automatiquement archivée via la Wayback Machine. Même si la page originale
        disparaît, sa copie reste accessible.
      </p>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-amber-100 text-amber-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Extraction automatique</h3>
      <p class="text-slate-600 text-sm">
        Collez une URL : Filum extrait automatiquement le titre, les auteurs, la date de publication
        et une description. Plus besoin de tout remplir à la main.
      </p>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-rose-100 text-rose-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
          /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">6 types de sources</h3>
      <p class="text-slate-600 text-sm">
        Articles scientifique, sources institutionnelles, presse, vidéos, images, sources originales
        — chaque type a son propre affichage et son propre poids dans le graphe.
      </p>
    </div>

    <div class="bg-white border border-slate-200 rounded-xl p-6">
      <div
        class="w-10 h-10 rounded-lg bg-indigo-100 text-indigo-600 flex items-center justify-center mb-3"
      >
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
          ><path
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          /><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg
        >
      </div>
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Sources clés (pivots)</h3>
      <p class="text-slate-600 text-sm">
        Marquez une source comme « pivot » pour indiquer qu'elle est structurante dans votre
        raisonnement. Elle apparaît en évidence dans le graphe.
      </p>
    </div>
  </div>

  <h2 id="a-venir" class="text-2xl font-semibold text-slate-900 mb-6">En préparation</h2>
  <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Copier-coller de bibliographie</h3>
      <p class="text-slate-600 text-sm">
        Collez votre bibliographie existante (depuis un article, YouTube, votre site) et Filum
        génère automatiquement une fiche avec les sources pré-remplies.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Citations intelligentes</h3>
      <p class="text-slate-600 text-sm">
        L'IA identifie l'emplacement exact de chaque citation dans le document source, pour y
        accéder en un clic.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Import Zotero / Obsidian</h3>
      <p class="text-slate-600 text-sm">
        Importez vos collections depuis Zotero, Obsidian, BibTeX et d'autres gestionnaires de
        références.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Bibliographies collaboratives</h3>
      <p class="text-slate-600 text-sm">
        Créez et éditez une fiche à plusieurs, avec contrôle de version et historique des
        modifications.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Export PDF / CSV / Excel</h3>
      <p class="text-slate-600 text-sm">
        Exportez vos fiches dans tous les formats : PDF, CSV, Excel, JSON, BibTeX, CSL-JSON.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">Extension navigateur</h3>
      <p class="text-slate-600 text-sm">
        Ajoutez une source en un clic depuis votre navigateur, sans quitter la page que vous
        consultez.
      </p>
    </div>
    <div class="bg-slate-50 rounded-xl p-6 border border-slate-200 border-dashed">
      <h3 class="text-lg font-semibold text-slate-900 mb-2">API publique</h3>
      <p class="text-slate-600 text-sm">
        Intégrez Filum dans vos outils : API REST publique et serveur MCP pour les agents IA.
      </p>
    </div>
  </div>
  <p class="text-sm text-slate-500">
    Ces fonctionnalités sont en cours de développement. Leur ordre d'arrivée peut varier. Des
    suggestions ? Écrivez-nous.
  </p>
</div>
