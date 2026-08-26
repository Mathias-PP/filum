# 07-03 — Tests unitaires (14 fichiers, ~6 400 LOC)

> **Fiche du lot 7.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G7**.
> **Dossier :** `apps/backend/tests/unit/` (14 fichiers).

## Rôle

Tests unitaires de la couche agent : boucle principale (texte, tool_call, approval, 429, retry, Gemini, compaction), providers BYOK (masquage, validation, test clé, cache), sessions (CRUD, compaction), discovery (quota, provider transient), fiche (7 étages ICM), workspace (normalisation, seed, frontmatter), outils MCP (lecture, écriture), auth MCP, schéma MCP, catalogue Philum.

## Fichiers

| Fichier | LOC | sha256 | Symboles | Contenu |
|---|---|---|---|---|
| `apps/backend/tests/unit/test_agent_loop.py` | 1502 | sha256: df2ae584da0c62ece757926b5b1888a82d88c279a7057e15f324bd3c306c6639 | 14 | Boucle agent : texte, tool_call, approval, 429, retry, Gemini, compaction, priming |
| `apps/backend/tests/unit/test_agent_providers.py` | 693 | sha256: b84ab4db0d471995613a4f1fb23c71e2ff884f0069d64abc279e80d720546b06 | 14 | Providers : masquage, validation, test clé, CRUD, cache modèles |
| `apps/backend/tests/unit/test_agent_sessions.py` | 222 | sha256: 463dd121a08816a663e530f2ef2692ff4fee599c05ccce1c89cf2d9283000889 | 7 | Sessions : titre, CRUD, approbations, compaction |
| `apps/backend/tests/unit/test_agent_discovery.py` | 158 | sha256: 6f104f07489d638acd1795d304e46351d44d73ce0779b285379cb8b3dcca28ba | 14 | Discovery : enabled/disabled, noms publics, quota, idempotence |
| `apps/backend/tests/unit/test_agent_fiche.py` | 240 | sha256: 9501b6b23334b87c4bbad19f93d21142dfea7710b45d9c9930af73ac00858db4 | 9 | Fiche : étapes ICM, lancement, état |
| `apps/backend/tests/unit/test_agent_definitions.py` | 142 | sha256: 9fabc0e5f41d49ca6c5a75354f81bc950268a7473db66077265761cd3a14a16b | 9 | Définitions : parsing YAML, validation, listing |
| `apps/backend/tests/unit/test_agent_workspace.py` | 245 | sha256: b5c94def718f5cd3ba2b4cb2ea513e2a4a81d752c1263bbc234b23ea97aa831b | 15 | Workspace : normalisation, CRUD, seed, frontmatter |
| `apps/backend/tests/unit/test_agent_tools.py` | 156 | sha256: b6f7bbf97b7805f78ac2d1d854ec5f65d3dbd52f1a64b65799a8f6f8a1162d37 | 4 | Outils : isolation workspace, isolation fiches |
| `apps/backend/tests/unit/test_agent_gratuit.py` | 418 | sha256: 98dd6717559808bfd75f6d34d89f3bcfe1c62db4e9ea7e8aa5721b8d34e2190d | 10 | Mode gratuit : consentement, lanes, quotas, modèles |
| `apps/backend/tests/unit/test_agent_philum_catalogue.py` | 182 | sha256: 50fb74248f932015cfbfbe40b2c2e204e71b211e896cbad78bafe5f6656d46d6 | 4 | Catalogue Philum : complétude, descriptions, schémas |
| `apps/backend/tests/unit/test_mcp_auth.py` | 122 | sha256: 1f274771cb4087e29104e82286f0d301d8a48a7980d1c47d6a64db04aac65334 | 10 | Auth MCP : tokens, expiration, OAuth |
| `apps/backend/tests/unit/test_mcp_mount.py` | 136 | sha256: ea14346563cf7fcd3878e8b8e21d4e0e6b62ffca4ab0824a59c6f3877146d222 | 11 | Montage MCP : routes, rate limit, well-known |
| `apps/backend/tests/unit/test_mcp_schema_compat.py` | 50 | sha256: 5a18a770065f766d826d31fabd790a9963094086d3c9344d10cfb72936ca3d9d | 2 | Compat schéma : flattening nullable |
| `apps/backend/tests/unit/test_workspace_seed_sync.py` | 53 | sha256: dee26785c82fd4f40c9a0885d3c489a566851fcebf3be15293095e9a1a9e148c | 3 | Sync seed : fichiers attendus, identité |

## Fichiers MCP écriture (couverts par la fiche dédiée)

| Fichier | LOC | sha256 | Symboles |
|---|---|---|---|
| `apps/backend/tests/unit/test_mcp_tools.py` | 715 | sha256: 5e6646fa2e9dde24f07ce1cf917ffc1e415d93e905800ff0cf09ef4956011e8c | 40 |
| `apps/backend/tests/unit/test_mcp_tools_write.py` | 1371 | sha256: a33d4dd85e8074d2b56f3da5aee7da8fdbd2acd985cc22012f97cec729bd0d93 | 81 |

## Invariants

- **isolation** : tous les tests utilisent `db_session` + `test_user` fixtures — pas d'état partagé entre tests.
- **mocks** : `httpx.MockTransport` pour simuler les appels fournisseur — pas de vrai réseau.
- **seed sync** : `test_workspace_seed_sync.py` vérifie que `agent_workspace_seed/` == `workspaces/createur-de-fiches/` (à exclusions près).

## Dettes

- `test_agent_loop.py` (1 502 LOC) : 9 classes, 15 définitions top-level — gros fichier qui pourrait être décomposé.
- `test_mcp_tools_write.py` (1 371 LOC) : 81 symboles tous module-level — pytest natif sans structure de groupe.
