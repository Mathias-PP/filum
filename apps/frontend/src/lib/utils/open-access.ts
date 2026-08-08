import type { OpenAccessStatus } from '$lib/api/types';

export interface OpenAccessBadge {
  label: string;
  help: string;
  /** Classes Tailwind du badge. */
  className: string;
  /** Une version gratuite existe, par opposition à un accès fermé ou inconnu. */
  isFree: boolean;
}

/**
 * Sept états, sept affirmations différentes — et un huitième, `null`, qui
 * n'affirme rien.
 *
 * `closed` est une information positive et datée : OpenAlex connaît cette
 * référence et ne trouve aucune version gratuite. `unverifiable` dit l'inverse :
 * la question n'a pas pu être posée. Les afficher pareil pourrait détourner le
 * lecteur d'une version libre qui existe.
 *
 * Les routes (or, vert, hybride…) sont nommées séparément parce qu'elles ne
 * promettent pas la même chose : une version « verte » est un dépôt d'auteur,
 * qui peut différer de la version publiée.
 */
const BADGES: Record<OpenAccessStatus, OpenAccessBadge> = {
  diamond: {
    label: 'Accès libre',
    help: 'Revue intégralement en libre accès, sans frais de publication.',
    className: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300',
    isFree: true,
  },
  gold: {
    label: 'Accès libre',
    help: 'Publié en libre accès par la revue.',
    className: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300',
    isFree: true,
  },
  green: {
    label: 'Version déposée',
    help: 'Une version est déposée en archive ouverte. Elle peut différer de la version publiée.',
    className: 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200',
    isFree: true,
  },
  hybrid: {
    label: 'Accès libre',
    help: 'Article libre dans une revue par ailleurs payante.',
    className: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-300',
    isFree: true,
  },
  bronze: {
    label: 'Lisible gratuitement',
    help: 'Lisible sans payer chez l’éditeur, mais sans licence de réutilisation — l’accès peut être retiré.',
    className: 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200',
    isFree: true,
  },
  open: {
    label: 'Accès libre',
    help: 'Une version gratuite existe, par une voie qu’OpenAlex ne nomme pas ici.',
    className: 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200',
    isFree: true,
  },
  closed: {
    label: 'Accès payant',
    help: 'OpenAlex connaît cette référence et ne trouve aucune version gratuite.',
    className: 'text-ink-tertiary',
    isFree: false,
  },
  unverifiable: {
    label: 'Accès non vérifié',
    help: 'Sans DOI connu d’OpenAlex, l’existence d’une version gratuite ne peut pas être vérifiée.',
    className: 'text-ink-placeholder',
    isFree: false,
  },
};

export function openAccessBadge(status: string | null | undefined): OpenAccessBadge | null {
  if (!status) return null;
  return BADGES[status as OpenAccessStatus] ?? null;
}

/** Une affirmation non datée est une promesse que rien ne soutient. */
export function openAccessTitle(
  status: string | null | undefined,
  checkedAt: string | null | undefined
): string {
  const badge = openAccessBadge(status);
  if (!badge) return '';
  if (!checkedAt) return badge.help;
  const d = new Date(checkedAt);
  if (Number.isNaN(d.getTime())) return badge.help;
  return `${badge.help} (vérifié le ${d.toLocaleDateString('fr-FR')})`;
}

/**
 * Lien à ouvrir pour lire gratuitement, ou `null`.
 *
 * Annoncer un accès libre sans lien reste honnête, mais un bouton qui ne mène
 * nulle part ne l'est pas : il n'apparaît que si l'URL existe.
 */
export function freeReadUrl(
  status: string | null | undefined,
  url: string | null | undefined
): string | null {
  const badge = openAccessBadge(status);
  if (!badge?.isFree) return null;
  const cleaned = (url ?? '').trim();
  return cleaned.startsWith('http') ? cleaned : null;
}

/** Licence déclarée, en forme lisible (« CC BY »). `null` si inconnue. */
export function licenseLabel(license: string | null | undefined): string | null {
  const cleaned = (license ?? '').trim();
  if (!cleaned) return null;
  return cleaned.startsWith('cc-') ? cleaned.replace(/-/g, ' ').toUpperCase() : cleaned;
}
