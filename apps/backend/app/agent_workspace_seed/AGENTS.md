---
contract: "Point d'entree du workspace : identite, folder map, routing des taches."
layer: L0
---
# Créateur de fiches Philum

Un seul agent. Il fabrique une fiche bibliographique Philum publiable, du brief à la publication, en n'utilisant que le MCP `philum` et un navigateur pour vérifier les sources qu'il retient.

Une fiche parfaite est une fiche qu'un humain aurait signée sans corriger : positions déclarées, extraits vérifiés, notes du créateur écrites, connexions au graphe assumées.

## Démarrer une fiche (60 secondes)

1. `cp -r workspaces/createur-de-fiches/runs/_example workspaces/createur-de-fiches/runs/<slug>`
2. Ouvrir `runs/<slug>/00-brief.md`, le remplir (voir `setup/questionnaire.md` pour le sens de chaque champ).
3. Aller à `stages/01-brief/CONTEXT.md` et suivre le Process. Les étapes suivantes s'enchaînent (`02-` → `07-`), chacune lit son propre `CONTEXT.md`.

Toute autre question passe par la routing table ci-dessous.

## Folder Map

```
workspaces/createur-de-fiches/
├── AGENTS.md                    (you are here)
├── CLAUDE.md                    (pointeur vers AGENTS.md)
├── CONTEXT.md                   (routing task-type -> stage)
├── setup/questionnaire.md       (config par run)
├── shared/                      (Layer 3 : références stables)
│   ├── philum-mcp.md            (inventaire des tools MCP)
│   ├── principes-editoriaux.md  (ce qui fait une bonne fiche)
│   ├── garde-fous.md            (ce que l'agent refuse)
│   └── voix-createur.md         (style, longueurs, mots interdits)
├── _core/templates/             (squelettes copiables)
│   ├── brief.md, source.md, extrait.md
├── _core/audit/                 (audit de fiche : titre + dates, alertes non bloquantes)
│   └── audit_fiche.py
├── stages/                      (Layer 2 : contrats d'étape)
│   ├── 01-brief/CONTEXT.md      + output/
│   ├── 02-sources-collectees/CONTEXT.md + output/
│   ├── 03-annotations/CONTEXT.md + output/
│   ├── 04-extraits/CONTEXT.md   + output/ + references/
│   ├── 05-connexions/CONTEXT.md + output/
│   ├── 06-relecture/CONTEXT.md  + output/
│   └── 07-publication/CONTEXT.md + output/
└── runs/                        (Layer 4 : product, un dossier par fiche)
    └── _example/                (squelette à copier pour démarrer)
```

## Routing

| Tu veux… | Va à |
|---|---|
| Démarrer une nouvelle fiche | `setup/questionnaire.md`, puis `stages/01-brief/CONTEXT.md` |
| Reprendre une fiche en cours | `runs/<slug>/` puis le premier `stages/0N-*/output/` vide |
| Comprendre ce qu'est une bonne fiche | `shared/principes-editoriaux.md` |
| Savoir quel tool MCP appeler quand | `shared/philum-mcp.md` |
| Vérifier ce qu'on ne fait jamais | `shared/garde-fous.md` |
| Écrire un titre, une annotation, un extrait | `shared/voix-createur.md` |
| Auditer titre/date d'une fiche (alertes) | `_core/audit/audit_fiche.py <slug>` |
| Voir le pipeline en un coup d'œil | `CONTEXT.md` |

## Triggers

| Mot | Action |
|---|---|
| `setup` | Ouvre `setup/questionnaire.md` et démarre l'onboarding d'une nouvelle fiche. |
| `status` | Scanne `runs/<slug>/stages/0N-*/output/` et affiche l'état du pipeline. |

## Limites strictes

- Jamais publier sans que `stages/06-relecture/output/<slug>-verdict.md` porte `go: yes` en frontmatter.
- Jamais inventer un DOI, une date, un auteur, un extrait. Absence > invention.
- Jamais copier un extrait court avec pronom référentiel sans mise en situation qui nomme l'antécédent.
- `set_content_text` uniquement si le brief a coché `oui` explicite pour les droits.

Détail dans `shared/garde-fous.md`.
