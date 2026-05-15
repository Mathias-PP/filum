<svelte:head>
  <title>Feuille de route — Filum</title>
  <meta
    name="description"
    content="La feuille de route de Filum : ce qui est disponible, ce qui arrive, et ce qui est prévu pour le futur."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-4">Feuille de route</h1>
  <p class="text-xl text-ink-secondary mb-12">
    Filum est en construction active. Voici les grandes étapes, passées et à venir.
  </p>

  <div class="space-y-12">
    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="w-3 h-3 rounded-full bg-emerald-500 shrink-0"></span>
        <h2 class="text-2xl font-semibold text-ink-primary">MVP : livré</h2>
        <span class="text-xs bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full"
          >Disponible</span
        >
      </div>
      <ul class="space-y-3 ml-6">
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Création de fiches de lecture avec titre, description, plateforme
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Ajout de sources avec 6 types, annotation, extraits
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Graphe interactif D3.js avec sources clés
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Attestation cryptographique Ed25519 des liens créateur·ice ↔ contenu
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Archivage automatique par Wayback Machine
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Extraction automatique des métadonnées (titre, auteurs, date)
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Authentification Google OAuth
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <svg
            class="w-5 h-5 text-emerald-500 shrink-0 mt-0.5"
            viewBox="0 0 20 20"
            fill="currentColor"
            ><path
              fill-rule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clip-rule="evenodd"
            /></svg
          >
          Pages publiques avec OpenGraph dynamique
        </li>
      </ul>
    </div>

    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="w-3 h-3 rounded-full bg-blue-500 shrink-0"></span>
        <h2 class="text-2xl font-semibold text-ink-primary">Prochainement</h2>
        <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">En cours</span>
      </div>
      <ul class="space-y-3 ml-6">
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-blue-500 shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Copier-coller de bibliographie pour auto-génération de fiches
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-blue-500 shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Import Zotero / BibTeX / Obsidian
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-blue-500 shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Export PDF / CSV / Excel / JSON / BibTeX
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-blue-500 shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Repérage automatique des citations dans les sources (IA)
        </li>
      </ul>
    </div>

    <div>
      <div class="flex items-center gap-3 mb-4">
        <span class="w-3 h-3 rounded-full bg-slate-300 shrink-0"></span>
        <h2 class="text-2xl font-semibold text-ink-primary">Futur</h2>
        <span class="text-xs bg-surface-tertiary text-ink-tertiary px-2 py-0.5 rounded-full"
          >À venir</span
        >
      </div>
      <ul class="space-y-3 ml-6">
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Bibliographies collaboratives (édition à plusieurs)
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Extension navigateur (ajout de source en un clic)
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          API publique REST + serveur MCP
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Score de qualité des références (variété, autorité, diversité)
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Plugin WordPress / Notion / Medium
        </li>
        <li class="flex items-start gap-2 text-ink-secondary">
          <span
            class="w-5 h-5 text-ink-tertiary shrink-0 mt-0.5 flex items-center justify-center text-sm"
            >→</span
          >
          Filum Desktop (application de bureau)
        </li>
      </ul>
    </div>
  </div>
</div>
