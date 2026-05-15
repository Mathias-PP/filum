<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    variant?: 'info' | 'success' | 'warning' | 'danger';
    title?: string;
    class?: string;
    children: Snippet;
  }

  let { variant = 'info', title, class: className = '', children }: Props = $props();

  const variantClasses = {
    info: 'bg-info-bg border-info/20 text-info',
    success: 'bg-success-bg border-success/20 text-success',
    warning: 'bg-warning-bg border-warning/20 text-warning',
    danger: 'bg-danger-bg border-danger/20 text-danger',
  };
</script>

<div class="rounded border px-4 py-3 text-sm {variantClasses[variant]} {className}" role="alert">
  {#if title}
    <p class="font-medium mb-0.5">{title}</p>
  {/if}
  <div class="text-ink-primary/90">
    {@render children()}
  </div>
</div>
