<script lang="ts">
  import { env } from '$env/dynamic/public';
  import { Button } from '$lib/components';
  import { reveal } from '$lib/actions/reveal';
  import type { User } from '$lib/api';

  const googleLoginUrl = `${env.PUBLIC_API_BASE_URL ?? ''}/api/v1/auth/google/login`;

  interface PageData {
    user: User | null;
  }

  let { data }: { data: PageData } = $props();
  const isAuthenticated = $derived(!!data.user);
</script>

<svelte:head>
  <title>Filum — Votre bibliographie devient une galaxie</title>
  <meta
    name="description"
    content="Filum transforme votre bibliographie en un graphe interactif : sources organisées, archivées, et chaque création que vous revendiquez est attestée cryptographiquement."
  />
</svelte:head>

<div class="relative">
  <!-- HERO: spatial dark background, galaxy SVG with 3D parallax -->
  <section class="hero relative overflow-hidden">
    <div class="hero-stars" aria-hidden="true"></div>
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24 relative">
      <div class="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
        <div class="text-center lg:text-left">
          <h1
            class="font-serif text-4xl md:text-5xl lg:text-6xl tracking-tight mb-6 text-white text-balance"
            style="font-weight: 500;"
          >
            Vous allez adorer<br />
            <span class="hero-accent">partager vos références</span>
          </h1>
          <p class="text-lg md:text-xl text-slate-300 mb-8 text-balance max-w-xl mx-auto lg:mx-0">
            Vos sources prennent vie dans un graphe interactif. Archivez, partagez et attestez
            chaque création.
          </p>
          <div
            class="flex flex-col sm:flex-row items-center lg:items-start justify-center lg:justify-start gap-3"
          >
            {#if isAuthenticated}
              <a
                href="/dashboard"
                class="hero-cta-primary inline-flex items-center justify-center gap-1.5 rounded font-medium transition-all duration-150"
                >Tableau de bord
              </a>
            {:else}
              <a href={googleLoginUrl} class="hero-cta-primary">
                <svg class="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="currentColor"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                  />
                  <path
                    fill="currentColor"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                  />
                </svg>
                Continuer avec Google
              </a>
            {/if}
            <a href="/@example/memoire-et-cerveau" class="hero-cta-secondary">
              Voir un exemple →
            </a>
          </div>
        </div>

        <!-- Galaxy SVG -->
        <div class="hero-galaxy-wrap">
          <div class="hero-galaxy">
            <svg
              viewBox="0 0 480 420"
              class="w-full max-w-md"
              role="img"
              aria-label="Illustration : galaxie de sources reliées au nœud Filum"
            >
              <defs>
                <radialGradient id="centralHalo" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stop-color="#6B8AFF" stop-opacity="0.55" />
                  <stop offset="55%" stop-color="#4A6CF7" stop-opacity="0.18" />
                  <stop offset="100%" stop-color="#4A6CF7" stop-opacity="0" />
                </radialGradient>
                <radialGradient id="nodeGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stop-color="#ffffff" stop-opacity="0.4" />
                  <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
                </radialGradient>
                <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="2.5" />
                </filter>
              </defs>

              <!-- Far background stars (small, slow drift — depth layer 3) -->
              <g class="star-layer star-layer-far" fill="#ffffff">
                <circle cx="38" cy="62" r="0.5" opacity="0.35" />
                <circle cx="170" cy="40" r="0.4" opacity="0.25" />
                <circle cx="380" cy="250" r="0.4" opacity="0.25" />
                <circle cx="20" cy="380" r="0.5" opacity="0.3" />
                <circle cx="200" cy="250" r="0.4" opacity="0.25" />
                <circle cx="300" cy="180" r="0.4" opacity="0.25" />
                <circle cx="50" cy="120" r="0.5" opacity="0.3" />
                <circle cx="410" cy="280" r="0.5" opacity="0.25" />
                <circle cx="30" cy="230" r="0.4" opacity="0.25" />
                <circle cx="430" cy="50" r="0.5" opacity="0.3" />
                <circle cx="360" cy="390" r="0.4" opacity="0.25" />
                <circle cx="460" cy="120" r="0.4" opacity="0.25" />
                <circle cx="40" cy="330" r="0.5" opacity="0.3" />
                <circle cx="420" cy="200" r="0.4" opacity="0.25" />
                <circle cx="140" cy="50" r="0.4" opacity="0.25" />
              </g>

              <!-- Mid-layer stars (medium, medium drift — depth layer 2) -->
              <g class="star-layer star-layer-mid" fill="#ffffff">
                <circle cx="105" cy="200" r="0.7" opacity="0.45" />
                <circle cx="320" cy="55" r="0.6" opacity="0.45" />
                <circle cx="450" cy="180" r="0.8" opacity="0.45" />
                <circle cx="60" cy="280" r="0.7" opacity="0.45" />
                <circle cx="340" cy="400" r="0.5" opacity="0.4" />
                <circle cx="290" cy="90" r="0.6" opacity="0.4" />
                <circle cx="350" cy="320" r="0.6" opacity="0.35" />
                <circle cx="150" cy="140" r="0.6" opacity="0.4" />
                <circle cx="250" cy="330" r="0.6" opacity="0.4" />
                <circle cx="100" cy="360" r="0.5" opacity="0.4" />
                <circle cx="310" cy="140" r="0.5" opacity="0.35" />
                <circle cx="190" cy="180" r="0.5" opacity="0.35" />
                <circle cx="130" cy="310" r="0.7" opacity="0.4" />
                <circle cx="445" cy="380" r="0.8" opacity="0.45" />
                <circle cx="160" cy="395" r="0.7" opacity="0.4" />
              </g>

              <!-- Near foreground stars (larger, faster drift, some twinkle — depth layer 1) -->
              <g class="star-layer star-layer-near" fill="#ffffff">
                <circle cx="75" cy="155" r="1.1" opacity="0.7" class="star-twinkle" />
                <circle cx="415" cy="100" r="1.3" opacity="0.6" class="star-twinkle" />
                <circle cx="265" cy="285" r="1" opacity="0.6" class="star-twinkle" />
                <circle cx="130" cy="140" r="1" opacity="0.5" class="star-twinkle" />
                <circle cx="350" cy="50" r="0.9" opacity="0.5" class="star-twinkle" />
                <circle cx="30" cy="290" r="1.1" opacity="0.55" class="star-twinkle" />
                <circle cx="210" cy="130" r="0.8" opacity="0.5" />
                <circle cx="330" cy="170" r="0.9" opacity="0.5" />
                <circle cx="180" cy="310" r="0.8" opacity="0.45" />
                <circle cx="280" cy="390" r="0.9" opacity="0.5" />
              </g>

              <!-- Central halo -->
              <circle cx="240" cy="210" r="160" fill="url(#centralHalo)" />

              <!-- Centre → sources : solid rays -->
              <g stroke="rgba(255,255,255,0.22)" stroke-width="1.2" stroke-linecap="round">
                <line x1="240" y1="210" x2="90" y2="95" />
                <line x1="240" y1="210" x2="400" y2="110" />
                <line x1="240" y1="210" x2="95" y2="335" />
                <line x1="240" y1="210" x2="405" y2="330" />
                <line x1="240" y1="210" x2="220" y2="55" />
                <line x1="240" y1="210" x2="265" y2="380" />
              </g>

              <!-- Source nodes (slight glow) -->
              <g filter="url(#softGlow)" opacity="0.55">
                <circle cx="90" cy="95" r="26" fill="#C0DD97" />
                <circle cx="400" cy="110" r="26" fill="#B5D4F4" />
                <circle cx="95" cy="335" r="26" fill="#FAC775" />
                <circle cx="405" cy="330" r="26" fill="#A7E8D9" />
                <circle cx="220" cy="55" r="24" fill="#CECBF6" />
                <circle cx="265" cy="380" r="24" fill="#FDE68A" />
              </g>
              <g>
                <circle cx="90" cy="95" r="22" fill="#C0DD97" stroke="#639922" stroke-width="1.5" />
                <circle
                  cx="400"
                  cy="110"
                  r="22"
                  fill="#B5D4F4"
                  stroke="#378ADD"
                  stroke-width="1.5"
                />
                <circle
                  cx="95"
                  cy="335"
                  r="22"
                  fill="#FAC775"
                  stroke="#EF9F27"
                  stroke-width="1.5"
                />
                <circle
                  cx="405"
                  cy="330"
                  r="22"
                  fill="#A7E8D9"
                  stroke="#2DAF8F"
                  stroke-width="1.5"
                />
                <circle
                  cx="220"
                  cy="55"
                  r="20"
                  fill="#CECBF6"
                  stroke="#7F77DD"
                  stroke-width="1.5"
                />
                <circle
                  cx="265"
                  cy="380"
                  r="20"
                  fill="#FDE68A"
                  stroke="#CA8A04"
                  stroke-width="1.5"
                />
              </g>

              <!-- Central "Filum" node (white-cream, blue stroke) -->
              <circle cx="240" cy="210" r="58" fill="url(#nodeGlow)" opacity="0.6" />
              <circle cx="240" cy="210" r="40" fill="#F0F2F5" stroke="#6B8AFF" stroke-width="2" />
              <text
                x="240"
                y="216"
                text-anchor="middle"
                font-size="16"
                font-weight="700"
                fill="#1A1A1A"
                font-family="Inter, system-ui">Filum</text
              >

              <!-- Source labels (only "Filum" kept, others removed) -->
            </svg>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- HOW: 3 steps with reveal -->
  <section class="bg-surface-secondary py-20" id="comment-ca-marche">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <h2 class="font-serif text-3xl md:text-4xl text-ink-primary mb-12 text-center" use:reveal>
        Comment ça marche
      </h2>
      <div class="grid md:grid-cols-3 gap-6 lg:gap-8">
        {#each [{ n: '1', title: 'Sourcer', desc: 'Ajoutez vos sources : articles, études, documents. Chaque source est automatiquement archivée.' }, { n: '2', title: 'Attester', desc: 'Chaque création que vous revendiquez est attestée avec votre clé Ed25519 : le triplet (vous, l’URL du contenu, la date) est signé et vérifiable par tous.' }, { n: '3', title: 'Partager', desc: 'Partagez votre page publique. Graphe interactif, statistiques, export PDF. Vérifiable par tous.' }] as step, i (i)}
          <div class="step-card" use:reveal style="transition-delay: {i * 80}ms">
            <div class="step-number font-serif">{step.n}</div>
            <h3 class="text-xl text-ink-primary mb-2 font-medium">{step.title}</h3>
            <p class="text-sm text-ink-secondary leading-relaxed">{step.desc}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <!-- WHO: 4 audiences -->
  <section class="py-20 bg-surface-primary">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-12" use:reveal>
        <h2 class="font-serif text-3xl md:text-4xl text-ink-primary mb-4">Pour qui ?</h2>
        <p class="text-lg text-ink-secondary max-w-2xl mx-auto">
          Filum s'adresse à tou·te·s les créateur·ice·s qui veulent rendre visible la qualité de
          leurs références.
        </p>
      </div>
      <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
        {#each [{ title: 'Vulgarisateurs scientifiques', desc: 'Rendez visible la rigueur de votre travail. Montrez que vos affirmations sont sourcées.' }, { title: 'Journalistes', desc: 'Protégez vos sources dans le temps. Prouvez votre méthodologie face aux critiques.' }, { title: 'Chercheurs', desc: 'Partagez vos bibliographies sous forme navigable. Facilitez la vérification par vos pairs.' }, { title: 'Créateur·ice·s de contenu', desc: 'Chaque source mérite d’être citée, quel que soit votre format.' }] as audience, i (i)}
          <div class="audience-card" use:reveal style="transition-delay: {i * 60}ms">
            <h3 class="text-base font-medium text-ink-primary mb-2">{audience.title}</h3>
            <p class="text-sm text-ink-secondary leading-relaxed">{audience.desc}</p>
          </div>
        {/each}
      </div>
    </div>
  </section>

  <!-- CTA: nearly-black background with white text -->
  <section class="cta-section py-20">
    <div class="max-w-4xl mx-auto px-4 text-center" use:reveal>
      <h2 class="font-serif text-3xl md:text-4xl text-white mb-4">Prêt à commencer&nbsp;?</h2>
      <p class="text-lg text-slate-300 mb-8">
        Rejoignez les créateurs qui prennent le temps de bien sourcer leur travail.
      </p>
      {#if isAuthenticated}
        <a href="/dashboard" class="hero-cta-light">Accéder au tableau de bord</a>
      {:else}
        <a href={googleLoginUrl} class="hero-cta-light">
          <svg class="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fill="currentColor"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
            />
            <path
              fill="currentColor"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="currentColor"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              fill="currentColor"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continuer avec Google
        </a>
      {/if}
    </div>
  </section>
</div>

<style>
  /* === HERO: spatial dark background === */
  .hero {
    background:
      radial-gradient(ellipse at 50% 50%, rgba(120, 50, 180, 0.1) 0%, transparent 60%),
      radial-gradient(ellipse at 25% 30%, rgba(160, 70, 220, 0.07) 0%, transparent 45%),
      radial-gradient(ellipse at 75% 65%, rgba(40, 160, 190, 0.05) 0%, transparent 40%),
      linear-gradient(165deg, #050508 0%, #0a0a14 50%, #07070f 100%);
    min-height: 80vh;
    color: white;
  }

  .hero-stars {
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(1.5px 1.5px at 12% 18%, rgba(255, 255, 255, 0.6), transparent 50%),
      radial-gradient(1px 1px at 24% 62%, rgba(255, 255, 255, 0.4), transparent 50%),
      radial-gradient(1.5px 1.5px at 38% 12%, rgba(255, 255, 255, 0.5), transparent 50%),
      radial-gradient(1px 1px at 55% 38%, rgba(255, 255, 255, 0.35), transparent 50%),
      radial-gradient(1.5px 1.5px at 72% 18%, rgba(255, 255, 255, 0.55), transparent 50%),
      radial-gradient(1px 1px at 88% 48%, rgba(255, 255, 255, 0.4), transparent 50%),
      radial-gradient(1.5px 1.5px at 18% 82%, rgba(255, 255, 255, 0.45), transparent 50%),
      radial-gradient(1px 1px at 46% 78%, rgba(255, 255, 255, 0.35), transparent 50%),
      radial-gradient(1.5px 1.5px at 78% 88%, rgba(255, 255, 255, 0.5), transparent 50%),
      radial-gradient(1px 1px at 92% 22%, rgba(255, 255, 255, 0.4), transparent 50%);
    pointer-events: none;
  }

  .hero-accent {
    background: linear-gradient(135deg, #b5d4f4 0%, #cecbf6 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }

  /* === HERO buttons (sit on dark background, can't reuse light Button) === */
  .hero-cta-primary {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: white;
    color: #1a1a1a;
    padding: 0.625rem 1.25rem;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 500;
    transition: all 150ms ease;
    text-decoration: none;
  }
  .hero-cta-primary:hover {
    background: #f0f2f5;
    transform: translateY(-1px);
  }
  .hero-cta-secondary {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    background: transparent;
    color: rgba(255, 255, 255, 0.8);
    padding: 0.625rem 1.25rem;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    font-size: 0.95rem;
    font-weight: 500;
    transition: all 150ms ease;
    text-decoration: none;
  }
  .hero-cta-secondary:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.35);
    color: white;
  }

  /* === GALAXY === */
  .hero-galaxy-wrap {
    display: flex;
    justify-content: center;
    position: relative;
  }
  .hero-galaxy {
    width: 100%;
    max-width: 28rem;
  }
  /* 3D depth layers: star drift at different speeds */
  :global(.star-layer-far) {
    animation: star-drift-far 90s ease-in-out infinite alternate;
  }
  :global(.star-layer-mid) {
    animation: star-drift-mid 50s ease-in-out infinite alternate;
  }
  :global(.star-layer-near) {
    animation: star-drift-near 30s ease-in-out infinite alternate;
  }
  :global(.star-twinkle) {
    animation: star-twinkle 3s ease-in-out infinite;
  }
  :global(.star-twinkle:nth-child(2n)) {
    animation-duration: 4.2s;
    animation-delay: -1s;
  }
  :global(.star-twinkle:nth-child(3n)) {
    animation-duration: 3.6s;
    animation-delay: -2.5s;
  }
  :global(.star-twinkle:nth-child(5n)) {
    animation-duration: 5s;
    animation-delay: -0.5s;
  }

  @keyframes star-drift-far {
    from {
      transform: translate(0, 0);
    }
    to {
      transform: translate(1.5px, 1px);
    }
  }
  @keyframes star-drift-mid {
    from {
      transform: translate(0, 0);
    }
    to {
      transform: translate(2.5px, 2px);
    }
  }
  @keyframes star-drift-near {
    from {
      transform: translate(0, 0);
    }
    to {
      transform: translate(4px, 3px);
    }
  }
  @keyframes star-twinkle {
    0%,
    100% {
      opacity: 0.25;
    }
    50% {
      opacity: 0.85;
    }
  }

  /* === REVEAL animation (uses data-reveal attr added by action) === */
  :global([data-reveal]) {
    opacity: 0;
    transform: translateY(16px);
    transition:
      opacity 600ms cubic-bezier(0.2, 0.7, 0.3, 1),
      transform 600ms cubic-bezier(0.2, 0.7, 0.3, 1);
  }
  :global([data-reveal].is-revealed) {
    opacity: 1;
    transform: translateY(0);
  }

  /* === STEP / AUDIENCE cards === */
  .step-card {
    background: rgb(var(--bg-primary));
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    padding: 1.5rem;
    position: relative;
    transition:
      transform 180ms cubic-bezier(0.2, 0.7, 0.3, 1),
      border-color 180ms ease;
  }
  .step-card:hover {
    transform: translateY(-3px);
    border-color: rgb(var(--border-strong));
  }
  .step-number {
    font-size: 2.5rem;
    line-height: 1;
    color: rgb(var(--info));
    font-weight: 500;
    margin-bottom: 0.75rem;
    display: block;
  }
  .audience-card {
    background: rgb(var(--bg-primary));
    border: 1px solid rgb(var(--border));
    border-radius: 12px;
    padding: 1.25rem;
    transition:
      transform 180ms cubic-bezier(0.2, 0.7, 0.3, 1),
      border-color 180ms ease;
  }
  .audience-card:hover {
    transform: translateY(-3px);
    border-color: rgb(var(--border-strong));
  }

  /* === CTA section === */
  .cta-section {
    background: #1a2a4a;
    color: white;
  }
  :global(.dark) .cta-section {
    background: #0d1525;
  }
  .hero-cta-light {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: white;
    color: #1a1a1a;
    padding: 0.75rem 1.5rem;
    border-radius: 6px;
    font-size: 1rem;
    font-weight: 500;
    transition: all 150ms ease;
    text-decoration: none;
    border: 1px solid rgba(255, 255, 255, 0.4);
  }
  .hero-cta-light:hover {
    background: #f0f2f5;
    transform: translateY(-2px);
  }
  :global(.dark) .hero-cta-light {
    background: #1e1e2a;
    color: #f5f5f5;
    border-color: rgba(255, 255, 255, 0.15);
  }
  :global(.dark) .hero-cta-light:hover {
    background: #2a2a3a;
    border-color: rgba(255, 255, 255, 0.25);
  }

  @media (prefers-reduced-motion: reduce) {
    :global(.star-layer),
    :global(.star-twinkle) {
      animation: none !important;
    }
  }
</style>
