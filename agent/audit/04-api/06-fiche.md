# Run de fiche — orchestration multi-étages SSE (`agent_fiche.py`)

## apps/backend/app/api/v1/endpoints/agent_fiche.py
Lu intégralement : oui (144/144 lignes) · sha256: 75ec25674c3e · date: 2026-08-25

Le lancement est un endpoint plutôt qu'un outil : sept boucles enchaînées coûtent cher, l'utilisateur doit voir ce qu'il déclenche (`apps/backend/app/api/v1/endpoints/agent_fiche.py:9`).

### Routes (2)

| Méthode | Route | Fonction | Description |
|---|---|---|---|
| `GET` | `/agent/fiche/{slug}` | `etat_fiche` | Où en est le run : quels étages ont déposé leur compte rendu |
| `POST` | `/agent/fiche` | `lancer_fiche` | Lance le run, rend un flux SSE avec événements `stage_start`, `stage_done`, `stage_failed` en plus de ceux de la boucle |

### Flux

`lancer_fiche` (`apps/backend/app/api/v1/endpoints/agent_fiche.py:56`) :
1. Résout le provider par défaut (erreur 400 si aucun).
2. Crée une session avec titre `Fiche : {slug}`.
3. Ajoute un message user décrivant l'intention.
4. Lance `agent_fiche.lancer()` dans une tâche async.
5. Les `stage_done` sont accumulés dans `franchis`.
6. **Après le run** (jamais pendant) : `_tracer_etages` écrit les étages franchis dans le journal de la session.

### `_tracer_etages` — `apps/backend/app/api/v1/endpoints/agent_fiche.py:133`

Note les étages franchis en append-only. L'écriture est **post-run** : la session DB est occupée par l'orchestrateur, et deux opérations concurrentes dessus font sauter SQLAlchemy (`apps/backend/app/api/v1/endpoints/agent_fiche.py:119-121`).

### `_sse` — `apps/backend/app/api/v1/endpoints/agent_fiche.py:40`

Variante simplifiée (sans `default=str`) du `_sse` du chat — les événements de fiche sont connus et contrôlés.
