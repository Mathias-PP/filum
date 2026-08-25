# Approbations humaines en attente (`agent_approvals.py`)

## apps/backend/app/services/agent_approvals.py
Lu intégralement : oui (70/70 lignes) · sha256: df7f945a81eb · date: 2026-08-25

Mécanisme : la boucle émet `approval_request` puis **s'arrête sur un `asyncio.Future`** ; le endpoint `POST /agent/approve` (lot 4) appelle `resoudre`, ce qui débloque la boucle exactement où elle s'était arrêtée (`apps/backend/app/services/agent_approvals.py:1`).

Choix d'architecture assumé en tête de fichier : l'attente vit **en mémoire du processus, pas en base**, et ne survit volontairement pas à un redémarrage — une demande orpheline dont personne ne se souvient est pire qu'un refus, et le flux SSE qui l'attendait est mort avec le processus. Le dict de module suffit car le moteur tourne in-process sur un worker unique (contrainte e2-micro) (`apps/backend/app/services/agent_approvals.py:8`).

Sécurité : le `creator_id` est stocké avec chaque attente — sans lui, connaître un `request_id` suffirait à approuver la publication d'un autre créateur (`apps/backend/app/services/agent_approvals.py:15`).

Constante : `DELAI_MAX`=300 s (`apps/backend/app/services/agent_approvals.py:29`) — un onglet fermé ne doit pas laisser un Future immortel retenir une tâche et une session DB.

État module : `_EN_ATTENTE: dict[request_id, tuple[creator_id, Future]]` (`apps/backend/app/services/agent_approvals.py:31`).

### Symboles (5)

- `ApprovalInconnueError` — `apps/backend/app/services/agent_approvals.py:34` — levée par `resoudre` ; message IDENTIQUE que la demande n'existe pas ou appartienne à un autre créateur (distinguer les deux dirait à un tiers qu'une demande existe, ligne 52).
- `enregistrer` — `apps/backend/app/services/agent_approvals.py:38` — crée le Future sur la boucle courante et l'inscrit.
- `oublier` — `apps/backend/app/services/agent_approvals.py:44` — retire une attente sans erreur si absente.
- `resoudre` — `apps/backend/app/services/agent_approvals.py:48` — vérifie existence + propriété, pose le verdict si le Future n'est pas déjà résolu, désinscrit.
- `attendre` — `apps/backend/app/services/agent_approvals.py:61` — côté boucle : enregistre, attend avec `asyncio.wait_for(delai=DELAI_MAX)` → False au-delà (refus), et **toujours** `oublier` dans un finally (pas de fuite d'attente).

Contrat inter-lots : appelé par `_executer_tour` via le callback `Approuver` injecté par l'endpoint chat (lot 4) qui branche `attendre` ; alimenté par l'endpoint approve (lot 4) qui appelle `resoudre`.
