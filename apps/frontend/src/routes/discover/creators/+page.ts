import type { PageLoad } from './$types';

const PAGE_SIZE = 20;

export interface CreatorResult {
  slug: string;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  is_verified: boolean;
  published_cards_count: number;
  url: string;
}

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, url }) => {
  const q = url.searchParams.get('q') ?? '';
  const pageNum = Math.max(1, Number(url.searchParams.get('page') ?? '1') || 1);
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  params.set('limit', String(PAGE_SIZE));
  params.set('offset', String((pageNum - 1) * PAGE_SIZE));

  const res = await fetch(`/api/v1/discover/creators?${params}`);
  const body = res.ok ? await res.json() : { total: 0, results: [], limit: PAGE_SIZE, offset: 0 };

  return {
    results: body.results as CreatorResult[],
    total: body.total as number,
    page: pageNum,
    pageSize: PAGE_SIZE,
    query: q,
    failed: !res.ok,
  };
};
