# Le pipeline

**Forme** : Pipeline (ICM). Une fiche entre au `01_brief`, sort publiée au `07_publication`. Chaque étape lit le dossier précédent et écrit dans le sien.

**Unité de travail** : une fiche, identifiée par `slug`. Vit sous `runs/<slug>/`. Un nouveau run = copier `runs/_example/` en `runs/<slug>/`.

**Factory vs. product** :
- Factory (stable, réutilisée entre runs) : `_system/`, `_templates/`. Ne bouge pas d'un run à l'autre.
- Product (nouveau à chaque run) : `runs/<slug>/`. Contient un sous-dossier par étape numérotée du pipeline.

## Contrat général de chaque étape

Chaque `NN_.../CONTEXT.md` déclare quatre lignes non négociables :

- **Reads** : chemins exacts des fichiers qu'elle lit (un travail précédent + une référence factory).
- **Does** : ce que l'agent produit à cette étape.
- **Writes** : chemins exacts des fichiers qu'elle écrit dans `runs/<slug>/NN_.../`.
- **Human gate** : ce que l'utilisateur relit avant que l'étape suivante démarre.

## État de la fiche

L'état est dérivé du filesystem, pas d'un champ « status ». Une étape est faite si son dossier `output/` contient les fichiers attendus.

| Étape | Fichier qui prouve qu'elle est terminée |
|---|---|
| 01 | `runs/<slug>/01_brief/brief.md` (rempli, human gate passée) |
| 02 | `runs/<slug>/02_sources-collectees/sources.md` (liste triée, DOI/dates vérifiés) |
| 03 | `runs/<slug>/03_annotations/annotations.md` (une note par source clé) |
| 04 | `runs/<slug>/04_extraits/extraits.md` (extraits verbatim des sources pivot) |
| 05 | `runs/<slug>/05_connexions/connexions.md` (suggestions confirmées ou refusées) |
| 06 | `runs/<slug>/06_relecture/verdict.md` avec ligne `go: yes` |
| 07 | `runs/<slug>/07_publication/publication.md` (URL publique + timestamp) |

## Boucle courte

Une étape ne s'exécute que si l'étape N-1 a passé sa human gate. Si un défaut est trouvé en N+1, on revient à N, on corrige, on re-passe la gate. Le pipeline supporte les allers-retours par conception : le filesystem est un état lisible.

## Ce qui n'est PAS ici

- Pas de code d'orchestration : l'agent lit `CLAUDE.md`, choisit l'étape, lit son `CONTEXT.md`, agit.
- Pas de scripts qui pilotent le pipeline : le pipeline est le pipeline, pas un programme.
- Pas de dépôt de fichiers ailleurs qu'à l'endroit prévu : un lien beat une copie.
