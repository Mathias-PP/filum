# Memory INDEX

> Pointeurs vers les sources de vérité du projet, classés par usage. C'est la **mémoire externe** de l'agent : tout ce qu'il a besoin de savoir vit ici ou dans les fichiers référencés.

---

## Source de vérité unique par sujet

Quand deux fichiers disent des choses différentes, c'est le **fichier de gauche** qui gagne.

| Sujet | Source de vérité | Sources dérivées (ne pas modifier en premier) |
|---|---|---|
| État courant du projet | [`../../STATE.md`](../../STATE.md) | `PROJECT_SNAPSHOT.md`, descriptions PR |
| Vision long terme | [`../../.docs/00-vision.md`](../../.docs/00-vision.md) | `PROJECT_SNAPSHOT.md`, `README.md` |
| Spec produit MVP | [`../../.docs/01-product-spec.md`](../../.docs/01-product-spec.md) | `README.md` |
| Architecture technique | [`../../.docs/02-tech-architecture.md`](../../.docs/02-tech-architecture.md) | `README.md` stack |
| Modèle de données | [`../../.docs/03-data-model.md`](../../.docs/03-data-model.md) | Migrations Alembic |
| API design | [`../../.docs/04-api-design.md`](../../.docs/04-api-design.md) | OpenAPI live (`/api/v1/docs`) |
| Design system | [`../../.docs/05-design-system.md`](../../.docs/05-design-system.md) | Composants Svelte |
| Roadmap historique | [`../../.docs/06-roadmap.md`](../../.docs/06-roadmap.md) | — |
| Questions ouvertes | [`../../.docs/07-open-questions.md`](../../.docs/07-open-questions.md) | — |
| Glossaire | [`../../.docs/08-glossary.md`](../../.docs/08-glossary.md) | — |
| Mode privé / intégrations (spec) | [`../../.docs/09-private-mode-and-integrations.md`](../../.docs/09-private-mode-and-integrations.md) | — |
| Plan vers MVP complet | [`../../.docs/10-mvp-completion-plan.md`](../../.docs/10-mvp-completion-plan.md) | Tasks de session |
| Critique & améliorations | [`../../.docs/11-critique-and-improvements.md`](../../.docs/11-critique-and-improvements.md) | — |
| Décisions techniques (ADR) | [`../../DECISIONS.md`](../../DECISIONS.md) | Code, commits |
| Changelog | [`../../CHANGELOG.md`](../../CHANGELOG.md) | — |
| Règles Claude Code | [`../../CLAUDE.md`](../../CLAUDE.md) | — |
| Règles agents génériques | [`../../AGENTS.md`](../../AGENTS.md) | — |
| Sécurité (politique projet) | [`../../SECURITY.md`](../../SECURITY.md) | — |
| Contribution | [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) | — |

---

## Règles agent (ce dossier)

| Sujet | Fichier |
|---|---|
| Point d'entrée agent | [`../README.md`](../README.md) |
| Permissions | [`../PERMISSIONS.md`](../PERMISSIONS.md) |
| Workflow git | [`../GIT_WORKFLOW.md`](../GIT_WORKFLOW.md) |
| Sécurité agent | [`../SECURITY.md`](../SECURITY.md) |
| Pièges à éviter | [`../PITFALLS.md`](../PITFALLS.md) |
| Protocole de tâche | [`../TASK_PROTOCOL.md`](../TASK_PROTOCOL.md) |
| Snapshot projet condensé | [`./PROJECT_SNAPSHOT.md`](./PROJECT_SNAPSHOT.md) |

---

## Skills (compétences spécialisées)

| Skill | Fichier | Quand l'utiliser |
|---|---|---|
| Migrations Alembic | [`../skills/alembic-migrations.md`](../skills/alembic-migrations.md) | Tout changement de schéma |
| Frontend SvelteKit | [`../skills/frontend-svelte.md`](../skills/frontend-svelte.md) | Composant, route, store, SSR |
| Backend FastAPI | [`../skills/backend-fastapi.md`](../skills/backend-fastapi.md) | Endpoint, service, schéma Pydantic |
| OAuth Google | [`../skills/oauth-google.md`](../skills/oauth-google.md) | Jalon M1 |
| Rate limiting | [`../skills/rate-limiting.md`](../skills/rate-limiting.md) | Endpoint public sensible |
| CI/CD | [`../skills/ci-cd.md`](../skills/ci-cd.md) | Workflow GitHub Actions, déploiement |
| Observabilité | [`../skills/observability.md`](../skills/observability.md) | Logs, erreurs runtime, monitoring |

---

## URLs de référence (vivantes)

| Cible | URL | Vérifier comment |
|---|---|---|
| Backend prod | https://filum-production-07bb.up.railway.app | `curl .../health` |
| Backend API docs | https://filum-production-07bb.up.railway.app/api/v1/docs | Browser |
| Frontend prod | https://filum-eight.vercel.app | Browser |
| Fiche démo publique | https://filum-eight.vercel.app/@example/memoire-et-cerveau | Browser |
| Repo GitHub | https://github.com/Mathias-PP/filum | `gh repo view` |
| Runs CI | `gh run list --branch main --limit 5` | CLI |

---

## Mémoire intentionnellement absente

L'agent n'a **pas** d'accès direct à :
- L'inbox / mails du développeur
- Le dashboard Railway / Vercel (uniquement via le développeur)
- La BDD prod (uniquement via API)
- Les credentials Google OAuth
- Les conversations Slack/Discord (s'il y en a)

Si une information est nécessaire et absente : demander dans la conversation, ne pas inventer.

---

*Cet index est référencé par `agent/README.md` et `agent/TASK_PROTOCOL.md`. Maintenir à jour quand un fichier est ajouté ou renommé.*
