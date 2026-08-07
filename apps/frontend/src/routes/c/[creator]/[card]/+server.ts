import { redirect } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

/**
 * Redirection vers la fiche canonique `/@createur/fiche`.
 *
 * Cette entree existe pour les agents qui refusent de fetcher une URL
 * contenant « @ ». Le 301 est cachable et transmet « Bing / Google /
 * Bingbot » a l'adresse canonique — voir aussi `[card].md/+server.ts`
 * qui, lui, sert le contenu directement sans redirection (les crawlers
 * d'IA ne suivent pas tous les redirections HTML).
 */
export const GET: RequestHandler = ({ params }) => {
  throw redirect(301, `/@${params.creator}/${params.card}`);
};
