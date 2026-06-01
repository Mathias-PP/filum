<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { auth } from '$lib/stores/auth';

  let statusMessage = "Finalisation de l'authentification…";

  onMount(async () => {
    const currentUrl = new URL(window.location.href);
    const error = currentUrl.searchParams.get('error');

    if (error) {
      statusMessage = 'Authentification refusée. Redirection…';
      setTimeout(() => goto('/'), 2000);
      return;
    }

    // The backend already set the session cookie and redirected here
    // — check /auth/me to hydrate the store and redirect to dashboard
    try {
      const user = await api.auth.me();
      if (user) {
        auth.setUser(user);
        goto('/dashboard');
      } else {
        statusMessage = "Échec de l'authentification. Redirection…";
        setTimeout(() => goto('/'), 2000);
      }
    } catch {
      statusMessage = 'Erreur de connexion. Redirection…';
      setTimeout(() => goto('/'), 2000);
    }
  });
</script>

<svelte:head>
  <title>Authentification — Philum</title>
</svelte:head>

<div class="flex items-center justify-center min-h-[60vh]">
  <div class="text-center">
    <div
      class="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"
    ></div>
    <p class="text-ink-secondary">{statusMessage}</p>
  </div>
</div>
