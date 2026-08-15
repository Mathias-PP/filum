import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

import type {
  ArchiveOutcome,
  Attestation,
  AttestationVerifyResponse,
  Card,
  CardConnection,
  AnnotationResponse,
  CardConnections,
  CardDetail,
  CardCreate,
  CardGraph,
  CardSearchResult,
  ChunkResponse,
  ChunkUnit,
  ExcerptSearchResponse,
  ExcerptSuggestResponse,
  ExcerptVerifyResponse,
  ImportFromUrlResponse,
  IncomingCitations,
  UrlMetadataResponse,
  YoutubeTranscriptResponse,
  LinkedAccount,
  LinkedAccountIn,
  Source,
  SourceCreate,
  SourceExcerpt,
  User,
  UserProfile,
} from './types';
import { normalizeCardDetail, normalizeSource } from './legacy-adapter';

// In the browser we ALWAYS use a relative path so requests hit the SvelteKit
// /api proxy (src/routes/api/[...path]/+server.ts), which forwards to the
// FastAPI backend SERVER-SIDE and makes session cookies first-party.
// Without this same-origin proxy, mobile Safari/iOS WebKit silently blocks
// the backend's session cookie as a third-party cookie (ITP), which is the
// exact symptom of the "Echec de l'authentification" reported on mobile only.
// On SSR (during page render on Vercel) we may still use the env var if set,
// but it works equally well with a relative path through the same proxy.
const API_BASE = browser ? '/api/v1' : `${env.PUBLIC_API_BASE_URL ?? ''}/api/v1`;

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // Un envoi multipart porte une frontière générée par le navigateur ; imposer
  // `application/json` la remplacerait et le serveur ne trouverait plus le
  // fichier dans un corps qu'il ne sait plus découper.
  const estMultipart = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(estMultipart ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: { code: 'unknown', message: 'An error occurred' },
    }));
    // Une session qui expire pendant la saisie remontait « Not authenticated »,
    // en anglais et sans suite à donner. Le message dit maintenant ce qui s'est
    // passé et ce qui reste possible : la page n'a pas été rechargée, donc ce
    // qui a été saisi est toujours là.
    if (response.status === 401) {
      throw new ApiError(
        401,
        'session_expired',
        'Votre session a expiré. Cette page conserve votre saisie : reconnectez-vous dans un autre onglet, puis réessayez.',
        error.error?.details
      );
    }
    throw new ApiError(
      response.status,
      error.error?.code || 'unknown',
      error.error?.message || 'An error occurred',
      error.error?.details
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const api = {
  auth: {
    login: () => {
      window.location.href = `${API_BASE}/auth/google/login`;
    },

    logout: async () => {
      await request('/auth/logout', { method: 'POST' });
    },

    me: async (): Promise<User | null> => {
      try {
        return await request<User>('/auth/me');
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) {
          return null;
        }
        throw e;
      }
    },
  },

  cards: {
    list: async (params?: {
      status?: string;
      limit?: number;
      offset?: number;
    }): Promise<Card[]> => {
      const searchParams = new URLSearchParams();
      if (params?.status) searchParams.set('status', params.status);
      if (params?.limit) searchParams.set('limit', String(params.limit));
      if (params?.offset) searchParams.set('offset', String(params.offset));

      const query = searchParams.toString();
      return request<Card[]>(`/cards${query ? `?${query}` : ''}`);
    },

    /** Fiches sélectionnables comme parent : celles de l'user + les publiques. */
    search: async (q: string, limit = 20): Promise<CardSearchResult[]> => {
      const params = new URLSearchParams({ limit: String(limit) });
      if (q) params.set('q', q);
      return request<CardSearchResult[]>(`/cards/search?${params.toString()}`);
    },

    create: async (data: CardCreate): Promise<Card> => {
      return request<Card>('/cards', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    get: async (cardId: string): Promise<Card> => {
      return request<Card>(`/cards/${cardId}`);
    },

    update: async (cardId: string, data: Partial<CardCreate>): Promise<Card> => {
      return request<Card>(`/cards/${cardId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },

    publish: async (
      cardId: string
    ): Promise<{
      id: string;
      status: string;
      published_at: string;
      public_url: string;
    }> => {
      return request(`/cards/${cardId}/publish`, { method: 'POST' });
    },

    delete: async (cardId: string): Promise<void> => {
      await request(`/cards/${cardId}`, { method: 'DELETE' });
    },

    listDeleted: async (): Promise<Card[]> => {
      return request<Card[]>('/cards/deleted');
    },

    restore: async (cardId: string): Promise<Card> => {
      return request<Card>(`/cards/${cardId}/restore`, { method: 'POST' });
    },

    /** Qui s'appuie sur mes fiches. */
    incomingCitations: async (): Promise<IncomingCitations> => {
      return request<IncomingCitations>('/cards/citations');
    },

    /**
     * Marque les citations entrantes comme vues. Renvoie la liste telle
     * qu'elle était AVANT le marquage : sinon la visite éteindrait sous les
     * yeux de l'utilisateur ce qu'il vient tout juste d'ouvrir.
     */
    markCitationsSeen: async (): Promise<IncomingCitations> => {
      return request<IncomingCitations>('/cards/citations/seen', { method: 'POST' });
    },

    getPublic: async (creatorSlug: string, cardSlug: string): Promise<CardDetail> => {
      const raw = await request<CardDetail>(`/@${creatorSlug}/${cardSlug}`);
      return normalizeCardDetail(raw);
    },

    getGraph: async (
      creatorSlug: string,
      cardSlug: string,
      opts: { depth?: number; includeSources?: boolean } = {}
    ): Promise<CardGraph> => {
      const params = new URLSearchParams();
      if (opts.depth !== undefined) params.set('depth', String(opts.depth));
      if (opts.includeSources !== undefined)
        params.set('include_sources', String(opts.includeSources));
      const qs = params.toString();
      return request<CardGraph>(`/@${creatorSlug}/${cardSlug}/graph${qs ? `?${qs}` : ''}`);
    },
    // `verify` removed (ADR-019). Use `api.attestations.verify(id)` instead.

    connections: (cardId: string): Promise<CardConnections> =>
      request<CardConnections>(`/cards/${cardId}/connections`),

    confirmConnection: (cardId: string, sourceId: string): Promise<CardConnection> =>
      request<CardConnection>(`/cards/${cardId}/connections/${sourceId}/confirm`, {
        method: 'POST',
      }),

    removeConnection: (cardId: string, sourceId: string): Promise<void> =>
      request<void>(`/cards/${cardId}/connections/${sourceId}`, { method: 'DELETE' }),
  },

  sources: {
    list: async (cardId: string): Promise<Source[]> => {
      const raw = await request<Source[]>(`/sources?card_id=${cardId}`);
      return raw.map((s) => normalizeSource(s));
    },

    /**
     * Relance l'archivage des sources désignées.
     *
     * L'archivage automatique est cadencé et peut prendre des heures sur une
     * grosse fiche : cette route permet de dire ce qui presse.
     */
    archive: async (sourceIds: string[]): Promise<ArchiveOutcome> =>
      request<ArchiveOutcome>('/sources/archive', {
        method: 'POST',
        body: JSON.stringify({ source_ids: sourceIds }),
      }),

    create: async (cardId: string, data: SourceCreate): Promise<Source> => {
      const raw = await request<Source>(`/sources?card_id=${cardId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return normalizeSource(raw);
    },

    createBatch: async (
      cardId: string,
      sources: SourceCreate[]
    ): Promise<{
      created: Source[];
      failed: Array<{ index: number; url: string; error: string }>;
    }> => {
      const raw = await request<{
        created: Source[];
        failed: Array<{ index: number; url: string; error: string }>;
      }>(`/sources/batch?card_id=${cardId}`, {
        method: 'POST',
        body: JSON.stringify({ sources }),
      });
      return {
        created: raw.created.map((s) => normalizeSource(s)),
        failed: raw.failed,
      };
    },

    update: async (sourceId: string, data: Partial<SourceCreate>): Promise<Source> => {
      const raw = await request<Source>(`/sources/${sourceId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
      return normalizeSource(raw);
    },

    delete: async (sourceId: string): Promise<void> => {
      await request(`/sources/${sourceId}`, { method: 'DELETE' });
    },
  },

  excerpts: {
    create: async (
      sourceId: string,
      data: {
        text: string;
        title?: string | null;
        /** Phrase qui situe le passage. Rangée à part : jamais recollée dans `text`. */
        context?: string | null;
        suggested_by_ai?: boolean;
        annotated_by_ai?: boolean;
        // Voisinage et position du passage dans le texte d'où il vient : c'est
        // ce qui permet de le retrouver dans une page qui a bougé. Absents
        // d'une saisie à la main, où le texte de la source n'est pas connu.
        anchor_prefix?: string | null;
        anchor_suffix?: string | null;
        anchor_offset?: number | null;
      }
    ): Promise<SourceExcerpt> => {
      return request<SourceExcerpt>(`/sources/${sourceId}/excerpts`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    delete: async (sourceId: string, excerptId: string): Promise<void> => {
      await request(`/sources/${sourceId}/excerpts/${excerptId}`, { method: 'DELETE' });
    },

    /**
     * Cherche par le sens dans ses propres extraits, toutes fiches confondues.
     *
     * La comparaison porte sur des vecteurs : la question n'a pas besoin de
     * reprendre les mots du passage. `available: false` dit que la recherche
     * n'a pas pu avoir lieu, ce qui ne se confond pas avec zéro résultat.
     */
    search: async (query: string, limit = 20): Promise<ExcerptSearchResponse> => {
      const params = new URLSearchParams({ q: query, limit: String(limit) });
      return request<ExcerptSearchResponse>(`/excerpts/search?${params}`);
    },

    /**
     * Relit la page de la source et cherche chaque extrait dans le texte
     * d'aujourd'hui.
     *
     * Les quatre états ne se replient pas l'un sur l'autre : `unreadable` dit
     * que la page n'a rendu aucun texte — on ne sait pas — là où `missing` dit
     * que le passage n'y est pas. Les confondre ferait passer une source
     * inaccessible pour une citation inventée.
     */
    verify: async (sourceId: string, text?: string): Promise<ExcerptVerifyResponse> => {
      return request<ExcerptVerifyResponse>(`/sources/${sourceId}/excerpts/verify`, {
        method: 'POST',
        body: JSON.stringify({ text: text ?? null }),
      });
    },

    /**
     * Propose un intitulé et une phrase de mise en situation pour un passage.
     *
     * Ne persiste rien : la réponse remplit des champs que l'auteur·ice relit,
     * corrige ou vide. `surrounding` est le texte d'où vient le passage —
     * sans lui un modèle ne peut que le paraphraser, alors que tout l'objet
     * de la mise en situation est de dire ce que le passage suppose connu.
     */
    annotate: async (
      sourceId: string,
      text: string,
      surrounding?: string
    ): Promise<AnnotationResponse> => {
      return request<AnnotationResponse>(`/sources/${sourceId}/excerpts/annotate`, {
        method: 'POST',
        body: JSON.stringify({ text, surrounding: surrounding ?? null }),
      });
    },

    suggest: async (sourceId: string, text?: string): Promise<ExcerptSuggestResponse> => {
      return request<ExcerptSuggestResponse>(`/sources/${sourceId}/excerpts/suggest`, {
        method: 'POST',
        body: JSON.stringify({ text: text ?? null }),
      });
    },

    /**
     * Découpe le texte d'une source en extraits proposables.
     *
     * Sans `text`, le serveur tente de lire la page — mesuré le 2026-08-08 :
     * cinq URLs sur dix n'en rendent rien. Avec `text`, rien ne dépend du site,
     * ce qui est le seul chemin qui marche derrière un anti-crawler.
     */
    chunk: async (
      sourceId: string,
      data: {
        text?: string;
        unit?: ChunkUnit;
        size?: number;
        suggest_titles?: boolean;
      } = {}
    ): Promise<ChunkResponse> => {
      return request<ChunkResponse>(`/sources/${sourceId}/excerpts/chunk`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    /**
     * Le même découpage, à partir d'un document déposé (.pdf, .docx, .odt,
     * .txt, .md).
     *
     * Un chapitre ne se colle pas : au-delà de quelques pages, le collage
     * devient la corvée qui fait renoncer. Le fichier n'est pas conservé, seul
     * son texte sert d'assise au découpage.
     */
    chunkFile: async (
      sourceId: string,
      file: File,
      data: { unit?: ChunkUnit; size?: number; suggest_titles?: boolean } = {}
    ): Promise<ChunkResponse> => {
      const corps = new FormData();
      corps.append('file', file);
      if (data.unit) corps.append('unit', data.unit);
      if (data.size) corps.append('size', String(data.size));
      if (data.suggest_titles) corps.append('suggest_titles', 'true');
      return request<ChunkResponse>(`/sources/${sourceId}/excerpts/chunk-file`, {
        method: 'POST',
        body: corps,
      });
    },
  },

  users: {
    getProfile: async (slug: string): Promise<UserProfile> => {
      return request<UserProfile>(`/users/@${slug}`);
    },

    getLinkedAccounts: async (): Promise<LinkedAccount[]> => {
      return request<LinkedAccount[]>('/users/me/linked-accounts');
    },

    setLinkedAccounts: async (accounts: LinkedAccountIn[]): Promise<LinkedAccount[]> => {
      return request<LinkedAccount[]>('/users/me/linked-accounts', {
        method: 'PUT',
        body: JSON.stringify({ accounts }),
      });
    },
  },

  attestations: {
    create: async (contentUrl: string): Promise<Attestation> => {
      return request<Attestation>('/attestations/content', {
        method: 'POST',
        body: JSON.stringify({ content_url: contentUrl }),
      });
    },

    get: async (attestationId: string): Promise<Attestation> => {
      return request<Attestation>(`/attestations/${attestationId}`);
    },

    verify: async (attestationId: string): Promise<AttestationVerifyResponse> => {
      return request<AttestationVerifyResponse>(`/attestations/${attestationId}/verify`);
    },
  },

  claims: {
    create: async (
      cardId: string,
      data: { email: string; channel_url: string; message?: string }
    ): Promise<{ ok: boolean }> => {
      return request<{ ok: boolean }>(`/cards/${cardId}/claim-requests`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
  },

  imports: {
    fromContentUrl: async (url: string): Promise<ImportFromUrlResponse> => {
      return request<ImportFromUrlResponse>('/import/from-content-url', {
        method: 'POST',
        body: JSON.stringify({ url }),
      });
    },
    youtubeTranscript: async (url: string): Promise<YoutubeTranscriptResponse> => {
      return request<YoutubeTranscriptResponse>('/import/youtube-transcript', {
        method: 'POST',
        body: JSON.stringify({ url }),
      });
    },
    urlMetadata: async (url: string): Promise<UrlMetadataResponse> => {
      return request<UrlMetadataResponse>('/import/url-metadata', {
        method: 'POST',
        body: JSON.stringify({ url }),
      });
    },
  },
};

export { ApiError };
export type { ApiError as ApiErrorType };
