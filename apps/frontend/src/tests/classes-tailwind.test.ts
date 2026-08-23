/**
 * Une classe de couleur qui ne correspond a aucun jeton du theme ne fait pas
 * echouer le build : elle ne produit simplement aucune regle, et personne ne le
 * voit. Le defaut se paie deux fois.
 *
 * Sur `bg-*` et `text-*`, rien n'est emis du tout : le badge de `/dashboard`
 * portait `bg-accent text-white`, donc du texte blanc sans fond, invisible sur
 * la surface claire. Sur `border-*`, c'est pire, parce que la regle de
 * compatibilite que Tailwind v4 pose dans `@layer base` donne a tout element une
 * `border-color: var(--color-gray-200)`. La couleur inventee retombe donc sur un
 * gris qui, en theme clair, ressemble assez a `--border` (#e8e6de contre
 * #e5e7eb) pour que le defaut passe inapercu pendant des mois, et qui en theme
 * sombre est un gris clair pose sur un fond presque noir : des contours
 * franchement trop lumineux. C'est ce qu'ont vecu `border-subtle`, utilise 33
 * fois, `bg-warning-subtle` et toute la famille `accent`, aucun de ces noms
 * n'ayant jamais ete declare dans le `@theme`.
 *
 * L'oracle de ce test est le compilateur Tailwind lui-meme, nourri du vrai
 * `app.css` : on lui soumet les classes trouvees dans le code et on regarde
 * lesquelles ne ressortent pas. Aucune liste de valeurs valides n'est ecrite
 * ici, et c'est le point : une liste ecrite a la main vieillirait a chaque
 * montee de version de Tailwind et a chaque jeton ajoute au theme, et ses faux
 * positifs finiraient par faire desactiver le test.
 */
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { compile } from 'tailwindcss';
import { describe, expect, it } from 'vitest';

const RACINE = process.cwd();

/** Prefixes d'utilitaires qui prennent une couleur en argument. */
const PREFIXES = [
  'accent',
  'bg',
  'border',
  'caret',
  'decoration',
  'divide',
  'fill',
  'from',
  'outline',
  'placeholder',
  'ring',
  'shadow',
  'stroke',
  'text',
  'to',
  'via',
];

function sources(dossier: string): string[] {
  const trouves: string[] = [];
  for (const entree of readdirSync(dossier, { withFileTypes: true })) {
    const chemin = join(dossier, entree.name);
    if (entree.isDirectory()) trouves.push(...sources(chemin));
    else if (/\.(svelte|ts)$/.test(entree.name)) trouves.push(chemin);
  }
  return trouves;
}

/**
 * Les classes candidates, avec les fichiers qui les portent.
 *
 * On ne lit que les positions de classe : l'attribut `class`, la directive
 * `class:nom` et les expressions `class={...}`. Un `stroke-width="2"` sur un SVG
 * ou un `text-decoration` dans un bloc `<style>` porte le meme prefixe sans etre
 * un utilitaire, et serait signale a tort.
 */
function candidats(): Map<string, Set<string>> {
  const trouves = new Map<string, Set<string>>();
  for (const fichier of sources(resolve(RACINE, 'src'))) {
    const contenu = readFileSync(fichier, 'utf-8').replace(/<style[\s\S]*?<\/style>/g, '');
    for (const bloc of contenu.matchAll(/class(?::([\w-]+)|\s*=\s*("[^"]*"|'[^']*'|\{[^}]*\}))/g)) {
      for (const jeton of (bloc[1] ?? bloc[2]).split(/[\s"'`{}(),?:]+/)) {
        // Les variantes (`hover:`, `dark:`) sont retirees pour tester le prefixe,
        // mais la classe est soumise entiere : c'est elle qui doit compiler.
        const nu = jeton.replace(/^[a-z-]+:/g, '');
        if (!PREFIXES.some((p) => nu.startsWith(`${p}-`))) continue;
        // Une classe construite a l'execution (`bg-${couleur}-100`) n'est pas
        // verifiable ici ; Tailwind ne la voit pas davantage.
        if (!/^[a-z][a-z0-9/[\].%-]*$/.test(jeton)) continue;
        if (!trouves.has(jeton)) trouves.set(jeton, new Set());
        trouves.get(jeton)?.add(relative(RACINE, fichier));
      }
    }
  }
  return trouves;
}

/** Le CSS que Tailwind produit pour ces classes, avec le theme du projet. */
async function compiler(classes: string[]): Promise<string> {
  const moteur = await compile(readFileSync(resolve(RACINE, 'src/app.css'), 'utf-8'), {
    base: resolve(RACINE, 'src'),
    loadStylesheet: async (id: string) => {
      const chemin = resolve(RACINE, 'node_modules', id === 'tailwindcss' ? `${id}/index.css` : id);
      return { path: chemin, base: chemin, content: readFileSync(chemin, 'utf-8') };
    },
    loadModule: async (id: string) => {
      const module = await import(/* @vite-ignore */ id);
      return { path: id, base: RACINE, module: module.default ?? module };
    },
  });
  return moteur.build(classes);
}

/** Le selecteur qu'une classe donne une fois echappee. */
function selecteur(classe: string): string {
  return `.${classe.replace(/([:.[\]/%])/g, '\\$1')}`;
}

describe('classes de couleur', () => {
  it('correspondent toutes a un jeton que Tailwind sait resoudre', async () => {
    const trouves = candidats();
    const classes = [...trouves.keys()].sort();
    expect(classes.length, 'aucune classe candidate : extraction cassee').toBeGreaterThan(50);

    const css = await compiler(classes);
    const mortes = classes.filter((classe) => !css.includes(selecteur(classe)));

    expect(
      mortes.map((c) => `${c} (${[...(trouves.get(c) ?? [])].join(', ')})`),
      'ces classes ne produisent aucune regle : le jeton correspondant manque au @theme'
    ).toEqual([]);
  });

  it('signale une classe dont le jeton n existe pas', async () => {
    const css = await compiler(['border-border', 'border-subtle']);
    expect(css).toContain(selecteur('border-border'));
    expect(css).not.toContain(selecteur('border-subtle'));
  });
});
