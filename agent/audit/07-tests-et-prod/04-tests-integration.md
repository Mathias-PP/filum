# 07-04 — Tests intégration API (7 fichiers, ~1 400 LOC)

> **Fiche du lot 7.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G7**.
> **Dossier :** `apps/backend/tests/integration/` (7 fichiers).

## Rôle

Tests d'intégration API : testent les endpoints HTTP complets avec `httpx.AsyncClient`, couvrant l'authentification, la CRUD sessions/providers, le chat SSE, le mode gratuit, les définitions, la fiche ICM, et le workspace.

## Fichiers

| Fichier | LOC | sha256 | Symboles | Contenu |
|---|---|---|---|---|
| `apps/backend/tests/integration/test_agent_chat_api.py` | 206 | sha256: 1312631f1cbc733d09e12f18990cd1a68913c46e751a6e316ede9e30eaa5c5d9 | 13 | Chat : auth, provider défaut, flux complet, action sensible |
| `apps/backend/tests/integration/test_agent_sessions_api.py` | 198 | sha256: 1c79be37c256d478b56a7ab5b0d616a33beba52f92b805f39ae25d102c5de52e | 14 | Sessions : CRUD, tour persisté, approbation |
| `apps/backend/tests/integration/test_agent_providers_api.py` | 321 | sha256: 447b8908d465d38ebc0a52dfa9bed1e0dfc62a7847a22609294f1baef932b215 | 20 | Providers : CRUD, masquage, isolation, test clé |
| `apps/backend/tests/integration/test_agent_mode_gratuit_api.py` | 263 | sha256: 9cf3543972d20b8a7a2012da260adb379ca82f7eef00a05f454e49bb7acec4bd | 13 | Mode gratuit : état, consentement, testeur, modèles, chat |
| `apps/backend/tests/integration/test_agent_definitions_api.py` | 91 | sha256: 448517a4672f45494b04596bfb6ef380ffa73b14783ccb4890223926d6956d47 | 7 | Définitions : auth, listing seed, obtention, rejet |
| `apps/backend/tests/integration/test_agent_fiche_api.py` | 167 | sha256: 06632dd2e2becad484342b78fa4a1efae97f2235f50f0deba953702216dd2e4c | 14 | Fiche : auth, lancement, slug invalide, run complet, état |
| `apps/backend/tests/integration/test_agent_workspace_api.py` | 165 | sha256: bf272cb3da89765c00f8456885db6cc6ab41164d99a5a8e86d39e0b2203101dd | 11 | Workspace : auth, tree seed, CRUD fichiers, isolation |

## Invariants

- **Auth** : tous les endpoints protégés testent d'abord `401 sans token`, puis `200 avec token`.
- **Isolation** : `test_isolation_entre_createurs` vérifie qu'un utilisateur ne voit pas les données d'un autre.
- **Rate limit** : `_reset_limiter()` dans chaque fichier pour éviter les faux positifs.
- **Pas de vrai réseau** : `httpx.MockTransport` pour simuler les appels LLM.

## Dettes

- Pas de test de performance (latence SSE) — les tests vérifient la correction, pas la vitesse.
- `_reset_limiter()` est dupliqué dans chaque fichier — pourrait être un fixture partagé.
