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
      desc: 'Export de la bibliographie. Formats : json, csv, bibtex, ris, csl, apa, markdown (Obsidian), xlsx, docx.',
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
      desc: 'Extraction de métadonnées (titre, auteurs, date, citations) depuis une URL : DOI, PII ScienceDirect, HTML. Limité à 10 req/min.',
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
    ['create_card, add_source, add_excerpt', 'Construire une fiche, source par source.'],
    ['import_from_content_url', 'Extraire les sources citées dans un contenu.'],
    ['suggest_excerpts, annotate_excerpt', 'Propositions d’extraits et de mises en situation.'],
    ['verify_excerpts', 'Relire les extraits posés face à la page d’origine.'],
    ['create_content_attestation', 'Signer le contenu documenté en Ed25519.'],
    ['publish_card', 'Publier la fiche.'],
  ];

  const mcpConfigPublic = `{
  "mcpServers": {
    "philum": {
      "url": "${MCP_URL}/"
    }
  }
}`;

  const mcpConfigCompte = `{
  "mcpServers": {
    "philum": {
      "url": "${MCP_URL}-account/"
    }
  }
}`;

  const mcpConfigGemini = `{
  "mcpServers": {
    "philum": {
      "httpUrl": "${MCP_URL}-account/"
    }
  }
}`;

  // Groupes d'outils MCP (39 outils, verifies le 2026-08-21).
  const mcpGroupes = [
    {
      titre: 'Lecture publique',
      outils: ['search_cards', 'get_card', 'get_source', 'find_cards_citing'],
    },
    { titre: 'Identite', outils: ['whoami'] },
    {
      titre: 'Fiche',
      outils: [
        'create_card',
        'update_card',
        'delete_card',
        'restore_card',
        'list_my_cards',
        'list_deleted_cards',
        'publish_card',
        'set_content_text',
      ],
    },
    {
      titre: 'Sources',
      outils: [
        'add_source',
        'add_sources_batch',
        'update_source',
        'delete_source',
        'list_sources',
        'archive_sources',
      ],
    },
    {
      titre: 'Extraits',
      outils: [
        'add_excerpt',
        'delete_excerpt',
        'verify_excerpts',
        'suggest_excerpts',
        'annotate_excerpt',
        'chunk_text',
        'search_my_excerpts',
      ],
    },
    {
      titre: 'Connexions',
      outils: [
        'list_connections',
        'confirm_connection',
        'remove_connection',
        'list_incoming_citations',
        'mark_citations_seen',
      ],
    },
    {
      titre: 'Imports',
      outils: [
        'import_from_content_url',
        'get_youtube_transcript',
        'get_url_metadata',
        'parse_biblio',
      ],
    },
    {
      titre: 'Attestations',
      outils: ['create_content_attestation', 'get_attestation', 'verify_attestation'],
    },
    { titre: 'Autre', outils: ['create_claim_request'] },
  ];

  let copie = $state('');
  let copieTimer: ReturnType<typeof setTimeout>;
  function copier(texte: string, cle: string) {
    if (typeof navigator === 'undefined' || !navigator.clipboard) return;
    navigator.clipboard.writeText(texte).then(() => {
      copie = cle;
      clearTimeout(copieTimer);
      copieTimer = setTimeout(() => (copie = ''), 2000);
    });
  }
</script>

<svelte:head>
  <title>API &amp; développeurs | Philum</title>
  <meta
    name="description"
    content="API REST publique et serveur MCP de Philum : fiches, sources, exports, extraction de métadonnées et vérification d'attestations."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <div use:reveal>
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
        class="text-info hover:underline">philum-api.duckdns.org/api/v1/docs</a
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
      une session authentifiée. Pour écrire depuis un assistant, utiliser le serveur MCP avec votre
      compte (ci-dessous) : l'autorisation se fait en un clic dans le navigateur.
    </p>
  </section>

  <section class="mb-12">
    <h2 class="text-2xl font-semibold text-ink-primary mb-3" use:reveal>Serveur MCP</h2>
    <p class="text-ink-secondary leading-relaxed mb-4" use:reveal>
      Philum expose un serveur <a
        href="https://modelcontextprotocol.io"
        target="_blank"
        rel="noopener"
        class="text-info hover:underline">Model Context Protocol</a
      >
      : un assistant IA (Claude, Cursor, Gemini…) peut interroger les bibliographies publiées, citer ses
      sources, et construire des fiches à votre place. Deux adresses, selon ce que vous voulez faire.
    </p>

    <div class="grid gap-4 sm:grid-cols-2 mb-4" use:reveal>
      {#each [['Lecture publique', `${MCP_URL}/`, 'pub'], ['Avec votre compte', `${MCP_URL}-account/`, 'compte']] as [titre, adresse, cle] (cle)}
        <div class="bg-surface-secondary border border-border rounded-xl p-5">
          <p class="text-sm font-semibold text-ink-primary mb-2">{titre}</p>
          <code class="block text-sm break-all text-ink-primary mb-2">{adresse}</code>
          <button
            type="button"
            class="text-xs text-info hover:underline"
            onclick={() => copier(adresse, cle)}
          >
            {copie === cle ? 'Copie' : "Copier l'adresse"}
          </button>
        </div>
      {/each}
    </div>
    <p class="text-sm text-ink-secondary mb-6" use:reveal>
      C'est l'adresse a coller dans le champ MCP server URL de ChatGPT ou d'un connecteur Claude.
      Garder la barre finale : sans elle le serveur répond une redirection que tous les clients ne
      suivent pas sur un POST.
    </p>

    <h3 class="text-lg font-semibold text-ink-primary mb-3" use:reveal>Recettes par client</h3>
    <div class="space-y-4 mb-6">
      <div class="bg-surface-secondary border border-border rounded-xl p-5" use:reveal>
        <p class="text-sm font-semibold text-ink-primary mb-2">Claude Code</p>
        <pre
          class="bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto mb-2"><code
            >claude mcp add --transport http philum {MCP_URL}-account/</code
          ></pre>
      </div>
      <div class="bg-surface-secondary border border-border rounded-xl p-5" use:reveal>
        <p class="text-sm font-semibold text-ink-primary mb-1">Claude (application) et ChatGPT</p>
        <p class="text-sm text-ink-secondary">
          Ajouter un connecteur, coller l'URL de votre choix ci-dessus. Rien d'autre à saisir.
        </p>
      </div>
      <div class="bg-surface-secondary border border-border rounded-xl p-5" use:reveal>
        <p class="text-sm font-semibold text-ink-primary mb-1">Gemini CLI</p>
        <p class="text-sm text-ink-secondary mb-2">
          Dans <code>~/.gemini/settings.json</code>. Chez Gemini CLI, <code>url</code> designe le
          transport SSE que Philum n'expose pas. Il faut <code>httpUrl</code>.
        </p>
        <pre
          class="bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto"><code
            >{mcpConfigGemini}</code
          ></pre>
      </div>
      <div class="bg-surface-secondary border border-border rounded-xl p-5" use:reveal>
        <p class="text-sm font-semibold text-ink-primary mb-2">Cursor, opencode, Codex</p>
        <pre
          class="bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto"><code
            >{mcpConfigCompte}</code
          ></pre>
      </div>
    </div>

    <h3 class="text-lg font-semibold text-ink-primary mb-3" use:reveal>39 outils disponibles</h3>
    <div class="space-y-4">
      {#each mcpGroupes as groupe, gi (groupe.titre)}
        <div use:reveal style="transition-delay: {gi * 40}ms">
          <p class="text-xs font-medium uppercase tracking-wider text-ink-tertiary mb-1">
            {groupe.titre}
          </p>
          <div class="flex flex-wrap gap-x-3 gap-y-0.5">
            {#each groupe.outils as name (name)}
              <code class="text-sm text-ink-primary">{name}</code>
            {/each}
          </div>
        </div>
      {/each}
    </div>
  </section>

  <section id="tunnel-ollama" class="mb-12" use:reveal>
    <h2 class="text-2xl font-semibold text-ink-primary mb-3">Brancher un modele local (Ollama)</h2>
    <p class="text-ink-secondary leading-relaxed mb-4">
      Le backend Philum tourne sur une VM distante : il ne peut pas joindre
      <code>localhost</code> sur votre machine. Pour utiliser Ollama ou tout autre modele local, exposez-le
      via un tunnel HTTPS et branchez-le comme provider custom.
    </p>

    <ol class="list-decimal pl-5 text-sm text-ink-secondary space-y-4">
      <li>
        <span class="text-ink-primary font-medium">Lancer Ollama et charger un modele.</span>
        <pre
          class="mt-2 bg-surface-primary border border-border rounded-lg p-3 text-xs overflow-x-auto"><code
            >ollama run llama3.2</code
          ></pre>
      </li>
      <li>
        <span class="text-ink-primary font-medium">Ouvrir un tunnel HTTPS.</span>
        <p class="mt-1">
          Deux options gratuites qui preservent l'authentification (recommandees face a ngrok sans
          auth, qui expose publiquement votre endpoint) :
        </p>
        <ul class="list-disc pl-5 mt-2 space-y-1">
          <li>
            <strong>Cloudflare Tunnel</strong> : stable, URL fixe avec Access auth, gratuit.
            <a
              href="https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/create-remote-tunnel/"
              target="_blank"
              rel="noopener"
              class="text-info hover:underline">Guide Cloudflare</a
            >
          </li>
          <li>
            <strong>Tailscale Funnel</strong> : necessiteer un compte Tailscale, URL fixe, zero
            config une fois installe.
            <a
              href="https://tailscale.com/kb/1223/funnel"
              target="_blank"
              rel="noopener"
              class="text-info hover:underline">Guide Tailscale Funnel</a
            >
          </li>
        </ul>
      </li>
      <li>
        <span class="text-ink-primary font-medium">Récupérer l'URL publique HTTPS</span> (ex. :
        <code>https://mon-tunnel.example.com</code>).
      </li>
      <li>
        <span class="text-ink-primary font-medium"
          >Dans Philum : Agent &rarr; Clés &rarr; Ajouter.</span
        >
        <ul class="list-disc pl-5 mt-1 space-y-1">
          <li>Fournisseur : <code>Autre (URL à saisir)</code></li>
          <li>URL de base : <code>https://mon-tunnel.example.com/v1</code></li>
          <li>Clé API : <code>ollama</code> (Ollama l'ignore, mais le champ est requis)</li>
          <li>Modèle : nom local, ex. <code>llama3.2</code></li>
        </ul>
      </li>
    </ol>

    <div
      class="mt-4 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
    >
      <span class="font-medium">Avertissements :</span> l'URL du tunnel est accessible sur Internet
      pendant toute sa durée de vie. Activez l'authentification (Access ou Tailscale ACL). Les quick
      tunnels ngrok/Cloudflare ont une URL changeante a chaque redemarrage. Ajoutez
      <code>OLLAMA_KEEP_ALIVE=24h</code> pour eviter qu'Ollama decharge le modele entre deux messages.
    </div>
  </section>

  <section use:reveal>
    <h2 class="text-2xl font-semibold text-ink-primary mb-3">Bonnes pratiques</h2>
    <ul class="list-disc pl-5 text-sm text-ink-secondary space-y-2">
      <li>
        Les réponses des fiches publiques sont cachées 5 minutes (<code>Cache-Control</code>) :
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
