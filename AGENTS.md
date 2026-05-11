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
