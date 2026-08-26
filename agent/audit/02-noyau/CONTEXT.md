# 02 — Noyau : boucle, approbations, sessions

> Fiches du lot 2 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G2** (`check_lot.sh 2`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

Le moteur : `boucle()` fait parler le modèle avec la clé BYOK déchiffrée à la volée, exécute les outils demandés via le registre (lot 3), suspend les actions sensibles derrière une approbation humaine, et persiste tout dans les tables du lot 1. `agent_sessions.py` porte la CRUD sessions/messages et **l'algorithme de compaction** ; `agent_approvals.py` le pont mémoire entre flux SSE et réponse humaine.

## Les fichiers

| Fiche | Contenu | Fichier |
|---|---|---|
| [01-boucle-agent.md](01-boucle-agent.md) | La boucle modèle↔outils : transport, retries, parsing SSE multi-providers, nettoyage d'historique, exécution des tours | `apps/backend/app/services/agent.py` (1074 l.) |
| [02-sessions.md](02-sessions.md) | CRUD sessions, append-only, budgets et compaction d'historique | `apps/backend/app/services/agent_sessions.py` (313 l.) |
| [03-approbations.md](03-approbations.md) | Futures en mémoire, délai 300 s, scoping par créateur | `apps/backend/app/services/agent_approvals.py` (70 l.) |

## Cycle de vie d'un tour (événements SSE dans l'ordre réel d'émission)

Séquence observée dans `boucle` + `_executer_tour` :

1. `message_delta` (`apps/backend/app/services/agent.py:987`) — chaque fragment texte du streaming, avec numéro de tour.
2. Si le modèle demande des outils, pour CHAQUE tool_call dans l'ordre :
   - `tool_call` (`apps/backend/app/services/agent.py:862`) — id, nom, arguments parsés, tour.
   - Si l'action est sensible (`est_sensible`, `apps/backend/app/services/agent.py:868`) :
     - `approval_request` (`apps/backend/app/services/agent.py:871`) avec `request_id` frais + `resume` calculé côté serveur ;
     - la boucle **s'arrête sur un Future** jusqu'à la réponse humaine (300 s max, sinon refus) ;
     - `approval_resolved` (`apps/backend/app/services/agent.py:884`) — verdict.
   - Exécution via le registre (refus simulé par dict d'erreur si non approuvé).
   - `tool_result` (`apps/backend/app/services/agent.py:898`) — résultat sérialisé (tronqué à `TOOL_RESULT_MAX`=120k).
3. Retour à l'étape 1 tant que le modèle redemande des outils et que le quota de tours n'est pas épuisé.
4. Fin possible :
   - texte sans tool_calls → `done` (`reason: complete`, usage cumulé) (`apps/backend/app/services/agent.py:1022`) ;
   - réponse vide → `error` avec diagnostic actionnable (`apps/backend/app/services/agent.py:1039`) ;
   - erreur provider/réseau → `error` avec message brut enrichi (`apps/backend/app/services/agent.py:1010`) ;
   - quota de tours atteint → compaction puis **`continuation`** (pause + reprise, pas une erreur) (`apps/backend/app/services/agent.py:1063`) ;
   - n'importe quand : `contexte_compacte` si la compaction a retiré des messages (`apps/backend/app/services/agent.py:979`).

## Invariants du lot

- **9 événements SSE émis depuis la boucle** : `message_delta`, `tool_call`, `approval_request`, `approval_resolved`, `tool_result`, `contexte_compacte`, `done`, `error`, `continuation` (les 12 de l'invariant G0 incluent ceux des endpoints, lot 4).
- **Borne de tours** : `quota_tours` de l'agent nommé si défini, sinon `MAX_TOURS` = `agent_max_tours` (48, figé au démarrage du module `apps/backend/app/services/agent.py:61`).
- **Budgets de compaction** : `BUDGET_HISTORIQUE`=96 000 tokens avant appel ; `BUDGET_APRES_REFUS`=6 000 après refus explicite « fenêtre saturée », rejeu unique (`apps/backend/app/services/agent_sessions.py:28`,`33` ; `apps/backend/app/services/agent.py:998`).
- **Délai d'approbation** : 300 s → refus automatique (`apps/backend/app/services/agent_approvals.py:29`).

## Dettes et pièges constatés à la lecture

- `MAX_TOURS`/`MAX_TURN_TOKENS` sont **lus une fois au niveau module** (`apps/backend/app/services/agent.py:61`) : changer la variable d'env exige un redémarrage, contrairement aux réglages consultés via `get_settings()` à l'appel.
- Le message de `continuation` affiche toujours `MAX_TOURS` même quand un agent nommé a un `quota_tours` différent (`apps/backend/app/services/agent.py:1067`).
- L'attente d'approbation vit **en mémoire process** : un restart pendant une demande = flux mort, pas de reprise (voulu, cf. fiche 03).
- `historique_pour_modele` mentionne « migration 043 » pour les lignes anciennes sans `tool_call_id` (`apps/backend/app/services/agent_sessions.py:256`) alors que la colonne arrive en **045** — commentaire imprécis, comportement correct.
