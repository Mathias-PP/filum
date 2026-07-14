<script lang="ts">
  import { Button, HeroPulsar, WaitlistForm } from '$lib/components';
  import { reveal } from '$lib/actions/reveal';
  import type { User } from '$lib/api';

  // Always relative — goes through the SvelteKit /api proxy so the OAuth
  // state + session cookies are first-party (see src/routes/api/[...path]/+server.ts).
  const googleLoginUrl = '/api/v1/auth/google/login';

  interface PageData {
    user: User | null;
  }

  let { data }: { data: PageData } = $props();
  const isAuthenticated = $derived(!!data.user);
</script>

<svelte:head>
  <title>Philum — Votre bibliographie devient une galaxie</title>
  <meta
    name="description"
    content="Philum transforme votre bibliographie en un graphe interactif : sources organisées, archivées, et chaque création que vous revendiquez est attestée cryptographiquement."
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

        <!-- Hero visual: WebGL pulsar with SVG fallback inline in the component. -->
        <div class="hero-galaxy-wrap">
          <HeroPulsar />
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
          Philum s'adresse à tou·te·s les créateur·ice·s qui veulent rendre visible la qualité de
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
        Connectez vos sources entre elles : votre bibliographie devient visible, archivable,
        navigable et vérifiable par tous.
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
        <div class="mt-10 border-t border-white/10 pt-10">
          <p class="text-sm text-slate-400 mb-4">
            Créateur·ice ? On crée votre fiche — recevez une notification à l'ouverture.
          </p>
          <WaitlistForm context="home-cta" />
        </div>
      {/if}
    </div>
  </section>
</div>

<style>
  /* === HERO: spatial dark background ===
     Colors tuned to match the WebGL canvas's inner palette so the alpha-faded
     edge of the graph dissolves invisibly into the section background.
     - Shader base void: vec3(0.004, 0.005, 0.010) ≈ #010103
     - Shader lit web:  vec3(0.028, 0.040, 0.095) ≈ #07091A
     - Shader edge bg:  vec3(0.011, 0.011, 0.025) ≈ #03030D
     The linear gradient stops are picked from this range; the soft radial
     overlays add only subtle hue (kept very low alpha). */
  .hero {
    background:
      radial-gradient(ellipse at 50% 50%, rgba(70, 90, 180, 0.08) 0%, transparent 60%),
      radial-gradient(ellipse at 25% 30%, rgba(90, 80, 200, 0.05) 0%, transparent 45%),
      radial-gradient(ellipse at 75% 65%, rgba(40, 80, 160, 0.04) 0%, transparent 40%),
      linear-gradient(165deg, #02020a 0%, #07091a 50%, #03030d 100%);
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

  /* === HERO VISUAL ===
     The pulsar canvas is intentionally MUCH LARGER than its column. We use a
     square aspect-ratio (1:1), no max-width, and aggressive negative margins
     so the canvas spills well beyond the column on lg+ screens. The shader's
     alpha-fade (45% opaque core, 55% gradient skirt) dissolves the edges into
     the hero background — wider and softer dissolve than before. */
  .hero-galaxy-wrap {
    position: relative;
    width: 100%;
    aspect-ratio: 1 / 1;
    margin-top: -3rem;
    margin-bottom: -3rem;
  }
  @media (min-width: 1024px) {
    .hero-galaxy-wrap {
      /* Spread further: bigger spill into the gap and toward both edges. */
      width: calc(100% + 12rem);
      margin-left: -6rem;
      margin-right: -6rem;
      margin-top: -7rem;
      margin-bottom: -7rem;
    }
  }

  /* Reveal animation styles are global in app.css ([data-reveal]). */

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

  /* Reduced motion handled inside HeroPulsar.svelte (skips WebGL init). */
</style>
