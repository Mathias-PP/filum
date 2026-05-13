<script lang="ts">
  interface Props {
    size?: number
    className?: string
  }

  let { size = 24, className = '' }: Props = $props()
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.5"
  stroke-linecap="round"
  stroke-linejoin="round"
  class={className}
  aria-hidden="true"
>
  <circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none" />
  <line x1="12" y1="12" x2="12" y2="2" />
  <line x1="12" y1="12" x2="21" y2="7" />
  <line x1="12" y1="12" x2="21" y2="17" />
  <line x1="12" y1="12" x2="12" y2="22" />
  <line x1="12" y1="12" x2="3" y2="17" />
  <line x1="12" y1="12" x2="3" y2="7" />
  <circle cx="12" cy="2" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="21" cy="7" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="21" cy="17" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="12" cy="22" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="3" cy="17" r="1.5" fill="currentColor" stroke="none" />
  <circle cx="3" cy="7" r="1.5" fill="currentColor" stroke="none" />
  <line x1="12" y1="2" x2="3" y2="17" stroke-dasharray="1 1.5" opacity="0.5" />
  <line x1="21" y1="7" x2="12" y2="22" stroke-dasharray="1 1.5" opacity="0.5" />
  <line x1="21" y1="17" x2="3" y2="7" stroke-dasharray="1 1.5" opacity="0.5" />
</svg>
