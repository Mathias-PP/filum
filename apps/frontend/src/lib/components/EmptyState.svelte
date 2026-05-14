<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    icon?: Snippet;
    action?: Snippet;
    class?: string;
  }

  let { title, description, icon, action, class: className = '' }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center text-center py-12 px-6 {className}">
  {#if icon}
    <div class="mb-4 text-ink-tertiary">
      {@render icon()}
    </div>
  {/if}
  <h3 class="text-lg font-medium text-ink-primary mb-1">{title}</h3>
  {#if description}
    <p class="text-sm text-ink-secondary max-w-md mb-6">{description}</p>
  {/if}
  {#if action}
    {@render action()}
  {/if}
</div>
