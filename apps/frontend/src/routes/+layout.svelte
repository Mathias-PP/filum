<script lang="ts">
  import '../app.css'
  import { auth } from '$lib/stores'
  import { page } from '$app/stores'

  interface Props {
    data: { user: unknown }
    children: any
  }

  let { data, children }: Props = $props()

  auth.setUser(data.user as any)

  const navItems = [
    { href: '/', label: 'Accueil' },
    { href: '/dashboard', label: 'Tableau de bord' },
    { href: '/about', label: 'À propos' }
  ]
</script>

<div class="min-h-screen flex flex-col">
  <header class="sticky top-0 z-50 bg-white border-b border-slate-200">
    <nav class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <a href="/" class="flex items-center gap-2">
          <svg class="w-8 h-8 text-blue-500" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 2L4 8v16l12 6 12-6V8L16 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M4 8l12 6 12-6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M16 14v14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="text-xl font-bold text-slate-900">Filum</span>
        </a>

        <div class="hidden md:flex items-center gap-6">
          {#each navItems as item}
            <a
              href={item.href}
              class="text-sm font-medium transition-colors {$page.url.pathname === item.href ? 'text-blue-600' : 'text-slate-600 hover:text-slate-900'}"
            >
              {item.label}
            </a>
          {/each}
        </div>

        <div class="flex items-center gap-3">
          {#if data.user}
            <a href="/dashboard" class="btn-primary text-sm">Tableau de bord</a>
          {:else}
            <a href="/api/v1/auth/login" class="btn-secondary text-sm">Se connecter</a>
            <a href="/api/v1/auth/login" class="btn-primary text-sm">Créer une fiche</a>
          {/if}
        </div>
      </div>
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
          <a href="https://github.com/Mathias-PP/filum" class="hover:text-slate-700 flex items-center gap-1">
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.461-1.334-5.461-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
            </svg>
            GitHub
          </a>
        </div>
      </div>
    </div>
  </footer>
</div>
