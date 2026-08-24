---
contract: "Definition du pipeline et routing task-type vers stage."
layer: L1
---

# Pipeline

**Forme ICM** : Pipeline. Une fiche entre au `stages/01-brief`, sort publiée au `stages/07-publication`. Chaque étape lit le dossier `output/` précédent et écrit dans le sien.

**Unité de travail** : une fiche, identifiée par `slug`. Vit sous `runs/<slug>/`. Nouveau run = copier `runs/_example/` en `runs/<slug>/`.

**Factory vs. product** (invariant #5) :

- Factory : `shared/`, `_core/templates/`, `stages/*/CONTEXT.md`, `stages/*/references/`. Stable entre runs.
- Product : `runs/<slug>/stages/0N-*/output/`. Nouveau à chaque run.

## Task routing

| Type de tâche                          | Va à                                      |
| -------------------------------------- | ----------------------------------------- |
| Nouvelle fiche depuis brief rempli     | `stages/01-brief/CONTEXT.md`              |
| Collecte et enrichissement des sources | `stages/02-sources-collectees/CONTEXT.md` |
| Rédaction annotations et positions     | `stages/03-annotations/CONTEXT.md`        |
| Extraction et pose des verbatim        | `stages/04-extraits/CONTEXT.md`           |
| Confirmation des connexions au graphe  | `stages/05-connexions/CONTEXT.md`         |
| Relecture qualité et verdict           | `stages/06-relecture/CONTEXT.md`          |
| Publication et vérifs post-publish     | `stages/07-publication/CONTEXT.md`        |

## État dérivé du filesystem (invariant #9)

Une étape est terminée si son `output/` contient au moins un fichier autre que `.gitkeep`. Le trigger `status` scanne tous les `runs/<slug>/stages/0N-*/output/` et rend un diagramme ASCII :

```
Pipeline Status: <slug>

  01-brief  ->  02-sources-collectees  ->  03-annotations  -> ...
  COMPLETE      COMPLETE                    PENDING
  (brief.md)    (sources.md, ids.json)      (empty)
```

## Boucle courte

Une étape N ne s'exécute que si N-1 a un `output/` non vide et que sa `Checkpoints` a été passée. Un défaut trouvé plus tard = retour à l'étape défaillante, correction, output remis à jour. Le filesystem supporte les allers-retours par conception.
