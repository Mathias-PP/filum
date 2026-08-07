import { error } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * La meme fiche en `application/vnd.philum+json` : JSON-LD (schema.org)
 * enrichi des champs Philum specifiques (stance, retraction, archive).
 *
 * Adresse devinable au meme titre que le `.md`. Reachable soit directement,
 * soit via l'URL canonique quand un client envoie `Accept:
 * application/vnd.philum+json` — la reecriture est dans hooks.server.ts.
 */
export const GET: RequestHandler = async ({ fetch, params }) => {
  const res = await fetch(`/api/v1/@${params.creator}/${params.card}/export?format=philum`);
  if (res.status === 404) error(404, 'Fiche non trouvée');
  if (!res.ok) error(res.status, 'Erreur de chargement');

  return new Response(await res.text(), {
    headers: {
      'content-type': 'application/vnd.philum+json; charset=utf-8',
      'cache-control': 'public, max-age=300',
    },
  });
};
