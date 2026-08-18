# Étape 4 : Extraits verbatim

**Reads**
- `runs/<slug>/02_sources-collectees/sources.md` (repérer les pivots).
- `runs/<slug>/02_sources-collectees/ids.json` (`source_id` pour `add_excerpt`).
- `runs/<slug>/03_annotations/annotations.md` (savoir ce que chaque source apporte).
- `_templates/extrait.md` (structure d'un extrait).
- `_system/garde-fous.md` (les extraits refusés par le serveur et pourquoi).
- `_system/principes-editoriaux.md` (règle des pivots).

**Does**
Pour chaque source pivot (obligatoire) et chaque autre source clé (souhaitable) :

1. **Récupérer le texte de la source** :
   - Si `content_url` HTML : le fetch via l'API (`POST /api/v1/sources/{id}/excerpts/chunk` avec `text` collé, ou l'extracteur backend).
   - Si PDF : coller le texte extrait manuellement.
   - Si la page est bloquée (anti-bot, paywall) : demander à l'utilisateur de fournir le texte.
2. **Sélectionner 3 à 5 extraits par pivot, 1 à 2 par autres**. Les passages qui portent une affirmation clé de la source.
3. **Vérifier verbatim** : le passage sélectionné doit exister mot pour mot dans le texte de la source. Toute reformulation invalide l'extrait.
4. **Écrire la mise en situation** (`context`) : si l'extrait fait moins de 15 mots ou commence par un pronom référentiel (« cela », « il », « ces », « this », « that »...), obligatoire. Nommer le référent en clair. Sinon, laisser vide.
5. **Écrire le titre** de l'extrait : 2 à 6 mots, ce qu'on trouve dedans.
6. **Appeler `mcp__philum__add_excerpt(source_id, text, title?, context?)`**. Si le serveur refuse (garde-fou anti-hors-contexte), élargir le passage OU compléter le `context` puis rappeler.

**Writes**
- `runs/<slug>/04_extraits/extraits.md` : une entrée par extrait, groupé par source. Reprend titre + verbatim + `context` + `excerpt_id` retourné.
- Chaque extrait posé porte automatiquement `annotated_by_ai=True` (tag serveur : l'agent laisse la trace).

**Human gate**
L'utilisateur ouvre `extraits.md` et vérifie :
- Chaque extrait est bien un verbatim de la source (spot-check sur 2 ou 3).
- Aucun extrait ne semble être un contresens hors contexte.
- Chaque pivot a au moins 2 extraits.
- Les titres d'extraits sont des repères, pas des slogans.

L'étape 5 démarre après validation.
