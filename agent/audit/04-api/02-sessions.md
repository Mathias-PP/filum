# Sessions et approbations — endpoints (`agent_sessions.py`)

## apps/backend/app/api/v1/endpoints/agent_sessions.py
Lu intégralement : oui (163/163 lignes) · sha256: 6bfdd705d256 · date: 2026-08-25

### Routes (8)

| Méthode | Route | Fonction | Rate-limit | Description |
|---|---|---|---|---|
| `GET` | `/agent/sessions` | `lister_sessions` | non | Sessions non supprimées du créateur |
| `POST` | `/agent/sessions` | `creer_session` | oui | Crée une session (title, provider_id, agent_slug) |
| `GET` | `/agent/sessions/{session_id}` | `lire_session` | non | Détail d'une session |
| `PATCH` | `/agent/sessions/{session_id}` | `mettre_a_jour_session` | oui | Renomme, change provider/modèle/agent |
| `GET` | `/agent/sessions/{session_id}/messages` | `lister_messages` | non | Journal ordonné des messages |
| `DELETE` | `/agent/sessions/{session_id}` | `supprimer_session` | non | Suppression logique (corbeille) |
| `GET` | `/agent/sessions/{session_id}/usage` | `usage_session` | non | Tokens cumulés (prompt + completion) |
| `POST` | `/agent/approve` | `repondre_approbation` | oui | Débloque la boucle SSE sur `request_id` |

### `POST /agent/approve` — `apps/backend/app/api/v1/endpoints/agent_sessions.py:149`

L'autre moitié du flux SSE. La boucle s'est arrêtée sur un `approval_request` (lot 2.1), ce endpoint la relance via `agent_approvals.resoudre(request_id, creator_id, approved)`. La réponse est 204 No Content : le client n'a pas besoin de lire le verdict, la boucle reprend de l'autre côté. `ApprovalInconnueError` → 404 (message identique que la demande n'existe pas ou appartienne à un autre créateur).
