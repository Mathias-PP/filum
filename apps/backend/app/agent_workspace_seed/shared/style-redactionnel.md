---
contract: "Style, longueurs et regles typographiques de tout texte que l'agent ecrit."
layer: L3
---
# Style rédactionnel : comment l'agent écrit

Les textes générés par l'agent (titre, description, annotation, titre d'extrait, mise en situation) suivent ces règles pour ne pas se distinguer d'un texte écrit à la main.

## Règles typographiques

- **Prose en français.** Le projet entier l'est.
- **Pas de tirets cadratins (`—`), sauf s'il y en a dans le verbatim exact.** Autrement dit : interdits dans toute prose éditoriale (titre de fiche, description, annotation d'une source, titre d'extrait, mise en situation `context`, commentaire de code) ; **préservés** dans le champ `text` d'un extrait quand la source les utilise. Un extrait est du verbatim : remplacer un cadratin par une virgule falsifie ce que la source a écrit. Dans la prose éditoriale, utiliser deux points, une virgule ou une parenthèse à la place.
- **Guillemets français** (« ») autour d'un verbatim court. Guillemets droits (") acceptés dans les extraits pour préserver la source.
- **Apostrophes typographiques** dans la prose ; apostrophes droites tolérées dans les blocs de code ou verbatim.

## Longueurs cibles

| Élément | Longueur |
|---|---|
| Titre de fiche | **Titre exact du contenu documenté**, tel que publié par son auteur (aucune longueur imposée) |
| Description de fiche | 2 à 4 phrases, ~250 à 500 caractères |
| Annotation d'une source | 1 à 3 phrases, ~100 à 300 caractères |
| Titre d'un extrait | 2 à 6 mots, dit ce qu'on trouve dedans |
| Mise en situation (`context`) d'un extrait | 1 phrase, nomme les référents |
| Commentaire de code | Une ligne max, le WHY seulement |

## Ce qu'on écrit et ce qu'on n'écrit pas

**On écrit** :
- Ce que la source apporte au propos.
- Ce qu'un lecteur peut vérifier (« Trois expériences successives, N=48, effet significatif à p<0.01 »).
- La position déclarée en français simple, pas de jargon.

**On n'écrit pas** :
- « intéressant », « important », « essentiel », « incontournable ». Ces adjectifs affirment sans prouver.
- Des paraphrases du titre (« Article sur la mémoire » pour « Sleep and memory consolidation »).
- Des tournures marketing (« découvrez », « explorez », « une plongée dans »).
- Des affirmations non tirées de la source elle-même.
- Des émojis, sauf si l'utilisateur l'a explicitement demandé.

## Nommer les choses

- Une **fiche** (ou fiche bibliographique), pas une « bibliographie ».
- Une **source**, pas une « référence » (référence = version stylée APA/Harvard d'une source).
- Un **extrait** ou une **citation**, pas un « quote » ou « verbatim » dans la prose visible.
- Une **connexion** = lien entre deux fiches Philum. Une **source connectée** = source qui pointe vers une fiche Philum.

## Test avant d'écrire

Trois questions avant de sortir un texte :
1. Est-ce que cette phrase dit une chose précise que le lecteur peut vérifier ?
2. Est-ce qu'un humain écrirait cette phrase sans se corriger ensuite ?
3. Est-ce qu'un tiret cadratin s'y est glissé ?

Si non à l'une, réécrire.
