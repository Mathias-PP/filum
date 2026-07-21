export interface User {
  id: string;
  username: string;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  public_key: string;
  is_verified: boolean;
}

export type Visibility = 'public' | 'private';

export interface Card {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  content_url: string | null;
  platform: Platform;
  content_type: ContentType;
  status: CardStatus;
  is_seed: boolean;
  visibility: Visibility;
  published_at: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface CardDetail extends Card {
  creator: CreatorInfo;
  sources: Source[];
  stats: CardStats;
}

export interface CreatorInfo {
  slug: string;
  display_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  public_key: string;
}

export interface CardStats {
  total_sources: number;
  chercheur: number;
  media: number;
  institution_publique: number;
  individu: number;
  archived_count: number;
  all_archived: boolean;
}

export interface CardCreate {
  slug: string;
  title: string;
  description?: string;
  content_url?: string;
  platform: Platform;
  content_type: ContentType;
  /**
   * Fiche « seed » = créée pour un contenu dont je ne suis pas l'auteur.
   * L'auteur réel pourra la revendiquer via /cards/{id}/claim-requests.
   */
  is_seed?: boolean;
  /**
   * `public` (default) : visible par tout le monde une fois publiée.
   * `private` : visible uniquement par l'owner connecté (404 pour les autres).
   */
  visibility?: Visibility;
}

export interface SourceExcerpt {
  id: string;
  position: number;
  text: string;
  suggested_by_ai: boolean;
}

export interface SuggestedExcerpt {
  text: string;
  char_offset: number;
  context_before: string;
  context_after: string;
}

export interface ExcerptSuggestResponse {
  suggestions: SuggestedExcerpt[];
  page_text_length: number;
  llm_enabled: boolean;
}

export interface Source {
  id: string;
  url: string;
  title: string | null;
  authors: string | null;
  published_at: string | null;
  format: SourceFormat;
  category: SourceCategory;
  author_kind: AuthorKind;
  annotation: string | null;
  is_pivot: boolean;
  archive_status: ArchiveStatus;
  archive_url: string | null;
  archive_timestamp: string | null;
  parent_source_id: string | null;
  conflict_of_interest: string | null;
  citations_count: number | null;
  subscribers_count: number | null;
  views_count: number | null;
  impact_factor: number | null;
  excerpts: SourceExcerpt[];
  created_at: string;
  updated_at: string | null;
}

export interface SourceCreate {
  url: string;
  title?: string;
  authors?: string;
  published_at?: string;
  format: SourceFormat;
  category: SourceCategory;
  author_kind: AuthorKind;
  annotation?: string;
  is_pivot?: boolean;
  parent_source_id?: string | null;
  /**
   * Optional manual archive URL (e.g. an existing Wayback snapshot the user
   * already has). When set, the backend skips its background Wayback Save
   * Page Now task. When omitted or empty, the backend auto-archives.
   */
  archive_url?: string | null;
}

export type LinkedPlatform = 'youtube' | 'instagram' | 'x' | 'tiktok' | 'twitch' | 'site';

export interface LinkedAccount {
  id: string;
  platform: LinkedPlatform;
  url: string;
  handle: string | null;
  verified: boolean;
}

export interface LinkedAccountIn {
  platform: LinkedPlatform;
  url: string;
  handle?: string | null;
}

export interface PublicLinkedAccount {
  platform: LinkedPlatform;
  url: string;
  handle: string | null;
  verified: boolean;
}

export interface UserProfile {
  slug: string;
  display_name: string | null;
  description: string | null;
  avatar_url: string | null;
  public_key: string;
  linked_accounts: PublicLinkedAccount[];
  stats: {
    total_cards: number;
    total_sources: number;
    first_published_at: string | null;
    last_published_at: string | null;
  };
  cards: Array<{
    slug: string;
    title: string;
    published_at: string | null;
    total_sources: number;
  }>;
}

// VerificationResponse removed: card-level /verify endpoint was deprecated
// in ADR-019 (pivot to content attestations). The frontend now exclusively
// uses AttestationVerifyResponse for the current verification flow.

export interface Attestation {
  id: string;
  user_id: string;
  content_url: string;
  attested_at: string;
  canonical_hash: string;
  signature: string;
  created_at: string | null;
}

export interface AttestationVerifyResponse {
  valid: boolean;
  attestation_id: string | null;
  content_url: string | null;
  creator_slug: string | null;
  public_key: string | null;
  hash_algorithm: string;
  signature_algorithm: string;
  canonicalization: string;
  reason: string | null;
}

export type Platform = 'youtube' | 'podcast' | 'blog' | 'x' | 'bluesky' | 'other';
export type ContentType = 'video' | 'article' | 'post' | 'podcast' | 'other';
export type CardStatus = 'draft' | 'published' | 'archived';

export type SourceFormat = 'texte' | 'video' | 'image' | 'audio' | 'data';

export type SourceCategory =
  | 'article-scientifique'
  | 'preprint'
  | 'article-presse'
  | 'communique'
  | 'documentaire'
  | 'interview'
  | 'podcast'
  | 'blog'
  | 'post-social'
  | 'livre'
  | 'page-web'
  | 'notes';

export type AuthorKind =
  | 'chercheur'
  | 'media'
  | 'institution-publique'
  | 'gouvernement'
  | 'ecole'
  | 'laboratoire'
  | 'entreprise'
  | 'asso'
  | 'individu';

export type ArchiveStatus = 'pending' | 'archived' | 'failed';

// --- Imports (biblio parsing → draft de fiche) -----------------------------

export interface ImportedSourceDraft {
  url: string;
  title: string | null;
  authors: string | null;
  published_at: string | null;
  format: SourceFormat;
  category: SourceCategory;
  author_kind: AuthorKind;
  /**
   * Classification IA du type d'URL. Le badge est indicatif — l'user coche
   * ou décoche à sa guise, rien n'est jamais filtré automatiquement.
   */
  classification?: 'source' | 'promo' | 'social' | 'other' | null;
}

export interface ImportedCardDraft {
  title: string | null;
  description: string | null;
  content_url: string;
}

export interface UrlMetadataResponse {
  title: string | null;
  description: string | null;
}

export interface ImportFromUrlResponse {
  card: ImportedCardDraft;
  sources: ImportedSourceDraft[];
  skipped: number;
  references_section_found: boolean;
  /** ok = HTML récupéré, unreachable = timeout/DNS/4xx/5xx, not_html = PDF/image/JSON. */
  /** ok = page live scrapée. ok_via_wayback = snapshot Wayback utilisée (fetch direct bloqué). */
  fetch_status: 'ok' | 'ok_via_wayback' | 'unreachable' | 'not_html';
  /** URL de la snapshot Wayback utilisée si fetch_status === 'ok_via_wayback'. */
  wayback_url?: string | null;
}
