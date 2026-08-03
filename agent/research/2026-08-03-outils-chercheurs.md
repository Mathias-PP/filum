# Étude — outils de recherche et valeur pour Philum

**Date** : 2026-08-03 · **Statut** : exploratoire, aucune implémentation décidée
**Périmètre** : les trois axes demandés — s'inspirer, interopérer, consommer en arrière-plan.
Toute affirmation périssable (quota, tarif, statut d'un service) a été vérifiée sur le web à
cette date. Les points non recoupés sont signalés « non vérifié ».

---

## Synthèse en une page

Le paysage se lit sur trois axes, et un même constat les traverse : **Philum n'a pas besoin
d'un corpus de citations, il a besoin d'être lisible par ceux qui en ont un.**

- **Inspiration** — la fonctionnalité vraiment différenciante n'est pas la découverte de
  papiers (Connected Papers, ResearchRabbit, Inciteful) : elle suppose un graphe de citations
  dense que Philum n'aura jamais. C'est la **qualification du lien de citation** — scite.ai
  classe chaque citation en *supporting / contrasting / mentioning* par NLP sur le plein texte.
  Philum peut obtenir le même résultat **en déclaratif**, par le créateur, sans modèle et sans
  RAM. Cela colle au positionnement (déclaration signée) et c'est agnostique au type de contenu.

- **Interopérabilité** — le meilleur levier est étonnamment petit : des **meta tags Highwire**
  et du **COinS** sur chaque page de fiche rendent Philum lisible par le connecteur Zotero et
  par Google Scholar sans écrire une ligne de connecteur. La doc Zotero le dit elle-même :
  *« the best translator is no translator at all »*. Ensuite, **CSL-JSON comme format pivot**,
  BibTeX et RIS n'étant que des sorties.

- **Arrière-plan** — **OpenAlex** est le pilier : le lookup DOI unitaire est facturé $0 dans la
  nouvelle grille (clé gratuite obligatoire depuis février 2026) et les données sont en **CC0**,
  donc réaffichables publiquement sans risque. **Unpaywall** (100 000 appels/jour, CC0) apporte
  la fonctionnalité la plus visible pour l'audience : « lire cette source légalement ».

**Si trois choses seulement** : (1) meta tags Highwire + COinS, (2) champ `stance` déclaratif
sur les sources, (3) enrichissement OpenAlex + Unpaywall en arrière-plan.

---

## Axe 1 — S'inspirer

### 1.1 Qualifier le lien de citation (inspiré de scite.ai) — **la piste la plus forte**

scite affiche la phrase citante exacte et la classe en *supporting / contrasting / mentioning*,
via un modèle NLP entraîné sur ~1,2 md d'énoncés. La classification est ancrée sur un extrait
vérifiable, ce qui la rend contestable par le lecteur.

**Transposition** : ajouter un champ `stance` sur `Source`, **déclaré par le créateur** —
`appuie` / `nuance-contredit` / `mentionne` / `contexte`. Pas de NLP, pas de plein texte, pas de
RAM. Philum dispose déjà des extraits cités et de l'annotation, qui servent d'ancrage.

Effet immédiat sur le méta-graphe : **colorer les arêtes par stance**. Une vidéo qui cite douze
sources dont trois qu'elle réfute devient lisible d'un coup d'œil. C'est aussi la seule chose
que Philum peut faire mieux que scite : scite infère, Philum fait déclarer et signer.

Corollaire quasi gratuit : un **agrégat façon « consensus meter »** (Consensus) — « sur les 7
fiches citant cette source, 5 l'appuient, 2 la contestent ».

### 1.2 Lisibilité du graphe à grande échelle (Connected Papers, ResearchRabbit)

Trois variables visuelles suffisent : taille = poids (nb de fiches citantes), couleur = récence
ou catégorie, épaisseur d'arête = nombre de sources partagées. ResearchRabbit ajoute un **mode
non-force-directed** : y = citations, x = date, ce qui supprime le chaos quand le graphe grossit.

**Transposition** : un toggle « graphe / chronologie » sur la vue existante. Meilleur rapport
valeur/effort du lot côté visualisation — c'est du d3 déjà en place.

À noter : Connected Papers plafonne délibérément autour de 40-50 nœuds affichés. Philum devrait
borner par degré/profondeur plutôt que de tout rendre.

### 1.3 Alerte rétractation (Zotero × Retraction Watch) — coût minuscule, signal énorme

Zotero signale les items rétractés et **re-vérifie les citations déjà insérées**. Couverture
limitée aux items avec DOI/PMID (~3/4 des données Retraction Watch).

**Transposition** : badge « source rétractée » sur les fiches publiques. Dégradation propre pour
les sources sans DOI — le dire explicitement plutôt que de laisser croire à une couverture totale.

### 1.4 Monitoring d'un graphe (Litmaps Monitor)

Litmaps réexécute périodiquement la recherche d'une carte et alerte par email. Transposé :
« quelqu'un vient de citer votre contenu dans une nouvelle fiche ». C'est un cron sur des données
que Philum possède déjà, et c'est un moteur de rétention **et** de viralité — chaque alerte
ramène un créateur.

### 1.5 Chemin entre deux nœuds (Inciteful Literature Connector)

« Comment cette vidéo est-elle reliée à cet article ? » — plus court chemin dans le méta-graphe.
Narratif, partageable, directement au cœur de la promesse. Recherche bidirectionnelle classique.

### 1.6 Ancrage d'extrait robuste (Hypothes.is)

Hypothes.is combine sélecteurs quote/position/range et un **fuzzy anchoring** pour retrouver un
passage même si la page a bougé. Transposé, c'est ce qui ferait passer les extraits cités de
Philum de *déclaratifs* à *vérifiables* : stocker le texte exact + un offset approximatif, et
se rattacher au snapshot Wayback si l'original a changé.

### 1.7 Sauvegarde en un clic (Zotero Connector) — fort levier, effort réel

Extension navigateur ou bookmarklet « ajouter cette page à ma fiche en cours », avec fallback
métadonnées (OpenGraph, Highwire, JSON-LD, puis Crossref par DOI). La friction de saisie tue
tous les outils de bibliographie. Fetch HTML + parsing suffit pour ~90 % des cas — **pas de
Playwright** (cf. contrainte e2-micro).

### Ce qu'il ne faut PAS copier

| À éviter | Pourquoi |
|---|---|
| Recommandation « papiers similaires » par co-citation / PageRank | Suppose un corpus dense que Philum n'aura jamais ; sur quelques centaines de fiches, c'est du bruit. Recommander plutôt par co-occurrence exacte de sources. |
| Collections / dossiers privés (Zotero, Mendeley) | Philum n'est pas une bibliothèque personnelle. Diluerait le positionnement public et doublerait la surface produit. |
| Extraction structurée par LLM sur N papiers (Elicit) | Coûteuse, pensée pour l'article IMRaD donc non agnostique, impossible sur 1 Go de RAM. |
| Classification automatique des citations par NLP (scite) | Dépend d'un plein texte que Philum n'a pas. Le déclaratif humain est ici **supérieur**, pas un pis-aller. |
| Lecteur/annotateur PDF intégré | Hors scope : Philum indexe des contenus (vidéo, podcast, blog), pas des PDF. |
| Discussion post-publication façon PubPeer | Modération, abus, anonymat — hors budget d'un solo dev pré-MVP. Direction, pas chantier. |
| Force-directed non filtré au-delà de ~150 nœuds | Illisible. Borner comme le font les concurrents. |

---

## Axe 2 — Interopérabilité

### 2.1 Format pivot : CSL-JSON

Seul format à la fois JSON natif et lu/écrit par Zotero, Pandoc, citeproc-js/py, Citation.js.
BibTeX et RIS sont des formats de **sortie** à générer depuis lui, pas des pivots (BibTeX :
encodage LaTeX, types divergents). EndNote XML, MODS et RDF sont des culs-de-sac pour un solo
pré-MVP : verbeux, peu de libs Python maintenues, aucun usage chez les vulgarisateurs.

Mapping direct : `url`→`URL`, `titre`→`title`, `doi`→`DOI`, `revue`→`container-title`,
`éditeur`→`publisher`, `date`→`issued.date-parts`, `annotation`→`note`, `archive`→`archive`.

**Deux pièges.**
1. `auteurs` est une chaîne libre chez Philum ; CSL attend `[{family, given}]`. `[{"literal": …}]`
   est supporté mais dégrade le tri dans Zotero → prévoir un parsing best-effort.
2. CSL `type` est un **vocabulaire fermé** : podcast→`broadcast`, documentaire→`motion_picture`,
   page-web→`webpage`, notes→`document`. Le couple (format, catégorie) de Philum est plus riche —
   table de correspondance explicite, et accepter la perte au retour.

**Champs propriétaires** (annotation, extraits, conflit d'intérêt, archive) : Zotero et citeproc-js
exploitent une *cheater syntax* par lignes `clé: valeur` dans le champ `note` CSL (= « Extra » de
Zotero), qui **survit à un aller-retour** Philum→Zotero→Philum. Convention à figer : préfixe
`philum-` (`philum-conflict:`, `philum-archive:`, `philum-card:`). Ne pas utiliser la syntaxe
`{:var:val}` de citeproc-js, moins bien persistée.

### 2.2 Meta tags Highwire + COinS — **le meilleur levier, de loin**

Le connecteur Zotero lit les `<meta>` Highwire (`citation_title`, `citation_author`,
`citation_doi`, `citation_journal_title`, `citation_publication_date`), Dublin Core et COinS.
Google Scholar **préfère explicitement** Highwire et exige au minimum titre + premier auteur +
année, sinon la page est traitée comme sans métadonnées.

Effort : quelques dizaines de lignes de `<svelte:head>`. Aucune dépendance, aucune auth, aucun
quota. Gain : bouton « Save to Zotero » fonctionnel **sans écrire de translator**, indexation
Scholar, lisibilité par tout crawler (y compris les crawlers de LLM — ce qui rejoint la vision
« couche de citation du web à l'ère de l'IA générative »).

**Piège** : les meta tags décrivent **une** ressource par page ; une fiche = 1 contenu + N sources.
Solution : Highwire décrit le **contenu de la fiche**, les N sources sont exposées en **COinS**
(`<span class="Z3988" title="…">`), que Zotero détecte comme items multiples. Ne pas mélanger.

### 2.3 Endpoints d'export `?format=csl-json|bibtex|ris`

Génération server-side depuis le pivot. `bibtexparser` (release janvier 2026) et `rispy`, ou
60 lignes de sérialisation manuelle — RIS et BibTeX sont triviaux à *écrire*, pénibles à *lire*.
« Exporter ma biblio » est la demande n°1 et couvre Zotero, Mendeley, EndNote, Word et LaTeX
d'un seul coup.

### 2.4 Import de fichier BibTeX / RIS / CSL-JSON

Ferme la boucle sans OAuth et supprime la friction de saisie. Piège : encodage LaTeX (`\'e`,
`{\"o}`) → passe de décodage (`pylatexenc`).

### 2.5 Export vers notes : Obsidian / Logseq / Readwise

Obsidian et Logseq sont des **fichiers Markdown** : un export « fiche → Markdown + front-matter
YAML » les couvre tous les deux, plus Quartz et Hugo. Effort quasi nul, aucune API.
Readwise : API v2 par token statique, 240 req/min, endpoint `highlights/create` — les extraits
cités de Philum y mappent parfaitement. **Notion** exige OAuth + un schéma imposé : rapport
valeur/effort nettement moins bon, à reporter.

### 2.6 ORCID — lecture seulement

La Public API (gratuite, sans adhésion) permet de lire les données publiques et d'obtenir un
ORCID iD authentifié (scope `/authenticate`). Utile pour vérifier l'identité d'un chercheur et
pré-remplir sa bibliographie. **L'écriture (`/works`) exige la Member API, payante**, et depuis
2026 les nouveaux services d'import doivent être hébergés par un membre Premium et certifiés.
⚠️ Les T&C du client public restreignent à un usage **non commercial** — à revoir si Philum se
monétise.

### 2.7 Zotero Web API v3 — après les pistes 2.2-2.4

OAuth **1.0a uniquement** (OAuth 2.0 annoncé, absent). Pas de quota publié : gérer `Backoff` /
`Retry-After`. Lecture d'une collection en `format=csljson` → mapping direct. La signature
HMAC-SHA1 en Python async est pénible : compter 2-3 jours.

### Fausses bonnes idées

| À écarter | Raison vérifiée |
|---|---|
| Frapper des DOI DataCite pour les fiches | Grille tarifaire avril 2026 : ~2 000 €/an d'adhésion consortium + ~500 €/organisation. Injustifiable pré-MVP, et un DOI sur une fiche mutable est conceptuellement douteux. |
| Héberger le Zotero translation-server sur l'e2-micro | Node + traducteurs sur 1 Go partagé avec Postgres + FastAPI : ne tiendra pas. Le déployer ailleurs (Lambda est un mode supporté) ou appeler Crossref/OpenAlex directement. |
| Miser sur JSON-LD / schema.org pour Zotero | Zotero **ignore toujours** JSON-LD et microdata en 2026. Bon pour Google et les crawlers LLM, mais ne remplace pas Highwire. |
| API Mendeley | Produit en déclin, Desktop figé. Aucune traction à espérer. |
| Paperpile | API publique **sur la roadmap, pas livrée**. Un serveur MCP est annoncé — l'interop se fera peut-être là. |
| unAPI | Élégant, supporté par Zotero, mais moribond. 20 lignes une fois les exports faits, pas avant. |

---

## Axe 3 — Services gratuits en arrière-plan

Contrainte transverse : **VM GCP e2-micro, 1 Go de RAM**. Tout enrichissement doit être un appel
HTTP à un tiers, jamais un traitement local lourd. Et Philum étant **public**, la licence des
données récupérées conditionne le droit de les réafficher.

| Service | Apport | Gratuit ? | Quota réel | Licence | Verdict |
|---|---|---|---|---|---|
| **OpenAlex** | Auteurs + ORCID, revue, éditeur, date, **nb de citations**, statut OA, ROR | Clé **obligatoire depuis fév. 2026**, gratuite | $1/jour offert ; **lookup DOI unitaire = $0** ; list/filter $0,0001 ; search $0,001 | **CC0** | ✅ Pilier n°1 |
| **Crossref REST** | Titre, auteurs, DOI, revue, dates, refs, licence | Oui, sans clé | **50 req/s par IP** ; `mailto=` → polite pool | Ouvertes | ✅ Déjà intégré |
| **Unpaywall** | Version **OA légale** d'un DOI + licence | Oui, `?email=` obligatoire | **100 000 appels/jour** | CC0 | ✅ Excellent ratio |
| **OpenCitations** | Citations entrantes/sortantes | Oui, token gratuit conseillé | Non chiffré | **CC0** | ✅ Complément |
| **Wayback SPN2 + Availability** | Archive horodatée au moment de la citation | Oui, clés S3 archive.org requises | ~15 req/min, 7 sessions concurrentes | — | ✅ mais **file async obligatoire** |
| **Europe PMC** | Biomédical : abstract, refs, MeSH | Oui, sans clé | Non vérifié | Variable | ✅ si corpus bio |
| **arXiv** | Preprints : titre, auteurs, abstract, version | Oui | **1 req/3 s**, 1 connexion | Métadonnées CC0 ; PDF non redistribuables | ✅ Simple et sûr |
| **DataCite** | Jeux de données, logiciels, thèses | Oui en lecture | Non vérifié | CC0 | ✅ Complément |
| **Wikidata** | Entités, désambiguïsation d'auteur | Oui | Non vérifié | **CC0** | ✅ (préférer à Wikipédia) |
| **Semantic Scholar** | Citations, TL;DR, refs | Sans clé possible | Sans clé : pool de 1000 req/s **partagé mondialement** (429 fréquents) ; **avec clé : 1 req/s** | Non vérifié | ⚠️ Fallback seulement |
| **NCBI E-utilities** | PubMed : PMID, abstract, MeSH | Oui | 3 req/s sans clé, 10 avec | ⚠️ **Abstracts possiblement sous copyright** | ⚠️ Prudence au réaffichage |
| **ROR** | Désambiguïser une affiliation | Oui | 2000 req/5 min ; **dès Q3 2026 sans client ID : 50 req/5 min** | CC0 | ⚠️ Enregistrer un client ID |
| **CORE** | Texte intégral de dépôts | Clé gratuite | ~1 batch / 5 unitaires par 10 s (non pleinement vérifié) | Variable | ⚠️ Optionnel |
| **DOAJ** | Revue prédatrice ou non → signal qualité | Oui | Non vérifié (doc 403) | CC0 (non vérifié) | ⚠️ Signal peu coûteux |
| **Open Library** | Livres : ISBN, couverture, éditeur | Oui | 1 req/s ; 3 avec User-Agent + email | Non explicite | ⚠️ « Backend haut trafic » interdit |
| **YouTube Data API** | Métadonnées d'une vidéo source | Oui | 10 000 unités/jour, mais seulement **100 `search.list`/jour** | Propriétaire, **règles de cache strictes** | ⚠️ Sous contrainte |
| **oEmbed / OpenGraph** | Titre, image, auteur d'une page quelconque | Oui | Dépend du site | Aucune licence explicite | ⚠️ Faits bruts uniquement |
| **Crossref Event Data** | — | — | — | — | ❌ **Éteint le 23/04/2026** |
| **Altmetric / PlumX** | Buzz social | **Non** : gratuit ≤ 6 mois, recherche non commerciale | — | Propriétaire | ❌ Hors licence pour Philum |

### Top 5 à intégrer

1. **OpenAlex** — le lookup DOI unitaire reste facturé $0, donc l'usage principal de Philum
   (enrichir une source depuis son DOI) est gratuit durablement. CC0 = zéro risque de réaffichage.
2. **Unpaywall** — 100 000 appels/jour, CC0, et c'est la fonctionnalité la plus visible pour
   l'audience : « lire cette source légalement, gratuitement ».
3. **Save Page Now + Availability** — cœur de la proposition de valeur (preuve horodatée).
   Tâche asynchrone avec backoff, **jamais dans la requête HTTP**.
4. **Crossref** — déjà en place, 50 req/s avec `mailto`, aucun quota journalier.
5. **OpenCitations** — CC0, comble les citations manquantes sans dépendre de Semantic Scholar.

### Risques juridiques de réaffichage public

- **Abstracts PubMed/NCBI** : possiblement sous copyright de l'éditeur. Lien ou extrait court,
  pas d'abstract intégral sans vérification.
- **Wikipédia (CC BY-SA)** : tout extrait réaffiché impose attribution + partage à l'identique —
  contaminant. **Wikidata (CC0) est sans risque**, le privilégier.
- **ORCID Public API** : usage non commercial seulement.
- **YouTube** : délais de rafraîchissement imposés, base persistante non synchronisée interdite.
- **OpenGraph scrapé** : rester sur titre/auteur/date (faits non protégeables), ne pas stocker
  les images.
- **GROBID auto-hébergé** : premier candidat à l'OOM sur 1 Go. Dégrader vers Crossref/OpenAlex.

---

## Séquencement proposé (indicatif, non engagé)

| # | Chantier | Effort | Axe | Pourquoi en premier |
|---|---|---|---|---|
| 1 | Meta tags Highwire + COinS | ½ j | 2 | Zéro dépendance, débloque Zotero + Scholar + crawlers LLM d'un coup |
| 2 | Champ `stance` déclaratif + arêtes colorées | 1-2 j | 1 | La vraie différenciation, et elle nourrit le graphe déjà construit |
| 3 | Enrichissement OpenAlex + Unpaywall | 2 j | 3 | Qualité des métadonnées + « lire en accès libre » |
| 4 | Pivot CSL-JSON + exports BibTeX/RIS | 1 j | 2 | Demande n°1, couvre tout l'écosystème |
| 5 | Import de fichier BibTeX/RIS | 1 j | 2 | Supprime la friction d'entrée |
| 6 | Badge rétractation (Retraction Watch via DOI) | ½ j | 1 | Signal de sérieux disproportionné au coût |
| 7 | Toggle graphe / chronologie | 1-2 j | 1 | Lisibilité à grande échelle, d3 déjà en place |
| 8 | Alertes « on vous cite » | 1 j | 1 | Rétention et viralité |

Restent en réserve, plus lourds : extension navigateur (axe 1.7), Zotero Web API OAuth 1.0a
(2.7), ancrage d'extrait fuzzy (1.6), chemin entre deux nœuds (1.5).

---

## Réserves d'honnêteté

- Les limites gratuites de Litmaps et ResearchRabbit proviennent de reviews tierces, non des
  pages de tarification officielles.
- Quotas chiffrés non trouvés pour Europe PMC, DataCite, DOAJ (doc en 403), Wikimedia.
- Termes exacts de licence de Semantic Scholar non recoupés.
- Consommation mémoire réelle du Zotero translation-server : aucun chiffre officiel publié,
  l'incompatibilité avec l'e2-micro est une déduction, pas une mesure.
