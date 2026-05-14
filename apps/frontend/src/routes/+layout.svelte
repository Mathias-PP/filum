<script lang="ts">
  import '../app.css';
  import { env } from '$env/dynamic/public';
  import { goto, invalidateAll } from '$app/navigation';
  import { api, type User } from '$lib/api';
  import { auth } from '$lib/stores';
  import { page } from '$app/stores';
  import { Logo, Button } from '$lib/components';

  const API_BASE = env.PUBLIC_API_BASE_URL ?? '';
  const googleLoginUrl = `${API_BASE}/api/v1/auth/google/login`;

  interface Props {
    data: { user: User | null };
    children: any;
  }

  let { data, children }: Props = $props();

  let showUserMenu = $state(false);
  let mobileNavOpen = $state(false);

  $effect(() => {
    auth.setUser(data.user);
  });

  function closeUserMenu() {
    showUserMenu = false;
  }

  function closeMobileNav() {
    mobileNavOpen = false;
  }

  function onGlobalKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      showUserMenu = false;
      mobileNavOpen = false;
    }
  }

  async function logout() {
    try {
      await api.auth.logout();
    } catch {
      // proceed even if server error
    }
    auth.reset();
    await invalidateAll();
    goto('/');
  }

  function userInitials(name: string): string {
    return name
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((n) => n[0])
      .join('')
      .toUpperCase();
  }

  const navItems = [
    { href: '/', label: 'Accueil' },
    { href: '/features', label: 'Fonctionnalités' },
    { href: '/roadmap', label: 'Roadmap' },
    { href: '/security', label: 'Sécurité' },
    { href: '/about', label: 'À propos' },
  ];
</script>

<svelte:window onclick={closeUserMenu} onkeydown={onGlobalKeydown} />

<div class="min-h-screen flex flex-col">
  <header class="sticky top-0 z-50 bg-white border-b border-slate-200">
    <nav class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16 gap-3">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="md:hidden p-2 -ml-2 text-slate-700 hover:text-slate-900 rounded-md hover:bg-slate-100 transition-colors"
            aria-label={mobileNavOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-nav"
            onclick={(e) => {
              e.stopPropagation();
              mobileNavOpen = !mobileNavOpen;
            }}
          >
            {#if mobileNavOpen}
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            {:else}
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            {/if}
          </button>
          <a href="/" class="flex items-center gap-2">
            <Logo size={32} className="text-blue-600" />
            <span class="text-xl font-bold text-slate-900">Filum</span>
          </a>
        </div>

        <div class="hidden md:flex items-center gap-6">
          {#each navItems as item}
            <a
              href={item.href}
              class="text-sm font-medium transition-colors {$page.url.pathname === item.href
                ? 'text-blue-600'
                : 'text-slate-600 hover:text-slate-900'}"
            >
              {item.label}
            </a>
          {/each}
        </div>

        <div class="flex items-center gap-3">
          {#if data.user}
            <!-- svelte-ignore a11y_click_events_have_key_events -->
            <!-- svelte-ignore a11y_no_static_element_interactions -->
            <div
              class="relative"
              onclick={(e) => {
                e.stopPropagation();
                showUserMenu = !showUserMenu;
              }}
            >
              {#if data.user.avatar_url}
                <img
                  src={data.user.avatar_url}
                  alt={data.user.display_name ?? data.user.username}
                  class="w-8 h-8 rounded-full cursor-pointer ring-2 ring-slate-200 hover:ring-blue-400 transition-all"
                />
              {:else}
                <div
                  class="w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-medium cursor-pointer ring-2 ring-slate-200 hover:ring-blue-400 transition-all"
                >
                  {userInitials(data.user.display_name ?? data.user.username)}
                </div>
              {/if}
              {#if showUserMenu}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div
                  class="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-50"
                  onclick={(e) => e.stopPropagation()}
                >
                  <div class="px-4 py-2 border-b border-slate-100">
                    <p class="text-sm font-medium text-slate-900 truncate">
                      {data.user.display_name ?? data.user.username}
                    </p>
                    <p class="text-xs text-slate-500 truncate">@{data.user.username}</p>
                  </div>
                  <a
                    href="/dashboard"
                    class="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
                  >
                    Tableau de bord
                  </a>
                  <button
                    type="button"
                    onclick={logout}
                    class="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                  >
                    Se déconnecter
                  </button>
                </div>
              {/if}
            </div>
          {:else}
            <Button href={googleLoginUrl} variant="secondary" size="sm">Se connecter</Button>
            <Button href={googleLoginUrl} variant="primary" size="sm">Créer une fiche</Button>
          {/if}
        </div>
      </div>

      {#if mobileNavOpen}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          id="mobile-nav"
          class="md:hidden border-t border-slate-200 py-2"
          onclick={(e) => e.stopPropagation()}
        >
          {#each navItems as item}
            <a
              href={item.href}
              onclick={closeMobileNav}
              class="block px-4 py-3 text-sm font-medium rounded-md {$page.url.pathname ===
              item.href
                ? 'text-blue-600 bg-blue-50'
                : 'text-slate-700 hover:bg-slate-50'}"
            >
              {item.label}
            </a>
          {/each}
        </div>
      {/if}
    </nav>
  </header>

  <main class="flex-1">
    {@render children()}
  </main>

  <footer class="bg-slate-50 border-t border-slate-200 mt-auto">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div class="flex flex-col md:flex-row items-center justify-between gap-4">
        <div class="flex items-center gap-2 text-sm text-slate-500">
          <span>© 2026 Filum</span>
          <span>·</span>
          <a href="/about" class="hover:text-slate-700">À propos</a>
          <span>·</span>
          <a href="/privacy" class="hover:text-slate-700">Confidentialité</a>
        </div>
        <div class="flex items-center gap-4 text-sm text-slate-500">
          <a
            href="https://github.com/Mathias-PP/filum"
            class="hover:text-slate-700 flex items-center gap-1"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path
                d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.461-1.334-5.461-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
              />
            </svg>
            GitHub
          </a>
        </div>
      </div>
    </div>
  </footer>
</div>
