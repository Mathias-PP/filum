# Guide de code — Philum

> Règles techniques stables : stack, principes, conventions de nommage, structure attendue, format de réponse, MCP servers utiles. Extrait de `CLAUDE.md` (2026-08-17) pour ramener l'entry file à sa vocation de routage.
>
> Cette page est la **référence** ; les fichiers d'entrée (`CLAUDE.md`, `AGENTS.md`, `agent/README.md`) pointent ici quand une décision technique doit être vérifiée.

---

## Stack — non négociable sauf ADR explicite

| Couche | Choix | Alternative refusée |
|---|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.x async, Alembic | pas de blocking I/O en route async |
| BDD transactionnel | PostgreSQL (Supabase en prod, local en dev) | — |
| Analytics | DuckDB + dbt-core | — |
| Crypto | `cryptography` (Ed25519, AES-GCM, SHA-256) | pas de `pycryptodome` |
| Frontend | SvelteKit 2, Svelte 5, TypeScript strict, Tailwind | pas de CSS-in-JS, pas de MUI, pas de framework UI lourd |
| Tests | `pytest` (backend), `vitest` (frontend) | — |
| Lint / format | `ruff` (backend), `prettier` + `eslint 9` (frontend) | — |
| Package manager | `uv` (Python), `pnpm 10.33.4` pinned (Node) | pnpm 11 casse la CI |
| Déploiement | VM GCP e2-micro (backend + Postgres via Supabase), Vercel (frontend) | plus de Railway (ADR-028) |
| LLM | LiteLLM proxy (voir `.docs/17-llm-strategy.md`) | pas d'appel direct provider en dur |

Une nouvelle dépendance = une justification dans la conversation.

---

## Principes de code

1. **Préférer la simplicité à l'élégance.** Pré-MVP, pas d'architecture entreprise. Pas de factories à plusieurs niveaux, pas de repositories en cascade. Du code direct, lisible.
2. **Async par défaut côté backend.** Toutes les routes FastAPI async, toutes les sessions SQLAlchemy async.
3. **Typage strict.** Python : `from __future__ import annotations` + Pydantic v2 + type hints partout. Frontend : TypeScript strict.
4. **Tests pour le code qui compte.** Pas de coverage 100 % obsessif, mais tester systématiquement : calculs de hash, génération de signatures, endpoints qui modifient des données, logique d'extraction des sources.
5. **Commits petits et descriptifs.** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`), titre ≤ 50 caractères.
6. **Migrations versionnées.** Toute modification de schéma passe par Alembic. Jamais de `db.create_all()` sauf dans les tests.
7. **Pas de secrets en dur.** Variables d'environnement via `.env` (jamais commit) et `.env.example` complet et à jour.
8. **Documentation au fil de l'eau.** Décision technique non triviale → une entrée dans `DECISIONS.md`. Feature terminée → mise à jour de `STATE.md`.

---

## Conventions de nommage

- **Fichiers Python** : `snake_case.py`
- **Fichiers Svelte** : `kebab-case.svelte` pour les composants partagés, `+page.svelte` pour les routes
- **Modèles SQLAlchemy** : `PascalCase` (`User`, `BiblioCard`, `Source`)
- **Tables Postgres** : `snake_case` au pluriel (`users`, `biblio_cards`, `sources`)
- **Routes API** : `kebab-case`, REST, pluriel (`/api/biblio-cards`, `/api/sources`)
- **Variables d'environnement** : `snake_case` lowercase (ADR-010 — `case_sensitive=True` dans pydantic-settings impose le lowercase ; UPPERCASE = silent fallback aux défauts sur Linux/CI)
- **Branches Git** : `feat/<sujet>`, `fix/<sujet>`, `docs/<sujet>`, `chore/<sujet>`, `refactor/<sujet>`, `test/<sujet>`
- **Migrations Alembic** : `NNN_<courte-description>` avec `NNN` ≤ 32 caractères total (cf. `agent/PITFALLS.md` §1.1)

---

## Structure du repo

```
philum/
├── README.md, CLAUDE.md, AGENTS.md, CONTRIBUTING.md, SECURITY.md, SETUP.md
├── STATE.md, DECISIONS.md, CHANGELOG.md         # documents vivants
├── Makefile
├── .docs/                                        # specs (00-09 figées, ≥10 vivantes)
├── .env.example
├── agent/                                        # instructions agent autonome
│   ├── README.md, PERMISSIONS.md, GIT_WORKFLOW.md, SECURITY.md,
│   │   PITFALLS.md, TASK_PROTOCOL.md, CONFIG.md
│   ├── memory/INDEX.md
│   ├── references/                               # règles techniques stables (dont ce fichier)
│   ├── reports/                                  # rapports ponctuels datés (walkthroughs, audits)
│   ├── skills/                                   # skills spécialisées
│   ├── plans/                                    # plans actifs (les exécutés → _archive/)
│   └── research/                                 # études techniques
├── apps/
│   ├── backend/                                  # FastAPI async
│   │   ├── pyproject.toml, alembic.ini
│   │   ├── app/
│   │   │   ├── main.py                           # entry point FastAPI
│   │   │   ├── core/config.py                    # settings via pydantic-settings
│   │   │   ├── db/database.py                    # session SQLAlchemy async + Base
│   │   │   ├── models/                           # SQLAlchemy models
│   │   │   ├── schemas/                          # Pydantic schemas
│   │   │   ├── api/v1/endpoints/                 # routers FastAPI
│   │   │   ├── services/                         # logique métier
│   │   │   ├── crypto/                           # hash, signature, keygen, AES-GCM
│   │   │   ├── extractors/                       # oracles d'extraction (Crossref, Wikipedia, PMC,
│   │   │   │                                     #   GROBID, S2, section detector, ref dedup,
│   │   │   │                                     #   ref scorer, open access, retraction)
│   │   │   └── mcp_server/                       # serveur MCP (lecture + écriture, auth par JWT)
│   │   ├── tests/unit/                           # tests unitaires
│   │   ├── tests/integration/                    # tests endpoints HTTP
│   │   └── alembic/                              # migrations
│   ├── frontend/                                 # SvelteKit
│   │   ├── package.json
│   │   └── src/{routes, lib/{components, stores, api, utils}}
│   ├── extension/                                # extension navigateur (ajout de source)
│   └── analytics/                                # dbt project sur DuckDB
├── infra/                                        # Docker, scripts de déploiement (VM GCP)
└── scripts/                                      # setup, dumps, migrations one-shot
```

---

## Format de réponse à l'utilisateur

- Concis. Pas de paraphrase de la demande.
- Modifications de plusieurs fichiers : plan court d'abord, exécution ensuite.
- Commandes lancées : une phrase pour expliquer ce qu'elles font.
- Bug ou incohérence détectés : les signaler, ne pas les contourner en silence.
- Français partout : prose, commentaires de code, messages de commit, corps des PR, UI.
- Jamais de tiret cadratin (« — »).

---

## MCP servers utiles pour ce projet

- **filesystem** : indispensable, lecture/écriture de fichiers
- **git** : commits, branches, log
- **gitmcp** : consulter des repos de référence (`c2pa-rs`, `internetarchive`, `icm-architect`, etc.)
- **obsidian** : si l'auteur tient ses notes projet dans Obsidian, utile pour consulter le contexte
- **philum** (interne) : le serveur MCP du projet lui-même expose `search_cards`, `get_card`, `get_source`, `find_cards_citing`, `whoami`, `create_card`, `add_source`, `add_excerpt`, `publish_card`. Voir `apps/backend/app/mcp_server/`.

Les autres (Docker Hub, Kubernetes, n8n, Notion) ne sont **pas** pertinents pour ce projet. S'ils sont actifs, ignorer leurs tools.

---

## Debug d'un bug prod : instrumenter avant de spéculer

Leçon payée 4 PRs (#33-#36, mai 2026) : un bug publish a été chassé pendant 4 itérations parce que le symptôme côté navigateur (`Failed to fetch` + erreur CORS) ne reflétait pas la vraie cause (`asyncpg.DataError` sur datetime tz-aware).

**Règle** : quand un bug prod résiste à 1 fix, arrête de patcher et instrumente. Ajoute un endpoint `/health/<feature>-diagnose` qui exerce le code path sans auth (sur des données de seed) et retourne le traceback brut. C'est l'endpoint qui a finalement révélé la vraie cause.

Quand un utilisateur reporte `TypeError: Failed to fetch` ou « blocked by CORS policy » alors que le 401 / OPTIONS preflight ont des headers CORS corrects : le bug est **dans le code path authentifié**, généralement une exception SQLAlchemy qui corrompt la session, et le commit post-yield de `get_db` retente sur session morte → réponse interrompue mid-stream → header CORS jamais finalisé.

Cas vécu détaillé : `agent/PITFALLS.md` §1.5.

---

## Choses à ne PAS faire

- Ajouter une dépendance sans le signaler.
- Déployer sans autorisation explicite (les déploiements autonomes sont autorisés depuis le 2026-08-08 hors actions destructives — cf. mémoire projet locale).
- Modifier `.docs/00` à `.docs/09` sans demande explicite. Ce sont des spécifications de référence figées.
- Créer des fichiers de configuration redondants (par ex. plusieurs `.eslintrc`). Une seule source de vérité.
- Utiliser du CSS-in-JS, des composants Material UI, ou un framework UI lourd. Tailwind + composants Svelte custom.
- Générer du code obfusqué ou prématurément optimisé. Lisibilité d'abord.
- Proposer des fonctionnalités hors scope du MVP sans le mentionner explicitement.
