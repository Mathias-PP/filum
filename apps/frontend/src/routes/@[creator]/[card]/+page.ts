import { error } from '@sveltejs/kit';
import { env } from '$env/dynamic/public';
import type { PageLoad } from './$types';
import type { CardDetail } from '$lib/api';
import { normalizeCardDetail } from '$lib/api/legacy-adapter';

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, params }) => {
  const base = env.PUBLIC_API_BASE_URL ?? '';
  const res = await fetch(`${base}/api/v1/@${params.creator}/${params.card}`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');
  const raw: CardDetail = await res.json();
  const card = normalizeCardDetail(raw);
  return { card, creatorSlug: params.creator ?? '', cardSlug: params.card ?? '' };
};
