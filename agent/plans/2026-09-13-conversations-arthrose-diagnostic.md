# Conversations « arthrose » : diagnostic de l'agent

> Établi le 2026-09-13 à partir des deux conversations de production lues en base,
> en lecture seule, et du code de `main` à `626beb5`.
>
> - **A**, « comment prévenir l'arthrose? », 08:52, modèle forcé
>   `ministral-8b-latest` : 211 messages, 9 messages utilisateur.
> - **B**, « Fait une fiche pour répondre à la question : comment prévenir
>   l'arthrose ? », 08:57, mode gratuit : 60 messages, 1 message utilisateur.
>
> Chaque point dit comment il a été établi : **mesuré** (en base), **lu** (dans le
> code), ou **probable**.

---

## Ce que les conversations ont produit

Deux fiches en brouillon sur le même sujet, aucune publiée.

| Fiche | Créée | Nature | Sources | Extraits |
|---|---|---|---|---|
| `prevention-arthrose` | 08:55 (A) | sujet | 4, dont Inserm sans extrait | 4, tous retrouvés |
| `prevention-arthrose-strategies-scientifiques` | 08:58 (B) | **contenu**, avec la page OMS comme « contenu » | 5, dont une sans titre | 6, tous retrouvés |

La garde d'ancrage a tenu : **aucun extrait posé n'est faux**. Tout ce qui suit
porte sur ce que l'agent a dit, sur la façon dont il s'y est pris, et sur la forme
des données.

---

## A. Ce que l'utilisateur lit est trompeur

### A1. La réponse finale est un empilement de narration, pas un bilan

**Mesuré, puis lu.** La réponse finale de B (4 017 caractères) est le plan rédigé
*avant* d'agir, recollé aux phrases de transition, suivi de « [Réponse
interrompue] ». Ce plan présente trois verbatims comme le contenu de la fiche :

- l'OMS, paraphrasée, qui n'est pas l'extrait réellement posé ;
- les recommandations belges, dans une version longue refusée cinq fois ;
- **l'OARSI, jamais posée, sur une page jamais lue** (0 caractère de texte).

Dans A, les dernières réponses font 9 115 et 21 159 caractères : des plans répétés
à chaque relance.

**Cause** : `reponse_finale` accumule tous les `message_delta` du tour
(`agent_chat.py:262-267`), de tous les appels au modèle.

**Correction** : la réponse finale est le texte du dernier appel au modèle,
après sa dernière action. Les textes intermédiaires restent dans le fil comme
narration, repliés dans le bloc d'activité. Et le serveur ajoute un **bilan
calculé à partir des actions réussies** (« 3 sources ajoutées, 2 extraits posés,
5 refusés »), que le modèle ne peut pas contredire.

### A2. L'agent répond de mémoire

**Mesuré.** Premier message de A : une liste de conseils (poids, exercice,
alimentation anti-inflammatoire) sans une seule source ni un seul appel d'outil.
La règle `shared/rien-de-memoire.md` existe, mais c'est une consigne, pas une
garantie.

**Correction** : tout message de l'assistant qui affirme sans avoir lu quoi que ce
soit dans le tour est marqué « sans source » dans l'interface, de façon visible.

### A3. Des positions « appuie » que rien n'étaye

**Mesuré.** Les neuf sources des deux fiches sont toutes « appuie ». L'Inserm n'a
aucun extrait, l'OARSI avait une page illisible au moment de l'ajout, et la
Fondation de l'Avenir parle d'injection de cellules souches, un traitement
expérimental et non de la prévention. Aucune recherche de nuance ou de
contradiction n'a été faite, pour une question médicale.

**Correction** : une source sans extrait ne peut pas porter une position ; la
recherche de ce qui nuance devient une étape du déroulé de fiche, dont le
résultat est déclaré même quand il est vide.

---

## B. L'agent tourne en rond sur les verbatims

### B1. Il reconstitue au lieu de copier

**Mesuré.** Dans A, 73 refus « ce passage ne figure pas dans la source » sur 83
appels à `add_excerpt`. Dans B, 5 refus sur 7. Après chaque refus, l'agent
réécrit une variante de sa paraphrase au lieu de relire la page.

**Correction**, structurelle plutôt que dans le prompt :
- rendre le passage le plus proche **dès le premier refus** quand la page en
  contient un ressemblant (aujourd'hui, seulement pour les variantes très proches) ;
- après trois refus sur une même source sans relecture de la page entre-temps,
  refuser `add_excerpt` en l'exigeant ;
- donner un outil qui cherche un passage dans la source et rend des verbatims
  candidats à copier.

### B2. Les césures de PDF font échouer l'ancrage

**Lu.** Cinq refus sur les recommandations belges avant succès : le PDF porte
« démo-graphiques », mot coupé en fin de ligne, et `_normalise`
(`excerpt_anchor.py:77`) ne réduit que les espaces.

**Correction** : recoller les césures de fin de ligne dans la normalisation, en
gardant la table d'offsets vers le texte réel.

### B3. `provided_text` détourné

**Mesuré.** L'agent passe sa propre paraphrase comme « texte fourni » à
`suggest_excerpts` et `annotate_excerpt`. Les suggestions et la mise en situation
sont alors calculées sur son propre texte, pas sur la source.

**Correction** : `provided_text` demande une approbation sur tous les outils, pas
seulement sur `add_excerpt`, et il est refusé quand la page est lisible.

### B4. Appels répétés pour rien

**Mesuré.** `verify_excerpts` appelé 16 fois sur la même source dans A, sans
écriture entre deux ; le même PDF de 25 Ko lu deux fois dans B ; des identifiants
d'extrait ou de source tronqués ou inventés. La garde « appel identique déjà
échoué » ne couvre que les échecs.

**Correction** : l'étendre aux appels réussis dont le résultat n'a pas pu changer,
et répondre depuis le cache avec une note.

---

## C. Les données sont mal formées

### C1. Une fiche en double

**Mesuré.** B a créé une seconde fiche sur le même sujet sans chercher l'existant,
alors que A venait d'en créer une et que l'utilisateur écrivait « La fiche
Prévention de l'arthrose existe déjà !! ».

**Correction** : `create_card` cherche les fiches du créateur au titre proche, et
refuse en les nommant.

### C2. Une fiche « contenu » sans contenu

**Mesuré.** La fiche de B est « contenu », avec la page de l'OMS comme contenu
documenté, alors que c'est une question, donc une fiche « sujet ». La
documentation de l'outil le dit pourtant (« Dans le doute, c'est une fiche sujet »).

**Correction** : refuser une fiche « contenu » dont l'adresse est aussi celle d'une
de ses sources.

### C3. Métadonnées perdues ou fausses

**Mesuré.**
- Les recommandations belges sont sans titre : le résolveur n'a rien rendu, et la
  proposition du modèle a été écartée. Le PDF porte pourtant son titre.
- L'OMS est classée « article de presse », avec « chercheur » comme type d'auteur
  dans A.
- L'OARSI, simple page web, est classée « article scientifique ».

**Correction** : quand le résolveur ne rend aucun titre, garder la proposition en
la marquant « déclarée, non résolue » ; lire le titre d'un PDF dans ses
métadonnées.

### C4. Extraits mal découpés

**Mesuré.** Un extrait « Les 10 messages clés » avec ses sauts de ligne bruts, un
extrait anglais sans mise en situation dans une fiche française, un extrait sur la
prévalence dans une fiche sur la prévention.

**Correction** : normaliser les sauts de ligne à l'enregistrement, et exiger une
mise en situation quand la langue de l'extrait diffère de celle de la fiche.

---

## D. La boucle et son affichage

### D1. Le flux est coupé vers 5 minutes

**Mesuré.** Le tour de B a duré 309 secondes, et le serveur a écrit « [Réponse
interrompue] ». **Lu** : le proxy `/api` du front passe par une fonction Vercel
(`adapter-auto`, aucun `maxDuration`), et la documentation de Vercel annonce
300 secondes par défaut avec Fluid compute, plafond en offre gratuite.

**Correction** : faire parler le navigateur directement à l'API pour le flux de
l'agent, et afficher « l'agent termine en arrière-plan » pendant la reprise plutôt
qu'une erreur.

### D2. Messages utilisateur en double

**Mesuré.** Dans A, chaque demande figure deux fois (08:52:17 et 08:54:55, 08:55:01
et 08:55:09, 09:01:39 et 09:04:46). **Probable** : renvoi ou « Réessayer » après une
réponse qui ne venait pas, qui réinscrit le message ; le modèle reçoit deux fois la
même demande.

**Correction** : un message identique au précédent, après un tour sans réponse,
n'est pas réinscrit.

### D3. Horodatage et consommation faux

**Mesuré.** Tous les messages d'un tour portent l'heure de fin : B va de 09:02:14 à
09:02:24 pour un tour commencé à 08:57. Aucun message ne porte de compte de jetons.

**Correction** : horodater chaque message à sa production, et remonter la
consommation des lanes gratuites.

---

## Découpage proposé

| # | Contenu | Pourquoi d'abord |
|---|---|---|
| 1 | A1 et A2 : réponse finale réduite au dernier texte, bilan calculé par le serveur, marque « sans source » | ce que l'utilisateur lit est faux aujourd'hui |
| 2 | D1 : flux direct vers l'API, reprise sans erreur | les tours longs, ceux qui construisent une fiche, sont coupés |
| 3 | B1 à B4 : césures, passage proche dès le premier refus, blocage après trois refus, recherche de verbatim, `provided_text` sous approbation, cache des appels répétés | les boucles coûtent le plus de temps et de jetons |
| 4 | C1 à C4 : doublon refusé, contenu distinct des sources, titres déclarés, extraits normalisés | la qualité de la fiche produite |
| 5 | A3, D2, D3 : positions étayées, recherche de nuance, messages dédoublonnés, horodatage et consommation | l'hygiène de la conversation |

---

## Avancement

### Lots 1 et 2, réunis dans une PR : `fix/agent-reponse-finale`

Réunis parce qu'ils touchent les mêmes lignes, et parce qu'une cause commune a
été trouvée en les lisant : **quand la connexion tombait, le serveur annulait le
tour** (`task.cancel()` dans le `finally` du flux). Un téléphone mis en veille
ou verrouillé arrêtait l'agent au milieu d'une fiche, exactement comme la coupure
de Vercel à 300 secondes. Le commentaire du front qui affirmait l'inverse était
faux.

- **Tour détaché de la connexion** (`services/agent_tours.py`) : le tour tourne
  dans une tâche à part, avec sa propre session de base. Chaque événement est
  numéroté et gardé en mémoire jusqu'à deux minutes après la fin.
- **Rattachement** : `GET /agent/sessions/{id}/flux?depuis=N` rejoue ce que le
  client n'a pas reçu, puis la suite en direct. Le front s'y rattache sur toute
  coupure, y compris un flux fermé proprement sans événement de fin (proxy), et
  réessaie dès que la page redevient visible ou que le réseau revient. D1 est
  donc réglé sans flux direct vers l'API : chaque rattachement repart pour cinq
  minutes.
- **Arrêter** passe par `POST /agent/sessions/{id}/arreter` : fermer l'onglet
  n'arrête plus rien. Le travail déjà fait est persisté, le texte coupé marqué.
- **D2** : un envoi pendant un tour en cours rend 409 `tour_en_cours` avant
  d'inscrire le message ; le front le remet dans la saisie et suit le tour.
- **A1** : la réponse persistée est le texte du dernier appel au modèle. Les
  événements de fin ne partent qu'une fois le tour écrit en base.
- **A1, bilan** : sous la dernière réponse de chaque tour, « Bilan : 2 sources
  ajoutées, 3 extraits posés, 5 extraits refusés. », compté sur les résultats des
  outils.
- **A2** : une réponse longue d'un tour sans aucun appel d'outil porte « Rédigé
  sans rien consulter ».

Reste : lots 3, 4 et 5.
