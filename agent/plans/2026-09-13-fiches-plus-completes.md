# Des fiches plus complètes, plus étayées, plus détaillées

> Établi le 2026-09-13, après le déroulé guidé (#660) et le banc d'essai (#662).
> Chaque constat dit s'il est **lu** (dans le code), **mesuré** ou **vérifié en
> ligne** (source citée). Rien n'est encore mesuré au banc.

## Le principe

**Une source sans extrait est quasi inutile**, surtout dans une fiche sujet :
elle affirme qu'un document existe sans rien montrer de ce qu'il dit. Ce qui
rend une fiche meilleure, c'est **le nombre d'extraits pertinents**. Pour en
trouver davantage, il faut **explorer davantage de sources**.

Il en découle trois règles pour l'agent, quel que soit le modèle :

1. **Explorer large** : beaucoup de sources candidates, de natures variées.
2. **Ne retenir que ce qui porte** : une source n'entre dans la fiche qu'avec au
   moins un extrait pertinent. Une candidate qui n'en donne aucun est écartée,
   et son écart est noté dans le compte rendu.
3. **Extraire à fond** : une source retenue donne tous les passages qui servent
   la fiche, jusqu'au découpage intégral quand tout son texte sert.

Aucun plafond fixé d'avance, ni en sources ni en extraits. L'exploration
s'arrête quand elle ne rapporte plus d'extraits nouveaux sur ce qui reste à
couvrir.

## Pour tous les sujets

La fiche « arthrose » a servi de cas d'étude, rien de plus. Philum doit tenir
sur une question d'histoire (« pourquoi l'empire romain d'Occident est-il
tombé ? »), d'économie (« la taxe carbone réduit-elle les émissions ? »), de
technique (« comment fonctionne un réacteur à neutrons rapides ? »), de culture,
de droit, de sport ou d'actualité. Chaque proposition ci-dessous doit donc
marcher sans supposer une discipline, et les outils de recherche doivent couvrir
d'autres terrains que la littérature biomédicale.

---

## A. Explorer plus de sources, et plus variées

### A1. Un plan de couverture avant de chercher

**Lu** : l'étape « recherche » du déroulé guidé lance quelques `web_search` sur
la question entière.

**Proposition** : une étape 0 découpe la question en sous-questions, écrites
dans `runs/<slug>/plan.md`. Pour « la taxe carbone réduit-elle les émissions ? » :
effets mesurés par pays, secteurs touchés, effets de fuite, acceptabilité,
redistribution, résultats contraires. Chaque sous-question devient une cible de
recherche et d'extraction. Un petit modèle y gagne le plus : il traite une
sous-question à la fois.

### A2. Une recherche par type de source, pas un seul moteur

**Lu** : l'agent ne découvre des sources que par `web_search` (Tavily, huit
résultats génériques). OpenAlex et Europe PMC sont déjà branchés, mais seulement
pour résoudre un DOI déjà connu.

**Proposition** : un outil de recherche qui interroge plusieurs familles et dit
de quelle famille vient chaque résultat :

| Famille | Exemples de sources | Pour quelles questions |
|---|---|---|
| Littérature scientifique, toutes disciplines | OpenAlex | sciences, sciences humaines, économie |
| Biomédical, texte intégral | Europe PMC ([doc](https://europepmc.org/RestfulWebService), gratuit et sans clé) | santé |
| Institutions et données publiques | sites gouvernementaux, agences, organisations internationales | politiques publiques, statistiques, droit |
| Presse et médias de référence | recherche web restreinte aux titres de presse | actualité, controverses |
| Encyclopédies et leurs références | Wikipédia comme point d'entrée vers ses sources citées | tout sujet, pour trouver les références |
| Contenus longs | transcriptions de vidéos et de podcasts (`get_youtube_transcript` existe côté MCP) | vulgarisation, entretiens |

Un plan de couverture qui touche plusieurs familles rend des sources plus
nombreuses et moins redondantes.

**Vérifié en ligne, à contrôler en prod** : depuis le 13 février 2026, OpenAlex
exige une clé d'API gratuite. Sans clé, le budget tombe à 100 crédits par jour ;
avec une clé, 100 000 ([annonce](https://groups.google.com/g/openalex-users/c/rI1GIAySpVQ),
[authentification](https://help.openalex.org/api/authentication/)). Le code
appelle `api.openalex.org` sans clé : la résolution des métadonnées et de
l'accès libre est peut-être déjà bridée en production.

### A3. Suivre les références

Une bonne source cite celles qui comptent. **Propositions** :

- depuis un article, remonter ses références et les travaux qui le citent
  (OpenAlex) ;
- depuis une page web, suivre les liens de sa bibliographie
  (`import_from_content_url` et `parse_biblio` existent) ;
- depuis Wikipédia, prendre les sources citées plutôt que la page.

C'est la méthode d'un documentaliste, et elle multiplie les candidates
pertinentes par construction.

### A4. Préférer les sources lisibles en entier

**Lu** : quand seul le résumé est lisible, `add_excerpt` refuse, et la source
reste sans extrait. **Proposition** : la recherche remonte l'adresse du texte
intégral quand elle existe (accès libre, dépôt, archive), et c'est elle qui est
explorée. Une candidate illisible passe après les lisibles.

### A5. La nature et la solidité de chaque candidate

**Proposition** : chaque résultat de recherche porte sa nature, lue dans les
métadonnées quand elles la disent, et l'exploration commence par le haut de
l'échelle propre au sujet :

| Terrain | Du plus solide au moins solide |
|---|---|
| Science et santé | recommandations, revues systématiques, essais, études observationnelles, avis |
| Histoire, droit | sources primaires (textes, archives, décisions), travaux de référence, synthèses, commentaires |
| Économie, politiques publiques | données officielles, évaluations, études, rapports d'organisations, tribunes |
| Actualité | documents d'origine, dépêches, enquêtes, analyses, opinions |

Aujourd'hui `shared/qualite-des-sources.md` le demande en prose, que l'agent ne
relit pas. Les candidates du bas de l'échelle ne sont pas exclues : elles
passent après, et leur nature est dite dans l'annotation.

### A6. Partir de ce que Philum sait déjà

**Lu** : `search_my_excerpts` (recherche par le sens, en production) et
`find_cards_citing` existent. **Proposition** : l'exploration commence par les
fiches publiques et les extraits déjà vérifiés sur le même sujet.

---

## B. Aucune source sans extrait, et le plus d'extraits pertinents

### B1. Une source n'entre dans la fiche qu'avec ses extraits

**Lu** : le déroulé guidé ajoute les sources à l'étape 2, puis cherche leurs
extraits à l'étape 3. Une source dont aucun passage n'est trouvé reste dans la
fiche, sans extrait. `add_source` accepte pourtant déjà des `excerpts` à la
pose, avec la même vérification qu'`add_excerpt`.

**Propositions** :

1. **Fusionner les étapes sources et extraits en une exploration** : pour chaque
   candidate, lire, trouver les passages, puis `add_source` avec ses extraits en
   un seul appel. Sans passage retenu, la candidate est écartée et notée.
2. **Garde serveur sur les fiches sujet** : `add_source` sans extrait est refusé
   quand l'appelant est l'agent. Le créateur, dans l'interface, garde la main.
3. **Relecture** : une source sans extrait restée dans une fiche (ajout manuel,
   extrait supprimé) est signalée, avec la proposition de l'explorer ou de la
   retirer.

### B2. Le serveur propose des passages, le modèle choisit

**Lu** : la recherche d'extraits par le sens tourne en production (seuil mesuré à
0,60). **Proposition** : pour chaque sous-question, le serveur découpe le texte de
la candidate, classe ses passages par proximité de sens, et en rend les
meilleurs. Le modèle ne génère plus de verbatim : il retient les passages
pertinents et écrit leur mise en situation. Les refus d'extrait disparaissent
par construction, et un petit modèle devient capable d'extraire autant qu'un
grand, puisqu'il juge au lieu de recopier.

### B3. Une passe par source, dans un contexte isolé

**Mesuré** : lire trois pages dans un même tour ajoutait 60 000 caractères au
contexte. **Proposition** : l'exploration lance une boucle courte par candidate,
qui ne voit que cette source, le plan de couverture et les passages proposés.
Les candidates passent en parallèle quand le fournisseur l'accepte. C'est ce qui
permet d'explorer beaucoup de sources sans saturer le contexte.

### B4. Extraire à fond les sources qui portent le sujet

**Lu** : les principes éditoriaux autorisent le découpage intégral quand tout le
texte sert, et `chunk_text` existe. **Proposition** : quand une candidate donne
beaucoup de passages pertinents, elle passe en extraction exhaustive : chaque
passage autonome qui sert une sous-question est posé, seules les redites et les
transitions sont écartées.

### B5. Chercher aussi ce qui nuance, dans chaque source

**Proposition** : chaque candidate est aussi interrogée sur ses propres limites
et réserves. Une source qui écrit qu'une conclusion reste discutée donne
souvent l'extrait le plus utile de la fiche.

### B6. Une mise en situation pour chaque extrait

**Proposition** : chaque extrait retenu porte sa mise en situation, obligatoire
quand sa langue diffère de celle de la fiche (point laissé ouvert par le lot 4).

### B7. Pas de redite

**Lu** : les extraits sont indexés par le sens. **Proposition** : un passage trop
proche d'un extrait déjà posé sur la fiche est écarté, pour que le nombre
d'extraits monte par apport et non par répétition.

---

## C. Des fiches plus détaillées, sans rien inventer

### C1. Une annotation de source structurée

**Proposition** : ce que la source apporte à la fiche, sa nature (étude,
rapport, article de presse, entretien), sa méthode quand elle en a une, ses
limites, sa date. Vérifiée par le juge de fidélité qui existe déjà.

### C2. Une synthèse ancrée par sous-question

**Proposition** : l'étape bilan rédige, pour chaque sous-question, un paragraphe
dont chaque phrase porte l'identifiant de l'extrait qui l'étaye. Le serveur
vérifie qu'aucune phrase n'est sans renvoi et que chaque renvoi existe, avant
d'écrire la synthèse dans la fiche.

### C3. Pivots et connexions

**Proposition** : marquer pivots les sources qui portent une sous-question, et
relier la fiche aux fiches Philum qui citent les mêmes sources.

---

## D. Continuer tant que ça rapporte

### D1. Un relecteur qui renvoie à l'exploration

**Proposition** : après chaque passe, une grille calculée par le serveur :

- sous-questions sans extrait ;
- sources sans extrait ;
- positions sans appui ;
- absence de nuance ;
- une seule famille de sources ;
- rétractations (vérification déjà en place).

Chaque manque relance l'exploration sur ce qui manque, avec de nouvelles
requêtes.

### D2. Une borne par rendement, pas par nombre

**Proposition** : l'exploration continue tant que les dernières candidates
explorées apportent des extraits nouveaux sur les sous-questions encore mal
couvertes. Elle s'arrête quand une série de candidates n'apporte plus rien, ou
sur « Arrêter ». Le mur de 20 minutes et la pause « Continuer » restent les
garde-fous techniques.

### D3. Un indicateur de couverture dans la fiche en direct

**Proposition** : la fiche en direct affiche, par sous-question, le nombre
d'extraits et de sources, et les candidates écartées. Le créateur voit ce qui
avance et ce qui manque, l'agent le lit par `fiche_state`.

---

## E. Adapter au modèle

| | Petit modèle | Grand modèle |
|---|---|---|
| Unité de travail | une candidate, une sous-question | plusieurs sous-questions par candidate |
| Extraits | retenus parmi les passages proposés (B2) | cherchés et retenus, extraction exhaustive plus fréquente |
| Relecture | grille calculée par le serveur | grille, plus une relecture rédigée |
| Parallélisme | candidates en file | candidates en parallèle |

**Routage par étape** : quand plusieurs clés ou lanes existent, l'exploration
mécanique va au modèle le plus économe, la synthèse et la relecture au plus
capable. Le champ `model_hint` des agents existe et n'est pas utilisé.

---

## F. Mesurer

Le banc (#662) doit suivre ce principe :

- **Chiffres à suivre** : extraits pertinents par fiche, sources sans extrait (à
  zéro), candidates explorées et écartées, couverture du plan, familles de
  sources.
- **Questions du banc** : elles couvrent aujourd'hui surtout la santé et la
  science. Il faut les élargir à l'histoire, l'économie, la technique, la
  culture, le droit et l'actualité.

---

## Ordre proposé

| # | Contenu | Pourquoi |
|---|---|---|
| 1 | Vérifier la clé OpenAlex en prod (A2) | bug possible déjà en production |
| 2 | Exploration atomique : source posée avec ses extraits, ou écartée (B1), garde serveur sur les fiches sujet | règle la source sans extrait tout de suite |
| 3 | Passages proposés par le serveur (B2), une passe par candidate (B3) | plus d'extraits, sans refus, y compris pour un petit modèle |
| 4 | Plan de couverture (A1), borne par rendement (D2), indicateur (D3) | explorer large et savoir quand s'arrêter |
| 5 | Recherche par famille de sources et suivi des références (A2, A3, A4) | plus de candidates, de toutes natures, sur tout sujet |
| 6 | Relecteur qui renvoie à l'exploration (D1), extraction exhaustive (B4), nuance par source (B5) | approfondissement |
| 7 | Synthèse ancrée (C2), annotation structurée (C1), redites (B7) | fiches plus longues et traçables |
| 8 | Banc élargi à toutes les disciplines (F), routage par étape (E) | mesurer et optimiser |
