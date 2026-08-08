<!--
  Le panneau d'export à la carte.

  Le menu « Exporter » sert le cas courant : un clic, un format, tout le
  contenu. Ce panneau sert l'autre cas — celui où on sait exactement ce qu'on
  veut emporter, et où emporter le reste serait du bruit.

  Deux choix y sont exposés que l'API distingue et que l'interface doit
  distinguer aussi : ce qu'on emporte *de* la fiche (le périmètre), et
  jusqu'où on va *autour* d'elle (le voisinage). Et dans le voisinage, les
  fiches qu'elle cite ne sont pas les fiches qui la citent : l'une est ses
  fondations, l'autre sa postérité. Deux zones, jamais fondues en une.

  Les cases qu'un format ne peut pas honorer sont grisées plutôt que
  silencieusement ignorées : cocher « extraits » pour un export BibTeX et
  recevoir un `.bib` sans extraits ressemblerait à un bug.
-->
<script lang="ts">
  import Modal from './Modal.svelte';
  import {
    MAX_DEGREE,
    NEIGHBOUR_FORMATS,
    SCOPED_FORMATS,
    SECTIONS,
    buildExportUrl,
    emptyScope,
    fullScope,
    type Scope,
  } from '$lib/export-query';

  interface Props {
    open: boolean;
    exportBase: string;
  }

  let { open = $bindable(false), exportBase }: Props = $props();

  const FORMAT_GROUPS = [
    {
      label: 'Documents',
      formats: [
        { value: 'markdown', label: 'Markdown / Obsidian' },
        { value: 'docx', label: 'Word (.docx)' },
      ],
    },
    {
      label: 'Données',
      formats: [
        { value: 'json', label: 'JSON' },
        { value: 'philum', label: 'Philum JSON-LD' },
        { value: 'csv', label: 'CSV' },
        { value: 'xlsx', label: 'Excel (.xlsx)' },
      ],
    },
    {
      label: 'Gestionnaires de références',
      formats: [
        { value: 'bibtex', label: 'BibTeX (.bib)' },
        { value: 'ris', label: 'RIS (EndNote, Mendeley)' },
        { value: 'csl', label: 'CSL-JSON (Zotero)' },
      ],
    },
    {
      label: 'Styles de citation (texte)',
      formats: [
        { value: 'apa', label: 'APA 7' },
        { value: 'harvard', label: 'Harvard' },
        { value: 'mla', label: 'MLA 9' },
        { value: 'chicago', label: 'Chicago (auteur-date)' },
        { value: 'vancouver', label: 'Vancouver' },
        { value: 'ieee', label: 'IEEE' },
      ],
    },
  ];

  let format = $state('markdown');
  let scope = $state<Scope>(fullScope());

  // Un périmètre par degré, préparé jusqu'au plafond : changer la profondeur
  // ne doit pas effacer ce qui avait été coché pour un degré déjà réglé.
  let citedScopes = $state<Scope[]>(Array.from({ length: MAX_DEGREE }, () => fullScope()));
  let citingScopes = $state<Scope[]>(Array.from({ length: MAX_DEGREE }, () => fullScope()));
  let citedDepth = $state(0);
  let citingDepth = $state(0);

  const honoreLePerimetre = $derived(SCOPED_FORMATS.has(format));
  const porteLeVoisinage = $derived(NEIGHBOUR_FORMATS.has(format));

  const url = $derived(
    buildExportUrl(exportBase, {
      format,
      scope,
      cited: citedScopes.slice(0, citedDepth),
      citing: citingScopes.slice(0, citingDepth),
    })
  );

  const DEPTHS = [
    { value: 0, label: 'Aucune' },
    ...Array.from({ length: MAX_DEGREE }, (_, i) => ({
      value: i + 1,
      label: `Jusqu'au degré ${i + 1}`,
    })),
  ];
</script>

{#snippet sections(cible: Scope, disabled: boolean, prefixe: string)}
  <div class="grid grid-cols-2 gap-x-4 gap-y-1.5">
    {#each SECTIONS as section (section.key)}
      <label
        class="flex items-center gap-2 text-xs {disabled
          ? 'text-ink-tertiary cursor-not-allowed'
          : 'text-ink-secondary cursor-pointer'}"
      >
        <input
          type="checkbox"
          {disabled}
          bind:checked={cible[section.key]}
          class="rounded border-border accent-info"
          id="{prefixe}-{section.key}"
        />
        {section.label}
      </label>
    {/each}
  </div>
{/snippet}

{#snippet degres(scopes: Scope[], profondeur: number, prefixe: string)}
  {#each scopes.slice(0, profondeur) as degreScope, i (i)}
    <details class="mt-1.5 rounded border border-border">
      <summary class="px-2.5 py-1.5 text-xs text-ink-secondary cursor-pointer select-none">
        Degré {i + 1}
      </summary>
      <div class="px-2.5 pb-2.5 pt-0.5">
        {@render sections(degreScope, false, `${prefixe}-${i + 1}`)}
      </div>
    </details>
  {/each}
{/snippet}

<Modal bind:open title="Export personnalisé" size="lg">
  <div class="space-y-5">
    <div>
      <label for="export-format" class="block text-xs font-medium text-ink-primary mb-1.5"
        >Format</label
      >
      <select
        id="export-format"
        bind:value={format}
        class="w-full text-xs rounded-md border border-border bg-surface-primary text-ink-primary px-2.5 py-1.5"
      >
        {#each FORMAT_GROUPS as groupe (groupe.label)}
          <optgroup label={groupe.label}>
            {#each groupe.formats as f (f.value)}
              <option value={f.value}>{f.label}</option>
            {/each}
          </optgroup>
        {/each}
      </select>
    </div>

    <div>
      <span class="block text-xs font-medium text-ink-primary mb-1"
        >Ce qu'on emporte de cette fiche</span
      >
      <p class="text-xs text-ink-tertiary mb-2">
        Les références partent toujours. Ces cases choisissent ce qui les accompagne.
      </p>
      {@render sections(scope, !honoreLePerimetre, 'perimetre')}
      {#if !honoreLePerimetre}
        <p class="text-xs text-ink-tertiary mt-2">
          Ce format suit une convention fermée : il ne porte que les références.
        </p>
      {/if}
    </div>

    <div>
      <span class="block text-xs font-medium text-ink-primary mb-1">Fiches connectées</span>
      <p class="text-xs text-ink-tertiary mb-2">
        Le degré 2 désigne une fiche atteinte par une fiche déjà atteinte.
      </p>
      {#if porteLeVoisinage}
        <div class="grid sm:grid-cols-2 gap-4">
          <div>
            <label for="profondeur-citees" class="block text-xs text-ink-secondary mb-1"
              >Fiches citées par celle-ci</label
            >
            <select
              id="profondeur-citees"
              bind:value={citedDepth}
              class="w-full text-xs rounded-md border border-border bg-surface-primary text-ink-primary px-2.5 py-1.5"
            >
              {#each DEPTHS as d (d.value)}
                <option value={d.value}>{d.label}</option>
              {/each}
            </select>
            {@render degres(citedScopes, citedDepth, 'citees')}
          </div>
          <div>
            <label for="profondeur-citantes" class="block text-xs text-ink-secondary mb-1"
              >Fiches qui citent celle-ci</label
            >
            <select
              id="profondeur-citantes"
              bind:value={citingDepth}
              class="w-full text-xs rounded-md border border-border bg-surface-primary text-ink-primary px-2.5 py-1.5"
            >
              {#each DEPTHS as d (d.value)}
                <option value={d.value}>{d.label}</option>
              {/each}
            </select>
            {@render degres(citingScopes, citingDepth, 'citantes')}
          </div>
        </div>
      {:else}
        <p class="text-xs text-ink-tertiary">
          Ce format ne sait pas porter de fiches voisines. Markdown, Word, Excel, JSON et Philum
          JSON-LD le font.
        </p>
      {/if}
    </div>
  </div>

  {#snippet footer()}
    <button
      type="button"
      onclick={() => (open = false)}
      class="text-xs text-ink-secondary hover:text-ink-primary px-3 py-1.5 rounded-md border border-border"
    >
      Annuler
    </button>
    <a
      href={url}
      download
      onclick={() => (open = false)}
      class="text-xs px-3 py-1.5 rounded-md bg-ink-primary text-surface-primary hover:opacity-90"
    >
      Télécharger
    </a>
  {/snippet}
</Modal>
