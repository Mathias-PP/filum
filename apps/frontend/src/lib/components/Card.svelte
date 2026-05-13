<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title?: string;
    class?: string;
    children: Snippet;
  }

  let { title, class: className = '', children }: Props = $props();
</script>

<div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden {className}">
  {#if title}
    <div class="px-6 py-4 border-b border-slate-200">
      <h3 class="text-lg font-semibold text-slate-900">{title}</h3>
    </div>
  {/if}
  <div class="p-6">
    {@render children()}
  </div>
</div>
