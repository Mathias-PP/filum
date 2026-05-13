# Instructions pour Claude Code

Ce fichier est lu automatiquement par Claude Code au démarrage de chaque session. Il contient les règles et conventions à respecter sur le projet Filum.

---

## Le projet en deux phrases

Filum est une infrastructure ouverte qui permet aux créateurs de contenu (vulgarisateurs scientifiques d'abord, puis journalistes et chercheurs) de transformer leur bibliographie en une fiche publique navigable, avec sources horodatées et signées cryptographiquement. La vision long terme est de devenir la couche standard de citation du web à l'ère de l'IA générative.

Pour le détail, lire dans cet ordre : [`README.md`](./README.md) → [`.docs/00-vision.md`](.docs/00-vision.md) → [`.docs/01-product-spec.md`](.docs/01-product-spec.md) → [`.docs/02-tech-architecture.md`](.docs/02-tech-architecture.md).

---

## Stack et choix techniques (non négociables sauf décision explicite)

- **Backend** : Python 3.12, FastAPI, SQLAlchemy 2.x (mode async), Alembic pour migrations
- **Bases de données** : PostgreSQL pour le transactionnel, DuckDB pour les analytics
- **Transformations data** : dbt-core sur DuckDB
- **Frontend** : SvelteKit (Svelte 5) en TypeScript, Tailwind CSS, pas de framework UI lourd
- **Crypto** : `cryptography` (Python) — pas de `pycryptodome`
- **Tests** : `pytest` côté backend, `vitest` côté frontend
- **Lint et format** : `ruff` (backend), `prettier` + `eslint` (frontend)
- **Package manager Python** : `uv` (très rapide, remplace pip)
- **Package manager Node** : `pnpm`
- **Déploiement cible MVP** : Railway pour le backend, Vercel ou Netlify pour le frontend

Ne propose pas de changer de stack sans discussion. Si tu détectes un problème, signale-le et attends.

---

## Principes de code

1. **Préférer la simplicité à l'élégance.** On est en pré-MVP, pas en architecture entreprise. Pas de patterns sur-conçus (factories à plusieurs niveaux, repositories en cascade, etc.). Du code direct, lisible.

2. **Async par défaut côté backend.** Toutes les routes FastAPI sont async, toutes les sessions SQLAlchemy sont async. Pas de blocking I/O dans une route async.

3. **Typage strict.** Côté Python, `from __future__ import annotations` + Pydantic v2 + type hints partout. Côté frontend, TypeScript strict.

4. **Tests pour le code qui compte.** Pas de coverage 100% obsessif, mais tester systématiquement : les calculs de hash, la génération de signatures, les endpoints qui modifient des données, la logique d'extraction des sources.

5. **Commits petits et descriptifs.** Conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`). Pas plus de 50 caractères au titre.

6. **Migrations versionnées.** Toute modification de schéma passe par Alembic. Jamais de `db.create_all()` sauf dans les tests.

7. **Pas de secrets en dur.** Variables d'environnement via `.env` (jamais commit) et un `.env.example` complet et à jour.

8. **Documentation au fil de l'eau.** Quand tu prends une décision technique non triviale, ajoute une entrée dans `DECISIONS.md`. Quand tu termines une feature, mets à jour `STATE.md`.

---

## Conventions de nommage

- **Fichiers Python** : `snake_case.py`
- **Fichiers Svelte** : `kebab-case.svelte` pour les composants partagés, `+page.svelte` pour les routes
- **Modèles SQLAlchemy** : `PascalCase` (`User`, `BiblioCard`, `Source`)
- **Tables Postgres** : `snake_case` au pluriel (`users`, `biblio_cards`, `sources`)
- **Routes API** : `kebab-case`, REST, pluriel (`/api/biblio-cards`, `/api/sources`)
- **Variables d'environnement** : `snake_case` lowercase (cf. ADR-010 — `case_sensitive=True` dans pydantic-settings impose le lowercase ; UPPERCASE = silent fallback aux défauts sur Linux/CI)
- **Branches Git** : `feat/<sujet>`, `fix/<sujet>`, `docs/<sujet>`

---

## Structure attendue du projet

```
filum/
├── README.md
├── CLAUDE.md, AGENTS.md
├── STATE.md, DECISIONS.md, CHANGELOG.md
├── Makefile
├── .docs/                       # specs (lecture seule pour Claude Code en pratique)
├── .env.example
├── apps/
│   ├── backend/                 # FastAPI app
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── app/                 # source root (PAS src/filum_api/)
│   │   │   ├── main.py          # entry point FastAPI
│   │   │   ├── core/config.py   # settings via pydantic-settings
│   │   │   ├── db/database.py   # session SQLAlchemy async + Base
│   │   │   ├── models/          # SQLAlchemy models (User, BiblioCard, Source, AuditEvent)
│   │   │   ├── schemas/         # Pydantic schemas
│   │   │   ├── api/v1/endpoints/  # routers FastAPI (auth, cards, sources, users)
│   │   │   ├── services/        # logique métier (auth, card, wayback)
│   │   │   ├── crypto/          # hash, signature, keygen, AES-GCM
│   │   │   └── extractors/      # ⚠️ vide — extraction URL→métadonnées non implémentée
│   │   ├── tests/unit/          # tests unitaires (auth, crypto, schemas)
│   │   ├── tests/integration/   # tests endpoints HTTP (auth /me, /logout)
│   │   └── alembic/             # migrations
│   ├── frontend/                # SvelteKit app
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── routes/
│   │   │   ├── lib/
│   │   │   │   ├── components/
│   │   │   │   ├── stores/
│   │   │   │   └── api/         # client API typé
│   │   │   └── app.html, app.css
│   │   └── tests/
│   └── analytics/               # dbt project
│       ├── dbt_project.yml
│       ├── profiles.yml
│       └── models/
│           ├── staging/
│           ├── marts/
│           └── analytics/
├── infra/                       # Docker, scripts de déploiement
└── notebooks/                   # exploration data (Marimo ou Jupyter)
```

---

## Avant de prendre une tâche : lire `STATE.md`

`STATE.md` contient deux sections critiques tenues à jour à chaque session :
- **« État production vérifié »** : ce qui est réellement live, vérifié par `curl` sur Railway/Vercel (pas par lecture de docs périmées).
- **« Prochaines étapes par priorité »** : P0 → P4. Toujours commencer par le P0 actuel sauf si l'utilisateur demande explicitement autre chose. Le P0 du moment est souvent un bug d'effet vitrine sur la démo (la fiche `/@example/memoire-et-cerveau`).

Si tu modifies l'état réel du projet (feature livrée, fix prod, déploiement), **mets à jour `STATE.md`** avant de fermer la session. C'est le contrat de continuité.

Pour une **session autonome longue** (mode plan + acceptEdits, ou agent tiers comme opencode), consulter aussi :
- [`.docs/10-mvp-completion-plan.md`](./.docs/10-mvp-completion-plan.md) — jalons M1/M2/M3 vers MVP complet
- [`.docs/11-critique-and-improvements.md`](./.docs/11-critique-and-improvements.md) — regard critique
- [`agent/README.md`](./agent/README.md) — point d'entrée du système d'instructions agent (permissions, git workflow, pitfalls, skills)

---

## Pièges Alembic à éviter (vécus en prod)

- **L'ID de révision Alembic doit faire ≤ 32 caractères.** La colonne `alembic_version.version_num` est `VARCHAR(32)` par défaut. Un ID trop long lève `StringDataRightTruncationError` au moment du `UPDATE alembic_version` final, et la transaction DDL rollback _toute_ la migration → boucle crash-loop sur Railway. Convention adoptée : `00X_<courte_description>`.
- **`sa.Column("col", ForeignKey(...), index=True)` à l'intérieur de `create_table` crée déjà l'index** (nom auto `ix_<table>_<col>`). Ne pas le redoubler par un `op.create_index` explicite après, sinon `DuplicateTableError` sur le second CREATE INDEX → rollback complet.
- **Les nouveaux champs sur `sources` ne doivent JAMAIS entrer dans le `canonical_hash` payload.** Voir `apps/backend/app/services/card.py` lignes 96-105 et 161-169 + `app/scripts/seed_demo.py`. Toute fiche déjà publiée doit rester vérifiable. Si un champ doit absolument entrer dans la signature → ADR explicite + plan de re-signature.

---

## Choses à ne PAS faire

- N'ajoute pas de dépendances sans le signaler. Une nouvelle lib = une justification dans la conversation.
- Ne déploie pas. Le déploiement est manuel par le développeur.
- Ne modifie pas `.docs/` sauf demande explicite. Ces fichiers sont les specs de référence.
- Ne crée pas de fichiers de configuration redondants (par ex. plusieurs `.eslintrc`). Une seule source de vérité.
- N'utilise pas de CSS-in-JS, de composants Material UI, ni de framework UI lourd. Tailwind + composants Svelte custom.
- Ne génère pas de code obfusqué ou prématurément optimisé. Lisibilité d'abord.
- Ne propose pas de fonctionnalités hors scope du MVP sans le mentionner explicitement.

---

## En cas de doute

1. Lis le fichier `.docs/` pertinent (souvent `01-product-spec.md` ou `02-tech-architecture.md`)
2. Si l'ambiguïté persiste, ajoute une entrée dans `.docs/07-open-questions.md` et choisis l'option la plus simple en l'attendant
3. Mentionne-le explicitement dans ta réponse au développeur

---

## Format de réponse souhaité

- Sois concis. Pas de paraphrase de la demande.
- Quand tu modifies plusieurs fichiers, présente d'abord un plan en quelques lignes, puis exécute.
- Quand tu lances des commandes, explique ce qu'elles font en une phrase.
- Quand tu détectes un bug ou une incohérence, signale-le. Ne le contourne pas silencieusement.

---

## MCP servers utiles pour ce projet

Si tu as accès à des MCP servers, ceux qui sont utiles pour ce projet :

- **filesystem** : indispensable, lecture/écriture de fichiers
- **git** : utile pour commits, branches, log
- **gitmcp** : utile pour consulter des repos de référence (`c2pa-rs`, `internetarchive`, etc.)
- **obsidian** : si l'auteur tient ses notes projet dans Obsidian, utile pour consulter le contexte

Les autres (Docker Hub, Kubernetes, n8n, Notion) **ne sont pas pertinents** pour ce projet. Si ils sont actifs, ignore leurs tools.

---

*Ce fichier évolue avec le projet. Si une règle te paraît dépassée ou bloquante, signale-le.*
