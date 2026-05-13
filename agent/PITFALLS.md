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

- **Symptôme** : `sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`
- **Cause** : on accède à une relation ORM async (`card.sources`, etc.) après `await db.commit()`, sans avoir `selectinload`-é avant.
- **Prévention** : chaînage explicite avant le commit : `select(BiblioCard).options(selectinload(BiblioCard.sources).selectinload(Source.excerpts))`. Si tu écris du nouveau code qui retourne un objet avec ses relations après commit, anticipe le `selectinload`.

### 1.5 `datetime.utcnow()` déprécié Python 3.12

- **Symptôme** : `DeprecationWarning` qui devient `Error` dans une version future.
- **Prévention** : `datetime.now(UTC).replace(tzinfo=None)` pour matcher les colonnes `DateTime` sans `timezone=True`. Import : `from datetime import datetime, UTC`.

### 1.6 Variables d'env UPPERCASE silencieusement ignorées

- **Symptôme** : settings semble OK localement, mais en CI ou Railway les valeurs sont les defaults (`debug=True`, etc.). Comportement inexplicable.
- **Cause** : `case_sensitive=True` dans `SettingsConfigDict` (cf. ADR-010). UPPERCASE = fallback silent aux defaults sur Linux/CI.
- **Prévention** : toutes les variables d'env en **lowercase**. Auditer `.env.example`, `ci.yml`, Railway dashboard. Si tu vois `DATABASE_URL` quelque part, c'est un bug.

### 1.7 `cors_origins` mal formaté côté Railway

- **Symptôme** : CORS reject sur le frontend.
- **Cause** : pydantic-settings attend un JSON array sérialisé, ex `'["https://filum-eight.vercel.app","http://localhost:5173"]'`.
- **Prévention** : toute nouvelle origine doit être ajoutée à la variable `cors_origins` dans Railway (au format JSON array entier, pas en concaténation).

### 1.8 Cookies session non envoyés cross-origin

- **Symptôme** : `auth/me` retourne 401 alors que le cookie est posé.
- **Cause** : `samesite=lax` actuel. Bloque cross-origin Vercel ↔ Railway.
- **Prévention** : au moment de brancher OAuth, basculer en `samesite=none, secure=True`. Localisation : `apps/backend/app/api/v1/endpoints/auth.py` ~128-152.
- **Test** : `curl --cookie-jar cookies.txt --cookie cookies.txt` après login OAuth pour vérifier que le cookie est bien renvoyé.

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

### 1.13 `CardService.verify_card()` cassée par mauvais wrapping de clé publique

- **Symptôme** : toute vérification d'une fiche signée retournait silencieusement `{"valid": False, "reason": "..."}` en prod. La promesse cryptographique du projet (vérifier que la fiche n'a pas été altérée) était cassée sans alerte.
- **Cause** : `verify_card()` (`apps/backend/app/services/card.py`) chargeait la clé **publique** de l'utilisateur (`card.user.public_key`, stockée en hex brut, 32 bytes) en l'enroulant dans des headers `-----BEGIN PRIVATE KEY-----` et en appelant `SigningService.from_pem(...)`, qui attend une clé **privée** au format PEM. `serialization.load_pem_private_key` levait une exception, immédiatement caught par le try/except qui retournait `valid=False`.
- **Statut : FIXED dans PR #24** — ajout de `SigningService.verify_with_public_key_hex()` (méthode statique) qui reconstruit un `Ed25519PublicKey` depuis les bytes raw. `verify_card()` l'appelle désormais. Tests de régression : `test_verify_card_returns_valid_for_freshly_signed_card` et `test_verify_card_detects_tampered_title`.
- **Prévention future** : tout endpoint qui prétend faire de la crypto **doit** avoir au moins un test positif (cas valide → True) ET un test négatif (cas invalide → False). Un try/except qui swallow tout est un signal d'alerte — préférer logger + re-raise, ou avoir un test qui vérifie le happy path.

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
