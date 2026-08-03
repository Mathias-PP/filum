import { describe, expect, it } from 'vitest';

import type { Source } from '$lib/api/types';
import { COMPARE_COLUMNS, compareCell, sortByColumn } from '$lib/utils/compare-columns';

function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: crypto.randomUUID(),
    url: 'https://example.org/a',
    title: 'Un titre',
    authors: null,
    published_at: null,
    format: 'texte',
    category: 'article-scientifique',
    author_kind: 'chercheur',
    annotation: null,
    stance: null,
    is_pivot: false,
    archive_status: 'archived',
    archive_url: null,
    archive_timestamp: null,
    parent_source_id: null,
    conflict_of_interest: null,
    citations_count: null,
    subscribers_count: null,
    views_count: null,
    impact_factor: null,
    excerpts: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  };
}

describe('compareCell — une cellule sans valeur dit pourquoi', () => {
  it('ne rend jamais une étiquette vide, quelle que soit la colonne', () => {
    // Le défaut de SciSpace est un `N/A` indifférencié ; le nôtre serait une
    // case blanche, qui se lirait comme un défaut d'affichage.
    const empty = makeSource();
    for (const column of COMPARE_COLUMNS) {
      const cell = compareCell(empty, column.id);
      expect(cell.label.trim()).not.toBe('');
      expect(cell.help.trim()).not.toBe('');
    }
  });

  it('distingue « jamais vérifié » de « non vérifiable » sur l’accès', () => {
    const never = compareCell(makeSource({ oa_status: null }), 'access');
    const cannot = compareCell(makeSource({ oa_status: 'unverifiable' }), 'access');
    expect(never.tone).toBe('absent');
    expect(cannot.tone).toBe('absent');
    expect(never.label).not.toBe(cannot.label);
  });

  it('distingue « jamais vérifié » de « aucun avis » sur la rétractation', () => {
    // `none` est une information positive et datée : Crossref connaît le DOI et
    // ne signale rien. La confondre avec l'absence de contrôle rassurerait sans
    // preuve.
    const never = compareCell(makeSource({ retraction_status: null }), 'retraction');
    const none = compareCell(makeSource({ retraction_status: 'none' }), 'retraction');
    expect(never.tone).toBe('absent');
    expect(none.tone).toBe('positive');
    expect(none.sortKey).not.toBeNull();
  });

  it('dit « sans objet » là où la notion de revue n’existe pas', () => {
    const video = compareCell(makeSource({ category: 'podcast' }), 'venue');
    const article = compareCell(makeSource({ category: 'article-scientifique' }), 'venue');
    expect(video.label).toBe('sans objet');
    expect(article.label).toBe('non renseignée');
  });

  it('ne prête pas une position à un auteur qui n’en a pas déclaré', () => {
    const silent = compareCell(makeSource({ stance: null }), 'stance');
    const mentions = compareCell(makeSource({ stance: 'mentionne' }), 'stance');
    expect(silent.tone).toBe('absent');
    expect(silent.label).not.toBe(mentions.label);
  });

  it('préfère la revue à l’éditeur quand les deux existent', () => {
    const cell = compareCell(makeSource({ journal: 'Nature', publisher: 'Springer' }), 'venue');
    expect(cell.label).toBe('Nature');
  });

  it('retombe sur l’éditeur quand la revue est une chaîne vide', () => {
    // Un import BibTeX ou Crossref produit couramment `journal: ''` plutôt
    // qu'absent : `??` ne l'aurait pas rattrapé et aurait masqué l'éditeur.
    for (const journal of ['', '   ']) {
      const cell = compareCell(makeSource({ journal, publisher: 'Springer' }), 'venue');
      expect(cell.label).toBe('Springer');
    }
  });

  it('signale une date illisible plutôt que d’afficher NaN', () => {
    const cell = compareCell(makeSource({ published_at: 'pas-une-date' }), 'year');
    expect(cell.label).not.toContain('NaN');
    expect(cell.tone).toBe('absent');
  });
});

describe('sortByColumn', () => {
  it('range les absences en queue dans les deux sens', () => {
    const sources = [
      makeSource({ id: 'sans-date', published_at: null }),
      makeSource({ id: '2020', published_at: '2020-01-01T00:00:00Z' }),
      makeSource({ id: '1999', published_at: '1999-01-01T00:00:00Z' }),
    ];
    expect(sortByColumn(sources, 'year', 'asc').map((s) => s.id)).toEqual([
      '1999',
      '2020',
      'sans-date',
    ]);
    expect(sortByColumn(sources, 'year', 'desc').map((s) => s.id)).toEqual([
      '2020',
      '1999',
      'sans-date',
    ]);
  });

  it('ne perd aucune ligne : comparer suppose de voir la bibliographie entière', () => {
    const sources = [
      makeSource({ id: 'a', oa_status: null }),
      makeSource({ id: 'b', oa_status: 'gold' }),
      makeSource({ id: 'c', oa_status: 'closed' }),
    ];
    expect(sortByColumn(sources, 'access', 'asc')).toHaveLength(3);
  });

  it('est stable : à valeur égale, l’ordre d’origine est conservé', () => {
    const sources = [
      makeSource({ id: 'a', published_at: '2020-06-01T00:00:00Z' }),
      makeSource({ id: 'b', published_at: '2020-01-01T00:00:00Z' }),
      makeSource({ id: 'c', published_at: '2020-09-01T00:00:00Z' }),
    ];
    expect(sortByColumn(sources, 'year', 'asc').map((s) => s.id)).toEqual(['a', 'b', 'c']);
  });

  it('remonte le plus grave en tête sur la rétractation', () => {
    const sources = [
      makeSource({ id: 'ok', retraction_status: 'none' }),
      makeSource({ id: 'retracte', retraction_status: 'retracted' }),
      makeSource({ id: 'garde', retraction_status: 'concern' }),
    ];
    expect(sortByColumn(sources, 'retraction', 'asc').map((s) => s.id)).toEqual([
      'retracte',
      'garde',
      'ok',
    ]);
  });

  it('ne modifie pas le tableau reçu', () => {
    const sources = [
      makeSource({ id: 'a', published_at: '2020-01-01T00:00:00Z' }),
      makeSource({ id: 'b', published_at: '1999-01-01T00:00:00Z' }),
    ];
    sortByColumn(sources, 'year', 'asc');
    expect(sources.map((s) => s.id)).toEqual(['a', 'b']);
  });
});
