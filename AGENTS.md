# Instructions pour agents IA autres que Claude Code

Ce fichier est destiné aux agents IA qui ne reconnaissent pas automatiquement `CLAUDE.md`. Il contient les mêmes règles essentielles que [`CLAUDE.md`](./CLAUDE.md) — lis ce dernier en complément si tu sais le faire.

Compatible avec : Aider, OpenAI Codex CLI, Continue.dev, Cursor, opencode, et tout autre agent capable de lire des fichiers du repo.

---

## Comment se synchroniser au projet en début de session

Lis dans l'ordre :

1. `README.md` — vue d'ensemble et stack technique
2. `STATE.md` — où en est le projet à l'instant T
3. `DECISIONS.md` — décisions prises antérieurement (ne pas remettre en cause sans raison)
4. `.docs/01-product-spec.md` — features et scénarios
5. `.docs/02-tech-architecture.md` — choix d'architecture
6. Tout autre `.docs/` pertinent pour la tâche en cours

Une fois ce contexte chargé, tu disposes du même niveau d'information qu'un Claude Code en session continue.

**`STATE.md` contient en particulier** :
- Une section « État production vérifié » : faits constatés par `curl` sur les URL prod, pas par re-lecture de la doc.
- Une section « Prochaines étapes par priorité » (P0 → P4). Commence par le P0 du moment sauf demande explicite contraire. Le P0 actuel décrit souvent un effet vitrine cassé sur la démo publique (`/@example/memoire-et-cerveau`).

---

## Stack technique non négociable

Voir [`CLAUDE.md`](./CLAUDE.md) section « Stack et choix techniques ». Résumé :

- Backend : Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL / DuckDB / dbt-core
- Frontend : SvelteKit / TypeScript / Tailwind
- Outils : `uv` (Python), `pnpm` (Node), `ruff`, `prettier`, `pytest`, `vitest`
- Déploiement : Railway (backend) + Vercel ou Netlify (frontend)

Ne propose pas d'alternatives sans demande explicite.

---

## Conventions de code et de commit

Voir [`CLAUDE.md`](./CLAUDE.md). Résumé :

- Async par défaut côté backend
- Typage strict (Pydantic v2, TypeScript strict)
- Conventional commits (`feat:`, `fix:`, `docs:`, etc.)
- Migrations Alembic versionnées
- Tests sur le code qui compte (crypto, endpoints mutables, extraction)

---

## Pièges déjà rencontrés (à NE PAS répéter)

Vécus en production sur ce repo. Détails complets dans `CLAUDE.md`, mais les essentiels :

**Backend / Alembic / SQLAlchemy**
- ID de révision Alembic ≤ **32 caractères** (colonne `alembic_version.version_num` est `VARCHAR(32)`). Au-delà → `StringDataRightTruncationError` au commit du `UPDATE alembic_version` → rollback total → Railway crash-loop. Convention : `00X_<courte_description>`.
- `Column(..., ForeignKey(...), index=True)` dans `create_table` crée déjà l'index `ix_<table>_<col>`. **Ne pas** doubler avec `op.create_index` derrière (DuplicateTableError → rollback).
- Aucun nouveau champ sur `sources` / `biblio_cards` ne doit entrer dans le `canonical_hash` payload (cf. `apps/backend/app/services/card.py` 96-105 / 161-169 et `app/scripts/seed_demo.py`). Sinon les fiches déjà signées deviennent invérifiables.
- `MissingGreenlet` : tout accès à une relation ORM async **après** `await db.commit()` doit avoir été `selectinload`-é avant le retour. Chaînage explicite : `selectinload(BiblioCard.sources).selectinload(Source.excerpts)`.
- `datetime.utcnow()` est déprécié en Python 3.12. Utiliser `datetime.now(UTC).replace(tzinfo=None)` pour matcher les colonnes `DateTime` sans `timezone=True`.
- Toutes les variables d'env en **lowercase** (ADR-010, `case_sensitive=True` dans pydantic-settings). UPPERCASE = silent fallback aux defaults sur Linux/CI.
- `cors_origins` Railway : JSON array sérialisé, ex `'["https://filum-eight.vercel.app","http://localhost:5173"]'`. Toute nouvelle origine à ajouter ici.
- Cookies auth : actuellement `samesite=lax`. À basculer en `samesite=none + secure=True` quand OAuth Google sera branché (cross-origin Vercel ↔ Railway).
- Lancer `uv run ruff format app/` **avant** chaque commit backend (pas juste `--check`). La CI bloque sinon.

**Frontend / SvelteKit / D3**
- pnpm **10.33.4** pinned via `packageManager` dans `apps/frontend/package.json` (ADR-013). Ne pas upgrade vers pnpm 11.
- D3 : importer depuis `'d3'` (umbrella), pas `'d3-force'` etc. (transitives non déclarées). Typer `.selectAll<SVGGElement, T>('g')` avant `.data().join()`.
- `.style('display', flag ? '' : 'none')` — pas `null` (types d3 plus stricts, échec build).
- SSR : `+layout.ts` est `ssr = false`. Surcharger via `+page.ts` (`export const ssr = true`) seulement sur les routes publiques qui en ont besoin. Les composants utilisant `document`/`window` (D3) doivent être dynamic-imported côté client.
- `tsconfig.json` ne doit pas redéclarer `paths`/`baseUrl` (conflit avec `.svelte-kit/tsconfig.json`). Les alias viennent de `svelte.config.js` → `kit.alias`.
- `toLocaleDateString` n'accepte pas `timeStyle` ; utiliser `toLocaleString` pour date+heure.
- `$page.params.<X>` est typé `string | undefined` même si la route le garantit ; utiliser `?? ''`.
- `<aside role="dialog">` lève un warning a11y. Utiliser `<div role="dialog" aria-modal="true">`.

**Tests / CI**
- Les tests backend ne tournent pas sur Windows (case-insensitivity env vars + `case_sensitive=True` pydantic). Lancer `ruff`/`mypy` localement, faire confiance à la CI Linux pour `pytest`.

**Git / déploiement**
- `git` Windows n'est pas dans le PATH ; passer par WSL : `wsl bash -lc 'cd /mnt/c/Users/mathi/Documents/filum_project/filum && git ...'`.
- `gh` CLI dispo via WSL, déjà authentifié.
- **Vérifier l'état exact de la branche distante avant de merger une PR**. Un cas vécu : un commit de fix poussé en dernier n'a pas été inclus dans le squash (cause exacte non élucidée). Toujours faire `git fetch && git log origin/<branche> -3 -- <fichier-critique>` ou consulter la diff de la PR sur GitHub avant le `gh pr merge`.
- Railway + Vercel auto-redeploy sur `git push origin main`. Pas de workflow CD séparé (ADR-015). Si Railway crash-loop sur une migration → la transaction DDL rollback à chaque essai, donc la DB n'est PAS corrompue ; il suffit de pousser le fix et attendre le prochain build.
- `_commit_msg.txt` est gitignored ; ne pas le commit. Utiliser `git commit -F _commit_msg.txt && rm _commit_msg.txt`.

---

## Maintenance du contexte projet

À la fin de chaque session de travail significative :

1. Mets à jour `STATE.md` avec ce qui a avancé, ce qui est en cours, ce qui est bloqué
2. Si tu as pris une décision technique non triviale, ajoute une entrée dans `DECISIONS.md`
3. Si tu as ajouté une feature, mentionne-la dans `CHANGELOG.md`

C'est ce qui permet à toi-même (ou à un autre agent) de reprendre efficacement à la session suivante.

---

## Format de communication avec le développeur humain

- Sois concis, pas de paraphrase de la demande
- Présente un plan court avant les modifications importantes
- Signale les ambiguïtés plutôt que de deviner silencieusement
- Quand tu ne peux pas répondre à 100 %, dis-le

---

*Ce projet est conçu pour être co-développé par plusieurs agents IA au fil du temps. La discipline documentaire est ce qui garantit la cohérence.*
