<script lang="ts">
  import { page } from '$app/stores';
  import { Button } from '$lib/components';
  import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

  const sessionId = $derived($page.params.id);
</script>

<svelte:head>
  <title>Agent · Philum</title>
</svelte:head>

<div class="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="mb-4 flex items-center justify-between gap-2">
    <h1 class="font-serif text-3xl text-ink-primary">Agent</h1>
    <div class="flex gap-1">
      <Button size="sm" variant="ghost" href="/dashboard/chat">Nouvelle</Button>
      <Button size="sm" variant="ghost" href="/dashboard/agents">Providers</Button>
    </div>
  </div>
  <div class="min-h-[60vh]">
    {#key sessionId}
      <ChatPanel {sessionId} />
    {/key}
  </div>
</div>
