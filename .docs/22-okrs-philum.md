# 22 — OKR Philum : objectifs, résultats clés, et mapping agent/tools

> Arbre OKR complet du projet Philum, avec pour chaque résultat clé les outils MCP, workflows, et composants techniques qui le livrent. Document vivant — mis à jour à chaque pivot d'objectif.

---

## North Star

> **Ce qu'HTTPS est à la confidentialité, Philum doit l'être à la provenance.**
> Devenir, à horizon 5-10 ans, la couche standard de citation du web.
>
> Deuxièmement : **un espace de travail où chaque créateur possède son corpus de sources vérifiées et peut interroger l'IA avec 100% du contexte qu'il contrôle.** Philum n'est pas seulement un label de qualité — c'est un environnement de recherche documentaire en ligne, boosté à l'IA si on le souhaite, où la chaîne documentaire de chaque citation est vérifiable.

---

## O1 — Prouver que les créateurs sourceurs veulent une bibliographie augmentée

*Hypothèse MVP : « Les vulgarisateurs scientifiques ET les journalistes trouvent suffisamment de valeur dans une bibliographie augmentée pour l'utiliser activement et la partager. »*

*Contexte : à l'ère de l'IA générative, des deepfakes et de l'ingérence informationnelle, faciliter l'accès aux sources vérifiées est un acte noble. Philum rend ce travail visible, vérifiable et défendable — la valeur doit être perceptible en quelques secondes.*

### KR1.1 — 3 créateurs actifs (vulgarisateurs + journalistes) dans le premier mois

#### OKR1.1.1 — Avoir une fiche fonctionnelle de bout en bout

Le parcours complet `create_card` → `add_source` → `add_excerpt` → `publish_card` doit Aboutir à une fiche publique sans erreur.

| Résultat clé | Outil(s) MCP | Workflow | Composant |
|---|---|---|---|
| Le flow « vidéo YouTube » Aboutit à une fiche publiée | `get_youtube_transcript` → `create_card` → `set_content_text` → `import_from_content_url` → `add_source` → `add_excerpt` → `verify_excerpts` → `publish_card` | Workflow A (`06-capabilities-workflows.md`) | `tools_write.py` + `agent_fiche.py` |
| Le flow « bibliographie texte » Aboutit à une fiche publiée | `parse_biblio` → `create_card` → `add_source` → `add_excerpt` → `publish_card` | Workflow B | `tools_write.py` + `parse_biblio` |
| L'agent LLM crée une fiche sans intervention humaine | Tous les outils via le workspace ICM 7 étages | `agent_fiche.py` ETAPES | `agent.py` boucle + `server.py` |
| Les enums sont validés à l'entrée (leçon créatine) | `_valeur_enum` sur `add_source`, `update_source` | — | `tools_write.py:60` |
| Le slug est unique par créateur | `create_card` vérifie l'unicité | — | `tools_write.py:176` |
| La dédup de source fonctionne par DOI/URL | `_identite` + `_identites_deja_citees` | — | `tools_write.py:134-143` |

**Pièges documentés** (`agent/PITFALLS.md`):
- §1.3 : le payload signé est immuable — tout changement nécessite un ADR
- §2.1 : les enums invalides s'inscrivent sans erreur mais cassent la relecture
- §3.5 : prettier --check strict sur le frontend

#### OKR1.1.2 — La fiche est belle et exploitable

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le graphe D3.js affiche les sources et leurs connexions | `get_card` rend `linked_card` par source | `AgentMarkdown.svelte` + `ChatPanel.svelte` |
| Les stats de sources sont visibles (nombre, types, peer-reviewed) | `get_my_card` rend `excerpts_verified` / `excerpts_unreadable` par source | `ToolCard.svelte` |
| Le rendu markdown est sans `{@html}` (XSS-safe) | — | `AgentMarkdown.svelte` (marked.parse + re-échappage) |
| Le responsive mobile fonctionne | — | Tailwind CSS, < 200 KB gzipped |
| Les extraits verbatim sont affichés avec leur source | `get_source` (seul outil qui rend le texte des extraits) | `ToolCard.svelte` |

#### OKR1.1.3 — La fiche est défendable

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le banner d'authenticité est compréhensible en 5 secondes | — | Page publique SSR (`agent_fiche.py` + SvelteKit) |
| L'attestation Ed25519 est vérifiable par un tiers sans le serveur | `verify_attestation` rend `valid` + raison | `tools_write.py:1611` |
| Le contenu est archivé avec un timestamp | `archive_sources` déclenche le worker Wayback | `agent_workspace.py` + Wayback API |
| La signature couvre le triplet prouvé | `create_content_attestation` signe `(creator_id, content_url, attested_at)` | `tools_write.py:1564`, ADR-019 |

**Ce que Philum PEUT prouver** (ADR-019-bis):
- À date T, compte C (contrôlant le canal K) a déclaré être l'auteur du contenu à l'URL U
- Trois éléments indépendamment vérifiables : date, contrôle du canal, déclaration

**Ce que Philum NE PEUT PAS prouver**:
- Que le contenu est authentique/non modifié/sans IA
- Que le déclarant est l'auteur intellectuel (seulement le contrôleur du canal)
- Que le contenu non attesté est faux

---

### KR1.2 — Le créateur partage sa fiche sur au moins un canal public

#### OKR1.2.1 — Le partage est naturel

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| OpenGraph affiche une preview riche sur X, Bluesky, Slack | — | SSR + meta tags (`agent_fiche.py`) |
| Le lien `/@pseudo/slug` est stable et ne casse pas | `update_card` : slug immuable | `tools_write.py:609` |
| La fiche peut être exportée en JSON, BibTeX, RIS, CSL-JSON, CSV, XLSX, Markdown, DOCX | `get_card` + `get_source` → exports | Endpoints REST + frontend |

#### OKR1.2.2 — Le créateur a un intérêt à partager

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le profil créateur est présentable | `list_my_cards` rend les fiches de l'utilisateur | Page `/@pseudo` SSR |
| Le créateur peut gérer ses fiches depuis le dashboard | `list_my_cards`, `get_my_card`, `update_card`, `delete_card` | `agents/+page.svelte` |
| Les données sont exportables (portabilité) | `get_card` + `get_source` → multi-format exports | `agent.ts` client API |

---

### KR1.3 — Le coût d'entrée est zéro pour les créateurs individuels

#### OKR1.3.1 — L'authentification est simple

| Résultat clé | Composant |
|---|---|
| Google OAuth en 1 clic | `authlib`, scope `openid email profile` |
| Pas de formulaire long | Inscription → première fiche < 5 min |

#### OKR1.3.2 — Le mode gratuit est généreux

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Unlimited signing, unlimited sources, free archival | `create_content_attestation`, `add_source`, `archive_sources` | — |
| Pas de paywall sur les fonctionnalités core | Vérifiable dans le code : pas de condition付费 sur les outils read/write | `tools.py` + `tools_write.py` |
| Le free tier est documenté | — | `BUSINESS-PLAN.md` section monetization |

#### OKR1.3.3 — L'agent LLM est accessible sans clé API

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Mode gratuit avec lanes serveur (Z.ai GLM) | Tous les outils via l'agent | `agent_gratuit.py` + `agent.py` |
| Rotation auto sur rate-limit | — | Cooldown 10 min, lane secours `zai-alt` |
| Le consentement est versionné | — | `agent_gratuit_consents` table |
| L'agent fonctionne avec la clé du créateur (BYOK) | Tous les outils | `agent_providers.py` + AES-GCM encryption |

**Outils MCP impliqués dans O1** : `create_card`, `add_source`, `add_excerpt`, `set_content_text`, `publish_card`, `update_card`, `get_youtube_transcript`, `import_from_content_url`, `parse_biblio`, `suggest_excerpts`, `annotate_excerpt`, `chunk_text`, `verify_excerpts`, `create_content_attestation`, `archive_sources`, `get_my_card`, `list_my_cards`, `get_card`, `get_source`, `list_sources`, `search_my_excerpts`, `update_source`, `delete_source`, `update_excerpt`, `delete_excerpt`

---

## O2 — Prouver que le public clique et explore les fiches

*Hypothèse MVP : « Leur audience clique sur les liens Philum et passe du temps à explorer la carte. »*

*Valeur défensive : face à l'ingérence informationnelle et aux deepfakes, Philum offre un signal objectif intermédiaire — pas un verdict de vérité, mais une preuve que le créateur a sourcé son travail et en assume la chaîne documentaire. Le lecteur peut vérifier en 5 secondes.*

### KR2.1 — 100 vues cumulées sur les fiches publiques en 30 jours

#### OKR2.1.1 — Les fiches sont indexées et trouvables

| Résultat clé | Composant |
|---|---|
| SSR produce des pages crawlables | SvelteKit SSR (`+page.server.ts`) |
| Schema.org/JSON-LD est valide | Meta tags dans la page publique |
| Le sitemap est soumis | `sitemap.xml` généré |

#### OKR2.1.2 — Le taux de rebond est faible

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le graphe est interactif et incite à cliquer | `get_card` rend les sources avec `linked_card` | D3.js, hover/clic/zoom |
| Les liens inter-fiches fonctionnent | `find_cards_citing` résout les variantes d'URL | `tools.py:214` |
| Le lecteur peut voir les extraits verbatim | `get_source` (seul outil qui rend le texte) | Page source publique |

---

### KR2.2 — Le lecteur comprend la valeur en < 10 secondes

#### OKR2.2.1 — La page est auto-explicative

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Titre + description + stats visibles sans scroll | `get_card` rend titre, description, sources | Above-the-fold SSR |
| Les sources sont triées par type et autorité | `list_sources` rend dans l'ordre d'affichage | `tools_write.py:1220` |
| Chaque source montre sa stance et son category | `add_source` validate les enums | `_valeur_enum` |

#### OKR2.2.2 — La confiance est établie

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le banner d'authenticité est visible | `create_content_attestation` → badge | Page publique |
| Les extraits verbatim sont cités avec leur source | `get_source` rend extraits + `verify_excerpts` rend verdicts | `ToolCard.svelte` |
| L'archivage est visible | `archive_sources` → `archive_url` sur la source | Banner « Archived at Wayback » |

---

## O3 — Garantir que la preuve cryptographique a de la valeur

### KR3.1 — L'attestation est techniquement robuste

#### OKR3.1.1 — Le payload signé est immuable

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le payload `(creator_id, content_url, attested_at)` ne change jamais | `create_content_attestation` | `tools_write.py:1564`, ADR-019 |
| Tout ajout/suppression de champ nécessite un ADR + plan de ré-attestation | — | `agent/PITFALLS.md` §1.3 |
| La signature est vérifiable sans le serveur | `verify_attestation` | Ed25519 via `cryptography` |

#### OKR3.1.2 — Les clés privées sont sûres

| Résultat clé | Composant |
|---|---|
| AES-GCM + master key en env var | `app/crypto/` |
| Pas de clé en clair dans la DB | Clés résolues depuis les env vars au runtime |
| Rotation des clés prévue (phase 2) | ADR-019, `BUSINESS-PLAN.md` |

---

### KR3.2 — L'archivage est fiable et traçable

#### OKR3.2.1 — Chaque source est archivée avec un timestamp

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| L'URL d'archivage est stockée sur la source | `add_source` pose `archive_status` | `Source.archive_url` + `Source.archive_status` |
| L'archivage est relancé en cas d'échec | `archive_sources` déclenche le worker | `wayback.py` + `asyncio.create_task` |
| Le worker Wayback tourne en background | — | Background task (fragilité connue : perdue au restart) |

#### OKR3.2.2 — L'archivage multi-cible est en place (phase 3+)

| Résultat clé | Composant |
|---|---|
| Wayback + Archive.today + Playwright | Worker multi-cible |
| Le fallback est automatique | Si Wayback échoue, le deuxième essaie |

---

### KR3.3 — Le registre public est always-open

#### OKR3.3.1 — Les attestations sont lisibles par tous

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Pas d'auth requise pour lire/verifier | `get_attestation`, `verify_attestation` | Endpoints publics sans JWT |
| Le registre est un bien commun | — | `BUSINESS-PLAN.md` : jamais de paywall sur la lecture |

#### OKR3.3.2 — Le registre est un bien commun

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| L'API publique est documentée et stable | `search_cards`, `get_card`, `get_source`, `find_cards_citing`, `whoami` | `tools.py` + OpenAPI |
| Pas de breaking changes sans versioning | — | `/api/v1/` prefix |

---

## O4 — Construire une infrastructure fiable et scalabe

### KR4.1 — Zéro downtime en production

#### OKR4.1.1 — Le health check est toujours vert

| Résultat clé | Composant |
|---|---|
| `/health` OK depuis l'extérieur | FastAPI health endpoint |
| Le conteneur redémarre sans perte de données | Supabase Postgres externe |
| Les migrations Alembic sont non-destructives | `alembic/versions/` (040→052) |

#### OKR4.1.2 — Le rate limiting protège l'API

| Résultat clé | Composant |
|---|---|
| slowapi sur les routes sensibles | `agent_chat.py`, `agent_sessions.py` |
| 60 req/min sur la route publique MCP | `server.py` rate limit |
| Caddy TLS en front | Reverse proxy Caddy |

---

### KR4.2 — La couverture de tests est > 95%

#### OKR4.2.1 — Les tests sont verts en CI

| Résultat clé | Composant |
|---|---|
| 16 jobs CI, tous verts avant merge | GitHub Actions |
| Branch protection | Pas de merge sans CI verte |
| ~1400 tests pytest | `apps/backend/tests/` |
| vitest frontend | `apps/frontend/` |

#### OKR4.2.2 — Les tests couvrent les edge cases

| Résultat clé | Test(s) | Composant |
|---|---|---|
| Bornes dures testées | `test_borne_max_tours` | `agent.py` |
| Boucle complète testée | `test_agent_loop` (14 classes, 15+ scénarios) | `agent.py` |
| Enums invalides bloqués | `test_valeur_enum` | `tools_write.py` |
| Auth testée | `test_mcp_auth.py`, `test_mcp_mount.py` | `auth.py` |
| Sessions persistées | `test_agent_sessions.py` | `agent_sessions.py` |
| Discovery + quota | `test_agent_discovery.py` | `agent_discovery.py` |
| Workspace isolation | `test_agent_tools.py` | `agent_workspace.py` |

---

### KR4.3 — La sécurité est vérifiée automatiquement

#### OKR4.3.1 — Les dépendances sont analysées

| Résultat clé | Outil |
|---|---|
| Pas de CVE critique non traité | Trivy (container), Safety (Python), Bandit (Python SAST) |
| Pas de secret en commit | TruffleHog (CI) |
| Bandit High/Medium = fail CI | `agent/SECURITY.md` |

#### OKR4.3.2 — L'auth est testée

| Résultat clé | Test(s) |
|---|---|
| Pas de bypass d'auth possible | Tests 401 sur toutes les routes protégées |
| Tokens expirés rejetés | `test_mcp_auth.py` |
| OAuth flow complet | `test_agent_providers_api.py` |

---

## O5 — Monétiser sans trahir les principes

### KR5.1 — Le core reste gratuit pour les créateurs individuels

#### OKR5.1.1 — Le free tier est clair

| Résultat clé | Outil(s) MCP |
|---|---|
| Création, sources, extraits, signatures = gratuit | `create_card`, `add_source`, `add_excerpt`, `create_content_attestation` |
| Pas de paywall sur les fonctionnalités core | Vérifiable : aucun gate付费 dans `tools_write.py` |
| Le seuil « généreux » est défini | Nombre de fiches/mois, nombre de sources/fiche (à définir, `07-open-questions.md` Q2) |

#### OKR5.1.2 — La monétisation est sur les features premium

| Feature premium | Description |
|---|---|
| Analytics de trafic défensif | « Combien de fois ton lien Philum a été cliqué en réponse à une contestation » |
| Archival avancé (multi-cible, Puppeteer) | Wayback gratuit, archivage premium avec Playwright |
| Alertes (nouvelles citations, changements) | `list_incoming_citations`, `mark_citations_seen` |
| API « Citation & Metadata » self-serve | `search_cards`, `get_card`, `get_source`, `find_cards_citing` |
| Philum Pro (8-12 EUR/mois) | Toutes les features premium |

---

### KR5.2 — Le modèle est viable à 1 000 EUR/mois net

#### OKR5.2.1 — Les coûts sont maîtrisés

| Poste | Coût |
|---|---|
| VM GCP e2-micro | 0 EUR (always-free) |
| Supabase Postgres | 0 EUR (free tier) |
| Vercel frontend | 0 EUR (free tier) |
| Domaine + TLS | ~1 EUR/mois |
| **Total** | **< 5 EUR/mois** |

#### OKR5.2.2 — Les revenus viennent de sources diversifiées

| Source | Priorité | Outil(s) MCP impliqué(s) |
|---|---|---|
| API self-serve « Citation & Metadata » | P1 | `search_cards`, `get_card`, `get_source`, `find_cards_citing` |
| MCP server (distribution API) | P1 bis | Tous les 45 outils |
| Philum Pro freemium | P2 | Analytics, alertes, archival avancé |
| Organisations (DSA/AI Act compliance) | P3 | API dédiée, dashboard |

---

### KR5.3 — L'indépendance est préservée

| Résultat clé | Composant |
|---|---|
| Pas de VC | Financement par grants (NLnet ~50K EUR) + revenus |
| La fondation détient le protocole | Modèle Mozilla : fondation + société |
| Le registre public est un bien commun | Jamais de paywall sur la lecture des attestations |

---

## O6 — Adopter et faire adopter le format

### KR6.1 — Le format est utilisé par d'autres outils

#### OKR6.1.1 — Le MCP server est opérationnel

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| 45 outils, API stable | Tous les outils | `server.py` |
| Un agent LLM peut lire les fiches via MCP | `search_cards`, `get_card`, `get_source`, `find_cards_citing` | `tools.py` |
| Un agent LLM peut créer/modifier des fiches via MCP | `create_card`, `add_source`, `add_excerpt`, `publish_card` | `tools_write.py` |
| Le MCP est documenté et testé | — | 1400+ tests, OpenAPI |

#### OKR6.1.2 — L'extension navigateur fonctionne

| Résultat clé | Composant |
|---|---|
| One-click source addition | `apps/extension/` (MV3) |
| L'extension ajoute des sources via `add_source` | MCP bridge |

---

### KR6.2 — Le format est compatible avec les standards

#### OKR6.2.1 — Le JSON-LD est valide

| Résultat clé | Composant |
|---|---|
| Schema.org compatible | Meta tags SSR |
| Les fiches sont lisibles par les crawlers | Google Rich Results |

#### OKR6.2.2 — Le format est C2PA-compatible

| Résultat clé | Composant |
|---|---|
| Le payload signé suit le standard C2PA | Ed25519 + SHA-256 |
| Pas besoin d'adhésion au consortium | Usage libre du standard (~10K EUR/an pour l'adhésion, phase 3+) |

---

### KR6.3 — Le graphe de connaissances grandit

#### OKR6.3.1 — Les liens inter-fiches se créent automatiquement

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| `linked_card` résolu via `find_cards_citing` | `find_cards_citing` normalise les variantes d'URL | `tools.py:214` |
| Le graphe est visualisable | `get_card` rend les sources avec `linked_card` | D3.js |
| Le graphe est navigable | Clic sur un nœud → fiche source | SvelteKit routing |

#### OKR6.3.2 — Le mécanisme Seed & Claim fonctionne

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Les fiches auto-générées sont créées | `create_card` (seed, sans propriétaire) | `PLAN-ACQUISITION.md` |
| Les créateurs revendent leurs fiches | `create_claim_request` → transfert admin | `tools_write.py:1806` |
| Le taux de revendication est mesuré | — | Dashboard admin |

---

## O7 — Garantir la souveraineté et la conformité

### KR7.1 — Les données sont en Europe

| Résultat clé | Composant |
|---|---|
| GCP europe-west + Supabase EU | Infra prod |
| Pas de transfert hors UE | Vérifiable dans la config |
| Pas de cookie sans consentement | Audit cookies |

### KR7.2 — Le framework légal est anticipé

| Résultat clé | Composant |
|---|---|
| Pas de label « vérifié » ou « certifié » | UI review — `ADR-019-bis` interdit ces termes |
| Les limitations sont claires | Banner d'authenticité = déclaration, pas garantie |
| La procédure de contestation est documentée | ADR-019-bis : claimed → contested → arbitrated |

---

## O8 — Construire un produit technique solide

### KR8.1 — Le code est maintenable

| Résultat clé | Composant |
|---|---|
| 192 fichiers documentés avec ancres `chemin:ligne` | `agent/audit/` (G0→G8 vert) |
| 43 outils MCP, 31 endpoints, 12 SSE, 15 env vars gelés | `_core/invariants.txt` |
| Chaque ADR a un plan de ré-attestation | `DECISIONS.md` |

---

### KR8.2 — Le LLM est un outil, pas un oracle

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le LLM propose, la crypto dispose | `suggest_excerpts` → `add_excerpt` → `verify_excerpts` | Chaîne LLM → validation |
| Pas de sortie LLM dans un payload signé sans validation | `_valeur_enum`, `verify_excerpts` | `tools_write.py` |
| La cascade de modèles gratuits fonctionne | — | `agent_gratuit.py` : Gemini → Mistral → GLM |
| Pas de panic si un modèle tombe | — | Rotation auto + cooldown |

---

### KR8.3 — L'agent IA est fiable

#### OKR8.3.1 — L'agent ne fait pas n'importe quoi

| Résultat clé | Composant |
|---|---|
| Bornes de tours : 48 max | `agent_max_tours=48`, compaction au lieu d'erreur |
| 6 outils sont approuvés (approval humaine) | `publish_card`, `delete_source`, `delete_excerpt`, `create_content_attestation`, `archive_sources`, `delete_card` |
| L'agent ne fabrique pas de sources | `_valeur_enum` valide les enums, `add_excerpt` relit la page |
| L'agent ne signe pas sans accord | `create_content_attestation` est dans `est_sensible` |

#### OKR8.3.2 — L'agent est BYOK

| Résultat clé | Composant |
|---|---|
| Les clés API sont chiffrées AES-GCM | `agent_providers.py` |
| L'agent fonctionne sans clé (mode gratuit) | `agent_gratuit.py` + lanes serveur |
| La rotation est automatique sur rate-limit | Cooldown 10 min, lane secours |

#### OKR8.3.3 — L'agent a une mémoire de graphe

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| `recall_memory` interroge le graphe en ~2ms | `recall_memory` (STARTER) | SQL pur, pas de LLM |
| `rebuild_graph` reconstruit déterministiquement | `rebuild_graph` (STARTER) | Pas de LLM, pas de coût |
| Le graphe est isolé par créateur | `recall_memory` scope par user | `tools_write.py` |

---

## O9 — Posséder son corpus et interroger l'IA avec un contexte maîtrisé

*Philum n'est pas seulement un label de qualité — c'est un espace de travail pour mener des recherches documentaires en ligne et construire sa bibliographie, boosté à l'IA si on le souhaite. La valeur : posséder un corpus de sources vérifiées avec citations, et pouvoir interroger une IA en maîtrisant 100% du contexte.*

### KR9.1 — Le créateur construit un corpus de sources vérifiées

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le créateur peut rassembler des sources depuis différents contenus | `create_card` × N (une fiche par contenu source) | `tools_write.py` |
| Chaque source a ses extraits verbatim vérifiés | `add_excerpt` → `verify_excerpts` | `tools_write.py:424` + `:895` |
| Les sources sont organisées par type et autorité | `add_source` avec `category`, `author_kind`, `stance` | `_valeur_enum` |
| Le créateur peut chercher dans tout son corpus | `search_my_excerpts` (full-text dans ses extraits) | `tools_write.py:1254` |
| Le créateur peut lister et naviguer ses fiches | `list_my_cards`, `get_my_card`, `list_sources` | `tools_write.py:1182-1220` |

#### OKR9.1.1 — Le corpus est structuré et navigable

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Les fiches sont liées entre elles quand elles citent les mêmes sources | `find_cards_citing` + `list_connections` + `confirm_connection` | `tools.py:214` + `tools_write.py:1056` |
| Le graphe personnel du créateur est visualisable | `get_card` rend `linked_card` | D3.js |
| Les connexions inter-fiches sont confirmées ou retirées | `confirm_connection`, `remove_connection` | `tools_write.py:1056-1087` |

#### OKR9.1.2 — Le corpus est exportable et portable

| Résultat clé | Composant |
|---|---|
| Export multi-format : JSON, BibTeX, RIS, CSL-JSON, CSV, XLSX, Markdown, DOCX | Endpoints REST + frontend |
| Le créateur possède ses données (pas de lock-in) | `get_card` + `get_source` → exports complets |

---

### KR9.2 — Le créateur peut interroger l'IA sur son corpus

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| L'agent LLM a accès à toutes les sources du créateur | `list_my_cards`, `get_my_card`, `list_sources`, `get_source` | `tools_write.py` |
| L'agent peut chercher dans le corpus du créateur | `search_my_excerpts`, `search_cards` | `tools_write.py:1254` + `tools.py:58` |
| L'agent peut interroger le graphe de connaissances | `recall_memory` (STARTER) | SQL pur, ~2ms |
| Les réponses de l'agent sont ancrées dans les sources vérifiées | L'agent utilise `get_source` pour obtenir les extraits verbatim avant de répondre | `agent.py` boucle |
| Le créateur peut choisir son modèle LLM (BYOK ou gratuit) | `agent_providers.py` (BYOK) + `agent_gratuit.py` (gratuit) | Lanes serveur |

#### OKR9.2.1 — L'agent est un assistant de recherche, pas un générateur

| Résultat clé | Principe | Composant |
|---|---|---|
| L'agent ne fabrique jamais de sources | « LLM propose, crypto dispose » | `add_excerpt` relit la page, `_valeur_enum` valide |
| L'agent cite toujours ses sources | Chaque réponse renvoie aux fiches/extraits utilisés | `agent.py` + `ToolCard.svelte` |
| L'agent peut résumer, comparer, et synthétiser à partir du corpus | `get_source` → texte → raisonnement LLM | `agent.py` boucle |
| L'agent refuse de répondre hors de son corpus | Si pas de source → il le dit, il n'invente pas | `agent.py` + `web_search` optionnel |

#### OKR9.2.2 — Le mode gratuit rend l'agent accessible à tous

| Résultat clé | Composant |
|---|---|
| Un créateur peut dialoguer avec l'agent sans clé API | `AGENT_GRATUIT_ENABLED=true` + consentement |
| La rotation de modèles gratuits est automatique | Cooldown 10 min, lane secours `zai-alt` |
| Le créateur peut upgrader vers un modèle payant (BYOK) | `agent_providers.py` + AES-GCM encryption |

---

### KR9.3 — Le workspace de recherche est un vrai lieu de travail

| Résultat clé | Outil(s) MCP | Composant |
|---|---|---|
| Le créateur peut structurer ses recherches par fiche | `create_card` (card_kind="sujet" pour les recherches en cours) | `tools_write.py:176` |
| Le créateur peut annoter ses sources | `update_source` (annotation, stance, is_pivot) | `tools_write.py:709` |
| Le créateur peut extraire du contenu depuis une URL | `import_from_content_url`, `get_url_metadata`, `get_youtube_transcript` | `tools_write.py:1515-1488` |
| Le créateur peut parser du texte bibliographique | `parse_biblio` (BibTeX, CSL, markdown, texte libre) | `tools_write.py:1841` |
| Le workspace ICM structure les recherches par étapes | 7 étages : brief → sources → annotations → extraits → connexions → relecture → publication | `agent_fiche.py` ETAPES |

#### OKR9.3.1 — Le workspace est persistant et reprendable

| Résultat clé | Composant |
|---|---|
| Les fiches sont sauvegardées en base | `biblio_card` + `source` + `source_excerpt` tables |
| L'historique de l'agent est persisté | `agent_sessions` table, append-only |
| Le créateur peut reprendre une session interrompue | `GET /agent/sessions/{id}` + rejeu |
| Le workspace ICM persiste entre les sessions | `agent_workspace` table + workspace files |

#### OKR9.3.2 — Le workspace est partageable (phase 3+)

| Résultat clé | Composant |
|---|---|
| Le créateur peut partager son corpus avec des collaborateurs | Visibility settings sur les fiches |
| Le créateur peut exporter son workspace complet | Export multi-format |
| Le corpus peut être consulté en lecture seule par d'autres | Fiches publiques + `get_card` |

---

**Outils MCP impliqués dans O9** : `create_card`, `add_source`, `add_excerpt`, `set_content_text`, `publish_card`, `update_card`, `update_source`, `get_my_card`, `list_my_cards`, `get_card`, `get_source`, `list_sources`, `search_my_excerpts`, `search_cards`, `find_cards_citing`, `list_connections`, `confirm_connection`, `remove_connection`, `import_from_content_url`, `get_url_metadata`, `get_youtube_transcript`, `parse_biblio`, `chunk_text`, `suggest_excerpts`, `annotate_excerpt`, `verify_excerpts`, `recall_memory`, `rebuild_graph`

---

## Matrice de couverture — Outils MCP × Objectifs

| Outil | O1 | O2 | O3 | O4 | O5 | O6 | O7 | O8 | O9 |
|---|---|---|---|---|---|---|---|---|---|
| `search_cards` | · | ✓ | · | · | ✓ | ✓ | · | · | ✓ |
| `get_card` | ✓ | ✓ | · | · | · | ✓ | · | · | ✓ |
| `get_source` | ✓ | ✓ | · | · | · | ✓ | · | · | ✓ |
| `find_cards_citing` | · | ✓ | · | · | · | ✓ | · | · | ✓ |
| `whoami` | · | · | · | · | · | · | · | · | · |
| `create_card` | ✓ | · | · | · | ✓ | ✓ | · | · | ✓ |
| `add_source` | ✓ | · | · | · | ✓ | · | · | · | ✓ |
| `add_excerpt` | ✓ | · | · | · | ✓ | · | · | · | ✓ |
| `set_content_text` | ✓ | · | · | · | · | · | · | · | ✓ |
| `publish_card` | ✓ | · | · | · | ✓ | · | · | · | ✓ |
| `update_card` | ✓ | · | · | · | · | · | · | · | ✓ |
| `update_source` | ✓ | · | · | · | · | · | · | · | ✓ |
| `delete_source` | ✓ | · | · | · | · | · | · | ✓ | ✓ |
| `delete_excerpt` | ✓ | · | · | · | · | · | · | ✓ | ✓ |
| `update_excerpt` | ✓ | · | · | · | · | · | · | · | ✓ |
| `verify_excerpts` | ✓ | ✓ | ✓ | · | · | · | · | ✓ | ✓ |
| `suggest_excerpts` | ✓ | · | · | · | · | · | · | ✓ | ✓ |
| `annotate_excerpt` | ✓ | · | · | · | · | · | · | · | ✓ |
| `chunk_text` | ✓ | · | · | · | · | · | · | · | ✓ |
| `import_from_content_url` | ✓ | · | · | · | · | · | · | · | ✓ |
| `parse_biblio` | ✓ | · | · | · | · | · | · | · | ✓ |
| `add_sources_batch` | ✓ | · | · | · | ✓ | · | · | · | · |
| `list_my_cards` | ✓ | · | · | · | · | · | · | · | ✓ |
| `get_my_card` | ✓ | · | · | · | · | · | · | · | ✓ |
| `list_sources` | ✓ | · | · | · | · | · | · | · | ✓ |
| `search_my_excerpts` | ✓ | · | · | · | · | · | · | · | ✓ |
| `list_deleted_cards` | · | · | · | · | · | · | · | · | · |
| `delete_card` | ✓ | · | · | · | · | · | · | ✓ | ✓ |
| `restore_card` | ✓ | · | · | · | · | · | · | · | · |
| `list_connections` | · | ✓ | · | · | · | ✓ | · | · | ✓ |
| `confirm_connection` | · | ✓ | · | · | · | ✓ | · | · | ✓ |
| `remove_connection` | · | ✓ | · | · | · | ✓ | · | · | ✓ |
| `create_content_attestation` | ✓ | · | ✓ | · | · | · | · | ✓ | · |
| `get_attestation` | · | · | ✓ | · | · | · | · | · |
| `verify_attestation` | · | · | ✓ | · | · | · | · | · |
| `list_incoming_citations` | · | · | · | · | · | ✓ | · | · |
| `mark_citations_seen` | · | · | · | · | · | ✓ | · | · |
| `archive_sources` | ✓ | · | ✓ | · | · | · | · | ✓ | · |
| `get_youtube_transcript` | ✓ | · | · | · | · | · | · | · | ✓ |
| `get_url_metadata` | ✓ | · | · | · | · | · | · | · | ✓ |
| `create_claim_request` | · | · | · | · | · | ✓ | · | · |
| `recall_memory` | · | · | · | · | · | ✓ | · | ✓ | ✓ |
| `rebuild_graph` | · | · | · | · | · | · | · | ✓ | ✓ |

---

## Les 3 hypothèses critiques (à valider en priorité)

| # | Hypothèse | Si elle échoue | Outils critiques |
|---|---|---|---|
| **H1** | Un créateur sourceur trouve assez de valeur pour créer et partager une fiche | Pivot : le format n'est pas assez attractif | `create_card`, `add_source`, `publish_card` |
| **H2** | Le public clique et reste sur les fiches | Pivot : le public ne comprend pas la valeur | `get_card`, `get_source`, `find_cards_citing` |
| **H3** | L'attestation cryptographique crée un moment « wow » défensif | Ajuster : la crypto n'est pas le trigger d'adoption | `create_content_attestation`, `verify_attestation` |
| **H4** | Le créateur veut interroger l'IA sur son corpus vérifié pour gagner du temps | Pivot : le besoin n'est pas assez fort pour justifier le workspace | `recall_memory`, `search_my_excerpts`, `get_source`, `agent.py` |

---

## Glossaire OKR

| Terme | Définition |
|---|---|
| **OKR** | Objectives and Key Results — framework de fixations d'objectifs |
| **North Star** | L'ambition ultime du projet (5-10 ans) |
| **KR** | Key Result — résultat mesurable qui prouve que l'objectif est atteint |
| **Sous-OKR** | Décomposition d'un KR en objectifs plus petits |
| **Mapping tool** | L'outil MCP qui permet d'atteindre le KR |
| **Workflow** | Séquence d'outils qui réalise une intention utilisateur |
| **Piège** | Erreur documentée dans `agent/PITFALLS.md` qui peut faire échouer le KR |
| **Corpus** | L'ensemble des sources vérifiées d'un créateur : fiches, sources, extraits, connexions |
| **Chaîne documentaire** | La trajectoire vérifiable d'une citation depuis sa source jusqu'à son utilisation |
| **Workspace de recherche** | L'espace de travail Philum où le créateur rassemble, organise et interroge ses sources |
| **BYOK** | Bring Your Own Key — le créateur utilise sa propre clé API LLM (AES-GCM chiffrée) |
| **ICM** | Interface Conversationnelle Manuscrite — le workspace 7 étapes pour créer une fiche |
