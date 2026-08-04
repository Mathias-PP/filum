import type { RequestHandler } from './$types';

const STATIC_PAGES = [
  { path: '/', priority: '1.0', changefreq: 'daily' },
  { path: '/discover', priority: '0.9', changefreq: 'daily' },
  { path: '/about', priority: '0.5', changefreq: 'monthly' },
  { path: '/features', priority: '0.5', changefreq: 'monthly' },
  { path: '/developers', priority: '0.5', changefreq: 'monthly' },
  { path: '/roadmap', priority: '0.4', changefreq: 'monthly' },
  { path: '/security', priority: '0.3', changefreq: 'yearly' },
  { path: '/privacy', priority: '0.3', changefreq: 'yearly' },
];

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/**
 * Le sitemap est bati depuis /discover, la meme source que la page publique :
 * il ne peut donc pas annoncer une fiche que le visiteur ne verrait pas.
 *
 * Si le backend ne repond pas, on sert quand meme les pages statiques plutot
 * qu'une 500 : un sitemap partiel vaut mieux qu'un sitemap absent, et un
 * crawler qui prend une erreur peut espacer ses visites pour longtemps.
 */
export const GET: RequestHandler = async ({ url, fetch, setHeaders }) => {
  const entries: string[] = STATIC_PAGES.map(
    (p) =>
      `  <url><loc>${esc(url.origin + p.path)}</loc>` +
      `<changefreq>${p.changefreq}</changefreq><priority>${p.priority}</priority></url>`
  );

  try {
    // Pagination explicite : le corpus grandira, et un sitemap tronque
    // silencieusement a 20 fiches serait pire qu'aucun sitemap.
    const LIMIT = 100;
    const MAX = 5000;
    for (let offset = 0; offset < MAX; offset += LIMIT) {
      const res = await fetch(`/api/v1/discover?limit=${LIMIT}&offset=${offset}`);
      if (!res.ok) break;
      const body = await res.json();
      for (const c of body.results ?? []) {
        const loc = `${url.origin}/@${c.creator_slug}/${c.slug}`;
        const lastmod = c.published_at ? String(c.published_at).slice(0, 10) : null;
        entries.push(
          `  <url><loc>${esc(loc)}</loc>` +
            (lastmod ? `<lastmod>${lastmod}</lastmod>` : '') +
            `<changefreq>weekly</changefreq><priority>0.8</priority></url>`
        );
      }
      if (offset + LIMIT >= (body.total ?? 0)) break;
    }
  } catch {
    // Backend injoignable : on sert les pages statiques seules.
  }

  setHeaders({
    'content-type': 'application/xml; charset=utf-8',
    'cache-control': 'public, max-age=1800',
  });
  return new Response(
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
      `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${entries.join('\n')}\n</urlset>\n`
  );
};
