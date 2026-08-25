# 03 — Outils MCP : serveur, auth, compat schéma, catalogues read/write

> Fiches du lot 3 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G3** (`check_lot.sh 3`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

Le pont entre les agents IA et la base Philum. Le serveur FastMCP (`server.py`) déclare **45 outils MCP** (43 dans l'invariant gelé + 2 outils graphe mémoire ajoutés après gel, statut `STARTER`) : 5 en lecture seule (`tools.py`), 40 en écriture (`tools_write.py`). L'auth (`auth.py`) réutilise le même JWT que le REST ; le `schema_compat.py` résout un bug Gemini qui refuse les schémas contenant `anyOf`.

**Dérive d'invariant constatée** : l'invariant G0 dénombre 43 outils MCP, mais le code en registre 45 au moment de la lecture (2026-08-25). Les deux outils supplémentaires sont `recall_memory` et `rebuild_graph` (graphe mémoire, imports retardés dans `server.py`). Ils sont balisés `# STARTER` et ne sont pas encore exposés dans la fenêtre `tools` de l'agent nommé par défaut. Cette fiche documente les 45 comme ils existent dans le code ; l'invariant G0 doit être mis à jour lors de la prochaine passe `gen_inventaire.sh`.

## Les fichiers

| Fiche | Contenu | Fichier |
|---|---|---|
| [01-serveur.md](01-serveur.md) | Serveur FastMCP, enregistrement des 45 outils, décorateur `outil()`, `mcp_http_app` | `apps/backend/app/mcp_server/server.py` (758 l.) |
| [02-auth.md](02-auth.md) | JWT bearer, `exiger_utilisateur`, `utilisateur_courant`, `bearer_exploitable` | `apps/backend/app/mcp_server/auth.py` (102 l.) |
| [03-schema-compat.md](03-schema-compat.md) | Aplatissement `anyOf: [T, null]` → `T` pour validateurs Gemini | `apps/backend/app/mcp_server/schema_compat.py` (39 l.) |
| [04-tools-read.md](04-tools-read.md) | 5 outils read-only : `search_cards`, `get_card`, `get_source`, `find_cards_citing`, `whoami` | `apps/backend/app/mcp_server/tools.py` (258 l.) |
| [05-tools-write.md](05-tools-write.md) | 40 outils d'écriture, catalogue exhaustif avec catégories, approbation, pièges | `apps/backend/app/mcp_server/tools_write.py` (1876 l.) |

## Invariants du lot

- **45 outils MCP** enregistrés dans `apps/backend/app/mcp_server/server.py` (43 + 2 graphe STARTER) — **à rapprocher de l'invariant gelé 43**.
- `_EXTRAITS_MAX_PAR_SOURCE`=12 (`apps/backend/app/mcp_server/tools_write.py:48`).
- `_MAX_CONTENT_TEXT`=500 000 chars (`apps/backend/app/mcp_server/tools_write.py:514`).
- `CONTENU_MAX`=20 000 chars pour le rendu tronqué de `get_my_card` (`apps/backend/app/mcp_server/tools_write.py:1119`).
- `_PUBLIC` (`apps/backend/app/mcp_server/tools.py:32`) : seul filtre pour la surface anonyme = `status == "published" & visibility == "public" & deleted_at IS NULL`. Les brouillons et fiches privées ne sont jamais rendus par les outils read-only.
- Auth : `verify_aud=False` sur tous les appels JWT (`apps/backend/app/mcp_server/auth.py:42`) — tokens OAuth portent `aud:"mcp"`, tokens `/auth/mcp-token` n'ont pas d'audience ; sans ce flag, aucun token OAuth ne passe.

## Dettes et pièges constatés à la lecture

- **Dérive invariant** : l'invariant G0 dit 43, le code 45. Il faut relancer `gen_inventaire.sh` après ce lot.
- `_valeur_enum` (`apps/backend/app/mcp_server/tools_write.py:60`) valide les enums à l'entrée pour éviter les colonnes VARCHAR libres qui rendent la fiche entière illisible à la relecture (`SourceResponse`). Leçon de la fiche créatine (2026-08-21, cf. PITFALLS).
- `_fiche_du_createur` et `_source_du_createur` refusent de dire « existe mais pas à vous » : révéler l'existence d'une fiche/source privée d'un autre créateur serait une fuite d'information (`apps/backend/app/mcp_server/tools_write.py:121`, `:153`).
- `import_from_content_url` construit un `fake_request` FastAPI (`SimpleNamespace`) pour contourner le rate-limit slowapi côté MCP (`apps/backend/app/mcp_server/tools_write.py:1533`).
- `verify_excerpts` importe `_texte_de_la_source` depuis l'endpoint REST (`apps/backend/app/mcp_server/tools_write.py:947`) : dépendance transversale endpoint↔MCP.
- Le `delete_card` soft-delete affecte la fiche ET ses sources, mais les attestations et citations restent en base (`apps/backend/app/mcp_server/tools_write.py:1295`).
