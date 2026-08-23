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
  /** Slug de l'agent nommé de cette session. Null = assistant généraliste. */
  agent_slug: string | null;
  created_at: string;
  last_message_at: string | null;
}

/** Un agent nommé, défini par un fichier `agents/<slug>.yaml` du workspace. */
export interface AgentDefinition {
  slug: string;
  name: string;
  contract: string;
  system_prompt: string;
  tools: string[];
  context: string[];
  layer: string | null;
  model_hint: string | null;
  /** Livré avec Philum : « Restaurer template » le recrée s'il est supprimé. */
  builtin: boolean;
  /** Outils demandés que la configuration serveur n'expose pas aujourd'hui. */
  tools_absents: string[];
  /** Chemin du fichier qui porte cette définition, pour ouvrir l'éditeur. */
  path: string;
}

/** Un fichier de `agents/` qui ne décrit pas un agent exploitable. */
export interface AgentDefinitionRejected {
  path: string;
  raison: string;
}

export interface AgentDefinitionList {
  agents: AgentDefinition[];
  rejected: AgentDefinitionRejected[];
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
  | {
      /** Mode gratuit : une lane serveur sert le tour. Même bannière que la
       * découverte, texte de rétention propre au fournisseur gratuit. */
      type: 'gratuit_actif';
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
        /** Phrase lisible qui décrit ce que l'utilisateur autorise, calculée
         * côté serveur qui seul peut résoudre les UUIDs en titres réels. */
        resume?: string;
        tour: number;
      };
    }
  | { type: 'approval_resolved'; payload: { request_id: string; tool: string; approved: boolean } }
  | {
      /** Le début de la conversation a été retiré pour tenir dans la fenêtre du
       * modèle. Le dire : l'agent qui « oublie » sans prévenir passe pour
       * défaillant alors qu'il subit une limite. */
      type: 'contexte_compacte';
      payload: { messages_retires: number };
    }
  | {
      type: 'done';
      payload: { reason: string; usage?: { prompt_tokens: number; completion_tokens: number } };
    }
  | { type: 'error'; payload: { message: string } };

export interface WorkspaceTreeEntry {
  path: string;
  type: 'file' | 'directory';
  sha256?: string | null;
  updated_at?: string | null;
  /** Layer ICM : L0/L1 routing, L2 contrat de stage, L3 factory. Null pour
   * un dossier ou un fichier utilisateur hors racines conventionnelles. */
  layer?: string | null;
  /** Phrase de contrat extraite du frontmatter YAML `contract:` ou du
   * premier paragraphe. Null pour un dossier. */
  contract?: string | null;
}

export interface WorkspaceFile {
  path: string;
  sha256: string;
  content: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ChatInput {
  message: string;
  session_id?: string;
  provider_id?: string;
  model_override?: string;
  agent_slug?: string;
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
    test: (id: string, model?: string | null) =>
      request<AgentProviderTestResult>(`/agent/providers/${id}/test`, {
        method: 'POST',
        body: JSON.stringify(model ? { model } : {}),
      }),
    models: (id: string) => request<AgentProviderModels>(`/agent/providers/${id}/models`),
  },

  /** Agents nommés du créateur. En lecture seule : un agent s'écrit en écrivant
   * son fichier via `workspace.write`, il n'a pas de second chemin d'écriture. */
  definitions: {
    list: () => request<AgentDefinitionList>('/agent/definitions'),
    get: (slug: string) => request<AgentDefinition>(`/agent/definitions/${slug}`),
  },

  sessions: {
    list: () => request<AgentSession[]>('/agent/sessions'),
    create: (body: { title?: string; provider_id?: string | null; agent_slug?: string } = {}) =>
      request<AgentSession>('/agent/sessions', { method: 'POST', body: JSON.stringify(body) }),
    get: (id: string) => request<AgentSession>(`/agent/sessions/${id}`),
    messages: (id: string) => request<AgentMessage[]>(`/agent/sessions/${id}/messages`),
    usage: (id: string) => request<AgentSessionUsage>(`/agent/sessions/${id}/usage`),
    update: (
      id: string,
      body: {
        title?: string;
        provider_id?: string | null;
        model_override?: string | null;
        agent_slug?: string | null;
      }
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

  /** Mode gratuit : lanes serveur sans clé utilisateur, derrière un
   * consentement versionné au traitement des données par le fournisseur. */
  gratuit: {
    etat: () =>
      request<{
        disponible: boolean;
        actif: boolean;
        version_warning: string;
        /** Nom public du fournisseur qui sert le mode actif, null sinon. */
        fournisseur_actuel: string | null;
        /** Modèle exact qui servirait le prochain tour (affichage/diagnostic). */
        modele_actuel: string | null;
      }>('/agent/mode-gratuit'),
    activer: (version: string) =>
      request<{ actif: boolean; version_warning: string }>('/agent/mode-gratuit', {
        method: 'PUT',
        body: JSON.stringify({ version }),
      }),
    desactiver: () => request<{ actif: boolean }>('/agent/mode-gratuit', { method: 'DELETE' }),
    /** Ping la lane active sans consommer de quota : même chemin d'appel que le chat. */
    tester: () =>
      request<{
        ok: boolean;
        detail: string;
        modele: string | null;
        latence_ms: number | null;
      }>('/agent/mode-gratuit/tester', { method: 'POST' }),
  },

  /** Workspace ICM du créateur : arbre, lecture, écriture, suppression, re-seed. */
  workspace: {
    tree: (prefix?: string) =>
      request<WorkspaceTreeEntry[]>(
        `/agent/workspace/tree${prefix ? `?prefix=${encodeURIComponent(prefix)}` : ''}`
      ),
    read: (path: string) =>
      request<WorkspaceFile>(`/agent/workspace/file?path=${encodeURIComponent(path)}`),
    write: (path: string, content: string) =>
      request<WorkspaceFile>(`/agent/workspace/file?path=${encodeURIComponent(path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
      }),
    remove: (path: string) =>
      request<void>(`/agent/workspace/file?path=${encodeURIComponent(path)}`, { method: 'DELETE' }),
    seed: () => request<{ seeded: number }>('/agent/workspace/seed', { method: 'POST' }),
  },

  streamChat,
};

async function* streamChat({
  message,
  session_id,
  provider_id,
  model_override,
  agent_slug,
  signal,
}: ChatInput): AsyncGenerator<AgentEvent> {
  const body: Record<string, unknown> = { message };
  if (session_id) body.session_id = session_id;
  if (provider_id) body.provider_id = provider_id;
  if (model_override) body.model_override = model_override;
  if (agent_slug) body.agent_slug = agent_slug;
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
