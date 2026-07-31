import { describe, expect, it } from 'vitest';

import { cardNodeLabel } from '$lib/utils/card-label';

describe('cardNodeLabel', () => {
  it('affiche les auteurs réels quand la fiche n’est pas revendiquée', () => {
    // Sans cela, une fiche documentée par Mathias sur un article de Dubois
    // s’affiche « Mathias » et laisse croire qu’il en est l’auteur.
    expect(
      cardNodeLabel({
        authors: 'Dubois, C.; Martin, P.',
        creatorName: 'Mathias',
        creatorSlug: 'mathias-pinault',
        isSeed: true,
      })
    ).toBe('Dubois, C.; Martin, P.');
  });

  it('affiche le créateur quand il revendique la fiche', () => {
    expect(
      cardNodeLabel({
        authors: 'Dubois, C.',
        creatorName: 'Mathias',
        creatorSlug: 'mathias-pinault',
        isSeed: false,
      })
    ).toBe('Mathias');
  });

  it('retombe sur le créateur quand les auteurs réels sont inconnus', () => {
    expect(
      cardNodeLabel({ authors: null, creatorName: 'Mathias', creatorSlug: 'mp', isSeed: true })
    ).toBe('Mathias');
    expect(cardNodeLabel({ authors: '   ', creatorName: null, creatorSlug: 'mp', isSeed: true })).toBe(
      'mp'
    );
  });

  it('retombe sur les auteurs quand aucun créateur n’est connu', () => {
    expect(cardNodeLabel({ authors: 'Nguyen, T.', creatorName: null, creatorSlug: null })).toBe(
      'Nguyen, T.'
    );
  });
});
