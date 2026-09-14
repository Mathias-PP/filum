<script lang="ts">
  /**
   * Le verdict de relecture d'un extrait, en un symbole.
   *
   * « Relu dans la source le 14 septembre 2026 » sous chaque extrait prenait une
   * ligne par citation. Le symbole dit l'essentiel (vérifié, vérifié avec
   * réserve, non vérifié) ; la phrase et sa date s'ouvrent au survol, au focus
   * clavier, ou par un appui long sur écran tactile.
   */
  import { CLASSES_VERDICT, type VerdictLu } from '$lib/utils/excerpt-verdict';

  interface Props {
    verdict: VerdictLu;
  }

  let { verdict }: Props = $props();

  const APPUI_LONG_MS = 450;

  let ouvert = $state(false);
  let racine = $state<HTMLSpanElement | null>(null);
  let minuteur: ReturnType<typeof setTimeout> | null = null;
  // Le clic qui suit un appui long ne doit pas refermer ce que l'appui a ouvert.
  let ouvertParAppui = false;

  const symbole = $derived(verdict.ton === 'verifie' || verdict.ton === 'nuance' ? '✓' : '?');

  function annulerAppui() {
    if (minuteur) clearTimeout(minuteur);
    minuteur = null;
  }

  function surPointeurBas(e: PointerEvent) {
    if (e.pointerType !== 'touch') return;
    annulerAppui();
    minuteur = setTimeout(() => {
      ouvert = true;
      ouvertParAppui = true;
    }, APPUI_LONG_MS);
  }

  function surClic() {
    if (ouvertParAppui) {
      ouvertParAppui = false;
      return;
    }
    ouvert = !ouvert;
  }

  $effect(() => {
    if (!ouvert) return;
    const fermerDehors = (e: PointerEvent) => {
      if (racine && !racine.contains(e.target as Node)) ouvert = false;
    };
    const fermerEchap = (e: KeyboardEvent) => {
      if (e.key === 'Escape') ouvert = false;
    };
    window.addEventListener('pointerdown', fermerDehors);
    window.addEventListener('keydown', fermerEchap);
    return () => {
      window.removeEventListener('pointerdown', fermerDehors);
      window.removeEventListener('keydown', fermerEchap);
    };
  });
</script>

<span class="relative inline-block align-baseline not-italic" bind:this={racine}>
  <button
    type="button"
    class="inline-flex h-4 min-w-4 select-none items-center justify-center rounded-full px-0.5 text-[0.7rem] font-semibold leading-none touch-manipulation {CLASSES_VERDICT[
      verdict.ton
    ]}"
    aria-label="{verdict.label}. {verdict.detail}"
    aria-expanded={ouvert}
    onmouseenter={() => (ouvert = true)}
    onmouseleave={() => (ouvert = false)}
    onfocus={() => (ouvert = true)}
    onblur={() => (ouvert = false)}
    onpointerdown={surPointeurBas}
    onpointerup={annulerAppui}
    onpointercancel={annulerAppui}
    oncontextmenu={(e) => e.preventDefault()}
    onclick={surClic}
  >
    <span aria-hidden="true">{symbole}</span>
  </button>
  {#if ouvert}
    <span
      role="tooltip"
      class="absolute bottom-full left-0 z-30 mb-1 block w-64 max-w-[80vw] rounded-md border border-border bg-surface-primary px-2.5 py-2 text-left text-xs font-normal not-italic text-ink-secondary shadow-lg"
    >
      <span class="block font-medium {CLASSES_VERDICT[verdict.ton]}">{verdict.label}</span>
      <span class="mt-0.5 block">{verdict.detail}</span>
    </span>
  {/if}
</span>
