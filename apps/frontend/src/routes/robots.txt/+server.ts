import type { RequestHandler } from './$types';

/**
 * Sans robots.txt, un crawler doit deviner. Les fiches etaient deja rendues
 * cote serveur, JSON-LD compris, mais rien ne disait ou les trouver — et le
 * tableau de bord, lui, n'a rien a faire dans un index.
 *
 * Les robots des IA generatives (GPTBot, ClaudeBot, PerplexityBot...) ne sont
 * pas distingues des autres : c'est precisement le trafic qu'on veut, puisque
 * chaque fiche existe pour etre citee.
 */
export const GET: RequestHandler = ({ url }) => {
  const body = [
    'User-agent: *',
    'Allow: /',
    'Disallow: /dashboard',
    'Disallow: /auth',
    'Disallow: /api/',
    'Disallow: /sandbox',
    '',
    `Sitemap: ${url.origin}/sitemap.xml`,
    '',
  ].join('\n');

  return new Response(body, {
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'public, max-age=3600',
    },
  });
};
