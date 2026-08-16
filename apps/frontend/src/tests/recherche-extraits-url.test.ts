/**
 * Une recherche d'extraits doit survivre a un rafraichissement.
 *
 * La question posee a cette page est une phrase, pas un mot-cle : « l'effet du
 * sommeil sur la consolidation ». La reformuler coute a l'utilisateur, et la
 * page la perdait a chaque rechargement parce que l'etat vivait uniquement en
 * memoire. Un resultat n'etait ni partageable ni retrouvable par le bouton
 * Retour, contrairement a /discover ou l'URL porte deja la recherche.
 *
 * Le test lit la source : monter cette page demanderait de simuler le routeur
 * et le client API, pour ne verifier au bout du compte que ce lien a l'URL.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const page = readFileSync(
  resolve(process.cwd(), 'src/routes/dashboard/recherche/+page.svelte'),
  'utf-8'
);

describe('recherche dans mes extraits', () => {
  it('lit la question dans l’URL au chargement', () => {
    expect(page).toMatch(/searchParams\.get\('q'\)/);
  });

  it('ecrit la question dans l’URL quand on cherche', () => {
    expect(page).toMatch(/goto\(`\?q=\$\{encodeURIComponent\(q\)\}`/);
  });

  it('encode la question plutot que de la concatener telle quelle', () => {
    // Une question contient des espaces, des apostrophes et des accents : sans
    // encodage, l'URL produite est invalide et la navigation echoue.
    const brut = page.match(/goto\(`\?q=\$\{(\w+)\}`/);
    expect(brut, 'question inseree dans l’URL sans encodeURIComponent').toBeNull();
  });
});
