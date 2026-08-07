import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';
import type { CardDetail } from '$lib/api';
import { normalizeCardDetail } from '$lib/api/legacy-adapter';

export const ssr = true;
export const prerender = false;

export const load: PageLoad = async ({ fetch, params, setHeaders, url }) => {
  // Relative — works both in the browser (SvelteKit /api proxy → backend) and
  // during SSR (server-side `fetch` resolves against the request origin and
  // re-enters the same proxy route).
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');
  const raw: CardDetail = await res.json();
  const card = normalizeCardDetail(raw);
  // Header RFC 5988 : les crawlers d'agents conversationnels lisent parfois
  // les en-tetes HTTP avant meme le HTML — la version markdown, deja
  // structuree, leur epargne d'inventer une bibliographie a partir du rendu.
  // Doublonne volontairement le <link rel="alternate"> du <head>.
  // Variante sans `@` : les couches de navigation de ChatGPT et consorts
  // traitent une URL qui en contient comme une requete de recherche et ne font
  // jamais le GET. Annoncer l'alternative en `/c/` est le seul moyen qu'un
  // agent qui suit cet en-tete atterrisse sur quelque chose qu'il sait fetcher.
  const base = `${url.origin}/c/${params.creator}/${params.card}`;
  setHeaders({
    Link:
      `<${base}.md>; rel="alternate"; type="text/markdown", ` +
      `<${base}.philum.json>; rel="alternate"; type="application/vnd.philum+json"`,
  });
  return { card, creatorSlug: params.creator ?? '', cardSlug: params.card ?? '' };
};
