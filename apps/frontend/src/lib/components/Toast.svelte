<script lang="ts" module>
  import { writable, get } from 'svelte/store';

  export type ToastVariant = 'info' | 'success' | 'warning' | 'danger';

  export interface ToastItem {
    id: string;
    variant: ToastVariant;
    message: string;
    title?: string;
    timeout: number;
  }

  const store = writable<ToastItem[]>([]);

  function push(
    message: string,
    options: { variant?: ToastVariant; title?: string; timeout?: number } = {}
  ): string {
    const id = crypto.randomUUID();
    const item: ToastItem = {
      id,
      variant: options.variant ?? 'info',
      message,
      title: options.title,
      timeout: options.timeout ?? 5000,
    };
    store.update((items) => [...items, item]);
    if (item.timeout > 0) {
      setTimeout(() => dismiss(id), item.timeout);
    }
    return id;
  }

  function dismiss(id: string) {
    store.update((items) => items.filter((t) => t.id !== id));
  }

  export const toast = {
    info: (msg: string, opts?: Omit<Parameters<typeof push>[1], 'variant'>) =>
      push(msg, { ...opts, variant: 'info' }),
    success: (msg: string, opts?: Omit<Parameters<typeof push>[1], 'variant'>) =>
      push(msg, { ...opts, variant: 'success' }),
    warning: (msg: string, opts?: Omit<Parameters<typeof push>[1], 'variant'>) =>
      push(msg, { ...opts, variant: 'warning' }),
    danger: (msg: string, opts?: Omit<Parameters<typeof push>[1], 'variant'>) =>
      push(msg, { ...opts, variant: 'danger' }),
    dismiss,
    get items() {
      return get(store);
    },
    subscribe: store.subscribe,
  };
</script>

<script lang="ts">
  import { fly } from 'svelte/transition';

  // La teinte de variante ne peut plus passer par `bg-*` ni par `border-l-4` :
  // `.glass` pose le fond et `.glass-panel` un contour d'un pixel sur les
  // quatre côtés, tous deux hors couche Tailwind, donc prioritaires. L'accent
  // devient une barre posée dans la plaque, et la teinte un voile par-dessus.
  const accentClasses: Record<ToastVariant, string> = {
    info: 'bg-info',
    success: 'bg-success',
    warning: 'bg-warning',
    danger: 'bg-danger',
  };

  const titleClasses: Record<ToastVariant, string> = {
    info: 'text-info',
    success: 'text-success',
    warning: 'text-warning',
    danger: 'text-danger',
  };
</script>

<div
  class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none"
  aria-live="polite"
  aria-atomic="false"
>
  {#each $store as item (item.id)}
    <div
      class="glass glass-panel pointer-events-auto relative rounded-lg overflow-hidden flex items-start gap-3 p-3 pl-4"
      role="alert"
      transition:fly={{ x: 320, duration: 200 }}
    >
      <span class="absolute inset-y-0 left-0 w-1 {accentClasses[item.variant]}" aria-hidden="true"
      ></span>
      <div class="flex-1 min-w-0">
        {#if item.title}
          <p class="text-sm font-medium {titleClasses[item.variant]}">{item.title}</p>
        {/if}
        <p class="text-sm text-ink-primary/90">{item.message}</p>
      </div>
      <button
        type="button"
        class="p-1 text-ink-tertiary hover:text-ink-primary transition-colors"
        onclick={() => toast.dismiss(item.id)}
        aria-label="Fermer la notification"
      >
        <svg
          viewBox="0 0 24 24"
          class="w-3.5 h-3.5"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
        >
          <line x1="6" y1="6" x2="18" y2="18" />
          <line x1="6" y1="18" x2="18" y2="6" />
        </svg>
      </button>
    </div>
  {/each}
</div>
