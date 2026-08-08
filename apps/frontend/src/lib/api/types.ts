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
  /**
   * Auteurs du contenu documenté — pas ceux de la fiche.
   *
   * Publier une fiche n'est pas signer ce qu'elle documente. Sans ce champ,
   * les auteurs ne vivaient que dans la bibliographie des fiches citantes, et
   * une fiche que personne ne cite ne pouvait s'annoncer que sous le nom de
   * son créateur Philum.
   */
  content_authors: string | null;
  platform: Platform;
  content_type: ContentType;
  status: CardStatus;
  is_seed: boolean;
  visibility: Visibility;
  published_at: string | null;
  created_at: string;
  updated_at: string | null;
  /** Referencement du contenu documente. null = non declare. */
  format: SourceFormat | null;
  category: SourceCategory | null;
  author_kind: AuthorKind | null;
}

export interface CardDetail extends Card {
  creator: CreatorInfo;
  sources: Source[];
  stats: CardStats;
}

/** Fiche sélectionnable comme parent dans le picker de méta-fiches. */
export interface CardSearchResult {
  id: string;
  title: string;
  slug: string;
  creator_slug: string;
  status: CardStatus;
  /** Fiche de l'utilisateur courant : elle peut être un brouillon. */
  is_own: boolean;
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
  /** Sources ayant une URL à archiver — dénominateur du compteur. Les
   *  références sans lien n'ont rien à archiver et en sont exclues. */
  archivable_count: number;
  all_archived: boolean;
}

export interface CardCreate {
  slug: string;
  title: string;
  description?: string;
  content_url?: string;
  content_authors?: string;
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
  /** Referencement du contenu documente. null = effacer la valeur. */
  format?: SourceFormat | null;
  category?: SourceCategory | null;
  author_kind?: AuthorKind | null;
}

export interface SourceExcerpt {
  id: string;
  position: number;
  text: string;
  /** Intitulé de repérage, facultatif : dix extraits empilés ne se distinguent pas. */
  title: string | null;
  suggested_by_ai: boolean;
}

/** L'unité dans laquelle la taille cible d'un extrait est exprimée. */
export type ChunkUnit = 'caracteres' | 'mots' | 'tokens';

export interface Chunk {
  text: string;
  start: number;
  end: number;
  size: number;
  title: string | null;
}

export interface ChunkResponse {
  chunks: Chunk[];
  /** Le texte découpé, pour que les bornes déplaçables désignent quelque chose. */
  text: string;
  /** 'none' fait basculer l'écran sur le collage plutôt que d'afficher un échec. */
  text_source: 'pasted' | 'fetched' | 'none';
  unit: ChunkUnit;
  suggested_size: number;
  /** Faux quand aucun modèle n'est configuré : la suggestion d'intitulés ne rendrait rien. */
  llm_enabled: boolean;
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
  /**
   * Rapport déclaré entre le propos du contenu et ce que dit la source.
   * `null` = non déclaré, ce qui ne vaut pas `mentionne` : l'un est un
   * silence, l'autre une réponse.
   */
  stance: SourceStance | null;
  is_pivot: boolean;
  archive_status: ArchiveStatus;
  archive_url: string | null;
  archive_timestamp: string | null;
  parent_source_id: string | null;
  /**
   * Fiche Philum désignée par cette source : choisie au picker, ou déduite
   * quand l'URL de la source pointe vers une fiche Philum. C'est ce lien qui
   * construit le méta-graphe et la constellation.
   */
  linked_card_id?: string | null;
  /** Chemin public de la fiche liée : peuplé depuis le méta-graphe seulement. */
  linked_card_slug?: string | null;
  linked_card_creator_slug?: string | null;
  /** Nombre de sources de la fiche liée (enrichi sur l'endpoint public). */
  linked_card_sources_count?: number | null;
  journal?: string | null;
  volume?: string | null;
  pages?: string | null;
  publisher?: string | null;
  doi?: string | null;
  conflict_of_interest: string | null;
  /**
   * Dérivé de Crossref, jamais saisi. `null` = jamais vérifié, ce qui ne se
   * confond ni avec `none` (vérifié, aucun avis) ni avec `unverifiable`
   * (vérification impossible, faute de DOI connu).
   */
  retraction_status?: RetractionStatus | null;
  retraction_notice_doi?: string | null;
  retraction_checked_at?: string | null;
  /**
   * Dérivé d'OpenAlex, jamais saisi. Même règle : `null` = jamais vérifié,
   * `closed` = vérifié et rien de gratuit, `unverifiable` = pas vérifiable.
   */
  oa_status?: OpenAccessStatus | null;
  oa_url?: string | null;
  oa_license?: string | null;
  /** `null` = OpenAlex ne dit rien, jamais « non » par défaut. */
  in_doaj?: boolean | null;
  oa_checked_at?: string | null;
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
  published_at?: string | null;
  format: SourceFormat;
  category: SourceCategory;
  author_kind: AuthorKind;
  annotation?: string;
  stance?: SourceStance | null;
  is_pivot?: boolean;
  parent_source_id?: string | null;
  linked_card_id?: string | null;
  /** Métadonnées bibliographiques optionnelles (exports BibTeX/CSL/APA). */
  journal?: string | null;
  volume?: string | null;
  pages?: string | null;
  publisher?: string | null;
  doi?: string | null;
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

export type Platform =
  'youtube' | 'podcast' | 'blog' | 'x' | 'bluesky' | 'revue-scientifique' | 'other';
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

export type ArchiveStatus = 'pending' | 'archived' | 'failed' | 'not_applicable';

/**
 * Ce qu'une demande d'archivage a réellement déclenché, poste par poste.
 *
 * Un seul compteur mentirait : « 40 » ne dirait pas si les 40 partent à
 * l'archivage ou si la moitié était déjà archivée.
 */
export interface ArchiveOutcome {
  scheduled: number;
  already_archived: number;
  /** Sans URL : il n'y a rien à archiver, ce n'est pas un échec d'archivage. */
  nothing_to_archive: number;
  /** Déjà dans la file d'une demande précédente : redemander ne fait rien. */
  already_running: number;
}

/** Déclaratif, jamais inféré : l'auteur de la fiche l'affirme et en répond. */
export type SourceStance = 'appuie' | 'nuance-contredit' | 'mentionne' | 'contexte';

/** Verdict Crossref / Retraction Watch. Machine, jamais déclaratif. */
export type RetractionStatus = 'none' | 'retracted' | 'concern' | 'corrected' | 'unverifiable';

/** Route d'accès libre selon OpenAlex. Machine, jamais déclaratif. */
export type OpenAccessStatus =
  | 'diamond'
  | 'gold'
  | 'green'
  | 'hybrid'
  | 'bronze'
  /** Libre par une voie qu'OpenAlex nomme d'une façon inconnue ici. */
  | 'open'
  | 'closed'
  | 'unverifiable';

// --- Imports (biblio parsing → draft de fiche) -----------------------------

export interface ImportedSourceDraft {
  url: string;
  title: string | null;
  authors: string | null;
  published_at: string | null;
  format: SourceFormat;
  category: SourceCategory;
  author_kind: AuthorKind;
  /** Métadonnées bibliographiques étendues (autofill Crossref). */
  journal?: string | null;
  volume?: string | null;
  pages?: string | null;
  publisher?: string | null;
  doi?: string | null;
  /**
   * Classification IA du type d'URL. Le badge est indicatif — l'user coche
   * ou décoche à sa guise, rien n'est jamais filtré automatiquement.
   */
  classification?: 'source' | 'promo' | 'social' | 'other' | null;
}

export interface ImportedCardDraft {
  title: string | null;
  description: string | null;
  /** Auteurs du contenu visé, extraits de la page (Crossref, JSON-LD, meta). */
  authors: string | null;
  content_url: string;
}

export interface UrlMetadataResponse {
  title: string | null;
  description: string | null;
  /** Auteurs du contenu visé, extraits de la page (Crossref, JSON-LD, meta). */
  authors: string | null;
  /**
   * Le site a refusé l'accès (obstacle anti-bot, 403, 429) — à distinguer d'une
   * page dont rien n'a pu être tiré. Les deux arrivent sous forme de champs
   * vides ; seul ce drapeau dit lequel des deux s'est produit.
   */
  access_blocked: boolean;
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
  /**
   * Pipeline d'extraction v2 : niveau de confiance de la validation anti-bruit.
   * - 'high'  : section References bornée dans le HTML → filtrage strict.
   * - 'medium': aucune section identifiable → fallback body-search.
   * - 'low'   : ni oracle ni HTML → aucune validation possible.
   */
  extraction_confidence?: 'high' | 'medium' | 'low';
  /** Nb de refs venues d'un oracle (Wikipedia API, Crossref) — autoritatives. */
  refs_from_oracle?: number;
  /** Nb de refs venues de S2/HTML/LLM, validées par section-detection. */
  refs_from_enrichment?: number;
  /** Nb de candidats éliminés par section-detection (transparence anti-bruit). */
  refs_dropped_validation?: number;
  /** Nb de candidats éliminés par le scoring syntaxique (fragments, artefacts). */
  refs_dropped_scoring?: number;
}

/**
 * Canal transcript YouTube. Volontairement séparé des références : le texte
 * vient d'une reconnaissance vocale, donc bruité. Chaque suggestion doit être
 * cochée explicitement, rien n'est ajouté d'office.
 */
export interface YoutubeTranscriptResponse {
  /** false = aucune piste de sous-titres exploitable sur cette vidéo. */
  available: boolean;
  transcript_chars: number;
  suggestions: ImportedSourceDraft[];
}

/**
 * Méta-graphe : fiches reliées entre elles par leurs sources.
 *
 * Une source dont l'URL pointe vers une fiche Philum publique porte
 * `linked_card_id`. Le backend suit ces liens en BFS borné et renvoie un
 * graphe normalisé qui alimente deux vues : le dépliage d'un nœud dans le
 * graphe d'une fiche, et la constellation (fiches seules).
 */
export interface GraphNode {
  /** `card:<uuid>` ou `source:<uuid>` — unique tous types confondus. */
  id: string;
  kind: 'card' | 'source';
  /** Nombre de sauts depuis la fiche racine. */
  depth: number;
  title?: string | null;
  url?: string | null;
  /**
   * Auteurs réels du contenu. Sur un nœud `card`, ils sont remontés depuis la
   * source qui désigne cette fiche dans la bibliographie de qui la cite : une
   * fiche ne connaît pas elle-même les auteurs du contenu qu'elle documente.
   */
  authors?: string | null;
  category?: string | null;
  format?: string | null;
  author_kind?: string | null;
  stance?: string | null;
  is_pivot?: boolean;
  published_at?: string | null;
  /** Métadonnées bibliographiques : la recherche du graphe porte dessus. */
  journal?: string | null;
  publisher?: string | null;
  doi?: string | null;
  /** Nœuds `card` uniquement — nécessaires pour étiqueter et naviguer. */
  slug?: string | null;
  creator_slug?: string | null;
  creator_name?: string | null;
  sources_count?: number | null;
  /** Fiche non revendiquée : son créateur Philum n'est pas l'auteur du contenu. */
  is_seed?: boolean;
  /** Nœuds `source` : fiche Philum visée, si elle existe. */
  linked_card_id?: string | null;
  /** Chemin public de la fiche liée (slug + username créateur). */
  linked_card_slug?: string | null;
  linked_card_creator_slug?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  /** `cites` : fiche → source. `is_card` : fiche → fiche (arête du méta-graphe). */
  kind: 'cites' | 'is_card';
  /** Rapport déclaré par la source qui porte l'arête : colore le trait. */
  stance?: string | null;
}

export interface CardGraph {
  root_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  /** true = plafond de nœuds atteint, le voisinage affiché est partiel. */
  truncated: boolean;
}

export interface IncomingCitation {
  source_id: string;
  cited_card_id: string;
  cited_card_title: string;
  cited_card_slug: string;
  citing_card_id: string;
  citing_card_title: string;
  citing_card_slug: string;
  citing_creator_slug: string;
  citing_creator_name?: string | null;
  /** null = aucun rapport déclaré, ce qui n'est pas « neutre ». */
  stance?: string | null;
  /** Date à laquelle la citation est devenue publique. */
  cited_at: string;
  is_new: boolean;
}

export interface IncomingCitations {
  citations: IncomingCitation[];
  new_count: number;
  /** null = jamais consulté. À dire tel quel, sans inventer de date. */
  seen_at?: string | null;
  truncated: boolean;
}

export type LinkOrigin = 'manuel' | 'url' | 'contenu';

export interface CardConnection {
  source_id: string;
  source_title: string | null;
  source_url: string;
  card_id: string;
  card_title: string;
  card_slug: string;
  card_creator_slug: string;
  stance: SourceStance | null;
  origin: LinkOrigin | null;
  confirmed: boolean;
  editable: boolean;
}

export interface CardConnections {
  outgoing: CardConnection[];
  incoming: CardConnection[];
}
