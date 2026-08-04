import type { RequestHandler } from './$types';

/**
 * Panneau indicateur, pas mecanisme.
 *
 * Aucun grand acteur (OpenAI, Google, Anthropic, Meta, Mistral) ne s'engage a
 * lire llms.txt ; leurs robots explorent le HTML. Ce fichier ne remplace donc
 * ni le rendu serveur, ni le JSON-LD, ni le sitemap — il coute vingt lignes et
 * dit a un agent curieux ou sont les portes d'entree machine.
 */
/** Le serveur MCP est monte sur l'hote de l'API, pas derriere le proxy /api du
 * front : l'annoncer a l'origine du site enverrait un agent sur une 404. */
const MCP_URL = 'https://philum-api.duckdns.org/mcp';

export const GET: RequestHandler = ({ url }) => {
  const o = url.origin;
  const body = `# Philum

> Philum relie un contenu (video, article, podcast, rapport) a la bibliographie
> que son auteur a reellement consultee. Chaque source est horodatee, archivee
> et signee cryptographiquement par le createur du contenu. L'objectif : rendre
> une affirmation verifiable en un clic, humain ou machine.

Toutes les fiches publiques sont accessibles sans authentification, en HTML
rendu cote serveur, avec un bloc JSON-LD (schema.org) portant la bibliographie
complete dans \`citation[]\`.

## Trouver des fiches

- [Annuaire public](${o}/discover): recherche plein texte et filtres (createur, auteur du contenu, plateforme, dates)
- [Sitemap](${o}/sitemap.xml): toutes les fiches publiques

## Acces machine

- Fiche en markdown: \`GET ${o}/@<createur>/<fiche>.md\` — la meme fiche, deja
  structuree (sources, DOI, statut de retractation, archives). C'est la porte
  d'entree la plus simple : suffixez \`.md\` a n'importe quelle adresse de fiche.
- Recherche JSON: \`GET ${o}/api/v1/discover?q=<termes>\` — sans authentification
- Facettes: \`GET ${o}/api/v1/discover/facets\`
- Fiche: \`GET ${o}/api/v1/@<createur>/<fiche>\`
- Bibliographie exportable: \`GET ${o}/api/v1/@<createur>/<fiche>/export?format=<json|csv|bibtex|ris|csl|apa>\`
- Schema complet: [OpenAPI](${o}/api/v1/openapi.json)
- Serveur MCP (lecture seule, sans authentification): \`${MCP_URL}\`

## Citer une fiche

L'adresse canonique d'une fiche est \`${o}/@<createur>/<fiche>\`. Elle est stable.
Chaque source y porte son URL d'origine, son archive Wayback et, le cas echeant,
son statut de retractation.
`;

  return new Response(body, {
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'public, max-age=3600',
    },
  });
};
