# La voix : ce qu'un texte Philum sonne

Les textes générés par l'agent (titre, description, annotation, titre d'extrait, mise en situation) suivent ces règles pour ne pas se distinguer d'un texte écrit à la main.

## Règles typographiques

- **Prose en français.** Le projet entier l'est (interfaces, commits, code).
- **Pas de tirets cadratins (« — »).** Utiliser deux points, une virgule, ou une parenthèse à la place. Règle du projet, à respecter partout : titre, description, annotation, extrait, mise en situation, commentaire de code.
- **Guillemets français** (« ») autour d'un verbatim court. Guillemets droits (" ") acceptés dans les extraits pour préserver la source.
- **Apostrophes typographiques** (') dans la prose, apostrophes droites (') tolérées dans les blocs de code ou verbatim.

## Longueurs cibles

| Élément | Longueur |
|---|---|
| Titre de fiche | 40 à 90 caractères, phrase complète, sans doublon avec le titre du contenu |
| Description de fiche | 2 à 4 phrases, ~250 à 500 caractères |
| Annotation d'une source | 1 à 3 phrases, ~100 à 300 caractères |
| Titre d'un extrait | 2 à 6 mots, dit ce qu'on trouve dedans |
| Mise en situation (`context`) d'un extrait | 1 phrase, nomme le référent des pronoms |
| Commentaire de code | Une ligne max. Le WHY seulement, jamais le WHAT |

## Ce qu'on écrit et ce qu'on n'écrit pas

**On écrit** :
- Ce que la source apporte au propos (« Ce papier fige la mesure du 12 février 2025... »).
- Ce qu'un lecteur peut vérifier (« Trois expériences successives, N=48, effet significatif à p<0.01 »).
- La position déclarée en français simple, jamais un jargon.

**On n'écrit pas** :
- Le mot « intéressant », « important », « essentiel », « incontournable ». Ces adjectifs affirment sans prouver.
- Des paraphrases du titre (« Article sur la mémoire » pour « Sleep and memory consolidation »).
- Des tournures marketing (« découvrez », « explorez », « une plongée dans »).
- Des affirmations non tirées de la source elle-même.
- Des émojis, sauf si l'utilisateur l'a explicitement demandé.

## Nommer les choses

- Une fiche n'est pas une « bibliographie » : c'est une **fiche** (ou une **fiche bibliographique**).
- Une source n'est pas une « référence » : c'est une **source**. « Référence » désigne la version stylée (APA, Harvard...) d'une source.
- Un extrait est un **extrait** ou une **citation**, jamais un « quote » ou un « verbatim » dans la prose visible.
- Une connexion est un lien entre deux fiches Philum. Une source qui pointe vers une fiche Philum est une **source connectée**.

## Test avant d'écrire

Avant de sortir un texte, l'agent se pose trois questions :
1. Est-ce que cette phrase dit une chose précise que le lecteur peut vérifier ?
2. Est-ce qu'un humain écrirait cette phrase sans se corriger ensuite ?
3. Est-ce qu'un tiret cadratin s'y est glissé ?

Si la réponse à l'une de ces questions est non, réécrire.
