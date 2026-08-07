import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * Meme fiche, meme markdown, adresse alternative sans « @ ».
 *
 * L'URL canonique reste `/@createur/fiche` ; celle-ci existe parce que
 * plusieurs crawlers d'agents conversationnels traitent « @ » comme le
 * separateur d'authentification RFC 3986 (`user@host`) et partent en
 * recherche Web au lieu de fetcher la ressource. `/c/createur/fiche.md`
 * n'a pas ce probleme, et un `Link: rel="canonical"` en tete conserve
 * l'agregation SEO sur la vraie adresse.
 */
export const GET: RequestHandler = async ({ fetch, params, url }) => {
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}/export?format=markdown`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');

  const canonical = `${url.origin}/@${params.creator}/${params.card}.md`;
  return new Response(await res.text(), {
    headers: {
      'content-type': 'text/markdown; charset=utf-8',
      'cache-control': 'public, max-age=300',
      link: `<${canonical}>; rel="canonical"`,
    },
  });
};
