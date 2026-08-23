<script lang="ts">
  interface Props {
    /** Nom du fournisseur qui servira les conversations (lane active). */
    fournisseur?: string;
    /** Version exacte du warning à consentir, fournie par le serveur. */
    version: string;
    onvalider: (version: string) => void | Promise<void>;
    onfermer: () => void;
  }

  let { fournisseur = 'GLM · Z.ai', version, onvalider, onfermer }: Props = $props();

  let lu = $state(false);
  let enCours = $state(false);

  async function valider() {
    if (!lu || enCours) return;
    enCours = true;
    try {
      await onvalider(version);
    } finally {
      enCours = false;
    }
  }
</script>

<!-- Overlay plein écran : le consentement doit être un geste explicite,
     pas une case cochée par défaut au milieu d'une page. -->
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
  <div
    role="dialog"
    aria-modal="true"
    aria-labelledby="titre-consentement"
    class="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-lg border border-subtle bg-surface-primary p-5"
  >
    <h2 id="titre-consentement" class="mb-2 font-serif text-lg text-ink-primary">
      Activer le mode gratuit ?
    </h2>
    <p class="mb-3 text-sm text-ink-secondary">
      Sans aucune clé de votre côté, vos conversations seront traitées par
      <span class="font-medium">{fournisseur}</span>, via une clé fournie par Philum.
    </p>
    <div
      class="mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-200"
    >
      <p class="mb-1 font-medium">Ce que cela implique :</p>
      <ul class="list-disc space-y-1 pl-4">
        <li>
          Le fournisseur peut <span class="font-medium">conserver vos échanges</span> et les utiliser
          pour entraîner ou améliorer ses modèles.
        </li>
        <li>Ne transmettez aucune donnée personnelle ou confidentielle dans l'agent.</li>
        <li>Usage limité (messages/jour) et bascule automatique entre fournisseurs partenaires.</li>
        <li>
          Vous pouvez désactiver ce mode à tout moment ; il ne s'applique qu'aux nouveaux messages.
        </li>
      </ul>
    </div>
    <label class="mb-4 flex items-start gap-2 text-sm text-ink-primary">
      <input type="checkbox" bind:checked={lu} class="mt-0.5" />
      <span>J'ai lu et j'accepte que mes échanges soient traités dans ces conditions.</span>
    </label>
    <div class="flex justify-end gap-2">
      <button
        type="button"
        class="rounded px-3 py-1.5 text-sm text-ink-secondary hover:bg-surface-secondary"
        onclick={onfermer}
      >
        Annuler
      </button>
      <button
        type="button"
        disabled={!lu || enCours}
        class="rounded bg-accent px-3 py-1.5 text-sm text-white disabled:opacity-40"
        onclick={valider}
      >
        {enCours ? 'Activation…' : 'Activer le mode gratuit'}
      </button>
    </div>
  </div>
</div>
