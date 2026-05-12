<script lang="ts">
  import type { SourceType } from '$lib/api'

  interface Props {
    type: SourceType
    size?: 'sm' | 'md'
  }

  let { type, size = 'sm' }: Props = $props()

  const config = {
    'peer-reviewed': { label: 'Peer-reviewed', class: 'bg-emerald-100 text-emerald-800' },
    institutional: { label: 'Institutionnel', class: 'bg-blue-100 text-blue-800' },
    press: { label: 'Presse', class: 'bg-amber-100 text-amber-800' },
    original: { label: 'Original', class: 'bg-purple-100 text-purple-800' }
  }

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-sm'
  }
</script>

<span class="inline-flex items-center rounded-full font-medium {config[type].class} {sizeClasses[size]}">
  {config[type].label}
</span>
