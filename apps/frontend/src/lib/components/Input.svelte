<script lang="ts">
  interface Props {
    label: string
    id?: string
    type?: 'text' | 'email' | 'url' | 'password'
    placeholder?: string
    value?: string
    error?: string
    required?: boolean
    disabled?: boolean
    class?: string
    oninput?: (e: Event) => void
  }

  let {
    label,
    id,
    type = 'text',
    placeholder = '',
    value = $bindable(''),
    error,
    required = false,
    disabled = false,
    class: className = '',
    oninput
  }: Props = $props()

  const inputId = id || label.toLowerCase().replace(/\s+/g, '-')
</script>

<div class="space-y-1.5 {className}">
  <label for={inputId} class="block text-sm font-medium text-slate-700">
    {label}
    {#if required}
      <span class="text-red-500">*</span>
    {/if}
  </label>
  <input
    {type}
    id={inputId}
    bind:value
    {placeholder}
    {required}
    {disabled}
    oninput={oninput}
    class="w-full px-4 py-2 rounded-lg border bg-white transition-all
      focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
      placeholder:text-slate-400
      disabled:bg-slate-50 disabled:cursor-not-allowed
      {error ? 'border-red-500 focus:ring-red-500 focus:border-red-500' : 'border-slate-300'}"
  />
  {#if error}
    <p class="text-sm text-red-500">{error}</p>
  {/if}
</div>
