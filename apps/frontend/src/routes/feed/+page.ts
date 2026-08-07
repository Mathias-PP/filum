import type { PageLoad } from './$types';

const PAGE_SIZE = 30;

export interface FeedEntry {
  id: string;
  kind: string;
  occurred_at: string;
  unpublished_at: string | null;
  creator_slug: string;
  creator_display_name: string | null;
  card_title: string;
  card_url: string;
  card_description: string | null;
}

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, url }) => {
  const before = url.searchParams.get('before') ?? '';
  const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (before) params.set('before', before);

  const res = await fetch(`/api/v1/feed?${params}`);
  const body = res.ok ? await res.json() : { entries: [], limit: PAGE_SIZE, next_before: null };

  return {
    entries: body.entries as FeedEntry[],
    nextBefore: body.next_before as string | null,
    failed: !res.ok,
  };
};
