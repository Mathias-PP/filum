---
contract: "Cinq proprietes d'une fiche Philum reussie."
layer: L3
---
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

Les deux exemples ci-dessous décrivent une fiche imaginaire. Ils montrent une forme, ils ne disent rien du sujet que vous traitez.

Bon exemple :
> Ce papier fige la mesure de référence : la valeur relevée à cette date. C'est la ligne de base contre laquelle les progrès ultérieurs sont comparés.

Mauvais exemple :
> Article scientifique publié dans une revue à comité de lecture sur le même thème.

## Extraits

Un extrait est un **verbatim** copié à la lettre, avec `context` qui nomme les référents et situe le passage.

- Titre court (2 à 6 mots) qui dit ce qu'on trouve dedans, pas un slogan.
- `context` rend l'extrait intelligible seul. Si le passage commence par « Cela », dire ce que « cela » nomme.
- Un extrait long qui pose lui-même son contexte n'a pas besoin d'un `context` séparé.
- Un extrait très court (trois mots, une formule) est acceptable si le `context` en fait la mise en situation. Le critère n'est pas la longueur : c'est l'intelligibilité une fois cité seul.

### Combien d'extraits par source

Il n'y a **pas de quota**. Ce que porte une source dépend de la part de son contenu qui sert réellement la fiche. Les fourchettes ci-dessous sont des recommandations, pas des limites : le créateur tranche.

| Ce qu'est la source pour cette fiche | Fourchette |
|---|---|
| Contenu inaccessible, donc invérifiable ; ou source vraiment secondaire | 0 |
| Consultée pour un point précis : une citation, un chiffre, l'origine d'une info ; ou source clé mais très courte | 1 à 3 |
| Source clé dont une grande part du contenu porte sur le sujet de la fiche | 3 à 4 et au-delà |
| Source dont la quasi-totalité du propos sert la fiche | jusqu'au découpage intégral du contenu |

Découper une source de bout en bout est un usage légitime, pas un abus : quand tout le texte est pertinent, chaque passage devient consultable et recherchable. Le seul plafond est technique (200 extraits par source).

Ce qui disqualifie un extrait n'est jamais son rang dans la liste, c'est qu'il n'apporte rien : redite d'un extrait déjà posé, passage de transition, phrase qui ne dit rien du sujet de la fiche.

### Quelle longueur

Un extrait est lu par un humain qui le rencontre seul, et indexé pour la recherche par le sens. Les deux poussent dans la même direction : un passage assez large pour se comprendre, assez serré pour ne dire qu'une chose. En recherche documentaire, les unités qui se retrouvent le mieux sont celles qui tiennent une idée à la fois et se suffisent à elles-mêmes, pas les plus longues.

| Ce que fait l'extrait | Longueur indicative |
|---|---|
| Une formule, un chiffre, une dénomination que la fiche cite | 3 à 15 mots, `context` obligatoire |
| Une affirmation, une donnée située, un résultat | 15 à 80 mots, une à trois phrases |
| Un raisonnement, une nuance, une contradiction argumentée | 80 à 160 mots, sans dépasser le plafond serveur de 1 000 caractères |

Un passage qui dépasse se coupe **entre deux phrases**, jamais à l'intérieur de l'une d'elles, ou se pose en deux extraits consécutifs. Un extrait plus long qu'il n'a besoin de l'être noie ce qu'il prouve.

## Titre et description de la fiche

La règle est posée une seule fois, dans `garde-fous.md`, section « Sur les métadonnées » : le titre de la fiche est celui que l'auteur du contenu a publié, sans reformulation. La raison : la fiche documente un contenu précis, l'afficher sous un autre titre la rend invérifiable.

Description : 2 à 4 phrases. Situer le contenu documenté et annoncer ce que la fiche prouve. C'est la description qui porte la lecture éditoriale, pas le titre.

## Dates de publication

**Une date de publication doit figurer quand elle existe** : sur la fiche (celle du contenu documenté) et sur chaque source.

- La date se prend sur le **contenu lui-même** : date affichée par la vidéo, pied de page du blog, page de l'éditeur, métadonnées de la page (`/sources/extract`), Crossref en source complémentaire pour les articles scientifiques.
- Une date connue qui manque est une erreur : jamais de « s. d. » quand la date est trouvable.
- Une date réellement introuvable est acceptée mais **tracée** : noter « pas de date trouvée » dans l'audit, jamais un simple oubli.

## Alertes, pas de blocage

Les vérifications de titre et de dates émettent des **alertes** qui alimentent le verdict de relecture. Aucune alerte ne bloque automatiquement la publication : la décision appartient à l'humain, mais rien ne doit passer silencieusement.

## Refuser une source

Une source proposée automatiquement qu'on n'utilise pas vraiment ne doit **pas** figurer dans la fiche pour la longueur. Retirer une source est un geste éditorial, comme l'ajouter.
