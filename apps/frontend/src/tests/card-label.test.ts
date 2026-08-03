import { describe, expect, it } from 'vitest';

import { cardNodeLabel } from '$lib/utils/card-label';

describe('cardNodeLabel', () => {
  it('affiche les auteurs du contenu plutôt que le créateur Philum', () => {
    // Sans cela, une fiche documentée par Mathias sur un article de Dubois
    // s’affiche « Mathias » et laisse croire qu’il en est l’auteur.
    expect(
      cardNodeLabel({
        authors: 'Dubois, C.; Martin, P.',
        creatorName: 'Mathias',
        creatorSlug: 'mathias-pinault',
      })
    ).toBe('Dubois, C.; Martin, P.');
  });

  it('affiche les auteurs même quand le créateur revendique la fiche', () => {
    // Revendiquer, c’est répondre de la bibliographie, pas signer le contenu.
    expect(
      cardNodeLabel({
        authors: 'Dubois, C.',
        creatorName: 'Mathias',
        creatorSlug: 'mathias-pinault',
      })
    ).toBe('Dubois, C.');
  });

  it('retombe sur le créateur quand les auteurs sont inconnus', () => {
    expect(cardNodeLabel({ authors: null, creatorName: 'Mathias', creatorSlug: 'mp' })).toBe(
      'Mathias'
    );
    expect(cardNodeLabel({ authors: '   ', creatorName: null, creatorSlug: 'mp' })).toBe('mp');
  });

  it('rend une chaîne vide quand rien n’est connu', () => {
    expect(cardNodeLabel({ authors: null, creatorName: null, creatorSlug: null })).toBe('');
  });
});
