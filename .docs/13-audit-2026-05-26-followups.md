# Audit 2026-05-26 — suites à donner (Phase 5)

> Suivi des items long-terme issus de l'audit complet du 26 mai 2026.
> Les phases 1–4 ont été livrées dans la même session (PRs #79, #80, #81 + cleanup branches). Cette page liste ce qui n'a **pas** été traité immédiatement, avec contexte, niveau d'urgence, effort estimé, et déclencheurs naturels.
>
> **Voir aussi** : [`15-audit-improvements-plan.md`](./15-audit-improvements-plan.md) — audit complémentaire du 2 juin 2026 (privacy leak User-Agent, déprécations `datetime.utcnow`, CVE `python-jose`, + windmills documentés pour ne pas re-auditer).

## Comment l'utiliser

Quand on attaque un nouveau jalon, lire d'abord cette page pour voir si une suite à donner est devenue pertinente. Les items sont triés par **priorité d'attaque** (le plus prioritaire en haut), pas par sévérité brute — une faille HIGH qui n'est pas exploitable aujourd'hui peut attendre, alors qu'un bottleneck MEDIUM qui bloque le prochain feature passe devant.

Chaque item a un **trigger** : la condition concrète qui doit faire passer l'item de « à faire un jour » à « à faire maintenant ».

---

## P1 — À traiter avant le premier vrai user payant

### F1. Génération automatique des types TypeScript depuis Pydantic / OpenAPI

**Constat code** : `apps/frontend/src/lib/api/types.ts` duplique manuellement les enums `SourceFormat`, `SourceCategory`, `AuthorKind`, `ArchiveStatus`, `CardStatus`, `Platform`, `ContentType`. Source de vérité : `apps/backend/app/schemas/source.py` + `biblio_card.py`. Toute évolution (ajouter `AuthorKind.ENSEIGNANT`, par exemple) doit être faite à deux endroits sans alerte automatique. Un drift silencieux = un bug à l'exécution côté frontend qui apparaît seulement quand un user crée une source avec le nouveau type.

**Trigger** : prochaine évolution du modèle de source ou ajout d'une nouvelle entité côté backend (donc : très bientôt, dès qu'on ajoute un nouveau type d'auteur ou un nouveau format).

**Options**
- `pydantic2ts` (mature, mais sort du Pydantic → JSON Schema → TS) — coût d'intégration ~2h
- `openapi-typescript` lit le `/openapi.json` déjà servi par FastAPI — plus standard, pas besoin d'installer un nouveau outil Python — coût ~3h avec le pipeline CI
- Garder la duplication + ajouter un test qui compare les valeurs d'enum (test simple, mais ne rattrape pas les divergences structurelles)

**Recommandation** : `openapi-typescript`. À lancer dans un step CI `frontend-build` qui régénère et fail si diff, ou via une commande `pnpm types:gen` que l'auteur lance avant de commit.

**Effort** : M (3-4h dont CI step).

### F2. Tests d'intégration sur `POST /cards/{id}/publish`

**Constat code** : la session du 14 mai a coûté 4 PRs (#33–#36) parce que `publish` plantait en prod avec des symptômes trompeurs (`Failed to fetch`, faux CORS). Le code est maintenant blindé par un try/except global et l'endpoint `/health/publish-diagnose`. Mais **aucun test d'intégration** ne couvre le path complet. Une régression sur la sérialisation des relations, sur un nouveau champ Pydantic, ou sur la signature Ed25519 ne sera attrapée que par un user en prod.

**Trigger** : prochaine modification de `CardService.publish_card` ou du modèle `BiblioCard`. À traiter en amont d'un travail sur la version 2 des attestations (Phase 3 roadmap principale).

**Effort** : M (faut un fixture user + card + sources, un mock de la signature crypto, vérification du status post-publish, et idéalement un round-trip de vérification d'attestation).

### F3. Tests Postgres au lieu de SQLite

**Constat code** : `tests/conftest.py:12` utilise `sqlite+aiosqlite:///./test.db`. Les migrations Alembic exécutent en SQLite, donc les index composites multi-colonnes, les contraintes `UNIQUE (col1, col2) WHERE col3 IS NULL` (partial unique index — pas supporté en SQLite), les types `JSONB`, et certaines particularités de transactions se comportent différemment en Postgres prod. Un bug Postgres-only peut passer le CI vert sans qu'on le voie.

**Trigger** : quand on ajoute un index partial / une contrainte conditionnelle / une colonne JSON. Aujourd'hui le risque est faible (rien de tout ça), mais devient critique dès la première fois.

**Options**
- `testcontainers-python` : démarre un container Postgres au début de la suite. ~5s d'overhead par run CI, simple.
- Garder SQLite par défaut + un job CI séparé `test-backend-postgres` optionnel qui n'est run que sur la branche `main` et sur les PR taggées `db-change`. Compromis acceptable.

**Effort** : L (configuration + tagging, ~1 jour avec validation que tout passe).

### F4. Endpoint admin `POST /cards/{id}/restore` pour annuler un soft-delete

**Constat code** : PR #81 introduit le soft-delete. Il n'y a actuellement aucun moyen pour un user de *revenir en arrière* sur une suppression. Soit on contacte le support (= toi avec un `UPDATE biblio_cards SET deleted_at = NULL WHERE id = ...`), soit la card reste à jamais cachée.

**Trigger** : le premier user qui clique "Supprimer" par erreur et qui demande à restaurer. Ça arrivera. À traiter avant que le support manuel devienne un coût.

**Effort** : S (endpoint, contrôle de propriété, fenêtre temporelle de 30 jours peut-être, test).

---

## P2 — À traiter quand la charge ou le scope augmente

### F5. Queue durable pour Wayback (Save Page Now)

**Constat code** : `endpoints/sources.py:174` lance `asyncio.create_task(_archive_bg())` qui poll Wayback pendant ~33s en background. Si le worker FastAPI redémarre (cold start Railway, push de déploiement, OOM) entre le `create_task` et la fin du polling, **le job est silencieusement perdu** — la source reste `archive_status = pending` sans personne pour la retenter. Aujourd'hui le user peut éditer la source pour relancer, mais c'est manuel.

**Trigger** : quand on a > 50 sources créées par jour OU quand un user signale qu'une de ses sources reste éternellement `pending`.

**Options**
- `arq` (Redis-based, ~150 lignes pour un worker, intégration FastAPI standard)
- Postgres-backed queue avec `SELECT ... FOR UPDATE SKIP LOCKED` — pas besoin d'infra supplémentaire
- Worker Railway séparé qui lit une table `pending_archive_jobs`

**Effort** : M-L selon l'option. Le pattern Postgres-backed est le plus aligné avec la stack actuelle (pas de Redis à ajouter).

### F6. Index DB composites pour le dashboard à plus grande échelle

**Constat code** : `BiblioCard` a `ix_biblio_cards_user_status` (user_id, status). Pour le query du dashboard (`get_user_cards` qui filtre par user + status + deleted_at, et trie par `created_at DESC`), un index sur `(user_id, status, deleted_at, created_at)` éviterait le sort en mémoire. Pareil sur `sources` pour `(biblio_card_id, position, deleted_at)`.

**Trigger** : EXPLAIN ANALYZE sur prod montre un `Sort` qui prend > 50ms. Probable à partir de quelques centaines de fiches par user.

**Effort** : S (une migration, deux index).

### F7. Rate limit plus strict sur `/sources/extract` ou auth requise

**Constat code** : `endpoints/sources.py:43` rate-limite à `10/minute`. L'endpoint est no-auth (volontaire — l'extraction d'URL est utilisée pour pré-remplir le formulaire d'ajout, avant que l'user ne soit logué). Avec le SSRF guard ajouté en PR #80, le risque sécurité est neutralisé, mais le coût en bande passante (httpx vers des sites externes) est porté par Filum à chaque appel. Un attaquant peut scrape le web à 600 URLs/heure via Filum.

**Trigger** : si on voit des spikes anormaux dans les logs Railway, ou si la facture sortante augmente. Pas urgent aujourd'hui.

**Options**
- Baisser à `3/minute` par IP
- Exiger l'auth (et casse le pré-remplissage côté landing — pas idéal pour la conv)
- Cacher les résultats par URL (TTL 24h) — réduit la charge sortante de 80%+

**Effort** : S.

---

## P3 — À traiter quand le produit pivote

### F8. Multi-tenancy / workspace

**Constat code** : tables `users`, `biblio_cards`, `sources` partagent une séquence UUID flat. Pas de `workspace_id` ni de `org_id`. Si Filum pivot vers du SaaS B2B (équipes de rédaction, agences de presse), le refactor coûtera des migrations en plusieurs étapes.

**Trigger** : décision produit B2B/B2B2C confirmée par signaux marché (au moins 3 prospects formulent le besoin "comptes équipe").

**Effort** : L (modèle de données + auth + UI dashboard équipe + facturation).

### F9. Backup PostgreSQL régulier hors-Railway

**Constat code** : actuellement le backup dépend du tier Railway (`docs/02-tech-architecture.md` cite "dump via dashboard Railway"). Si on bascule sur Infomaniak (ADR-022) ou si on grossit, ce backup manuel devient un risque.

**Trigger** : 100+ fiches publiées en prod, OU bascule d'hébergeur, OU avant de communiquer publiquement sur le produit (le jour où on est "en exploitation visible").

**Effort** : S–M selon la cible (`pg_dump` cron + objet S3 = simple ; backup incrémental WAL = plus complexe).

### F10. Refactor `client.ts` en séparant domain / transport

**Constat code** : `apps/frontend/src/lib/api/client.ts` est un seul gros objet `api` avec sous-clés (`auth`, `cards`, `sources`, `users`, `attestations`). Pas de souci aujourd'hui (200 lignes). Si la surface d'API double, splitter en modules par domaine sera plus lisible.

**Trigger** : `client.ts` dépasse 400 lignes ou plus de 4-5 développeurs touchent le frontend simultanément.

**Effort** : S (juste du déplacement).

### F11. Migration de purge des colonnes legacy (ADR-019 cleanup)

**Constat code** : les colonnes `canonical_hash` et `signature` sur `biblio_cards` ont été rendues nullable par migration 005 mais existent toujours physiquement. Depuis ADR-019, elles ne sont plus utilisées (la signature vit dans `content_attestations`). Pas de bug actif, juste du dead-storage.

**Trigger** : prochaine grosse migration de schéma — autant les drop par la même occasion.

**Effort** : S (`alembic revision` + drop column + tests).

---

## Items écartés (pour mémoire)

- **« HeroPulsar lazy-load manquant »** — finding hallucination de l'agent audit. Vérifié : `apps/frontend/src/lib/components/HeroPulsar.svelte:399` fait bien `import('ogl').then(...)`.
- **« STATE.md absent »** — autre hallucination. STATE.md existe et est à jour.
- **« Validation `url` perdue sur SourceCreate »** — autre hallucination. Le commentaire dans le code (`apps/backend/app/schemas/source.py:67`) documente explicitement que le retrait du champ override était voulu pour que `SourceBase.url`'s `Field(min_length, max_length)` soit hérité.
- **« Colonnes `canonical_hash`/`signature` mortes sur BiblioCard »** — l'agent confondait avec `ContentAttestation` (où ces colonnes sont LÉGITIMES). Le vrai dead-storage est sur `BiblioCard` (cf. F11 ci-dessus).

---

*Document créé suite à l'audit du 26 mai 2026 (cf. STATE.md). Mettre à jour quand un item est traité ou quand son trigger se réalise.*
