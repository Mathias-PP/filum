export interface User {
  id: string
  username: string
  display_name: string | null
  bio: string | null
  avatar_url: string | null
  public_key: string
  is_verified: boolean
}

export interface Card {
  id: string
  slug: string
  title: string
  description: string | null
  content_url: string | null
  platform: Platform
  content_type: ContentType
  status: CardStatus
  canonical_hash: string | null
  signature: string | null
  signed_at: string | null
  published_at: string | null
  created_at: string
  updated_at: string | null
}

export interface CardDetail extends Card {
  creator: CreatorInfo
  sources: Source[]
  stats: CardStats
}

export interface CreatorInfo {
  slug: string
  display_name: string | null
  bio: string | null
  avatar_url: string | null
  public_key: string
}

export interface CardStats {
  total_sources: number
  peer_reviewed: number
  institutional: number
  press: number
  original: number
  all_archived: boolean
}

export interface CardCreate {
  slug: string
  title: string
  description?: string
  content_url?: string
  platform: Platform
  content_type: ContentType
}

export interface Source {
  id: string
  url: string
  title: string | null
  authors: string | null
  published_at: string | null
  source_type: SourceType
  authority_level: AuthorityLevel
  annotation: string | null
  is_pivot: boolean
  archive_status: ArchiveStatus
  archive_url: string | null
  archive_timestamp: string | null
  created_at: string
  updated_at: string | null
}

export interface SourceCreate {
  url: string
  title?: string
  authors?: string
  published_at?: string
  source_type: SourceType
  annotation?: string
  is_pivot?: boolean
}

export interface UserProfile {
  slug: string
  display_name: string | null
  description: string | null
  avatar_url: string | null
  public_key: string
  stats: {
    total_cards: number
    total_sources: number
    first_published_at: string | null
    last_published_at: string | null
  }
  cards: Array<{
    slug: string
    title: string
    published_at: string | null
    total_sources: number
  }>
}

export interface VerificationResponse {
  valid: boolean
  creator_slug: string | null
  card_slug: string | null
  content_hash: string | null
  signature: string | null
  signed_at: string | null
  details: {
    hash_algorithm: string
    signature_algorithm: string
    canonicalization: string
  } | null
  reason: string | null
}

export type Platform = 'youtube' | 'podcast' | 'blog' | 'x' | 'bluesky' | 'other'
export type ContentType = 'video' | 'article' | 'post' | 'podcast' | 'other'
export type CardStatus = 'draft' | 'published' | 'archived'
export type SourceType = 'peer-reviewed' | 'institutional' | 'press' | 'original'
export type AuthorityLevel = 'high' | 'medium' | 'low'
export type ArchiveStatus = 'pending' | 'archived' | 'failed'
