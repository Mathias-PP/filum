<script lang="ts">
  import { api } from '$lib/api/client';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';

  interface Props {
    cardId: string;
    creatorName: string;
  }

  let { cardId, creatorName }: Props = $props();

  let open = $state(false);
  let email = $state('');
  let channelUrl = $state('');
  let message = $state('');
  let submitStatus = $state<'idle' | 'loading' | 'done' | 'error'>('idle');

  async function submit(e: SubmitEvent) {
    e.preventDefault();
    if (submitStatus === 'loading') return;
    submitStatus = 'loading';
    try {
      await api.claims.create(cardId, {
        email,
        channel_url: channelUrl,
        message: message || undefined,
      });
      submitStatus = 'done';
    } catch {
      submitStatus = 'error';
    }
  }
</script>

<div
  class="mb-6 flex flex-col sm:flex-row sm:items-center gap-3 rounded border border-border-strong bg-surface-secondary px-4 py-3 text-sm"
>
  <p class="flex-1 text-ink-secondary">
    Fiche d'exemple établie par Philum à partir de sources publiques — non validée par
    {creatorName}. Vous êtes {creatorName}&nbsp;?
  </p>
  <Button size="sm" variant="secondary" onclick={() => (open = true)}>Réclamer cette fiche</Button>
</div>

<Modal bind:open title="Réclamer cette fiche">
  {#if submitStatus === 'done'}
    <p class="text-sm text-ink-secondary">
      Demande envoyée — nous vous recontactons sous 48&nbsp;h. Merci&nbsp;!
    </p>
  {:else}
    <form onsubmit={submit} class="flex flex-col gap-3">
      <input
        type="email"
        bind:value={email}
        required
        placeholder="votre@email.fr"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-1"
        aria-label="Email"
      />
      <input
        type="url"
        bind:value={channelUrl}
        required
        placeholder="Lien de votre chaîne / site"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-1"
        aria-label="Lien de votre chaîne"
      />
      <textarea
        bind:value={message}
        rows="3"
        placeholder="Message (optionnel)"
        class="rounded border border-border-strong bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-1"
      ></textarea>
      <Button type="submit" loading={submitStatus === 'loading'}>Envoyer la demande</Button>
      {#if submitStatus === 'error'}
        <p class="text-sm text-danger">Erreur — réessayez.</p>
      {/if}
    </form>
  {/if}
</Modal>
