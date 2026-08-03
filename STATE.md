# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-08-03**

---

## ✅ État production vérifié (2026-07-21)

**Prod migrée Railway → GCP + Supabase** (cf. ADR-028). **VM redéployée le 2026-07-21** (commit 464ba95, PRs #179-#181 incluses). Vérifié par curl depuis la VM :
- `https://philum-api.duckdns.org/health` → `{"status":"ok","version":"0.1.0"}` (HTTPS Let's Encrypt via Caddy)
- `POST /api/v1/import/from-content-url` et `POST /api/v1/import/parse` → 401 (auth requise = endpoints déployés)
- `grobid_base_url` dans le conteneur → `https://zfhxi-grobid.hf.space` (défaut code, rien dans le `.env`)
- Fiche démo `https://filum-eight.vercel.app/@example/memoire-et-cerveau` → 200, sources + graphe OK
- Login Google → dashboard OK (redirect URI DuckDNS ajoutée au client OAuth ; l'URI Railway existe encore, à retirer)

Infra : VM GCP e2-micro us-central1 always-free (Ubuntu 24.04, swap 2 GB, Docker Compose `infra/oracle/docker-compose.micro.yml` : backend + Caddy) · Postgres Supabase free (Session pooler **5432**, jamais 6543) · DuckDNS + IP statique GCP. 10 migrations Alembic + seed démo appliqués sur base neuve (secrets régénérés — l'ancienne `master_encryption_key` Railway était un placeholder).

**Railway est décommissionnable** (laissé en secours quelques jours). Boucle retry Oracle (WSL) toujours active en arrière-plan si A1 Paris se libère.

---

## Phase courante

**Phase 3 — Features d'adoption (juillet 2026) : imports/exports, IA, extension, API.**

Livré (mergé) : exports multi-formats (JSON/CSV/BibTeX/Markdown/xlsx/**docx**), imports (BibTeX/CSL-JSON/Markdown/PDF + biblio collée via LLM + multi-liens + **URL de contenu → draft de fiche + sources citées, PR #154**), citations IA vérifiées verbatim, extraction métadonnées durcie (DOI éditeurs + **PII ScienceDirect via Crossref**), fix session 7 jours, durcissement sécurité MCP + **rate-limit 60/min par IP sur `/mcp/` (PR #147)**, extension navigateur MV3 (`apps/extension/`), page `/developers` (docs API + MCP).

✅ **VM GCP redéployée le 2026-07-21** sur `main` (464ba95) : endpoints d'import (#154, #179-#181), rate-limit `/mcp/` (#147) et extraction DOCX/HTML/PDF-GROBID effectifs en prod. Piège connu : toujours vérifier `git branch` avant un pull sur la VM. Note : les 502 juste après `docker compose up` sont normaux (alembic + seed avant uvicorn, e2-micro lente) ; et `docker compose exec backend` doit passer par `uv run python`.

Avant : Phase 2 (identité visuelle Pulsar-graph + audit) et Phase 1 (MVP complet, flow login → création → signature → attestation → publication).

---

## PRs ouvertes

**#249** — `fix/graphe-cadrage-dates`. Session 2026-08-03 (autonome) — **quatre défauts d'affichage du graphe, signalés à l'usage** :
- ⚠️ **La mise à l'échelle qui saute.** Le recadrage était appelé à *chaque tick* dès `alpha < 0.06` : le graphe s'affichait, le lecteur commençait à le parcourir, et deux à trois secondes plus tard tout changeait d'échelle. La disposition est désormais déroulée d'un coup (`simulation.tick(n)`) **avant** le premier rendu, puis la vue posée une seule fois. Mesuré sur la fiche Frontiers : **une seule transformation sur 24 s** d'observation. Coût du calcul synchrone ~200 ms, invisible puisqu'il précède l'affichage. (Cet item remplace le « Cadrage initial du graphe Sources » du court terme — le correctif envisagé, « recadrer à chaque tick », était précisément la cause.)
- **Années rognées en frise.** Le bandeau était accroché au sommet du nuage, dont la hauteur dépend de la simulation. Il vit maintenant hors du groupe zoomable, à hauteur fixe, et ne suit le cadrage qu'horizontalement ; le recadrage lui réserve sa place.
- **Date sous chaque nœud**, au même seuil de zoom que le nom d'auteur, avec la même source de vérité que la frise pour que les deux modes ne se contredisent pas. Date inconnue → « s. d. », jamais une place vide qui se confondrait avec un défaut d'affichage.
- **Nœuds fiche** 28→22 px (racine) et 22→19 px (voisines), et ils suivent désormais la densité comme les références. Au passage, redimensionnement et plein écran ne relancent plus la simulation : ils ne changent pas les liens, et réchauffer la disposition faisait dériver un graphe qu'on venait de lire.

**#248** — `feat/citations-entrantes`. Session 2026-08-03 (autonome) — **qui s'appuie sur mes fiches** :
- `Source.linked_card_id` lu à l'envers donne les citations entrantes. Trois règles de prudence : seules les fiches **publiées ET publiques** d'un **tiers** comptent (un brouillon fuiterait, une auto-citation gonflerait le compteur), et la date de la citation est celle où elle est devenue **publique**, pas celle de la ligne en base.
- ⚠️ **`citations_seen_at` est nullable et `NULL` veut dire « jamais consulté », pas « rien de nouveau »** : à la première visite tout est signalé neuf, et l'interface le dit explicitement au lieu de faire semblant. `POST /cards/citations/seen` renvoie l'état **d'avant** le marquage — sinon la visite éteindrait sous les yeux de l'utilisateur ce qu'il vient d'ouvrir.
- 🔧 **Effet de bord notable : les 31 tests adossés à la base ne pouvaient pas tourner sous Windows.** Cause réelle trouvée (et non « Windows ne peut pas ») : Windows stocke les variables d'environnement en majuscules, donc `os.environ["database_url"]` du conftest devenait `DATABASE_URL`, que `case_sensitive=True` (ADR-010) rend invisible à pydantic-settings — repli silencieux sur un Postgres local absent. `case_sensitive` relâché **dans le conftest uniquement** (le garder en prod évite qu'un `DEBUG=1` d'un outil tiers active le mode debug). Résultat : **413 passed en 16 s** contre 369 passed / 31 errors en 147 s.
- Migration `022_citations_seen`. **Mergée et déployée le 2026-08-03**, migration appliquée sur la VM (`alembic current` → `022_citations_seen (head)`), `/api/v1/cards/citations` → 401 en prod (route servie).

**#247** — `feat/ris-import`. Session 2026-08-03 (autonome) — **le sens inverse du pivot CSL** : import RIS + décodage LaTeX. **Mergée et déployée le 2026-08-03.** Validée par un aller-retour réel sur la fiche Frontiers : **148/148 références ayant une URL relues avec titres et auteurs intacts**, 0 titre vide, 0 auteur manquant. Les 4 « perdues » sur 152 n'ont **ni URL ni DOI** en base — exactement le cas que le compteur `skipped` est fait pour exposer plutôt que masquer.

**#246** — `feat/csl-pivot-ris`. Session 2026-08-03 (autonome) — **CSL-JSON devient le pivot, RIS s'ajoute** :
- BibTeX et RIS sont des formats de *sortie*, pas des pivots. Les faire descendre d'un même `app/services/csl.py` garantit qu'ils ne divergent pas : un champ corrigé l'est partout. Neuvième format d'export (`?format=ris`, EndNote/Mendeley/Zotero).
- ⚠️ **Le point dur est le nom d'auteur.** Philum stocke une chaîne libre, CSL attend `{family, given}`. L'ancien code passait tout en `[{literal}]` (tri dégradé dans Zotero) **et** cassait `"Dupont, Marie"` en deux co-auteurs. La virgule joue deux rôles : `"Dupont, J."` est *un* auteur, `"Dupont J., Martin A."` en fait deux. Le découpage s'appuie d'abord sur les initiales (seule marque typographique fiable), puis sur la parité des morceaux mono-mot. **Pari assumé et documenté** : il peut se tromper sur `"Bell, Aron"` (deux auteurs sans prénom), chaîne que rien ne distingue d'un auteur unique — **le point-virgule lève l'ambiguïté et reste la forme à préférer**.
- Deux bugs trouvés par les tests pendant l'écriture : un auteur fantôme `{family: ""}` sur une chaîne de séparateurs seuls, et une clé de citation qui donnait `cerveau` pour « Mémoire et cerveau » (un titre n'a pas de nom de famille).
- RIS : vocabulaire fermé dérivé du type CSL (défaut `ELEC`), un auteur par ligne `AU`, `ER  - ` obligatoire — sans lui les lecteurs fusionnent silencieusement toutes les références en une seule ; note multi-ligne repréfixée `N1` ligne par ligne.
- **Mergée et déployée le 2026-08-03.** Vérifié en prod sur la fiche Frontiers : **152 enregistrements RIS, 152 `ER`, 0 ligne malformée** ; CSL et BibTeX rendent `{family, given}` sans `literal` résiduel (`author = {Adleman, N. and Menon, V. and …}`). 49 tests unitaires, dont un qui vérifie que RIS et BibTeX découpent les noms à l'identique — la garantie de non-divergence du pivot.

**#245** — `feat/open-access`. Session 2026-08-03 (autonome) — **où lire gratuitement une référence payante** :
- Une bibliographie qui renvoie à un paywall arrête le lecteur net. OpenAlex agrège les routes d'accès libre (dépôt HAL, revue en libre accès, version acceptée chez l'éditeur) et expose au passage le référencement DOAJ de la revue — l'item DOAJ du chantier 3 est donc réglé sans seconde intégration.
- ⚠️ **Même règle à trois états que les rétractations.** `NULL` = jamais vérifié · `closed` = OpenAlex connaît la référence et ne trouve rien de gratuit, **information positive et datée** · `unverifiable` = pas de DOI, DOI inconnu, service muet. Afficher « payant » dans le troisième cas détournerait le lecteur d'une version libre qui existe. `in_doaj` est **nullable** pour la même raison : `False` affirmerait que la revue n'est pas référencée.
- Migration `021_source_oa` (`oa_status`, `oa_url`, `oa_license`, `in_doaj`, `oa_checked_at`). `retraction_check.py` devient `source_enrichment.py` : une seule passe, mais chaque service enveloppé **séparément** — une panne OpenAlex n'efface pas un verdict de rétractation obtenu, et deux pannes n'écrivent **rien** plutôt que de dater une vérification qui n'a pas eu lieu.
- `freeReadUrl` refuse de rendre un bouton mort (statut libre **et** URL en `http`). Le badge compact ne signale que l'accès libre : un « payant » gris sur 152 références serait du bruit ; le verdict complet et daté vit dans le panneau déplié.
- **Mergée et déployée le 2026-08-03**, migration `021` appliquée. Vérifié en prod sur la fiche Frontiers (152 sources) : **0 NULL** — 76 `closed`, 24 `gold`, 20 `green`, 13 `bronze`, 7 `hybrid`, 12 `unverifiable` (exactement les 12 sans DOI). **64 références lisibles gratuitement avec un lien réel** là où la fiche n'en signalait aucune. DOAJ : 88 `None` / 36 `False` / 28 `True`. Vérification visuelle navigateur non faite.

**#243 + #244** — `feat/graph-cap`, `feat/graph-chrono`. Session 2026-08-03 (autonome) — **le graphe reste lisible, et il sait dire le temps** :
- #243 borne le rendu aux 60 premières références (`GRAPH_SOURCE_CAP`). La troncature n'est **jamais silencieuse** : bouton `+N autres` / `Réduire à 60` dans la barre d'outils et mention permanente « N sur M références affichées » dans la légende — un graphe de 60 nœuds sur 152 ne doit pas passer pour un graphe complet.
- #244 ajoute un second axe de lecture (bascule Réseau / Chronologie). Le maillage dit qui dépend de qui, jamais l'ancienneté : « cette affirmation s'appuie sur un article de 1998 » est une information qu'il ne peut pas porter.
- ⚠️ **Une source sans date connue ne reçoit jamais une position inventée sur la frise.** Elle est garée dans une colonne hachurée à part, étiquetée « sans date (N) ». Les cas dégénérés sont tous testés : rien de daté (tout au centre, aucune graduation), une seule année (centrée et non écrasée à gauche), et les bornes réelles toujours graduées — une frise 1998-2024 par pas de 5 commencerait à 2000 et ferait croire que la source la plus ancienne date de 2000.
- Les nœuds de jonction restent libres (pas de date propre, ils tireraient leurs branches vers une année qu'ils n'ont pas) et `forceCenter` est désactivé en frise (il ramènerait une source de 1998 vers le milieu). **Mergées, frontend seul → Vercel.**

**#241 + #242** — `feat/retraction-badge`, `feat/retraction-lazy-check`. Session 2026-08-03 (autonome) — **une source dit si l'article qu'elle cite a été rétracté** :
- Une bibliographie qui cite un article rétracté le cite pour toujours : une fois le contenu publié, ni le lecteur ni l'auteur de la fiche n'ont de moyen de l'apprendre. Crossref agrège Retraction Watch et expose les avis sur `works/{doi}` (champ `updated-by`), vérifié empiriquement avant d'écrire une ligne.
- ⚠️ **Trois états, pas deux.** `NULL` = jamais vérifié · `none` = Crossref connaît le DOI et ne signale rien, **information positive et datée** · `unverifiable` = pas de DOI, DOI inconnu, service muet. Afficher « aucune rétractation » dans le troisième cas serait un mensonge par omission. Le plus grave l'emporte (corrigé en 2004 puis rétracté en 2010 → « Rétracté ») et un type Crossref inconnu retombe sur `concern` : inviter à vérifier plutôt que rassurer à tort.
- Migration `020_source_retraction` (`retraction_status`, `retraction_notice_doi`, `retraction_checked_at`). Champs **read-only** sur `SourceResponse` seulement : dérivés machine, jamais saisis.
- #242 comble le trou de #241 : la vérification ne partait qu'à la création, donc toute fiche antérieure serait restée muette indéfiniment. L'affichage d'une fiche publique planifie désormais le contrôle des sources jamais vérifiées, via `app/services/retraction_check.py` (garde anti-doublon + séquentiel sur le lot — le projet n'a pas d'ordonnanceur).
- **Mergées et déployées le 2026-08-03**, migration `020` appliquée. Vérifié en prod sur la fiche Frontiers (152 sources) : **139 `none`, 12 `unverifiable` (exactement les 12 sans DOI), 1 `corrected`** avec le DOI de l'erratum (`10.1016/j.jecp.2017.04.001`). Vérification visuelle navigateur non faite.

**#240** — `feat/source-stance`. Session 2026-08-03 (autonome) — **le rapport déclaré entre une source et le propos** :
- Une bibliographie dit sur quoi on s'appuie, jamais comment. Quatre valeurs déclaratives (`appuie`, `nuance-contredit`, `mentionne`, `contexte`), migration `019_source_stance`, arêtes colorées dans le graphe et légende conditionnelle.
- ⚠️ `NULL` (non déclaré) n'est **jamais** ramené à `mentionne` : l'un est un silence, l'autre une réponse. Invariant tenu dans le modèle, le schéma, le sélecteur (« Non déclaré » en premier), la légende et trois tests.
- Point dur : une source qui désigne une fiche Philum est absorbée en arête fiche→fiche et disparaît comme nœud — sa position déclarée se serait perdue précisément sur les liens qui structurent le graphe. Résolu par `card_edges` en dict avec règle de fusion (premier non-nul gagne). **Mergée et déployée.**

**#239** — `feat/citation-meta`. Session 2026-08-03 (autonome) — **meta tags Highwire + COinS sur les fiches publiques** :
- Google Scholar exige titre + premier auteur + année ; Zotero résout dans l'ordre translator > unAPI > COinS > DOI. Les fiches n'exposaient rien : ni indexables, ni capturables en un clic.
- COinS avec trois contextes OpenURL (`journal`, `book`, **`dc`**) — c'est le contexte Dublin Core qui rend l'export agnostique : sans lui une source YouTube devrait mentir sur son genre pour être exportable.
- **Mergée et déployée.** Vérifié dans le HTML servi par Vercel : 5 tags Highwire, 18 spans COinS pour 18 sources.

**#238** — `feat/card-content-authors`. Session 2026-08-03 (autonome) — **la fiche porte enfin les auteurs de son contenu** :
- Suite directe de #237, qui n'avait changé que la règle de préséance sans régler le manque de donnée : le nœud racine continuait d'afficher « Mathias ». ⚠️ **Une fiche n'avait aucun champ d'auteurs.** La seule source était `Source.authors` d'une source *d'une autre fiche* pointant vers elle (`_load_card_authors`) — donc rien du tout quand personne ne cite. Le repli sur le créateur était correct au regard du code et faux au regard du sens.
- Colonne `biblio_cards.content_authors` (migration `018_card_authors`, backfill depuis les sources citantes en gardant le candidat le plus long). Trois voies d'alimentation, pour couvrir toutes les situations : backfill des lignes existantes, PATCH opportuniste après import (l'extraction connaît déjà les auteurs via Crossref/JSON-LD/OG), et champ « Auteurs du contenu » dans l'éditeur de fiche (seul recours pour une fiche saisie à la main et jamais citée). `/import/url-metadata` expose désormais `authors` pour pré-remplir ce champ.
- Préséance à trois étages dans `card_graph.py` : `content_authors` déclarés → reconstitution depuis les fiches citantes → créateur. La fiche fait foi sur son propre contenu.
- Correction de rendu associée : d3 pose les étiquettes **impérativement** dans `mountGraph()`. `rootAuthors` arrivant après coup, le garde de remontage `if (neighborCards.size > 0)` laissait le nœud avec le nom de son créateur — devenu `|| rootAuthors`.
- Nouveau `CardDetailPanel.svelte` : cliquer un nœud fiche (racine, ou voisine sans source à déplier) ouvre un encadré — auteurs, date, nombre de sources, description, lien vers le contenu, créateur. Pendant du `SourceDetailPanel`, mêmes règles de placement ; les deux panneaux s'excluent.
- **Mergée et déployée le 2026-08-03.** Migration `018_card_authors` appliquée sur la VM (`Running upgrade 017_link_by_content -> 018_card_authors`), backend sain. Vérifié en prod : la fiche Frontiers renvoie `content_authors = "Kang W., Hernández S., Rahman M., Voigt K., Malvaso A."` et son nœud racine les porte dans `/graph`.
- Reste attendu : la fiche `f99a1b64` garde `authors: null` — personne ne la cite avec des auteurs et elle n'a jamais été importée. C'est le cas résiduel que la saisie manuelle est là pour couvrir, pas un défaut.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : l'encadré du nœud fiche n'a pas été observé en conditions réelles.

**#237** — `feat/root-node-identity`. Session 2026-08-03 (autonome) — **une fiche se nomme par les auteurs du contenu, pas par son créateur Philum** :
- Le nœud d'une fiche revendiquée affichait le créateur (« Mathias »), laissant croire qu'il était l'auteur de l'article ou de la vidéo décrits. ⚠️ Revendiquer une fiche, c'est répondre de sa bibliographie, **pas** signer le contenu cité : la distinction `is_seed` n'avait pas lieu d'être dans l'étiquetage. Les auteurs réels priment désormais toujours, le créateur n'étant qu'un repli ; `isSeed` disparaît de `CardLabelInput` et de ses trois sites d'appel.
- Le nom du créateur ne pouvant plus servir de « vous êtes ici », le nœud racine se distingue par un fond indigo profond `#312e81` (les voisines restent ardoise `#1e293b`) **et** un anneau plein. Redondance couleur + forme volontaire : la distinction doit tenir en vision des couleurs réduite. La vue constellation distinguait déjà sa racine en ambre, inchangée.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : les couleurs et le halo n'ont pas été observés en conditions réelles.

**#236** — `fix/expand-badge-size`. Session 2026-08-03 (autonome) — **la pastille de dépliage montre son nombre en entier** :
- Le disque de 8 px de rayon tronquait son propre libellé dès deux chiffres : sur une fiche de 306 références, la pastille censée annoncer ce que le clic révèle ne le montrait pas. Elle n'était pas non plus une cible cliquable acceptable, alors que #235 venait d'en faire la seule prise du dépliage.
- Gélule de hauteur fixe (18 px) dont la largeur suit le libellé. ⚠️ Elle part du point où se tenait le disque et s'allonge **vers l'extérieur** : la centrer ferait mordre un nombre à trois chiffres sur le nœud. La pastille « − » adopte la même hauteur, pour que les deux actions se lisent comme un seul contrôle à deux états.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : la largeur est approximée sur l'avance des chiffres, à contrôler sur un nombre à trois chiffres.

**#235** — `feat/card-node-source-panel`. Session 2026-08-02 (autonome) — **l'encadré d'une référence reste ouvrable quand elle est rendue comme fiche** :
- Depuis #233, une référence qui fait l'objet d'une fiche **est** le nœud fiche. Mais ce nœud ne gardait aucune trace de la référence absorbée et son clic servait à déplier : revue, DOI, date et annotation devenaient inatteignables. Le nœud reprend désormais la référence (`absorbedSource`).
- **Cliquer un nœud ouvre son encadré, source ou fiche.** La règle cesse de dépendre de la représentation choisie par le graphe — ce qu'un lecteur ne peut pas deviner. Déplier/replier passent aux pastilles, qui les annonçaient déjà : « +N » déplie, « − » referme, les deux avec `stopPropagation`.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée).

**#234** — `fix/seed-demo-real-urls`. Session 2026-08-02 (autonome) — **la fiche d'exemple ne cite que des pages réelles** :
- Sept des dix-huit références de `/@example/memoire-et-cerveau` pointaient vers des pages inexistantes ou tout autres : l'URL Nature rendait un article de Virginia Gewin sur le racisme dans la science, l'URL Simon & Schuster un roman d'Emma Fedor, et Lex Fridman / Wellcome / YouTube étaient en 404. Une vitrine dont les liens mentent contredit exactement la promesse du produit.
- Remplacées par TIME (Purtill), Quanta (Svoboda), CNRS Le Journal (Gros), Radiolab (« Memory and Forgetting », transcript confirmant Karim Nader), Penguin Random House (le vrai éditeur de Genova), Wikimedia Commons (planche de Cajal, 1911) et « Building Blocks of Memory in the Brain » (Kirsanov). **Chaque URL a été ouverte** et son titre, auteur et date vérifiés sur la page servie.
- ⚠️ `nytimes.com` et `lemonde.fr` bloquent toute vérification automatique : proposer une autre URL sur ces domaines aurait reproduit le problème. La Wayback Machine n'a **aucun** instantané des deux URL d'origine — alors qu'un vrai article NYT Well ou Le Monde Sciences est systématiquement archivé : elles étaient fabriquées.
- **Mergée et déployée le 2026-08-02** (aucune migration ; `_get_or_create_demo_card` supprime et recrée ses sources à chaque exécution, le redéploiement suffit). Vérifié par curl : les 18 URL en prod sont les nouvelles.

**#233** — `feat/source-card-identity`. Session 2026-08-02 (autonome) — **une source rejoint la fiche qui documente le même contenu** :
- Une référence vers un article et la fiche Philum qui documente cet article sont le même objet. Le lien ne dépendait que d'un clic manuel dans le picker ou d'une URL `/@user/slug` : sur la fiche `examining-…`, la source vers `doi.org/10.3389/fpsyg.2022.651547` flottait isolée alors que la fiche `inhibitory-control-…` existait pour ce DOI exact.
- `content_identity.py` (module pur, 20 tests) : deux références désignent le même contenu si elles partagent un DOI ou une URL normalisée. Critère **agnostique** — vaut pour un article, une vidéo, un blog ou un rapport, sans connaître le domaine. ⚠️ Le `/full` de Frontiers et le `/pdf` de Wiley sont retirés du DOI : sans ça la clé extraite d'une URL d'éditeur ne correspondait jamais au DOI nu saisi sur la source qui la cite, et le rattrapage ne faisait silencieusement rien.
- **Matérialisé à l'écriture, pas résolu à la lecture** : trois points d'application (création/batch/édition de source, publication de fiche, migration `017` de rattrapage). Résoudre dans `card_graph` aurait été auto-réparateur mais laissait `find_cards_citing`, la constellation et le sens entrant aveugles.
- La publication d'une fiche rattrape les références déjà saisies vers son contenu : une fiche existe souvent **parce que** quelqu'un a cité le contenu.
- `_load_card_authors` retient désormais la liste d'auteurs la plus complète (« Kang » d'un côté, « Kang W., Hernández S., Rahman M., Voigt K., Malvaso A. » de l'autre), la plus ancienne départageant à longueur égale.
- **Mergée et déployée le 2026-08-02** (migration `017_link_by_content` passée). Vérifié par curl sur `examining-…?depth=3` : le nœud source isolé a disparu, la 3ᵉ arête `is_card` racine → `inhibitory-control-…` est apparue, et le nœud fiche porte la liste d'auteurs complète.

**#232** — `fix/graph-fade-and-seed-banner`. Session 2026-08-02 (autonome) — **apparition du graphe et place du bandeau seed** :
- Le graphe s'allumait nœud par nœud pendant que les liens gris étaient dessinés d'emblée : des traits flottaient entre des extrémités invisibles, et l'animation durait quinze secondes sur une fiche de 300 références. Le groupe racine est désormais fondu d'un bloc en 350 ms. Fondre le parent plutôt que chaque nœud évite en plus le conflit avec le `$effect` de survol/recherche, qui écrit lui aussi l'opacité des `.node`.
- Le bandeau « fiche non revendiquée / Réclamer cette fiche » passe **sous** le graphe : c'est une réserve sur la provenance, pas la première chose qu'un visiteur doit lire.
- **Mergée le 2026-08-02** (frontend seul, déploiement Vercel automatique).

**#227** — `feat/graph-search`. Session 2026-07-31 (autonome) — **recherche dans le graphe** :
- Barre de recherche sur `SourceGraph`. Elle porte sur tout ce qui identifie une référence — titre, auteurs, revue, éditeur, DOI, URL, année, **et les libellés lisibles** du type d'auteur / format / catégorie (taper « article scientifique » fonctionne, pas seulement le code `article-scientifique`). Insensible à la casse et aux accents ; termes combinés en **ET à travers les champs**, si bien que `madigan 2023` trouve la référence alors que le nom et l'année ne sont jamais adjacents dans le texte indexé.
- **Le backend devait suivre** : le méta-graphe ne renvoyait ni `journal`, ni `publisher`, ni `doi`. Sans eux, une source de fiche voisine aurait été introuvable sur des critères qui trouvent une source de la racine — le filtre aurait donné des résultats différents selon la provenance du nœud.
- Rendu : les non-correspondants s'effacent (opacité 0.08) au lieu de disparaître, une arête reste visible dès qu'**une** extrémité correspond (elle dit à quelle fiche le résultat est rattaché), et un résultat affiche son titre quel que soit le zoom. Compteur + « Recadrer » (aussi sur Entrée).
- ⚠️ L'index de recherche est calculé **une fois par montage**, pas à chaque frappe : 300 nœuds re-normalisés à chaque caractère seraient sensibles. La logique de correspondance vit dans `$lib/utils/graph-search.ts` (fonctions pures, 11 tests).
- **Mergée et déployée le 2026-07-31** (VM sur `f19eb32`, aucune migration). Vérifié par curl sur `inhibitory-control-…?depth=3` : sur 306 nœuds source, 263 portent `doi` et `publisher`, 262 `journal`, 302 `published_at`, 303 `authors`.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : la correspondance est couverte par les tests unitaires, mais le rendu de la barre elle-même n'a pas été vu.

**#226** — `feat/graph-panel-and-bidirectional-links`. Session 2026-07-31 (autonome) — **le graphe se lit dans les deux sens** :
- **Une source de fiche voisine ouvre l'encadré, pas un onglet.** Cliquer sur un nœud issu d'une fiche dépliée déclenchait un `window.open`. Le méta-graphe ne renvoyant pas `published_at` sur ses nœuds source, le champ est ajouté au nœud backend plutôt que fabriqué côté client, sinon l'encadré serait apparu amputé de « Publié le … ». Les champs réellement absents (extraits, archive, annotation) sont déjà facultatifs dans `SourceDetailPanel`.
- **Les arêtes fiche → fiche viennent du backend.** Le frontend les déduisait des seules sources affichées : construction structurellement incapable de montrer le sens entrant, ou une chaîne A → B → C tant que B n'est pas dépliée. Toutes les fiches du voisinage sont désormais rendues en permanence, seules leurs *sources* restant masquées jusqu'au dépliage. Côté backend, le parcours des citations entrantes — jusqu'ici réservé à la constellation — est activé pour les deux vues. Le repli en cascade de `collapseCard` devient obsolète : replier une fiche ne rend plus aucune autre inatteignable.
- ⚠️ `test_source_graph_stays_outgoing_only` verrouillait l'ancien comportement ; remplacé par `test_source_graph_surfaces_incoming_citations_too`, qui revérifie au passage qu'une fiche **privée** citant la racine ne transparaît toujours pas.
- **Mergée et déployée le 2026-07-31** (VM sur `03dcd56`, aucune migration). Vérifié par curl : depuis `clarifying-…`, `examining-…` **et** `inhibitory-control-…` — les trois maillons de la chaîne — la réponse est identique (3 nœuds fiche, 2 arêtes `is_card`, 0 arête partant d'un nœud source), donc le voisinage complet est restitué quel que soit le bout par lequel on entre. 302 des 306 nœuds source portent `published_at` (les 4 restants n'en ont pas en base).
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) ; forme du graphe validée par CI Linux + curl prod.

**#225** — `feat/graph-real-authors-direct-card-links`. Session 2026-07-31 (autonome) — **lisibilité du méta-graphe** :
- **Auteurs réels sur les nœuds fiche.** Une fiche ne porte aucun champ auteur : la seule source agnostique est `Source.authors` sur la source qui la désigne (`linked_card_id`) dans la bibliographie de qui la cite. Le backend la remonte sur les nœuds `card` et expose `is_seed`. Règle d'étiquetage partagée par les deux vues (`$lib/utils/card-label.ts`) : auteurs réels quand la fiche n'est pas revendiquée, créateur sinon. Étiqueter « Mathias » une fiche seed laissait croire qu'il était l'auteur du contenu.
- **Plus de nœud source intercalé entre deux fiches.** Une source qui désigne une fiche **est** cette fiche ; la rendre en plus comme nœud affichait deux fois le même contenu en chaîne. Arête `card → card` directe, affordance de dépliage déplacée sur la fiche cible. ⚠️ **Le fix devait porter des deux côtés** : `SourceGraph.svelte` construit les sources de la fiche racine depuis `card.sources` (payload CardDetail), pas depuis l'endpoint graphe — un correctif backend seul aurait laissé la redondance visible sur la fiche racine.
- **Mergée et déployée le 2026-07-31** (VM sur `64cc2d9`, aucune migration). Vérifié par curl sur `/@mathias-pinault/clarifying-…/graph?depth=3` : le nœud fiche liée porte `authors="Kang W., Hernández S., …"` et `is_seed=true`, 1 arête `is_card` directe, **0 arête partant d'un nœud source**.
- Limite connue : la fiche racine n'a pas d'auteurs réels tant que personne ne la cite (rien ne les porte). Repli sur le créateur, comme prévu.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) ; forme du graphe validée sur fixture SQLite ad hoc + CI Linux + curl prod.

**#224** — `fix/constellation-stale-simulation`. Session 2026-07-30 (autonome) — **méta-graphe rendu réellement utilisable** :
- **PRs #222/#223 mergées, #224 en cours.** Le picker « fiche liée » écrivait une colonne que rien ne lisait : aucune méta-fiche n'était possible malgré des liens bien saisis (cf. §Méta-fiches ci-dessous). Fusion dans `linked_card_id` (migration `016`), libellés du picker clarifiés, et deux vues sur le méta-graphe — nœud dépliable dans le graphe Sources, et **constellation** (fiches seules).
- **Chaîne vérifiée en prod** : picker → `linked_card_id` → `/cards/{id}/graph` renvoie bien l'arête `is_card` et le nœud cerclé se déplie.
- **Leçon de cadrage d3** (PR #224) : un recadrage déclenché par un `setTimeout` ou par un seuil d'alpha se calcule sur des positions que la simulation déplace encore — la boîte englobante vaut alors les positions phyllotaxiques initiales de d3, d'où un `scale(2.5)` que les nœuds quittent aussitôt (canevas noir). **Recadrer à chaque tick** tant que l'utilisateur n'a pas pris la main, et lui donner un bouton « Recentrer » pour revenir. Les ticks d3 sont pilotés par `requestAnimationFrame` : ils ne tournent pas dans un onglet non rendu, donc tout cadrage adossé à une horloge `setTimeout` dérive.

Session 2026-07-30 (autonome) — **refonte du pipeline d'extraction v2, agnostique** :
- **PRs #191-#199 et #210 mergées.** Le pipeline est passé d'un empilement d'heuristiques à 7 étages explicites (cf. ADR-030) : oracle spécialisé par domaine (Wikipedia via API MediaWiki, **YouTube via `ytInitialPlayerResponse.videoDetails.shortDescription`**) → autoritatif Crossref si DOI → enrichissement (S2 + BS4 + LLM) → validation par section-detection (`app/extractors/section_detector.py`) → dédup multi-clé (`ref_dedup.py`) → scoring syntaxique (`ref_scorer.py`) → classification.
- **Vérité terrain établie sur Frontiers `10.3389/fpsyg.2022.651547`** : le site affiche 152 refs, Crossref en dépose 152, S2 en renvoie 160 (8 hallucinations ML). Philum rendait 156, puis 154, puis 153 ; **rend maintenant exactement 152**. Fixtures figées dans `tests/fixtures/frontiers_651547*` (HTML 1,6 Mo + JSON Crossref + JSON S2), test d'intégration en assertion stricte `== 152`.
- **Dédup asymétrique par couche** (PR #210, la clé du 153→152) : `same_ref` reste strict pour la dédup générale (deux éditions d'un même travail sont des références distinctes) ; mais `matches_authoritative_work`, utilisé **uniquement** en pré-filtre S2-vs-Crossref, accepte un titre long identique (≥40 car. normalisés) sans comparer les auteurs. Raison : ce n'est pas une dédup de set mais un test d'appartenance à un ensemble déjà complet, et les sources dégradent les chaînes d'auteurs de façons incompatibles (`J. Ridley` chez S2 contre `Stroop` chez Crossref, pour le même Stroop 1935). ⚠️ **Ne pas « harmoniser » ces deux fonctions** : l'asymétrie est le correctif.
- **Backfill par visite d'URL** (`_backfill_url_metadata`) : dernier filet pour les corpus non-académiques (description YouTube, blog, rapport) où ni Crossref ni le LLM bibliographique ne peuvent produire un titre. Branché sur `/import/paste` **et** `/import/from-content-url`. Le chemin paste reçoit désormais la même chaîne complète que le chemin URL (blocs + LLM par bloc + Crossref + visite d'URL).
- **Canal transcript YouTube** (PR #212) : `yt-dlp` récupère la piste de sous-titres (json3, sous-titres rédigés prioritaires sur l'ASR), le texte est découpé en morceaux de 30 k caractères puis passé au LLM. Les travaux nommés à l'oral arrivent comme **suggestions à cocher**, jamais fusionnées dans la liste de références : l'ASR massacre les noms propres. Endpoint dédié `POST /import/youtube-transcript`.
- **Méta-fiches** (PR #214, puis #222) : `parent_card_id` a été **fusionné dans `linked_card_id`** (migration `016`). La distinction n'avait aucun consommateur — le picker écrivait `parent_card_id`, que rien ne lisait, tandis que le méta-graphe et la constellation lisaient `linked_card_id`, que seule une URL Philum collée pouvait remplir : d'où 0 méta-fiche possible en prod. Un seul concept désormais, « cette source désigne cette fiche », alimenté soit par le picker soit par l'URL. `GET /cards/search` sert le picker (fiches de l'user, brouillons compris, + toutes les fiches publiées et publiques) et `assert_linked_card_allowed` revalide ce périmètre à l'écriture, sinon un id deviné permettrait de confirmer l'existence d'une fiche privée d'autrui. ⚠️ `SourceUpdate` **doit** déclarer `linked_card_id` : sans lui toute édition d'un autre champ effaçait le lien (cf. `test_link_survives_an_unrelated_edit`).
- Avant : garde-fou de cohérence de titre contre les DOIs erronés déposés par l'éditeur (cas Aron 2003 → DOI d'un papier sur les abeilles chez Oikos) ; auteurs canoniques forcés depuis Crossref ; refs sans URL autorisées (`url=""` pour livres/chapitres) ; alertes Dependabot traitées (#191).

Session 2026-07-22 :
- **PRs #185-#190 mergées** : quick-wins UI ; stepper cliquable + édition des infos d'une fiche existante (`/dashboard/new?card_id=`) ; indicateurs majoritaires sur fiche publiée (% auteur/catégorie réels, plus de compteurs fixes) ; **sources exhaustives** (résolution PII ScienceDirect → DOI + fallback Crossref `works/{doi}.reference` quand S2 élide — ScienceDirect 0→136 refs, Frontiers 160) ; **fiche parente v1** (migration `013 sources.linked_card_id`, détection serveur des URLs `/@user/slug` du frontend, badge « Fiche Philum · N sources » + bouton « Explorer la fiche », affordance lien parent par ligne dans le wizard) ; **métadonnées bibliographiques étendues** (migration `014` : journal/volume/pages/publisher/doi, autofill Crossref, date de publication dans le wizard, zone repliable pour les extras, exports **CSL-JSON Zotero** + **APA** + BibTeX enrichi).
- **VM GCP redéployée** après #186, #188, #189 et #190 (migrations 013 et 014 appliquées), health vérifié par curl.

Session 2026-07-21 :
- **PRs #179-#181 mergées** : retry Crossref 2ᵉ passe + backoff S2 429 (100 % métadonnées récupérées, 100 % gratuit) ; parcours « Nouvelle fiche » unifié (suppression `/dashboard/from-url`, extraction depuis la page sources, drop de fichier via store) ; **extraction fichiers DOCX/HTML + refs structurées PDF via GROBID** (Space HF `zfhxi/grobid`, fallback regex gracieux, ADR-023, support arXiv/CoRR).

Sessions précédentes (2026-07-19/20) :
- PRs #135-#144 mergées (imports, citations IA, session 7j, export docx, métadonnées PII, deps sécurité, durcissement MCP, extension MV3, page /developers, docs) — 2026-07-19
- **PRs #147-#154 mergées** (rate-limit MCP 60/min, fix hero moon-line-depth v1/v2/v3, fix dédup DOI/URL, endpoint `POST /import/from-content-url`, UI `/dashboard/from-url` avec preview + progression + fetch_status) — 2026-07-20
- **9 PRs Dependabot #153-#163 mergées** (vitest 4, svelte-check 4.7, svelte 5.56, sveltekit 2.70, eslint-plugin-svelte 3, svelte-eslint-parser 1.8, prettier 3.9, @types/node 26, autoprefixer 10.5) — 2026-07-20
- **PR #156 fermée** (tailwind v4 breaking, migration dédiée nécessaire)

Backend 197/197 tests, frontend check/build/lint OK.

> Mergées avant : #121-#134 (exports, imports, citations IA, graph colors, etc.), #116-#120 (infra GCP + LLM extract), #112-#115 (waitlist, seed & claim, MCP, adoption).

> _Quand cette section est vide, plus rien n'est en attente côté review humaine._

---

## URLs production

- **Frontend** : https://filum-eight.vercel.app
- **Backend** : https://philum-api.duckdns.org (GCP e2-micro + Caddy, cf. ADR-028)
- **API docs** : https://philum-api.duckdns.org/api/v1/docs
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau
- **Ancien backend Railway** : https://filum-production-07bb.up.railway.app — décommissionnable

---

## Stack effective

**Backend** : Python 3.12 · FastAPI async · SQLAlchemy 2.x async · Alembic · PostgreSQL (Supabase, Session pooler 5432) · Crypto Ed25519 + AES-GCM + HS256 (PyJWT) · Pillow (OG images) · slowapi (rate limit) · pytest (~70 tests) · Hébergé sur GCP e2-micro (Docker Compose + Caddy TLS).

**Frontend** : SvelteKit 2 · Svelte 5 (runes) · TypeScript · Tailwind · D3 v7 (graphe) · OGL (WebGL hero, lazy) · Vercel · pnpm 10 pinné · Logo Philum v1 (Pulsar-graph CB12 + Z13 palette).

**Analytics** : dbt-core sur DuckDB (job `dbt compile` en CI).

**Architecture OAuth** : Frontend → proxy SvelteKit `/api/[...path]` → Backend (cookies first-party). Backend lit `X-Filum-Public-Origin` (set par proxy) pour construire `redirect_uri` (cf. ADR-025).

---

## CI (workflows GitHub Actions)

3 workflows : `ci.yml`, `analytics.yml`, `security.yml`. Jobs (~16 total) : Lint/Test/Type-Check Backend + Frontend, Build Frontend, Analytics (dbt compile), Security Scan (Trivy), Static Analysis (Bandit), Vulnerability Check (Safety), Secrets Detection (TruffleHog), Dependency Review, CI Summary, Vercel preview.

Toutes les actions bumpées en juin 2026 (`pnpm v6`, `setup-python v6`, `checkout v6`).

---

## Variables d'environnement (production GCP)

Fichier `~/filum/infra/oracle/.env` sur la VM (modèle : `infra/oracle/.env.example`) :

```
database_url           = postgresql://postgres.<ref>:<pwd>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://philum-api.duckdns.org
google_redirect_uri    = https://philum-api.duckdns.org/api/v1/auth/google/callback
cors_origins           = ["https://filum-eight.vercel.app"]
google_client_id       = <Google OAuth Client ID>
google_client_secret   = <Google OAuth Client secret>
API_DOMAIN             = philum-api.duckdns.org   # utilisée par Caddy (TLS)
```

⚠️ **Toutes en lowercase** (ADR-010 — pydantic-settings `case_sensitive=True`), sauf `API_DOMAIN` (consommée par Caddy, pas par pydantic). ⚠️ Supabase : **Session pooler port 5432**, jamais le Transaction pooler 6543 (casse asyncpg).

Vercel : `BACKEND_URL=https://philum-api.duckdns.org` (env var serverless, jamais exposée navigateur).

---

## Bugs latents (non bloquants)

| Bug | Sévérité | Localisation |
|---|---|---|
| `impact_factor` toujours `null` | Faible | OpenAlex retiré, pas de fallback. Soit rebrancher une source, soit retirer le champ UI. |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5. |
| Wayback queue durability | Moyenne | `asyncio.create_task` perdu au restart du container backend. Cf. F5 dans `13-audit-2026-05-26-followups.md`. |
| Pas de domaine custom | Feature | Brancher `philum.app` quand 1er ambassadeur prêt. |

---

## Prochaines étapes (par ordre d'impact/coût)

> **Roadmap consolidée et priorisée** : [`.docs/19-roadmap-2026-07.md`](./.docs/19-roadmap-2026-07.md). Plan d'audit détaillé : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md). Comptes plateformes liés : [`.docs/18-linked-accounts.md`](./.docs/18-linked-accounts.md).

**Immédiat**
- ~~Redéployer la VM GCP~~ ✅ fait le 2026-07-21 (464ba95, vérifié par curl).
- ~~3 alertes Dependabot high sur main~~ ✅ fermées le 2026-07-22 (PR #191 : overrides pnpm brace-expansion 1.x/5.x + js-yaml 4.x).
- **Alerte budget 1 € sur GCP** (Billing → Budgets & alerts) si pas déjà en place — filet de sécurité, pas de plafond natif.
- **Décommissionner Railway** : supprimer le service + retirer l'ancienne redirect URI Railway du client OAuth Google.
- **Migrer Tailwind v3 → v4** (PR dédiée) : PR Dependabot #156 fermée car breaking (nouveau format config, PostCSS séparé `@tailwindcss/postcss`, syntaxes `@theme`/`@source`).

**Chantiers outils-chercheurs** (étude `agent/research/2026-08-03-outils-chercheurs.md`, dans l'ordre)
- ~~1. Meta tags Highwire + COinS~~ ✅ #239 · ~~2. Champ `stance` déclaratif~~ ✅ #240 · ~~3. Badge rétractation~~ ✅ #241+#242 · ~~4. Bornage + chronologie~~ ✅ #243+#244 · ~~5. Enrichissement OpenAlex~~ ✅ #245 · ~~6. Pivot CSL-JSON + RIS~~ ✅ #246 · ~~7. Import de fichier~~ ✅ #247 · ~~8. Alertes « on vous cite »~~ ✅ #248.
- **9. Colonnes de comparaison sans IA** — année, type, revue, accès libre, rétraction. Tous les champs existent déjà sur `Source` : le chantier est surtout frontend. ⚠️ Contrainte de l'étude §2.4 : ne pas reproduire le `N/A` indifférencié de SciSpace, où l'absence de preuve devient indiscernable de la preuve d'absence. Une case vide doit dire **pourquoi** elle l'est (pas d'information / source inaccessible / source morte).
- ~~**DOAJ**~~ ✅ — réglé par #245 sans seconde intégration : `best_oa_location.source.is_in_doaj` d'OpenAlex donne le drapeau au passage.

**Court terme** (semaines)
- **F1** — `openapi-typescript` (gen auto des types TS depuis OpenAPI, prévient drift back/front) — effort 3-4h.
- **F4** — Endpoint `POST /cards/{id}/restore` (annule un soft-delete) — effort S.
- **F2** — Tests d'intégration sur `POST /cards/{id}/publish` (couvre le path qui a coûté 4 PRs en mai).

**Moyen terme** (déclencheurs naturels)
- **F5** — Queue Wayback durable (Postgres-backed + worker) quand > 50 sources/jour.
- **Phases 2-4 du rename Philum** — convertir en issues GitHub plutôt qu'attendre un gros chantier (cf. `.docs/14-philum-rename-migration.md`).
- **F3** — Tests Postgres au lieu de SQLite quand on ajoute un index partial / colonne JSONB.

**Long terme** (conditionnel à validation produit)
- **Axe A** — Stockage cloud R2 pour contenu original (décision dépend des interviews créateurs).
- **Axe B** — Archivage multi-cible (Wayback → Archive.today → Playwright + table `archive_attempts`).
- **F8** — Multi-tenancy si pivot B2B confirmé.
- Domaine custom `philum.app` + import Zotero/BibTeX/Obsidian + plugin navigateur (après 3-5 créateurs actifs).

---

## Décisions techniques majeures

Voir [`DECISIONS.md`](./DECISIONS.md) pour le détail. Les plus structurantes :

- **ADR-013** : pnpm 10 pinné
- **ADR-014** : `python-jose` → `PyJWT` (CVE)
- **ADR-019** : signature sur le triplet `(creator_id, content_url, attested_at)`, fiches mutables
- **ADR-020** : taxonomie sources 3 axes (`format` / `category` / `author_kind`)
- **ADR-024** : sandbox tunable → port prod
- **ADR-025** : proxy SvelteKit pour OAuth cross-origin
- **ADR-026** : topologie graphe (lune + Y-fork virtuel + perspective 3D)
- **ADR-028** : hébergement GCP e2-micro always-free + Supabase (post-Railway)

---

## Commandes utiles

```bash
# Backend local
cd apps/backend
uv sync --all-extras
uv run uvicorn app.main:app --reload
uv run pytest tests/ -v
uv run alembic upgrade head
uv run ruff check app/ && uv run ruff format app/ && uv run mypy app/ --ignore-missing-imports

# Frontend local
cd apps/frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run check
pnpm run lint
pnpm run build

# CI
wsl gh run list --branch main --limit 5
wsl gh pr list
```

---

## Comment relancer une session

1. **Lire ce fichier** (snapshot court).
2. Pour le détail historique : [`CHANGELOG.md`](./CHANGELOG.md).
3. Pour les items en attente : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).
4. Pour les décisions techniques : [`DECISIONS.md`](./DECISIONS.md).
5. Pour l'agent IA autonome multi-sessions : [`agent/README.md`](./agent/README.md).
6. Vérifier l'état avec : `git log --oneline -10`, `wsl gh pr list`, `curl https://philum-api.duckdns.org/health`.
7. Choisir une tâche dans « Prochaines étapes » ci-dessus.
8. Branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite.

---

## Mettre à jour ce fichier

Quand la session apporte un changement significatif (PR mergée, phase qui change, URL prod modifiée, nouvelle ADR), **éditer la section pertinente** et bumper la date en haut. Pour les détails de la session (commits, root causes, bugs résolus), **écrire dans `CHANGELOG.md`** — pas ici.
