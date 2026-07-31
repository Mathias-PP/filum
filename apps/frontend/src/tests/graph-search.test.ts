import { describe, expect, it } from 'vitest';

import { buildHaystack, matchesAllTerms, searchTerms } from '$lib/utils/graph-search';

/** Référence type, telle que le graphe l'indexe. */
const madigan = buildHaystack([
  'Adverse childhood experiences: A meta-analysis of prevalence and moderators',
  'Madigan S., Deneault A., Racine N.',
  'World Psychiatry',
  'Wiley',
  '10.1002/wps.21122',
  'https://onlinelibrary.wiley.com/doi/10.1002/wps.21122',
  '2023',
  'Chercheur·euse(s)',
  'Texte',
  'Article scientifique',
]);

describe('searchTerms', () => {
  it('ignore la casse et les accents', () => {
    expect(searchTerms('Préprint')).toEqual(['preprint']);
  });

  it('rend une liste vide sur une requête blanche', () => {
    expect(searchTerms('   ')).toEqual([]);
  });
});

describe('matchesAllTerms', () => {
  it('trouve sur le titre', () => {
    expect(matchesAllTerms(madigan, searchTerms('meta-analysis'))).toBe(true);
  });

  it('trouve sur les auteurs sans se soucier de la casse', () => {
    expect(matchesAllTerms(madigan, searchTerms('MADIGAN'))).toBe(true);
  });

  it('trouve sur la revue et sur l’éditeur', () => {
    expect(matchesAllTerms(madigan, searchTerms('world psychiatry'))).toBe(true);
    expect(matchesAllTerms(madigan, searchTerms('wiley'))).toBe(true);
  });

  it('trouve sur le DOI', () => {
    expect(matchesAllTerms(madigan, searchTerms('10.1002/wps.21122'))).toBe(true);
  });

  it('trouve sur le libellé lisible de la catégorie, pas seulement sur son code', () => {
    expect(matchesAllTerms(madigan, searchTerms('article scientifique'))).toBe(true);
  });

  it('trouve sur un libellé accentué tapé sans accent', () => {
    expect(matchesAllTerms(madigan, searchTerms('chercheur euse'))).toBe(true);
  });

  it('combine les termes en ET à travers des champs distincts', () => {
    // Le nom et l'année ne sont jamais adjacents dans le texte indexé.
    expect(matchesAllTerms(madigan, searchTerms('madigan 2023'))).toBe(true);
    expect(matchesAllTerms(madigan, searchTerms('madigan 1998'))).toBe(false);
  });

  it('ne trouve rien qui ne soit pas dans la référence', () => {
    expect(matchesAllTerms(madigan, searchTerms('stroop'))).toBe(false);
  });
});

describe('buildHaystack', () => {
  it('écarte les champs absents sans coller les mots voisins', () => {
    expect(buildHaystack(['Sapiens', null, undefined, 'Harari'])).toBe('sapiens harari');
  });
});
