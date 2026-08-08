import type { RetractionStatus } from '$lib/api/types';

export interface RetractionBadge {
  label: string;
  help: string;
  /** Classes Tailwind du badge. */
  className: string;
  /** Un avis a lire, par opposition a une simple absence d'avis. */
  isNotice: boolean;
}

/**
 * Quatre etats, quatre affirmations differentes -- et un cinquieme, `null`,
 * qui n'affirme rien du tout.
 *
 * `none` est une information positive et datee : Crossref connait ce DOI et
 * ne signale rien. `unverifiable` dit l'inverse : la question n'a pas pu etre
 * posee. Les afficher pareil reviendrait a rassurer le lecteur sans preuve.
 *
 * Les trois avis portent un fond colore, clair dans les deux themes : la
 * nuance y est figee a raison, elle ne s'inverse pas. Les deux non-avis sont
 * du texte nu pose sur la surface de la page, donc des jetons — `text-neutral-*`
 * y laissait la lisibilite dependre du theme.
 */
const BADGES: Record<RetractionStatus, RetractionBadge> = {
  retracted: {
    label: 'Rétracté',
    help: 'Cet article a été retiré de la littérature scientifique.',
    className: 'bg-red-100 text-red-800 ring-1 ring-red-300',
    isNotice: true,
  },
  concern: {
    label: 'Mise en garde',
    help: 'L’éditeur a publié une réserve sur cet article.',
    className: 'bg-amber-100 text-amber-900 ring-1 ring-amber-300',
    isNotice: true,
  },
  corrected: {
    label: 'Corrigé',
    help: 'Un erratum ou une correction a été publié après l’article.',
    className: 'bg-blue-100 text-blue-800 ring-1 ring-blue-300',
    isNotice: true,
  },
  none: {
    label: 'Aucun avis',
    help: 'Crossref connaît cette référence et ne signale ni rétractation ni correction.',
    className: 'text-ink-tertiary',
    isNotice: false,
  },
  unverifiable: {
    label: 'Non vérifiable',
    help: 'Sans DOI connu de Crossref, l’existence d’un avis de rétractation ne peut pas être vérifiée.',
    className: 'text-ink-placeholder',
    isNotice: false,
  },
};

export function retractionBadge(status: string | null | undefined): RetractionBadge | null {
  if (!status) return null;
  return BADGES[status as RetractionStatus] ?? null;
}

/** Une affirmation non datée est une promesse que rien ne soutient. */
export function retractionTitle(
  status: string | null | undefined,
  checkedAt: string | null | undefined
): string {
  const badge = retractionBadge(status);
  if (!badge) return '';
  if (!checkedAt) return badge.help;
  const d = new Date(checkedAt);
  if (Number.isNaN(d.getTime())) return badge.help;
  return `${badge.help} (vérifié le ${d.toLocaleDateString('fr-FR')})`;
}

/** DOI de l'avis -> URL lisible, pour que le lecteur puisse aller le lire. */
export function noticeUrl(doi: string | null | undefined): string | null {
  const cleaned = (doi ?? '').trim();
  return cleaned ? `https://doi.org/${cleaned}` : null;
}
