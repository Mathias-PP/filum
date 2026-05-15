<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    class?: string;
    padding?: 'sm' | 'md' | 'lg' | 'none';
    children: Snippet;
  }

  let { title, class: className = '', padding = 'md', children }: Props = $props();

  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6',
  };
</script>

<div class="bg-surface-primary rounded-lg border border-border overflow-hidden {className}">
  {#if title}
    <div class="px-5 py-3 border-b border-border">
      <h3 class="text-base font-medium text-ink-primary">{title}</h3>
    </div>
    <div class={paddingClasses[padding]}>
      {@render children()}
    </div>
  {:else}
    <div class={paddingClasses[padding]}>
      {@render children()}
    </div>
  {/if}
</div>
