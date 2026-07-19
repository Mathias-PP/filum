<script lang="ts">
  import { reveal } from '$lib/actions/reveal';

  const API_BASE = 'https://philum-api.duckdns.org/api/v1';
  const MCP_URL = 'https://philum-api.duckdns.org/mcp';

  const publicEndpoints = [
    {
      method: 'GET',
      path: '/@{createur}/{fiche}',
      desc: 'Détail public d’une fiche publiée : métadonnées, créateur·ice et sources.',
      example: `${API_BASE}/@example/memoire-et-cerveau`,
    },
    {
      method: 'GET',
      path: '/@{createur}/{fiche}/export?format=…',
      desc: 'Export de la bibliographie. Formats : json, csv, bibtex, markdown (Obsidian), xlsx, docx.',
      example: `${API_BASE}/@example/memoire-et-cerveau/export?format=bibtex`,
    },
    {
      method: 'GET',
      path: '/users/@{createur}',
      desc: 'Profil public d’un·e créateur·ice et ses fiches publiées.',
      example: `${API_BASE}/users/@example`,
    },
    {
      method: 'GET',
      path: '/sources/extract?url=…',
      desc: 'Extraction de métadonnées (titre, auteurs, date, citations) depuis une URL — DOI, PII ScienceDirect, HTML. Limité à 10 req/min.',
      example: `${API_BASE}/sources/extract?url=https://doi.org/10.1038/nature12373`,
    },
    {
      method: 'GET',
      path: '/attestations/{id}/verify',
      desc: 'Vérifie la signature cryptographique d’une attestation de contenu (Ed25519).',
      example: null,
    },
  ];

  const mcpTools = [
    ['search_cards', 'Recherche de fiches publiées par titre ou créateur·ice.'],
    ['get_card', 'Détail d’une fiche (créateur + slug) avec ses sources.'],
    ['get_source', 'Détail complet d’une source (annotation, archive, taxonomie).'],
    ['find_cards_citing', 'Quelles fiches citent une URL donnée.'],
  ];

  const mcpConfig = `{
  "mcpServers": {
    "philum": {
      "url": "${MCP_URL}"
    }
  }
}`;
</script>

<svelte:head>
  <title>API &amp; développeurs — Philum</title>
  <meta
    name="description"
    content="API REST publique et serveur MCP de Philum : fiches, sources, exports, extraction de métadonnées et vérification d'attestations."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <div use:reveal>
    <p class="page-overline">Développeurs</p>
    <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-4">API publique</h1>
    <p class="text-lg text-ink-secondary leading-relaxed mb-8">
      Toutes les données publiées sur Philum sont accessibles en lecture via une API REST ouverte,
      sans clé ni authentification. Pas de lock-in : ce que vous voyez sur une fiche, vous pouvez le
      récupérer en JSON.
    </p>
  </div>

  <section use:reveal class="mb-12">
    <h2 class="text-2xl font-semibold text-ink-primary mb-3">URL de base</h2>
    <pre
      class="bg-surface-secondary border border-border rounded-xl p-4 text-sm overflow-x-auto"><code
        >{API_BASE}</code
      ></pre>
    <p class="text-sm text-ink-secondary mt-2">
      Référence interactive complète (OpenAPI) :
      <a
        href="https://philum-api.duckdns.org/api/v1/docs"
        target="_blank"
        rel="noopener"
        class="text-accent hover:underline">philum-api.duckdns.org/api/v1/docs</a
      >
    </p>
  </section>

  <section class="mb-12">
    <h2 class="text-2xl font-semibold text-ink-primary mb-4" use:reveal>
      Endpoints publics (sans authentification)
    </h2>
    <div class="space-y-4">
      {#each publicEndpoints as ep, i (ep.path)}
        <div
          class="bg-surface-secondary border border-border rounded-xl p-5"
          use:reveal
          style="transition-delay: {i * 60}ms"
        >
          <div class="flex items-baseline gap-2 flex-wrap">
            <span
              class="text-xs font-bold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200"
              >{ep.method}</span
            >
            <code class="text-sm font-semibold text-ink-primary break-all">{ep.path}</code>
          </div>
          <p class="text-sm text-ink-secondary mt-2">{ep.desc}</p>
          {#if ep.example}
            <pre
              class="mt-3 bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto"><code
                >curl "{ep.example}"</code
              ></pre>
          {/if}
        </div>
      {/each}
    </div>
    <p class="text-sm text-ink-secondary mt-4" use:reveal>
      Les endpoints d'écriture (création de fiches et de sources, imports, publication) requièrent
      une session authentifiée. Des jetons d'API personnels sont prévus sur la roadmap.
    </p>
  </section>

  <section class="mb-12">
    <h2 class="text-2xl font-semibold text-ink-primary mb-3" use:reveal>Serveur MCP</h2>
    <p class="text-ink-secondary leading-relaxed mb-4" use:reveal>
      Philum expose un serveur <a
        href="https://modelcontextprotocol.io"
        target="_blank"
        rel="noopener"
        class="text-accent hover:underline">Model Context Protocol</a
      >
      en lecture seule : un assistant IA (Claude, etc.) peut interroger les bibliographies publiées et
      citer ses sources.
    </p>
    <div class="bg-surface-secondary border border-border rounded-xl p-5 mb-4" use:reveal>
      <p class="text-sm font-semibold text-ink-primary mb-2">
        Configuration client (Claude Desktop, Claude Code…)
      </p>
      <pre
        class="bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto"><code
          >{mcpConfig}</code
        ></pre>
    </div>
    <div class="space-y-2">
      {#each mcpTools as [name, desc], i (name)}
        <div class="flex gap-3 items-baseline" use:reveal style="transition-delay: {i * 50}ms">
          <code class="text-sm font-semibold text-ink-primary shrink-0">{name}</code>
          <span class="text-sm text-ink-secondary">{desc}</span>
        </div>
      {/each}
    </div>
  </section>

  <section use:reveal>
    <h2 class="text-2xl font-semibold text-ink-primary mb-3">Bonnes pratiques</h2>
    <ul class="list-disc pl-5 text-sm text-ink-secondary space-y-2">
      <li>
        Les réponses des fiches publiques sont cachées 5 minutes (<code>Cache-Control</code>) —
        inutile de poller plus vite.
      </li>
      <li>
        L'extraction de métadonnées est limitée à 10 requêtes/minute par IP ; les autres endpoints
        publics ont des limites plus larges.
      </li>
      <li>
        Le format d'export <code>json</code> est versionné (<code>philum_export_version</code>) :
        fiez-vous à ce champ pour la compatibilité.
      </li>
    </ul>
  </section>
</div>
