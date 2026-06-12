/**
 * Transitional adapter: normalize backend payloads that still expose the
 * legacy `source_type` / `authority_level` fields (and the legacy
 * `CardStats` shape with `peer_reviewed` / `institutional` / ...) to the
 * 3-axis taxonomy introduced by ADR-020.
 *
 * Once Railway has redeployed past commit ca2a6f6 (PR #44 merge), the API
 * returns the new shape directly and these adapters become no-ops.
 *
 * Safe to keep for a few days as a safety net against backend/frontend
 * deployment ordering. Remove when the prod backend has been on the new
 * code path for at least 1 week and no requests for old shape are seen.
 *
 * Same mapping as Alembic migration 007_taxonomy backfill.
 */

import type {
  AuthorKind,
  CardDetail,
  CardStats,
  Source,
  SourceCategory,
  SourceFormat,
} from './types';

type LegacySourceType =
  | 'peer-reviewed'
  | 'institutional'
  | 'press'
  | 'video'
  | 'image'
  | 'original';

interface LegacySourceFields {
  source_type?: LegacySourceType;
  authority_level?: string;
}

const TAXONOMY_MAP: Record<
  LegacySourceType,
  { format: SourceFormat; category: SourceCategory; author_kind: AuthorKind }
> = {
  'peer-reviewed': {
    format: 'texte',
    category: 'article-scientifique',
    author_kind: 'chercheur',
  },
  institutional: { format: 'texte', category: 'communique', author_kind: 'institution-publique' },
  press: { format: 'texte', category: 'article-presse', author_kind: 'media' },
  video: { format: 'video', category: 'documentaire', author_kind: 'media' },
  image: { format: 'image', category: 'page-web', author_kind: 'individu' },
  original: { format: 'texte', category: 'notes', author_kind: 'individu' },
};

export function normalizeSource(raw: Source & LegacySourceFields): Source {
  if (raw.format && raw.category && raw.author_kind) {
    return raw;
  }
  const legacyType = raw.source_type;
  const fallback = legacyType ? TAXONOMY_MAP[legacyType] : null;
  return {
    ...raw,
    format: raw.format ?? fallback?.format ?? 'texte',
    category: raw.category ?? fallback?.category ?? 'page-web',
    author_kind: raw.author_kind ?? fallback?.author_kind ?? 'individu',
  };
}

interface LegacyCardStats {
  total_sources: number;
  peer_reviewed?: number;
  institutional?: number;
  press?: number;
  video?: number;
  image?: number;
  original?: number;
  all_archived: boolean;
}

export function normalizeStats(raw: CardStats & LegacyCardStats): CardStats {
  if (typeof raw.chercheur === 'number') {
    return {
      ...raw,
      archived_count: raw.archived_count ?? (raw.all_archived ? raw.total_sources : 0),
    };
  }
  return {
    total_sources: raw.total_sources,
    chercheur: raw.peer_reviewed ?? 0,
    media: (raw.press ?? 0) + (raw.video ?? 0),
    institution_publique: raw.institutional ?? 0,
    individu: (raw.original ?? 0) + (raw.image ?? 0),
    archived_count: raw.all_archived ? raw.total_sources : 0,
    all_archived: raw.all_archived,
  };
}

export function normalizeCardDetail(raw: CardDetail): CardDetail {
  return {
    ...raw,
    sources: raw.sources.map((s) => normalizeSource(s as Source & LegacySourceFields)),
    stats: normalizeStats(raw.stats as CardStats & LegacyCardStats),
  };
}
