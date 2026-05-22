import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { CardDetail } from '$lib/api';
import { normalizeCardDetail } from '$lib/api/legacy-adapter';

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, params }) => {
  // Relative — works both in the browser (SvelteKit /api proxy → backend) and
  // during SSR (server-side `fetch` resolves against the request origin and
  // re-enters the same proxy route).
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');
  const raw: CardDetail = await res.json();
  const card = normalizeCardDetail(raw);
  return { card, creatorSlug: params.creator ?? '', cardSlug: params.card ?? '' };
};
