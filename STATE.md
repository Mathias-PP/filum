# État du projet

> Document vivant. À mettre à jour à la fin de chaque session de travail significative.

---

## Dernière mise à jour

**2026-06-02 — Audit improvements : privacy, deps, déprecations, et 3 windmills retirés.**

Session de vérification croisée du plan d'audit contre le code réel. 3 problèmes retirés (faux positifs), 4 corrections appliquées en PR #92 (`feat/audit-improvements`).

**Corrections appliquées :**
- **Privacy leak** : email personnel développeur remplacé par `contact@philum.app` dans User-Agent de `url_extractor.py`
- **Dépendance obsolète** : `python-jose` → `pyjwt` dans `requirements.txt` (CVE)
- **Dockerfile.migrate** : aligné sur `pyproject.toml` + `uv sync --frozen`
- **Deprecation warnings** : `datetime.utcnow()` remplacé dans 3 modèles (`source.py`, `biblio_card.py`, `audit_event.py`)

**Moulins à vents retirés (vérifiés contre le code réel) :**
- ❌ IndexError `users.py:68-69` : guard `if cards` bien présent, aucun bug
- ❌ CSRF SameSite=None : proxy + CORS + JSON API = protection complète
- ❌ AES-GCM key derivation : 128-bit effectif, toujours sécurisé (NSPM 2022)

**Docs créées/mises à jour :**
- `.docs/15-audit-improvements-plan.md` : plan complet vérifié, items retirés vs. maintenus
- `STATE.md` : cette entrée
- `.docs/14-philum-rename-migration.md` : noté changement User-Agent

**Non traité (documenté) :**
- Wayback queue durability (`asyncio.create_task` perdu au restart) — déjà documenté F5
- Renommage Filum→Philum phases 2-4 — toujours en attente

Doc `.docs/15-audit-improvements-plan.md` sert de document de référence pour les items à traiter plus tard (queue Wayback, risque juridique, cleanup legacy).

---

**2026-05-28 — Refonte complète du hero pulsar (12 passes en sandbox + port prod).**

Session longue d'itération sur `/sandbox/hero` avec retours utilisateur à chaque étape (12 commits, branche `feat/hero-design-iter`), puis port du résultat validé vers le composant prod `apps/frontend/src/lib/components/HeroPulsar.svelte`. La sandbox tunable a servi exactement à l'usage prévu (ADR-024).

**Apports du nouveau hero vs. version précédente :**

- **Graphe agrandi ×1.3** : pulsar 0.085 → 0.143 NDC, orbites et rayons nœuds idem. Plus présent sur le hero du landing.
- **Nœuds simplifiés + biomes stabilisés** : limbe net (AA 0.8×), color delta resserré (0.05), patterns adoucis. Biome et seed dérivés de l'identité du nœud (uniform `uNodeIdx`), plus du slot trié → fini les "changements de netteté" à chaque croisement en z.
- **Palette repensée** : 8 couleurs matérielles (cobalt, emerald, cyan azure, coral, amber, violet, gold, jade), jamais fluo. Pulsar passé d'un bleu électrique à une **naine bleue-blanche** (~25 000 K, type Sirius B) avec rim bleu + centre blanc-chaud.
- **Anneau chromosphérique** rose-saumon discret au limbe (remplace les "vents solaires" multi-couches qui dessinaient des halos désaxés).
- **Background apaisé** : filaments cosmiques et dust lanes atténués → ne concurrencent plus le pulsar.
- **Connexions enrichies** :
  - lignes intensifiées avec **data-pulse comète** (gauss + tail asymétrique, vitesse 0.25 cycles/s, envelope smoothstep 15 %/15 % pour fluidité parfaite)
  - **trails orbitaux** (ring buffer 6 frames, gauss additif fade exp)
- **Topologie de graphe** :
  - **lune** (nœud 5, violet) qui orbite un nœud parent (1, emerald) → connexion lune → parent, parent → pulsar
  - **Y-fork** (nœuds 3 coral et 4 amber) : leur lignes se rejoignent sur un point virtuel M qui orbite le pulsar, puis trunk M → pulsar. M jamais rendu. Les twins **tournent autour de l'axe pulsar↔M** (3D propre, perp-vectors via produit vectoriel), branches ouvertes à 70° total (35° de chaque côté), jamais d'angle droit. Joint à M invisible (gradient de couleur node→trunk + endpoint taper sur le haze).
- **Perspective 3D cohérente** : `uAnchors` étendu en vec4 (ajout du Z), `uForkTrunk` packé avec Mz. Nouvelle 2ᵉ passe lignes après le pulsar : pour chaque pixel à l'intérieur du disque pulsar, on calcule `pulsarFrontZ = sqrt(coreR² − d²)` et on redessine les portions de ligne dont `lineZ(t) > pulsarFrontZ`. **Conséquence** : quand un nœud est devant le pulsar (z > 0), sa ligne passe devant ; sinon elle reste cachée. Cohérent avec l'occlusion des nœuds eux-mêmes (déjà géré via `behindMix`).
- **Stop des animations qui surprenaient** : tailles fixes (plus de breathing pulsar, plus de depthScale nœuds, plus de hover-size — l'effet hover passe maintenant uniquement par luminosité). Rotation propre des nœuds Earth-like discrète (0.03 rad/s ≈ 200s/rev).

**Port prod** : `HeroPulsar.svelte` réécrit en intégrant tout cela. Contraintes prod préservées :
- Lazy-import OGL (`import('ogl')`) → chunk séparé, 0 KB sur les autres routes
- SVG fallback synchrone pour LCP, fade out à `webglReady`
- `prefers-reduced-motion` → skip WebGL
- IntersectionObserver pause le RAF hors-écran
- DPR plafonné à 2
- Canvas en alpha premultiplié, edge fade en transparence → pas de rectangle visible
- Constantes hardcodées au lieu des sliders sandbox

**Doc mise à jour** : ADR-024 (sandbox→prod cycle) augmentée d'une note sur le port du 28/05. Nouvelle ADR-026 sur la topologie de graphe (lune, Y-fork virtuel, perspective 3D). DECISIONS.md complétée. `.docs/05-design-system.md` mis à jour avec la nouvelle palette nœuds + pulsar.

**Build vérifié** : `pnpm build` OK, `svelte-check` 0 erreur, `pnpm lint` (eslint + prettier) propre.

---

**2026-05-26 (soir) — Audit complet du repo et nettoyage. 4 PR poussées en phases.**

Audit déclenché par la demande utilisateur : cohérence doc/code, anticipation des bottlenecks, nettoyage des branches obsolètes. Délégué l'audit code à un agent Explore, sanity-checké ses findings (3 hallucinations sur 8 dans son rapport — corrigées avant action). Résultat livré en 4 phases, chacune une PR distincte sur main.

- **PR #79** (`chore/salvage-sandboxes-to-main`) — Phase 1 : sauvegarde sur main des sandboxes `/sandbox/hero` (884 lignes) et `/sandbox/logo` (607 lignes), qui vivaient depuis 4 jours uniquement sur la branche stranded `feat/polish-and-a11y`. Méthode `git checkout origin/feat/polish-and-a11y -- apps/frontend/src/routes/sandbox/{hero,logo}/+page.svelte` plutôt que cherry-pick (qui aurait charrié 28 autres fichiers obsolètes).
- **PR #80** (`fix/ssrf-secrets-cleanup`) — Phase 3 sécurité/robustesse :
  - **SSRF guard** (`apps/backend/app/core/url_safety.py`) sur `/sources/extract` et défense en profondeur dans `WaybackService`. Bloque loopback, RFC1918, link-local (169.254.169.254 metadata cloud), multicast, reserved. 16 tests.
  - **Fail-hard sur secrets manquants en prod** : `config.py::_validate_secrets` lève un `RuntimeError` clair si `session_secret`/`master_encryption_key` sont vides hors dev/CI. Avant : régénération silencieuse à chaque démarrage Railway → invalidation de toutes les sessions + corruption de la clé qui chiffre les clés privées.
  - **Suppression endpoint `/verify` legacy** (cards + schemas + frontend stub).
  - **Doc `.env.example`** : `PUBLIC_API_BASE_URL` marqué "do not set in prod".
- **PR #81** (`feat/soft-delete-cards-sources`) — Phase 4 : soft-delete sur `BiblioCard` et `Source`.
  - Migration `008_source_deleted_at` ajoute la colonne sur sources (BiblioCard l'avait déjà depuis 001 mais elle était inutile — aucune query ne filtrait).
  - Toutes les queries publiques + dashboard + endpoints sources filtrent `deleted_at IS NULL`, eager-loads compris.
  - `DELETE /cards/{id}` et `DELETE /sources/{id}` set `deleted_at = now()` au lieu de `db.delete(card)` (qui cascadait sur les sources et brisait la citation history). Cards publiées toujours non-deletable. 6 nouveaux tests.
- **PR #82** (`docs/audit-2026-05-26-roadmap`) — la présente : roadmap Phase 5 (long terme) consignée dans [`.docs/13-audit-2026-05-26-followups.md`](.docs/13-audit-2026-05-26-followups.md) — 11 items priorisés P1/P2/P3 avec triggers naturels (génération auto des types TS, tests Postgres, queue Wayback durable, multi-tenancy, restore endpoint, etc.).

**Dependabot enquêté mais reporté** : les 10 PR Dependabot ouvertes échouent toutes au job `Lint Frontend` à cause d'un `pnpm-lock.yaml` non-prettier-formaté (Dependabot ne lance pas `pnpm format` après bump). Plus important encore : elles ont été ouvertes AVANT les PR #66–#77, donc les merger aujourd'hui reverterait les fix OAuth. À traiter en une PR groupée fresh quand le besoin se présente. Pour l'instant : ne pas merger ces PRs Dependabot, les fermer ou les laisser ouvertes selon préférence.

**Nettoyage de branches** : après le merge des PRs ouvertes, supprimer les 24 branches feature/fix/docs locales+remotes désormais inutiles (cf. PR #79 pour la liste exhaustive). Garder `main` + les PRs en cours uniquement.

**Bilan audit** : pas de finding CRITICAL en prod. Le projet est dans un état sain pour son stade (MVP pré-utilisateurs). Les bottlenecks anticipés (multi-tenancy, queue durable, scaling) sont documentés et déclenchables au bon moment.

---

**2026-05-26 — Saga « OAuth mobile + Wayback + UI polish ». 7 PR mergées (#66, #67, #75, #76, #77, plus #74 ouverte/fermée pour Wayback démo), ADR-025 ajoutée.**

Au démarrage : sur mobile, "Se connecter" produisait "Échec de l'authentification. Redirection…" alors que desktop marchait parfaitement. Symptôme classique de cookies tiers bloqués par ITP/Safari, mais le vrai diagnostic n'est tombé qu'à la 4ᵉ tentative. À chaque étape, un nouveau symptôme remplaçait le précédent — j'ai préservé toutes les PRs en historique parce que chacune posait une brique nécessaire (même si certaines ne suffisaient pas seules).

**Chronologie OAuth mobile** (du plus simpliste au vrai root cause) :

1. **PR #66** — Boutons header overflow + tentative #1 cross-origin cookies via `vercel.json` rewrite. **Inactive en prod** : le fichier contenait `REPLACE_WITH_BACKEND_HOST` (placeholder à remplir manuellement) que je n'ai pas signalé clairement. Brique architecturale correcte mais inopérante. **Leçon** : un fix qui dépend d'une action manuelle silencieuse n'est PAS un fix.

2. **PR #67** — `auth.py::_public_callback_url(request)` lit `X-Forwarded-Host` pour construire le `redirect_uri` OAuth. Aussi : démo `/@example/memoire-et-cerveau` enrichie avec 5 `archive_url` Wayback pré-remplis, SourceDetailPanel devient scrollable (max-height pixel-exacte calculée depuis `containerHeight - top - MARGIN`, plus scrollbar `.panel-scroll` toujours visible). Le volet OAuth restait inactif tant que le proxy de #66 n'était pas fonctionnel.

3. **PR #68** — Remplacement du `vercel.json` édité-à-la-main par un **proxy SvelteKit** `apps/frontend/src/routes/api/[...path]/+server.ts` qui lit `BACKEND_URL` en env var (server-side). Tous les fetchs côté navigateur passés en chemin relatif (`/api/v1/...`). `client.ts` force le path relatif via `import { browser } from '$app/environment'`. `PUBLIC_API_BASE_URL` n'est plus utilisé dans le browser. **Action utilisateur requise** : ajouter `BACKEND_URL=https://filum-production-07bb.up.railway.app` dans les env vars Vercel.

4. **PR #75** — Après #68, l'OAuth atteignait Google mais retombait sur `invalid_state` au callback. Cause : mon proxy itérait `response.headers` avec `for (const [name, value] of headers)`, ce qui en **undici (Node fetch sur Vercel)** collapse plusieurs `Set-Cookie` en un seul header virgule-séparé — comportement spécifique au runtime Node, différent des navigateurs. Le state cookie n'arrivait jamais dans le browser. Fix : skip explicite de `set-cookie` dans la copie générale, puis re-append individuel via `response.headers.getSetCookie()` (Node 18+ undici).

5. **PR #76** — Encore `invalid_state`. URL Google fournie par l'utilisateur révèle que Google redirigeait vers `filum-production-07bb.up.railway.app/api/v1/auth/google/callback` (Railway direct) au lieu de la Vercel. Donc le `redirect_uri` envoyé à Google par le backend pointait sur Railway. Root cause : **Railway's ingress réécrit unconditionnellement `X-Forwarded-Host` et `X-Forwarded-Proto`** avec son propre hostname avant que la requête n'atteigne FastAPI (sécurité standard contre host spoofing). PR #67 lisait toujours le hostname Railway, jamais le Vercel. Fix : header custom `X-Filum-Public-Origin` (non standard → Railway le laisse passer), avec fallback sur `settings.frontend_base_url`. Plus aucun chemin ne mène à `backend_base_url` pour l'OAuth.

6. **PR #77** — Auth mobile fonctionne enfin pour le compte existant `mathias.pinault@hotmail.fr`, mais un nouveau Gmail produit un 500 `internal_error`. Root cause : `username = email.split("@")[0]` collisionne avec un user existant (même local part `mathias.pinault`). Colonne `username` `unique=True` → `IntegrityError` → 500 générique. Fix : `_slugify_username()` + `_resolve_available_username()` dans `services/auth.py` qui slugifie (`mathias.pinault` → `mathias-pinault`) et résout les collisions (`mathias-pinault-2`, `-3`, …). Catch de l'`IntegrityError` résiduelle sur email duplicate → 409 propre au lieu de 500.

**Autres améliorations de la session :**

- **WaybackService refait** (PR #66) : POSTAIT seulement sur `/wayback/available` (qui n'archive pas, juste check) → tous les sources fraîches finissaient `FAILED`. Nouvelle version trigger d'abord `/save/<url>` (Save Page Now public, best-effort), puis poll `/available` avec back-offs croissants ~33 s.
- **Champ manuel `archive_url`** sur `SourceCreate`/`SourceUpdate` (PR #66) : utilisateur peut coller un snapshot existant, backend skip l'auto-archive et persiste avec `ARCHIVED` directement. Champ dans le formulaire d'ajout/édition de source.
- **5 démo sources avec archive Wayback pré-remplie** (PR #67) : Kandel, Nader, NYT, Le Monde, PBS Nova. Persistées via `archive_status=ARCHIVED` + URL `web.archive.org/web/20240601000000/...` qui résout via redirection vers le snapshot existant le plus proche.
- **Boutons header `whitespace-nowrap`** + masquage de "Créer une fiche" sous 480 px (`xs:` breakpoint Tailwind ajouté).
- **3 nouveaux tests** dans `test_auth.py` couvrant la slugification, la résolution de collision, et le fallback.

**Architecture résultante (à connaître) :**

- **Frontend → Backend** : tout passe par le proxy SvelteKit `src/routes/api/[...path]/+server.ts`. Browser appelle `/api/v1/...` (relatif), Vercel route vers la fonction serverless qui forwarde vers `BACKEND_URL`. Cookies first-party. Set-Cookie ré-appendés un-par-un.
- **Backend OAuth `redirect_uri`** : prioritairement `X-Filum-Public-Origin` (set par le proxy), fallback `frontend_base_url`. Plus jamais `backend_base_url` dans l'OAuth.
- **Configuration prod** :
  - Vercel env vars : `BACKEND_URL=https://filum-production-07bb.up.railway.app` (PUBLIC_API_BASE_URL ignoré côté navigateur, peut rester ou être supprimé)
  - Railway env vars : `frontend_base_url=https://filum-eight.vercel.app`
  - GCP OAuth Client : `Authorized redirect URI` = `https://filum-eight.vercel.app/api/v1/auth/google/callback`

**ADR-025** (nouvelle) — choix du proxy SvelteKit vs rewrite Vercel, avec les 3 pitfalls qui ont façonné le design (placeholder Vercel, undici Set-Cookie, Railway clobbering).

**Pitfalls ajoutés** dans `agent/PITFALLS.md` §1.16, §2.10, §2.11 (cookies cross-origin mobile + undici Set-Cookie + username collision).

---

**2026-05-22 — Refonte hero (WebGL pulsar) + logo V11 + favicon, déployés en prod sur `main`. Sandbox `/sandbox/hero` et `/sandbox/logo` conservées pour itérations futures.**

Quatre PR mergées dans `main` cette journée, séquence courte mais avec une grosse leçon de process :

- **PR #61** (`feat/hero-pulsar-prod` → `main`, mergée 10:29 UTC) — Mise en prod de la première version du hero WebGL et du logo V11.
  - Nouveau composant `apps/frontend/src/lib/components/HeroPulsar.svelte` : single full-screen quad fragment shader rendu via OGL (~12 KB gzippé, **lazy-imported** via `import('ogl')`). Étoile bleue type O/B au centre (limb darkening, couronne multi-couches, pointes de diffraction, éruptions plasma au limbe), 6 nœuds-exoplanètes en orbite 3D inclinée avec occlusion **par pixel** quand ils passent derrière l'astre, 4 biomes procéduraux (géante gazeuse, rocheuse, marbrée, glacée). Fond : matrice cosmique continue (ridged noise + dust lanes).
  - Contrat de performance respecté : SVG fallback inline rendu synchrone → LCP préservé, `IntersectionObserver` pause le RAF hors-écran, `prefers-reduced-motion` skip WebGL, `devicePixelRatio` plafonné à 2. Chunk OGL séparé (~27 KB), 0 KB sur le bundle initial des autres routes.
  - Interactivité : hover par nœud et sur le pulsar (curseur CSS + highlight) ; click-and-drag sur n'importe quel élément, retour à l'orbite/anchor en easing à la libération.
  - Logo `apps/frontend/src/lib/components/Logo.svelte` réécrit en V11 (3 forks + 3 simples alternés à 60°, symétrie d'ordre 3). API props inchangée, utilise `currentColor` donc `className="text-info"` continue de marcher.
  - Dépendance ajoutée : `ogl@^1.0.11` (MIT). Pitfalls documentés en **ADR-024**.

- **PR #62** — **PR perdue par erreur de process** : créée avec `--base feat/hero-pulsar-prod` à l'origine (parce que #61 n'était pas encore mergée et que je voulais isoler le diff), puis non rebasée vers `main` quand #61 a été mergée. Mergée dans `feat/hero-pulsar-prod` → contenu jamais arrivé sur `main`. **Leçon retenue** : quand une PR cible une feature branch en attente d'une PR parente, signaler explicitement la nécessité de rebaser dès que la parente est mergée.

- **PR #63** (`fix/recover-pr62-to-main` → `main`, mergée 13:55 UTC) — Cherry-pick du commit perdu vers `main`. Apporte :
  - **Favicon mis à jour** (`static/favicon.svg`) avec le tracé V11. Onglet Chrome / bookmarks / PWA reflètent enfin le nouveau logo.
  - **Cadre rigide du hero supprimé** : WebGL en `alpha: true` + `premultipliedAlpha: true` + `gl.clearColor(0,0,0,0)`. Shader sort `vec4(col * alpha, alpha)` avec fondu alpha → le canvas est réellement transparent à ses bords, le fond du `<section class="hero">` bleed à travers.
  - **Graphe ~2× plus gros** : aspect-ratio 1:1 sans max-width, marges négatives sur lg+ pour spill au-delà de la colonne.

- **PR #64** (`feat/hero-bigger-and-spread` → `main`, mergée fin de journée) — Ajustements esthétiques finaux :
  - Pulsar et nœuds 1.5× plus gros (`CORE_R` 0.085 → 0.13, rayons nœuds 0.038 → 0.057).
  - **7 nœuds** au lieu de 6 (`NODE_COUNT` 7, distribution angulaire corrigée en `(i / NODE_COUNT) * 2π` pour éviter le chevauchement à 360°).
  - Fade élargi : `smoothstep(0.45, 1.05)` au lieu de `(0.65, 1.0)` → 45 % opaque, 60 % de dissolution douce. Wrapper margins doublés sur lg+ (`width: calc(100% + 12rem)`, `-6/-7rem`).
  - Fond de la `<section class="hero">` recalé sur la palette intérieure du shader (`#02020a → #07091a → #03030d`, halos radiaux désaturés) → la transition canvas → page est désormais imperceptible.

**Sandbox laissées en place** sur la branche `feat/polish-and-a11y` (déjà mergée via PR #60 pour le polish UI, mais les commits sandbox d82e030 + 6cfee68 sont **stranded** dessus, non mergés dans main) :
- `apps/frontend/src/routes/sandbox/hero/+page.svelte` — proto avec 6 sliders live (bloom, vitesse pulsation/orbite, nodeCount, ellipticité, teinte cœur, étendue)
- `apps/frontend/src/routes/sandbox/logo/+page.svelte` — 11 variantes + référence du logo, panneau de contrôle live (taille, épaisseur, couleurs)

Ces routes sont en `<meta name="robots" content="noindex, nofollow">` et n'ont jamais été déployées en prod. Si tu veux les rendre accessibles en prod un jour pour réitérer, il faudra les cherry-picker depuis `feat/polish-and-a11y` vers une nouvelle branche basée sur `main`.

**ADR-024 (Hero WebGL via OGL)** également stranded sur `feat/polish-and-a11y`. La présente PR docs le rapatrie dans `DECISIONS.md` sur `main` pour qu'il soit consultable depuis l'arborescence principale.

---

**2026-05-15 — UI polish branch `feat/polish-and-a11y` : dark mode, hero, hover effects, CTA, bouton primary.**

Branche `feat/polish-and-a11y` créée depuis `main` avec 6 commits de refonte design system + dark mode + layout + hero galaxie + nouveaux composants. Puis corrections de polish appliquées directement sur la branche :

- **Texte hero** : restauré « Vous allez adorer partager vos références » (original pré-redesign).
- **Tokens dark mode** : `--bg-secondary` éclairci (`#0F0F11` → `#14141A`), `--text-primary` éclairci (`#EDEDED` → `#F5F5F5`), couleurs sémantiques saturées +15 %.
- **Bouton primary** : `bg-ink-primary text-white` → `bg-black text-white dark:bg-white dark:text-black` (résout le bug white-on-white en dark mode).
- **Section CTA** : background marine dédié (`#1A2A4A` light / `#0D1525` dark) au lieu d'hériter de `rgb(var(--text-primary))`.
- **SVG hero** : étiquettes des nœuds supprimées (seul « Filum » conservé), 2 clusters Y-fork ajoutés, densité d'étoiles ~13 → ~30.
- **Pages features/security/about** : `bg-white` → `bg-surface-primary` sur les cartes Features, `dark:prose-invert` ajouté sur les blocs prose Security et About.
- **Hover lift** : `translateY(-3px)` sur les step-cards, audience-cards et feature-cards.
- **Nouveaux utilitaires CSS** : `.cta-section`, `.hero-cta-light`, `.hover-lift`, `--bg-surface-secondary`.

ADR-021/ADR-022 et migration Railway → Infomaniak toujours en attente. Voir ci-dessous.

---

## Mises à jour précédentes

**2026-05-14 (PR taxonomie en cours)** — **Refonte taxonomie sources en 3 axes orthogonaux + corrections hero + parent links UI (ADR-020).**

- **Taxonomie 3 axes** : `source_type` (mélangeait format + catégorie) et `authority_level` (legacy) supprimés. Remplacés par `format` (5 valeurs), `category` (12), `author_kind` (9). Migration Alembic 007 avec backfill best-effort.
- **Graphe coloré par `author_kind`** : la couleur du nœud encode désormais l'origine épistémique (chercheur / média / institution-publique / etc.), pas un mélange format/catégorie. Palette dans `apps/frontend/src/lib/utils/author-colors.ts`.
- **Formulaire d'ajout de source** : 1 dropdown → 3 dropdowns obligatoires + dropdown optionnel « Cette source en cite une autre déjà ajoutée ? » qui persiste `parent_source_id`. Composants `AuthorKindBadge`, `FormatBadge`, `CategoryBadge` côté détail.
- **Bug fix** : `POST /cards/{id}/sources` ignorait silencieusement `parent_source_id` au CREATE (champ jamais passé au constructeur `Source(...)`). Le seed le contournait par insertion directe.
- **Garde levée** : `POST/PATCH/DELETE /sources/...` n'interdisent plus l'édition sur fiches publiées (cohérent avec ADR-019 — fiches mutables).
- **Hero accueil** : suppression du mot « contenu » dans « chaque contenu original que vous revendiquez » (collision sémantique avec l'ex-`source_type=original`) et refonte du SVG (lignes droites, 2 arêtes pointillées entre sources pour illustrer le feature parent, labels mis à jour avec la nouvelle taxonomie).
- `CardStats` re-keyé : `peer_reviewed`/`institutional`/... → `chercheur`/`media`/`institution_publique`/`individu`. La fiche publique adapte les 2 tuiles statistiques.
- Branche `feat/taxonomy-redesign`, PR à ouvrir, merge manuel par l'utilisateur.

**2026-05-14 (PR #43 mergée)** — **Passe UX/UI : mobile nav + dashboard édition + hero + 404.**

- **Mobile nav** : menu hamburger ajouté dans `+layout.svelte`. Les 4 onglets de navigation (`Fonctionnalités`, `Roadmap`, `Sécurité`, `À propos`) étaient inaccessibles sur mobile (`hidden md:flex` sans alternative). Drawer fermé sur Escape ou clic extérieur.
- **Dashboard fiches publiées** : ajout des boutons Voir / Éditer / Supprimer (les fiches sont mutables depuis ADR-019, l'édition réutilise `/dashboard/new/{id}/sources`).
- **Compteurs dashboard** (X brouillons, Y publiées) + skeleton loader.
- **Hero accueil refondu** : layout 2 colonnes, illustration SVG vectorielle dédiée (graphe de citation stylisé avec types de sources colorés et nœud central animé), background dégradé subtil.
- **Page 404 custom** (`+error.svelte`) avec CTA contextuels.
- **`/privacy`** : stub minimal pour éviter le 404 footer.
- **Loading states** : labels dynamiques + `disabled` pendant submit sur création fiche, ajout source, publication.
- Branche `feat/ux-mobile-dashboard-hero`, PR à ouvrir, merge manuel par l'utilisateur.

**2026-05-14 (post-PR #40)** — **Axe C terminé et déployé en prod.** Migration 006 + table `content_attestations` + endpoints attestation + seed signing sont opérationnels. Plusieurs crashs résolus. Plan 3 axes révisé : le P0 (Axe C) est livré, place au P1 (Axe B — archivage multi-cible).

**2026-05-14 (PR #39 + PR #40) — Axe C déployé, 2 crashs production résolus.**

- **PR #39** — Fix migration 006 : `op.drop_index("ix_biblio_cards_canonical")` retiré car l'index n'a jamais été créé en base (seul `ix_biblio_cards_canonical_hash` auto-généré par `Column(index=True)` existe). PostgreSQL cascade-drop automatiquement l'index avec la colonne. Conflits de merge résolus (rebased on `main` après merge PR #38). CI toute verte.
- **PR #40** — Fix `NotNullViolationError` sur `content_attestations.created_at` : le modèle avait `default=None, server_default=None`, ce qui forçait SQLAlchemy à envoyer `NULL` dans l'INSERT, court-circuitant le `server_default=sa.func.now()` défini dans la migration 006. Fix : `server_default=func.now()` sans `default=None`.
- Root cause documentée dans [`agent/PITFALLS.md`](agent/PITFALLS.md) §1.8.
- Backend stable : migration 006 s'exécute correctement, seed demo crée les attestations, endpoints attestation fonctionnels.

**2026-05-14 (PR #36) — VRAIE root cause du bug publish trouvée et corrigée.** Après 3 PRs de fausses pistes (#33 MissingGreenlet, #34 try/except + diagnostic, #35 endpoint /health/publish-diagnose), l'endpoint diagnostic a exposé le vrai traceback : `asyncpg.DataError: can't subtract offset-naive and offset-aware datetimes`. `CardService.publish_card` faisait `datetime.now(UTC)` sans `.replace(tzinfo=None)` (oubli du pattern PITFALLS §1.5) → colonne `TIMESTAMP WITHOUT TIME ZONE` refusait → commit aborté → `get_db` cleanup retentait le commit sur session morte → réponse interrompue mid-stream → CORS header jamais ajouté → user voit "blocked by CORS policy" alors que CORS marche partout ailleurs. Fix : `.replace(tzinfo=None)` + rollback défensif dans le try/except du endpoint. PITFALLS §1.5 enrichi.

**2026-05-14 (PR #34)** — Diagnostic & filet de sécurité publish : le user a signalé que le bug `Failed to fetch` persistait après PR #33 mergée. Triple action : (1) endpoint `publish_card` enveloppé d'un `try/except` qui garantit une réponse JSON 500 propre quelle que soit l'exception (au lieu d'une connexion qui meurt en silence) ; (2) `/health` retourne désormais `commit` (SHA git Railway) pour vérifier en un `curl` que Railway a bien redéployé ; (3) message d'erreur frontend publish reformulé pour guider le user vers la console DevTools. Voir CHANGELOG `[Unreleased]`.

**2026-05-14 (PR #33)** — Fix critique du publish : `MissingGreenlet` sur `card.user.username` post-commit/refresh dans `CardService.publish_card`. Navigateur recevait `TypeError: Failed to fetch` (pas un bug réseau ni CORS, mais la sérialisation HTTP qui mourait sans body). PITFALLS §1.4 enrichi avec le symptôme côté frontend.

**2026-05-14 (PR #32)** — **Pivot crypto** : signature désormais sur le lien créateur·ice ↔ contenu via triplet `(creator_id, content_url, attested_at)`, plus sur la fiche. Reformulation copy globale, suppression FAQ sécurité, ajout Filum Desktop dans roadmap. Voir ADR-019 dans `DECISIONS.md`. La PR backend de bascule (migration `006_remove_card_signature`, table `content_attestations`, refonte endpoint publish) reste à ouvrir.

**2026-05-13** — Session PR #31 : MVP améliorations — CI lint frontend fixée (`.prettierignore` + format 4 fichiers), README mis à jour. Voir `CHANGELOG.md` pour le détail.

### PR #30 — Missing Request type hints (mergée)
- **Root cause du bug "An error occurred"** : `get_current_user` dans `sources.py` et `users.py` avait `request` sans `: Request` type hint → FastAPI traitait `request` comme paramètre query au lieu d'injecter l'objet Request → tous les endpoints sources retournaient 422.
- Fichiers : `sources.py:63`, `users.py:20` — ajout de `request: Request` + import `Request` dans `users.py`.

### PR #31 — MVP améliorations (cette session)
- **3 nouvelles pages** : `/features` (fonctionnalités dispo + à venir), `/roadmap` (feuille de route), `/security` (cryptographie, clés, FAQ)
- **OpenGraph dynamique** : backend `GET /api/v1/og?title=&creator=` génère une image PNG 1200×630 via Pillow + police DejaVu Serif ; frontend `og:image` / `twitter:image` sur les fiches publiques
- **Logout fix** : `invalidateAll()` après déconnexion pour rafraîchir `data.user` — l'avatar Google ne reste plus affiché
- **Publish** : message "Impossible de contacter le serveur" au lieu de "Failed to fetch" en cas d'erreur réseau
- **Texte "Pour qui?"** : 4e catégorie "Créateur·ice·s de contenu" + note "N'oubliez pas de citer..." sur accueil et À propos
- **About enrichi** : histoire, valeurs (transparence, pérennité, liberté), liens vers /security et GitHub

### Jalons terminés
- **M1** — OAuth Google (backend + frontend, manque credentials humains)
- **M2** — Auth guard + extracteur URL branché
- **M3** — Rate limiting, logs structurés, backup documenté

Jalon M1 livré précédemment :
- Backend : endpoints `/auth/google/login` et `/auth/google/callback` complétés. State token CSRF en cookie HttpOnly. Échange code → id_token vérifié via Google JWKS (PyJWKClient). Création/retrouvage User. Cookie session avec samesite conditionnel (`lax` en debug, `none+secure` en prod). Génération paire Ed25519 chiffrée AES-GCM à la première connexion.
- Frontend : bouton « Continuer avec Google » sur `/` avec icône. Page `/auth/callback` qui hydrate le store auth. `credentials: 'include'` déjà présent dans le client API.
- Tests : 72 tests pytest (66 existants + 6 nouveaux). 1 test d'intégration callback mocké + tests unitaires state cookie.
- Aucune nouvelle dépendance ajoutée (PyJWT + httpx + cryptography existaient déjà).

Itérations précédentes :
- PR1 (itération 3) : lint frontend enforced (ESLint 9 flat config, prettier bloquant), `signing.py` refactorisé, `dashboard/new` + `dashboard/new/[card_id]/sources` créés, vitest source-colors, `svelte-kit sync` ajouté en CI avant tests.
- PR2 (itération 3) : extracteur URL (`url_extractor.py` — Crossref + HTML scraping), endpoint `GET /sources/extract`, fix critique `asyncio.create_task` + session SQLAlchemy isolée (Wayback), guard SSRF (`HttpUrl` + scheme check), fix DOI regex, dead code supprimé.

---

## Phase courante

**Phase 1 — MVP complet + Axe C (ADR-019) livré.** Tous les jalons M1+M2+M3 sont terminés. Axe C (refonte backend post-ADR-019) également déployé : migration 006, table `content_attestations`, endpoints attestation, désormais la signature porte sur le triplet `(creator_id, content_url, attested_at)` et non plus sur la fiche. Le flow complet login → création → signature → attestation → publication est opérationnel.

---

## URLs

- **Repo** : https://github.com/Mathias-PP/filum
- **Backend prod** : https://filum-production-07bb.up.railway.app
  - `/health` → `{"status":"ok","version":"0.1.0"}`
  - `/health/database` → `{"status":"ok","database":"connected"}`
  - `/api/v1/docs` → Swagger UI
- **Frontend prod** : https://filum-eight.vercel.app
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau (graphe D3 interactif, 18 sources neurosciences, 8 arêtes de citation, embranchement Y)

---

## Branches Git

| Branche | État |
|---|---|---|
| `main` | Branche de déploiement. PR #39 (fix migration 006 drop index) et PR #40 (fix model `created_at` NULL) mergées et supprimées. Axe C fully live. |
| `feat/polish-and-a11y` | UI polish : dark mode tokens, hero text/SVG, bouton primary, CTA, hover effects, `dark:prose-invert`. PR à ouvrir. |

---

## CI

9/9 jobs verts sur `main` :

- Security Scan (Trivy SARIF, TruffleHog sur PR uniquement)
- Lint Backend (ruff)
- Type Check Backend (mypy, 0 erreur)
- Test Backend (41 tests pytest, 100% pass)
- Lint Frontend (eslint 9 flat config, prettier, **actif** depuis PR1 itération 3)
- Test Frontend (vitest, test source-colors 2/2)
- Build Frontend (vite, `--frozen-lockfile`, pnpm 10 pinned)
- Analytics Check (dbt compile)

Workflow `cd.yml` supprimé : Railway déploie en natif via son intégration GitHub (cf. ADR-015).

**Améliorations CI récentes (2026-05-13)** :
- Suppression du double `uv sync` dans `lint-backend` (le `--only-dev` initial était écrasé par `--all-extras`)
- Ajout de `.github/dependabot.yml` : mises à jour hebdo pip/npm, mensuelles GitHub Actions
- Sécurité : dépendance `Pillow` ajoutée (OG images dynamiques, installée via `uv add Pillow`)

---

## Stack effective déployée

### Backend
- Python 3.12 + FastAPI async + SQLAlchemy 2.x async + Alembic
- PostgreSQL (Railway plugin, lié via `${{Postgres.DATABASE_URL}}`)
- Crypto : Ed25519 + AES-GCM + HS256 (PyJWT, plus de python-jose, cf. ADR-014)
- Models : User, BiblioCard, Source, AuditEvent
- API REST sous `/api/v1/` : auth, cards, sources, users, og
- Migrations Alembic exécutées au boot dans le `CMD` Docker
- 72 tests (pytest — unit + integration)
- Extracteur URL : `app/extractors/url_extractor.py` (Crossref + HTML scraping)
- Endpoint `GET /api/v1/sources/extract` (no auth, best-effort metadata)
- Générateur OpenGraph : `app/services/og_image.py` (Pillow, police DejaVu Serif), endpoint `GET /api/v1/og?title=&creator=`

### Frontend
- SvelteKit 2 + Svelte 5 + TypeScript + Tailwind, déployé sur Vercel
- pnpm 10.33.4 pinned via `packageManager` (cf. ADR-013)
- Design system : Button, Input, Card, Avatar, Badge, Alert, SourceTypeBadge, SourceGraph, SourceDetailPanel
- Stores : auth, cards
- Routes : home, dashboard, features, roadmap, security, about, public card (avec graphe D3, OpenGraph dynamique, SSR + JSON-LD), user profile, `/dashboard/new` (création fiche 2 étapes)
- D3 v7 (force-directed) + utilitaire `lib/utils/source-colors.ts` (single source of truth des couleurs de type de source)
- API base URL pilotée par `PUBLIC_API_BASE_URL` (env Vercel)

### Analytics
- dbt-core sur DuckDB (job `dbt compile` en CI)

---

## Décisions techniques récentes (post-merge)

Voir `DECISIONS.md` pour le détail :

- **ADR-013** : pin pnpm 10 (les workarounds pnpm 11 dégagent)
- **ADR-014** : migration `python-jose` → `PyJWT` (suppression CVE ecdsa Minerva)
- **ADR-015** : déploiement Railway via intégration native GitHub (pas de workflow CD)
- **ADR-016** : graphe interactif D3.js + `Source.parent_source_id` pour le citation graph (la fiche publique reflète enfin la promesse "wow" de la vision)
- **ADR-017** : itération 2 — indicateurs typés (citations, IF, abonnés, vues), table `source_excerpts`, conflits d'intérêt déclarés, SSR + JSON-LD sur la fiche publique, panneau de détail ancré au nœud, renommage Pivot → Source clé

---

## Variables d'environnement (Railway, production)

```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://filum-production-07bb.up.railway.app
cors_origins           = ["https://filum-eight.vercel.app","http://localhost:5173"]
debug                  = false
```

⚠️ **Toutes en lowercase** (ADR-010, `case_sensitive=True` dans pydantic-settings).

Variables intentionnellement non configurées (defaults dans `config.py` suffisent) :
- `google_client_id`, `google_client_secret`, `google_redirect_uri` — OAuth non activé
- `wayback_api_key` — feature Wayback pas encore branchée
- `duckdb_path` — DuckDB n'est pas chargé dans le backend (analytics séparé)

---

## Bugs latents identifiés (non fixés)

| Bug | Sévérité | Localisation |
|---|---|---|
| ~~`apps/backend/app/extractors/` vide~~ | **Résolu** | `url_extractor.py` implémenté (Crossref + HTML scraping), endpoint `GET /sources/extract` |
| ~~`crypto/signing.py` = stub~~ | **Résolu** | SigningService + Canonicalizer déplacés dans `signing.py` |
| ~~Deps eslint frontend manquantes~~ | **Résolu** | 6 deps ajoutées, eslint 9 flat config, CI `\|\| true` retiré |
| ~~8 warnings `state_referenced_locally`~~ | **Résolu** | Composants convertis à `$derived()` / `$effect()` |
| ~~Auth guard absent sur `/dashboard*`~~ | **Résolu** | `+layout.ts` dans `/dashboard/` redirige vers `/` si non connecté |
| ~~Rate limiting absent sur `GET /sources/extract`~~ | **Résolu** | slowapi branché : 10 req/min sur `/sources/extract`, 20 req/h sur `POST /cards` |
| ~~Signature fiche encore présente en base (post-ADR-019)~~ | **Résolu** | Migration 006 mergée et déployée : table `content_attestations` créée, colonnes `canonical_hash/signature/signed_at` dropées de `biblio_cards`. Seed demo crée les attestations. |
| `impact_factor` toujours `null` | Faible | OpenAlex supprimé (dead code), pas de fallback |
| ~~Publish renvoie « Impossible de contacter le serveur »~~ | **Vraie résolution PR #36** | `asyncpg.DataError` sur `card.signed_at = datetime.now(UTC)` (manquait `.replace(tzinfo=None)`) dans `CardService.publish_card`. Commit aborté → `get_db` cleanup retente sur session morte → réponse interrompue → CORS header jamais ajouté → user voyait "blocked by CORS policy". Fix : naive UTC datetime + rollback défensif. PITFALLS §1.5 enrichi. PR #33 (MissingGreenlet) et #34 (try/except) n'étaient pas la vraie cause mais restent utiles comme filet de sécurité. |
| Test composant Svelte 5 incompat | Faible | À réécrire avec API testing-library compatible Svelte 5 |
| ~~Cookie `samesite=lax`~~ | **Résolu** | Bascule `samesite=none + secure=True` conditionnée sur `settings.debug` (PR jalon M1) |
| Pas de domaine custom | Feature | Brancher `filum.app` quand prêt |

---

## État production vérifié (2026-05-13)

Vérifié par `curl` sur les URL prod, pas par lecture des docs :

- ✅ Backend `/health` → 200 OK, version 0.1.0
- ✅ API `/api/v1/@example/memoire-et-cerveau` → 200, 16 sources (dont 2 non-académiques), signature Ed25519 présente
- ✅ Migration 004 **appliquée** : les nouveaux champs (`citations_count`, `subscribers_count`, `views_count`, `impact_factor`, `conflict_of_interest`, `excerpts[]`) sont bien sérialisés dans la réponse API
- ✅ Frontend SSR fonctionne : `<script type="application/ld+json">` présent dans le HTML statique, meta `og:title`/`og:description`/`og:image` présents
- ✅ OpenGraph dynamique : `GET /api/v1/og?title=Test` retourne une image PNG 1200×630
- ✅ Nouvelles pages : `/features`, `/roadmap`, `/security` accessibles sur le frontend
- ✅ **Seed P0 résolu** : `_get_or_create_demo_card` ne fait plus early-return. Les sources sont delete+recreate à chaque run, les nouveaux champs (excerpts, conflits, indicateurs) sont rafraîchis, et 2 nouvelles sources non-académiques sont ajoutées (documentaire NOVA + dessin Cajal). La fiche démo prod est re-signée à chaque run du seed.

---

## Prochaines étapes par priorité (basé sur l'état prod vérifié)

> Plan détaillé dans [`.docs/12-next-steps.md`](.docs/12-next-steps.md). Cette section est l'**index** opérationnel.

### P0 — Axe C : refonte backend post-ADR-019 ✅ **LIVRÉ**

Migration 006 mergée et déployée. Table `content_attestations` en prod. Endpoints attestation fonctionnels. Seed demo signé. Deux bugs résolus en cours de route (DROP INDEX inexistant, `created_at` NULL).

### P1 — Axe B : archivage multi-cible (1 semaine)

- Refacto `WaybackService` → `ArchiveOrchestrator` (Wayback → Archive.today → Playwright)
- Table `archive_attempts` + retry exponentiel via cron Railway
- Badge archive sur chaque source côté UI
- Endpoint public `GET /sources/{id}/archive`

### P2 — Validation produit (1 semaine)

Interviewer 3 créateurs cibles avant Axe A : « voudriez-vous héberger vos vidéos/articles directement sur Filum, ou Filum doit-il rester un index ? »
Sans validation, ne pas attaquer Axe A.

### P3 — Axe A : stockage cloud R2 (2-3 semaines, conditionnel)

- ADR-020 : Cloudflare R2 comme blob store principal (10 GB free + zero egress), Internet Archive en miroir long terme
- Service `BlobStorage` (interface) + impls R2 + InternetArchive
- Migration `007_add_content_files`
- Endpoints `POST /uploads/initiate` (URL pré-signée R2) + `/uploads/complete`
- Frontend `<ContentUploader>` avec upload direct R2
- Sécurité : ClamAV scan, max 500 Mo/fichier, vérif checksum SHA-256

### P4 — Autres (mûr mais non bloquant)

- Tests E2E Playwright (golden path)
- Import Zotero / BibTeX / Obsidian (bloqué jusqu'à axe C livré)
- Plugin navigateur (après 3-5 créateurs actifs)
- Domaine custom `filum.app` (après premier ambassadeur prêt)
- Améliorer l'extraction de métadonnées (fallbacks supplémentaires)

### P2 — Qualité interne (dette dormante)

- Réécrire test composant Svelte 5 (compatible testing-library Svelte 5)
- ~~Nettoyage `authority_level` (legacy, plus utilisé par l'UI)~~ **Résolu par ADR-020** : colonne droppée par migration 007
- Réduire cold start Railway (keep-alive ou instance hobby)

### P3 — Ouverture produit

- Import Zotero / BibTeX / Obsidian
- Export PDF / CSV / Excel / JSON / BibTeX
- Plugin navigateur (ajout de source en un clic)
- API publique + serveur MCP
- Domaine custom `filum.app`
- Score de sourçage IA

---

## Commandes utiles

```bash
# Backend local
cd apps/backend
uv sync --all-extras
uv run uvicorn app.main:app --reload                 # dev server
uv run pytest tests/ -v                              # tous les tests
uv run alembic upgrade head                          # appliquer migrations
uv run ruff check app/ && uv run mypy app/ --ignore-missing-imports

# Frontend local
cd apps/frontend
pnpm install --frozen-lockfile
pnpm run dev                                         # dev server
pnpm run check                                       # type check
pnpm run build                                       # production build

# Logs Railway
# → dashboard https://railway.com/project/<id>
# → service backend → Logs

# Voir les runs CI
wsl gh run list --branch main --limit 5

# Re-trigger CI (push vide)
git commit --allow-empty -m "ci: retrigger" && git push origin main
```

---

## Comment relancer une session avec un agent IA

Pour qu'un agent (Claude Code, Aider, opencode, etc.) reprenne efficacement :

1. **Travail autonome multi-sessions** : commencer par [`agent/README.md`](./agent/README.md). Le dossier `agent/` contient le protocole complet (permissions, git workflow, pitfalls, skills) + une mémoire condensée dans [`agent/memory/PROJECT_SNAPSHOT.md`](./agent/memory/PROJECT_SNAPSHOT.md).
2. **Plan de complétion MVP** : [`.docs/10-mvp-completion-plan.md`](./.docs/10-mvp-completion-plan.md) — jalons M1 (OAuth), M2 (auth guard + extracteur), M3 (durcissement).
3. **Travail ponctuel (une session)** : lire dans l'ordre `README.md` → `STATE.md` (ce fichier) → `DECISIONS.md` → `.docs/01-product-spec.md` → `.docs/02-tech-architecture.md`.
4. **Vérifier l'état actuel** :
   - `git log --oneline -10`
   - `wsl gh run list --branch main --limit 3`
   - `curl https://filum-production-07bb.up.railway.app/health`
5. **Choisir une tâche** : suivre le jalon courant du plan MVP, sinon prendre dans « Prochaines étapes » ci-dessus.
6. **Travailler** : branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite (cf. [`agent/GIT_WORKFLOW.md`](./agent/GIT_WORKFLOW.md)).
