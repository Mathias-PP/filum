/**
 * Colonnes de comparaison d'une bibliographie, sans un seul appel à un modèle.
 *
 * L'outil de référence du marché (SciSpace) affiche `N/A` dans une cellule
 * aussi bien quand l'information manque que quand le document est inaccessible.
 * L'absence de preuve y devient indiscernable de la preuve d'absence, et le
 * lecteur ne peut plus distinguer « on n'a pas trouvé » de « il n'y a rien ».
 *
 * Ici, une cellule vide n'existe pas. Une case sans valeur dit *pourquoi* elle
 * n'en a pas, et les quatre raisons ne se confondent jamais :
 *
 * - **non renseignée** — le champ n'a jamais été rempli ; rien n'a été cherché ;
 * - **sans objet**     — la question ne se pose pas pour ce type de source ;
 * - **non vérifié**    — le contrôle machine n'a jamais tourné (`null`) ;
 * - **non vérifiable** — le contrôle a été tenté et ne peut pas conclure.
 *
 * C'est la même règle que celle qui gouverne `retraction_status` et
 * `oa_status` : trois états, jamais deux.
 */

import type { Source, SourceCategory } from '$lib/api/types';
import { categoryLabel } from '$lib/utils/author-colors';
import { openAccessBadge, openAccessTitle } from '$lib/utils/open-access';
import { montrerAvisRetractation, retractionBadge, retractionTitle } from '$lib/utils/retraction';
import { stanceStyle } from '$lib/utils/stance';

export type CellTone =
  /** Une valeur factuelle, sans jugement. */
  | 'neutral'
  /** Une bonne nouvelle vérifiée (accès libre, aucun avis de rétractation). */
  | 'positive'
  /** Une réserve publiée sur la source. */
  | 'warning'
  /** Un retrait de la littérature. */
  | 'danger'
  /** Pas de valeur — la cellule dit pourquoi. */
  | 'absent';

export interface CompareCell {
  /** Ce qui s'affiche. Jamais vide : une absence se formule. */
  label: string;
  /** Infobulle : ce que la cellule affirme exactement, et depuis quand. */
  help: string;
  tone: CellTone;
  /**
   * Clé de tri. `null` pour toute cellule `absent` : une absence n'a pas de
   * rang, elle se range en fin de liste quel que soit le sens du tri.
   */
  sortKey: string | number | null;
}

export type CompareColumnId = 'year' | 'category' | 'venue' | 'access' | 'retraction' | 'stance';

export interface CompareColumn {
  id: CompareColumnId;
  label: string;
  /** Ce que la colonne compare, et d'où vient la donnée. */
  hint: string;
}

export const COMPARE_COLUMNS: CompareColumn[] = [
  { id: 'year', label: 'Année', hint: 'Année de publication, telle que renseignée sur la fiche.' },
  {
    id: 'category',
    label: 'Type',
    hint: 'Nature de la source, déclarée par l’auteur de la fiche.',
  },
  { id: 'venue', label: 'Revue ou éditeur', hint: 'Revue pour un article, éditeur pour un livre.' },
  { id: 'access', label: 'Accès', hint: 'Existence d’une version gratuite, d’après OpenAlex.' },
  {
    id: 'retraction',
    label: 'Rétraction',
    hint: 'Avis de rétractation ou de correction, d’après Crossref.',
  },
  {
    id: 'stance',
    label: 'Position',
    hint: 'Rapport déclaré entre le propos du contenu et ce que dit la source.',
  },
];

function absent(label: string, help: string): CompareCell {
  return { label, help, tone: 'absent', sortKey: null };
}

/**
 * Catégories pour lesquelles une revue ou un éditeur est attendu.
 *
 * Ailleurs — une vidéo, un fil social, une page web — la case n'est pas vide
 * par oubli : la notion n'existe pas. Dire « non renseignée » y serait un
 * reproche adressé à l'auteur de la fiche pour une information qui n'existe pas.
 */
const VENUE_EXPECTED: ReadonlySet<SourceCategory> = new Set<SourceCategory>([
  'article-scientifique',
  'preprint',
  'article-presse',
  'livre',
  'communique',
]);

function yearCell(source: Source): CompareCell {
  if (!source.published_at) {
    return absent(
      'non renseignée',
      'Aucune date de publication n’est enregistrée pour cette source.'
    );
  }
  const year = new Date(source.published_at).getFullYear();
  if (Number.isNaN(year)) {
    return absent('date illisible', 'La date enregistrée n’a pas pu être interprétée.');
  }
  return {
    label: String(year),
    help: `Publiée en ${year}.`,
    tone: 'neutral',
    sortKey: year,
  };
}

function categoryCell(source: Source): CompareCell {
  const label = categoryLabel(source.category);
  return {
    label,
    help: `Type déclaré par l’auteur de la fiche : ${label.toLowerCase()}.`,
    tone: 'neutral',
    sortKey: label.toLowerCase(),
  };
}

function venueCell(source: Source): CompareCell {
  // `??` ne suffit pas : un import BibTeX ou Crossref produit couramment un
  // `journal` vide plutôt qu'absent, et l'éditeur serait alors masqué par une
  // chaîne vide qui n'est pourtant `null` ni `undefined`.
  const journal = (source.journal ?? '').trim();
  const venue = journal || (source.publisher ?? '').trim();
  if (venue) {
    return {
      label: venue,
      help: journal ? `Publiée dans ${venue}.` : `Éditée par ${venue}.`,
      tone: 'neutral',
      sortKey: venue.toLowerCase(),
    };
  }
  if (!VENUE_EXPECTED.has(source.category)) {
    return absent(
      'sans objet',
      `Une source de type « ${categoryLabel(source.category).toLowerCase()} » n’a ni revue ni éditeur.`
    );
  }
  return absent('non renseignée', 'Aucune revue ni éditeur n’est enregistré pour cette source.');
}

function accessCell(source: Source): CompareCell {
  const badge = openAccessBadge(source.oa_status);
  if (!badge) {
    return absent(
      'non vérifié',
      'L’existence d’une version gratuite n’a jamais été vérifiée pour cette source.'
    );
  }
  const help = openAccessTitle(source.oa_status, source.oa_checked_at);
  if (source.oa_status === 'unverifiable') {
    return absent('non vérifiable', help);
  }
  return {
    label: badge.label,
    help,
    tone: badge.isFree ? 'positive' : 'neutral',
    // Une version gratuite d'abord : c'est la seule chose qui change ce que le
    // lecteur peut faire de la référence.
    sortKey: badge.isFree ? 0 : 1,
  };
}

function retractionCell(source: Source): CompareCell {
  const badge = retractionBadge(source.retraction_status);
  if (!badge) {
    return absent(
      'non vérifié',
      'Aucun contrôle de rétractation n’a jamais été fait sur cette source.'
    );
  }
  const help = retractionTitle(source.retraction_status, source.retraction_checked_at);
  if (source.retraction_status === 'unverifiable') {
    // Une revue rétracte un article, pas un podcast ni une page de
    // laboratoire. Dire « non vérifiable » là où rien n'est rétractable
    // laisse croire à un contrôle qui aurait échoué.
    if (!montrerAvisRetractation(source.retraction_status, source.category)) {
      return absent('sans objet', 'La rétractation ne concerne que la littérature scientifique.');
    }
    return absent('non vérifiable', help);
  }
  const tone: CellTone =
    source.retraction_status === 'retracted'
      ? 'danger'
      : source.retraction_status === 'none'
        ? 'positive'
        : 'warning';
  // Le plus grave en tête : c'est ce qu'on trie une bibliographie pour trouver.
  const rank: Record<string, number> = { retracted: 0, concern: 1, corrected: 2, none: 3 };
  return { label: badge.label, help, tone, sortKey: rank[source.retraction_status ?? ''] ?? 4 };
}

function stanceCell(source: Source): CompareCell {
  const style = stanceStyle(source.stance);
  if (!style) {
    // Un silence n'est pas « mentionne » : l'auteur n'a rien affirmé, et lui
    // prêter la position la plus tiède serait mettre un mot dans sa bouche.
    return absent(
      'non déclarée',
      'L’auteur de la fiche n’a pas déclaré de position pour cette source.'
    );
  }
  const rank: Record<string, number> = {
    'nuance-contredit': 0,
    appuie: 1,
    contexte: 2,
    mentionne: 3,
  };
  return {
    label: style.label,
    help: `Déclaré par l’auteur de la fiche — ${style.help}`,
    tone: source.stance === 'nuance-contredit' ? 'warning' : 'neutral',
    sortKey: rank[source.stance ?? ''] ?? 4,
  };
}

const BUILDERS: Record<CompareColumnId, (source: Source) => CompareCell> = {
  year: yearCell,
  category: categoryCell,
  venue: venueCell,
  access: accessCell,
  retraction: retractionCell,
  stance: stanceCell,
};

export function compareCell(source: Source, column: CompareColumnId): CompareCell {
  return BUILDERS[column](source);
}

/**
 * Trie les sources selon une colonne, absences toujours en queue.
 *
 * Le tri ne retire jamais une ligne : comparer une bibliographie suppose de la
 * voir entière, y compris ce qu'on ne sait pas d'elle.
 */
export function sortByColumn(
  sources: Source[],
  column: CompareColumnId,
  direction: 'asc' | 'desc'
): Source[] {
  const factor = direction === 'asc' ? 1 : -1;
  return [...sources]
    .map((source, index) => ({ source, index, key: compareCell(source, column).sortKey }))
    .sort((a, b) => {
      if (a.key === null && b.key === null) return a.index - b.index;
      if (a.key === null) return 1;
      if (b.key === null) return -1;
      if (a.key === b.key) return a.index - b.index;
      return (a.key < b.key ? -1 : 1) * factor;
    })
    .map((entry) => entry.source);
}
