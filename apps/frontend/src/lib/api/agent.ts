/**
 * Client de l'agent BYOK : providers, sessions, flux de chat SSE, approbations.
 *
 * Le chat n'utilise pas `request` : sa réponse est un `text/event-stream` qu'il
 * faut lire au fil de l'eau. `streamChat` rend un itérateur asynchrone
 * d'événements, pour que l'appelant affiche chaque tour dès qu'il arrive au
 * lieu d'attendre la fin de la réponse.
 */

import { API_BASE, ApiError, request } from './client';

export type ProviderKind =
  | 'openai'
  | 'anthropic'
  | 'deepseek'
  | 'gemini'
  | 'groq'
  | 'openrouter'
  | 'mistral'
  | 'cerebras'
  | 'custom';

export interface AgentProvider {
  id: string;
  provider: ProviderKind;
  display_name: string;
  base_url: string;
  model: string;
  is_default: boolean;
  api_key_masked: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface AgentProviderCreate {
  provider: ProviderKind;
  display_name?: string | null;
  base_url?: string | null;
  model: string;
  api_key: string;
  is_default?: boolean;
}

export type AgentProviderUpdate = Partial<Omit<AgentProviderCreate, 'provider'>>;

export interface AgentProviderTestResult {
  ok: boolean;
  http_status: number | null;
  model_resolved: string;
  url: string;
  message: string;
  provider_message: string | null;
  latency_ms: number | null;
  // Sur un test réussi, la liste des modèles du compte est chargée en même
  // temps (cache serveur 15 min chauffé). Null sur échec.
  models: string[] | null;
}

export interface ProviderMetaEntry {
  label: string;
  [key: string]: unknown;
}

export interface AgentProviderMeta {
  data_scope: string;
  providers: Record<string, ProviderMetaEntry>;
  recommended_models?: Record<string, string[]>;
}

export interface AgentModelMeta {
  id: string;
  context_length?: number;
  pricing?: { prompt: string; completion: string };
}

export interface AgentProviderModels {
  models: (string | AgentModelMeta)[];
  source: 'provider' | 'repli';
  message?: string;
}

export interface AgentSessionUsage {
  total_prompt_tokens: number;
  total_completion_tokens: number;
  cost_eur: number | null;
}

export interface AgentSession {
  id: string;
  title: string;
  provider_id: string | null;
  model_override: string | null;
  created_at: string;
  last_message_at: string | null;
}

export interface AgentMessage {
  id: string;
  role: string;
  content: string;
  tool_calls: Record<string, unknown>[] | null;
  tool_name: string | null;
  /** Identifiant du tool_call auquel ce message répond : sert à réapparier
   * appel et résultat au rechargement d'une session. */
  tool_call_id?: string | null;
  created_at: string;
}

export type AgentEvent =
  | { type: 'session'; payload: { id: string } }
  | {
      type: 'discovery_active';
      payload: {
        provider_public_name: string;
        remaining_today: number | null;
        retention_notice: string;
      };
    }
  | { type: 'message_delta'; payload: { delta: string; tour: number } }
  | {
      type: 'tool_call';
      payload: {
        id: string | null;
        name: string;
        arguments: Record<string, unknown>;
        tour: number;
      };
    }
  | {
      type: 'tool_result';
      payload: { id: string | null; name: string; result: Record<string, unknown> };
    }
  | {
      type: 'approval_request';
      payload: {
        request_id: string;
        tool: string;
        arguments: Record<string, unknown>;
        tour: number;
      };
    }
  | { type: 'approval_resolved'; payload: { request_id: string; tool: string; approved: boolean } }
  | {
      type: 'done';
      payload: { reason: string; usage?: { prompt_tokens: number; completion_tokens: number } };
    }
  | { type: 'error'; payload: { message: string } };

export interface ChatInput {
  message: string;
  session_id?: string;
  provider_id?: string;
  model_override?: string;
  signal?: AbortSignal;
}

export const agentApi = {
  providers: {
    meta: () => request<AgentProviderMeta>('/agent/providers/meta'),
    list: () => request<AgentProvider[]>('/agent/providers'),
    create: (body: AgentProviderCreate) =>
      request<AgentProvider>('/agent/providers', { method: 'POST', body: JSON.stringify(body) }),
    update: (id: string, body: AgentProviderUpdate) =>
      request<AgentProvider>(`/agent/providers/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    remove: (id: string) => request<void>(`/agent/providers/${id}`, { method: 'DELETE' }),
    test: (id: string) =>
      request<AgentProviderTestResult>(`/agent/providers/${id}/test`, { method: 'POST' }),
    models: (id: string) => request<AgentProviderModels>(`/agent/providers/${id}/models`),
  },

  sessions: {
    list: () => request<AgentSession[]>('/agent/sessions'),
    create: (body: { title?: string; provider_id?: string | null } = {}) =>
      request<AgentSession>('/agent/sessions', { method: 'POST', body: JSON.stringify(body) }),
    get: (id: string) => request<AgentSession>(`/agent/sessions/${id}`),
    messages: (id: string) => request<AgentMessage[]>(`/agent/sessions/${id}/messages`),
    usage: (id: string) => request<AgentSessionUsage>(`/agent/sessions/${id}/usage`),
    update: (
      id: string,
      body: { title?: string; provider_id?: string | null; model_override?: string | null }
    ) =>
      request<AgentSession>(`/agent/sessions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    remove: (id: string) => request<void>(`/agent/sessions/${id}`, { method: 'DELETE' }),
  },

  /** Répond à une action sensible suspendue. Débloque la boucle côté serveur. */
  approve: (requestId: string, approved: boolean) =>
    request<void>('/agent/approve', {
      method: 'POST',
      body: JSON.stringify({ request_id: requestId, approved }),
    }),

  streamChat,
};

async function* streamChat({
  message,
  session_id,
  provider_id,
  model_override,
  signal,
}: ChatInput): AsyncGenerator<AgentEvent> {
  const body: Record<string, unknown> = { message };
  if (session_id) body.session_id = session_id;
  if (provider_id) body.provider_id = provider_id;
  if (model_override) body.model_override = model_override;
  const response = await fetch(`${API_BASE}/agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      detail?.error?.code ?? detail?.detail?.code ?? 'agent_chat_failed',
      detail?.error?.message ??
        detail?.detail?.message ??
        "L'agent n'a pas pu démarrer. Réessayez dans un instant."
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let tampon = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      tampon += decoder.decode(value, { stream: true });
      // Un événement SSE se termine sur une ligne vide. Le dernier morceau du
      // tampon est peut-être un événement tronqué : on le garde pour la suite.
      const blocs = tampon.split('\n\n');
      tampon = blocs.pop() ?? '';
      for (const bloc of blocs) {
        const event = parseEvent(bloc);
        if (event) yield event;
      }
    }
    const dernier = parseEvent(tampon);
    if (dernier) yield dernier;
  } finally {
    reader.releaseLock();
  }
}

function parseEvent(bloc: string): AgentEvent | null {
  const ligne = bloc
    .split('\n')
    .map((l) => l.trim())
    .find((l) => l.startsWith('data: '));
  if (!ligne) return null;
  try {
    return JSON.parse(ligne.slice('data: '.length)) as AgentEvent;
  } catch {
    return null;
  }
}
