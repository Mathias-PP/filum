# Garde-fous : ce que l'agent refuse de faire

Chaque règle bloque une action, avec la raison. Aucune n'est négociable.

## Sur les extraits

- **Refuser un extrait de moins de 15 mots qui commence par un pronom référentiel** sans `context` qui nomme l'antécédent. Le serveur refuse déjà (garde-fou depuis PR #473). Mieux vaut ne pas appeler pour rien.
- **Refuser un extrait qui n'est pas vérifiable dans le texte de la source**. Toujours confirmer que le passage existe verbatim avant de l'ajouter.
- **Refuser de couper à l'intérieur d'une phrase pour raccourcir**. Élargir ou choisir un autre passage.
- **Refuser plus de 5 extraits par source**. Le serveur plafonne à 10 ; l'usage éditorial en autorise 3 à 5 pour les pivots, 1 à 2 pour les autres.

## Sur les auteurs

- **Refuser d'inventer un prénom ou un nom** quand la source signe par un pseudonyme, une initiale ou une institution.
- Les institutions se posent telles quelles : « American Nuclear Society », pas « Society, A.N. ». Les particules restent avec la famille : « van den Broeck », pas « Broeck, V.D. ».
- **Refuser de séparer un auteur institutionnel** avec `;` ou `,` si le nom contient plusieurs mots. Poser tel quel.

## Sur les métadonnées

- **Refuser d'inventer DOI, date, pagination, journal.** Absence > invention.
- **Vérifier via une source d'autorité** avant d'écrire :
  - DOI et référence complète : Crossref (`https://api.crossref.org/works/{doi}`) ou OpenAlex.
  - Date de publication : la source elle-même, jamais un tiers.
  - Auteurs : la source elle-même, dans l'ordre où ils y figurent.

## Sur la position déclarée (`stance`)

- **Refuser `stance=appuie` par défaut**. Le silence (`null`) est une position déclarée : « je n'ai pas tranché ». Plus honnête qu'un défaut.
- **`stance=nuance-contredit`** ne se pose que si l'agent a lu au moins un extrait où la source dit clairement quelque chose de différent du propos.

## Sur les pivots

- **Refuser plus de 3 pivots par fiche.** Un « tout est pivot » veut dire « rien n'est pivot ».
- **Refuser qu'une source pivot n'ait pas d'extrait.** Un pivot sans extrait est une affirmation d'affirmation.

## Sur le texte intégral (`set_content_text`)

- **Ne l'appeler QUE si le brief a coché `oui` explicite** pour les droits de publication. `confirm_publication_rights=True` engage la responsabilité du compte : ne jamais le passer sans validation utilisateur.
- **Ne pas coller un extrait > 500 000 caractères** : le serveur refuse. Un texte long se coupe en plusieurs sources.

## Sur la publication

- **Refuser de publier sans que `stages/06-relecture/output/<slug>-verdict.md` rende `go: yes`** en frontmatter. Une publication est un événement de feed unique : on ne rembobine pas.
- **Refuser de publier si un extrait est marqué `verified_status=missing`** sans autorisation utilisateur explicite.

## Sur le graphe

- **Refuser de laisser des connexions suggérées sans verdict** à l'étape 05. Chaque suggestion doit être soit confirmée soit refusée. Laisser pendant = « je n'ai pas voulu trancher », état interdit pour publier.
