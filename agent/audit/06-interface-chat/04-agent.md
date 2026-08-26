# 06-04 — agent.ts (client API BYOK, SSE streaming)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/api/agent.ts` (426 l., 20 symboles).
> sha256: 4fb8e7dc774539d94e47766b22092bf56da47dc82c270236f858f3e11aec295a

## Rôle

Client API complet pour l'agent IA : sessions CRUD, providers BYOK CRUD, streaming SSE, mode gratuit, workspace, définitions. Porte les types TypeScript (`AgentSession`, `AgentProvider`, `AgentProviderMeta`, etc.) et encapsule tous les appels HTTP.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ProviderKind` | `apps/frontend/src/lib/api/agent.ts:12` | Union des kinds supportés (openai, anthropic, gemini, mistral, groq, openrouter, cerebras, deepseek, custom) |
| `AgentProvider` | `apps/frontend/src/lib/api/agent.ts:23` | Interface provider BYOK (id, provider, model, api_key_masked, is_default) |
| `AgentProviderCreate` | `apps/frontend/src/lib/api/agent.ts:35` | Interface de création provider (provider, model, api_key, base_url, display_name, is_default) |
| `AgentProviderUpdate` | `apps/frontend/src/lib/api/agent.ts:44` | Type de mise à jour provider (Partial de AgentProviderCreate) |
| `AgentProviderTestResult` | `apps/frontend/src/lib/api/agent.ts:46` | Interface résultat test clé (ok, message, latency_ms, http_status, url) |
| `ProviderMetaEntry` | `apps/frontend/src/lib/api/agent.ts:59` | Interface métadonnées fournisseur (kind, label, recommended_models) |
| `AgentProviderMeta` | `apps/frontend/src/lib/api/agent.ts:64` | Interface métadonnées providers (data_scope, recommended_models) |
| `AgentModelMeta` | `apps/frontend/src/lib/api/agent.ts:70` | Interface métadonnées modèles (source, message, models) |
| `AgentProviderModels` | `apps/frontend/src/lib/api/agent.ts:76` | Interface réponse liste modèles (models, source, message) |
| `AgentSessionUsage` | `apps/frontend/src/lib/api/agent.ts:82` | Interface usage session (tokens_in, tokens_out, cost_estimate) |
| `AgentSession` | `apps/frontend/src/lib/api/agent.ts:88` | Interface session (id, title, model, created_at, usage) |
| `AgentDefinition` | `apps/frontend/src/lib/api/agent.ts:100` | Interface agent nommé (slug, name, description, model, tools) |
| `AgentDefinitionRejected` | `apps/frontend/src/lib/api/agent.ts:118` | Interface définition rejetée (slug, reason) |
| `AgentDefinitionList` | `apps/frontend/src/lib/api/agent.ts:123` | Interface liste définitions (agents, rejected) |
| `AgentMessage` | `apps/frontend/src/lib/api/agent.ts:128` | Interface message (id, role, content, tool_calls, tool_results) |
| `AgentEvent` | `apps/frontend/src/lib/api/agent.ts:140` | Type union des événements SSE (text, tool_call, tool_result, approval_request, done, error) |
| `WorkspaceTreeEntry` | `apps/frontend/src/lib/api/agent.ts:205` | Interface entrée arbre workspace (path, type, size) |
| `WorkspaceFile` | `apps/frontend/src/lib/api/agent.ts:218` | Interface fichier workspace (path, content, meta) |
| `ChatInput` | `apps/frontend/src/lib/api/agent.ts:226` | Interface input chat (message, session_id, provider_id, agent_slug) |
| `agentApi` | `apps/frontend/src/lib/api/agent.ts:235` | Objet racine contenant les namespace sessions, providers, gratuit, workspace, defs |

## Invariants

- **BYOK** : `agentApi` (`apps/frontend/src/lib/api/agent.ts:235`) ne porte jamais de clé API en dur — tout appel passe par `getApiBase()` + header `Authorization` optionnel.
- **SSE** : `streamChat()` retourne un `ReadableStream` — le consommateur (ChatPanel) gère le débit.
- **Types** : tous les types sont exportés et utilisés par les composants UI (ToolCard, ChatPanel, agents/+page).

## Dettes

- `_parseSSE()` : parser maison — pourrait bénéficier d'un test unitaire dédié.
- Le namespace `agentApi` est un gros objet plat — une décomposition par domaine rendrait l'import plus granulaire.
