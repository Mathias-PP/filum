---
contract: "Format d'un fichier d'agent et regles de validation appliquees au chargement."
layer: L1
---

# Agents : un fichier YAML par agent

Un agent est un fichier `agents/<slug>.yaml`. Il déclare quels outils l'agent a
le droit d'appeler, quels fichiers de configuration sont injectés dans son
contexte, et ce qu'il est censé faire.

Restreindre les outils n'est pas cosmétique. Un agent qui voit cinq outils au
lieu de trente-trois se trompe moins souvent d'outil, et son contexte tient en
quelques milliers de jetons au lieu de quarante mille.

## Champs

| Champ           | Obligatoire | Contenu                                                                       |
| --------------- | ----------- | ----------------------------------------------------------------------------- |
| `slug`          | oui         | Identifiant en kebab-case. Doit être égal au nom du fichier sans l'extension. |
| `name`          | oui         | Nom affiché dans le sélecteur d'agent.                                        |
| `contract`      | oui         | Une phrase : ce que l'agent fait, et ce qu'il ne fait pas.                    |
| `layer`         | non         | Layer ICM. `L1` pour un agent généraliste, `L2` pour un agent d'étape.        |
| `tools`         | oui         | Liste de noms d'outils. Un nom inconnu invalide le fichier.                   |
| `context`       | non         | Chemins de fichiers du workspace injectés dans le prompt système.             |
| `model_hint`    | non         | Modèle recommandé, à titre indicatif. Le créateur reste maître du choix.      |
| `system_prompt` | oui         | Instructions propres à cet agent, ajoutées aux règles communes.               |

## Validation

Un fichier invalide n'est pas chargé et n'apparaît pas dans le sélecteur. Sont
refusés : un `slug` qui ne correspond pas au nom du fichier, un outil inconnu,
une liste `tools` vide, un chemin de `context` hors du workspace.

Un chemin de `context` qui pointe vers un fichier absent est toléré : il est
simplement ignoré à l'injection. Supprimer un fichier de référence ne doit pas
casser tous les agents qui le citent.

## Écrire son propre agent

Copier un fichier existant, changer le `slug` et le nom du fichier, retirer les
outils dont l'agent n'a pas besoin. Les agents livrés avec Philum sont recréés
par « Restaurer template » s'ils sont supprimés ; un agent que vous avez ajouté
n'est jamais touché.

## Ce qu'un `system_prompt` n'a pas à redire

Les règles communes (agir plutôt que planifier, ne rien fabriquer de mémoire,
verbatim dans la langue de la source, corriger avant de supprimer) sont déjà
posées pour tous les agents. Les répéter dilue les instructions propres à
l'agent.
