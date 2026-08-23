/** SvelteKit n'accepte que `load`, `ssr`, `prerender`… dans un `+page.ts`.
 * Tout le reste vit ici.
 */

export interface DiscoverResult {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  url: string;
  creator_slug: string;
  creator_name: string | null;
  card_kind: string;
  content_url: string | null;
  content_authors: string | null;
  /** Nuls sur une fiche sujet, qui ne documente aucun contenu existant. */
  content_type: string | null;
  platform: string | null;
  published_at: string | null;
  source_count: number;
}

export interface Facet {
  value: string;
  count: number;
}

export interface DiscoverFacets {
  total: number;
  card_kinds: Facet[];
  platforms: Facet[];
  content_types: Facet[];
  creators: Facet[];
}

export const PAGE_SIZE = 20;

/** Les filtres vivent dans l'URL, pas dans un state local.
 *
 * Une recherche se partage, se met en favori, et surtout se rend cote serveur :
 * un crawler qui suit un lien filtre doit voir les memes resultats que nous.
 */
export const FILTER_KEYS = [
  'q',
  'creator',
  'content_author',
  'card_kind',
  'platform',
  'content_type',
  'published_after',
  'published_before',
  'sort',
] as const;
