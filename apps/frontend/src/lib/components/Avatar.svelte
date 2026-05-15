<script lang="ts">
  interface Props {
    avatarUrl?: string | null;
    name: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    verified?: boolean;
    interactive?: boolean;
  }

  let { avatarUrl, name, size = 'md', verified = false, interactive = false }: Props = $props();

  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-10 h-10 text-sm',
    lg: 'w-14 h-14 text-lg',
    xl: 'w-20 h-20 text-2xl',
  };

  const palettes = [
    'bg-info text-white',
    'bg-success text-white',
    'bg-warning text-white',
    'bg-orig-stroke text-white',
    'bg-press-stroke text-white',
    'bg-peer-stroke text-white',
  ];

  const initials = $derived(
    name
      .split(' ')
      .map((w) => w[0])
      .slice(0, 2)
      .join('')
      .toUpperCase()
  );

  const colorIndex = $derived(
    name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % palettes.length
  );
</script>

<div
  class="relative inline-flex {interactive
    ? 'transition-shadow hover:ring-2 hover:ring-info hover:ring-offset-2 rounded-full'
    : ''}"
>
  {#if avatarUrl}
    <img src={avatarUrl} alt={name} class="{sizeClasses[size]} rounded-full object-cover" />
  {:else}
    <div
      class="{sizeClasses[
        size
      ]} rounded-full flex items-center justify-center font-medium {palettes[colorIndex]}"
    >
      {initials}
    </div>
  {/if}

  {#if verified}
    <div
      class="absolute -bottom-0.5 -right-0.5 bg-info text-white rounded-full p-0.5 ring-2 ring-surface-primary"
      title="Compte vérifié"
    >
      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
        <path
          fill-rule="evenodd"
          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
          clip-rule="evenodd"
        />
      </svg>
      <span class="sr-only">Compte vérifié</span>
    </div>
  {/if}
</div>
