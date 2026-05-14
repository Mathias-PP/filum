<script lang="ts">
  interface Props {
    variant?: 'text' | 'card' | 'circle' | 'graph';
    width?: string;
    height?: string;
    class?: string;
    count?: number;
  }

  let { variant = 'text', width, height, class: className = '', count = 1 }: Props = $props();

  const variantClasses = {
    text: 'h-4 rounded',
    card: 'rounded-lg',
    circle: 'rounded-full aspect-square',
    graph: 'rounded-lg w-full',
  };

  const defaultHeights = {
    text: undefined,
    card: '8rem',
    circle: '2.5rem',
    graph: '75vh',
  };

  const items = $derived(Array.from({ length: count }));
</script>

{#each items as _, i (i)}
  <div
    class="skeleton-shimmer {variantClasses[variant]} {className}"
    style:width
    style:height={height ?? defaultHeights[variant]}
    aria-busy="true"
    aria-live="polite"
  ></div>
{/each}
