<script lang="ts">
  import Button from '../Button.svelte';

  interface Props {
    tool: string;
    args: Record<string, unknown>;
    /** Phrase lisible calculée par le serveur (résout UUIDs en titres). */
    resume?: string | undefined;
    /** `null` tant que personne n'a répondu. */
    approved?: boolean | null;
    onrespond: (approved: boolean) => void;
  }

  let { tool, args, resume, approved = null, onrespond }: Props = $props();

  let envoi = $state(false);

  // Libelle contextuel : "Supprimer" est plus clair que "Autoriser" pour un
  // delete ; l'action doit dire ce qui va arriver.
  const libelleOK = $derived(
    tool.startsWith('delete_')
      ? 'Supprimer'
      : tool.startsWith('publish_') || tool === 'update_card'
        ? 'Publier'
        : tool === 'create_content_attestation'
          ? 'Signer'
          : tool === 'archive_sources'
            ? 'Archiver'
            : tool === 'verify_excerpts'
              ? 'Attester'
              : 'Autoriser'
  );

  const libelleNon = $derived(tool.startsWith('delete_') ? 'Annuler' : 'Refuser');

  async function repondre(valeur: boolean) {
    envoi = true;
    try {
      await onrespond(valeur);
    } finally {
      envoi = false;
    }
  }
</script>

<div class="rounded-lg border border-warning/40 bg-warning-bg px-4 py-3 text-sm">
  {#if resume}
    <p class="text-ink-primary font-medium">{resume}</p>
    <p class="mt-1 text-xs text-ink-tertiary">
      Action sensible <span class="font-mono">{tool}</span>, lancée seulement si vous la validez.
    </p>
  {:else}
    <p class="text-ink-primary">
      L'agent veut exécuter <span class="font-mono">{tool}</span>. Cette action écrit chez vous :
      elle n'est lancée que si vous la validez.
    </p>
  {/if}
  <details class="mt-2 text-xs text-ink-secondary">
    <summary class="cursor-pointer text-ink-tertiary hover:text-ink-secondary">
      Voir les arguments bruts
    </summary>
    <pre class="mt-1 overflow-x-auto rounded bg-surface-tertiary p-2">{JSON.stringify(
        args,
        null,
        2
      )}</pre>
  </details>
  {#if approved === null}
    <div class="mt-3 flex gap-2">
      <Button size="sm" loading={envoi} onclick={() => repondre(true)}>{libelleOK}</Button>
      <Button size="sm" variant="ghost" loading={envoi} onclick={() => repondre(false)}>
        {libelleNon}
      </Button>
    </div>
  {:else}
    <p class="mt-2 text-xs text-ink-tertiary">
      {approved ? 'Autorisée.' : 'Refusée : rien n’a été écrit.'}
    </p>
  {/if}
</div>
