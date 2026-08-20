# Ce qui fait une bonne fiche Philum

Une fiche Philum n'est pas une bibliographie. C'est un **lien de confiance** entre un contenu (vidéo, article, podcast) et ses fondations. Chaque source y a un rôle nommé, pas juste une existence.

## Les cinq propriétés d'une fiche parfaite

1. **Chaque source affirme quelque chose de précis.** Pas de source « en général » : on nomme ce qu'elle apporte au contenu documenté. Sans quoi la fiche est un tas de liens.
2. **Chaque source pivot porte au moins un extrait verbatim.** Sans extrait, une source pivot n'est pas prouvée ; c'est une affirmation d'affirmation.
3. **Chaque source déclare sa position** (`stance`) par rapport au propos : appuie, nuance, contextualise, ou mentionne. `null` = silence assumé, pas position neutre.
4. **Les métadonnées sont exactes.** Titre de la fiche = titre exact du contenu. Date de publication (fiche et sources) renseignée quand elle existe, prise sur le contenu lui-même. DOI vérifié via Crossref pour les articles scientifiques, auteurs tels qu'ils signent.
5. **La fiche est branchée au graphe.** Si une source est déjà une fiche Philum publiée, la connexion doit être confirmée. Sinon la fiche est un îlot.

## Ce qui n'est PAS une bonne fiche

- Une liste de 40 sources dont aucune ne porte d'extrait.
- Des `stance: null` partout (personne n'a rien à dire de la relation entre le contenu et ses sources).
- Des annotations qui paraphrasent le titre de la source (« Article scientifique sur la mémoire » pour un article intitulé « The role of sleep in memory consolidation »).
- Des extraits d'une phrase avec pronom démonstratif sans antécédent visible (« Cela améliore la mémoire ». Quoi, cela ?). Le garde-fou serveur les refuse, mais le principe est plus large : un extrait cité seul doit rester intelligible.
- Une source dont la date de publication est connue mais absente de la fiche (« s. d. »), ou une fiche qui affiche une date qui n'est pas celle du contenu documenté.

## Sources pivots

`is_pivot=True` veut dire : cette source porte la thèse. Pas de plafond arbitraire : une fiche peut légitimement avoir deux, cinq ou dix pivots selon le nombre de pans que la thèse recouvre. Sur un sujet qui documente plusieurs facettes distinctes (opération, fabrication, mesures, interactions...), chacune mérite son pivot si un papier différent la porte. Ce qui compte : chaque pivot porte quelque chose que la fiche perdrait s'il disparaissait. Une fiche sans aucun pivot déclaré est presque toujours une fiche qui n'assume pas ce qu'elle affirme.

## L'annotation d'une source

Une annotation dit ce que la source **apporte** à la fiche. Deux à quatre lignes. Ni résumé, ni éloge : ce que le créateur a pris dans cette source pour construire son propos.

Bon exemple :
> Ce papier fige la mesure du 12 février 2025 : plasma stable à 1337 secondes sur WEST. C'est la ligne de base contre laquelle les progrès ultérieurs sont comparés.

Mauvais exemple :
> Article scientifique publié dans Nuclear Fusion sur le tokamak WEST.

## Extraits

Un extrait est un **verbatim** copié à la lettre, avec `context` qui nomme les référents et situe le passage. Trois à cinq extraits par source pivot, pas plus.

- Titre court (2 à 6 mots) qui dit ce qu'on trouve dedans, pas un slogan.
- `context` rend l'extrait intelligible seul. Si le passage commence par « Cela », dire ce que « cela » nomme.
- Un extrait long qui pose lui-même son contexte n'a pas besoin d'un `context` séparé.
- Un extrait très court (trois mots, une formule) est acceptable si le `context` en fait la mise en situation. Le critère n'est pas la longueur : c'est l'intelligibilité une fois cité seul.

## Titre et description de la fiche

**Le titre de la fiche EST le titre exact du contenu documenté.** Aucune reformulation, aucun ajout, aucune traduction : le titre de la fiche est celui que l'auteur du contenu a publié, quelle que soit la nature du contenu (article scientifique, article de blog, vidéo, livre, podcast…). La fiche documente un contenu précis ; l'afficher sous un autre titre la rend non vérifiable.

- Titre du contenu (vidéo) : « WEST bat le record du plasma le plus long ».
- Titre de la fiche : « WEST bat le record du plasma le plus long » (identique).

Description : 2 à 4 phrases. Situer le contenu documenté et annoncer ce que la fiche prouve. C'est la description qui porte la lecture éditoriale, pas le titre.

## Dates de publication

**Une date de publication doit figurer quand elle existe** — sur la fiche (celle du contenu documenté) et sur chaque source.

- La date se prend sur le **contenu lui-même** : date affichée par la vidéo, pied de page du blog, page de l'éditeur, métadonnées de la page (`/sources/extract`), Crossref en source complémentaire pour les articles scientifiques.
- Une date connue qui manque est une erreur : jamais de « s. d. » quand la date est trouvable.
- Une date réellement introuvable est acceptée mais **tracée** : noter « pas de date trouvée » dans l'audit, jamais un simple oubli.

## Alertes, pas de blocage

Les vérifications de titre et de dates émettent des **alertes** qui alimentent le verdict de relecture. Aucune alerte ne bloque automatiquement la publication : la décision appartient à l'humain, mais rien ne doit passer silencieusement.

## Refuser une source

Une source proposée automatiquement qu'on n'utilise pas vraiment ne doit **pas** figurer dans la fiche pour la longueur. Retirer une source est un geste éditorial, comme l'ajouter.
