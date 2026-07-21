<script lang="ts">
  interface Step {
    label: string;
    description?: string;
    /** Rend l'étape cliquable (cercle + texte) — nécessite onStepClick. */
    clickable?: boolean;
  }

  interface Props {
    steps: Step[];
    current: number;
    class?: string;
    onStepClick?: (index: number) => void;
  }

  let { steps, current, class: className = '', onStepClick }: Props = $props();
</script>

{#snippet stepContent(step: Step, i: number, isActive: boolean, isDone: boolean)}
  <div
    class="flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium shrink-0 transition-colors
      {isDone
      ? 'bg-success text-white'
      : isActive
        ? 'bg-ink-primary text-surface-primary'
        : 'bg-surface-tertiary text-ink-tertiary border border-border'}"
    aria-current={isActive ? 'step' : undefined}
  >
    {#if isDone}
      <svg viewBox="0 0 20 20" fill="currentColor" class="w-3.5 h-3.5" aria-hidden="true">
        <path
          fill-rule="evenodd"
          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
          clip-rule="evenodd"
        />
      </svg>
    {:else}
      {i + 1}
    {/if}
  </div>
  <div class="min-w-0 text-left">
    <p
      class="text-xs sm:text-sm font-medium truncate {isActive
        ? 'text-ink-primary'
        : isDone
          ? 'text-ink-secondary'
          : 'text-ink-tertiary'}"
    >
      {step.label}
    </p>
    {#if step.description}
      <p class="hidden sm:block text-xs text-ink-tertiary truncate">
        {step.description}
      </p>
    {/if}
  </div>
{/snippet}

<nav aria-label="Progression" class={className}>
  <ol class="flex items-center gap-2 sm:gap-4">
    {#each steps as step, i (i)}
      {@const isActive = i === current}
      {@const isDone = i < current}
      {@const isClickable = Boolean(step.clickable && onStepClick && !isActive)}
      <li class="flex items-center gap-2 sm:gap-3 flex-1">
        {#if isClickable}
          <button
            type="button"
            class="flex items-center gap-2 sm:gap-3 min-w-0 rounded cursor-pointer group hover:opacity-80 transition-opacity"
            onclick={() => onStepClick?.(i)}
            title="Aller à l'étape « {step.label} »"
          >
            {@render stepContent(step, i, isActive, isDone)}
          </button>
        {:else}
          <div class="flex items-center gap-2 sm:gap-3 min-w-0">
            {@render stepContent(step, i, isActive, isDone)}
          </div>
        {/if}
        {#if i < steps.length - 1}
          <div
            class="hidden sm:block flex-1 h-px {isDone ? 'bg-success' : 'bg-border'}"
            aria-hidden="true"
          ></div>
        {/if}
      </li>
    {/each}
  </ol>
</nav>
