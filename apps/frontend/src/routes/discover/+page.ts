import type { PageLoad } from './$types';
import { FILTER_KEYS, PAGE_SIZE, type DiscoverFacets, type DiscoverResult } from './shared';

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, url }) => {
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const v = url.searchParams.get(key);
    if (v) params.set(key, v);
  }
  const page = Math.max(1, Number(url.searchParams.get('page') ?? '1') || 1);
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String((page - 1) * PAGE_SIZE));

  const [listRes, facetRes] = await Promise.all([
    fetch(`/api/v1/discover?${params}`),
    fetch('/api/v1/discover/facets'),
  ]);

  const list = listRes.ok
    ? await listRes.json()
    : { total: 0, results: [], limit: PAGE_SIZE, offset: 0 };
  const facets: DiscoverFacets = facetRes.ok
    ? await facetRes.json()
    : { total: 0, platforms: [], content_types: [], creators: [] };

  return {
    results: list.results as DiscoverResult[],
    total: list.total as number,
    page,
    facets,
    // Erreur backend distinguee d'un corpus vide : « aucun resultat » et
    // « je n'ai pas pu chercher » ne sont pas la meme phrase.
    failed: !listRes.ok,
  };
};
