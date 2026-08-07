import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * Alternative sans « @ » pour les agents qui refusent l'URL canonique.
 * Voir le doublon `/@createur/fiche.philum.json` et la note dans
 * `[card].md/+server.ts`.
 */
export const GET: RequestHandler = async ({ fetch, params, url }) => {
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}/export?format=philum`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');

  const canonical = `${url.origin}/@${params.creator}/${params.card}.philum.json`;
  return new Response(await res.text(), {
    headers: {
      'content-type': 'application/vnd.philum+json; charset=utf-8',
      'cache-control': 'public, max-age=300',
      link: `<${canonical}>; rel="canonical"`,
    },
  });
};
