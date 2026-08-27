<script lang="ts">
  import Button from '../Button.svelte';

  interface Props {
    tool: string;
    args: Record<string, unknown>;
    /** Phrase lisible calculée par le serveur (résout UUIDs en titres). */
    resume?: string | undefined;
    /** `null` tant que personne n'a répondu. */
    approved?: boolean | null;
    /** Époque (secondes) d'expiration de la demande, fournie par le serveur. */
    expiresAt?: number | undefined;
    onrespond: (approved: boolean) => void;
  }

  let { tool, args, resume, approved = null, expiresAt = undefined, onrespond }: Props = $props();

  let envoi = $state(false);
  let dateMaintenant = $state(Date.now());

  // Re-rend la carte chaque seconde tant qu'une réponse est encore possible,
  // pour faire vivre le compte à rebours sans bloquer le reste de l'UI.
  $effect(() => {
    if (approved !== null || expiresAt === undefined) return;
    const handle = window.setInterval(() => {
      dateMaintenant = Date.now();
    }, 1000);
    return () => window.clearInterval(handle);
  });

  // Refus automatique à expiration : on veut exactement un appel, et seulement
  // si l'utilisateur n'a pas encore répondu (le serveur refuse à son tour, on
  // ne fait que le refléter dans l'UI sans re-poster sur un cas déjà tranché).
  let autoDenie = $state(false);
  $effect(() => {
    if (approved !== null || autoDenie) return;
    if (expiresAt !== undefined && dateMaintenant >= expiresAt * 1000) {
      autoDenie = true;
      repondre(false);
    }
  });

  const restantes = $derived(
    expiresAt === undefined
      ? null
      : Math.max(0, Math.ceil((expiresAt * 1000 - dateMaintenant) / 1000))
  );

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

  // Le bouton refuse doit disparaître au même instant que le serveur refuse :
  // laisser intact un "Refuser" après une expiration auto-marnée inviterait à
  // un double-refus inoffensif mais confus.
  const apresExpiration = $derived(approved === null && restantes !== null && restantes <= 0);
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
    {#if restantes !== null}
      <p class="mt-2 text-xs text-ink-tertiary" role="timer" aria-live="polite">
        Auto-refus dans {restantes > 0 ? `${restantes} s` : '…'}. Sans réponse, l’action n’est pas
        lancée.
      </p>
    {/if}
    <div class="mt-3 flex gap-2">
      <Button size="sm" loading={envoi} disabled={apresExpiration} onclick={() => repondre(true)}
        >{libelleOK}</Button
      >
      <Button
        size="sm"
        variant="ghost"
        loading={envoi}
        disabled={apresExpiration}
        onclick={() => repondre(false)}
      >
        {libelleNon}
      </Button>
    </div>
  {:else}
    <p class="mt-2 text-xs text-ink-tertiary">
      {approved ? 'Autorisée.' : 'Refusée : rien n’a été écrit.'}
    </p>
  {/if}
</div>
