/**
 * Le lien d'evitement est la premiere chose qu'atteint une navigation au
 * clavier, et la seule qui permette de sauter le menu. Il vit hors de l'ecran
 * jusqu'au focus : personne ne le voit jamais par hasard, donc rien ne signale
 * qu'il a cesse d'etre lisible.
 *
 * Mesure du 2026-08-08 en mode sombre sur la fiche de demo : `color: white`
 * sur `background: rgb(var(--text-primary))` rendait blanc sur #F5F5F5, soit
 * **1,09:1**. En mode clair la meme regle donnait 17:1 — le defaut ne pouvait
 * apparaitre que dans un theme, et seulement au focus clavier.
 *
 * La regle tenue ici : les deux couleurs viennent de jetons qui s'inversent
 * ensemble. Une couleur figee en face d'un jeton de theme laisse le contraste
 * dependre du theme, ce qui n'est pas un choix mais un oubli.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const layout = readFileSync(resolve(process.cwd(), 'src/routes/+layout.svelte'), 'utf-8');

/** Le corps de la regle `.skip-link` de base (pas `:focus`). */
function regleSkipLink(source: string): string {
  const marqueur = ':global(.skip-link) {';
  const debut = source.indexOf(marqueur);
  expect(debut, '+layout.svelte doit styler .skip-link').toBeGreaterThan(-1);
  const ouvrante = debut + marqueur.length - 1;
  let profondeur = 0;
  for (let i = ouvrante; i < source.length; i++) {
    if (source[i] === '{') profondeur++;
    else if (source[i] === '}' && --profondeur === 0) return source.slice(ouvrante + 1, i);
  }
  throw new Error('regle .skip-link non fermee');
}

describe('lien d’evitement', () => {
  it('tire son fond et son texte de jetons qui s’inversent ensemble', () => {
    const corps = regleSkipLink(layout);
    for (const propriete of ['background', 'color']) {
      const declaration = corps.match(new RegExp(`^\\s*${propriete}\\s*:\\s*([^;]+);`, 'm'));
      expect(declaration, `.skip-link doit declarer ${propriete}`).not.toBeNull();
      expect(
        declaration![1].trim(),
        `${propriete} figee : elle ne suivra pas le passage en mode sombre`
      ).toMatch(/var\(--/);
    }
  });
});
