<script lang="ts">
  import type { SourceCategory } from '$lib/api';
  import { categoryLabel } from '$lib/utils/author-colors';

  interface Props {
    category: SourceCategory;
    size?: 'sm' | 'md';
  }

  let { category, size = 'sm' }: Props = $props();

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };
</script>

<span
  class="inline-flex items-center rounded-full font-medium bg-surface-tertiary text-ink-primary {sizeClasses[
    size
  ]}"
>
  {categoryLabel(category)}
</span>
