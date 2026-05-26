# PITFALLS — erreurs déjà payées par le projet, à ne pas reproduire

> Source vérité : `CLAUDE.md` et `AGENTS.md` contiennent l'essentiel. Ce fichier les **agrège, complète et catégorise** pour un agent autonome qui pourrait ne pas avoir lu les deux.
>
> Convention : chaque entrée a un **symptôme observable**, une **cause racine**, et une **prévention vérifiable**. Si tu identifies un nouveau piège lors d'une session, **ajoute-le ici** avant la fin de la PR.

---

## 0. Comment l'agent doit utiliser ce fichier

- Lire en entier au démarrage de session (la première fois).
- Re-vérifier la section pertinente avant toute action qui s'en rapproche (ex: avant de créer une migration, relire la section Alembic).
- Si une PR rencontre un problème mentionné ici → la procédure de prévention a été ignorée, comprendre pourquoi.
- Si une PR rencontre un problème **non** mentionné ici → ajouter une entrée avant le merge.

---

## 1. Backend / SQLAlchemy / Alembic

### 1.1 ID de révision Alembic > 32 caractères

- **Symptôme** : `StringDataRightTruncationError` au commit du `UPDATE alembic_version`. Rollback complet de la migration. Railway crash-loop.
- **Cause** : la colonne `alembic_version.version_num` est `VARCHAR(32)` par défaut. Toute revision id plus longue est tronquée silencieusement par autogen → erreur à l'UPDATE final.
- **Prévention** : nommage `00X_<description-courte>` ≤ 32 caractères. Vérifier après `alembic revision -m "..."` avec `head -1` sur le fichier créé.

### 1.2 Double création d'index

- **Symptôme** : `DuplicateTableError` (ou `relation "ix_X_Y" already exists`) sur le second CREATE INDEX. Rollback complet.
- **Cause** : `sa.Column("col", ForeignKey(...), index=True)` à l'intérieur d'un `create_table()` crée déjà l'index avec nom auto `ix_<table>_<col>`. Ajouter un `op.create_index("ix_<table>_<col>", ...)` après est redondant.
- **Prévention** : si `index=True` dans la colonne, **pas** de `op.create_index` derrière. Et inversement.

### 1.3 Payload signé immuable (ex-`canonical_hash` sur fiche, maintenant attestation de contenu)

> ⚠️ **Pivot ADR-019 (2026-05-14)** : la signature ne porte plus sur la fiche bibliographique mais sur le **lien créateur·ice ↔ contenu** — triplet `(creator_id, content_url, attested_at)`. Les fiches sont mutables. Tant que la migration `006_remove_card_signature` + table `content_attestations` ne sont pas mergées, l'ancien `canonical_hash` sur `biblio_cards` reste en base mais n'est plus exposé en frontend.

- **Symptôme** : une attestation de contenu déjà émise devient invérifiable (la vérification renvoie `False`) car le payload signé a changé de forme.
- **Cause** : un payload signé est gelé. Tout champ ajouté/retiré au schéma sérialisé change le hash de toutes les signatures passées.
- **Prévention** : **aucun nouveau champ ne doit entrer dans le payload canonicalisé d'une `content_attestation`** sans :
  1. Un ADR explicite expliquant pourquoi c'est nécessaire
  2. Un plan de re-attestation pour toutes les attestations existantes
- **Localisation post-migration** : à définir (probablement `apps/backend/app/services/attestation.py`). Pre-migration : `apps/backend/app/services/card.py` + `apps/backend/app/scripts/seed_demo.py`.

### 1.4 `MissingGreenlet` sur accès relation ORM post-commit

- **Symptôme côté backend** : `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`
- **Symptôme côté frontend** : `TypeError: Failed to fetch` dans la console — le navigateur ne reçoit aucun body et croit à une coupure réseau. C'est trompeur : ce n'est pas CORS ni le réseau, c'est le backend qui meurt en pleine sérialisation.
- **Cause** : on accède à une relation ORM async (`card.sources`, `card.user.username`, etc.) après `await db.commit()` sans avoir `selectinload`-é avant. Pire : un `await db.refresh(card)` post-commit **réexpire toutes les relations** même si elles étaient eager-loadées initialement.
- **Prévention** :
  1. `selectinload` chaîné dans le `get_*` initial : `select(BiblioCard).options(selectinload(BiblioCard.sources).selectinload(Source.excerpts)).options(selectinload(BiblioCard.user))`.
  2. **Ne pas appeler `await db.refresh(obj)` si on n'en a pas besoin** (les valeurs en mémoire suffisent souvent).
  3. **Capturer les scalaires de relations AVANT le commit** quand on doit les utiliser après. Ex : `username = card.user.username` puis `await db.commit()` puis `f"@{username}"`.
- **Cas vécu** (2026-05-14, fix sur PR #33) : `CardService.publish_card` accédait à `card.user.username` ligne 138 après `await db.commit() + await db.refresh(card)`. Le `refresh` avait expiré la relation `user`, l'accès lazy a planté la sérialisation HTTP → tous les `POST /cards/{id}/publish` retournaient `Failed to fetch` côté navigateur, sans aucun log clair côté Railway car l'exception est levée trop tard dans le pipeline ASGI.
- **Filet de sécurité** (2026-05-14, PR #34) : `publish_card` endpoint enveloppé d'un `try/except Exception` qui log la stack et retourne un 500 JSON propre. Désormais, même si un `MissingGreenlet` futur est ré-introduit, le navigateur recevra `{"error": {"code": "publish_failed", ...}}` au lieu d'un `Failed to fetch` opaque. À répliquer sur tout endpoint qui mute + sérialise des relations.
- **Vérifier que Railway a redéployé** : `curl https://filum-production-07bb.up.railway.app/health` retourne maintenant `{"commit": "<sha>"}` (champ ajouté PR #34). Comparer à `git log -1 --format=%H origin/main` pour confirmer que la version live est bien la dernière.

### 1.5 `datetime.utcnow()` déprécié Python 3.12 ET tz-aware datetime sur colonnes `TIMESTAMP WITHOUT TIME ZONE`

- **Symptôme déprécation** : `DeprecationWarning` qui devient `Error` dans une version future.
- **Symptôme tz-aware** : `asyncpg.exceptions.DataError: invalid input for query argument $1: ... (can't subtract offset-naive and offset-aware datetimes)` au moment du commit. La session SQLAlchemy passe en état "transaction aborted". Si l'endpoint a un `try/except` qui catch et retourne `JSONResponse`, `get_db`'s post-yield `await session.commit()` retente sur session corrompue → seconde exception **après** que la réponse a commencé à se construire → stream interrompu → **le navigateur reçoit ERR_FAILED et un message CORS trompeur "No 'Access-Control-Allow-Origin' header"** alors que CORS marche très bien sur tous les autres endpoints.
- **Cause** : les colonnes `Mapped[datetime] = mapped_column(DateTime, ...)` sont par défaut sans `timezone=True` côté SQLAlchemy → asyncpg envoie en `TIMESTAMP WITHOUT TIME ZONE`. Un `datetime.now(UTC)` est tz-aware → asyncpg refuse.
- **Prévention** : **toujours** `datetime.now(UTC).replace(tzinfo=None)` pour matcher les colonnes `DateTime` sans `timezone=True`. Import : `from datetime import datetime, UTC`.
- **Cas vécu** (2026-05-14, fix sur PR #36) : `CardService.publish_card` faisait `card.signed_at = datetime.now(UTC)` (oubli du `.replace(tzinfo=None)`). En prod, **tout** `POST /cards/{id}/publish` retournait CORS error côté navigateur. Le pattern de PITFALLS §1.4 (`TypeError: Failed to fetch`) cachait la vraie cause pendant 3 PRs : on a chassé un MissingGreenlet qui n'existait pas. Diagnostiqué via `/health/publish-diagnose` (endpoint ajouté PR #35) qui exposait le traceback réel.

### 1.6 Variables d'env UPPERCASE silencieusement ignorées

- **Symptôme** : settings semble OK localement, mais en CI ou Railway les valeurs sont les defaults (`debug=True`, etc.). Comportement inexplicable.
- **Cause** : `case_sensitive=True` dans `SettingsConfigDict` (cf. ADR-010). UPPERCASE = fallback silent aux defaults sur Linux/CI.
- **Prévention** : toutes les variables d'env en **lowercase**. Auditer `.env.example`, `ci.yml`, Railway dashboard. Si tu vois `DATABASE_URL` quelque part, c'est un bug.

### 1.7 `cors_origins` mal formaté côté Railway

- **Symptôme** : CORS reject sur le frontend.
- **Cause** : pydantic-settings attend un JSON array sérialisé, ex `'["https://filum-eight.vercel.app","http://localhost:5173"]'`.
- **Prévention** : toute nouvelle origine doit être ajoutée à la variable `cors_origins` dans Railway (au format JSON array entier, pas en concaténation).

### 1.8 Cookies session non envoyés cross-origin (mis à jour 2026-05-26)

- **Symptôme initial** : `auth/me` retourne 401 alors que le cookie est posé, *uniquement sur mobile*.
- **Cause profonde** : `SameSite=None; Secure` est correctement set côté backend, MAIS Safari iOS / WebKit Chrome iOS bloquent les cookies tiers par défaut via ITP. Vercel et Railway étant deux origines différentes du point de vue du navigateur, le cookie posé par Railway est traité comme un cookie tiers et droppé silencieusement. Desktop est plus permissif et masque le bug.
- **Solution architecturale (ADR-025)** : proxy SvelteKit `src/routes/api/[...path]/+server.ts` qui forwarde `/api/*` vers `BACKEND_URL` côté serveur. Le navigateur ne voit qu'une seule origine → cookies first-party. Voir aussi pitfalls §1.16, §2.10, §2.11 pour les sous-problèmes rencontrés.
- **Diagnostic** : si la conn marche sur PC et pas sur mobile, c'est presque certainement un cookie tiers. Tester en dev en utilisant deux ports différents (frontend `:5173`, backend `:8000`) reproduit le problème.
- **Anti-pattern à éviter** : ajouter une rewrite `vercel.json` avec un placeholder `REPLACE_WITH_BACKEND_HOST` — invisible si le placeholder n'est pas remplacé, et il n'y a pas d'interpolation d'env var dans `vercel.json` (PR #66 a fait cette erreur).

### 1.9 `ruff format` oublié avant commit

- **Symptôme** : CI `lint-backend` rouge sur un commit pourtant qui passait `ruff check`.
- **Cause** : `ruff check` ≠ `ruff format`. La CI exige les deux.
- **Prévention** : lancer `uv run ruff format app/` (PAS juste `--check`) avant chaque commit backend.

### 1.10 Tests pytest qui ne tournent pas sur Windows

- **Symptôme** : tests échouent sur Windows avec des messages cryptiques sur les variables d'env.
- **Cause** : Windows = case-insensitivity native sur les env vars, conflit avec `case_sensitive=True` pydantic.
- **Prévention** : lancer `ruff` + `mypy` en local sur Windows. Faire confiance à la CI Linux pour `pytest`. Si vraiment besoin de tester sur Windows, passer par WSL.

### 1.11 Modèle SQLAlchemy `nullable=False` désaligné avec la migration

- **Symptôme** : tests qui créent un `BiblioCard` via `Base.metadata.create_all` (conftest SQLite) reçoivent `IntegrityError: NOT NULL constraint failed: biblio_cards.canonical_hash` alors qu'on tente d'insérer un draft. Aurait aussi cassé `POST /cards` en prod pour tout user tiers (cas pas encore exercé puisque OAuth pas branché).
- **Cause** : `BiblioCard.canonical_hash` et `BiblioCard.signature` étaient déclarés `nullable=False` dans `apps/backend/app/models/biblio_card.py`, et la migration 001 créait les colonnes NOT NULL aussi. Mais `CardService.create_card()` les laisse `None`. La seule raison que la démo marche : le seed enchaîne immédiatement avec `publish_card()` qui remplit les champs.
- **Statut : FIXED dans PR #24** — modèle passé à `Mapped[str | None]` + `nullable=True` + migration `005_nullable_card_hash_sig.py`. Test de régression : la fixture `published_card` de `tests/unit/test_canonical_hash.py` crée un draft sans canonical_hash et passe.
- **Prévention future** : à chaque ajout de colonne `nullable=False`, vérifier qu'au moins un test crée la ligne sans setter ce champ (preuve que c'est *vraiment* requis dans tous les chemins).

### 1.12 Field constraints Pydantic perdus par redéfinition de champ en sous-classe

- **Symptôme** : `Field(min_length=..., max_length=...)` déclaré sur `SourceBase` n'était PAS appliqué quand on instanciait `SourceCreate`. Validation longueur silently absente sur le payload d'entrée.
- **Cause** : `class SourceCreate(SourceBase): url: str` redéfinissait complètement le champ `url`, ce qui efface le `Field(...)` hérité. Pydantic v2 ne fusionne pas — il remplace.
- **Statut : FIXED dans PR #24** — la ligne `url: str` redondante a été retirée de `SourceCreate`. Tests de régression : `test_url_max_length_enforced` + `test_url_min_length_enforced` dans `tests/unit/test_schemas.py`.
- **Prévention future** : si tu veux hériter d'un champ + son `Field(...)`, ne **pas** le redéfinir dans la sous-classe. Si tu dois absolument le redéfinir, copier explicitement le `Field(...)`.

### 1.14 `default=None` dans un modèle SQLAlchemy override le `server_default` de la DB

- **Symptôme** : `NotNullViolationError` sur une colonne qui a pourtant `server_default=sa.func.now()` dans la migration. L'INSERT envoie explicitement `None`.
- **Cause** : le modèle SQLAlchemy a `default=None, server_default=None`, ce qui force SQLAlchemy à inclure la colonne dans l'INSERT avec `None`, court-circuitant le `DEFAULT now()` PostgreSQL.
- **Prévention** : ne **jamais** mettre `default=None` sur une colonne `nullable=False` avec `server_default`. Soit on omet complètement les defaults (SQLAlchemy omet la colonne de l'INSERT si elle n'est pas set), soit on utilise `server_default=func.now()` seul. Si on veut un default côté Python, utiliser un callable (`default=datetime.utcnow`) pas `None`.
- **Cas vécu** (2026-05-14, PR #40) : `ContentAttestation.created_at` avait `default=None, server_default=None`. La migration 006 définissait `server_default=sa.func.now()` mais le modèle override. Le seed demo et `AttestationService.create_attestation` ne settaient pas `created_at` → `NotNullViolationError` en boucle sur Railway.
- **Localisation** : `apps/backend/app/models/content_attestation.py:36-40`
- **Test** : créer une `ContentAttestation` sans setter `created_at` — l'INSERT doit réussir et `created_at` doit être rempli par la DB.

### 1.13 `CardService.verify_card()` cassée par mauvais wrapping de clé publique

- **Symptôme** : toute vérification d'une fiche signée retournait silencieusement `{"valid": False, "reason": "..."}` en prod. La promesse cryptographique du projet (vérifier que la fiche n'a pas été altérée) était cassée sans alerte.
- **Cause** : `verify_card()` (`apps/backend/app/services/card.py`) chargeait la clé **publique** de l'utilisateur (`card.user.public_key`, stockée en hex brut, 32 bytes) en l'enroulant dans des headers `-----BEGIN PRIVATE KEY-----` et en appelant `SigningService.from_pem(...)`, qui attend une clé **privée** au format PEM. `serialization.load_pem_private_key` levait une exception, immédiatement caught par le try/except qui retournait `valid=False`.
- **Statut : FIXED dans PR #24** — ajout de `SigningService.verify_with_public_key_hex()` (méthode statique) qui reconstruit un `Ed25519PublicKey` depuis les bytes raw. `verify_card()` l'appelle désormais. Tests de régression : `test_verify_card_returns_valid_for_freshly_signed_card` et `test_verify_card_detects_tampered_title`.
- **Prévention future** : tout endpoint qui prétend faire de la crypto **doit** avoir au moins un test positif (cas valide → True) ET un test négatif (cas invalide → False). Un try/except qui swallow tout est un signal d'alerte — préférer logger + re-raise, ou avoir un test qui vérifie le happy path.

### 1.16 OAuth signup : collision sur `username` quand deux comptes Google partagent le local part de l'email

- **Symptôme** : 500 `internal_error` au callback OAuth pour certains nouveaux comptes Google, alors que l'utilisateur initial avait un compte qui marchait. Souvent même personne physique avec deux Gmail dont le local part collisionne (`prenom.nom@hotmail.fr` vs `prenom.nom@gmail.com`).
- **Cause** : `auth.py` faisait `username = email.split("@")[0]`. Colonne `User.username` est `unique=True` → 2e INSERT lève `IntegrityError` → catch-all `main.py` retourne le 500 générique. **Bonus** : les caractères hors `[a-z0-9-]` (points, plus-tags, accents) étaient persistés tels quels, ce qui aurait cassé les URLs publiques `/@<username>`.
- **Prévention** : `services/auth.py::_slugify_username()` + `_resolve_available_username()` — slugifie le local part (`mathias.pinault` → `mathias-pinault`), récupère en une seule requête les usernames `base` et `base-%`, append un suffix numérique sur collision (`-2`, `-3`, …), fallback `user-<google_id[:12]>` si la slugification donne du vide. Catch de l'`IntegrityError` résiduelle (email duplicate sur 2 comptes Google) → 409 propre au lieu de 500. PR #77.
- **Test** : `tests/unit/test_auth.py::test_create_user_from_google_resolves_username_collision`.

### 1.15 Champ Pydantic accepté mais silencieusement non persisté (constructeur SQLAlchemy oublié)

- **Symptôme** : `parent_source_id` envoyé en payload sur `POST /cards/{id}/sources` était bien accepté par Pydantic (présent sur `SourceCreate`) mais jamais persisté en base. Aucune erreur, juste une donnée perdue. Le seed démo (qui insère directement en base) n'était pas affecté, donc le bug se cachait. Découvert quand on a voulu exposer le champ dans l'UI.
- **Cause** (`sources.py:138-149` avant ADR-020) : le constructeur `Source(...)` listait explicitement les champs (`url=`, `title=`, `source_type=`, etc.) mais avait oublié `parent_source_id=source_data.parent_source_id`. Pas de `**source_data.model_dump()` ni de `setattr` boucle → tout champ non explicite est silencieusement laissé à `None`.
- **Statut : FIXED dans la PR taxonomie (ADR-020)**.
- **Prévention future** : un endpoint CREATE qui construit manuellement le modèle SQLAlchemy à partir d'un `Pydantic.BaseModel` doit (a) soit utiliser `Model(**payload.model_dump(exclude_unset=False, exclude={"computed_fields"}))` pour ne rien oublier, (b) soit avoir un test d'intégration qui vérifie le round-trip pour **chaque champ** déclaré dans le schéma. Si on choisit la liste explicite, ajouter le test round-trip est non-négociable.

---

## 2. Frontend / SvelteKit / D3

### 2.1 pnpm 11 dégrade tout

- **Symptôme** : `ERR_PNPM_IGNORED_BUILDS` exit 1, `pnpm-workspace.yaml` réécrit avec du junk, install qui boucle.
- **Cause** : pnpm 11 a un policy build-scripts strict + réexécute un install avant chaque run.
- **Prévention** : pnpm 10.33.4 pinné via `packageManager` dans `apps/frontend/package.json` (ADR-013). **Ne pas** upgrade. Ne pas écouter Dependabot sur pnpm. Suivi : Q16 dans `.docs/07-open-questions.md`.

### 2.2 Import D3 par sous-module

- **Symptôme** : `Module not found: d3-force` ou types `any` partout.
- **Cause** : `'d3-force'` etc. sont des deps transitives non déclarées.
- **Prévention** : importer depuis `'d3'` (umbrella). Typer `.selectAll<SVGGElement, T>('g')` avant `.data().join()`.

### 2.3 `.style('display', null)` casse le build

- **Symptôme** : `TS2322: Type 'null' is not assignable to type 'string'`.
- **Cause** : types d3 plus stricts en v7.
- **Prévention** : `.style('display', flag ? '' : 'none')` — chaîne vide, pas `null`.

### 2.4 SSR mal configuré sur une route publique

- **Symptôme** : la page publique apparaît vide dans la vue source HTML. Pas de JSON-LD, donc invisible pour les bots et les moteurs IA (Perplexity, Claude.ai, SearchGPT).
- **Cause** : `+layout.ts` a `ssr = false` par défaut. Si on oublie de surcharger via `+page.ts` (`export const ssr = true`) sur la route publique, c'est du CSR pur.
- **Prévention** : **toute nouvelle route publique** (`/@[slug]`, `/@[slug]/[card]`, `/blog`, …) → `+page.ts` avec `ssr=true`. Les composants D3 (avec `document`/`window`) doivent être dynamic-imported côté client.

### 2.5 `tsconfig.json` qui redéclare `paths`/`baseUrl`

- **Symptôme** : alias `$lib` ne résout plus.
- **Cause** : conflit avec `.svelte-kit/tsconfig.json` généré.
- **Prévention** : alias dans `svelte.config.js` → `kit.alias`, jamais dans `tsconfig.json`.

### 2.6 `toLocaleDateString({ timeStyle: ... })`

- **Symptôme** : `RangeError: Unknown option timeStyle`.
- **Cause** : `toLocaleDateString` n'accepte pas `timeStyle`, c'est `toLocaleString`.
- **Prévention** : utiliser `toLocaleString` pour date + heure.

### 2.7 `$page.params.<X>` typé `string | undefined`

- **Symptôme** : `TS2322` à l'usage.
- **Cause** : SvelteKit type `params` génériquement, même si la route le garantit.
- **Prévention** : `$page.params.slug ?? ''`.

### 2.8 `<aside role="dialog">` warning a11y

- **Prévention** : `<div role="dialog" aria-modal="true">`. `aside` ne doit pas avoir `role="dialog"`.

### 2.9 SvelteKit 2 + option dépréciée

- **Symptôme** : `Unexpected option config.kit.vitePlugin`.
- **Cause** : `kit.vitePlugin.inspector` supprimé en SvelteKit 2.
- **Prévention** : auditer `svelte.config.js` à chaque upgrade SvelteKit.

### 2.10 Proxy SvelteKit qui mange les `Set-Cookie` (undici en Node fetch)

- **Symptôme** : derrière `src/routes/api/[...path]/+server.ts`, l'OAuth retourne `invalid_state` au callback alors que tout le flow semble correct. Le navigateur n'a aucun cookie `filum_oauth_state` stocké après la réponse `/login`.
- **Cause** : itérer `response.headers` avec `for (const [name, value] of headers)` en Node fetch (undici, utilisé par Vercel) **collapse plusieurs `Set-Cookie` en un seul header virgule-séparé**. Comportement spécifique du runtime Node — c'est différent du fetch des navigateurs. Quand plusieurs cookies sont posés ou quand un cookie contient des virgules dans `Expires=...`, le browser reçoit un Set-Cookie illisible et ne stocke rien.
- **Prévention** : dans un proxy Node fetch, skip explicite de `set-cookie` lors de la copie des autres headers, puis re-append individuel via `response.headers.getSetCookie()` (Node 18+ undici, supporté sur Vercel). Voir `apps/frontend/src/routes/api/[...path]/+server.ts` pour le pattern complet (PR #75).
- **Test** : DevTools Network → réponse de `GET /api/v1/auth/google/login` → vérifier qu'il y a bien un header `Set-Cookie: filum_oauth_state=...; SameSite=None; Secure` visible et que l'onglet Application → Cookies montre le cookie stocké pour le domaine Vercel.

### 2.11 Railway clobbe `X-Forwarded-Host` (sécurité contre host spoofing)

- **Symptôme** : derrière un proxy qui set `X-Forwarded-Host: <vercel-domain>`, le backend FastAPI lit toujours `<railway-host>` quand on inspecte `request.headers.get("x-forwarded-host")`. Conséquence concrète : OAuth `redirect_uri` envoyé à Google pointe sur Railway directement, bypass le proxy Vercel sur le retour, cookie tiers à nouveau, `invalid_state`.
- **Cause** : l'ingress Railway réécrit unconditionnellement `X-Forwarded-Host` et `X-Forwarded-Proto` avec son propre hostname **avant** que la requête n'atteigne le code applicatif. C'est une sécurité standard contre le host spoofing, mais ça invalide tout protocole qui dépend de ces headers pour reconstruire l'origine publique.
- **Prévention** : utiliser un header custom non standard (ex. `X-Filum-Public-Origin`) que Railway laisse passer. Combiner avec un fallback sur `settings.frontend_base_url` qui est canonical. Voir `apps/backend/app/api/v1/endpoints/auth.py::_public_callback_url` et le proxy SvelteKit (PR #76).
- **Diagnostic rapide** : si Google te redirige sur le hostname Railway au lieu du frontend Vercel pendant un OAuth flow, c'est ce pitfall.

---

## 3. CI / GitHub Actions

### 3.1 Workflow YAML invalide

- **Symptôme** : 0 jobs, 0s runtime, pas d'erreur visible.
- **Cause classique** : `workflow_dispatch:` au top-level au lieu d'être nesté sous `on:`.
- **Prévention** : `gh workflow view <name>` pour vérifier que les jobs sont listés.

### 3.2 Action GitHub inexistante

- **Symptôme** : `Could not find action ...`.
- **Cause vécue** : `railway-devrel/railway-actions@v1` (fiction d'un LLM lors du scaffolding initial).
- **Prévention** : vérifier sur le marketplace GitHub avant d'utiliser une action peu connue.

### 3.3 `dependency-review-action` qui bloque sur une CVE transitive non exploitable

- **Symptôme** : PR bloquée sur `ecdsa Minerva attack` alors que le projet n'utilise pas ECDSA.
- **Cause** : `python-jose` tire `ecdsa` même si on utilise HS256.
- **Prévention** : voir ADR-014. Migration vers `PyJWT` faite. Ne pas réintroduire `python-jose`.

### 3.4 `|| true` qui masque un vrai bug

- **Symptôme** : CI verte mais feature cassée en prod.
- **Cause** : `|| true` pour contourner un échec en CI cache la cause racine.
- **Prévention** : pas de `|| true` en CI. Si une étape échoue légitimement, soit on la fixe, soit on la retire.

---

## 4. Git / déploiement / process

### 4.1 `git` indisponible sur Windows

- **Symptôme** : `git: command not found` en PowerShell.
- **Cause** : `git` n'est pas dans le PATH Windows.
- **Prévention** : passer par WSL — `wsl bash -lc 'cd /mnt/c/Users/mathi/Documents/filum_project/filum && git ...'`.

### 4.2 Commit de fix manquant dans le squash

- **Symptôme** : PR mergée mais le dernier commit (fix critique) n'est pas dans `main`.
- **Cause** : non élucidée. Cas vécu.
- **Prévention obligatoire** : **avant `gh pr merge`**, faire :
  ```bash
  git fetch origin
  git log origin/<branche> -3 -- <fichier-critique>
  gh pr view <num> --json commits
  ```
  Et croiser avec la diff sur l'UI GitHub.

### 4.3 `_commit_msg.txt` accidentellement commité

- **Symptôme** : fichier `_commit_msg.txt` dans le repo.
- **Cause** : oubli du `rm` après `git commit -F`.
- **Prévention** : `git commit -F _commit_msg.txt && rm _commit_msg.txt`. Le fichier est dans `.gitignore` mais reste créable.

### 4.4 Railway crash-loop sur une migration

- **Symptôme** : déploiements successifs échouent au boot.
- **Cause** : migration Alembic qui throw → DDL rollback → version_num pas avancée → retry au prochain boot, même résultat.
- **Bonne nouvelle** : la BDD n'est PAS corrompue (DDL rollback est atomique).
- **Prévention** : tester `alembic upgrade head` en local sur un Postgres frais avant push. Si crash-loop en prod : pousser le fix, attendre le prochain build.

### 4.5 Variable d'env non reflétée après modif Railway

- **Symptôme** : on modifie une env var, mais le backend continue avec l'ancienne valeur.
- **Cause** : Railway ne redémarre pas automatiquement le service à chaque modif env.
- **Prévention** : trigger un redéploy manuel (dashboard) ou push un commit vide.

### 4.6 Modification d'une fiche déjà publiée

- **Symptôme** : signature `verify_card` échoue.
- **Cause** : on a modifié un champ qui entre dans le `canonical_hash`.
- **Prévention** : ne **jamais** modifier une fiche publiée. Soit on republie (re-sign), soit on laisse tel quel.

---

## 5. Sécurité

### 5.1 Secret commité (clé Google, master key, etc.)

- **Symptôme** : TruffleHog en CI flag le commit.
- **Prévention** : avant `git add`, `git diff --staged | grep -iE 'key|secret|token|password'`. Tous les secrets dans `.env` (gitignored) + placeholders dans `.env.example`.

### 5.2 SQL formaté à la main

- **Symptôme** : SQL injection potentielle.
- **Prévention** : **toujours** SQLAlchemy ORM ou `text()` avec params. Jamais `f"SELECT ... WHERE x = '{user_input}'"`.

### 5.3 Endpoint mutable sans auth

- **Symptôme** : n'importe qui peut appeler `POST /cards` et créer une fiche.
- **Prévention** : tout endpoint qui modifie des données doit avoir une dépendance `Depends(get_current_user)`.

### 5.4 Rate limit absent sur endpoint public

- **Symptôme** : un bot spam `/sources/extract` et fait grimper la facture Wayback/Crossref + saturation.
- **Prévention** : `slowapi` sur tous les endpoints publics qui appellent un service externe. Voir `agent/skills/rate-limiting.md`.

### 5.5 SSRF via URL utilisateur

- **Symptôme** : l'utilisateur soumet `http://localhost:6379` à `/sources/extract` et lit Redis.
- **Prévention** : valider que l'URL passée à l'extracteur est `https?://` + résolution DNS publique (cf. `app/extractors/url_extractor.py`). C'est déjà fait via `HttpUrl` Pydantic mais à vérifier à chaque nouvel endpoint qui fetch une URL utilisateur.

---

## 6. Données utilisateur

### 6.1 Test sur compte créateur réel sans consentement

- **Prévention** : utiliser un compte de test dédié. Pas de fiche d'utilisateur tiers manipulée en dev.

### 6.2 Dump BDD prod copié en local sans anonymisation

- **Prévention** : si un dump est nécessaire, anonymiser les emails, hash les noms, ne pas garder les clés privées chiffrées.

---

## 7. Spec / produit

### 7.1 Implémenter une feature hors MVP "parce que c'est facile"

- **Symptôme** : sprawl, PRs qui s'allongent, MVP retardé.
- **Cause** : pression de la "completude perçue".
- **Prévention** : se référer à `.docs/10-mvp-completion-plan.md` section « Anti-features ». Si la feature n'est pas explicitement dans M1/M2/M3, la noter en backlog (issue GitHub) et ne pas l'implémenter.

### 7.2 Modifier un fichier `.docs/00-…` à `.docs/09-…` sans demande

- **Symptôme** : la spec de référence change sans trace.
- **Prévention** : ces fichiers sont **figés**. Tout changement de spec passe par une demande explicite du développeur.

---

## 8. Template pour ajouter une entrée

```markdown
### N.M Titre court actionnable

- **Symptôme** : ce qu'on observe (message d'erreur, comportement)
- **Cause** : pourquoi ça se produit
- **Prévention** : commande / pattern de code à appliquer
- **Localisation** (optionnel) : `fichier:lignes`
```

---

*Ce fichier grossit à chaque session significative. C'est sain. Un fichier `PITFALLS.md` qui ne grossit jamais, c'est un projet qui réinvente les mêmes bugs.*
