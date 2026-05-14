<script lang="ts">
  import type { SourceFormat } from '$lib/api';
  import { formatLabel } from '$lib/utils/author-colors';

  interface Props {
    format: SourceFormat;
    size?: 'sm' | 'md';
  }

  let { format, size = 'sm' }: Props = $props();

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm',
  };
</script>

<span
  class="inline-flex items-center rounded-full font-medium bg-slate-100 text-slate-700 {sizeClasses[
    size
  ]}"
>
  {formatLabel(format)}
</span>
