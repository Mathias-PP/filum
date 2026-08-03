# Étude — outils de recherche et valeur pour Philum

**Date** : 2026-08-03 · **Révision 2** (fact-check intégral + deep dive ResearchRabbit et SciSpace)
**Statut** : exploratoire, aucune implémentation décidée

**Cadrage de la révision 2.** La v1 raisonnait implicitement pour un chercheur académique. C'était
une erreur de périmètre. Philum sert **d'abord les créateurs de contenu et les vulgarisateurs, et
surtout leur audience** — la personne ordinaire qui veut vérifier une affirmation entendue dans
une vidéo, le journaliste, le doctorant, l'étudiant. Le chercheur est un utilisateur **secondaire**.
Chaque recommandation ci-dessous a été rejugée sur une seule question : *est-ce que ça aide
quelqu'un qui n'est pas expert du domaine à savoir s'il peut faire confiance à ce qu'on lui dit ?*

Toute affirmation périssable a été revérifiée en source primaire à cette date. Les corrections
apportées à la v1 sont signalées **[CORRIGÉ]**, les points non recoupés « non vérifié ».

---

## Synthèse

Trois constats, dont deux sont nouveaux.

**1. Le graphe n'est pas le produit — et le marché vient de le prouver.** ResearchRabbit a
**supprimé** son graphe force-directed non trié lors de sa refonte 2025, pour le remplacer par un
nuage de points à axes signifiants (x = année, y = citations), et n'affiche par défaut que les
**20 meilleurs nœuds**. C'est un aveu produit de la part de l'acteur le plus avancé du domaine.
Ce que les gens utilisent, ce n'est pas la carte : c'est la **boucle graine → suggestions → tri →
nouvelle graine**, rendue cumulative par des collections persistantes. Philum doit en tirer deux
conséquences directes : borner l'affichage, et prévoir un mode à axes signifiants à côté du d3
force-directed actuel.

**2. Le trou laissé béant par les deux leaders est exactement le terrain de Philum.**
ResearchRabbit n'a **aucun** contrôle qualité : ni détection de rétractation, ni signalement de
revue prédatrice, ni traçabilité, et un algorithme de recommandation propriétaire et opaque dont
les résultats varient selon qu'on saisit un titre ou un DOI. SciSpace, lui, produit des références
fabriquées (rapport vérifié de février 2026) et vend sa fiabilité comme un **palier tarifaire**
— le « Verified Report » est réservé au plan à 70 $/mois, et la nature de la vérification n'est
documentée nulle part. Leur propre benchmark donne une précision de **~0,40** chez le meilleur
outil du marché : six papiers remontés sur dix sont du bruit. Philum ne joue pas dans la même
catégorie et n'a pas à y jouer : il déclare et signe au lieu d'inférer.

**3. La fonctionnalité la plus différenciante reste la qualification déclarative du lien de
citation.** scite classe chaque citation en *supporting / contrasting / mentioning* par NLP sur
1,6 md d'énoncés — et publie sa propre distribution : **92,6 % de « mentioning », 6,5 % de
supporting, 0,8 % de contrasting**. Autrement dit, l'inférence automatique produit 93 % de bruit.
Le créateur qui déclare lui-même « cette source, je la conteste » produit 100 % de signal
intentionnel, et il le signe. C'est le seul endroit où la contrainte de Philum (pas de plein
texte, pas de RAM, pas de corpus) devient un **avantage** plutôt qu'un pis-aller.

**Si trois choses seulement** : (1) meta tags Highwire + COinS sur les pages de fiche,
(2) champ `stance` déclaratif sur les sources avec arêtes colorées, (3) enrichissement OpenAlex +
Unpaywall + badge rétractation en arrière-plan.

---

## Pour qui, exactement

| Persona | Ce qu'il fait sur Philum | Ce qui le fait partir |
|---|---|---|
| **L'audience** — la personne qui vient de voir une vidéo | Arrive par un lien, veut savoir en 30 s si l'affirmation tient. Ne cherche rien, ne s'inscrit pas. | Un graphe illisible, du jargon, une page qui demande de comprendre la bibliométrie. |
| **Le vulgarisateur / créateur** | Publie sa bibliographie, veut que ça se voie et que ça le crédibilise. | La saisie manuelle. C'est le point de mortalité n°1 de tous les outils de biblio. |
| **Le journaliste** | Vérifie une source sous contrainte de temps, veut la version accessible et la date. | Un paywall, une source morte, une absence de trace horodatée. |
| **Le doctorant** | Utilise déjà Zotero. Veut faire entrer et sortir sa biblio sans ressaisir. | Un format propriétaire, un export absent. |
| **L'étudiant** | Découvre le sujet, ne sait pas distinguer une revue sérieuse d'une prédatrice. | Aucun signal de qualité. Il ne saura jamais que le papier a été rétracté. |
| *(secondaire)* Le chercheur | Cas d'usage marginal : il a déjà ses outils. | — |

**Conséquence de tri.** Toute fonctionnalité qui n'améliore la vie que du chercheur passe en
dernier. Toute fonctionnalité visible par l'audience **sans compte et sans effort** passe devant.

---

## Axe 1 — ResearchRabbit, en détail

### 1.1 Ce qu'il faut savoir avant tout : ce n'est plus ni indépendant, ni gratuit **[CORRIGÉ]**

La v1 traitait ResearchRabbit (§1.2) et Litmaps (§1.4) comme deux concurrents distincts. **Litmaps
a racheté ResearchRabbit le 8 mai 2025**, avec une levée d'environ 1 M$ (premier closing NZ$680K,
mené par Scholarly Angels), en annonçant 1 M$ d'ARR et plus de 2 M d'utilisateurs cumulés. La
refonte d'octobre-novembre 2025 en découle directement.

Le positionnement « gratuit pour toujours » que répètent encore la plupart des blogs est
**périmé**. Grille actuelle (page `/pricing`, source primaire) :

| Plan | Prix | Graines | Notable |
|---|---|---|---|
| **Free** | 0 $ | **50** | Recherches illimitées sur 310 M+ articles, bibliothèque et collections illimitées, partage de collections |
| **ResearchRabbit+** | **10 $/mois annuel, 12,5 $ mensuel** | **300** | Contrôles de recherche avancés, projets multiples, **alertes Signals**, support prioritaire |
| **Institution** | sur devis | — | LibKey, stats d'usage |

Sources de données (convergence de plusieurs évaluations tierces, dont la LibGuide critique de
Deakin) : **OpenAlex + Semantic Scholar + PubMed**, toutes des API ouvertes — donc techniquement
accessibles à Philum aussi. **Aucune API publique ResearchRabbit n'existe** : l'intégration ne
peut être qu'un lien sortant.

### 1.2 La leçon centrale : ils ont supprimé le graphe **[NOUVEAU]**

Le « Network Graph » force-directed non trié **n'existe plus**. Il a été remplacé par un graphe à
axes sémantiques : **x = année de publication, y = nombre de citations** (échelle log optionnelle),
taille de nœud paramétrable (année, citations, nombre de références).

Trois autres décisions de la refonte, toutes dans le même sens — *réduire ce qu'on montre* :

- **Plafond d'affichage par défaut à 20 nœuds**, configurable 10/20/40, classés « par leur degré
  de connexion aux papiers-graines ». Une recherche peut matcher des centaines de milliers de
  papiers ; on en montre vingt. C'est la confirmation chiffrée de la consigne « borner le graphe »
  que la v1 n'appuyait que sur une estimation vague à propos de Connected Papers.
- **Anti-hairball par le temps, pas par le layout** : l'interface n'affiche principalement que la
  visualisation de la **dernière** étape, avec un système de **checkpoints** permettant de remonter
  les itérations et de brancher. Au lieu d'accumuler N nœuds dans un écran, on montre une tranche
  et on garde un historique navigable.
- **Les modes ne créent pas d'itération.** Basculer entre Similar / References / Citations change
  la *lentille* sur le même jeu de nœuds ; seul le bouton *Search* engendre une nouvelle étape.
  Ça évite d'exploser la profondeur d'exploration par accident.

**Transposition Philum.** (a) Borner le méta-graphe par degré/profondeur avec un plafond explicite
et un « + N autres » cliquable, jamais un rendu total. (b) Prévoir un **toggle « graphe /
chronologie »**. Attention : *ne pas copier l'axe y = citations*, Philum n'a pas de compteur de
citations crédible et l'axe serait vide ou faux. Les axes que Philum **possède réellement** sont
`date de publication`, `nombre de sources`, `part de sources archivées`. (c) Adopter la
distinction lentille/navigation : changer de filtre ne doit pas empiler une étape.

### 1.3 La boucle d'usage, et l'état vide **[NOUVEAU]**

Le parcours réel est : login → **un seul champ de recherche** → liste de résultats (titre, date,
nombre de citations) → l'utilisateur coche **1 à 3 papiers-graines** → bouton *Next* → le graphe
se construit.

**L'état vide n'est jamais un graphe vide : c'est un champ de recherche.** Le graphe n'apparaît
qu'après que l'utilisateur a fourni une intention. C'est directement applicable à la constellation
de Philum, qui souffrira longtemps d'une densité faible.

Codage visuel (documenté pour l'interface antérieure ; **non vérifié** après la refonte, mais le
principe se tient) : nœud **vert** = déjà dans ma collection, **bleu** = suggestion non encore
considérée, bleu plus foncé = plus récent. Ce simple binôme fait tout le travail cognitif
« connu vs à explorer ».

### 1.4 Trois mécanismes à voler tels quels **[NOUVEAU]**

- **Le sas avant sauvegarde.** Les articles découverts atterrissent dans « Recently Found »,
  groupés par moment d'utilisation, et **restent hors des collections** tant qu'on ne fait pas
  « save to… ». Explorer ne pollue pas. Ajouté en février 2026, complété en juillet 2026 par une
  **« Reading list »** décrite comme un « parking lot d'exploration ». Pour Philum : un brouillon
  de fiche ne doit jamais forcer un choix binaire garder/jeter au moment de l'import.

- **La dégradation gracieuse des articles pauvres en métadonnées.** Avant : les articles sans
  abstract ni citations (typiquement accès fermé ou très récents) étaient **cachés**. Depuis
  février 2026, ils sont **affichés avec un avertissement explicite que les résultats sont
  incomplets**, sauvegardables et éditables à la main, tout en restant inutilisables par
  l'algorithme. C'est exactement l'inverse du `N/A` indifférencié de SciSpace (cf. §2.4), et c'est
  le bon patron : *dire ce qu'on ne sait pas plutôt que masquer ou mentir par omission*.

- **Signals — l'alerte au risque, inférée du réseau.** Partenariat annoncé en juillet 2026 :
  Signals « cherche les papiers à haut risque d'après leur **comportement de citation et leur
  réseau de citations** », et les indicateurs apparaissent dans les collections existantes **et**
  pendant l'exploration. C'est plus fort que le badge rétractation de la v1 (§3.2) : le risque est
  inféré du comportement, pas lu dans une liste. Philum ne peut pas reproduire l'inférence
  (pas de corpus), mais peut reproduire **l'emplacement du signal** : dans le flux d'exploration,
  pas dans une page de détail que personne n'ouvre. Et c'est **payant** chez eux (RR+) — donc
  gratuit chez Philum, c'est un argument.

### 1.5 Ce que ResearchRabbit ne fait pas, et que Philum peut faire

Reproches documentés, et ils dessinent en creux le positionnement de Philum :

- **Opacité algorithmique.** Deakin : « transparence limitée sur la façon dont les recommandations
  Similar Work sont générées ; les algorithmes sont propriétaires ». Reproductibilité faible : les
  résultats varient selon qu'on entre un titre ou un DOI.
- **Aucun filtrage** de la désinformation, des articles rétractés ou des revues prédatrices.
- **Cold start** : il faut déjà connaître son domaine pour choisir de bonnes graines. Inaccessible
  à l'étudiant et à l'audience — les deux personas prioritaires de Philum.
- **Le paywall** est le grief n°1 post-2025 : bonne volonté construite sur le gratuit total,
  maintenant sous tension. Filtres avancés et alertes passés derrière RR+.

### 1.6 Ce que Philum ne PEUT PAS copier — sans complaisance

Tout ce qui suit n'existe que grâce à ~310 M de papiers et des milliards d'arêtes. Avec quelques
milliers de fiches, c'est **structurellement mort** :

1. **« Similar Work ».** Une recommandation sémantique n'a de sens qu'avec des centaines de
   candidats plausibles. Sur 2 000 fiches, ce sera du bruit ou des quasi-doublons.
2. **« Later Work » / chaînage avant.** Suppose que d'autres publications citent l'objet. Le
   méta-graphe de Philum sera à densité quasi nulle très longtemps. **Un bouton qui renvoie vide
   détruit la confiance plus vite que son absence.**
3. **Suggested Authors / réseaux de co-autorat.** Les créateurs sont majoritairement solos.
4. **Axe y = nombre de citations.** Métrique que Philum ne possède pas (cf. §1.2).
5. **Alertes sur la nouveauté de la littérature.** Suppose un flux d'entrée massif et continu.
6. **La promesse d'exploration infinie.** Chez Philum, on touche le fond en deux clics, et ça se
   voit.

---

## Axe 2 — SciSpace, en détail

### 2.1 Ce que c'est **[NOUVEAU]**

**PubGenius Inc.** (Milpitas CA + Bengaluru), fondé en 2015 sous le nom Typeset, rebaptisé SciSpace
en 2022. Financement modeste et ancien (~890 K$ à ~3,85 M$ selon la source, dernier tour
décembre 2021). Le produit s'est restructuré en 2025-2026 autour d'un « SciSpace Agent » et d'une
**Agent Gallery** (Reference Checker, DOI Finder, Citation Context Analyzer, Plagiarism Checker,
SLR Data Extraction…).

Tarifs (page `/pricing`, vérifiée en direct le 2026-08-03, promo « SCI30 » -30 % sur l'annuel
jusqu'au 3 août 2026) :

| Plan | Crédits/mois | Prix | Requêtes parallèles |
|---|---|---|---|
| Basic (gratuit) | **100** | 0 $ | 1 |
| Premium | 1 200 | **12 $** annuel / 20 $ mensuel | 4 |
| Advanced | 10 000 | **70 $** / 90 $ | 8 |
| Max | 40 000 | **160 $** / 200 $ | 16 |

Crédits **non reportables**. Ordres de grandeur donnés par eux : résumer un preprint = 24 crédits ;
trouver les 3 papiers les plus cités sur un sujet = 186 crédits. **Le gratuit à 100 crédits, c'est
environ 4 résumés par mois — une démo, pas un outil.**

Corpus revendiqué : **280-285 M de papiers**. Leur whitepaper précise que la couche de *retrieval*
interroge **Google Scholar + PubMed + arXiv**. L'origine de l'index de 280 M n'est pas documentée
publiquement — l'attribution à OpenAlex/Semantic Scholar est une inférence tierce, **non vérifiée**.

**Aucune API, aucun serveur MCP.** Vérifié indépendamment (theaiagentindex, 8 juillet 2026) et
listé chez eux comme une limitation. **Philum ne peut pas appeler SciSpace en backend.** La seule
intégration possible est un lien sortant.

### 2.2 La matrice de revue de littérature — le meilleur emprunt UX du lot **[NOUVEAU]**

C'est mécaniquement plus simple qu'il n'y paraît.

**Entrée** : une question en langue naturelle (ils recommandent explicitement de finir par `?`) ou
un corpus PDF uploadé. Trois modes exposés : **Standard / High Quality / Deep Review**.

**Sortie** : deux blocs empilés — (1) un paragraphe de synthèse avec 5 à 10 citations inline,
(2) en dessous, un **tableau : 1 ligne = 1 papier, 1 colonne = 1 attribut extrait**.

**Le différenciateur réel** : « Create a New Column » — un formulaire à deux champs, *nom de
colonne* + *instruction en langue naturelle*, exécuté ensuite sur **tous** les papiers du tableau.
À côté, des colonnes préréglées (résumé, conclusions, résultats, limitations, méthodologie).
Export CSV / BibTeX / RIS / Excel / XML, plus « Show more like selected » (relevance feedback) et
un bouton pour éjecter un papier.

**Transposition Philum — et c'est la piste la plus concrète de cette étude.** Le pattern
« nom de colonne + instruction → exécution sur N documents » est excellent, mais il faut le
retourner sur trois points :

- **Sur les abstracts, pas les PDF.** Les abstracts sont récupérables gratuitement via OpenAlex,
  Crossref et Europe PMC. Aucun plein texte requis.
- **Déclenché par le créateur, une fois, à la publication.** Une fiche à 20 sources = 20 appels sur
  ~250 mots, de l'ordre du centime. Résultat **stocké en Postgres** et servi statiquement à des
  milliers de lecteurs : coût marginal nul. Jamais déclenché par un visiteur anonyme — le produit
  cartésien N papiers × M colonnes est insoutenable à budget quasi nul.
- **Verbatim obligatoire, vérifié côté serveur.** Le modèle doit rendre un extrait de l'abstract ;
  toute cellule dont la citation n'est pas une **sous-chaîne exacte** de l'abstract source est
  rejetée et laissée vide. C'est la seule façon d'emprunter de l'IA sans trahir la proposition de
  valeur.

### 2.3 Le lecteur et le Copilot **[NOUVEAU]**

Layout split-pane persistant : PDF à gauche, Copilot à droite.

- **Sélection de texte → barre d'outils flottante** : *Highlight*, *Explain*, *Summarize*, et
  *Get related papers* — des recommandations rattachées **au passage surligné**, pas au document.
  Élégant, et conceptuellement transposable à un graphe ancré sur un extrait.
- **« Explain Math and Table »** : on trace une **zone rectangulaire** sur la page. Sélection
  *spatiale*, donc pipeline vision/OCR côté serveur — hors de portée de Philum.
- **Le ton de la réponse est un paramètre**, pas un bouton : longueur, ton, format réglables.
  C'est leur « explain like I'm five », et c'est exactement ce dont l'audience de Philum a besoin.
- 75+ langues en entrée comme en sortie — on peut converser en français sur un PDF anglais.

### 2.4 Confiance : ce qu'ils réussissent, ce qu'ils ratent **[NOUVEAU]**

**Ce qu'ils font bien** : l'ancrage est structurel, pas cosmétique — la réponse est contrainte au
PDF uploadé ou à leur index. Leur marketing attaque frontalement ChatGPT et Claude sur les
« citations hallucinées ».

**Ce qui ne va pas**, et ce sont autant de garde-fous pour Philum :

- **Références fabriquées.** Avis Capterra vérifié d'un chercheur clinicien (février 2026) :
  citations inexistantes, co-auteurs faux, détails de revue erronés — y compris des références
  générées sous le nom de l'utilisateur. Mode d'échec classique : dès que le système **génère** au
  lieu d'**extraire**, l'ancrage saute.
- **Faux positif de support** : le Q&A peut faire croire qu'un article soutient un point alors
  qu'il ne le soutient pas. C'est précisément le risque que Philum existe pour éliminer.
- **`N/A` indifférencié** : la cellule affiche `N/A` aussi bien quand l'information manque que
  quand le PDF est inaccessible. **L'absence de preuve devient indiscernable de la preuve
  d'absence.** À ne surtout pas reproduire : Philum doit distinguer « pas d'information » de
  « source inaccessible » de « source morte ».
- **Aucun score de confiance affiché.** Le seul signal est tarifaire : « Standard Report » vs
  **« Verified Report »** réservé au plan à 70 $/mois, dont la nature de vérification n'est pas
  documentée publiquement. *De la confiance vendue comme un palier de prix, pas comme une propriété
  du contenu.*
- **Non-reproductibilité** assumée : les résultats de recherche ne sont pas stables d'une
  exécution à l'autre.
- **Précision ~0,40.** Leur propre benchmark (200 requêtes, jugement par vote majoritaire de trois
  LLM, juin 2026) donne Deep Review à 26,3 papiers « hautement pertinents » par requête contre 13,0
  pour Elicit — mais une précision moyenne de **0,3995**. À lire avec méfiance (étude conduite par
  eux-mêmes), mais le chiffre à retenir n'est pas le classement : c'est que **six papiers sur dix
  sont du bruit chez le meilleur outil du marché**.

### 2.5 Le fait stratégique : ils vont dans le sens inverse de Philum **[NOUVEAU]**

Deux observations qui, mises côte à côte, définissent la relation entre les deux produits :

- Le **« Citation Booster »** transforme un papier PDF en **abstract vidéo** avec avatar IA, voix
  de synthèse, sous-titres et export MP4 « optimisé pour Instagram, TikTok, YouTube », plus des
  slides et des podcasts. C'est le trajet **chercheur → créateur**. Philum fait le trajet inverse :
  **créateur → sources**. Ce sont deux moitiés du même pont, pas deux concurrents.
- Leur **extension Chrome fonctionne déjà sur le NYT, le WSJ, Scientific American et Medium** —
  pas seulement sur Nature et Elsevier. Ils lorgnent le grand public tout en construisant un
  produit et une grille tarifaire pour chercheurs, avec un gratuit à 100 crédits qui le leur ferme.
  **C'est exactement l'espace que Philum occupe.**

### 2.6 Ce que Philum ne PEUT PAS copier

- **Bloqué par l'absence de plein texte** : chat-with-PDF, explication de passage, « Explain Math
  and Table », résumé section par section, extraction de méthodologie ou de taille d'échantillon.
  Philum a une URL, des métadonnées et un snapshot Wayback — pas les PDF sous paywall. Noter que
  **SciSpace lui-même n'y arrive pas** : il affiche `N/A` et vend le déblocage via le proxy
  institutionnel de l'utilisateur.
- **Dépense LLM prohibitive** : Deep Review (recherche récursive sur 1000+ papiers), SLR PRISMA,
  paraphraser, AI Writer. Leur propre grille montre qu'une tâche modeste coûte 24 à 217 crédits sur
  un budget mensuel de 1 200 à 12 $ : la marge est mince même pour eux.
- **Impossible sur 1 Go de RAM** : détecteur d'IA, index vectoriel sur 280 M de documents
  (des centaines de Go), OCR/vision, PDF-to-video (TTS + rendu).

---

## Axe 3 — S'inspirer des autres outils

### 3.1 Qualifier le lien de citation (scite) — **toujours la piste la plus forte** **[CORRIGÉ]**

scite affiche la phrase citante exacte et la classe en *supporting / contrasting / mentioning*.
Couverture actuelle : **1,6 md d'énoncés de citation** et 300 M d'articles en texte intégral —
et non 1,2 md comme l'indiquait la v1, chiffre qui circule encore dans des tutoriels de 2024-2025.
**scite a été racheté par Research Solutions, Inc. le 27 novembre 2023** et est commercialisé sous
« Scite by Research Solutions » : il n'existe **aucune voie d'accès gratuite ou ouverte** à ces
données pour Philum.

**L'argument décisif, nouveau** : scite publie sa propre distribution — **92,6 % mentioning,
6,5 % supporting, 0,8 % contrasting**. L'inférence NLP produit donc 93 % de non-information. La
déclaration humaine ne produit que du signal intentionnel, et elle est signable.

**Transposition** : champ `stance` sur `Source`, **déclaré par le créateur** — `appuie` /
`nuance-contredit` / `mentionne` / `contexte`. Pas de NLP, pas de plein texte, pas de RAM. Les
extraits cités et l'annotation servent d'ancrage vérifiable.

Effet immédiat sur le méta-graphe : **colorer les arêtes par stance**. Une vidéo qui cite douze
sources dont trois qu'elle réfute devient lisible d'un coup d'œil — y compris par quelqu'un qui
n'a jamais entendu parler de bibliométrie. C'est la fonctionnalité la plus directement utile à
**l'audience**, pas au créateur.

Corollaire quasi gratuit : un agrégat façon **consensus meter** (Consensus, dont le « Meter 2.0 »
détaille désormais par position la méthodologie, la récence et la revue) — « sur les 7 fiches
citant cette source, 5 l'appuient, 2 la contestent ».

### 3.2 Alerte rétractation (Zotero × Retraction Watch) — coût minuscule, signal énorme

Zotero signale les items rétractés et **re-vérifie les citations déjà insérées** dans le traitement
de texte. Couverture limitée aux items ayant un DOI ou un PMID, soit **« environ 3/4 des données
Retraction Watch »** — formulation issue du blog Zotero lui-même, chiffre confirmé.

**Transposition** : badge « source rétractée » sur les fiches publiques, **gratuit et visible sans
compte**. C'est le signal de qualité que ni ResearchRabbit ni SciSpace n'affichent, et c'est
précisément ce dont l'étudiant et l'audience ont besoin. Dégradation propre pour les sources sans
DOI : le dire explicitement plutôt que de laisser croire à une couverture totale (cf. le patron
ResearchRabbit §1.4, pas le `N/A` de SciSpace §2.4).

### 3.3 Monitoring (Litmaps Monitor) **[CORRIGÉ]**

Litmaps réexécute périodiquement la recherche d'une carte et alerte par email. Chiffres réels,
que la v1 n'avait pas :

- **Gratuit** : alertes **mensuelles**, 2 Litmaps, 100 articles par map, recherche plafonnée à
  20 entrées.
- **Pro** (~10 $/mois en annuel éducation) : alertes **hebdomadaires** ou temps réel, recherches
  automatisées illimitées.

Transposé : « quelqu'un vient de citer votre contenu dans une nouvelle fiche ». C'est un cron sur
des données que Philum possède déjà, et c'est un moteur de rétention **et** de viralité — chaque
alerte ramène un créateur. Et c'est payant chez le concurrent.

### 3.4 Chemin entre deux nœuds (Inciteful Literature Connector)

« Comment cette vidéo est-elle reliée à cet article ? » — plus court chemin dans le méta-graphe.
Narratif, partageable, compréhensible sans expertise. Recherche bidirectionnelle classique.

### 3.5 Ancrage d'extrait robuste (Hypothes.is) — vérifié intégralement

Les trois sélecteurs sont confirmés : **RangeSelector** (XPath + offsets), **TextPositionSelector**
(offsets caractères), **TextQuoteSelector** (texte exact + préfixe + suffixe). Le **fuzzy
anchoring** est un concept officiel documenté, conçu pour survivre aux changements de structure
*et* de contenu. Le compromis est explicite dans leur doc — position = rapide et fragile, quote =
lent et robuste — et la stratégie recommandée est de **stocker plusieurs sélecteurs pour la même
cible**.

Transposé, c'est ce qui ferait passer les extraits cités de Philum de *déclaratifs* à
*vérifiables* : stocker le texte exact + un offset approximatif, et se rattacher au snapshot
Wayback si l'original a bougé. C'est la brique qui rend le clic « voir la phrase exacte » possible,
et donc la promesse tenable pour l'audience.

### 3.6 Sauvegarde en un clic (Zotero Connector) — fort levier, effort réel

Extension navigateur ou bookmarklet « ajouter cette page à ma fiche en cours », avec fallback
métadonnées (OpenGraph, Highwire, JSON-LD, puis Crossref par DOI). **La friction de saisie tue tous
les outils de bibliographie** — c'est le point de mortalité n°1 pour le persona créateur. Fetch
HTML + parsing suffit pour ~90 % des cas ; **pas de Playwright** (contrainte e2-micro).

À noter que SciSpace a fait le même pari, et que son extension couvre déjà la presse généraliste
(§2.5).

### 3.7 Ce qu'il ne faut PAS copier

| À éviter | Pourquoi |
|---|---|
| Recommandation « contenus similaires » par co-citation / PageRank | Suppose un corpus dense que Philum n'aura jamais. Recommander plutôt par **co-occurrence exacte de sources** — signal réel, calculable, explicable. |
| Chaînage avant (« qui cite cette fiche ») exposé comme un bouton | Renverra vide pendant des mois. Un bouton vide coûte plus cher que son absence. |
| Collections / dossiers privés (Zotero, Mendeley) | Philum n'est pas une bibliothèque personnelle. Diluerait le positionnement public. |
| Synthèse rédigée multi-documents par LLM (Deep Review, Elicit) | C'est exactement là où SciSpace se fait démolir (§2.4). Coûteuse, non reproductible, et elle détruit la proposition de valeur. |
| Classification automatique des citations par NLP (scite) | Dépend d'un plein texte absent, et produit 93 % de « mentioning ». Le déclaratif humain est **supérieur**, pas un pis-aller. |
| Lecteur / annotateur PDF intégré | Philum indexe des vidéos, podcasts, blogs — pas des PDF. |
| Discussion post-publication façon PubPeer | Modération, abus, anonymat. Direction, pas chantier. |
| Force-directed non filtré au-delà de ~150 nœuds | Le leader du secteur l'a **supprimé** (§1.2). |

---

## Axe 4 — Interopérabilité

### 4.1 Format pivot : CSL-JSON

Seul format à la fois JSON natif et lu/écrit par Zotero, Pandoc, citeproc-js/py, Citation.js.
BibTeX et RIS sont des formats de **sortie**, pas des pivots. EndNote XML, MODS et RDF sont des
culs-de-sac pour un solo pré-MVP.

Mapping direct : `url`→`URL`, `titre`→`title`, `doi`→`DOI`, `revue`→`container-title`,
`éditeur`→`publisher`, `date`→`issued.date-parts`, `annotation`→`note`, `archive`→`archive`.

**Deux pièges.** (1) `auteurs` est une chaîne libre chez Philum ; CSL attend `[{family, given}]`.
`[{"literal": …}]` est supporté mais dégrade le tri dans Zotero → parsing best-effort. (2) CSL
`type` est un **vocabulaire fermé** : podcast→`broadcast`, documentaire→`motion_picture`,
page-web→`webpage`, notes→`document`. Table de correspondance explicite, et accepter la perte
au retour.

**Champs propriétaires — précision importante [CORRIGÉ].** La v1 affirmait que Zotero et
citeproc-js « exploitent » une *cheater syntax* `clé: valeur` dans le champ `note` / « Extra ».
C'est inexact : seules les **variables CSL valides** y sont interprétées. Les préfixes
`philum-conflict:`, `philum-archive:`, `philum-card:` ne seront **jamais** reconnus comme des
variables — ils resteront du texte libre. C'est précisément ce qu'on veut (ils **survivent intacts
à un aller-retour** Philum→Zotero→Philum), mais il faut le formuler comme tel : *préservés, pas
interprétés*. Le choix d'écarter la syntaxe `{:var:val}` de citeproc-js reste bon.

### 4.2 Meta tags Highwire + COinS — **le meilleur levier, de loin** (vérifié intégralement)

La doc Zotero « Exposing Your Metadata » liste : **Embedded Metadata, tags Highwire/Google Scholar,
Dublin Core, COinS, unAPI** (+ MODS/MARC/RIS/BibTeX via unAPI). **Aucune mention de JSON-LD ni de
microdata.** La citation est exacte : *« the best translator is no translator at all »*.

**Hiérarchie de résolution du connecteur**, utile pour le piège ci-dessous :
`translator spécifique > unAPI > COinS > DOI > Embedded Metadata`.

Google Scholar, guidelines officielles : *« supports Highwire Press tags…, BE Press tags…, and
PRISM tags…. Use Dublin Core tags as a last resort »*, avec un minimum de **trois champs** — titre,
nom complet du premier auteur, année de publication.

Effort : quelques dizaines de lignes de `<svelte:head>`. Aucune dépendance, aucune auth, aucun
quota. Gain : bouton « Save to Zotero » fonctionnel **sans écrire de translator**, indexation
Scholar, lisibilité par tout crawler — y compris les crawlers de LLM, ce qui rejoint directement
la vision « couche de citation du web à l'ère de l'IA générative ».

**Piège** : les meta tags décrivent **une** ressource par page ; une fiche = 1 contenu + N sources.
Solution : Highwire décrit le **contenu de la fiche**, les N sources sont exposées en **COinS**
(`<span class="Z3988" title="…">`), que Zotero détecte comme items multiples. Ne pas mélanger.

### 4.3 Endpoints d'export `?format=csl-json|bibtex|ris`

Génération server-side depuis le pivot. `bibtexparser` et `rispy`, ou 60 lignes de sérialisation
manuelle — RIS et BibTeX sont triviaux à *écrire*, pénibles à *lire*. « Exporter ma biblio » est
la demande n°1 du persona doctorant et couvre Zotero, Mendeley, EndNote, Word et LaTeX d'un coup.

À noter : chez SciSpace, l'export Zotero est **payant**. Gratuit chez Philum, c'est un argument.

### 4.4 Import de fichier BibTeX / RIS / CSL-JSON

Ferme la boucle sans OAuth et supprime la friction d'entrée. Piège : encodage LaTeX (`\'e`,
`{\"o}`) → passe de décodage (`pylatexenc`).

### 4.5 Export vers notes : Obsidian / Logseq / Readwise **[CORRIGÉ]**

Obsidian et Logseq sont des **fichiers Markdown** : un export « fiche → Markdown + front-matter
YAML » les couvre tous les deux, plus Quartz et Hugo. Effort quasi nul, aucune API.

Readwise : token statique `Authorization: Token XXX`, endpoint `highlights/create`,
**240 req/min** — mais **les endpoints LIST sont plafonnés à 20 req/min**, ce que la v1 omettait.
Si l'export lit avant d'écrire, c'est cette limite-là qui mordra. Header `Retry-After` sur 429.

**Notion** exige OAuth + un schéma imposé : rapport valeur/effort nettement moins bon, à reporter.

### 4.6 ORCID — lecture seulement

Public API gratuite (lecture des données publiques, scope `/authenticate`). L'écriture `/works`
exige la **Member API payante**, et depuis 2026 les nouveaux services d'import doivent être
hébergés par un membre **Premium** et certifiés via le programme **ORCID Certified Service
Provider**. ⚠️ Les T&C de l'API publique restreignent explicitement à un usage **non commercial** —
c'est un vrai risque produit si Philum se monétise, pas une note de bas de page.

Utilité réelle pour Philum : marginale, puisque le persona chercheur est secondaire. À reléguer.

### 4.7 Zotero Web API v3 — après 4.2-4.4

Doc officielle révisée le 9 mai 2026 : OAuth **1.0a uniquement**, OAuth 2.0 mentionné comme
évolution future non implémentée. Pas de quota publié : gérer `Backoff` / `Retry-After`. Lecture
d'une collection en `format=csljson` → mapping direct. La signature HMAC-SHA1 en Python async est
pénible : compter 2-3 jours (estimation, non vérifiée).

### 4.8 Fausses bonnes idées

| À écarter | Raison vérifiée |
|---|---|
| Frapper des DOI DataCite pour les fiches **[CORRIGÉ]** | Grille `datacite.org/fees` : adhésion **à partir de 2 000 €/an** + frais d'infrastructure **200-700 €**. La refonte d'avril 2026 a basculé la tarification sur la **géographie et le chiffre d'affaires** (1 000 à 10 000 € pour une organisation à but lucratif) et a **supprimé** le « ~500 €/organisation » qu'annonçait la v1 — une organisation membre d'un consortium est aujourd'hui à **0 € d'adhésion**. Verdict inchangé : injustifiable pré-MVP, et un DOI sur une fiche mutable est conceptuellement douteux. |
| Héberger le Zotero translation-server sur l'e2-micro | Node + traducteurs sur 1 Go partagé avec Postgres + FastAPI : ne tiendra pas. Le déployer ailleurs ou appeler Crossref/OpenAlex directement. |
| Miser sur JSON-LD / schema.org pour Zotero | **Ignoré à ce jour, sans évolution annoncée** (dernières discussions forum en 2023, confirmé par des tests de novembre 2025). Bon pour Google et les crawlers LLM, mais ne remplace pas Highwire. |
| API Mendeley | Produit en déclin, Desktop figé. |
| API SciSpace ou ResearchRabbit | **Aucune des deux n'existe.** L'intégration ne peut être qu'un lien sortant (§2.1, §5). |
| Paperpile | API REST publique « en construction », non livrée. Un serveur MCP est annoncé sans calendrier. |
| unAPI | Élégant et supporté par Zotero, mais moribond. 20 lignes une fois les exports faits, pas avant. |

---

## Axe 5 — Services gratuits en arrière-plan

Contrainte transverse : **VM GCP e2-micro, 1 Go de RAM**. Tout enrichissement doit être un appel
HTTP à un tiers, jamais un traitement local lourd. Et Philum étant **public**, la licence des
données conditionne le droit de les réafficher.

| Service | Apport | Quota réel | Licence | Verdict |
|---|---|---|---|---|
| **OpenAlex** | Auteurs + ORCID, revue, éditeur, date, nb de citations, statut OA, ROR | Clé gratuite **obligatoire depuis le 13/02/2026** ; $1/jour offert ; **lookup DOI unitaire = $0 et illimité** ; list/filter $0,0001 ; search $0,001 ; **PDF/XML via Content API $0,01** | **CC0** (sauf snapshot format MAG, ODC-BY) | ✅ Pilier n°1 |
| **Crossref REST** **[CORRIGÉ]** | Titre, auteurs, DOI, revue, dates, refs, licence | **Depuis le 01/12/2025** : public **5 req/s** unitaire / **1 req/s** liste, concurrence 1. Polite (`mailto=`) : **10 / 3**, concurrence 3. Lire `x-rate-limit-limit`, `x-rate-limit-interval`, `x-concurrency-limit` | Ouvertes | ✅ mais **5× moins que ce qu'annonçait la v1** |
| **Unpaywall** | Version **OA légale** d'un DOI + licence | 100 000 appels/jour, `?email=` obligatoire | CC0 | ✅ Excellent ratio |
| **OpenCitations** | Citations entrantes/sortantes | Non chiffré ; token gratuit conseillé | **CC0, réutilisable y compris commercialement** | ✅ Complément |
| **Wayback SPN2 + Availability** | Archive horodatée au moment de la citation | ~15 req/min (au-delà : blocage IP 5 min) ; clés S3 sur `archive.org/account/s3.php` | — | ✅ mais **file async obligatoire** |
| **Europe PMC** | Biomédical : abstract, refs, MeSH | Non vérifié | Variable | ✅ si corpus bio ; **utile pour les abstracts** (cf. §2.2) |
| **arXiv** | Preprints | **1 req/3 s, une seule connexion** ; débit supérieur négociable | Métadonnées CC0 ; PDF non redistribuables | ✅ Simple et sûr |
| **DataCite** (lecture) | Jeux de données, logiciels, thèses | Non vérifié | CC0 | ✅ Complément |
| **Wikidata** | Entités, désambiguïsation d'auteur | Non vérifié | **CC0** | ✅ (préférer à Wikipédia) |
| **YouTube Data API** **[CORRIGÉ]** | Métadonnées d'une vidéo source | 10 000 unités/jour. `search.list` = 100 unités → 100 recherches/jour, **mais `videos.list` = 1 unité → 10 000 lookups/jour**. Le cas d'usage réel de Philum (on a déjà l'ID) est donc **beaucoup moins contraint** que ne le disait la v1 | Propriétaire, règles de cache strictes | ✅ moins contraint que prévu |
| **Semantic Scholar** | Citations, TL;DR, refs | Sans clé : pool de 1000 req/s **partagé mondialement** (donc saturé). Avec clé : **1 req/s dédié, limite « introductive » relevable sur demande** | **Non vérifiée** — ne pas affirmer CC0 | ⚠️ Fallback |
| **NCBI E-utilities** | PubMed : PMID, abstract, MeSH | 3 req/s sans clé, 10 avec, au-delà sur demande | ⚠️ **Abstracts possiblement sous copyright** | ⚠️ Prudence au réaffichage |
| **ROR** | Désambiguïser une affiliation | 2000 req/5 min ; **dès Q3 2026, sans client ID : 50 req/5 min**. Enregistrement gratuit sur `ror.org/api-client-id` | CC0 | ⚠️ Enregistrer un client ID |
| **CORE** | Texte intégral de dépôts | Non pleinement vérifié | Variable | ⚠️ Optionnel |
| **DOAJ** | Revue prédatrice ou non → signal qualité | Non vérifié (doc 403) | Non vérifié | ⚠️ Signal peu coûteux, **très utile au persona étudiant** |
| **Open Library** | Livres : ISBN, couverture, éditeur | 1 req/s ; **3 avec User-Agent identifiant + email**. UA absent ou générique = blocage possible | Non explicite | ⚠️ « Backend haut trafic » interdit |
| **oEmbed / OpenGraph** | Titre, image, auteur d'une page quelconque | Dépend du site | Aucune licence explicite | ⚠️ Faits bruts uniquement |
| **Crossref Event Data** **[PRÉCISÉ]** | — | Éteint le **23/04/2026**. Données historiques disponibles **sur demande** au support, et Crossref a livré un **endpoint de remplacement dédié aux citations de données** | — | ❌ mais une alternative existe |
| **Altmetric / PlumX** **[CORRIGÉ]** | Buzz social | Accès gratuit à la Details Page API via le programme **SRAD**, réservé à la recherche scientométrique **non commerciale**. La mention « ≤ 6 mois » de la v1 **n'est attestée nulle part** et est retirée | Propriétaire | ❌ Hors licence pour Philum |

### Top 5 à intégrer **[NUANCÉ]**

1. **OpenAlex** — le lookup DOI unitaire est à $0 et illimité, donc l'usage principal de Philum
   est gratuit **aujourd'hui**. La v1 écrivait « durablement » : c'est une extrapolation que rien
   ne garantit — OpenAlex est justement passé à un modèle payant en février 2026. CC0 = zéro
   risque de réaffichage.
2. **Unpaywall** — 100 000 appels/jour, CC0, et c'est la fonctionnalité la plus visible pour
   l'audience : « lire cette source légalement, gratuitement ». ⚠️ **Risque de concentration** :
   Unpaywall tourne depuis 2025 sur la base de code d'OpenAlex. Les points 1 et 2 sont donc la
   **même infrastructure**, chez le même opérateur (OurResearch).
3. **Save Page Now + Availability** — cœur de la proposition de valeur. Tâche asynchrone avec
   backoff, **jamais dans la requête HTTP**.
4. **Crossref** — déjà en place. Mais avec 3 req/s en liste sur le pool polite au lieu des 50
   supposés, un backfill sur quelques milliers de sources devient un job de **plusieurs heures**.
   Toute logique de fallback Crossref doit être asynchrone dès le départ.
5. **Retraction Watch via DOI** — remplace OpenCitations dans le top 5 après le recadrage vers
   l'audience : un badge « rétracté » vaut plus, pour un étudiant, que dix arêtes de citation
   supplémentaires.

### Risques juridiques de réaffichage public

- **Abstracts PubMed/NCBI** : possiblement sous copyright de l'éditeur. Lien ou extrait court.
- **Wikipédia (CC BY-SA)** : contaminant (attribution + partage à l'identique). **Wikidata (CC0)
  est sans risque**, le privilégier.
- **ORCID Public API** : usage non commercial seulement.
- **YouTube** : délais de rafraîchissement imposés, base persistante non synchronisée interdite.
- **OpenGraph scrapé** : rester sur titre/auteur/date (faits non protégeables), ne pas stocker
  les images.
- **GROBID auto-hébergé** : premier candidat à l'OOM sur 1 Go. Dégrader vers Crossref/OpenAlex.

---

## Lier, copier, ou ignorer — décision par outil

| Outil | Décision | Raison |
|---|---|---|
| **ResearchRabbit / Litmaps** | **Ignorer comme partenaire, copier trois patrons UX** | Pas d'API. Copier : le plafond d'affichage, le sas « Recently Found », l'état vide = champ de recherche, la dégradation gracieuse des items pauvres. Ne pas copier : Similar Work, chaînage avant, axe y = citations. |
| **SciSpace** | **Lien sortant + copier un patron** | Pas d'API ni de MCP. Un bouton « comprendre ce papier » vers leur lecteur est la seule intégration possible. Copier : la colonne custom en langue naturelle, mais sur abstracts, pré-calculée, avec verbatim vérifié serveur. |
| **Zotero** | **Interopérer, en priorité** | Highwire + COinS (§4.2) puis exports (§4.3) et imports (§4.4). C'est le persona doctorant, et c'est bon marché. |
| **scite / Consensus** | **S'inspirer, ne pas intégrer** | Propriétaires, pas d'accès gratuit. Le mécanisme (stance, consensus meter) est reproductible en déclaratif, et en mieux. |
| **Retraction Watch** | **Consommer** | Gratuit via Crossref, couverture ~3/4 sur DOI/PMID. Signal disproportionné au coût. |
| **Hypothes.is** | **Copier l'architecture d'ancrage** | Spécification publique et documentée. Rend les extraits vérifiables au lieu de déclaratifs. |
| **Connected Papers** **[CORRIGÉ]** | Ignorer | La v1 écrivait « plafonne délibérément à 40-50 nœuds » : **aucune page officielle ne publie de plafond**, et « délibérément » suppose une intention non documentée. Ce qui est attesté : ils analysent ~50 000 papiers et en retiennent « quelques dizaines » (~25 à 40 observés par des guides tiers). Free tier : 5 graphes/mois. La recommandation de borner reste bonne, elle s'appuie désormais sur ResearchRabbit (§1.2), qui publie son chiffre. |

---

## Séquencement proposé (indicatif, non engagé)

Réordonné par utilité pour **l'audience et le créateur**, pas pour le chercheur.

| # | Chantier | Effort | Pour qui | Pourquoi à ce rang |
|---|---|---|---|---|
| 1 | Meta tags Highwire + COinS | ½ j | Doctorant, crawlers LLM | Zéro dépendance, débloque Zotero + Scholar + crawlers d'un coup |
| 2 | Champ `stance` déclaratif + arêtes colorées | 1-2 j | **Audience** | La vraie différenciation, lisible sans expertise, et elle nourrit le graphe existant |
| 3 | Badge rétractation + DOAJ | ½ j | **Étudiant, audience** | Le trou déclaré des deux leaders. Coût minuscule, signal énorme |
| 4 | Bornage du graphe + toggle chronologie | 1-2 j | **Audience** | Le marché vient de prouver que c'est nécessaire (§1.2). d3 déjà en place |
| 5 | Enrichissement OpenAlex + Unpaywall | 2 j | Journaliste, audience | Qualité des métadonnées + « lire en accès libre », la fonction la plus visible |
| 6 | Pivot CSL-JSON + exports BibTeX/RIS | 1 j | Doctorant | Demande n°1, couvre tout l'écosystème, et c'est payant chez SciSpace |
| 7 | Import de fichier BibTeX/RIS | 1 j | Créateur | Supprime la friction d'entrée — le point de mortalité n°1 |
| 8 | Alertes « on vous cite » | 1 j | Créateur | Rétention et viralité. Mensuel gratuit chez Litmaps, hebdo à 10 $/mois |
| 9 | Colonnes de comparaison sans IA | 1-2 j | Journaliste, doctorant | Année, type, revue, OA, rétracté — la matrice SciSpace sans un seul appel LLM |

Restent en réserve, plus lourds : extension navigateur (§3.6), colonnes custom LLM sur abstracts
(§2.2), ancrage d'extrait fuzzy (§3.5), chemin entre deux nœuds (§3.4), Zotero Web API OAuth 1.0a
(§4.7).

---

## Réserves d'honnêteté

**Levées depuis la v1** : les limites de Litmaps et de ResearchRabbit sont désormais chiffrées en
source primaire (§1.1, §3.3). Les claims OpenAlex et Semantic Scholar, dont je doutais, sont
**exacts au chiffre près**.

**Corrigées** : Crossref (5× moins que prévu), DataCite (~500 €/organisation n'existe plus), scite
(1,2 → 1,6 md), Litmaps (alertes mensuelles et non hebdomadaires en gratuit), YouTube (en notre
faveur), Readwise (limite LIST omise), cheater syntax CSL (préservée, pas interprétée), Connected
Papers (plafond non attesté).

**Maintenues** :

- Termes exacts de licence de Semantic Scholar **non recoupés** — ne pas affirmer CC0.
- Quotas chiffrés non trouvés pour Europe PMC, DataCite en lecture, DOAJ (doc en 403), Wikimedia.
- Consommation mémoire réelle du Zotero translation-server : déduction, pas mesure.
- **« 7 sessions concurrentes » SPN2 : non attesté** — la doc officielle est un Google Doc non
  indexable et les implémentations tierces se contredisent (6/min authentifié vs 3/min anonyme
  chez `savepagenow`, 20 jobs parallèles ailleurs). Le chiffre est retiré du tableau ; la
  conclusion (file asynchrone obligatoire) tient sans lui.
- **Altmetric « ≤ 6 mois » : non attesté**, retiré. Le cadre vérifié est le programme SRAD.
- **SciSpace : traçabilité au niveau cellule non attestée.** Ils revendiquent des « insights
  adossés à des citations de sections spécifiques », mais aucune source primaire ne montre qu'une
  cellule du tableau porte un numéro de page et un verbatim cliquable. Le modèle documenté est
  cellule → lien vers le papier → Chat with PDF. À considérer comme de la traçabilité **au niveau
  document**, voire probablement faux au sens strict.
- **SciSpace : origine de l'index de 280 M non documentée.** L'attribution à OpenAlex/Semantic
  Scholar est une inférence tierce.
- **SciSpace : chiffres d'usage incohérents entre leurs propres pages** — « 1 million+
  researchers » sur `/pricing` vs « 10 MILLION+ USERS » sur `/search` vs 6 M en novembre 2025.
  À traiter comme du marketing.
- **ResearchRabbit : codage couleur vert/bleu** documenté pour l'interface antérieure ; non
  confirmé après la refonte 2025.
