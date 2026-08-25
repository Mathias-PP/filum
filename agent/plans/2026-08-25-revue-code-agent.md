# Plan — Revue exhaustive du code Agent IA + documentation d'état

> **Statut : PROPOSÉ (non démarré).** Ce plan est conçu pour être exécutable par n'importe quel agent, en plusieurs sessions, sans jamais pouvoir « prétendre avoir lu » sans preuve mesurable.
>
> **Mécanisme central** : le plan est jalonné de **portes bloquantes (G0→G8)** — des boucles de vérification scriptées qui interdisent tout passage à la phase suivante tant que leurs conditions d'arrêt ne sont pas toutes remplies, preuve machine à l'appui (voir section « Les portes bloquantes »).
>
> **Objectif double :**
> 1. Passer au peigne fin **100 % du code lié à l'Agent IA** (backend, MCP, API, frontend, données, tests, workspace ICM) — aucune ligne oubliée, preuve à l'appui.
> 2. Produire une **documentation d'état exacte et datée**, découpée par domaine, routée depuis les points d'entrée du repo, servant ensuite de référence de suivi (base de comparaison lors des évolutions futures).

---

## Pourquoi ce plan existe

Les agents LLM déclarent couramment « lu » un fichier qu'ils n'ont que partiellement parcouru. Ce plan ne fait pas confiance à la déclaration : chaque étape de lecture produit une **preuve vérifiable par script**, et la documentation ne peut être écrite qu'au vu de cette preuve. La règle mère :

> **Règle zéro — interdiction d'écrire une ligne de doc sur un fichier avant d'avoir lu ce fichier en entier, et chaque affirmation doit porter une ancre `chemin:ligne`.**

---

## Périmètre (inventaire initial mesuré le 2026-08-25, commit `dae9cc0`)

À reconstruire mécaniquement en Phase 0 (c'est LA source de vérité, pas cette liste) :

| Domaine | Fichiers | ~LOC |
|---|---|---|
| Noyau backend (`app/services/agent*.py`, 9 fichiers dont `agent.py` 1074 l.) | 9 | ~3200 |
| Serveur MCP (`mcp_server/` : `tools.py` 258, `tools_write.py` 1876, `server.py`, `auth.py`, `schema_compat.py`) | 6 | ~2500 |
| Couche LLM (`services/llm.py` 715, `llm_adapters.py` 365) | 2 | ~1080 |
| Endpoints API (`api/v1/endpoints/agent_*.py`, 7 fichiers : chat SSE, providers, sessions, mode-gratuit, fiche, definitions, workspace) | 7 | ~900 |
| Schémas + modèles (`schemas/agent_*.py` ×3, `models/agent_*.py` ×4) | 7 | ~500 |
| Migrations agent (`040_agent_providers` → `052_lane_zai_secours`) | 8 | ~400 |
| Config (`core/config.py` — uniquement les réglages `agent_*`, `llm_*`) | 1 (partiel) | ~100 |
| Frontend lib (`lib/agent/conversation.ts`, `toolLabels.ts`, `markdown.ts`, `api/agent.ts`) | 4 | ~600 |
| Frontend UI (`components/chat/*.svelte` ×5 dont ChatPanel 1007 l., routes `dashboard/chat/+page.svelte` et `[id]/+page.svelte`, route `/dashboard/agents`) | ~9 | ~2600 |
| Tests backend (`test_agent*.py` ×10, `test_mcp*.py` ×5, `test_workspace_seed_sync.py`) | 16 | ~6400 |
| Workspace ICM consommé par l'agent (`workspaces/createur-de-fiches/` : 51 fichiers) + seed embarqué (`app/agent_workspace_seed/` 27 fichiers) | 78 | ~3000 |
| Scripts outillant le workspace (`app/scripts/build_workspace_seed.py`, `export_openapi.py`) | 2 | ~150 |
| **Total estimé** | **~80 fichiers** | **~21 400** |

**Exclusions explicites** (documentées comme telles, non passées au peigne fin) : moteur graphe hybride (`graph_memory.py`, revu PR #557), imports/exports de fiches, analytics. Les fonctions de ces modules **appelées par l'agent** sont documentées comme *interface* (signature + contrat), pas en interne.

⚠️ Le piège connu du nommage : tout fichier agent n'a pas « agent » dans son nom (ex. `schema_compat.py`, `llm_adapters.py`). D'où la fermeture par imports en Phase 0 — la liste ci-dessus est une amorce, pas une garantie.

**Correction G0 du 2026-08-25** : le comptage machine (fermeture d'imports comprise) donne **147 fichiers périmètre / 24 046 LOC** (+ 37 fichiers classés *interface*), soit ~12 % de plus que l'estimation manuelle ci-dessus — hors bande ±5 %, porte G0 restée rouge jusqu'à correction de la présente référence. Enseignement immédiat : l'inventaire estimé sous-comptait le lot 7 (workspace réel > 51 fichiers, tests d'intégration) et ignorait des dépendances directes (`app/agent_tools/`, `url_extractor.py`, `wayback.py`, `import_parsers.py`). La vérité de périmètre = `agent/audit/_core/inventaire.csv`, pas ce tableau.

---

## Phase 0 — Inventaire machine et carte de lecture (½ session)

Aucune lecture avant cette phase terminée.

1. Générer `_core/inventaire.csv` (destination : voir Phase 8 pour l'arborescence doc) via script, **pas à la main** :
   - `git ls-files` filtré par les patterns du tableau ci-dessus ;
   - **fermeture par imports** : partir des modules noyau, grep récursif des `import`/`from` pour attraper toute dépendance directe non nommée ; itérer jusqu'à point fixe ; classer chaque fichier trouvé en « périmètre » ou « interface seulement » ;
   - colonnes : `chemin, loc (wc -l), sha256, lot, statut(todo|lu|documente|verifie), symboles(grep count)`.
2. Extraire par fichier la liste des symboles (`grep -nE '^(def|class|async def) '` pour Python, composants/fonctions exportées pour TS/Svelte), stockée dans le CSV (colonne compte) — c'est la liste de contrôle fine qui rendra impossible une revue partielle.
3. Compter précisément les outils MCP exposés, les routes API agent, les événements SSE émis (grep `type.*:.*payload|yield.*event`), les variables d'environnement `AGENT_*`/`LLM_*` lues. Ces quatre totaux deviennent des **invariants chiffrés** que la doc finale doit retrouver exactement.
4. Geler le CSV en commit initial de la branche `docs/revue-agent`.

**Porte de sortie G0 (bloquante)** : `check_inventaire.sh` doit retourner zéro échec **deux fois de suite** — voir tableau des portes. Tant que G0 est rouge, AUCUNE ligne de code n'est lue. Les scripts de vérification (`check_inventaire.sh`, `check_lot.sh`, `spot_check.sh`) sont écrits et testés pendant cette phase : un vérificateur qui n'a jamais vu d'échec n'est pas un vérificateur, on le valide en lui faisant rater volontairement un fichier de contrôle.

---

## Les règles de lecture (anti-illusion, valables pour toutes les phases)

1. **Lecture intégrale obligatoire** : un fichier se lit du début à la fin en une ou deux commandes Read couvrant `1..wc -l`. La note de lecture enregistre « lu jusqu'à ligne {N} » où N = nombre de lignes du CSV. Un fichier > 2000 lignes se découpe explicitement en tranches listées dans la note.
2. **En-tête normalisé obligatoire** sur chaque note de fichier :
   ```
   ### <chemin relatif>
   Lu intégralement : oui (1074/1074 lignes) · sha256: ab12… · date: 2026-08-XX
   ```
3. **Liste des symboles exhaustive et cochée** : reprendre la liste greppée en Phase 0 ; pour CHACUN : ancre `fichier:ligne`, signature, description en une phrase, effets de bord (DB / réseau / état). Un symbole non traité = fichier non terminé, point final.
4. **Ancres obligatoires** : toute affirmation factuelle cite `chemin:ligne`. Toute chose non vérifiable à la lecture est marquée `⚠️à-vérifier`, jamais affirmée.
5. **Interdits** : se fier à sa mémoire des sessions précédentes, aux docs existantes (STATE.md, PITFALLS, commentaires du code) comme *sources* — elles servent d'hypothèses à confirmer par la lecture ; paraphraser un nom de fonction sans l'avoir vue ; « globalement ce fichier fait X ».
6. **Registre à jour après chaque fichier** : statut passe `todo→lu→documente→verifie` dans le CSV. Une session interrompue reprend là où le CSV s'arrête — le CSV est la mémoire, pas l'agent.
7. **Vérification de couverture par lot** (script `_core/check_coverage.sh`, écrit en Phase 0) : il échoue tant que (a) un fichier du lot n'est pas `documente`, (b) un symbole greppé n'apparaît pas dans la doc du domaine, (c) une ancre citée ne pointe pas une ligne existante. Aucun lot suivant ne démarre tant que le script n'est pas vert sur le lot courant.

---

## Les portes bloquantes (mécanisme central du plan)

Chaque phase est fermée par une **porte** (`G0`, `G1`…`G8`). Une porte est une **boucle de vérification qui bloque** : tant que ses conditions d'arrêt ne sont pas toutes remplies, la phase suivante est **interdite** — pas déconseillée, interdite. Le passage en force est traité comme un échec du plan, pas comme une avancée.

### L'algorithme de boucle (identique pour toutes les portes)

```
PORTE(P, vérificateur Vp):
  répéter
      1. lire le dernier rapport d'échec de Vp (liste objective des manques)
      2. travailler UNIQUEMENT ces manques (lecture complémentaire, doc à compléter…)
      3. ré-exécuter Vp À FRAIS depuis le disque (il recalcule tout, il ne fait pas confiance au CSV)
  jusqu'à Vp retourne ZÉRO échec lors de DEUX exécutions consécutives
  archiver le rapport vert horodaté dans _core/preuves/
```

Deux propriétés rendent la boucle infalsifiable :
- **Double vert obligatoire** : deux exécutions consécutives sans échec. Une seule passe verte peut être un hasard ; deux, rarement.
- **Le vérificateur recalcule tout** (LOC, sha256, symboles, ancres) depuis les fichiers réels. Tricher dans le CSV ou la doc est détecté au recalcul.

### Les conditions d'arrêt, porte par porte

| Porte | Vérificateur | Conditions d'arrêt (TOUTES obligatoires, sinon rebouclage) |
|---|---|---|
| **G0** fin Phase 0 | `check_inventaire.sh` | (a) fermeture par imports au point fixe : relancer l'analyse n'ajoute **aucun** fichier ; (b) tout fichier des patterns du périmètre figure au CSV ; (c) totaux LOC cohérents à ±5 % avec la mesure de référence ; (d) chaque ligne du CSV a `loc > 0`, un sha256 et un compte de symboles ; (e) les 4 invariants chiffrés (outils MCP, endpoints, événements SSE, vars env) posés et datés |
| **G1…G7** fin de chaque lot | `check_lot.sh <lot>` | (a) 100 % des fichiers du lot au statut `verifie` ; (b) **100 % des symboles greppés retrouvés dans la doc du domaine** (recherche textuelle du nom dans le dossier) ; (c) **chaque ancre `chemin:ligne` citée existe** (fichier présent, ligne ≤ wc -l actuel) ; (d) en-tête de lecture normalisé présent avec sha256 **courant** du fichier ; (e) ≥ 1 ancre par symbole documenté ; (f) invariants du lot == comptages machine de G0 |
| **sous-boucle spot-check** (dans G1…G7) | `spot_check.sh <lot>` | tirage **aléatoire seedé** de 3 ancres par fichier ; rouvrir le fichier à ces lignes ; toute affirmation contredite par le code réel → le fichier **retombe à `statut=lu`**, sa doc est réécrite, et la boucle G du lot **repart de zéro** |
| **G8** fin Phase 8 | `check_coverage.sh` | (a) rejeu **de tous les G1…G7** depuis le disque, tous verts ; (b) les 4 invariants de G0 retrouvés à l'identique dans la doc finale ; (c) tout lien de routage résout (AGENTS.md → audit CONTEXT.md → fiches) ; (d) spot-check global 10 % vert ; (e) test « agent frais » tracé : répondre à 5 questions piochées au hasard dans le CSV en ≤ 2 clics depuis AGENTS.md |

### Règles anti-contournement (valables pour toutes les portes)

1. **La sortie brute du vérificateur est collée** dans le journal de session à chaque itération (horodatée). Pas de rapport = pas de travail accompli, même si le travail est fait.
2. **Interdiction d'éditer le statut dans le CSV à la main** sans rapport vert joint ; de toute façon G8 recalcule tout — une statut mensonger explose tôt ou tard.
3. **Une porte rouge fige tout** : si après plusieurs itérations une condition s'avère impossible à remplir (ex. fichier illisible, invariant instable), le plan S'ARRÊTE et le blocage est remonté à l'utilisateur avec le rapport. On ne contourne pas, on ne « considère pas comme bon ».
4. **Dérogations** : seule chose dérogable = une **exclusion de périmètre** (découverte d'un fichier hors sujet), consignée dans `_core/exceptions.md` avec justification. Jamais une couverture partielle.
5. **Si le soupçon porte sur le vérificateur lui-même** (faux positifs massifs) : corriger le vérificateur d'abord, puis **rejouer toutes les portes déjà franchies** depuis leur dernier état vert. Un vérificateur amendé invalide ses verts antérieurs.
6. **Interruption de session** : au redémarrage, la première action est de rejouer la porte de la phase en cours AVANT tout nouveau travail — elle dit objectivement où on en est.

---

## Phases 1→7 — Les sept lots de lecture (un lot = une session max, un dossier doc)

Ordre choisi par dépendance (on lit les fondations avant leurs clients). Chaque lot produit un dossier de doc avec son propre `CONTEXT.md` routeur, et **se clôt exclusivement par sa porte** (G1 pour le lot 1 … G7 pour le lot 7) : voir tableau ci-dessus.

### Lot 1 — Fondations : config, données, transport LLM
`config.py` (partie agent/llm) · `models/agent_*.py` ×4 · migrations 040/042/045/046/047/049/051/052 · `services/llm.py` · `llm_adapters.py`.
Doc produite : schéma de données complet (tables, colonnes, contraintes, qui écrit quoi), tous les réglages env avec défauts réels et effet, chaîne de transport provider (alias, racines URL, classification d'erreurs).

### Lot 2 — Noyau : boucle, approbations, sessions
`services/agent.py` (1074 l., lecture en 2 tranches) · `agent_approvals.py` · `agent_sessions.py`.
Doc produite : cycle de vie d'un tour (SSE événements dans l'ordre réel d'émission), compaction, borne 48 tours + continuation, gestion d'approbation, persistance des messages, nettoyage d'historique multi-providers.

### Lot 3 — Outils MCP (le bras armé)
`mcp_server/server.py` · `auth.py` · `schema_compat.py` · `tools.py` · `tools_write.py` (1876 l., 2 tranches).
Doc produite : **catalogue exhaustif des outils** — un tableau par outil : nom, catégorie, arguments typés, effet DB, approbation requise oui/non, valeur retournée, pièges connus. Comptage final == invariant Phase 0 (attendu ~39).

### Lot 4 — Surface API : endpoints REST + SSE
7 fichiers `endpoints/agent_*.py` (+ leur montage dans le routeur v1).
Doc produite : une fiche par endpoint (méthode, chemin, auth, payload, réponse, erreurs), séquence SSE documentée événement par événement avec payloads exacts (source de vérité pour le front).

### Lot 5 — Services métier agent : providers, gratuit, discovery, definitions, fiche, workspace
`agent_providers.py` · `agent_gratuit.py` · `agent_discovery.py` · `agent_definitions.py` · `agent_fiche.py` · `agent_workspace.py`.
Doc produite : CRUD clés (chiffrement, masquage), lanes gratuites + rotation/cooldown + quotas, découverte, chargement des définitions YAML (contrats, outils autorisés, `quota_tours`), run ICM 7 étapes, workspace hébergé.

### Lot 6 — Frontend : lib + UI chat + routes
`lib/agent/*.ts` ×3 · `api/agent.ts` · `components/chat/*.svelte` ×5 · `routes/dashboard/chat/+page.svelte` + `[id]/+page.svelte` · route providers (`/dashboard/agents`).
Doc produite : mapping événement SSE → rendu UI (qui affiche quoi), labels d'outils (règles de `toolLabels.ts`), flux approbation, consentement gratuit, gestion d'erreurs visible utilisateur.

### Lot 7 — Garanties : tests + workspace ICM + état prod
16 fichiers de tests (lecture intégrale) · 51 fichiers `workspaces/createur-de-fiches/` · scripts `build_workspace_seed.py`.
Doc produite : **une ligne par test** — ce qu'il garantit en production (pas « teste X », mais « si tu casses Y, Z casse en prod ») ; structure ICM du workspace et cycle de vie du seed ; puis **vérification VM** : `curl` des endpoints publics, `docker logs`, `alembic current`, variables env effectives — la section « en production » de la doc décrit le monde réel, pas le code supposé.

---

## Phase 8 — Assemblage, routage, preuve finale (1 session)

### Arborescence doc cible (conventions ICM respectées : routeur CONTEXT.md par dossier, `_core/` outil, `shared/` transversal)

```
agent/audit/
  CONTEXT.md                  ← routeur : comment naviguer, tableau de bord d'avancement, date de gel
  _core/
    inventaire.csv            ← manifeste machine (chemin, LOC, sha256, statut)
    check_coverage.sh         ← preuve de couverture rejouable
  shared/
    evenements-sse.md         ← référence transversale : contrat SSE complet
    variables-env.md          ← toutes les vars agent/llm, défauts, effets
    catalogue-outils-mcp.md   ← les ~39 outils, tableau maître
  01-fondations/CONTEXT.md + fiches
  02-noyau/CONTEXT.md + fiches
  03-outils-mcp/CONTEXT.md
  04-api/CONTEXT.md
  05-services-metier/CONTEXT.md
  06-interface-chat/CONTEXT.md
  07-tests-et-prod/CONTEXT.md
```

Chaque `CONTEXT.md` suit le même gabarit : rôle du domaine, liste des fichiers avec lien vers leur fiche, invariants chiffrés, dettes/pièges constatés **à la lecture** (différence avec PITFALLS : ici c'est l'état, pas l'histoire).

### Routage (pour que tout agent arrivant trouve)

1. `AGENTS.md` racine : nouvelle ligne dans la table « Où aller selon la question » → « Comment marche l'Agent IA, fichier par fichier ? → `agent/audit/CONTEXT.md` ».
2. `agent/README.md` (index du système agent) : entrée vers l'audit.
3. `STATE.md` : entrée de session à la livraison (date, commit de gel, chiffres de couverture).

### Preuve finale d'infaillibilité (DoD mesurable — c'est la porte G8, bloquante)

- [ ] **G8 vert deux fois de suite** : rejeu depuis le disque de TOUS les G1…G7 (100 % fichiers `verifie`, 100 % symboles documentés, toutes ancres résolues, en-têtes sha256 valides)
- [ ] Invariants Phase 0 retrouvés dans la doc : nb d'outils MCP, nb d'endpoints, nb d'événements SSE, nb de vars env — identiques au comptage machine
- [ ] Spot-check anti-fraude : 10 % des fichiers tirés au hasard (seed datée), 3 ancres vérifiées par fichier — zéro contradiction avec le code réel ; une seule contradiction = retour au lot concerné et G8 repart de zéro
- [ ] Test d'usage : un agent « frais » répond à 5 questions piochées au hasard dans le CSV en ≤ 2 clics depuis AGENTS.md (trace conservée)
- [ ] Livraison : PR unique `docs/revue-exhaustive-agent` (+ mention dans STATE.md). Le CSV gèle l'état à date : toute évolution future relance `check_coverage.sh` et voit immédiatement ce qui a dérivé

---

## État courant

> Rappel mécanique : une case n'est cochée que si la porte associée est **verte deux fois de suite**, rapport horodaté archivé dans `_core/preuves/`. Aucun autre critère de cochage n'existe.

- [x] Phase 0 : inventaire machine + CSV + vérificateurs écrits et validés (faux échec provoqué) — **Porte G0 VERTE** le 2026-08-25 : 184 fichiers / 24 042 LOC périmètre, invariants gelés (43 outils · 31 endpoints · 12 SSE · 15 vars env), double vert + test anti-fraude + smoke-tests des portes G1-G7 bloquantes. Correction de la référence du plan (estimation manuelle 21 400 LOC sous-évaluée de ~12 % — voir note « Correction G0 »)
- [ ] Lot 1 fondations → `01-fondations/` — **Porte G1 + spot-check**
- [ ] Lot 2 noyau → `02-noyau/` — **Porte G2 + spot-check**
- [ ] Lot 3 outils MCP → `03-outils-mcp/` — **Porte G3 + spot-check** (invariant nb d'outils)
- [ ] Lot 4 API → `04-api/` — **Porte G4 + spot-check** (invariants endpoints + SSE)
- [ ] Lot 5 services métier → `05-services-metier/` — **Porte G5 + spot-check**
- [ ] Lot 6 frontend → `06-interface-chat/` — **Porte G6 + spot-check**
- [ ] Lot 7 tests + workspace + prod → `07-tests-et-prod/` — **Porte G7 + spot-check**
- [ ] Phase 8 : assemblage, routage AGENTS.md/README/STATE — **Porte G8 (rejeu global)**

*Estimation : 8-9 sessions de travail concentré (~21 k lignes à lire intégralement + rédaction). Chaque case ci-dessus n'est cochée que si sa preuve de couverture est verte.*
