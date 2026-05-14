<script lang="ts">
  import { env } from '$env/dynamic/public';
  import { Button } from '$lib/components';
  import type { User } from '$lib/api';

  const googleLoginUrl = `${env.PUBLIC_API_BASE_URL ?? ''}/api/v1/auth/google/login`;

  interface PageData {
    user: User | null;
  }

  let { data }: { data: PageData } = $props();
  const isAuthenticated = $derived(!!data.user);
</script>

<svelte:head>
  <title>Filum - Votre gestionnaire de références bibliographiques</title>
  <meta
    name="description"
    content="Vous allez adorer partager vos références. Constituez votre bibliographie, archivez chaque source et partagez-la avec le monde."
  />
</svelte:head>

<div class="relative">
  <section class="relative overflow-hidden hero-bg">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 lg:py-24">
      <div class="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
        <div class="text-center lg:text-left">
          <h1 class="text-4xl md:text-5xl lg:text-6xl font-bold text-slate-900 tracking-tight mb-6">
            Vous allez adorer partager <span class="text-blue-600">vos références</span>
          </h1>
          <p class="text-xl text-slate-600 mb-8 text-balance">
            Filum transforme votre bibliographie en un graphe interactif : sources organisées,
            archivées, et chaque contenu original que vous revendiquez est attesté
            cryptographiquement.
          </p>
          <div class="flex flex-col sm:flex-row items-center lg:items-start justify-center lg:justify-start gap-4">
            {#if isAuthenticated}
              <Button href="/dashboard" variant="primary" size="lg">
                Accéder au tableau de bord
              </Button>
            {:else}
              <Button href={googleLoginUrl} variant="primary" size="lg">
                <span class="flex items-center gap-2">
                  <svg class="w-5 h-5" viewBox="0 0 24 24">
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
                </span>
              </Button>
            {/if}
            <Button href="/@example/memoire-et-cerveau" variant="secondary" size="lg">
              Voir un exemple
            </Button>
          </div>
        </div>

        <div class="relative flex justify-center lg:justify-end">
          <svg
            viewBox="0 0 480 420"
            class="w-full max-w-md drop-shadow-sm"
            role="img"
            aria-label="Illustration : graphe de citation Filum"
          >
            <defs>
              <radialGradient id="halo" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.35" />
                <stop offset="70%" stop-color="#3b82f6" stop-opacity="0" />
              </radialGradient>
              <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="2" />
              </filter>
            </defs>

            <circle cx="240" cy="210" r="140" fill="url(#halo)" />

            <g stroke="#cbd5e1" stroke-width="1.5" fill="none" stroke-linecap="round">
              <path d="M 240 210 C 180 150, 130 120, 90 95" />
              <path d="M 240 210 C 300 150, 350 130, 400 110" />
              <path d="M 240 210 C 180 260, 130 290, 95 335" />
              <path d="M 240 210 C 310 260, 360 300, 405 330" />
              <path d="M 240 210 C 220 130, 215 90, 220 55" />
              <path d="M 240 210 C 260 290, 270 340, 265 380" />
              <path d="M 90 95 C 110 70, 160 60, 220 55" />
              <path d="M 400 110 C 360 80, 290 60, 220 55" />
            </g>

            <g>
              <circle cx="240" cy="210" r="34" fill="#3b82f6" stroke="#1d4ed8" stroke-width="2.5">
                <animate
                  attributeName="r"
                  values="34;36;34"
                  dur="2.5s"
                  repeatCount="indefinite"
                />
              </circle>
              <text
                x="240"
                y="216"
                text-anchor="middle"
                font-size="14"
                font-weight="700"
                fill="white"
                font-family="ui-sans-serif, system-ui"
              >Filum</text>

              <circle cx="90" cy="95" r="22" fill="#C0DD97" stroke="#639922" stroke-width="2" />
              <circle cx="400" cy="110" r="22" fill="#B5D4F4" stroke="#378ADD" stroke-width="2" />
              <circle cx="95" cy="335" r="22" fill="#FAC775" stroke="#EF9F27" stroke-width="2" />
              <circle cx="405" cy="330" r="22" fill="#F2A7BE" stroke="#D4456E" stroke-width="2" />
              <circle cx="220" cy="55" r="20" fill="#A7E8D9" stroke="#2DAF8F" stroke-width="2" />
              <circle cx="265" cy="380" r="20" fill="#CECBF6" stroke="#7F77DD" stroke-width="2" />
            </g>

            <g font-family="ui-sans-serif, system-ui" font-size="11" fill="#475569">
              <text x="90" y="135" text-anchor="middle">Article</text>
              <text x="400" y="150" text-anchor="middle">Institution</text>
              <text x="95" y="375" text-anchor="middle">Presse</text>
              <text x="405" y="370" text-anchor="middle">Vidéo</text>
              <text x="220" y="25" text-anchor="middle">Image</text>
              <text x="265" y="412" text-anchor="middle">Original</text>
            </g>
          </svg>
        </div>
      </div>
    </div>
  </section>

  <section class="bg-slate-50 py-20">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <h2 class="text-3xl font-bold text-center text-slate-900 mb-12">Comment ça marche</h2>
      <div class="grid md:grid-cols-3 gap-8">
        <div class="text-center">
          <div
            class="w-16 h-16 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto mb-4"
          >
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">1. Sourcer</h3>
          <p class="text-slate-600">
            Ajoutez vos sources : articles, études, documents. Chaque source est automatiquement
            archivée.
          </p>
        </div>
        <div class="text-center">
          <div
            class="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-4"
          >
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
              />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">2. Attester</h3>
          <p class="text-slate-600">
            Chaque contenu original que vous revendiquez est attesté avec votre clé Ed25519 : le
            triplet (vous, l'URL du contenu, la date) est signé et vérifiable par tous.
          </p>
        </div>
        <div class="text-center">
          <div
            class="w-16 h-16 rounded-full bg-purple-100 text-purple-600 flex items-center justify-center mx-auto mb-4"
          >
            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
              />
            </svg>
          </div>
          <h3 class="text-xl font-semibold text-slate-900 mb-2">3. Partager</h3>
          <p class="text-slate-600">
            Partagez votre page publique. Graphe interactif, statistiques, export PDF. Vérifiable
            par tous.
          </p>
        </div>
      </div>
    </div>
  </section>

  <section class="py-20">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="text-center mb-12">
        <h2 class="text-3xl font-bold text-slate-900 mb-4">Pour qui ?</h2>
        <p class="text-xl text-slate-600 max-w-2xl mx-auto">
          Filum s'adresse à tou·te·s les créateur·ice·s qui veulent rendre visible la qualité de
          leurs références.
        </p>
      </div>
      <div class="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Vulgarisateurs scientifiques</h3>
          <p class="text-slate-600">
            Rendez visible la rigueur de votre travail de recherche. Montrez que vos affirmations
            sont sourcées.
          </p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Journalistes</h3>
          <p class="text-slate-600">
            Protégez vos sources dans le temps. Prouvez votre méthodologie face aux critiques.
          </p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Chercheurs</h3>
          <p class="text-slate-600">
            Partagez vos bibliographies sous forme navigable. Facilitez la vérification par vos
            pairs.
          </p>
        </div>
        <div class="card">
          <h3 class="text-lg font-semibold text-slate-900 mb-2">Créateur·ice·s de contenu</h3>
          <p class="text-slate-600">
            Chaque source mérite d'être citée, quel que soit votre format.
          </p>
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
      {#if isAuthenticated}
        <Button
          href="/dashboard"
          variant="secondary"
          size="lg"
          class="bg-white text-blue-600 hover:bg-blue-50"
        >
          Accéder au tableau de bord
        </Button>
      {:else}
        <Button
          href={googleLoginUrl}
          variant="secondary"
          size="lg"
          class="bg-white text-blue-600 hover:bg-blue-50"
        >
          <span class="flex items-center gap-2">
            <svg class="w-5 h-5" viewBox="0 0 24 24">
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
          </span>
        </Button>
      {/if}
    </div>
  </section>
</div>

<style>
  .hero-bg {
    background-image:
      radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.06) 0%, transparent 50%),
      radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 50%);
  }
</style>
