<script lang="ts">
  import type { SourceType } from '$lib/api';
  import { SOURCE_COLORS } from '$lib/utils/source-colors';

  interface Props {
    type: SourceType;
    size?: 'sm' | 'md';
  }

  let { type, size = 'sm' }: Props = $props();

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };
</script>

<span
  class="inline-flex items-center rounded-full font-medium {SOURCE_COLORS[type]
    .bgClass} {sizeClasses[size]}"
>
  {SOURCE_COLORS[type].label}
</span>
