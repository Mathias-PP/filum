<script lang="ts">
  import { reveal } from '$lib/actions/reveal';

  type Phase = {
    title: string;
    badge: string;
    status: 'done' | 'current' | 'future';
    items: string[];
  };

  const phases: Phase[] = [
    {
      title: 'MVP : livré',
      badge: 'Disponible',
      status: 'done',
      items: [
        'Création de fiches de lecture avec titre, description, plateforme',
        "Ajout de sources avec taxonomie à trois axes (format, catégorie, type d'auteur·ice), annotation, extraits",
        'Graphe interactif D3.js avec sources clés',
        'Attestation cryptographique Ed25519 des liens créateur·ice ↔ contenu',
        'Archivage automatique par Wayback Machine',
        'Extraction automatique des métadonnées (titre, auteurs, date)',
        'Authentification Google OAuth',
        'Pages publiques avec OpenGraph dynamique',
      ],
    },
    {
      title: 'Prochainement',
      badge: 'En cours',
      status: 'current',
      items: [
        'Copier-coller de bibliographie pour auto-génération de fiches',
        'Import Zotero / BibTeX / Obsidian',
        'Export PDF / CSV / Excel / JSON / BibTeX',
        'Repérage automatique des citations dans les sources (IA)',
      ],
    },
    {
      title: 'Futur',
      badge: 'À venir',
      status: 'future',
      items: [
        'Bibliographies collaboratives (édition à plusieurs)',
        'Extension navigateur (ajout de source en un clic)',
        'API publique REST + serveur MCP',
        'Score de qualité des références (variété, autorité, diversité)',
        'Plugin WordPress / Notion / Medium',
        'Philum Desktop (application de bureau)',
      ],
    },
  ];
</script>

<svelte:head>
  <title>Feuille de route — Philum</title>
  <meta
    name="description"
    content="La feuille de route de Philum : ce qui est disponible, ce qui arrive, et ce qui est prévu pour le futur."
  />
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
  <div use:reveal>
    <p class="page-overline">Vision</p>
    <h1 class="text-3xl sm:text-4xl font-bold text-ink-primary mb-4">Feuille de route</h1>
    <p class="text-xl text-ink-secondary mb-12">
      Philum est en construction active. Voici les grandes étapes, passées et à venir.
    </p>
  </div>

  <div class="timeline">
    {#each phases as phase, pi (phase.title)}
      <section class="timeline-phase" use:reveal style="transition-delay: {pi * 100}ms">
        <div class="timeline-marker" aria-hidden="true">
          <span class="timeline-dot {phase.status}"></span>
        </div>
        <div class="pb-12">
          <div class="flex flex-wrap items-center gap-3 mb-5">
            <h2 class="text-2xl font-semibold text-ink-primary">{phase.title}</h2>
            {#if phase.status === 'done'}
              <span
                class="text-xs font-medium bg-success-bg text-success px-2.5 py-0.5 rounded-full"
              >
                {phase.badge}
              </span>
            {:else if phase.status === 'current'}
              <span class="text-xs font-medium bg-info-bg text-info px-2.5 py-0.5 rounded-full">
                {phase.badge}
              </span>
            {:else}
              <span
                class="text-xs font-medium bg-surface-tertiary text-ink-tertiary px-2.5 py-0.5 rounded-full"
              >
                {phase.badge}
              </span>
            {/if}
          </div>
          <ul class="space-y-3">
            {#each phase.items as item (item)}
              <li class="flex items-start gap-2.5 text-ink-secondary">
                {#if phase.status === 'done'}
                  <svg
                    class="w-5 h-5 text-success shrink-0 mt-0.5"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    aria-hidden="true"
                    ><path
                      fill-rule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clip-rule="evenodd"
                    /></svg
                  >
                {:else}
                  <span
                    class="w-5 h-5 shrink-0 mt-0.5 flex items-center justify-center text-sm {phase.status ===
                    'current'
                      ? 'text-info'
                      : 'text-ink-tertiary'}"
                    aria-hidden="true">→</span
                  >
                {/if}
                {item}
              </li>
            {/each}
          </ul>
        </div>
      </section>
    {/each}
  </div>
</div>

<style>
  .timeline {
    position: relative;
  }
  /* Vertical connecting line, fading out at the bottom */
  .timeline::before {
    content: '';
    position: absolute;
    left: 7px;
    top: 8px;
    bottom: 2rem;
    width: 2px;
    background: linear-gradient(
      to bottom,
      rgb(var(--success) / 0.55) 0%,
      rgb(var(--info) / 0.5) 45%,
      rgb(var(--border-strong)) 75%,
      transparent 100%
    );
  }
  .timeline-phase {
    position: relative;
    padding-left: 2.25rem;
  }
  .timeline-marker {
    position: absolute;
    left: 0;
    top: 6px;
  }
  .timeline-dot {
    display: block;
    width: 16px;
    height: 16px;
    border-radius: 9999px;
    border: 2px solid rgb(var(--bg-secondary));
  }
  .timeline-dot.done {
    background: rgb(var(--success));
    box-shadow: 0 0 0 4px rgb(var(--success) / 0.15);
  }
  .timeline-dot.current {
    background: rgb(var(--info));
    box-shadow: 0 0 0 4px rgb(var(--info) / 0.2);
    animation: dot-pulse 2.4s ease-in-out infinite;
  }
  .timeline-dot.future {
    background: rgb(var(--border-strong));
  }
  @keyframes dot-pulse {
    0%,
    100% {
      box-shadow: 0 0 0 4px rgb(var(--info) / 0.2);
    }
    50% {
      box-shadow: 0 0 0 8px rgb(var(--info) / 0.08);
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .timeline-dot.current {
      animation: none;
    }
  }
</style>
