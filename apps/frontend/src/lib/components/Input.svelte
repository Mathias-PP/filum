<script lang="ts">
  interface Props {
    label: string;
    id?: string;
    type?: 'text' | 'email' | 'url' | 'password' | 'search';
    placeholder?: string;
    value?: string;
    error?: string;
    hint?: string;
    required?: boolean;
    disabled?: boolean;
    readonly?: boolean;
    class?: string;
    oninput?: (e: Event) => void;
    onblur?: (e: FocusEvent) => void;
  }

  let {
    label,
    id,
    type = 'text',
    placeholder = '',
    value = $bindable(''),
    error,
    hint,
    required = false,
    disabled = false,
    readonly = false,
    class: className = '',
    oninput,
    onblur,
  }: Props = $props();

  const inputId = $derived(id || label.toLowerCase().replace(/\s+/g, '-'));
</script>

<div class="space-y-1.5 {className}">
  <label for={inputId} class="block text-sm font-medium text-ink-secondary">
    {label}
    {#if required}
      <span class="text-danger" aria-hidden="true">*</span>
    {/if}
  </label>
  <input
    {type}
    id={inputId}
    bind:value
    {placeholder}
    {required}
    {disabled}
    {readonly}
    {oninput}
    {onblur}
    aria-invalid={error ? 'true' : undefined}
    aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
    class="form-input w-full h-9 rounded bg-surface-primary border border-border px-3 py-2 text-sm transition-colors
      focus:outline-none focus:border-info focus:ring-2 focus:ring-info focus:ring-offset-0
      placeholder:text-ink-tertiary
      read-only:bg-surface-tertiary read-only:text-ink-secondary
      disabled:bg-surface-tertiary disabled:cursor-not-allowed disabled:opacity-60
      {error ? 'border-danger focus:border-danger focus:ring-danger' : ''}"
  />
  {#if error}
    <p id="{inputId}-error" class="text-xs text-danger">{error}</p>
  {:else if hint}
    <p id="{inputId}-hint" class="text-xs text-ink-tertiary">{hint}</p>
  {/if}
</div>
