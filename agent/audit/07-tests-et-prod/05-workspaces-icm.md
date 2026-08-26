# 07-05 — Workspaces ICM (51 fichiers, ~3 000 LOC)

> **Fiche du lot 7.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G7**.
> **Dossier :** `workspaces/createur-de-fiches/` (51 fichiers).

## Rôle

Le workspace ICM de production : miroir du seed (`agent_workspace_seed/`) plus le questionnaire de dev (`setup/`), les runs d'exemple (`runs/`), et `CLAUDE.md`. C'est la source de vérité que `build_workspace_seed.py` copie vers le seed.

## Structure

### Configuration (identique au seed)
- `AGENTS.md`, `CONTEXT.md`, `CLAUDE.md`
- `agents/` : 7 agents YAML + CONTEXT.md
- `shared/` : 5 docs partagés
- `stages/` : 7 stages (01-brief → 07-publication) avec CONTEXT.md chacun
- `_core/templates/` : brief.md, extrait.md, source.md
- `_core/audit/audit_fiche.py`

### Développement
- `setup/questionnaire.md` (23 LOC) : questionnaire de configuration du workspace

### Runs d'exemple
- `runs/_example/` : brief, README, sources, annotations, extraits, connexions, relecture, publication
- `runs/stellaris-stellarator-centrale-fusion/` : run complet d'exemple sur un vrai sujet

## Fichiers spécifiques (non dans le seed)

| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `workspaces/createur-de-fiches/CLAUDE.md` | 1 | sha256: d5d6c817ff52ed7edcd72908c0c7d759a9f99787b8fd41ee597436eefebb57a2 | Instructions Claude (exclu du seed) |
| `workspaces/createur-de-fiches/setup/questionnaire.md` | 23 | sha256: d381f4ea24f2ad7ab66ed5f04cab8db049c0efdf4fddf86b48f22dd81e508f1a | Questionnaire de dev (exclu du seed) |
| `workspaces/createur-de-fiches/runs/_example/00-brief.md` | 34 | sha256: 7db403d720d00d7b60929734baed664a52f40c01f3a2e4361c6cfcc4a981a777 | Brief d'exemple |
| `workspaces/createur-de-fiches/runs/_example/README.md` | 19 | sha256: 907a291601e73f6228684d9cfaad3bc05ee5130ddc986e9d43fe72dbb0c11645 | README de l'exemple |

### Runs stellaris (12 fichiers)
Tous les fichiers sous `runs/stellaris-stellarator-centrale-fusion/` sont des données d'exemple (brief, card JSON, sources, annotations, extraits, connexions, relecture, publication).

## Invariants

- **Miroir** : les fichiers de configuration sont identiques au seed (même SHA256) — la sync est vérifiée par `test_workspace_seed_sync.py`.
- **Exclusions** : `CLAUDE.md`, `setup/`, `runs/` sont exclus du seed par `build_workspace_seed.py`.
- **Données d'exemple** : les runs sont des données readonly — pas de code à vérifier.

## Dettes

- Les runs d'exemple prennent 51 fichiers mais ne contiennent pas de code — le ratio LOC/fichier est faible.
- La duplication seed/workspace est intentionnelle (séparation dev/production) mais nécessite une discipline de sync.
