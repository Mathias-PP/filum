/**
 * Un jeton de texte n'est pas lisible dans l'absolu : il l'est *contre une
 * surface*. `--text-tertiary` avait ete regle a #757575 parce qu'il donnait
 * 4,61:1 — sur blanc pur. Mesure au navigateur le 2026-08-08 : la meme nuance
 * tombait a **4,41:1** des qu'elle etait posee sur `--bg-secondary`, qui est la
 * surface la plus courante de l'application. Un seuil qui ne tient que sur le
 * fond le plus favorable ne tient pas.
 *
 * Ce test verifie donc chaque jeton de texte contre **chaque** surface du meme
 * theme, pas seulement contre la plus clemente. Il lit `app.css` plutot que le
 * DOM parce que c'est la que le reglage se fait, et qu'un test qui monte un
 * navigateur ne serait pas lance a chaque commit.
 *
 * `--text-placeholder` est hors du lot : un exemple dans un champ vide n'est
 * pas du texte a lire, et le confondre avec une valeur saisie est le defaut
 * qu'on lui evite. Il n'a donc pas a franchir le seuil du texte.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const css = readFileSync(resolve(process.cwd(), 'src/app.css'), 'utf-8');

type Triplet = [number, number, number];

/** Les declarations `--nom: r g b;` d'un bloc de theme. */
function jetons(bloc: string): Record<string, Triplet> {
  const trouve: Record<string, Triplet> = {};
  for (const m of bloc.matchAll(/--([\w-]+):\s*(\d+)\s+(\d+)\s+(\d+)\s*;/g)) {
    trouve[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])];
  }
  return trouve;
}

/** Le corps du selecteur donne, accolades equilibrees. */
function bloc(selecteur: string): string {
  // Ancre sur le debut de ligne : `.dark` apparait d'abord dans la declaration
  // `@custom-variant dark (&:is(.dark *))`, qui n'est pas un bloc de jetons.
  const debut = css.search(new RegExp(`^\\s*${selecteur.replace('.', '\\.')}\\s*\\{`, 'm'));
  expect(debut, `app.css doit declarer ${selecteur}`).toBeGreaterThan(-1);
  const ouvrante = css.indexOf('{', debut);
  let profondeur = 0;
  for (let i = ouvrante; i < css.length; i++) {
    if (css[i] === '{') profondeur++;
    else if (css[i] === '}' && --profondeur === 0) return css.slice(ouvrante + 1, i);
  }
  throw new Error(`bloc ${selecteur} non ferme`);
}

function luminance([r, g, b]: Triplet): number {
  const lin = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function contraste(a: Triplet, b: Triplet): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

const TEXTES = ['text-primary', 'text-secondary', 'text-tertiary'];
const SURFACES = ['bg-primary', 'bg-secondary'];
const SEUIL_AA = 4.5;

describe('jetons de texte', () => {
  for (const [theme, selecteur] of [
    ['clair', ':root'],
    ['sombre', '.dark'],
  ] as const) {
    it(`franchissent le seuil AA sur toutes les surfaces du theme ${theme}`, () => {
      const t = jetons(bloc(selecteur));
      for (const texte of TEXTES) {
        expect(t[texte], `${selecteur} doit declarer --${texte}`).toBeDefined();
        for (const surface of SURFACES) {
          expect(t[surface], `${selecteur} doit declarer --${surface}`).toBeDefined();
          const ratio = contraste(t[texte], t[surface]);
          expect(
            ratio,
            `${theme} : --${texte} sur --${surface} donne ${ratio.toFixed(2)}:1, sous le plancher AA`
          ).toBeGreaterThanOrEqual(SEUIL_AA);
        }
      }
    });
  }
});
