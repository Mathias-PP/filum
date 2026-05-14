<script lang="ts">
  import type { AuthorKind } from '$lib/api';
  import { AUTHOR_COLORS } from '$lib/utils/author-colors';

  interface Props {
    kind: AuthorKind;
    size?: 'sm' | 'md';
  }

  let { kind, size = 'sm' }: Props = $props();

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };
</script>

<span
  class="inline-flex items-center rounded-full font-medium {AUTHOR_COLORS[kind]
    .bgClass} {sizeClasses[size]}"
>
  {AUTHOR_COLORS[kind].label}
</span>
