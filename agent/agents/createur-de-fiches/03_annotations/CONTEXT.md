# Étape 3 : Annotations et positions déclarées

**Reads**
- `runs/<slug>/02_sources-collectees/sources.md` (le catalogue des sources posées).
- `runs/<slug>/02_sources-collectees/ids.json` (les UUID pour rappeler `add_source`).
- `runs/<slug>/01_brief/brief.md` (la thèse : c'est contre elle qu'on positionne).
- `_system/principes-editoriaux.md` (l'annotation dit ce qu'on a *pris*).
- `_system/voix-createur.md` (ni « intéressant » ni « essentiel »).

**Does**
Pour chaque source, en particulier les pivots :

1. **Rédiger l'annotation** : 1 à 3 phrases, français, sans tiret cadratin. Ce que la source apporte à la fiche, pas ce que la source raconte. Voir `_system/voix-createur.md` pour la longueur et les mots interdits.
2. **Déclarer la position** (`stance`) :
   - `appuie` : la source défend la même chose que le propos.
   - `nuance-contredit` : la source dit quelque chose de différent, à mentionner pour l'honnêteté du dossier.
   - `contexte` : la source ne prend pas position mais éclaire l'arrière-plan.
   - `mentionne` : la source est citée sans être discutée.
   - Ne rien mettre (`null`) est valide : « je n'ai pas tranché » vaut mieux que « je mens ». Voir `_system/garde-fous.md`.
3. **Réappeler `mcp__philum__add_source`** avec les mêmes champs plus `annotation` et `stance`. Attention : l'API met à jour la source existante par identité URL/DOI (pas de doublon).

**Writes**
- `runs/<slug>/03_annotations/annotations.md` : une entrée par source annotée. Reprend le nom de la source pour lisibilité, puis l'annotation et la stance.
- Chaque appel `add_source` renvoie la version mise à jour : consigner l'ID dans les entrées.

**Human gate**
L'utilisateur ouvre `annotations.md` et vérifie chaque annotation :
- Est-ce qu'un lecteur qui n'a pas lu la source comprendrait *pourquoi* elle est ici ?
- Est-ce que la stance est cohérente avec l'annotation ?
- Est-ce qu'aucune annotation ne paraphrase le titre de la source ?

Corrections directes dans `annotations.md`, puis nouvel appel `add_source` pour propager. L'étape 4 démarre quand toutes les sources annotées sont validées.
