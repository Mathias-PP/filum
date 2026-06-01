<script lang="ts">
  import '../app.css';
  import { goto, invalidateAll } from '$app/navigation';
  import { fly } from 'svelte/transition';
  import { api, type User } from '$lib/api';
  import { auth } from '$lib/stores';
  import { page } from '$app/stores';
  import { Logo, Button, Toast, ThemeToggle } from '$lib/components';

  // Relative — routed through the SvelteKit /api proxy for first-party cookies.
  const API_BASE = '';
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

<a href="#main-content" class="skip-link">Aller au contenu principal</a>

<div class="min-h-screen flex flex-col">
  <header class="sticky top-0 z-40 bg-surface-primary/85 backdrop-blur-md border-b border-border">
    <nav class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-14 gap-3">
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="md:hidden p-2 -ml-2 text-ink-secondary hover:text-ink-primary rounded hover:bg-surface-tertiary transition-colors"
            aria-label={mobileNavOpen ? 'Fermer le menu' : 'Ouvrir le menu'}
            aria-expanded={mobileNavOpen}
            aria-controls="mobile-nav"
            onclick={(e) => {
              e.stopPropagation();
              mobileNavOpen = !mobileNavOpen;
            }}
          >
            <div class="hamburger" class:open={mobileNavOpen} aria-hidden="true">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </button>
          <a href="/" class="flex items-center gap-2">
            <Logo size={28} className="text-info" />
            <span class="text-base font-serif font-medium text-ink-primary">Philum</span>
          </a>
        </div>

        <div class="hidden md:flex items-center gap-1">
          {#each navItems as item}
            <a
              href={item.href}
              class="nav-link {$page.url.pathname === item.href ? 'is-active' : ''}"
            >
              {item.label}
            </a>
          {/each}
        </div>

        <div class="flex items-center gap-2">
          <ThemeToggle />
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
                  class="w-8 h-8 rounded-full cursor-pointer ring-1 ring-border hover:ring-info transition-all"
                />
              {:else}
                <div
                  class="w-8 h-8 rounded-full bg-info/10 text-info flex items-center justify-center text-xs font-medium cursor-pointer ring-1 ring-border hover:ring-info transition-all"
                >
                  {userInitials(data.user.display_name ?? data.user.username)}
                </div>
              {/if}
              {#if showUserMenu}
                <!-- svelte-ignore a11y_click_events_have_key_events -->
                <!-- svelte-ignore a11y_no_static_element_interactions -->
                <div
                  class="absolute right-0 mt-2 w-52 bg-surface-primary rounded-lg shadow-md border border-border py-1 z-50"
                  onclick={(e) => e.stopPropagation()}
                  transition:fly={{ y: -4, duration: 120 }}
                >
                  <div class="px-3 py-2 border-b border-border">
                    <p class="text-sm font-medium text-ink-primary truncate">
                      {data.user.display_name ?? data.user.username}
                    </p>
                    <p class="text-xs text-ink-tertiary truncate">@{data.user.username}</p>
                  </div>
                  <a
                    href="/dashboard"
                    class="block px-3 py-2 text-sm text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary transition-colors"
                  >
                    Tableau de bord
                  </a>
                  <a
                    href="/@{data.user.username}"
                    class="block px-3 py-2 text-sm text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary transition-colors"
                  >
                    Mon profil public
                  </a>
                  <button
                    type="button"
                    onclick={logout}
                    class="w-full text-left px-3 py-2 text-sm text-danger hover:bg-danger-bg transition-colors"
                  >
                    Se déconnecter
                  </button>
                </div>
              {/if}
            </div>
          {:else}
            <Button href={googleLoginUrl} variant="secondary" size="sm">Se connecter</Button>
            <!-- Hidden on phones (< 480px) to keep both buttons on one line.
                 Same destination (Google login) so no feature regression. -->
            <span class="hidden xs:inline-flex">
              <Button href={googleLoginUrl} variant="primary" size="sm">Créer une fiche</Button>
            </span>
          {/if}
        </div>
      </div>

      {#if mobileNavOpen}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          id="mobile-nav"
          class="md:hidden border-t border-border py-2"
          onclick={(e) => e.stopPropagation()}
          transition:fly={{ y: -8, duration: 180 }}
        >
          {#each navItems as item}
            <a
              href={item.href}
              onclick={closeMobileNav}
              class="block px-4 py-2.5 text-sm font-medium rounded {$page.url.pathname === item.href
                ? 'text-info bg-info-bg'
                : 'text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary'}"
            >
              {item.label}
            </a>
          {/each}
        </div>
      {/if}
    </nav>
  </header>

  <main id="main-content" class="flex-1">
    {#key $page.url.pathname}
      <div in:fly|global={{ y: 8, duration: 180 }}>
        {@render children()}
      </div>
    {/key}
  </main>

  <footer class="bg-surface-secondary border-t border-border mt-auto">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div class="flex flex-col md:flex-row items-center justify-between gap-3 text-sm">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-tertiary">
          <span>© 2026 Philum</span>
          <span aria-hidden="true">·</span>
          <a href="/about" class="hover:text-ink-primary transition-colors">À propos</a>
          <span aria-hidden="true">·</span>
          <a href="/privacy" class="hover:text-ink-primary transition-colors">Confidentialité</a>
          <span aria-hidden="true">·</span>
          <a href="/security" class="hover:text-ink-primary transition-colors">Sécurité</a>
        </div>
        <a
          href="https://github.com/Mathias-PP/filum"
          target="_blank"
          rel="noopener noreferrer"
          class="text-ink-tertiary hover:text-ink-primary transition-colors flex items-center gap-1.5"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.461-1.334-5.461-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
            />
          </svg>
          GitHub
        </a>
      </div>
    </div>
  </footer>

  <Toast />
</div>

<style>
  :global(.skip-link) {
    position: fixed;
    left: 1rem;
    top: -3rem;
    z-index: 100;
    background: rgb(var(--text-primary));
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.875rem;
    transition: top 150ms ease;
  }
  :global(.skip-link:focus) {
    top: 0.5rem;
    outline: 2px solid rgb(var(--info));
    outline-offset: 2px;
  }

  .nav-link {
    padding: 0.375rem 0.75rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: rgb(var(--text-secondary));
    border-radius: 6px;
    transition: all 150ms ease;
    text-decoration: none;
  }
  .nav-link:hover {
    color: rgb(var(--text-primary));
    background: rgb(var(--bg-tertiary));
  }
  .nav-link.is-active {
    color: rgb(var(--text-primary));
  }
  .nav-link.is-active::after {
    content: '';
    display: block;
    height: 2px;
    background: rgb(var(--info));
    margin-top: 0.25rem;
    border-radius: 1px;
  }

  /* Animated hamburger -> X */
  .hamburger {
    width: 20px;
    height: 14px;
    position: relative;
    display: inline-block;
  }
  .hamburger span {
    position: absolute;
    left: 0;
    width: 100%;
    height: 2px;
    background: currentColor;
    border-radius: 1px;
    transition:
      transform 220ms cubic-bezier(0.4, 0, 0.2, 1),
      opacity 180ms ease,
      top 220ms cubic-bezier(0.4, 0, 0.2, 1);
  }
  .hamburger span:nth-child(1) {
    top: 0;
  }
  .hamburger span:nth-child(2) {
    top: 6px;
  }
  .hamburger span:nth-child(3) {
    top: 12px;
  }
  .hamburger.open span:nth-child(1) {
    top: 6px;
    transform: rotate(45deg);
  }
  .hamburger.open span:nth-child(2) {
    opacity: 0;
  }
  .hamburger.open span:nth-child(3) {
    top: 6px;
    transform: rotate(-45deg);
  }
</style>
