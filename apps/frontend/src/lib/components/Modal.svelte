<script lang="ts">
  import type { Snippet } from 'svelte';
  import { fade, scale } from 'svelte/transition';

  interface Props {
    open: boolean;
    title?: string;
    onClose?: () => void;
    size?: 'sm' | 'md' | 'lg';
    closeOnBackdrop?: boolean;
    children: Snippet;
    footer?: Snippet;
  }

  let {
    open = $bindable(false),
    title,
    onClose,
    size = 'md',
    closeOnBackdrop = true,
    children,
    footer,
  }: Props = $props();

  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-2xl',
  };

  function close() {
    open = false;
    onClose?.();
  }

  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && open) {
      e.preventDefault();
      close();
    }
  }

  function onBackdropClick() {
    if (closeOnBackdrop) close();
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
  <div
    class="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
    role="dialog"
    aria-modal="true"
    aria-labelledby={title ? 'modal-title' : undefined}
  >
    <button
      type="button"
      class="absolute inset-0 bg-ink-primary/40 backdrop-blur-sm"
      aria-label="Fermer"
      onclick={onBackdropClick}
      transition:fade={{ duration: 150 }}
    ></button>
    <div
      class="relative bg-surface-primary rounded-t-xl sm:rounded-lg border border-border w-full {sizeClasses[
        size
      ]} max-h-[calc(100dvh-2rem)] overflow-hidden flex flex-col"
      transition:scale={{ duration: 180, start: 0.96, opacity: 0 }}
    >
      {#if title}
        <header class="px-5 py-3 border-b border-border flex items-center justify-between">
          <h2 id="modal-title" class="text-base font-medium text-ink-primary">{title}</h2>
          <button
            type="button"
            onclick={close}
            class="p-1 text-ink-tertiary hover:text-ink-primary transition-colors rounded"
            aria-label="Fermer la fenêtre"
          >
            <svg
              viewBox="0 0 24 24"
              class="w-4 h-4"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
            >
              <line x1="6" y1="6" x2="18" y2="18" />
              <line x1="6" y1="18" x2="18" y2="6" />
            </svg>
          </button>
        </header>
      {/if}
      <div class="p-5 overflow-y-auto">
        {@render children()}
      </div>
      {#if footer}
        <footer
          class="px-5 py-3 border-t border-border bg-surface-secondary flex justify-end gap-2"
        >
          {@render footer()}
        </footer>
      {/if}
    </div>
  </div>
{/if}
