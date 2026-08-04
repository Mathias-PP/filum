import { describe, expect, it } from 'vitest';

import { authorSummary, splitAuthors } from '$lib/utils/author-names';

describe('splitAuthors', () => {
  it('tranche sur le point-virgule, format Crossref', () => {
    expect(splitAuthors('Smith, J.; Doe, A.; Roe, B.')).toEqual([
      'Smith, J.',
      'Doe, A.',
      'Roe, B.',
    ]);
  });

  it('sépare des noms complets séparés par des virgules', () => {
    expect(splitAuthors('John Smith, Jane Doe')).toEqual(['John Smith', 'Jane Doe']);
  });

  it('recolle les initiales au nom qui précède', () => {
    // Sans ça, « J. » passerait pour un auteur à part entière.
    expect(splitAuthors('Smith, J., Doe, A.')).toEqual(['Smith, J.', 'Doe, A.']);
  });

  it('accepte « et », « and » et « & » comme séparateurs', () => {
    expect(splitAuthors('John Smith et Jane Doe')).toEqual(['John Smith', 'Jane Doe']);
    expect(splitAuthors('John Smith and Jane Doe')).toEqual(['John Smith', 'Jane Doe']);
    expect(splitAuthors('John Smith & Jane Doe')).toEqual(['John Smith', 'Jane Doe']);
  });

  it('ne renvoie rien quand il n’y a rien', () => {
    expect(splitAuthors(null)).toEqual([]);
    expect(splitAuthors('   ')).toEqual([]);
    expect(splitAuthors(undefined)).toEqual([]);
  });

  it('rend un auteur unique tel quel', () => {
    expect(splitAuthors('Marie Curie')).toEqual(['Marie Curie']);
  });
});

describe('authorSummary', () => {
  const list = 'Smith, J.; Doe, A.; Roe, B.; Poe, C.';

  it('rend la liste entière quand aucun réglage n’est actif', () => {
    // Ne rien réduire est la seule option qui ne perd aucune information.
    expect(authorSummary(list, { first: false, last: false })).toBe(list);
  });

  it('garde le premier nom et dit que la liste est tronquée', () => {
    expect(authorSummary(list, { first: true, last: false })).toBe('Smith, J. et al.');
  });

  it('garde le dernier nom, souvent celui qui dirige les travaux', () => {
    expect(authorSummary(list, { first: false, last: true })).toBe('Poe, C. et al.');
  });

  it('encadre par une ellipse quand les deux réglages sont actifs', () => {
    expect(authorSummary(list, { first: true, last: true })).toBe('Smith, J. … Poe, C.');
  });

  it('n’invente pas d’ellipse quand il n’y a personne entre les deux', () => {
    expect(authorSummary('Smith, J.; Doe, A.', { first: true, last: true })).toBe(
      'Smith, J., Doe, A.'
    );
  });

  it('ne colle pas « et al. » à un auteur qui est seul', () => {
    expect(authorSummary('Marie Curie', { first: true, last: false })).toBe('Marie Curie');
    expect(authorSummary('Marie Curie', { first: true, last: true })).toBe('Marie Curie');
  });

  it('rend une chaîne vide quand il n’y a pas d’auteur', () => {
    expect(authorSummary(null, { first: true, last: false })).toBe('');
  });
});
