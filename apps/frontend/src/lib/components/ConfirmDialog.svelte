<script lang="ts">
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';

  interface Props {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: 'default' | 'danger';
    onConfirm: () => void | Promise<void>;
    onCancel?: () => void;
  }

  let {
    open = $bindable(false),
    title,
    message,
    confirmLabel = 'Confirmer',
    cancelLabel = 'Annuler',
    variant = 'default',
    onConfirm,
    onCancel,
  }: Props = $props();

  let working = $state(false);

  async function confirm() {
    working = true;
    try {
      await onConfirm();
      open = false;
    } finally {
      working = false;
    }
  }

  function cancel() {
    open = false;
    onCancel?.();
  }
</script>

<Modal bind:open {title} onClose={cancel} size="sm">
  <p class="text-sm text-ink-secondary">{message}</p>
  {#snippet footer()}
    <Button variant="ghost" onclick={cancel} disabled={working}>{cancelLabel}</Button>
    <Button
      variant={variant === 'danger' ? 'danger' : 'primary'}
      onclick={confirm}
      loading={working}
    >
      {confirmLabel}
    </Button>
  {/snippet}
</Modal>
