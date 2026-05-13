# Skills — index

> Compétences spécialisées. Chaque skill est un **mémo opérationnel** pour une catégorie de tâches : que faire, dans quel ordre, où regarder, quels pièges éviter.
>
> Les skills ne remplacent pas les fichiers `.docs/` (spec) ni les ADR (décisions). Ils donnent le **comment** quand la décision et le quoi sont déjà tranchés.

---

## Quand ouvrir un skill

L'agent ne lit un skill que quand sa tâche en relève. Il **n'ouvre pas** tous les skills systématiquement (coût attention).

| Tâche | Skill |
|---|---|
| Toute migration de schéma BDD | [alembic-migrations](./alembic-migrations.md) |
| Composant Svelte, route, store, SSR | [frontend-svelte](./frontend-svelte.md) |
| Nouvel endpoint FastAPI, schéma Pydantic, service | [backend-fastapi](./backend-fastapi.md) |
| OAuth Google (jalon M1) | [oauth-google](./oauth-google.md) |
| Endpoint public sensible (extracteur, publish) | [rate-limiting](./rate-limiting.md) |
| Modification CI, déploiement | [ci-cd](./ci-cd.md) |
| Logs, monitoring, erreurs runtime | [observability](./observability.md) |

---

## Comment ajouter un skill

Quand un domaine est touché ≥ 2 fois et qu'à chaque fois l'agent doit redécouvrir les mêmes pièges :

1. Créer `skills/<nom-kebab>.md`
2. Suivre le template ci-dessous
3. Référencer le skill depuis [`../memory/INDEX.md`](../memory/INDEX.md) et ce README
4. Ouvrir une PR `docs: add skill <nom>`

### Template

```markdown
# Skill: <Nom>

> Quand l'utiliser — 1 phrase.

## Contexte

Pourquoi ce skill existe (1-3 phrases). Quel problème il résout.

## Checklist d'exécution

1. ...
2. ...
3. ...

## Pièges spécifiques

- ...

## Fichiers à connaître

- `chemin/fichier.py:lignes` — quoi
- ...

## Pour aller plus loin

- Lien vers ADR / .docs / code source
```

---

*Ce répertoire grossit organiquement. Pas plus d'1 skill par sujet. Pas de skill « divers ».*
