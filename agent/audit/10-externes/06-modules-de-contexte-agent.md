# Conception 06. Modules de contexte pour l'agent Philum, et l'impossibilité structurelle d'inventer

> Troisième volet de la série ARS, après [`04-ars-claim-audit.md`](./04-ars-claim-audit.md) (ce qu'ARS fait) et [`05-fidelite-des-affirmations-conception.md`](./05-fidelite-des-affirmations-conception.md) (ce que Philum construit sur la fidélité). Celle-ci traite du **contexte que l'agent lit avant d'agir**, et de la doctrine qui doit le rendre incapable d'inventer.
>
> ARS est sous **CC BY-NC 4.0**. Aucune ligne de son code ni de sa prose n'est reprise. Tout ce qui suit décrit des idées en français, à réécrire de zéro.

> Lecture faite le 2026-09-10 : les quatre skills d'ARS et leurs 85 fichiers de référence, dont `academic-paper/references/anti_leakage_protocol.md`, `deep-research/references/source_quality_hierarchy.md`, `logical_fallacies.md`, `socratic_mode_protocol.md`, `interdisciplinary_bridges.md`, `literature_monitoring_strategies.md`, `academic-pipeline/references/plagiarism_detection_protocol.md`, `ai_research_failure_modes.md`, `shared/ground_truth_isolation_pattern.md`, `shared/cross_model_verification.md`, `evals/heldout/claim_standing_probe/`. Côté Philum : `app/agent_workspace_seed/` en entier, `mcp_server/tools_write.py`, `services/excerpt_insertion.py`.

---

## 1. Trois contraintes posées par le créateur, le 2026-09-10

Elles gouvernent tout ce document, et le plan d'implémentation à venir.

1. **Une invention doit être interdite et structurellement impossible.** Une règle de prompt qui dit « n'invente pas » n'est pas une réponse. Elle est violable et sa violation est indétectable.
2. **Le niveau d'exigence est maximal pour tous les domaines.** Ce qui vaut pour un créateur qui parle de physique vaut pour celui qui parle de cuisine ou d'histoire. Un module de qualité des sources conçu pour la science seule est refusé.
3. **L'agent doit être ouvert, et inciter à citer ce qui contredit ou nuance.** Une fiche qui ne cite que ce qui l'arrange est le mode de défaillance principal du produit, et c'est la contrainte qui inverse le sens du module « sophismes » d'ARS : sa forme négative détecte la sélection favorable, sa forme positive va chercher la contradiction.

---

## 2. Le point de départ : Philum a déjà la mécanique

`app/services/agent_workspace.py` gère un **workspace par créateur**, persisté en base, copie du gabarit `app/agent_workspace_seed/`. Racines fermées (`shared`, `stages`, `_core`, `runs`, `setup`, `agents`), chemins normalisés, `sha256` par fichier pour l'audit, portée stricte par `creator_id`.

Le gabarit compte aujourd'hui cinq modules `shared/` à frontmatter (`contract:`, `layer: L3`) et sept rôles en YAML sous `agents/` :

| Existant | Rôle |
|---|---|
| `shared/garde-fous.md` (57 l.) | ce que l'agent refuse, avec la raison de chaque refus |
| `shared/principes-editoriaux.md` (97 l.) | les cinq propriétés d'une bonne fiche, longueurs et fourchettes d'extraits |
| `shared/pieges-vecus.md` (127 l.) | erreurs constatées en usage réel |
| `shared/philum-mcp.md` (102 l.) | catalogue d'outils |
| `shared/style-redactionnel.md` (55 l.) | forme de la prose |
| `agents/*.yaml` | assistant, bibliographe, extracteur, publicateur, rechercheur, redacteur, relecteur |

**Un module en plus est donc un fichier en plus.** Rien à construire, et il est déjà éditable par le créateur puisque le workspace est le sien.

---

## 3. La doctrine : le modèle choisit, il ne saisit pas

C'est la réponse à la contrainte 1, et elle ne s'écrit pas dans un prompt, elle s'écrit dans les signatures d'outils.

**Principe.** Aucun champ de la base ne doit pouvoir recevoir un fait produit librement par le modèle. Pour tout fait, il existe un résolveur, et l'outil n'accepte qu'une valeur **issue d'une réponse de résolveur au cours du même tour**. Inventer cesse alors d'être interdit : il n'y a plus de porte par laquelle une invention entrerait.

**Où Philum tient déjà cette doctrine.**

- Un extrait ne peut pas être inventé. `add_excerpt` (`tools_write.py:535`) relit la page et refuse un passage qui n'y figure pas ; `excerpt_insertion.py:49` pose `SEUIL_TYPOGRAPHIQUE = 0.95` et refuse la paraphrase à l'insertion. C'est le modèle de ce qu'il faut faire partout ailleurs.
- Un ancrage inventé est impossible : les trois sélecteurs sont nullables et le commentaire du modèle de données dit pourquoi, « un ancrage inventé serait pire que pas d'ancrage » (`models/source_excerpt.py:54-58`).
- `ancrer()` rend `None` plutôt qu'un ancrage approximatif (`services/excerpt_anchor.py`).

**Où la porte est encore ouverte, et c'est là que le plan doit agir.**

- **Les métadonnées d'une source.** `add_source` (`tools_write.py:338`) appelle déjà `verifier_que_la_source_existe(url, doi)` : une URL dont le domaine n'existe pas, qui rend 404 ou 410, ou un DOI inconnu de Crossref, sont refusés. L'identité de la source passe donc bien par un résolveur. Restent libres, en texte brut, `title`, `authors`, `journal`, `published_at`, `publisher` et `annotation` : rien n'oblige ces valeurs-là à venir de la page ou d'un résolveur. `garde-fous.md` le couvre par une règle de prose, « refuser d'inventer DOI, date, pagination, journal », donc par une interdiction, pas par une impossibilité. La correction structurelle : l'outil ne reçoit plus les champs, il reçoit **l'identifiant d'une réponse de résolveur** (page consultée, Crossref, OpenAlex, métadonnées de la page) et le choix du modèle porte sur *laquelle*, jamais sur *quoi*. Ce qu'aucun résolveur ne rend reste vide, et le vide est un état affichable.
- **La mise en situation écrite sans avoir lu.** `annotate_excerpt` (`tools_write.py:1536`) fait rédiger `title` et `context` par un modèle. Quand aucun `provided_text` n'est fourni, le texte d'entourage se replie sur le titre et l'annotation de la source (`tools_write.py:1552-1554`). Le modèle rédige donc la mise en situation d'un passage **sans le texte qui l'entoure**. C'est une fabrication rendue possible par une valeur de repli. La correction structurelle : pas de texte d'entourage réel, pas d'annotation ; l'outil refuse au lieu de se rabattre.
- **La recherche web indisponible.** Si aucune source ne peut entrer sans passer par un résolveur, une recherche en panne ne produit plus de sources de mémoire : elle produit zéro source et un message. La panne devient visible au lieu d'être comblée.

**Ce qui ne peut pas être rendu impossible, et ce qu'on fait à la place.** Une mise en situation est de la prose libre : par nature, aucun schéma ne peut garantir sa fidélité. C'est exactement le périmètre du juge décrit dans la fiche 05, et c'est la raison d'être du juge. Là où l'impossibilité structurelle est atteignable, elle rend le juge inutile ; là où elle ne l'est pas, le juge prend le relais. Les deux ne se substituent pas, ils se partagent le terrain.

---

## 4. Les modules à ajouter

### 4.1 `shared/rien-de-memoire.md`

Source d'inspiration : le protocole anti-fuite d'ARS (`academic-paper/references/anti_leakage_protocol.md`).

Ce qu'ARS formule bien, et qu'il faut reprendre :

- La règle est une **priorité, pas une interdiction** : la matière de la session prime sur la mémoire du modèle. Formulée en interdiction pure, elle rendrait le modèle inutilisable.
- **La distinction fait / langue.** Le contenu factuel est contraint, la compétence de langue reste libre. Sans cette phrase, le modèle cesse d'écrire correctement.
- **Le manque se déclare.** Quand la matière ne couvre pas un point, on pose une balise de manque au lieu de combler. C'est le geste que Philum n'a nulle part : `garde-fous.md` dit « absence > invention » pour DOI, date et pagination seulement.
- **La revendication d'absence est un cas à part.** « Aucune étude ne dit X » n'est étayable par aucune source, par construction. ARS la rattache à la stratégie de recherche menée, avec ses termes et son périmètre, plutôt que de la traiter comme un manque. Une fiche Philum qui dit « il n'existe pas de travaux sur » relève exactement de ce cas.

Adaptation Philum : ce module dit ce qui doit venir de la session (tout fait, toute métadonnée, tout verbatim, toute date) et ce qui peut venir du modèle (la langue, la structure, la mise en forme). Il nomme le geste de déclaration de manque et sa forme dans le workspace.

### 4.2 `shared/qualite-des-sources.md`, généralisé à tous les domaines

Philum n'a **rien** sur la qualité d'une source. `principes-editoriaux.md` exige qu'une source « affirme quelque chose de précis » ; il ne dit jamais si elle vaut quelque chose.

Ce qu'ARS apporte, et qu'il faut prendre : **deux axes séparés, et la faute de les confondre.**

- Axe 1, la **nature de la preuve** : de quel type de matériau s'agit-il. Absolu, indépendant du domaine.
- Axe 2, l'**adéquation à l'affirmation dans les normes de son domaine** : est-ce la meilleure preuve que ce domaine offre pour ce qui est affirmé ici.

Leur propre document dit pourquoi les confondre est une faute : cela plafonne le travail interprétatif quelle que soit son excellence. Une source primaire d'archive est au bas de leur pyramide et reste la meilleure preuve que l'histoire offre pour une affirmation d'histoire.

**Ce qu'on refuse d'importer.** Leur pyramide à sept niveaux est médicale, méta-analyses en haut, avis d'expert en bas. Transposée telle quelle, elle décrète qu'un créateur qui parle de cuisine ou d'histoire ne cite jamais rien de bon. C'est le contraire de l'exigence maximale : c'est une exigence d'un seul domaine appliquée à tous.

**Ce que fait Philum à la place, et qui est plus exigeant, pas moins.** Le module ne classe pas les sources sur une échelle. Il pose **trois questions à toute source, dans tout domaine** :

1. **De quelle nature est cette preuve ?** Mesure, témoignage, document d'époque, démonstration, texte de loi, déclaration d'un acteur, synthèse d'autres travaux, opinion. Nommer, pas noter.
2. **Est-ce la meilleure preuve disponible pour ce qui est affirmé ici ?** Une recette exécutée par un chef est la meilleure preuve d'une technique et n'est aucune preuve d'un mécanisme physico-chimique ; un article de science alimentaire est l'inverse. La question n'est jamais « cette source est-elle bonne », toujours « est-elle bonne **pour cette affirmation-là** ».
3. **Est-elle ce qu'elle prétend être ?** C'est ici que la liste des douze signaux d'éditeur prédateur d'ARS se généralise : leur idée est qu'un objet peut porter tous les signes extérieurs de sa catégorie sans en être. Cela vaut bien au-delà des revues : ferme de contenu qui imite un média, site généré qui imite une encyclopédie, agrégateur qui republie sans attribuer, chaîne qui présente une opinion sous la forme d'un documentaire, communiqué qui se donne pour une étude.

Cette forme est plus exigeante que la pyramide, parce qu'elle ne laisse aucun domaine s'exempter : il n'y a pas de sujet où l'on puisse répondre « ici, la question ne se pose pas ».

### 4.3 `shared/chercher-la-contradiction.md`

Inspiration : le catalogue de sophismes d'ARS (`deep-research/references/logical_fallacies.md`), **retourné**.

Leur catalogue de trente entrées est un outil de détection, destiné à un agent d'avocat du diable. Une seule entrée compte vraiment ici, la **sélection favorable** : citer cinq travaux qui vont dans le sens de la thèse en taisant les douze qui n'y vont pas. Leur méthode de détection est bonne et simple : comparer les sources citées au résultat d'une recherche large sur le même sujet.

Mais la contrainte 3 du créateur inverse la priorité : Philum ne veut pas seulement détecter la sélection favorable, il veut **inciter à la contradiction**. Le module est donc écrit à l'endroit :

- Sur toute affirmation contestée, l'agent **cherche activement** ce qui la nuance ou la contredit, et le propose au créateur. Ne rien trouver est un résultat qui se dit ; ne pas avoir cherché n'en est pas un.
- Philum a déjà le champ pour l'accueillir : `stance` avec `nuance-contredit`, et `garde-fous.md` pose la bonne règle de pose, elle ne se déclare que si l'agent a lu un extrait où la source dit clairement autre chose. Ce qui manque n'est pas le champ, c'est **l'injonction d'aller chercher**.
- Une fiche dont toutes les sources appuient n'est pas suspecte en soi. Elle mérite une question, pas un reproche : le sujet est-il consensuel, ou la recherche a-t-elle été menée dans un seul sens.

Les deux autres entrées à garder du catalogue, parce qu'elles visent des gestes fréquents chez un créateur : l'**appel à l'autorité**, publié dans une revue prestigieuse donc valide, et l'**appel à la nouveauté**, plus récent donc meilleur.

### 4.4 `agents/socratique.yaml`

Inspiration : le mode socratique d'ARS (`deep-research/references/socratic_mode_protocol.md`). Ce n'est pas un module `shared/`, c'est un huitième rôle.

Un mode où l'agent **ne répond pas, il questionne**, pour amener le créateur à formuler ce que sa fiche affirme réellement. Cinq couches chez ARS, du cadrage du problème à l'auto-examen critique. Les questions qui transposent le mieux à une fiche Philum : quelle est la question à laquelle ce contenu répond, quelle preuve te convaincrait du contraire, comment quelqu'un qui pense l'inverse te réfuterait-il.

Deux règles de conception à reprendre telles quelles, parce qu'elles sont ce qui empêche le mode de se dégrader en générateur d'idées :

- **Non-génération stricte.** Même après plusieurs tours sans convergence, l'agent ne propose aucune thèse candidate. Il résume ce que le créateur a exprimé, nomme ce qui reste ouvert, continue de questionner.
- **Sortie annoncée.** Si le créateur demande explicitement des propositions, l'agent annonce la sortie du mode par un marqueur visible, et ce qui suit est étiqueté comme venant de lui, pas comme une idée du créateur. Il ne rentre jamais silencieusement dans le mode.

Ce mode croise directement la contrainte 3 : la couche d'auto-examen est le moment où la contradiction se cherche.

---

## 5. Les trois fichiers lus en dernier, et ce qu'il en reste

### 5.1 Détection de plagiat (`academic-pipeline/references/plagiarism_detection_protocol.md`, 239 lignes)

Conçu pour un manuscrit académique avant soumission. Trois choses seulement transposent.

- **Le seuil du verbatim non attribué**, vingt mots consécutifs identiques sans guillemets. Chez Philum le geste inverse existe déjà et est mieux tenu : un extrait *est* du verbatim, marqué comme tel, ancré et vérifié. Le risque Philum n'est pas le verbatim caché, c'est le contraire, le verbatim présenté comme de la prose du créateur dans `content_text`.
- **Leur échelle à cinq degrés**, original, savoir commun, reformulation, quasi-copie, verbatim, est une bonne grille pour un futur contrôle de `content_text` contre les extraits de la fiche. Elle recoupe Q3b de la fiche 05.
- **Leur avertissement sur la détection de texte généré par IA**, qui est la partie la plus honnête du fichier : six indicateurs listés, et l'ordre explicite de **ne jamais rendre un verdict** sur la question, taux de faux positifs trop élevé. Position à reprendre telle quelle pour Philum, où la tentation d'un badge « écrit par IA » existera.

Le reste, taux d'échantillonnage de 30 % ou 50 % des paragraphes, auto-plagiat de l'auteur, comparaison par recherche web sur des fragments de huit à douze mots, suppose un manuscrit et un auteur académique. Écarté.

### 5.2 Ponts interdisciplinaires (`deep-research/references/interdisciplinary_bridges.md`, 292 lignes)

Six patrons, dont trois utiles à Philum et un excellent.

- **Concept partagé, noms différents** : la même notion existe sous d'autres mots dans un autre champ. Directement utile à l'agent `rechercheur` quand une recherche rend peu de choses : le vocabulaire d'un domaine voisin ouvre le corpus.
- **Reformulation du problème** : le même problème réel, redéfini depuis un autre champ, produit d'autres questions et d'autres réponses. C'est le patron le plus fort pour Philum, et il rejoint la contrainte 3 : la contradiction la plus utile n'est souvent pas une étude contraire, c'est un cadrage contraire.
- **Perspectives complémentaires** : plusieurs disciplines éclairent le même phénomène par des questions différentes.

Leurs tableaux sont peuplés d'exemples d'enseignement supérieur, sans intérêt ici. C'est la forme des patrons qu'on garde, pas leur contenu. Verdict : trop mince pour un module `shared/` propre, à fondre dans le rôle `rechercheur.yaml` comme méthode d'élargissement quand une recherche rend peu.

### 5.3 Veille bibliographique (`deep-research/references/literature_monitoring_strategies.md`, 263 lignes)

Un guide de configuration d'alertes, Google Scholar, PubMed, flux RSS, serveurs de préprints, avec bonnes pratiques et limites par plateforme. Rien n'est du contexte d'agent : ce sont des instructions à un humain pour paramétrer des services tiers. Écarté comme module.

**Une seule idée en sort, et elle est bonne.** Leur intégration de la veille des rétractations tient trois gestes distincts, que Philum confond aujourd'hui en un seul : un contrôle initial à la pose de la source, un abonnement au flux pour l'avenir, et un **re-contrôle périodique des sources déjà citées**. Philum n'a que le premier (`extractors/retraction.py`). C'est exactement l'apport C de la fiche 04, la péremption datée d'une vérification, et cette lecture le confirme depuis un deuxième endroit du dépôt.

Second détail utile : leur table de raisons de rétractation gradue l'action. Une fabrication de données impose de retirer la citation ; une erreur honnête demande seulement de vérifier si l'erreur touche ce qui était cité ; un litige d'auteurs ne change rien aux résultats. Une rétractation n'est donc pas un fait binaire, et un affichage Philum qui la rendrait binaire serait faux.

---

## 6. Ce que la relecture d'ARS a fait remonter d'autre, et qui n'était pas dans les fiches 04 et 05

Quatre mécanismes manqués au premier passage, tous consignés ici pour ne pas être reperdus.

### 6.1 Le vérificateur ne doit pas être de la même famille que le générateur

`shared/cross_model_verification.md` s'ouvre sur une mesure : soixante-huit citations produites par IA, 31 % défectueuses, **et toutes avaient passé trois tours de contrôle par le même modèle**. Le motif écrit : vérificateur et générateur partagent la distribution d'entraînement, donc les angles morts. ARS en tire un protocole croisé entre familles de modèles, explicitement optionnel, avec deux honnêtetés à imiter : le taux d'erreur après vérification croisée n'a jamais été mesuré, et le procédé ne corrige ni le verrouillage de cadre ni la complaisance, communs à tous les modèles alignés.

Conséquence pour Philum : le juge de fidélité ne doit jamais être le même appel que celui qui a écrit l'annotation. Idéalement pas le même modèle. C'est une garde qui coûte presque rien.

Détail de conception à reprendre : chez eux, un fournisseur sans outil de recherche intégré voit son verdict positif **dégradé**, parce qu'aucune preuve ne l'étaye ; son verdict négatif, lui, survit. Un désaccord vaut toujours quelque chose, un accord non étayé ne vaut rien.

### 6.2 L'isolement de la vérité terrain

`shared/ground_truth_isolation_pattern.md`. Trois couches, à sens unique : entrées brutes, artefacts vérifiés, grille et corrigé. Aucun agent qui produit ne doit avoir le corrigé dans sa fenêtre. Ils appellent cela un pare-feu épistémologique, et le motif est net : un agent qui voit ce qui compte comme bonne réponse s'oriente vers les marques extérieures de la justesse plutôt que vers la qualité qu'elles signalent.

Trois règles concrètes à garder : séparer les invocations, pas seulement les consignes, car un modèle qui a vu la grille dans son historique s'oriente vers elle sans qu'on le lui demande ; le cadrage « contre-exemple » ne protège pas, les modèles s'alignent sur les exemples quelle que soit leur polarité ; et le corrigé de calibration n'est jamais versé au dépôt, il est fourni au moment de la session.

Ils écrivent aussi ce que ce n'est pas : de la convention et un lint, pas un verrou technique. Un contributeur décidé peut passer outre.

### 6.3 La posture « non mesuré », qui est leur meilleure leçon

ARS a un second jeu de cas étiquetés (`evals/heldout/claim_standing_probe/`) et il est **explicitement non mesuré**. Le fichier de tête porte en clair la mention correspondante, la suite est délibérément absente du registre d'évaluations, et il est écrit que rien de ce qui s'y trouve n'étaye une affirmation d'exactitude, d'utilité ou de couverture.

Leur exigence pour qu'une vérité terrain existe est bien plus dure que ce que décrit la fiche 04 : au moins deux experts qualifiés étiquetant en aveugle, un adjudicateur distinct qui tranche les désaccords sans voir la sortie du système, les fichiers d'experts scellés par empreinte, et des items rédigés par un modèle d'une autre famille que celui qui sera testé, pour que le sujet n'ait pas écrit son propre examen. Ils ajoutent que l'intention de construction de chaque item n'est **jamais** la vérité terrain, seulement de la comptabilité de couverture.

**Décision Philum, prise le 2026-09-10** : le jeu doré est reporté. Le juge part en production avec un état affiché « non mesuré », le verdict reste privé pour le créateur, aucune page publique ne s'en sert, et le créateur mesurera lui-même une fois la chose en production. La posture d'ARS est reprise entière : livrer sans mesure est acceptable, promettre sans mesure ne l'est pas.

### 6.4 Un vocabulaire de verdict mieux construit que celui de la fiche 04

`evals/heldout/claim_standing_probe/label_guide.md` impose un ordre : pertinence d'abord, vérifiabilité ensuite, direction en dernier, et la direction ne se pose que si les deux premières ont été franchies. Énumération fermée à six valeurs, soutient, contredit, mixte, ne traite pas, preuve insuffisante, ambigu.

Trois règles à reprendre telles quelles :

- **Une preuve absente n'est jamais « ne traite pas ».** Le silence de ce texte-ci n'est pas le silence de la littérature. Confondre les deux est la faute qui transforme une panne en verdict.
- **Aucun score numérique nulle part.** Un fichier d'étiquetage qui en contient un est rejeté. Le motif implicite est bon : un scalaire invite à la moyenne, et une moyenne de jugements catégoriels ne veut rien dire.
- **La portée de ce qui a été jugé se déclare** : abstrait, texte intégral, métadonnées seules. On ne prétend pas avoir jugé sur le texte intégral quand on n'a lu qu'un résumé.

---

## 7. L'activation des modules : tranché, aucun champ nouveau

La question posée était : faut-il un champ d'activation dans le frontmatter, pour que le créateur coche les modules qu'il veut charger ?

**Non.** Le mécanisme existe déjà, et c'est la liste `context:` de `agents/*.yaml`.

Le chat résout toujours un agent : `agent_chat.py` prend `session.agent_slug or SLUG_DEFAUT`, donc `_priming_workspace` reçoit une liste explicite de chemins, jamais `None`. La prémisse « les modules `shared/` sont tous chargés, sans interrupteur » était fausse : ils ne sont chargés que si un `agents/*.yaml` les nomme. Un créateur qui ne veut pas d'un module retire sa ligne du YAML, ou supprime le fichier ; les deux gestes marchent aujourd'hui, depuis l'éditeur de workspace déjà en place.

Ajouter un champ d'activation créerait une seconde maison pour le même fait, ce que le module qui les charge interdit dans sa propre première ligne : « Une seule maison par fait (invariant ICM) », `agent_definitions.py:1-6`. Deux mécanismes contradictoires (un module actif par frontmatter mais absent du `context:` d'un rôle) n'auraient aucune réponse évidente.

Reste le coût en jetons, qui était le vrai motif de la question. Il est traité par le plafond : `_PRIMING_MAX` passe de 40 000 à 60 000 caractères, et `test_le_seed_shared_tient_sous_le_plafond` échoue le jour où le gabarit repasse au-dessus, au lieu de laisser la troncature silencieuse retirer les derniers fichiers de l'ordre alphabétique.

---

## 8. Ce que cette note ne fait pas

- Elle ne propose aucun code, aucun prompt, aucune structure recopiée d'ARS.
- Elle n'a pas lu les gabarits `stages/` de Philum en détail, ni les sept fichiers `agents/*.yaml`, dont le contenu conditionne où chaque module doit être référencé.
- Elle ne chiffre pas l'effort : le plan d'implémentation le fera.

---

_Rédigé le 2026-09-10, après lecture des quatre skills d'ARS et du gabarit de workspace de Philum. ARS reste sous CC BY-NC 4.0 : idées reprises, code jamais._
