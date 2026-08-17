/**
 * Métadonnées de citation exposées dans le HTML des fiches publiques.
 *
 * Deux formats, deux rôles distincts, à ne surtout pas mélanger :
 *
 * - **Highwire** (`<meta name="citation_*">`) décrit *une seule* ressource par
 *   page — ici le contenu que la fiche documente. C'est ce que lit Google
 *   Scholar, qui exige au minimum titre + premier auteur + année.
 * - **COinS** (`<span class="Z3988" title="…">`) décrit *N* ressources dans le
 *   corps de la page — ici chaque source de la bibliographie. Le connecteur
 *   Zotero les détecte comme autant d'items sélectionnables.
 *
 * Ordre de résolution du connecteur Zotero :
 * translator spécifique > unAPI > COinS > DOI > Embedded Metadata.
 */

import type { CardDetail, Source, SourceCategory } from '$lib/api/types';

export interface MetaTag {
  name: string;
  content: string;
}

/** Une suite d'initiales (« A. », « D.S. », « J-P. », « JP ») et rien d'autre. */
const INITIALS_SHAPE = /^([A-ZÀ-Þ]\.?[-\s]?)+$/;

/**
 * Un fragment de nom qui n'est que des initiales.
 *
 * La forme seule ne suffit pas : « DUPONT » a la même forme qu'une suite
 * d'initiales. On exige donc un point, ou une longueur de deux caractères au
 * plus — sinon un nom de famille en capitales serait recollé au précédent.
 */
function isInitialsOnly(part: string): boolean {
  if (!INITIALS_SHAPE.test(part)) return false;
  return part.includes('.') || part.replace(/[-\s]/g, '').length <= 2;
}

/**
 * Découpe une chaîne d'auteurs libre en noms individuels.
 *
 * Philum stocke les auteurs en texte libre : il faut donc encaisser aussi bien
 * « Kang W., Hernández S. » que « Diamond, A.; Ling, D.S. » ou « X and Y ».
 * Le point délicat est la virgule, qui sépare tantôt deux auteurs, tantôt le
 * nom de famille de ses initiales. Heuristique : après découpe sur la virgule,
 * un fragment qui n'est *que* des initiales est recollé au fragment précédent.
 */
export function splitAuthors(raw: string | null | undefined): string[] {
  if (!raw) return [];
  const trimmed = raw.trim();
  if (!trimmed) return [];

  // Le point-virgule est non ambigu : s'il est présent, il fait autorité.
  if (trimmed.includes(';')) {
    return trimmed
      .split(';')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const parts = trimmed
    .split(/,| and | et /i)
    .map((s) => s.trim())
    .filter(Boolean);

  const merged: string[] = [];
  for (const part of parts) {
    if (merged.length > 0 && isInitialsOnly(part)) {
      merged[merged.length - 1] = `${merged[merged.length - 1]}, ${part}`;
    } else {
      merged.push(part);
    }
  }
  return merged;
}

/** Date au format Highwire `YYYY/MM/DD`, ou `YYYY` si le jour est inconnu. */
export function highwireDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  // Testé avant tout parsing : `new Date('1984')` réussit et rendrait
  // « 1984/01/01 », soit un jour et un mois inventés de toutes pièces.
  const yearOnly = /^(\d{4})$/.exec(iso.trim());
  if (yearOnly) return yearOnly[1];

  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}/${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())}`;
}

/** Année seule, utilisée par COinS (`rft.date`) quand rien de plus fin n'existe. */
export function year(iso: string | null | undefined): string | null {
  const hw = highwireDate(iso);
  if (!hw) return null;
  return hw.slice(0, 4);
}

/**
 * Tags Highwire décrivant le contenu documenté par la fiche.
 *
 * Les auteurs sont ceux du **contenu**, pas ceux de la fiche : publier une
 * fiche n'est pas signer ce qu'elle documente. À défaut d'auteurs déclarés, on
 * ne retombe sur le créateur QUE quand il documente son propre contenu
 * (`is_seed === false`) : autrement, le créateur d'une fiche seed apparaîtrait
 * comme auteur d'un article qu'il n'a pas écrit, aussi bien dans Zotero que
 * dans Google Scholar. Mieux vaut une page invisible de Scholar qu'une page
 * qui lui ment sur l'auteur.
 */
export function cardHighwireTags(card: CardDetail, publicUrl: string): MetaTag[] {
  const tags: MetaTag[] = [{ name: 'citation_title', content: card.title }];

  const authors = splitAuthors(card.content_authors);
  if (authors.length === 0 && !card.is_seed) {
    authors.push(card.creator.display_name ?? card.creator.slug);
  }
  for (const author of authors) {
    tags.push({ name: 'citation_author', content: author });
  }

  const date = highwireDate(card.published_at ?? card.created_at);
  if (date) tags.push({ name: 'citation_publication_date', content: date });

  tags.push({ name: 'citation_public_url', content: publicUrl });
  if (card.content_url) {
    tags.push({ name: 'citation_abstract_html_url', content: card.content_url });
  }
  return tags;
}

/** Catégories pour lesquelles le contexte OpenURL « journal » est le bon. */
const JOURNAL_CATEGORIES: ReadonlySet<SourceCategory> = new Set<SourceCategory>([
  'article-scientifique',
  'preprint',
  'article-presse',
  'communique',
]);

/**
 * Valeur de l'attribut `title` d'un span COinS pour une source.
 *
 * Trois contextes OpenURL selon la nature de la source : `journal` pour ce qui
 * est article, `book` pour les livres, et Dublin Core pour tout le reste —
 * vidéos, podcasts, pages web. Le contexte `dc` est ce qui rend le dispositif
 * agnostique : sans lui, une source YouTube devrait mentir sur son genre.
 */
export function sourceCoins(source: Source): string {
  const params: [string, string][] = [['ctx_ver', 'Z39.88-2004']];
  const title = source.title?.trim() || source.url;
  const isBook = source.category === 'livre';
  const isJournal = JOURNAL_CATEGORIES.has(source.category);

  if (isJournal) {
    params.push(['rft_val_fmt', 'info:ofi/fmt:kev:mtx:journal']);
    params.push(['rft.genre', 'article']);
    params.push(['rft.atitle', title]);
    if (source.journal) params.push(['rft.jtitle', source.journal]);
    if (source.volume) params.push(['rft.volume', source.volume]);
    if (source.pages) params.push(['rft.pages', source.pages]);
  } else if (isBook) {
    params.push(['rft_val_fmt', 'info:ofi/fmt:kev:mtx:book']);
    params.push(['rft.genre', 'book']);
    params.push(['rft.btitle', title]);
    if (source.publisher) params.push(['rft.pub', source.publisher]);
  } else {
    params.push(['rft_val_fmt', 'info:ofi/fmt:kev:mtx:dc']);
    params.push(['rft.type', 'webpage']);
    params.push(['rft.title', title]);
    if (source.publisher) params.push(['rft.publisher', source.publisher]);
  }

  const d = year(source.published_at);
  if (d) params.push(['rft.date', d]);

  for (const author of splitAuthors(source.authors)) {
    params.push(['rft.au', author]);
  }

  if (source.doi) params.push(['rft_id', `info:doi/${source.doi}`]);
  if (source.url) params.push(['rft_id', source.url]);

  return params.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
}
