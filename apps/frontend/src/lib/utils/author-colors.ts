import type { AuthorKind, SourceCategory, SourceFormat } from '$lib/api';

export interface AuthorColor {
  label: string;
  fill: string;
  stroke: string;
  text: string;
  bgClass: string;
}

/**
 * Palette by author_kind — drives the graph node colors (ADR-020).
 * The choice of "who said it?" as the primary epistemic signal means the
 * graph color directly communicates the source's authority origin.
 */
export const AUTHOR_COLORS: Record<AuthorKind, AuthorColor> = {
  chercheur: {
    label: 'Chercheur·euse(s)',
    fill: '#C0DD97',
    stroke: '#639922',
    text: '#173404',
    bgClass: 'bg-emerald-100 text-emerald-800',
  },
  media: {
    label: 'Média',
    fill: '#FAC775',
    stroke: '#EF9F27',
    text: '#412402',
    bgClass: 'bg-amber-100 text-amber-800',
  },
  'institution-publique': {
    label: 'Institution publique',
    fill: '#B5D4F4',
    stroke: '#378ADD',
    text: '#042C53',
    bgClass: 'bg-blue-100 text-blue-800',
  },
  gouvernement: {
    label: 'Gouvernement',
    fill: '#F2A7BE',
    stroke: '#D4456E',
    text: '#4A0E21',
    bgClass: 'bg-pink-100 text-pink-800',
  },
  ecole: {
    label: 'École',
    fill: '#A7E8D9',
    stroke: '#2DAF8F',
    text: '#08382C',
    bgClass: 'bg-teal-100 text-teal-800',
  },
  laboratoire: {
    label: 'Laboratoire',
    fill: '#BAE6FD',
    stroke: '#0EA5E9',
    text: '#0C4A6E',
    bgClass: 'bg-sky-100 text-sky-800',
  },
  entreprise: {
    label: 'Entreprise',
    fill: '#CBD5E1',
    stroke: '#64748B',
    text: '#1E293B',
    bgClass: 'bg-slate-200 text-slate-800',
  },
  asso: {
    label: 'Association',
    fill: '#FDE68A',
    stroke: '#CA8A04',
    text: '#422006',
    bgClass: 'bg-yellow-100 text-yellow-800',
  },
  individu: {
    label: 'Individu(s)',
    fill: '#CECBF6',
    stroke: '#7F77DD',
    text: '#26215C',
    bgClass: 'bg-purple-100 text-purple-800',
  },
};

/** Axe de couleur du graphe — les 3 axes de la taxonomie ADR-020. */
export type ColorMode = 'author_kind' | 'format' | 'category';

export interface NodeColor {
  label: string;
  fill: string;
  stroke: string;
}

export const FORMAT_COLORS: Record<SourceFormat, NodeColor> = {
  texte: { label: 'Texte', fill: '#C7D2FE', stroke: '#4F46E5' },
  video: { label: 'Vidéo', fill: '#FECACA', stroke: '#DC2626' },
  image: { label: 'Image', fill: '#FDE68A', stroke: '#CA8A04' },
  audio: { label: 'Audio', fill: '#A7F3D0', stroke: '#059669' },
  data: { label: 'Données', fill: '#BAE6FD', stroke: '#0284C7' },
};

export const CATEGORY_COLORS: Record<SourceCategory, NodeColor> = {
  'article-scientifique': { label: 'Article scientifique', fill: '#C0DD97', stroke: '#639922' },
  preprint: { label: 'Préprint', fill: '#D9F99D', stroke: '#65A30D' },
  'article-presse': { label: 'Article de presse', fill: '#FAC775', stroke: '#EF9F27' },
  communique: { label: 'Communiqué', fill: '#FED7AA', stroke: '#EA580C' },
  documentaire: { label: 'Documentaire', fill: '#F2A7BE', stroke: '#D4456E' },
  interview: { label: 'Interview', fill: '#FBCFE8', stroke: '#DB2777' },
  podcast: { label: 'Podcast', fill: '#CECBF6', stroke: '#7F77DD' },
  blog: { label: 'Blog', fill: '#DDD6FE', stroke: '#7C3AED' },
  'post-social': { label: 'Post réseaux', fill: '#BAE6FD', stroke: '#0EA5E9' },
  livre: { label: 'Livre', fill: '#B5D4F4', stroke: '#378ADD' },
  'page-web': { label: 'Page web', fill: '#CBD5E1', stroke: '#64748B' },
  notes: { label: 'Notes', fill: '#E7E5E4', stroke: '#78716C' },
};

export function sourceColor(
  s: { author_kind: AuthorKind; format: SourceFormat; category: SourceCategory },
  mode: ColorMode
): NodeColor {
  if (mode === 'format') return FORMAT_COLORS[s.format];
  if (mode === 'category') return CATEGORY_COLORS[s.category];
  const c = AUTHOR_COLORS[s.author_kind];
  return { label: c.label, fill: c.fill, stroke: c.stroke };
}

const FORMAT_LABELS: Record<SourceFormat, string> = {
  texte: 'Texte',
  video: 'Vidéo',
  image: 'Image',
  audio: 'Audio',
  data: 'Données',
};

const CATEGORY_LABELS: Record<SourceCategory, string> = {
  'article-scientifique': 'Article scientifique',
  preprint: 'Préprint',
  'article-presse': 'Article de presse',
  communique: 'Communiqué',
  documentaire: 'Documentaire',
  interview: 'Interview',
  podcast: 'Podcast',
  blog: 'Blog',
  'post-social': 'Post réseaux',
  livre: 'Livre',
  'page-web': 'Page web',
  notes: 'Notes',
};

export function formatLabel(format: SourceFormat): string {
  return FORMAT_LABELS[format];
}

export function categoryLabel(category: SourceCategory): string {
  return CATEGORY_LABELS[category];
}

export function authorLabel(authorKind: AuthorKind): string {
  return AUTHOR_COLORS[authorKind].label;
}
