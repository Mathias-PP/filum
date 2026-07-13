<script lang="ts">
  import { api } from '$lib/api/client';
  import Button from './Button.svelte';

  interface Props {
    context?: string;
  }

  let { context = 'home' }: Props = $props();

  let email = $state('');
  let submitStatus = $state<'idle' | 'loading' | 'done' | 'error'>('idle');

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (!email || submitStatus === 'loading') return;
    submitStatus = 'loading';
    try {
      await api.waitlist.join(email, context);
      submitStatus = 'done';
    } catch {
      submitStatus = 'error';
    }
  }
</script>

{#if submitStatus === 'done'}
  <p class="text-sm text-slate-300">Merci ! Nous vous contacterons à l'ouverture.</p>
{:else}
  <form onsubmit={submit} class="flex flex-col sm:flex-row gap-2 max-w-md mx-auto">
    <input
      type="email"
      bind:value={email}
      required
      placeholder="votre@email.fr"
      class="flex-1 rounded border border-white/20 bg-white/10 px-3 py-2 text-sm text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-white/40"
      aria-label="Adresse email"
    />
    <Button type="submit" loading={submitStatus === 'loading'} variant="secondary">
      Être notifié·e
    </Button>
  </form>
  {#if submitStatus === 'error'}
    <p class="mt-1 text-sm text-red-400">Une erreur est survenue, réessayez.</p>
  {/if}
{/if}
