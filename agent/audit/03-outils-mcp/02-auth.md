# Authentification MCP (`auth.py`)

## apps/backend/app/mcp_server/auth.py
Lu intégralement : oui (102/102 lignes) · sha256: 45deacee73bd7 · date: 2026-08-25

Réutilise le même JWT que le REST (obtenu via `/auth/mcp-token`) : un secret, une seule classe d'expiration, une seule surface à protéger (`apps/backend/app/mcp_server/auth.py:8`). Le token voyage dans `Authorization: Bearer ...`.

### Symboles (5)

- `_user_depuis_token` — `apps/backend/app/mcp_server/auth.py:30` — décode JWT avec `verify_aud=False` (tokens OAuth portent `aud:"mcp"`, tokens `/auth/mcp-token` n'ont pas d'audience — sans ce flag, aucun token OAuth ne passe), résout `sub` → `User`, exclut les comptes supprimés (`deleted_at`).
- `_token_dans_l_entete` — `apps/backend/app/mcp_server/auth.py:51` — lit `Authorization` depuis `get_http_request()` ; retourne `None` hors contexte HTTP (tests unitaires).
- `bearer_exploitable` — `apps/backend/app/mcp_server/auth.py:61` — vérifie cryptographiquement un header bearer **sans** résoudre l'utilisateur (pas de DB). Utilisé par le middleware MCP pour décider s'il doit répondre 401 et déclencher la découverte OAuth côté client.
- `utilisateur_courant` — `apps/backend/app/mcp_server/auth.py:83` — résout le Bearer en `User | None` : les tools qui acceptent l'anonyme l'utilisent.
- `exiger_utilisateur` — `apps/backend/app/mcp_server/auth.py:89` — lève `ToolError` avec un message qui indique où trouver le token si absent/invalide. Tous les outils d'écriture l'appellent.
