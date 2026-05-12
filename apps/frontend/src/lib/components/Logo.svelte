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
  <line x1="12" y1="22" x2="12" y2="17" />
  <path d="M12 17 L7 12 M12 17 L17 12" />
  <path d="M7 12 L4 7 M7 12 L9 7" />
  <path d="M17 12 L15 7 M17 12 L20 7" />
  <path d="M4 7 L9 7" stroke-dasharray="1.5 1.5" opacity="0.55" />
  <path d="M9 7 L15 7" stroke-dasharray="1.5 1.5" opacity="0.55" />
  <path d="M15 7 L20 7" stroke-dasharray="1.5 1.5" opacity="0.55" />
  <circle cx="4" cy="7" r="2" fill="currentColor" stroke="none" />
  <circle cx="9" cy="7" r="2" fill="currentColor" stroke="none" />
  <circle cx="15" cy="7" r="2" fill="currentColor" stroke="none" />
  <circle cx="20" cy="7" r="2" fill="currentColor" stroke="none" />
</svg>
