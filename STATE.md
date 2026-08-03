# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-07-30**

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

**Court terme** (semaines)
- **Cadrage initial du graphe Sources** — `SourceGraph.svelte` souffre du même défaut que la constellation avant PR #224 : le premier rendu tasse les nœuds en bas à droite. Le correctif est le même (recadrer à chaque tick plutôt qu'à un seuil d'alpha).
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
