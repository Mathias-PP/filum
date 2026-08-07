# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-08-07**

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

## Session 2026-08-07 (fin) — accessibilite mesuree et cloture des lots B a F

**Parcours visiteur (#78, clos).** Mesure sur le deploiement de prod, pas sur la
PR — sonde iframe 375px dans Chrome, viewport reel 362px, sur
`/@mathias-pinault/ca-sert-a-quoi-de-dormir`. Chrome refuse de descendre sous
~547px de large, d'ou l'iframe.

| mesure | avant | apres |
|---|---|---|
| scroll horizontal | 423px pour 362 de large | aucun (362/362) |
| cibles tactiles sous 24x24 | 8 | 1 |
| `--success` sur son fond de badge | 2,98:1 | 4,54:1 |
| `--warning` sur son fond de badge | 3,24:1 | 4,53:1 |

Le debordement venait du bouton « Partager » : les enfants de la barre d'action
portent `shrink-0`, donc sous ~380px il sortait du conteneur (PR #301,
`flex-wrap`). La cible restante, « En savoir plus », est un lien au fil d'une
phrase : le critere WCAG 2.5.8 l'exempte explicitement (clause « Inline »), et
l'agrandir casserait l'interligne du paragraphe. PRs #301 et #302.

**Signale, pas corrige — arbitrage design en attente.** `--text-placeholder` a
2,17:1 : le monter a 4,5:1 le rendrait indiscernable de `--text-tertiary`
(4,61:1), ce qui contredit son intention documentee. Les bordures de champ
(`--border-strong`) a 1,59:1 contre les 3:1 du critere 1.4.11, en zone
authentifiee seulement. 22 textes sous 12px, essentiellement des etiquettes de
graphe zoomables.

**Interoperabilite (lot E, clos).** Bug reel trouve : `coins.ts` decoupait
`content_authors` sur la virgule seule alors que `citation-meta.ts`, qui
alimente les balises Highwire de la **meme page**, a un `splitAuthors` correct.
Sur `Diamond, A.; Ling, D.S.`, Highwire annoncait 2 auteurs et COinS 4, dont
`A.` et `D.S.` seuls — et Zotero resout COinS avant Embedded Metadata, donc
c'est la version fausse qui gagnait. Corrige et teste (PR #302).

**ADR perime corrige.** `DECISIONS.md` disait « ne pas produire de `llms.txt` »
alors que la route existe et sert un fichier en prod. La route est posterieure a
l'entree : c'est la decision qui visait a cote, elle confondait « mecanisme
d'acces » (ecarte, argument toujours valable) et « panneau indicateur » (retenu,
purement additif). Critere pose pour les cas suivants : est-ce qu'on en
dependrait pour etre lu ? (PR #303)

**Lots B, C, D, F : verifies complets, aucun code manquant.** B1-B5 (marqueurs
de fleche, selecteur de sens a trois positions, imbrication au depliage,
epinglage, acces a la fiche depuis une source absorbee), C1-C3 (migration 026,
API, formulaire et coloration des noeuds fiche par mode de lecture), D1-D4
(migration 027, provenance des liens, `card_connections.py`, ecran
`/dashboard/new/[card_id]/connexions`), F1-F3 (`.docs/19-preuve-autorat.md`,
`.docs/20-profils-et-feed.md`, perimetre de la garantie dans `DECISIONS.md`).
Le selecteur de sens et les marqueurs de fleche sont confirmes en prod.

**Reste a faire, et pourquoi ca bloque.** Les audits de persona (#74 a #77 :
article de presse d'investigation, video de vulgarisation, essai de blog long
format, rapport institutionnel) demandent de **creer du vrai contenu** sous un
compte reel. Ils ne sont pas faisables sans l'utilisateur. Rappel : le corpus
actuel est un echantillon de un, il ne prouve rien sur le comportement des
createurs.

**Hors de portee d'un agent, a faire par l'utilisateur.** Soumettre le sitemap a
la Search Console — le rendu serveur rend les pages indexables, il ne les indexe
pas ; sans soumission, l'indexation prend des semaines plutot que des jours. Et
le DNS de `philum.app` chez le registrar.

572 tests backend et 132 tests frontend au vert.

---

## Session 2026-08-07 (apres-midi) — securite Supabase et rendu serveur

- **ADR-034 / migration `030_rls_lockdown`** (PR #296, appliquee en prod).
  Supabase exposait le schema `public` en PostgREST : les 11 tables etaient
  sans RLS et les roles `anon` / `authenticated` portaient
  `SELECT, INSERT, UPDATE, DELETE, TRUNCATE` sur toutes, y compris `users` et
  les cles privees chiffrees de `linked_accounts` — avec une cle `anon`
  publique par conception. Verifie apres coup :
  `tables=11 sans_RLS=0 grants_anon_auth=0`, application intacte.
  **Tout nouvel environnement Supabase doit rejouer ce verrou.**

- **Rendu serveur retabli** (PR #297). `src/routes/+layout.ts` portait
  `export const ssr = false` : accueil, pages vitrine et profils renvoyaient
  1477 octets et **zero caractere de texte indexable**. C'est la cause du
  `site:filum-eight.vercel.app` -> zero resultat, donc de l'echec de ChatGPT a
  atteindre les fiches (une couche de navigation IA qui ne trouve rien dans
  l'index ne tente jamais le GET). Le SSR redevient le defaut ; `dashboard`,
  `auth` et `sandbox` s'en exemptent explicitement. Le profil `/@[username]`
  passe d'un chargement en `$effect` (jamais execute en SSR) a un `load`
  SvelteKit, ce qui corrige aussi le soft-404. Mesure en prod apres deploiement :
  `/` 1500 car, `/about` 3406, `/features` 3693, `/discover` 4066,
  `/@mathias-pinault` 1587, `/@inexistant-xyz` -> **404**.

- **Diagnostic invalide a ne pas rejouer** : le `@` dans l'URL n'etait pas la
  cause de l'echec de ChatGPT. Teste avec les deux formes, echec identique.
  Les variantes `/c/<createur>/<fiche>` (PR #295) restent utiles pour les
  agents qui suivent l'en-tete `Link`, mais elles ne reglaient pas le probleme.

- **Serveur MCP** verifie de bout en bout sans authentification sur
  `https://philum-api.duckdns.org/mcp/` (protocole 2025-06-18) :
  `search_cards` et `get_card` repondent. C'est le canal d'acces qui marche
  aujourd'hui pour un agent conversationnel.

## Session 2026-08-07 (autonome) — audits persona #74-#77 : quatre fiches mesurees

Harnais `apps/backend/scripts/audit_personas.py` (PR #306) : il appelle
`parse_content_url` directement — le code exact derriere le bouton « importer
depuis une URL » du dashboard — sans aucune ecriture en base ni en prod.
Quatre URLs publiques reelles, une par persona. Six defauts trouves, chacun
mesure d'abord, chacun corrige par un test ecrit rouge avant le code.

| persona | URL | avant | apres | confiance | sans titre |
|---|---|---|---|---|---|
| journaliste | ProPublica *How the IRS was gutted* | 0 | **12** | medium | 0 |
| vulgarisateur | YouTube 3Blue1Brown *neural network* | 16 (bruitees) | **6** (propres) | high | 0 |
| essayiste | gwern.net *scaling hypothesis* | 0 | **78** | medium | 0 |
| institution | fiche depression de l'OMS | 1 | **6** | medium | 0 |

Les correctifs, par PR :

- **#306** `_resolve_confidence` — l'ecran annoncait « confiance haute » sur
  **zero reference**, c'est-a-dire affirmait que le contenu ne cite rien. La
  promotion medium → high exige desormais que l'oracle ait effectivement
  fourni quelque chose : un resultat vide satisfait « zero ref enrichie » sans
  etre le cas vise.
- **#306** `_fallback_title_from_anchor` — 6 sources sur 11 arrivaient sans
  titre, plusieurs sites (treasury.gov) refusant la visite du backfill. Une
  source sans titre s'affiche comme une URL nue, que le lecteur ne peut pas
  situer. Le texte du lien est le dernier filet, borne a 120 caracteres —
  `raw_text` porte aussi des blocs de reference entiers (Frontiers, PMC).
- **#307** `app/extractors/body_links.py` — un article de presse et un essai
  n'ont pas de section References : leur bibliographie est faite de liens
  poses dans le texte. Sans ce repli, journaliste et essayiste voyaient un
  **ecran vide** la ou la page cite des dizaines de pieces. ⚠️ **Le module ne
  tranche pas ce qui est une source** — il ecarte ce qui ne peut pas en etre
  une (navigation, chrome, boutons de partage, ancres vides) et laisse
  l'auteur·ice arbitrer a l'ecran. D'ou le branchement aux seules pages sans
  section *et* sans refs Crossref, et la confiance maintenue a « medium ».
- **#307** ⚠️ **Le texte du lien n'est pas un titre.** Premiere version :
  `title = label`. Mesure : la fiche affichait « at least $3 billion », et
  renseigner `title` **bloquait silencieusement** `_backfill_url_metadata`,
  qui ne visite que les refs sans titre. Le label part en `raw_text`
  (contexte de citation) ; les vrais titres remontent alors.
- **#308** `is_creator_self_link` — la fin d'une description YouTube est un
  **bloc de signature** (Patreon, site perso, comptes sociaux, boutique)
  reconduit a l'identique d'une video a l'autre. 11 des 16 sources extraites
  en venaient. Filtre sur le nom de chaine (`videoDetails.author`) dans l'URL
  *et* dans le titre — l'album de la bande-son a une URL Spotify opaque que
  seul son titre trahit. Plancher a 6 caracteres : « Vox » apparait dans
  voxeurop.eu.
- **#309** citations internes — l'OMS cite **cinq de ses propres
  publications**, toutes ecartees comme « liens internes ». On distingue
  desormais par la **position** : un lien pose au milieu d'une phrase de texte
  courant (≥ 80 caracteres autour) est une citation, un lien isole dans un
  bloc court est de la navigation. Plafond a 20 : mesure des « liens internes
  dans une phrase » — ProPublica **0**, OMS **5**, Gwern **238**. Les trois
  regimes se separent nettement ; au-dela du plafond on n'en garde aucun,
  plutot que d'en trier arbitrairement (sinon la fiche Gwern passait de 78 a
  316 sources).

⚠️ **Non verifiable localement, consigne pour arbitrage ulterieur** :
`classification` est `None` sur toutes les sources en execution locale.
L'etage 7 (classification LLM source/promo/social/other) ne tourne pas sans
cle API, donc l'etiquetage promo/social n'a pas pu etre mesure sur ces quatre
personas. A refaire depuis le dashboard en prod.

594 tests backend verts. PRs #306 → #309 toutes mergees sur `main`.

### Suite : le manque d'annee (PR #315)

Le re-audit apres #309→#314 ne montre **aucune regression** (12 / 6 / 78 / 6
sources, `sans titre=0` partout) mais un manque massif : `sans annee` = 10/12,
5/6, 35/78, 6/6. Une source sans annee tombe dans la colonne « sans date » de
la frise chronologique.

Sonde 1 : **100 %** de ces sources portent un titre. Le backfill d'URL les
saute donc toutes, par construction (`imports.py:331` et `:386` ne visitent
que les refs *sans titre*).

Sonde 2 — la question decisive, posee aux pages elles-memes : **9 des 10
pages sondees ne publient aucune date exploitable** (treasury.gov,
washingtonpost/archive, colah.github.io, distill.pub, github, openai.com,
incompleteideas.net, who.int, vizhub). Elargir le backfill aux refs « titrees
mais sans annee » couterait des dizaines de visites reseau par import pour
recuperer environ une date sur dix. **Ecarte, faute de justification.**

La 10e page revele en revanche un vrai defaut, corrige par #315 : bioRxiv et
medRxiv collent le numero de version et la variante d'affichage au DOI dans
le chemin. `10.1101/2020.06.26.174482.full` ne retourne **rien** de Crossref ;
le meme DOI sans suffixe retourne titre et date (2020-06-27). Le nettoyage
existait mais n'attendait qu'un separateur `/`, la ou ces serveurs utilisent
un point et les cumulent (`v2.full.pdf`).

Sonde 3 : la date presente dans le *chemin* de certaines URLs de presse
(`/1996/02/03/`) semblait un gisement gratuit — aucune requete reseau. Mesure
sur les quatre personas : **1 source sur 55** sans annee en porte une
(journaliste 1/10, vulgarisateur 0/5, essayiste 0/34, institution 0/6).
Ecrire un extracteur de date d'URL pour une source rendrait le code plus
lourd sans rendre une fiche plus lisible. **Ecarte.**

Apres #315, l'essayiste passe de 35 a **34** sources sans annee : le preprint
bioRxiv a recupere sa date. Reste que la majorite des sources sans annee sont
des pages qui, reellement, n'en publient pas — ce n'est pas un defaut du
pipeline mais un fait du web, et la colonne « sans date » de la frise existe
precisement pour ca.

609 tests backend verts.

## Session 2026-08-07 (autonome) — la surveillance du corpus vaut-elle la peine ?

Question posee **avant** d'ecrire la moindre ligne de produit de veille : sur
les sources reellement publiees, combien de retractations, de liens morts et
de bascules en acces ouvert une surveillance periodique trouverait-elle ? Si
le chiffre etait proche de zero, mieux valait le savoir tout de suite.
Script `apps/backend/scripts/mesure_surveillance.py`, resultat brut dans
`apps/backend/mesure_surveillance.json`.

**643 sources publiees, 575 portant un DOI.** Ce qu'une veille trouverait :

- **6 corrections/retractations** non refletees a l'ecran. ⚠️ **Deux d'entre
  elles sont enregistrees en base comme `unverifiable`** : ce n'est pas une
  absence d'information, c'est une information **perimee et fausse**. La
  fiche affirme « je n'ai pas pu verifier » la ou le papier est corrige.
- **117 bascules en acces ouvert.** Une source enregistree comme fermee est
  devenue librement lisible sans que la fiche le dise. C'est le gisement le
  plus gros, et de loin celui qui sert le plus le lecteur.
- **5 liens morts**, dont **4 DOI `doi.org` qui ne resolvent plus** sur des
  articles anciens (`10.1111/j.1572-0241.*`). Un DOI mort est une promesse de
  permanence rompue : c'est precisement ce que Philum pretend garantir.
- Repartition acces ouvert mesuree : 341 `unverifiable`, 114 `closed`, 36
  `green`, 36 `bronze`, 31 `gold`, 15 `hybrid`, 2 `diamond`.

⚠️ **Biais de mesure a ne pas oublier** : sur les 610 liens testes, **455 ont
repondu « bloque »** (anti-bot). Les 5 morts sont donc un **plancher**, pas
un compte. Le vrai chiffre est necessairement plus eleve, et une veille
devra distinguer « le serveur me refuse » de « la ressource n'existe plus » —
la faute deja payee neuf fois en session 2026-08-04.

**Conclusion : la surveillance a un interet mesure**, porte surtout par les
117 bascules d'acces ouvert et par les 2 etats perimes qui font mentir la
fiche. Le corpus reste toutefois celui d'un seul createur (cf. la limite
consignee ailleurs : il ne prouve rien sur le comportement des createurs en
general).

✅ **Ces deux gisements sont desormais captes par #311**, sans ordonnanceur ni
produit de veille nouveau : le declenchement paresseux existant reprend les
verdicts qui ont vieilli. Trois regimes plutot qu'un delai unique — jamais
sans DOI (aucun service ne sait repondre, le « non verifiable » y est
definitif), 6 h quand le verdict est `unverifiable` **avec** un DOI (c'est une
panne de service, pas un fait), 30 j pour un verdict etabli.

⚠️ **Ce qui reste non justifie par la mesure** : la surveillance des liens
morts. 5 sur 610 seulement, et **455 des liens testes repondent « bloque »** —
le chiffre est un plancher, pas un compte. Construire un produit de veille de
liens sur cette base serait batir sur une mesure qu'on sait aveugle. A
remesurer si l'anti-bot se contourne.

## Session 2026-08-07 (nuit) — chantier 2 : DOI depuis URL editeur

Branche `feat/extraction-pipeline-v2`. Le pipeline d'extraction v2 (ADR-030,
389a291, 2026-07-23) etait deja en prod avec ses 7 etages, ses tests unitaires
et son integration frontend (`extraction_confidence`, `refs_from_oracle`,
`refs_dropped_validation`). Le plan `agent/plans/2026-08-07-chantiers-conception.md`
listait « chantier 2 pending » a tort.

Ce qui reste vraiment ajoute cette session :
- **DOI derive de l'URL editeur** pour Nature (`10.1038/<slug>`), bioRxiv
  et medRxiv (`10.1101/<date>.<id>` avec strip du suffixe de version `vN`).
  Sans cette resolution, la fiche Nature `nrn3667` faisait echouer tout le
  pipeline : anti-bot bloque le HTML, aucun DOI dans l'URL -> Crossref
  jamais interroge -> zero ref extraite. Maintenant Crossref donne les 152
  refs autoritatives et le blocage anti-bot est sans consequence.

## Session 2026-08-07 (soir) — chantiers de conception

Branche `feat/chantiers-p0-p3-ia-feed-search`, 5 chantiers du plan `agent/plans/2026-08-07-chantiers-conception.md` :

- **3a** — message anti-scraping oriente maintenant vers l'import fichier (`.ris`/`.bib`) quand Nature/Elsevier/IEEE bloquent. Meme logique pour « aucune section References ».
- **1B** — content negotiation : `hooks.server.ts` reecrit l'URL canonique vers `.md` ou `.philum.json` selon `Accept`. Une seule URL, plusieurs representations.
- **1C** — nouveau format `application/vnd.philum+json` (JSON-LD schema.org + champs Philum : `philum:stance`, `philum:retractionStatus`, `philum:archiveUrl`). Route `.philum.json` et export backend `format=philum`.
- **5** — recherche createurs : endpoint `GET /discover/creators`, page `/discover/creators` avec onglet depuis `/discover`.
- **4** — feed chronologique : migration `028_feed_events`, endpoint `GET /feed` (curseur `before`), page `/feed` groupee par jour, insertion automatique dans `publish_card`. Registre, jamais fil algorithmique.

Migrations a appliquer sur la VM apres merge : **028_feed_events**.

Chantiers restant du plan :
- **2** — pipeline extraction v2 (7 etages, plan `.claude/plans/effervescent-foraging-lollipop.md`), 3-4 j
- **6** — audits persona (#74-#77) : besoin de creer du vrai contenu
- **7** — audit visiteur (#78) : besoin de test mobile

## PRs ouvertes

**`feat/graphe-corrections-visuelles` (en cours, sessions 2026-08-06 / 2026-08-07)** — **graphe, connexions et identité** — PR à ouvrir après la vérification finale :
- **Lot A** (A1-A3) : épaisseur des liens caractérisés réduite, légende repliable, purge des em-dashes.
- **Lot B** (B1-B5) : flèches de sens sur les arêtes fiche→fiche, sélecteur à trois positions (sortant/entrant/deux), imbrication des fiches affichée, épinglage, lien « ★ Ouvrir la fiche Philum » dans l'encadré de source.
- **Lot C** (C1-C3) : migration `026_card_ref` (columns `format`/`category`/`author_kind` sur `biblio_cards`), PATCH API + schéma, sélecteur UI dans le formulaire de fiche, coloration des nœuds fiche selon le mode de couleur actif.
- **Lot D** (D1-D4) : migration `027_link_prov` (`link_origin`/`link_confirmed_at` sur `sources`), `LinkResolution` + `resolve_link()` dans `card_link.py`, endpoints REST de gestion des connexions (`GET/POST/DELETE /api/v1/cards/{id}/connections`), page `/dashboard/new/[card_id]/connexions` avec encart ambre pour les suggestions, liste des citations entrantes en lecture seule, bande d'annulation 8 s.
- **Lot E** (E1-E3) : `coinsTitle()` dans `$lib/utils/coins.ts` + `<span class="Z3988">` sur la fiche publique, balises Highwire déjà en place (#239) ; alertes de citation déjà sur le dashboard (#248) ; décision `llms.txt` → MCP consignée dans `DECISIONS.md`.
- **Lot F** (F1-F3) : `.docs/19-preuve-autorat.md` (périmètre honnête de la garantie, anti-usurpation, formulations interdites, ORCID, faux) ; `.docs/20-profils-et-feed.md` (feed chronologique, recherche créateurs) ; question feed rétroactivité dans `.docs/07-open-questions.md`.
- **731 tests backend, 131 tests frontend, 0 erreur lint.**
- **Non encore déployé** : les migrations 026 et 027 doivent être appliquées sur la VM après le merge.

**#281 → #287** — Session 2026-08-05 (autonome) — **rendre les fiches trouvables, cesser de servir ce qui était privé, cesser de perdre des références, cesser de confondre une citation avec un titre.** Toutes mergées, VM redéployée et prod vérifiée.
- **#281** `fix/mcp-fiches-privees` — ⚠️ **vraie fuite de données**. Le serveur MCP (ses quatre outils) et l'endpoint d'export public (ses huit formats) ne filtraient que sur `status == "published"`. Or **« publiée » dit que le travail est achevé, « publique » qu'il est offert au monde** : une fiche pouvait être l'un sans être l'autre, et n'importe quel appelant anonyme obtenait la bibliographie complète de fiches que leur autrice avait gardées privées. Prouvé rouge avant correction (4 échecs MCP, 6 échecs d'export — un par format). Le contrôle était recopié à chaque route publique et l'export l'avait simplement oublié : il passe désormais par un `_load_public_card()` unique, qui répond **404 et non 403** pour ne pas confirmer qu'une fiche existe à cette adresse. Le graphe, lui, était déjà protégé.
- **#282** `feat/annuaire-public` — tout était déjà accessible sans compte (HTML rendu côté serveur, JSON-LD portant la bibliographie dans `citation[]`, REST public, MCP anonyme) mais **rien ne permettait de *trouver* une fiche** sans en connaître l'adresse : `robots.txt`, `sitemap.xml` et toute surface de navigation répondaient 404 en prod. Ajoute `GET /api/v1/discover` (recherche plein texte titre / description / auteur du contenu / créateur, filtres plateforme / type / dates, tri, pagination, sans authentification) et `/discover/facets`. ⚠️ **Un seul chemin de filtrage partagé** entre la requête de résultats et celle des comptes, pour que les facettes ne puissent pas diverger des résultats — l'interface n'invente pas ses filtres depuis les enums du modèle, une case à cocher qui ne ramène jamais rien est une promesse non tenue. Page `/discover` avec tout l'état dans l'URL (partageable, et rendue côté serveur pour les crawlers) ; « aucun résultat » et « je n'ai pas pu chercher » restent deux phrases distinctes. `autoescape=True` sur la recherche, sans quoi un `%` saisi ramène tout le corpus. **Vérifié en prod** : 10 fiches publiques rendues en SSR, sitemap à 18 URL, `llms.txt` pointant vers `philum-api.duckdns.org/mcp` (l'annoncer à l'origine du front enverrait un agent sur une 404).
- **#283** `feat/fiches-markdown` — un agent conversationnel à qui on donne `/@créateur/fiche` reçoit du HTML, doit en extraire la bibliographie, **et c'est là qu'il invente**. Suffixer `.md` lui rend le même contenu déjà structuré, servi par l'export markdown du backend — **une seule sérialisation**, donc aucune divergence possible entre ce qu'on télécharge et ce qu'on lit (l'écart entre deux copies d'une même vérité est la faute payée en #263/#264). L'export s'enrichit de ce qui rend une source *vérifiable* et pas seulement citable : rétractation + DOI de l'avis, DOI quand l'URL ne le porte pas déjà, texte intégral gratuit, revue, position déclarée. Bouton « Pour une IA » sur la fiche, `<link rel="alternate" type="text/markdown">` et une entrée dans `llms.txt` pour que l'agent apprenne la convention sans la deviner. ⚠️ **Une mesure a changé le design** : rendu sur la fiche réelle de 185 sources, répéter l'état de vérification sous chaque source ajoutait **370 lignes n'affirmant rien** et noyait les quelques faits qui comptent — le détail par source ne porte donc que des **faits établis**, et le recensement complet passe en tête sous `## Fiabilité des sources`. Rien n'est tu, c'est la place de l'information qui change (796 → 510 lignes) ; « jamais vérifiée », « vérifiée sans rétractation » et « non vérifiable » restent trois phrases distinctes. **Limite mesurée et assumée** : `parse_markdown` récolte toute URL **et tout DOI nu**, donc l'URL d'accès ouvert et le DOI d'un avis de rétractation coûtent chacun une source fantôme au réimport — deux tests le mesurent plutôt que de le taire. **Vérifié en prod** : `text/markdown` sans `content-disposition`, 75 lignes d'accès ouvert, 404 sur fiche inexistante.
- **#285** `fix/scoring-ne-supprime-plus-de-refs-reelles` — une fiche recréée par extraction seule affichait **184 références là où l'éditeur en dépose 187**. Ni Crossref, ni la dédup, ni l'URL obligatoire : l'**étage 6 (scoring syntaxique)** en supprimait trois, silencieusement, alors que chacune portait un DOI valide (mesure locale sur `10.1186/s12916-019-1380-z` : Crossref 187 → dédup 187 → **scoring 184**). Il les jugeait sur le champ `unstructured` de Crossref — **la citation brute entière recopiée dans `title`** — et y voyait des mots dupliqués là où il y avait deux auteurs homonymes (`Nasr I, Nasr I`) et un titre publié reprenant une expression (`... risk of celiac disease: risk of celiac disease ...`). Deux corrections agnostiques : une répétition ne compte comme artefact de concaténation que si elle **recouvre ≥ 50 % des mots** du titre ; et **un DOI résolvable prime sur toute heuristique typographique** — ce module note la cohérence d'un titre, il n'a pas autorité pour supprimer une œuvre enregistrée dont le titre reste rattrapable par résolution. ⚠️ **La cause amont reste ouverte** : `_crossref_reference_item_to_ref` (`url_extractor.py:549`) recopie `unstructured` dans `title` au lieu de le laisser en `raw_text`, ce qui produit aussi les titres dégradés sur les dépôts Springer/BMC (99 % des refs de cet article, contre 0 % chez Frontiers qui dépose structuré).
- **#286** `fix/aucune-reference-ecartee-faute-de-lien` — le `.ris` que Springer expose (`citation-needed.springer.com/v2/references/<DOI>?format=refman&flavour=references` — bien `flavour=references`, pas `citation` qui ne rend que l'article lui-même) compte **187 entrées ; Philum en importait 170**. Les 17 écartées portaient auteurs, année, revue et titre complets : leur seul tort, aucune adresse. **Un livre, un chapitre, un article antérieur au DOI n'en ont pas** — les écarter ampute une bibliographie de ses références les plus anciennes, celles qu'aucune autre voie ne rattrapera. Les trois parseurs (RIS, BibTeX, CSL-JSON) le faisaient au nom d'une contrainte énoncée dans le docstring du module — « le modèle Source exige une URL » — **qui n'existe plus** : `SourceCreate.url` a pour défaut la chaîne vide et un chemin voisin (`_s2_ref_to_imported_ref`) conservait déjà ces refs ; le commentaire avait survécu à la règle. Une entrée n'est désormais écartée que si **rien ne l'identifie**, ni adresse ni titre — sans URL *ni* titre elle reste comptée dans `skipped`, le silence serait malhonnête. ⚠️ `_dedupe` distingue les refs sans lien par titre + auteurs + année : la clé URL vide les aurait **toutes fondues en une seule entrée**. Un test d'intégration tient la chaîne entière, de l'envoi en batch à la relecture — l'extraction ne sert à rien si l'enregistrement refuse ce qu'elle produit. Mesure : `170 / 17 écartées` → **`187 / 0 écartée`**.
- **#287** `fix/crossref-unstructured-titles` — la cause amont laissée ouverte par #285. Springer, BMC et Wiley ne déposent souvent chez Crossref **aucun champ structuré** : seulement la citation entière (`unstructured`), parfois seulement le nom de la revue (`journal-title`). Les deux étaient recopiés dans `title`, ce qui donnait 187 références intitulées `Okada H, Kuhn C. The hygiene hypothesis. Clin Exp Immunol. 2010;160(1):1-9.` — ou pire, `N Engl J Med`. Illisible pour un humain, et **c'est exactement ce sur quoi une IA hallucine** quand elle lit la fiche. ⚠️ **Le titre manquant se résout par le DOI, jamais en découpant la citation** : découper une chaîne de citation est une heuristique qui casse dès qu'un éditeur change de style, alors qu'interroger Crossref sur le DOI rend le titre exact que l'éditeur du papier *cité* a lui-même déposé — exact plutôt qu'heuristique, et valable pour n'importe quel éditeur. Requêtes groupées par 50 DOI (4 allers-retours pour 187 refs). La citation brute est conservée en `raw_text` et ne sert que de **dernier recours**, quand aucun DOI n'existe ; `journal` est stocké à part et n'est plus jamais pris pour un titre. Un échec réseau laisse la référence intacte. Mesure : `10.1186/s12916-019-1380-z` **187 refs, 175 désormais titrées correctement** (les 12 restantes n'ont aucun DOI, la citation brute est le repli honnête) ; aucune régression sur `10.3389/fpsyg.2022.651547` (152 refs, 0 citation brute).
- **Correctif d'accessibilité au passage** : `--text-tertiary` échouait au seuil WCAG AA dans **les deux thèmes** (3,54:1 en clair, 3,59:1 en sombre). Ce token porte dates, compteurs et libellés de filtre, souvent en 12px, sur ~118 usages du dépôt — corrigé **au niveau du token** (#757575 → 4,61:1 ; #8B92A1 → 5,52:1) plutôt qu'en rustine sur la seule page nouvelle, hiérarchie préservée (secondaire à 7,13:1). **Reste ouvert** : `--text-placeholder` clair est à 2,17:1, et il n'y a pas de place entre un placeholder conforme et le nouveau tertiaire — arbitrage produit, pas un patch glissé dans cette PR.

**#257 → #272** — Session 2026-08-04 (autonome) — **audit UX de bout en bout, puis une même faute retrouvée à neuf profondeurs différentes.** Toutes mergées, VM redéployée. Le fil conducteur : *un état ne doit jamais en absorber un autre.* Un délai n'est pas un échec ; rien à archiver n'est pas un échec d'archivage ; un service qui refuse de répondre n'est pas une absence d'instantané ; un canal qui refuse n'est pas l'archive qui n'a rien ; un dépassement de délai n'est pas une réponse ; un panneau indicateur n'est pas la ressource ; une capture de « Redirecting » n'est pas une archive ; une source jamais atteinte n'est pas « en attente », elle est ignorée ; et **« le service a essayé et échoué » n'est pas « le service refuse de me répondre »**.
- **#257** `fix/archivage-cadence` — l'archivage inscrivait `failed` faute d'avoir trouvé à temps. Un délai n'est pas un échec : la source reste `pending` et la reprise paresseuse la repropose.
- **#258** `fix/fiche-demo` — métadonnées de la fiche démo. **Vérifié en prod** : 18 sources, 9 datées, 5 DOI, les 4 positions, 16 archivées, **0 en échec**.
- **#259** `fix/coherence-pages-vitrine` — trois affirmations fausses sur les pages publiques, chacune vérifiée dans le code avant correction : l'inscription Google est ouverte, donc la liste d'attente ne pouvait pas promettre « une notification à l'ouverture ». Six fonctionnalités livrées mais jamais annoncées ont été ajoutées à `/features` et `/roadmap` — **chacune grepée dans le code avant d'être vendue**.
- **#260** `fix/csrf-and-sandbox` — ⚠️ **vraie faille**. `csrf.checkOrigin: false` traînait depuis #22 sans justification écrite ; or le cookie de session est `SameSite=None` en prod et `/api/[...path]` relaie les POST avec ce cookie — une page tierce pouvait soumettre un formulaire authentifié. Rien ne requiert de POST cross-origin (les deux étapes OAuth sont des GET, aucune `action` SvelteKit). Bloc supprimé, **test vérifié rouge quand on le réintroduit**. Au passage `/sandbox` répond 404 hors développement.
- **#261** `fix/archive-not-applicable` — 4 sources sur 152 n'avaient **aucune URL** (manuel DSM-IV-TR, chapitre de livre) et étaient marquées `failed`. Nouvel état `not_applicable`, et surtout **dénominateur honnête** : `archivable_count` exclut ce qui n'a rien à archiver, sinon « 148/152 » était indépassable sur une fiche pourtant complète.
- **#262** `fix/wayback-adaptive-pacing` — mesuré sur la VM : Save Page Now répondait `429` **et** `523` malgré l'intervalle fixe de 6 s ; zéro source archivée sur 152. Deux défauts. ⚠️ **Un intervalle fixe ne peut pas être juste** — les limites d'archive.org ne sont pas publiées et varient avec sa charge. La cadence part d'un plancher, double à chaque refus (`Retry-After` honoré), redescend quand ça repasse, sous un budget de temps par lot. Et `_lookup_snapshot` avalait le 429 pour répondre « aucun instantané » — conclure sur une URL qu'on n'a **jamais réussi à interroger**. Le refus est désormais un signal distinct.
- **#263** `fix/archive-status-schema-enum` — ⚠️ **régression de #261, active en prod, trouvée par la vérification post-déploiement**. `not_applicable` était écrit en base par la migration 024, mais `app/schemas/source.py` redéclarait **sa propre copie** de l'enum, restée à trois valeurs : toute fiche contenant une source sans URL répondait **500**. La fiche de démo n'en contient aucune — elle passait, ce qui a rendu la CI *et* le premier contrôle post-déploiement muets. La copie est supprimée, le schéma réexporte l'enum du modèle, deux tests interdisent la divergence de revenir.
- **#264** `test/enums-parity` — la parade générique à #263, écrite parce que corriger une copie ne dit rien des six autres. Le test **découvre les enums par introspection** de `app.models` et `app.schemas` et exige que toute paire homonyme porte les mêmes valeurs — il couvre donc aussi les enums qui n'existent pas encore. **Vérifié rouge** en injectant une valeur canari dans une seule des deux déclarations.
- **#265** `fix/wayback-cdx-fallback` — toujours zéro archivée après #262. Mesuré depuis la VM, **à la même seconde et depuis la même IP** : `archive.org/wayback/available` répondait `429` pendant que `web.archive.org/cdx/search/cdx` répondait `200` avec l'instantané. ⚠️ **La limitation porte sur le point d'entrée, pas sur l'archive.** Les deux canaux interrogent le même index ; `ThrottledError` n'est levée que si *aucun* n'a pu se prononcer, et une absence n'est affirmée que sur une réponse saine.
- **#266** `fix/wayback-lookup-first` — toujours zéro. Le sondage exécuté **à la main dans le conteneur** trouvait l'instantané de la première URL immédiatement : le lot ne parvenait donc jamais à la phase de sondage. Deux défauts. ⚠️ **On demandait une capture avant de regarder s'il en existait une** — or une bibliographie académique cite surtout des travaux archivés depuis des années, et Save Page Now est la partie la plus lente et la plus limitée du service. Les deux boucles sont inversées. Et ⚠️ **le budget comptait les pauses, pas le temps écoulé** : avec des requêtes de 30 s, un lot tenait des heures sans jamais « dépasser » 900 s. Le test de #257 qui figeait l'ancien ordre a été **réécrit, pas supprimé**, sa justification conservée.
- **#267** `fix/wayback-lookup-timeout` — toujours zéro, et le journal disait `Wayback lookup unusable ... :` suivi de rien. ⚠️ **`httpx.ReadTimeout` a un `str()` vide** — le log taisait sa propre cause. J'ai d'abord soupçonné un corps CDX vide ; `curl` a prouvé que CDX renvoie un `[]\n` parfaitement valide. La mesure a tranché : **18,41 s / 18,68 s / 19,67 s** pour trois appels ne renvoyant rien, contre un délai partagé de 30 s. CDX cherche dans un index de centaines de milliards de captures — il a droit à son propre délai (60 s), et le journal consigne désormais le **type** de l'exception, pas seulement son message.
- **#268** `fix/wayback-resolve-redirects` — toujours zéro, et la mesure a enfin nommé la cause : **les 148 sources en attente sont toutes des `doi.org`**. `doi.org` est un résolveur ; toutes ses captures sont des `302`, le sondage filtre sur `200` et ne pouvait donc rien trouver. ⚠️ **On sondait et on archivait le panneau indicateur au lieu de la ressource.** Le filtre `200` a raison — c'est l'URL visée qui était mauvaise. Résolution par **comportement**, jamais par liste de domaines. Deux pièges réels, chacun testé : les éditeurs répondent `403` aux robots mais la redirection a déjà eu lieu (juger sur le code jetterait une URL exacte), et **doi.org limite lui aussi les rafales** — une résolution impossible laisse l'URL intacte. **Vérifié en prod : 0 → 16 archivées.** Au passage, les recorders des tests existants n'écrasaient pas `_resolve` et faisaient de **vrais appels réseau** (suite wayback : 50 s → 1 s).
- **#269** `fix/wayback-meta-refresh` — trouvée **en lisant le résultat plutôt que le compteur**. Plusieurs des 16 pointaient sur `linkinghub.elsevier.com` ; j'ai ouvert l'instantané : **9,5 ko de HTML pour un seul mot de texte, « Redirecting »**. ⚠️ `linkinghub` répond **200** — aucun client HTTP n'y voit une redirection — avec un `<meta http-equiv="refresh">`. Seize sources affirmaient donc être archivées sur une capture qui ne préserve **rien** : la même faute, un cran plus bas encore. Les deux formes de redirection sont désormais suivies. Garde-fou testé : les deux conditions sont exigées sur la **même balise**, sans quoi un `<meta name="citation_title" content="0; url=…">` déplacerait la cible. Les 23 sources concernées ont été remises en attente par un correctif ponctuel formulé en règle générale (une capture ne vaut que si elle a saisi la ressource).
- **#270** `fix/wayback-refresh-entities` — trouvée **en lisant la sortie de cette réparation**, pas en relisant le code : la résolution rendait `…%3Fvia%253Dihub&`, avec un `&` final seul. ⚠️ Mon motif bornait l'URL sur `;` — or le point-virgule n'apparaît dans une URL de `meta refresh` qu'à l'intérieur d'une **entité HTML**. La cible était coupée au milieu de `&amp;`. Corrigé, la chaîne atteint bien `sciencedirect.com/science/article/pii/…`. **Vérifié en prod après redéploiement** : les 16 `archive_url` pointent toutes vers un éditeur réel (Wiley, ScienceDirect, Cambridge, Frontiers, Hindawi, Taylor & Francis) — plus aucun `doi.org` ni `linkinghub`. Deux instantanés relus : **12 146 et 641 mots**, titres conformes à la référence citée, contre **1 mot** avant. **Limite mesurée et volontairement non corrigée** : CDX cherche l'URL exacte et `linkinghub` ajoute `?via=ihub` ; retirer la requête à l'aveugle transformerait `article.aspx?doi=…` en `article.aspx`, une page générique — on archiverait la mauvaise ressource. Consignée dans les bugs latents.
- **#271** `fix/wayback-tour-de-role` — les 16 archivées de #270 pointaient enfin sur la bonne ressource, mais **132 restaient en attente après six passes de reprise**, avec un journal montrant des réponses CDX saines. La cause n'était ni la résolution ni la cadence : `cards.py` construisait la liste des `pending` **toujours dans le même ordre**, et le lot s'arrête sur son budget de temps. ⚠️ **Les sources situées après la frontière n'étaient jamais atteintes — pas « plus tard », jamais.** Mesuré en résolvant un échantillon à la main : `10.3389/fnsys.2014.00206` et `10.3389/fnhum.2017.00020` avaient une capture `200` disponible à l'instant même et restaient `pending`. Même faute que le reste de la série, une couche plus haut : `pending` disait « en cours de traitement » pour des sources que personne ne traitait. Le remède rend l'état vrai — `archive_attempted_at` consigne **quand on a essayé**, distinctement de `archive_timestamp` qui date **la capture** (les confondre réintroduirait exactement l'erreur corrigée ici), et la file sert d'abord les sources tentées le moins récemment. Garde-fou testé : **marquer une tentative ne conclut rien** — ni `archived` ni `failed`. **Question de backlog tranchée au passage** : retirer les paramètres de tracking avant la requête CDX n'est pas seulement risqué, c'est **mesurément faux** — sur 15 URL, les 4 cas où seule l'URL nue avait une capture renvoyaient **tous la même page générique** `linkinghub.elsevier.com/retrieve/articleSelectSinglePerm`. Quatre articles distincts auraient été marqués archivés sur une seule page de rebond.
- **#272** `fix/wayback-save-outcome` — trouvée **en surveillant l'effet de #271**, pas en relisant le code : le tour de rôle a bien débloqué le sondage (130 → 125 en attente, 18 → 23 archivées après six passes stériles), puis tout s'est figé à 10:09. La phase de **capture** du lot répondait `520` sur toutes ses requêtes, et le service réessayait la même URL en doublant l'attente — 19 s, 30 s, 56 s, 102 s, 127 s — soit **les 900 s du budget brûlées sur sept requêtes et deux URL**, zéro capture demandée pour les 128 autres sources. ⚠️ En lisant le **corps** de ces `520` depuis la VM, ce ne sont pas des refus de service, et ils ne disent même pas tous la même chose : `example.com` → « already captured 5 times today […] please try again tomorrow » ; `sciencedirect.com/…?via%3Dihub` → « Job failed », archive.org a essayé et n'a pas pu — cohérent avec nos propres journaux où l'éditeur répond `403` aux robots. Dans les deux cas le service **s'est prononcé sur cette URL** : redemander la même deux minutes plus tard ne peut rien y changer, et sur le cas du quota **ce sont nos propres réessais qui le consomment**. Le remède : seuls `429`, `503` et `523` disent « reviens plus tard » et ralentissent la cadence ; tout autre code fait passer à l'URL suivante et **laisse la source `pending`** — « archive.org n'a pas pu capturer aujourd'hui » n'est pas « cette page est perdue ». Le critère est le **code de réponse, jamais le corps** : lire de la prose HTML pour piloter un flot de contrôle réintroduirait la fragilité de #269 ; aucune liste de domaines non plus. **Deux garde-fous testés** : `_refusal` reste inchangée, donc sur le chemin du **sondage** un `5xx` demeure une absence de réponse et jamais une absence d'instantané (régression de #262) ; et un `429` reste bien réessayé, pour que le correctif ne devienne pas « on n'insiste plus jamais ».
- **Leçon de méthode** : quatre expériences successives ont été nécessaires pour distinguer « archive.org est en panne » de « nous sommes limités » — et **deux hypothèses intermédiaires ont dû être corrigées** (un `200` isolé s'est révélé être un cache CDN). Instrumenter avant de spéculer, y compris contre soi-même.
- **Décision assumée** : pas de refonte UI. L'interface est cohérente ; c'était la donnée affichée qui était vide ou fausse.

**#251 → #256** — Session 2026-08-03 (autonome) — **passe de sécurité et de dépendances**, une fois les 9 chantiers livrés :
- **#251** `fix/postcss-path-traversal` — la seule alerte Dependabot ouverte (sévérité haute, scope runtime) : postcss ≤ 8.5.17 laissait un `sourceMappingURL` forgé faire lire un `.map` arbitraire au build. Le lockfile était sur 8.5.14. ⚠️ **Le plancher déclaré `^8.5.0` autorisait la plage vulnérable** — il ne suffit pas de bouger le lockfile, le plancher est relevé à `^8.5.25` pour qu'il ne puisse plus redescendre. Même logique appliquée aux autres paquets : `^9.0.0` ou `^5.0.0` permettaient un lockfile très en deçà de ce qui est réellement testé. **Mergée. Zéro alerte Dependabot ouverte depuis.**
- **#252** `chore/deps-patch-minor` — svelte 5.56.8, prettier 3.9.6, @eslint/js 9.39.5, @testing-library/svelte 5.4.2, @tailwindcss/typography 0.5.20. **Mergée.**
- **#253** `chore/deps-actions` — setup-python v7, setup-node v7, codeql-action v4.37.3, trufflehog 6f3c981. ⚠️ De l'infra CI ne se vérifie pas en local : **la CI de la PR elle-même est la seule validation qui vaille**. **Mergée.**
- **#254** `chore/deps-test-majors` — jsdom 30, jest-dom 7. Majeures, mais confinées à l'outillage de test. **Mergée.**
- **#255** `chore/deps-prettier-svelte4` — prettier-plugin-svelte 4.1.1. La crainte usuelle (un reformatage massif noyant les revues suivantes) a été **mesurée plutôt que supposée** : `prettier --write .` ne modifie aucun fichier. **Mergée.**
- **#256** `chore/deps-eslint10` — eslint 10.8.0. ⚠️ **La montée a trouvé un vrai défaut** : la nouvelle règle `no-useless-assignment` a relevé `let host = ''` dans `guessPlatform` (`dashboard/new/+page.svelte`), dont la valeur initiale n'était jamais lue puisque le `catch` sort en retour anticipé. Corrigé en `let host: string`.
- **Méthode** : 15 PRs Dependabot regroupées en 6 PRs par nature de risque (patch/minor, infra CI, outillage de test, formateur, linter), pour ne pas déclencher 15 CI complètes et pour qu'un job rouge désigne sans ambiguïté sa cause.

**#250** — `feat/colonnes-comparaison`. Session 2026-08-03 (autonome) — **chantier 9, la matrice de comparaison sans un seul appel à un modèle**. **Mergée et déployée le 2026-08-03** (sélecteur « Liste / Tableau » rendu côté serveur en prod) :
- Bouton « Liste / Tableau » au-dessus des sources citées. Six colonnes triables — année, type, revue ou éditeur, accès, rétraction, position déclarée — toutes lues dans des champs déjà en base. Rien n'est généré, donc rien ne peut être halluciné : c'est le contrat qui sépare ce tableau des matrices LLM.
- ⚠️ **Aucune case n'est vide.** Le `N/A` indifférencié de SciSpace (étude §2.4) confond « l'information manque » et « le document est inaccessible ». Ici quatre formulations qui ne se recouvrent jamais : *non renseignée* (rien n'a été saisi), *sans objet* (un podcast n'a pas de revue), *non vérifié* (le contrôle n'a jamais tourné), *non vérifiable* (le contrôle ne peut pas conclure). Même règle à trois états que `retraction_status` / `oa_status` ; un `stance` non déclaré n'est jamais rabattu sur « mentionne ».
- Le tri suit la même logique : **une absence n'a pas de rang** et se range en queue dans les deux sens. Troisième clic sur un en-tête → retour à l'ordre voulu par l'auteur. La liste reste montée sous le tableau (`hidden print:block`) car c'est elle qui porte les balises COinS que Zotero détecte.
- 🔧 Bug attrapé au navigateur : le clic sur une ligne ne défilait pas jusqu'à la source. `requestAnimationFrame` s'exécutait avant que Svelte n'ait retiré la classe `hidden` — sans boîte de rendu, `scrollIntoView` est un no-op. Remplacé par `await tick()`.
- Vérifié sur données de prod (Frontiers 651547, 152 références) : **152 lignes, 0 cellule vide**, trois formulations d'absence présentes en réel (152 « non déclarée », 24 « non vérifiable », 13 « non renseignée »). 12 tests unitaires ; 105 tests frontend au vert.

**#249** — `fix/graphe-cadrage-dates`. Session 2026-08-03 (autonome) — **quatre défauts d'affichage du graphe, signalés à l'usage**. **Mergée le 2026-08-03** (frontend seul → Vercel déploie automatiquement) :
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
| Wayback queue durability | Moyenne | `asyncio.create_task` perdu au restart du container backend. Cf. F5 dans `13-audit-2026-05-26-followups.md`. Atténué depuis #274 : `POST /api/v1/sources/archive` permet de relancer à la main ce qui a été perdu, sans attendre le tour de rôle — mais la file reste en mémoire. |
| Pas de domaine custom | Feature | Brancher `philum.app` quand 1er ambassadeur prêt. |
| Liste d'attente email retirée de l'UI, back-end encore là | Faible | Décidé le 2026-08-04 : le bloc « laissez votre email » de la page d'accueil est retiré (l'inscription Google est ouverte, la promesse faisait doublon). **Seule la visibilité a été supprimée** — restent à supprimer quand la décision sera confirmée : `WaitlistForm.svelte` et son export, l'endpoint `app/api/v1/endpoints/waitlist.py`, le modèle et la table associés (migration). ⚠️ Vérifier d'abord si des adresses ont déjà été collectées : les supprimer sans les exporter perdrait des contacts réels. |
| Quota anonyme de Save Page Now | Faible | Mesuré le 2026-08-04 : archive.org répond `520` « already captured 5 times today » sur une URL déjà demandée. `wayback_api_key` existe dans la config mais est **vide en prod** (vérifié sur la VM) et n'est de toute façon jamais transmis à la demande de capture. Une clé S3 authentifiée relèverait le quota — elle exige un compte archive.org, donc une action humaine, pas un correctif de code. Sans elle, la convergence est simplement plus lente : depuis #272 le budget n'est plus brûlé sur une URL. **Vérifié en prod le 2026-08-04 après #274** : la fiche `inhibitory-control-…` est passée de 23 à 44 sources archivées sur 152, et les 44 portent toutes une vraie URL `web.archive.org` — aucune source « archivée » sans capture, aucune capture sans le statut. |
| Taxonomie « Plateforme » sans case pour une revue | Faible | Constaté en parcourant la création de fiche le 2026-08-04 : `nature.com` et `sciencedirect.com` retombent sur « Autre », faute d'entrée `revue-scientifique` dans l'enum `Platform`. Ce n'est pas une détection ratée mais une taxonomie incomplète : l'ajouter demande une migration côté backend, donc une décision, pas un correctif. |
| 131 brouillons dépliés d'un coup | Faible | Constaté le 2026-08-04 : une extraction de 131 réfs rend 131 formulaires, métadonnées étendues ouvertes dès que Crossref a répondu. `#276` a remonté « Tout ajouter » en tête de liste, mais la page reste très lourde. Replier par défaut cacherait ce qui a été extrait — arbitrage à trancher, pas à improviser. |
| Paramètre de suivi ajouté par un redirecteur | Moyenne | Mesuré le 2026-08-04 : `linkinghub` ajoute `?via=ihub`, et CDX cherche l'URL **exacte** — la capture de `…/pii/S0896627301005839` existe, celle de `…?via%3Dihub` non. Retirer la requête à l'aveugle serait pire : `article.aspx?doi=…` deviendrait `article.aspx`, une page générique, et on archiverait la mauvaise ressource. Il faut un critère qui distingue un paramètre de suivi d'un identifiant — pas une heuristique de plus. |

---

## Prochaines étapes (par ordre d'impact/coût)

> **Roadmap consolidée et priorisée** : [`.docs/19-roadmap-2026-07.md`](./.docs/19-roadmap-2026-07.md). Plan d'audit détaillé : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md). Comptes plateformes liés : [`.docs/18-linked-accounts.md`](./.docs/18-linked-accounts.md).

**Immédiat**
- ✅ **Dates manquantes et voie « sans date » en chronologie** (signalé le 2026-08-04) — **les deux défauts sont traités**, vérifié le 2026-08-07.
  1. ~~**L'identification de la date échoue là où la donnée existe.**~~ ✅ **#312**. Cause trouvée et mesurée comme générale : `_parse_crossref_work` ne lisait que `published-print` et `published-online`, et un enregistrement `posted-content` ne porte **ni l'un ni l'autre** — sa date vit dans `issued`. Vérifié sur OSF, bioRxiv et medRxiv comme la note le demandait. `issued` ajouté en **dernier** repli : présent sur tous les types (donc pas de branche par hébergeur ni de test sur `type`), et placé en dernier pour que la parution papier continue de faire foi — `nrn3667` reste à `2014-03-01`, aucun enregistrement déjà daté ne bouge. Cas témoin `10.31234/osf.io/x4yj3` : `null` → `2021-09-09`.
     - ⚠️ **Mesuré au passage, hors périmètre** : `_extract_doi` *et* le résolveur générique `resolve_doi_from_url` rendent `None` sur `osf.io/preprints/…` **et** `arxiv.org/abs/…`. Le correctif ci-dessus ne sauve donc que les références dont le DOI est déjà connu. L'oracle arXiv est au backlog du plan d'extraction v2 ; OSF n'y est pas encore.
  2. ~~**La voie « sans date » se lit comme une date.**~~ ✅ **déjà livré, la note était périmée**. `graph-chrono.ts` porte `breakX` — un **filet de rupture** explicite, convention usuelle pour « l'échelle s'interrompt ici » — et la colonne est passée **à droite** de la frise : à gauche elle occupait la place que l'œil lit comme « le plus ancien ». Rendu vérifié dans `SourceGraph.svelte:1140`, 16 tests dans `graph-chrono.test.ts`. Le principe est tenu : un simple décalage n'aurait pas suffi, une position sur un axe temporel *signifie* une date quel que soit l'écart.
- ~~Redéployer la VM GCP~~ ✅ fait le 2026-07-21 (464ba95, vérifié par curl).
- ~~3 alertes Dependabot high sur main~~ ✅ fermées le 2026-07-22 (PR #191 : overrides pnpm brace-expansion 1.x/5.x + js-yaml 4.x).
- ~~Alerte Dependabot high postcss (traversée de chemin)~~ ✅ fermée le 2026-08-03 (PR #251). **Zéro alerte ouverte**, et les 15 PRs Dependabot en attente ont été traitées ou closes (#251→#256).
- **Alerte budget 1 € sur GCP** (Billing → Budgets & alerts) si pas déjà en place — filet de sécurité, pas de plafond natif. *Action Cloud Console, hors de portée d'un agent.*
- **Décommissionner Railway** : supprimer le service + retirer l'ancienne redirect URI Railway du client OAuth Google. *Destructif et touche le client OAuth Google — demande une autorisation explicite, à ne pas faire en autonomie.*
- **Migrer Tailwind v3 → v4** (PR dédiée) : PR Dependabot #156 fermée car breaking (nouveau format config, PostCSS séparé `@tailwindcss/postcss`, syntaxes `@theme`/`@source`). ⚠️ Changement purement visuel : sans capture d'écran fonctionnelle, une régression ne serait pas détectable. Vérifier que l'outillage de capture marche **avant** de s'y lancer.

**Chantiers outils-chercheurs** (étude `agent/research/2026-08-03-outils-chercheurs.md`, dans l'ordre)
- ~~1. Meta tags Highwire + COinS~~ ✅ #239 · ~~2. Champ `stance` déclaratif~~ ✅ #240 · ~~3. Badge rétractation~~ ✅ #241+#242 · ~~4. Bornage + chronologie~~ ✅ #243+#244 · ~~5. Enrichissement OpenAlex~~ ✅ #245 · ~~6. Pivot CSL-JSON + RIS~~ ✅ #246 · ~~7. Import de fichier~~ ✅ #247 · ~~8. Alertes « on vous cite »~~ ✅ #248 · ~~9. Colonnes de comparaison sans IA~~ ✅ #250.
- **Les 9 chantiers de l'étude sont livrés.** Restent en réserve, plus lourds : extension navigateur (§3.6), colonnes custom LLM sur abstracts (§2.2), ancrage d'extrait fuzzy (§3.5), chemin entre deux nœuds (§3.4), Zotero Web API OAuth 1.0a (§4.7).
- ~~**DOAJ**~~ ✅ — réglé par #245 sans seconde intégration : `best_oa_location.source.is_in_doaj` d'OpenAlex donne le drapeau au passage.

**Court terme** (semaines)
- ~~**F1** — `openapi-typescript`~~ ✅ — dépendance et script `generate:api` en place dans `apps/frontend/package.json`.
- ~~**F4** — `POST /cards/{id}/restore`~~ ✅ — `cards.py:333`, vérifié en prod le 2026-08-03 (401 = route servie, auth requise).
- ~~**F2** — Tests d'intégration sur `POST /cards/{id}/publish`~~ ✅ — `tests/integration/test_publish.py` couvre le path qui a coûté 4 PRs en mai.
- ⚠️ Ces trois lignes traînaient comme « à faire » alors qu'elles étaient livrées. Vérifier l'état réel (grep + curl) **avant** de rouvrir un item de ce backlog.

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
