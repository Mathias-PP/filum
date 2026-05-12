<script lang="ts">
  import type { Snippet } from 'svelte'

  interface Props {
    variant?: 'default' | 'success' | 'warning' | 'error'
    class?: string
    children: Snippet
  }

  let { variant = 'default', class: className = '', children }: Props = $props()

  const variantClasses = {
    default: 'bg-slate-50 border-slate-200',
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    warning: 'bg-amber-50 border-amber-200 text-amber-800',
    error: 'bg-red-50 border-red-200 text-red-800'
  }
</script>

<div
  class="rounded-lg border p-4 {variantClasses[variant]} {className}"
  role="alert"
>
  {@render children()}
</div>
