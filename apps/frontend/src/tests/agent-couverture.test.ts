import { describe, expect, it } from 'vitest';

import { libelleExtraits, resumeCouverture } from '$lib/agent/couverture';
import type { CouvertureFiche } from '$lib/api/agent';

function couverture(extraits: number[]): CouvertureFiche {
  return {
    slug: 'taxe-carbone',
    sous_questions: extraits.map((n, i) => ({
      texte: `Question ${i + 1}`,
      extraits: n,
      sources: n,
    })),
    sources_sans_extrait: 0,
    extraits: extraits.reduce((a, b) => a + b, 0),
  };
}

describe('couverture du plan', () => {
  it('ne dit rien sans plan', () => {
    expect(resumeCouverture(null)).toBeNull();
    expect(resumeCouverture(couverture([]))).toBeNull();
  });

  it('compte les sous-questions qui ont un extrait', () => {
    expect(resumeCouverture(couverture([2, 0, 1]))).toBe(
      '2 sous-questions sur 3 avec au moins un extrait'
    );
  });

  it('dit quand tout le plan est couvert', () => {
    expect(resumeCouverture(couverture([1, 4]))).toBe(
      'Les 2 sous-questions du plan ont au moins un extrait'
    );
  });

  it('nomme une sous-question vide sans chiffre zéro', () => {
    expect(libelleExtraits(0)).toBe('aucun extrait');
    expect(libelleExtraits(1)).toBe('1 extrait');
    expect(libelleExtraits(3)).toBe('3 extraits');
  });
});
