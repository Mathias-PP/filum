/**
 * Une fiche non revendiquée ne doit pas se dire revendiquée.
 *
 * Le pied de page affirmait « Contenu revendiqué par son créateur·ice » et
 * « attestée par signature Ed25519 » sur toute fiche publiée. Sur une fiche
 * seed, la même page portait deux phrases contraires : le bandeau du haut
 * annonçait qu'elle n'était pas validée par l'auteur·rice du contenu, le pied
 * affirmait le contraire. C'est la promesse centrale du produit qui se
 * contredisait a l'écran.
 *
 * Le test lit la source : monter cette page demanderait de simuler le routeur,
 * le client API et le graphe, pour ne verifier au bout du compte que cette
 * condition.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const page = readFileSync(
  resolve(process.cwd(), 'src/routes/@[creator]/[card]/+page.svelte'),
  'utf-8'
);

describe('pied de page d’une fiche publique', () => {
  it('conditionne la mention de revendication a une fiche revendiquée', () => {
    const i = page.indexOf('Contenu revendiqué par son créateur·ice');
    expect(i, 'mention de revendication introuvable').toBeGreaterThan(-1);
    // La condition la plus proche au-dessus de la mention doit la porter.
    const avant = page.slice(0, i);
    expect(avant.lastIndexOf('{#if !card.is_seed}')).toBeGreaterThan(avant.lastIndexOf('{/if}'));
  });

  it('ne promet la signature Ed25519 que dans ce meme bloc', () => {
    const iSig = page.indexOf('attestée par signature Ed25519');
    const iCond = page.lastIndexOf('{#if !card.is_seed}', iSig);
    expect(iCond).toBeGreaterThan(-1);
    expect(page.slice(iCond, iSig)).not.toContain('{/if}');
  });
});
