/**
 * Depuis Tailwind v4, `--color-*` n'est plus un nom libre : c'est l'espace de
 * noms du theme. Une variable de ce nom declaree ailleurs que dans `@theme`
 * ecrase celle que `@theme` genere, et le fait silencieusement — la classe
 * existe toujours dans le CSS produit, seule sa valeur change.
 *
 * C'est ainsi que six alias herites de la v3 ont survecu a la migration :
 * `--color-border: var(--border)` rendait le triplet nu « 232 230 222 », qui
 * n'est pas une couleur valide, si bien que `border-border` retombait sur
 * `currentColor` et que les contours de carte prenaient le noir du texte.
 * Ni le build, ni les tests, ni le diff des selecteurs du CSS ne l'ont vu ;
 * il a fallu lire la valeur calculee dans un navigateur.
 *
 * Ce test tient la seule regle qui aurait suffi a l'eviter.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest sert les modules par HTTP : `import.meta.url` n'est pas un chemin de
// fichier. La racine du projet est le repertoire de travail de vitest.
const css = readFileSync(resolve(process.cwd(), 'src/app.css'), 'utf-8');

/** Le corps du bloc `@theme { … }`, seul endroit ou `--color-*` est legitime. */
function corpsDuTheme(source: string): string {
  const debut = source.indexOf('@theme');
  expect(debut, 'app.css doit declarer un bloc @theme').toBeGreaterThan(-1);
  const ouvrante = source.indexOf('{', debut);
  let profondeur = 0;
  for (let i = ouvrante; i < source.length; i++) {
    if (source[i] === '{') profondeur++;
    else if (source[i] === '}' && --profondeur === 0) return source.slice(ouvrante + 1, i);
  }
  throw new Error('bloc @theme non ferme');
}

describe('app.css', () => {
  it('ne declare aucun `--color-*` hors du bloc @theme', () => {
    const theme = corpsDuTheme(css);
    const dehors = css.replace(theme, '');
    const collisions = [...dehors.matchAll(/^\s*(--color-[\w-]+)\s*:/gm)].map((m) => m[1]);
    expect(collisions).toEqual([]);
  });

  it('donne aux couleurs du theme une valeur qui en est une', () => {
    // `--color-x: var(--jeton)` ou `--jeton` porte un triplet RGB nu est le
    // piege exact qui a mordu : syntaxiquement valide, sans couleur au bout.
    const nues = [...corpsDuTheme(css).matchAll(/^\s*(--color-[\w-]+)\s*:\s*var\([^)]+\)\s*;/gm)];
    expect(nues.map((m) => m[1])).toEqual([]);
  });
});
