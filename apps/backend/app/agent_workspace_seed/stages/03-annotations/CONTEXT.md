---
contract: "Contrat de l'etape 03 : rediger les annotations et positions par source."
layer: L2
---

# 03-annotations

## Scope

Rédiger la note du créateur et déclarer la position (`stance`) pour chaque source posée à l'étape 02.

## Inputs

| Source                | File                                                | Section                                    | Why                                    |
| --------------------- | --------------------------------------------------- | ------------------------------------------ | -------------------------------------- |
| Catalogue des sources | `../02-sources-collectees/output/<slug>-sources.md` | Full file                                  | Liste et ordre des sources             |
| Mapping UUID          | `../02-sources-collectees/output/<slug>-ids.json`   | Full file                                  | `source_id` pour rappeler `add_source` |
| Brief propre          | `../01-brief/output/<slug>-brief.md`                | Section « Thèse en une phrase »            | Contre quoi on positionne              |
| Règles d'annotation   | `../../shared/principes-editoriaux.md`              | « L'annotation d'une source »              | Ni résumé, ni éloge                    |
| Mots interdits        | `../../shared/style-redactionnel.md`                | « Ce qu'on écrit et ce qu'on n'écrit pas » | Éviter les adjectifs vides             |
| Règles de stance      | `../../shared/garde-fous.md`                        | « Sur la position déclarée »               | Pas de défaut `appuie`                 |

## Process

1. Pour chaque source, en particulier les pivots, rédiger l'annotation : 1 à 3 phrases, français, sans tiret cadratin.
2. Déclarer la `stance` : `appuie`, `nuance-contredit`, `contexte`, `mentionne`, ou laisser `null`.
3. Appeler `mcp__philum__update_source(source_id, annotation=..., stance=...)` pour poser annotation et position déclarée sur chaque source. Ne modifie que les champs passés, préserve le reste.

## Outputs

| Artifact             | Location                       | Format                                   |
| -------------------- | ------------------------------ | ---------------------------------------- |
| Annotations rédigées | `output/<slug>-annotations.md` | Markdown (une entrée par source annotée) |

## Checkpoints

| After Step | Agent Presents                               | Human Decides                                               |
| ---------- | -------------------------------------------- | ----------------------------------------------------------- |
| 1          | Annotations rédigées pour les pivots d'abord | Signer, corriger, ou réécrire                               |
| 2          | Table `source -> stance choisie`             | Confirmer les positions ou signaler celles à laisser `null` |

## Audit

| Check                      | Pass Condition                                                                                                  |
| -------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Aucune paraphrase du titre | L'annotation n'est pas une reformulation du titre de la source                                                  |
| Aucun mot interdit         | Absence de « intéressant », « important », « essentiel », « incontournable », « découvrez », « explorez »       |
| Stance cohérente           | Une source `stance=nuance-contredit` est adossée à au moins un extrait (posé à l'étape 04) qui montre la nuance |
| Longueurs                  | Annotations 100 à 300 caractères                                                                                |
| Aucun tiret cadratin       | `grep "—"` sur `<slug>-annotations.md` retourne 0                                                               |
