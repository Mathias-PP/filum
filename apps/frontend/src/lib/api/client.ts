import { env } from '$env/dynamic/public';

import type {
  Card,
  CardDetail,
  CardCreate,
  Source,
  SourceCreate,
  User,
  UserProfile,
  VerificationResponse,
} from './types';

const API_BASE = `${env.PUBLIC_API_BASE_URL ?? ''}/api/v1`;

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
      canonical_hash: string;
      signature: string;
      signed_at: string;
      published_at: string;
      public_url: string;
    }> => {
      return request(`/cards/${cardId}/publish`, { method: 'POST' });
    },

    delete: async (cardId: string): Promise<void> => {
      await request(`/cards/${cardId}`, { method: 'DELETE' });
    },

    getPublic: async (creatorSlug: string, cardSlug: string): Promise<CardDetail> => {
      return request<CardDetail>(`/@${creatorSlug}/${cardSlug}`);
    },

    verify: async (creatorSlug: string, cardSlug: string): Promise<VerificationResponse> => {
      return request<VerificationResponse>(`/@${creatorSlug}/${cardSlug}/verify`);
    },
  },

  sources: {
    create: async (cardId: string, data: SourceCreate): Promise<Source> => {
      return request<Source>(`/sources?card_id=${cardId}`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },

    update: async (sourceId: string, data: Partial<SourceCreate>): Promise<Source> => {
      return request<Source>(`/sources/${sourceId}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      });
    },

    delete: async (sourceId: string): Promise<void> => {
      await request(`/sources/${sourceId}`, { method: 'DELETE' });
    },
  },

  users: {
    getProfile: async (slug: string): Promise<UserProfile> => {
      return request<UserProfile>(`/users/@${slug}`);
    },
  },
};

export { ApiError };
export type { ApiError as ApiErrorType };
