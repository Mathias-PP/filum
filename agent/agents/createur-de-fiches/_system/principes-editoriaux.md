# Ce qui fait une bonne fiche Philum

Une fiche Philum n'est pas une bibliographie. C'est **un lien de confiance** entre un contenu (vidéo, article, podcast) et ses fondations. Chaque source y a un rôle nommé, pas juste une existence.

## Les cinq propriétés d'une fiche parfaite

1. **Chaque source affirme quelque chose de précis.** Pas de source « en général » : on nomme ce qu'elle apporte au contenu documenté. Sans quoi la fiche est un tas de liens.
2. **Chaque source clé (pivot) porte au moins un extrait verbatim.** Sans extrait, une source pivot n'est pas prouvée ; c'est une affirmation d'affirmation.
3. **Chaque source déclare sa position** (`stance`) par rapport au propos qu'elle sert : appuie, nuance, contextualise, ou mentionne. `null` = silence assumé, pas position neutre.
4. **Les métadonnées bibliographiques sont exactes ou absentes**, jamais approximatives. DOI vérifié via Crossref, dates depuis la source elle-même, auteurs tels qu'ils signent.
5. **La fiche est branchée au graphe.** Si une des sources est déjà une fiche Philum publiée, la connexion doit être confirmée. Sinon, la fiche est un îlot.

## Ce qui n'est PAS une bonne fiche

- Une liste de 40 sources dont aucune ne porte d'extrait.
- Des `stance: null` partout (personne n'a rien à dire de la relation entre le contenu et ses sources).
- Des annotations qui paraphrasent le titre de la source (« Article scientifique sur la mémoire » pour un article intitulé « The role of sleep in memory consolidation »).
- Des extraits d'une phrase qui contiennent un pronom démonstratif sans antécédent visible (« Cela améliore la mémoire » : quoi, cela ?). Le garde-fou serveur les refuse maintenant, mais le principe est plus large : un extrait cité seul doit rester intelligible.
- Le titre de la fiche qui doublonne exactement le titre du contenu documenté, mot pour mot.

## Sources pivots

Marquer une source comme pivot (`is_pivot=True`) veut dire : **cette source porte la thèse**. Trois pivots maximum par fiche. Au-delà, la notion se dilue.

Une fiche sans pivot déclaré est presque toujours une fiche qui n'assume pas ce qu'elle affirme. Prendre le temps de nommer les pivots avant de rédiger les annotations.

## L'annotation d'une source

Une annotation dit ce que la source apporte à la fiche. Deux à quatre lignes. Ni résumé de la source, ni éloge : ce que le créateur de la fiche a pris dans cette source pour construire son propos.

Bon exemple :
> « Ce papier fige la mesure du 12 février 2025 : plasma stable à 1337 secondes sur WEST. C'est la ligne de base contre laquelle les progrès ultérieurs seront comparés. »

Mauvais exemple :
> « Article scientifique publié dans Nuclear Fusion sur le tokamak WEST. »

## Extraits (`add_excerpt`)

Un extrait est un **verbatim** copié à la lettre de la source, avec `context` qui nomme les référents des pronoms et situe le passage. Trois à cinq extraits par source clé, pas plus.

- Chaque extrait porte un titre court (2 à 6 mots) qui dit *ce qu'on trouve dedans*, pas un slogan éditorial.
- `context` doit rendre l'extrait intelligible seul. Si le passage commence par « Cela », dire ce que « cela » nomme.
- Un extrait long qui pose lui-même son contexte n'a pas besoin d'un `context` séparé.

## Titre et description de la fiche

Le titre décrit **ce que la fiche prouve**, pas juste ce que le contenu documenté raconte. Comparer :
- Titre du contenu : « WEST bat le record du plasma le plus long ».
- Titre de la fiche : « WEST et la préparation d'ITER : le tokamak du CEA bat les records de durée de plasma ».

La description (2 à 4 phrases) situe le contenu documenté et annonce ce que la fiche va prouver.

## Refuser une source

Une source proposée automatiquement (par extraction) qu'on n'utilise pas vraiment ne doit **pas** figurer dans la fiche pour la longueur. Retirer une source est un geste éditorial, comme l'ajouter.
