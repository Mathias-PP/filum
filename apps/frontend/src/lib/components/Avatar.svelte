<script lang="ts">
  interface Props {
    avatarUrl?: string | null;
    name: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    verified?: boolean;
  }

  let { avatarUrl, name, size = 'md', verified = false }: Props = $props();

  const sizeClasses = {
    sm: 'w-8 h-8 text-sm',
    md: 'w-10 h-10 text-base',
    lg: 'w-14 h-14 text-xl',
    xl: 'w-20 h-20 text-3xl',
  };

  const colors = [
    'bg-blue-500',
    'bg-emerald-500',
    'bg-amber-500',
    'bg-purple-500',
    'bg-rose-500',
    'bg-cyan-500',
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
    name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % colors.length
  );
</script>

<div class="relative inline-flex">
  {#if avatarUrl}
    <img src={avatarUrl} alt={name} class="{sizeClasses[size]} rounded-full object-cover" />
  {:else}
    <div
      class="{sizeClasses[
        size
      ]} rounded-full flex items-center justify-center text-white font-medium {colors[colorIndex]}"
    >
      {initials}
    </div>
  {/if}

  {#if verified}
    <div class="absolute -bottom-0.5 -right-0.5 bg-blue-500 text-white rounded-full p-0.5">
      <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
        <path
          fill-rule="evenodd"
          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
          clip-rule="evenodd"
        />
      </svg>
    </div>
  {/if}
</div>
