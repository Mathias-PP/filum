# 04 — API : endpoints agent, routes SSE, Flux chat, sessions, providers, workspace

> Fiches du lot 4 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G4** (`check_lot.sh 4`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

La couche HTTP qui expose l'agent au frontend : 7 routers FastAPI, **31 routes** au total, tous sous `/agent`. Le chat est un flux SSE (`POST /agent/chat`) qui appelle `boucle()` (lot 2). Les providers BYOK, les sessions, le workspace ICM, les agents nommés, le mode gratuit et le run de fiche ont leurs propres routers. L'auth passe par `get_current_user` (JWT standard).

## Les fichiers

| Fiche | Contenu | Routes | Fichier |
|---|---|---|---|
| [01-agent-chat.md](01-agent-chat.md) | `POST /agent/chat` — flux SSE, résolution provider, cooldown lane gratuite | 1 | `apps/backend/app/api/v1/endpoints/agent_chat.py` (404 l.) |
| [02-sessions.md](02-sessions.md) | CRUD sessions + `POST /agent/approve` (réponse humaine aux approvals) | 8 | `apps/backend/app/api/v1/endpoints/agent_sessions.py` (163 l.) |
| [03-providers.md](03-providers.md) | CRUD providers BYOK, test de clé, listing modèles, meta souveraineté | 7 | `apps/backend/app/api/v1/endpoints/agent_providers.py` (189 l.) |
| [04-mode-gratuit.md](04-mode-gratuit.md) | Consentement, test lane, catalogue modèles gratuits | 6 | `apps/backend/app/api/v1/endpoints/agent_mode_gratuit.py` (108 l.) |
| [05-definitions.md](05-definitions.md) | Lecture des agents nommés du créateur (sans mutation) | 2 | `apps/backend/app/api/v1/endpoints/agent_definitions.py` (68 l.) |
| [06-fiche.md](06-fiche.md) | Run de fiche (7 étages SSE), état d'avancement | 2 | `apps/backend/app/api/v1/endpoints/agent_fiche.py` (144 l.) |
| [07-workspace.md](07-workspace.md) | Fichiers ICM du créateur : arbre, lecture, écriture, suppression, seed | 5 | `apps/backend/app/api/v1/endpoints/agent_workspace.py` (120 l.) |

## Invariants du lot

- **31 routes** sous `/agent` (cohérent avec l'invariant G0).
- Rate-limiting sur les mutations : `@limiter.limit(f"{settings.rate_limit_per_minute}/minute")` (chat, sessions create/update, providers create/update/delete/test, workspace write/seed, mode gratuit).
- Chat : `StreamingResponse` avec headers `Cache-Control: no-cache`, `X-Accel-Buffering: no` (anti-proxy de cache).
- Le SSE d'erreur pour quota gratuit/découverte est émis en-stream (pas une exception HTTP) : `StreamingResponse(iter([session_event, error_event]))` — le client reçoit toujours le `session_id` même en erreur.
- `_persister_tour` (`apps/backend/app/api/v1/endpoints/agent_chat.py:358`) écrit le tour en append-only dans l'ordre réel : tool calls d'abord, réponse texte finale ensuite (elle est émise en `message_delta` mais pas dans `messages` pendant la boucle).

## Dettes et pièges constatés à la lecture

- `default=str` dans `_sse()` (`apps/backend/app/api/v1/endpoints/agent_chat.py:108`) : fusible de sérialisation. Un `datetime` brut dans le résultat d'un outil fait dégrader le champ au lieu de tuer le flux. Leçons de `fs_list` (datetime non sérialisable tuait le stream au milieu).
- Le `finally: task.cancel()` du `gen()` chat (`apps/backend/app/api/v1/endpoints/agent_chat.py:349`) coupe la boucle quand le client ferme l'onglet : sans elle, la boucle tournerait jusqu'à 24 tours en facturant le provider via une session DB déjà fermée.
- `emit_surveille` (`apps/backend/app/api/v1/endpoints/agent_chat.py:266`) intercepte les erreurs provider en mode gratuit pour traduire l'erreur technique en message actionnable (`_MESSAGE_SURCHARGE_GRATUIT`).
- `_tracer_etages` (`apps/backend/app/api/v1/endpoints/agent_fiche.py:133`) note les étages APRÈS le run, jamais pendant : la session DB est occupée par l'orchestrateur et deux opérations concurrentes font sauter SQLAlchemy.
- Les providers ne rendent jamais la clé en clair après création : le endpoint lit le résultat du service qui masque la valeur (`apps/backend/app/api/v1/endpoints/agent_providers.py:81`).
- `lister_modeles_provider` cache 15 min, `?refresh=true` force le rappel réseau (`apps/backend/app/api/v1/endpoints/agent_providers.py:180`).
