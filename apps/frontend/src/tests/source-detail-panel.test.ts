/**
 * Premier test de composant du projet.
 *
 * Le backlog portait « Test composant Svelte 5 incompat — à réécrire avec API
 * testing-library compatible Svelte 5 ». Vérifié le 2026-08-07 : il n'y avait
 * plus aucun test de composant à réécrire, seulement `@testing-library/svelte`
 * installé et jamais appelé. L'absence se lisait comme une incompatibilité.
 *
 * Ce test prouve que la chaîne fonctionne, et verrouille au passage #317 :
 * `impact_factor`, `subscribers_count` et `views_count` n'ont jamais été
 * renseignés par du code de production — seul le seed de démo leur donnait une
 * valeur, en dur. Les réafficher remettrait un chiffre sans provenance sur une
 * fiche qui promet la traçabilité.
 */
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import SourceDetailPanel from '$lib/components/SourceDetailPanel.svelte';
import type { CardDetail, Source } from '$lib/api/types';

function makeSource(overrides: Partial<Source> = {}): Source {
  return {
    id: 's1',
    url: 'https://exemple.fr/a',
    title: 'Un titre de source',
    authors: 'Doe, J.',
    published_at: '2020-01-01',
    format: 'texte',
    category: 'article-scientifique',
    author_kind: 'chercheur',
    annotation: null,
    stance: null,
    is_pivot: false,
    archive_status: 'pending',
    archive_url: null,
    archive_timestamp: null,
    parent_source_id: null,
    conflict_of_interest: null,
    citations_count: null,
    subscribers_count: null,
    views_count: null,
    impact_factor: null,
    excerpts: [],
    created_at: '2020-01-01T00:00:00Z',
    updated_at: null,
    ...overrides,
  } as Source;
}

function makeCard(sources: Source[]): CardDetail {
  return { sources } as CardDetail;
}

function renderPanel(source: Source) {
  return render(SourceDetailPanel, {
    props: {
      source,
      card: makeCard([source]),
      onClose: () => {},
      onSelect: () => {},
    },
  });
}

describe('SourceDetailPanel', () => {
  it('affiche le titre de la source', () => {
    renderPanel(makeSource());
    expect(screen.getByText('Un titre de source')).toBeTruthy();
  });

  it('affiche les citations, qui viennent réellement de Crossref', () => {
    renderPanel(makeSource({ citations_count: 1234 }));
    expect(screen.getByText(/citations/)).toBeTruthy();
  });

  it("n'affiche aucun indicateur jamais mesuré", () => {
    renderPanel(
      makeSource({ impact_factor: 49.8, subscribers_count: 120000, views_count: 2100000 })
    );
    expect(screen.queryByText(/Impact factor/)).toBeNull();
    expect(screen.queryByText(/abonnés/)).toBeNull();
    expect(screen.queryByText(/vues/)).toBeNull();
  });
});
