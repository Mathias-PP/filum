# Sessions, historique et compaction (`agent_sessions.py`)

## apps/backend/app/services/agent_sessions.py
Lu intégralement : oui (313/313 lignes) · sha256: 5da96cb10578 · date: 2026-08-25

Tout est scopé par `creator_id` ; une session étrangère se lit « introuvable », jamais « interdite » (ne pas apprendre à un tiers qu'elle existe) (`apps/backend/app/services/agent_sessions.py:1`).

Constantes :

- `TITRE_MAX`=80 (`apps/backend/app/services/agent_sessions.py:21`).
- `BUDGET_HISTORIQUE`=96 000 tokens avant appel — tient dans les fenêtres 128k en laissant place au système/workspace/réponse ; pas de table de fenêtres par modèle (vieillirait mal) (`apps/backend/app/services/agent_sessions.py:28`).
- `BUDGET_APRES_REFUS`=6 000 tokens après refus explicite de fenêtre saturée — assez petit pour passer sur un modèle local à 8 000 sans connaître sa fenêtre à l'avance (`apps/backend/app/services/agent_sessions.py:33`).

### Symboles (16)

**Estimation et découpage**

- `_taille` — `apps/backend/app/services/agent_sessions.py:40` — coût approximatif d'un message : sérialisation JSON entière //4 +8 tokens (les arguments d'outils comptent ; marge d'encadrement de rôle).
- `taille_historique` — `apps/backend/app/services/agent_sessions.py:56` — somme des `_taille`.
- `_debuts_de_blocs` — `apps/backend/app/services/agent_sessions.py:61` — indices de coupure sûrs : un assistant porteur de `tool_calls` et les `tool` qui lui répondent forment un bloc indivisible.
- `_message_synthese` — `apps/backend/app/services/agent_sessions.py:83` — message system remplaçant le tronçon retiré : dit au modèle CE QUI LUI MANQUE (« demandez au créateur plutôt que de supposer ») — sans lui, le modèle comblerait le trou par déduction.
- `compacter` — `apps/backend/app/services/agent_sessions.py:100` — l'algorithme : si déjà sous budget → intouchable ; les `system` de tête sont TOUJOURS gardés (ils portent le comportement, pas la mémoire) ; le dernier bloc est toujours gardé même surdimensionné (couper la demande en cours rendrait la réponse absurde) ; coupes testées du plus ancien au plus récent jusqu'à tenir le budget ; jamais de coupe sur un `tool` en tête (historique bancal) ; si aucune coupe ne suffit → dernier recours = plus grande coupe possible. Retour (liste, nb retirés).

**CRUD sessions**

- `AgentSessionNotFoundError` — `apps/backend/app/services/agent_sessions.py:36`.
- `lister` — `apps/backend/app/services/agent_sessions.py:146` — sessions non supprimées, tri last_message_at desc nulls-last puis created_at desc.
- `creer` — `apps/backend/app/services/agent_sessions.py:155` — commit immédiat, titre par défaut « Nouvelle conversation ».
- `obtenir` — `apps/backend/app/services/agent_sessions.py:175` — scoped creator_id + non-supprimée, sinon NotFound.
- `messages` — `apps/backend/app/services/agent_sessions.py:189` — journal ordonné par created_at puis id (cohérent avec l'horodatage Python côté modèle).
- `ajouter_message` — `apps/backend/app/services/agent_sessions.py:199` — **append-only** (aucune mise à jour) ; met à jour `last_message_at` côté Python.
- `usage_session` — `apps/backend/app/services/agent_sessions.py:229` — somme SQL prompt/completion tokens ; `cost_eur` rendu None (pas encore tarifé).
- `mettre_a_jour` — `apps/backend/app/services/agent_sessions.py:279` — patch partiel (seuls les champs passés changent) ; titre vide normalisé « Nouvelle conversation » ; `model_override`/`agent_slug` vides → None.
- `supprimer` — `apps/backend/app/services/agent_sessions.py:309` — suppression LOGIQUE (`deleted_at`) : la trace reste.

**Rejeu vers le provider**

- `titre_depuis_message` — `apps/backend/app/services/agent_sessions.py:137` — titre coupé sur un mot à 80 chars, ellippe.
- `historique_pour_modele` — `apps/backend/app/services/agent_sessions.py:248` — remet le journal persisté au format provider : message `tool` avec `name`+`tool_call_id` si présent (lignes anciennes sans id : rejeu dégradé sur Gemini, correct ailleurs — le commentaire cite « migration 043 » mais la colonne arrive en 045) ; assistant avec tool_calls portés tels quels ; autres rôles simples.
