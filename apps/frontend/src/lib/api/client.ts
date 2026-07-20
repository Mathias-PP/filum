import { browser } from '$app/environment';
import { env } from '$env/dynamic/public';

import type {
  Attestation,
  AttestationVerifyResponse,
  Card,
  CardDetail,
  CardCreate,
  ExcerptSuggestResponse,
  ImportFromUrlResponse,
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
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      error: { code: 'unknown', message: 'An error occurred' },
    }));
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

    getPublic: async (creatorSlug: string, cardSlug: string): Promise<CardDetail> => {
      const raw = await request<CardDetail>(`/@${creatorSlug}/${cardSlug}`);
      return normalizeCardDetail(raw);
    },
    // `verify` removed (ADR-019). Use `api.attestations.verify(id)` instead.
  },

  sources: {
    list: async (cardId: string): Promise<Source[]> => {
      const raw = await request<Source[]>(`/sources?card_id=${cardId}`);
      return raw.map((s) => normalizeSource(s));
    },

    create: async (cardId: string, data: SourceCreate): Promise<Source> => {
      const raw = await request<Source>(`/sources?card_id=${cardId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      return normalizeSource(raw);
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
      data: { text: string; suggested_by_ai?: boolean }
    ): Promise<SourceExcerpt> => {
      return request<SourceExcerpt>(`/sources/${sourceId}/excerpts`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    delete: async (sourceId: string, excerptId: string): Promise<void> => {
      await request(`/sources/${sourceId}/excerpts/${excerptId}`, { method: 'DELETE' });
    },

    suggest: async (sourceId: string): Promise<ExcerptSuggestResponse> => {
      return request<ExcerptSuggestResponse>(`/sources/${sourceId}/excerpts/suggest`, {
        method: 'POST',
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

  waitlist: {
    join: async (email: string, context: string = 'home'): Promise<{ ok: boolean }> => {
      return request<{ ok: boolean }>('/waitlist', {
        method: 'POST',
        body: JSON.stringify({ email, context }),
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
  },
};

export { ApiError };
export type { ApiError as ApiErrorType };
