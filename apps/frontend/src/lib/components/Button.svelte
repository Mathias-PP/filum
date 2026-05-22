<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    variant?: 'primary' | 'secondary' | 'tertiary' | 'ghost' | 'danger';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    type?: 'button' | 'submit' | 'reset';
    href?: string;
    target?: '_blank' | '_self' | '_parent' | '_top';
    rel?: string;
    class?: string;
    onclick?: (e: MouseEvent) => void;
    children: Snippet;
  }

  let {
    variant = 'primary',
    size = 'md',
    disabled = false,
    loading = false,
    type = 'button',
    href,
    target,
    rel,
    class: className = '',
    onclick,
    children,
  }: Props = $props();

  const computedRel = $derived(rel ?? (target === '_blank' ? 'noopener noreferrer' : undefined));

  const variantClasses = {
    primary: 'bg-black text-white dark:bg-white dark:text-black hover:opacity-90 active:opacity-80',
    secondary:
      'bg-transparent text-ink-primary border border-border-strong hover:bg-surface-tertiary',
    tertiary: 'bg-transparent text-info hover:underline px-0',
    ghost: 'bg-transparent text-ink-secondary hover:bg-surface-tertiary hover:text-ink-primary',
    danger: 'bg-danger text-white hover:opacity-90 active:opacity-80',
  };

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm h-8',
    md: 'px-4 py-2 text-sm h-9',
    lg: 'px-5 py-2.5 text-base h-11',
  };

  // `whitespace-nowrap` keeps button labels on a single line. Wrapped labels
  // overflow the fixed `h-{8|9|11}` heights and look broken (caught on mobile
  // header buttons "Se connecter" / "Créer une fiche").
  const classes = $derived(
    `${variantClasses[variant]} ${variant === 'tertiary' ? 'text-sm py-1' : sizeClasses[size]} ${className} inline-flex items-center justify-center gap-1.5 rounded font-medium whitespace-nowrap transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none`
  );
</script>

{#if href && !disabled}
  <a {href} {target} rel={computedRel} class={classes}>
    {@render children()}
  </a>
{:else}
  <button {type} class={classes} disabled={disabled || loading} {onclick}>
    {#if loading}
      <svg
        class="animate-spin -ml-0.5 h-4 w-4"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    {/if}
    {@render children()}
  </button>
{/if}
