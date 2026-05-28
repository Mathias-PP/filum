# Journal des décisions

> Ce fichier consigne les décisions techniques et stratégiques importantes prises au fil du projet. Format inspiré des « Architecture Decision Records » (ADR).
>
> **Une entrée par décision.** Chaque entrée est datée, contient le contexte, l'option retenue, les alternatives écartées, et les conséquences.

---

## ADR-026 — Topologie de graphe hero : lune + Y-fork virtuel + perspective 3D ligne/sphère

**Date** : 2026-05-28

**Contexte**
La première version du hero pulsar (ADR-024, mai 2026) montrait N nœuds tous reliés en étoile au pulsar central. C'est lisible, mais ça ne raconte pas la **topologie d'une vraie fiche bibliographique Filum** : les sources peuvent dépendre d'un autre auteur (citation indirecte, série de papiers d'un même labo) ou être groupées (deux sources qui débattent un même point, citées ensemble). La PR #83 a introduit deux structures topologiques supplémentaires + un fix de perspective 3D pour que le rendu soit cohérent à toutes les positions orbitales.

**Trois mécaniques visuelles ajoutées**

### 1. Lune autour d'un parent (nœud 5 → nœud 1)

- Le nœud 5 (violet, rayon × 0.55) orbite **localement autour du parent** (nœud 1, emerald, rayon × 1.2), pas autour du pulsar.
- Connexion : lune → parent (pas lune → pulsar). Parent → pulsar comme un nœud régulier.
- Implémentation : passe B après la passe orbitale classique, override `(x, y, z)` du moon avec `parent.position + Math.cos/sin(t × localSpeed) × localOrbitR` (ellipse + bobbing z).
- Sens produit : « cette source dépend d'une autre source de la fiche ».

### 2. Y-fork (lien qui se divise vers deux nœuds)

- Deux nœuds (3 coral, 4 amber) partagent un **point de division M virtuel** qui n'est jamais rendu comme sphère.
- M orbite le pulsar avec ses propres paramètres orbitaux (`VIRTUAL_FORK` côté JS).
- Les twins **tournent autour de l'axe pulsar↔M en 3D** (perp-vectors construits via deux produits vectoriels, position = M + cos(spin)·perp1 + sin(spin)·perp2) **avec une composante axiale** dans le sens de la prolongation pulsar→M : `branchLen × cos(35°)` au long de l'axe + `branchLen × sin(35°)` perpendiculaire. L'angle total du Y est donc **70°**, jamais droit.
- Lignes : pulsar → M (trunk) + M → twin A + M → twin B.
- **Joint à M invisible** :
  - Gradient de couleur sur la ligne twin : `mix(nodeColor, trunkColor, smoothstep(0.15, 1.0, tNorm))` → à M les 3 lignes ont toutes la couleur du trunk
  - Endpoint taper sur le haze : `endTaper = smoothstep(0, 0.08, tN) × (1 − smoothstep(0.85, 1.0, tN))` → trois hazes additives ne forment plus de halo
  - Aucun "junction node" rendu (un disque visible à M avait été testé et rejeté car il lisait comme un nœud parasite)
- Sens produit : « ces deux sources sont citées ensemble depuis un sous-point de l'argumentation ».

### 3. Perspective 3D ligne/pulsar (cohérence d'occlusion)

- Avant : les lignes étaient dessinées **avant** le pulsar, donc systématiquement recouvertes par sa sphère, même quand leur nœud était devant en perspective.
- Maintenant : `uAnchors` étendu en vec4 (ajout de `anchorZ`), `uForkTrunk` packé avec `Mz`.
- **2ᵉ passe lignes après le pulsar** : pour chaque pixel à l'intérieur du disque pulsar, on calcule `pulsarFrontZ = sqrt(coreR² − d²)` (z de la surface frontale 3D de la sphère). Pour chaque ligne : `lineZ(t) = mix(node.z, anchor.z, along/lineLen)`. Si `lineZ > pulsarFrontZ` → la portion de ligne est redessinée par-dessus.
- Cohérent avec l'occlusion des nœuds eux-mêmes (déjà gérée via `behindMix` per-pixel depuis ADR-024).
- Résultat : quand un nœud est devant (z > 0), sa ligne passe devant le pulsar. Sinon elle reste cachée. Lecture 3D naturelle.

**Stabilité des biomes (correctif au passage)**

Bug latent depuis ADR-024 : le shader dérivait `biome = mod(float(i), 4.0)` où `i` était le slot trié back-to-front. Quand deux nœuds échangeaient leur z, ils échangeaient leurs slots **et leurs biomes** → impression de « netteté qui change » pendant l'orbite. Fix : nouvel uniform `uNodeIdx[8]` écrit côté JS avec `slice[i].colorIdx`. Biome et seed dérivés de l'**identité** du nœud, plus du slot.

**Bibliothèque de gestes UI volontairement supprimés**

- Plus de breathing animation sur la taille du pulsar (`coreR * (0.985 + 0.030 × pulse)` → `coreR`)
- Plus de modulation `depthScale` sur les rayons nœuds (la profondeur est lue par luminosité via `depthBright`, pas par taille)
- Plus de `hover * 0.35` sur la taille des nœuds (l'effet hover passe désormais uniquement par le glow et la luminosité du `lit factor`)
- Raison : ces animations donnaient l'illusion que le pulsar ou les nœuds changeaient de taille au moment des croisements en z, ce qui parasitait la lecture de profondeur réelle.

**Conséquences**

- Le hero raconte désormais visuellement la **topologie d'un graphe de citations** (étoile + lune + fourchette), pas juste « une étoile au centre avec des planètes ».
- Coût GPU : la 2ᵉ passe lignes ajoute ~8 × pixel-couvert-par-le-disque-pulsar évaluations. Négligeable car le disque ~3 % de la surface (radius 0.143 / NDC 2 × 2).
- Pas d'augmentation du chunk WebGL prod (toujours `import('ogl')` lazy).
- ADR-024 reste la référence pour les contraintes de perf et le contrat fallback SVG.

---

## ADR-025 — Auth cross-origin : proxy SvelteKit `/api/[...path]/+server.ts` (et pas rewrite Vercel)

**Date** : 2026-05-26

**Contexte**
Frontend déployé sur Vercel (`https://filum-eight.vercel.app`), backend FastAPI sur Railway (`https://filum-production-07bb.up.railway.app`). Quand le SPA appelait Railway directement depuis Vercel, le `Set-Cookie filum_session` posé par Railway était un cookie tiers du point de vue du navigateur. **Mobile Safari et iOS WebKit (Chrome iOS inclus) bloquent les cookies tiers par défaut via ITP**, donc le cookie de session était droppé silencieusement et le SPA recevait 401 sur le `GET /auth/me` post-OAuth, produisant "Échec de l'authentification" — uniquement sur mobile, jamais sur desktop (qui est plus permissif).

Objectif : rendre l'API first-party du point de vue du navigateur, sans modifier la cible de déploiement (Railway reste backend, Vercel reste frontend).

**Options envisagées**

- **Rewrite Vercel statique dans `vercel.json`** (tentée puis abandonnée — PR #66) : `destination: "https://<backend>/api/$1"`. Le placeholder doit être édité manuellement avant déploiement — pas d'interpolation d'env var dans `vercel.json`. Sur ce projet le placeholder n'avait pas été remplacé → la rewrite était inopérante en prod et le fix « n'avait aucun effet », ce qui est invisible au coup d'œil et difficile à debugger. Pattern rejeté.
- **Proxy SvelteKit `src/routes/api/[...path]/+server.ts`** (retenue — PR #68 + #75 + #76) : un endpoint catch-all qui lit `BACKEND_URL` server-side et forwarde toutes les méthodes HTTP. Une seule env var à set (pas de fichier statique à éditer). Cohérent en dev et prod.
- **Authorization header avec JWT en localStorage** (rejetée) : changement complet du modèle d'auth, déconnecté du reste de la session-via-cookie. Trop lourd pour ce besoin précis.

**Justifications**

- Configuration en **une seule étape** : ajouter `BACKEND_URL` aux env vars Vercel. Pas de placeholder dans le code à oublier de remplacer.
- Cookies first-party automatiquement : le navigateur ne voit qu'une seule origine (Vercel).
- Le proxy peut **injecter des headers contrôlés** (utilisé pour `X-Filum-Public-Origin`, voir pitfall plus bas).
- Marche identiquement en dev (default `localhost:8000`, vite proxy fait la même chose en parallèle) et en prod (Vercel serverless).

**Conséquences**

- **Latence** : 1 hop additionnel pour chaque requête API (browser → Vercel edge → Railway). Mesuré ~30-80 ms supplémentaires sur Vercel France. Acceptable pour ce produit.
- **Cold start** : la fonction proxy est petite (~5 KB JS), cold start négligeable (~50 ms).
- **Toutes les URLs côté navigateur DOIVENT être relatives** : on ne peut plus jamais utiliser `PUBLIC_API_BASE_URL` dans le `<script>` browser, sinon le proxy est court-circuité. `client.ts` force le path relatif via `import { browser } from '$app/environment'`.
- Le SSR (sur Vercel) re-traverse le proxy via `fetch` relatif — 1 hop supplémentaire à l'intérieur du même runtime. Performance acceptable.

**Pitfalls rencontrés et résolus dans la même session**

1. **`undici` Set-Cookie mangling (PR #75)** : itérer `response.headers` avec `for (const [name, value] of headers)` en Node fetch collapse plusieurs `Set-Cookie` en un seul header virgule-séparé. Comportement spécifique à undici/Node, différent du fetch des navigateurs. Le browser ne stocke alors pas les cookies correctement. **Solution** : skip explicite de `set-cookie` dans la copie générale puis ré-append individuel via `response.headers.getSetCookie()` (Node 18+ undici, disponible sur Vercel).

2. **Railway clobbering `X-Forwarded-Host` (PR #76)** : l'ingress Railway réécrit unconditionnellement `X-Forwarded-Host` et `X-Forwarded-Proto` avec son propre hostname avant que la requête n'atteigne FastAPI (sécurité standard contre host spoofing). Donc se reposer sur ces headers standards pour reconstruire le `redirect_uri` OAuth ne marche PAS. **Solution** : header custom `X-Filum-Public-Origin` (non standard → Railway le laisse passer), avec fallback `settings.frontend_base_url` (déjà set sur Railway).

3. **Username collision sur signup OAuth (PR #77)** : `email.split("@")[0]` peut générer le même username pour 2 comptes Google différents (`mathias.pinault@hotmail.fr` vs `mathias.pinault@gmail.com`). Colonne `unique=True` → `IntegrityError` → 500 générique. **Solution** : slugification (`mathias-pinault`) + résolution de collision (`-2`, `-3`, …) dans `services/auth.py`.

**Actions requises pour ce setup en prod**

- Vercel env var : `BACKEND_URL=https://filum-production-07bb.up.railway.app`
- Railway env var : `frontend_base_url=https://filum-eight.vercel.app` (déjà set, utilisé aussi pour le redirect post-OAuth `/auth/callback`)
- GCP OAuth Client → Authorized redirect URIs : `https://filum-eight.vercel.app/api/v1/auth/google/callback`

---

## ADR-024 — Hero accueil : WebGL via OGL plutôt que SVG/Canvas 2D/three.js

**Date** : 2026-05-22

**Contexte**
Le hero du site (accueil `/`) sert d'effet vitrine. Le SVG statique précédent (galaxie 2D + parallax 3D au survol) ne tenait pas le niveau visuel souhaité (« naine bleue avec exoplanètes en orbite »). Besoin d'un rendu temps-réel haute qualité sans dégrader les Core Web Vitals (LCP en particulier).

**Options envisagées**
- **SVG enrichi + CSS animations** : 0 KB de bundle. Pas de vrai bloom, pas de particules GPU, plafond visuel atteint.
- **Canvas 2D pur** : 0 KB. Glow via gradients radiaux acceptable, mais pas de post-process volumétrique, CPU-bound (~5-15 % continu mobile).
- **Three.js** : ~150 KB gzippé. Capacité visuelle maximale, mais coût bundle disproportionné pour un seul composant.
- **[OGL](https://github.com/oframe/ogl) (retenu)** : ~12 KB gzippé, WebGL low-level minimaliste, MIT. Capacité quasi-équivalente à three.js (custom shaders, FBO, instancing) pour 12× moins de poids.

**Justifications**
- 1 draw call par frame (un seul quad fullscreen, tout le rendu en fragment shader) → faible coût GPU desktop comme mobile.
- Bundle isolé via import dynamique : le chunk WebGL ne charge **que** sur la route home, jamais sur dashboard/fiches publiques/etc.
- LCP préservé par fallback SVG statique affiché immédiatement, swap quand le canvas est prêt.
- `IntersectionObserver` met la boucle RAF en pause hors-écran (0 % CPU quand on scrolle plus bas).
- `prefers-reduced-motion` → on ne charge même pas le module WebGL, on reste sur le SVG.
- DPR plafonné à 2 (au-delà : invisible à l'œil, cuit le GPU mobile).

**Conséquences**
- Une dépendance frontend supplémentaire (`ogl@^1.0.11`).
- Maintien possible par un développeur seul (shaders GLSL ES 1.0 documentés, sans abstractions surcouches).
- Coût mesuré (en prod) : +0 KB sur le bundle initial des autres routes, +27 KB sur le chunk de la home (lazy), 1-3 % CPU desktop quand visible.
- **Implémentation prod** (PR #61 + #63 + #64) : `apps/frontend/src/lib/components/HeroPulsar.svelte` — SVG fallback inline rendu synchrone, OGL dynamic-imported sur mount, IntersectionObserver pause/reprise, prefers-reduced-motion skip WebGL, DPR cap, canvas en `alpha: true`/`premultipliedAlpha`, edge-fade alpha pour dissolution dans le fond de la `<section class="hero">`.

**Pitfalls rencontrés (à connaître pour future maintenance)**
- OGL détecte les uniforms array via `Array.isArray()` : il faut passer `Array<Array<number>>`, **pas** un `Float32Array` (qui échoue silencieusement avec « Active uniform xxx[0] has not been supplied »).
- En WebGL1 (ANGLE/D3D sur Windows), `break` ou `continue` dépendant d'un uniform dans une boucle peuvent être rejetés par le driver. Pattern adopté : masque multiplicatif `step(float(i)+0.5, float(uCount))` et toutes les itérations exécutées.
- `pow(x, y)` avec `x < 0` retourne `NaN` en GLSL — qui se propage et noircit toute la frame via `mix`. Toujours `max(x, 0.0)` avant `pow`.
- Le tonemap Reinhard `col / (1.0 + col)` écrase les couleurs très brillantes (RGB ~1.5 chacun) vers le gris. Pour conserver une teinte forte, **pré-compenser** : utiliser des valeurs HDR > 1.0 avec ratios bleu-dominants marqués.
- Sur le node count : la distribution angulaire `(i / N) * 2π` doit utiliser `N = NODE_COUNT` exactement, pas un littéral hardcodé — sinon les nœuds 0 et N se superposent à 360° quand on change `NODE_COUNT`.

**Mise à jour 2026-05-28 (PR #83)**
Refonte complète portée depuis `/sandbox/hero`. La sandbox tunable a servi exactement à l'usage prévu : 12 passes d'itération avec retours utilisateur en boucle courte, puis port d'une seule passe vers le composant prod. Apports majeurs : graphe × 1.3, naine bleue-blanche type Sirius B (rim bleu + centre blanc-chaud, plus de bleu électrique), anneau chromosphérique au limbe (à la place des flares noise-driven qui dessinaient des halos désaxés), nouvelle palette 8 couleurs matérielles, data-pulse comète sur les connexions, trails orbitaux (ring buffer 6 frames), biome stable par identité de nœud (uniform `uNodeIdx`). Le contrat de perf (lazy import, fallback SVG synchrone pour LCP, IntersectionObserver pause, prefers-reduced-motion, DPR ≤ 2, canvas alpha premultiplié) est intact. La topologie de graphe (lune + Y-fork virtuel) et la perspective 3D ligne/pulsar font l'objet d'une **ADR-026** distincte.

---

## ADR-001 — Stack backend : FastAPI + PostgreSQL + DuckDB + dbt

**Date** : 2026-04 (phase de planification)

**Contexte**
Le projet doit servir à la fois de produit pour les créateurs et de pièce maîtresse dans un portfolio Data Engineer. Le développement initial se fait en solo avec assistance IA, sur 1 semaine pour un prototype démontrable.

**Options envisagées**
- Next.js full-stack (rejetée : peu différenciant pour un profil Data Engineer, lourdeur du doublement HTML+JSON)
- Rust pour le backend (rejetée : courbe d'apprentissage incompatible avec 1 semaine MVP, pas un signal Data Engineer fort)
- FastAPI + PostgreSQL + DuckDB + dbt (retenue)

**Justifications**
- Python + FastAPI : maîtrise par les LLMs maximale (efficacité du dev assisté IA), écosystème data dense
- PostgreSQL pour le transactionnel : standard, fiable
- DuckDB pour les analytics : moderne, valorisant pour le portfolio, parfait pour les requêtes sur le graphe de citations
- dbt-core sur DuckDB : signal Data Engineer fort, transformations versionnées et testées

**Conséquences**
- Bon TTM (time to market)
- Stack moderne et valorisable
- Pas de Rust en phase 1 — éventuelle migration de modules critiques en phase 3 (c2pa-rs notamment)

---

## ADR-002 — Frontend : SvelteKit en TypeScript

**Date** : 2026-04

**Contexte**
Le front doit être performant, beau, et rapide à développer. Pas de surcouche framework UI lourde.

**Options envisagées**
- Next.js (rejetée : lourdeur, duplication HTML+JSON, peu différenciant)
- SvelteKit (retenue)
- Astro avec îlots React (envisagée : très performante mais moins de cohérence pour une SPA-like)

**Justifications**
- SvelteKit : syntaxe ultra-claire, bundle léger, excellent rendu serveur
- Compatible avec un déploiement Vercel/Netlify gratuit
- Maîtrisé par les LLMs

**Conséquences**
- Apprentissage léger nécessaire si non maîtrisé
- Pas de duplication HTML+JSON contrairement à Next.js

---

## ADR-003 — Cryptographie en MVP : Ed25519 réel, sans intégration C2PA

**Date** : 2026-04

**Contexte**
Décider du niveau d'investissement crypto pour la semaine 1.

**Options envisagées**
- Tout simulé (rejetée : creux)
- Hash SHA-256 réel + signature Ed25519 réelle, sans C2PA (retenue)
- Intégration complète c2pa-rs (rejetée pour la phase MVP, prévue pour la phase 3)

**Justifications**
- Hash et signature réels sont peu coûteux à implémenter (`cryptography` Python)
- Format C2PA peut être adopté plus tard sans refactoring majeur (signatures Ed25519 réutilisables)

**Conséquences**
- MVP techniquement sérieux dès le départ
- Migration C2PA prévue en phase 3 sans refonte du modèle de données

---

## ADR-004 — OAuth en MVP : Google uniquement

**Date** : 2026-04

**Contexte**
Décider du provider d'identité pour le MVP.

**Options envisagées**
- Pas d'OAuth (rejetée : creux)
- GitHub OAuth seul (envisagée)
- Google OAuth seul (retenue)
- Multi-provider (rejetée pour MVP : trop de setup)

**Justifications**
- Google couvre la quasi-totalité des créateurs cible (un compte Google est universel)
- Setup ~2-3h vs jours pour OAuth multi-provider
- Extension prévue à YouTube en phase 2 (qui passe par Google OAuth)

**Conséquences**
- Setup OAuth Google nécessaire dès la phase MVP
- Architecture d'identité prévue pour accueillir d'autres providers en phase 2

---

## ADR-005 — Snapshots de sources : API Wayback Machine

**Date** : 2026-04

**Contexte**
Décider du mécanisme d'archivage des URLs sources.

**Options envisagées**
- Pas de snapshots (rejetée : creux)
- API Wayback Machine d'Internet Archive (retenue)
- Snapshots propres via Puppeteer/Playwright (rejetée pour MVP : complexité)

**Justifications**
- Wayback Machine : gratuit, fiable, mondialement reconnu
- L'API `https://web.archive.org/save/<url>` est simple à intégrer
- Pas de stockage côté Filum nécessaire en phase 1

**Conséquences**
- Dépendance externe à Internet Archive en phase 1 — acceptable
- Investigation pour snapshots propres en phase 2-3 si volumétrie ou besoins de contrôle

---

## ADR-006 — Saisie des sources : commencer par formulaire manuel

**Date** : 2026-04

**Contexte**
Le créateur entre ses sources dans la fiche. Trois flux possibles : manuel, extraction IA depuis texte, import standard (Zotero/BibTeX/RIS).

**Options envisagées**
- Formulaire manuel uniquement (retenue pour MVP semaine 1)
- Extraction IA depuis du texte collé (prévue pour phase 2)
- Import Zotero/BibTeX/RIS (prévu pour phase 3)

**Justifications**
- Formulaire manuel : aucun risque, base solide
- L'extraction IA et l'import standardisé sont des accélérateurs de saisie ajoutés ensuite

**Conséquences**
- Friction utilisateur initiale plus élevée
- Architecture API conçue pour accepter plusieurs flux d'entrée dès le départ (un endpoint qui accepte une liste structurée de sources, quelque soit la source amont)

---

## ADR-007 — Déploiement MVP : Railway + Vercel/Netlify

**Date** : 2026-04

**Contexte**
Le MVP doit être déployable rapidement et gratuitement.

**Options envisagées**
- Vercel full-stack (rejetée car backend Python pas idéal sur Vercel Serverless)
- Railway pour le backend + Vercel/Netlify pour le frontend (retenue)
- Scaleway dès le MVP (rejetée : surcoût d'apprentissage Docker)
- Fly.io ou Render (envisagées : alternatives valables à Railway)

**Justifications**
- Railway : tier gratuit suffisant pour MVP, Postgres inclus, déploiement en 5 min
- Vercel ou Netlify pour SvelteKit : déploiement instantané, CDN
- Scaleway prévu pour phase 3 (production souveraine européenne)

**Conséquences**
- Migration vers Scaleway prévue dès que l'audience justifie le narratif souverain
- Infrastructure totalement gratuite en phase MVP

---

## ADR-008 — Nom du projet : Filum (provisoire)

**Date** : 2026-04

**Contexte**
Choisir un nom de code pour le projet.

**Options envisagées** : Filum, Stemma, Colophon, Upstream, Tracé, Provenance

**Retenue** : Filum, comme nom de code de travail

**Justifications**
- Court, latin, évoque la filiation et le fil généalogique
- Distinctif (pas de doublons en tech ou en crypto)
- Portable linguistiquement
- Décision révisable avant le lancement public

**Conséquences**
- Domaines à réserver (`filum.app`, `filum.org`, `filum.eu`, `filum.io`)
- Décision définitive à prendre avant le lancement public (phase 2)

---

## ADR-009 — Chiffrement AES-GCM au lieu de Fernet

**Date** : 2026-05

**Contexte**
Chiffrement de la clé privée Ed25519 de chaque utilisateur avant stockage en base.

**Options envisagées**
- Fernet (standard dans la communauté Python, simple) — rejeté car obsolète
- AES-GCM avec `cryptography` (retenue)

**Justifications**
- AES-GCM est le standard moderne, authentifié (AEAD), recommandé par les autorités (ANSSI, NIST)
- `cryptography` est déjà une dépendance du projet pour Ed25519
- Fernet est une surcouche qui masque les détails cryptographiques (pédagogiquement moins intéressant pour un portfolio Data Engineer)

**Conséquences**
- Implémentation légèrement plus verbeuse que Fernet
- Code crypto plus transparent et valorisable

---

## ADR-010 — `case_sensitive=True` dans pydantic-settings : variables d'env en lowercase

**Date** : 2026-05

**Contexte**
La classe `Settings` utilise `case_sensitive=True` dans `SettingsConfigDict`. Cela casse la lecture des variables d'environnement en SCREAMING_SNAKE_CASE.

**Options envisagées**
- Passer `case_sensitive=False` (rejeté : moins de contrôle sur les collisions de noms)
- Conserver `case_sensitive=True` et utiliser des noms lowercase dans les env vars partout (retenue)

**Justifications**
- Cohérence avec la définition exacte des champs dans la classe Settings
- `case_sensitive=True` évite les ambiguïtés (ex: `database_url` vs `DATABASE_URL`)
- GitHub Actions gère correctement les env vars lowercase

**Conséquences**
- `.env` : utiliser `database_url`, `session_secret`, etc. (pas `DATABASE_URL`)
- CI/CD : env vars en lowercase dans `ci.yml` et `cd.yml`
- Conftest de test : env vars en lowercase avant import des modules app

---

## ADR-011 — pnpm 11 : workaround `ERR_PNPM_IGNORED_BUILDS`

**Date** : 2026-05

**Contexte**
pnpm 11 a introduit une politique stricte sur les build scripts (`onlyBuiltDependencies`). esbuild (dépendance transitive de SvelteKit/Vite) n'est pas autorisé à exécuter ses postinstall scripts, causant `ERR_PNPM_IGNORED_BUILDS` avec exit code 1.

**Options envisagées**
- `onlyBuiltDependencies` dans `package.json` (essayé, ignoré par pnpm 11 en CI)
- `.pnpm-approve-builds.json` (essayé, ignoré par pnpm 11)
- `pnpm config set onlyBuiltDependencies` + `|| true` sur install (retenue)

**Justifications**
- La config dans `package.json` est respectée par pnpm local mais pas systématiquement en CI
- `.pnpm-approve-builds.json` est déprécié par pnpm 11
- `|| true` est un workaround pragmatique : l'install réussit malgré le warning, l'erreur exit code est supprimée

**Conséquences**
- Toute job CI frontend avec `pnpm install` doit avoir `|| true`
- La config `pnpm config set onlyBuiltDependencies` reste présente comme bonne pratique
- À réévaluer quand pnpm 11 sera plus mature ou que le bug sera fixé

---

## ADR-012 — Tests DB async : SQLite + aiosqlite, import explicite des modèles

**Date** : 2026-05

**Contexte**
Tests unitaires des services qui dépendent de la base de données (AuthService). Nécessité d'une isolation par test et de la création/destruction des tables.

**Options envisagées**
- PostgreSQL de test via Docker (rejeté : complexité, CI déjà configurée en SQLite)
- SQLite + aiosqlite avec fixture `db_session` créant les tables par test (retenue)

**Justifications**
- SQLite est utilisée en CI (ci.yml : `database_url: sqlite+aiosqlite:///./test.db`)
- Pas de dépendance Docker pour les tests unitaires
- aiosqlite compatible avec SQLAlchemy async

**Piège évité**
`Base.metadata.create_all` ne crée rien si les modèles ne sont pas importés. En conftest, il faut importer explicitement `app.models.user`, `app.models.biblio_card`, etc. avant d'appeler `create_all`, car SQLAlchemy ne découvre les tables qu'au moment de l'import de chaque modèle.

**Conséquences**
- `conftest.py` importe tous les modèles avant `create_all`
- Tables créées et détruites à chaque test (via `db_session` fixture)
- Performances acceptables (38 tests en ~11s)

---

## ADR-013 — Pin pnpm 10 via `packageManager` + suppression des workarounds CI

**Date** : 2026-05

**Contexte**
Le job `build-frontend` échouait sur `pnpm run build`. Investigation :

1. **Cause racine pnpm 11** : `pnpm install` retourne exit 1 sur `ERR_PNPM_IGNORED_BUILDS` (esbuild postinstall script non approuvé), **même si toute la résolution + l'écriture sur disque ont réussi** (les binaires esbuild proviennent de sous-packages prebuilds, le postinstall était cosmétique). pnpm 11 réexécute en plus un `pnpm install` interne avant chaque `pnpm run <script>` (`verify-deps-before-run=true` par défaut), reproduisant l'exit 1 fatalement.
2. **Aggravation** : pnpm 11 réécrit `pnpm-workspace.yaml` à chaque install pour y insérer un bloc placeholder malformé `allowBuilds: esbuild: set this to true or false`, qui empoisonne la suite du fichier et invalide le `onlyBuiltDependencies` qu'on essaye d'y mettre.
3. **Cause racine secondaire** : `svelte.config.js` portait `kit.vitePlugin.inspector`, option supprimée dans SvelteKit 2 (`Unexpected option config.kit.vitePlugin`) — invisible tant que (1) bloquait avant.

**Options envisagées**
- Empiler des workarounds pnpm 11 : `|| true` sur install + `pnpm exec` + `verify-deps-before-run=false` (rejetée : 3 workarounds pour 1 bug, masque la cause)
- Migrer vers npm ou yarn (rejetée : coût de migration disproportionné)
- **Pin pnpm 10 via `packageManager: "pnpm@10.33.4"` dans `package.json`** (retenue)

**Justifications**
- pnpm 10 n'a pas le comportement strict-exit-1 ni le re-install implicite — l'ancien comportement est ce que tout l'écosystème SvelteKit assume aujourd'hui
- `pnpm/action-setup@v4` honore automatiquement le champ `packageManager` → CI alignée avec local et avec le Dockerfile (qui utilise déjà `corepack enable pnpm`)
- Permet `--frozen-lockfile` en CI (builds déterministes)
- Aucun fichier supplémentaire (pnpm-workspace.yaml, .pnpm-approve-builds.json) — restaure `pnpm.onlyBuiltDependencies` dans `package.json` (format pnpm 10 standard)

**Conséquences**
- `pnpm install` exit 0, `pnpm run build` direct, CI lisible
- Mêmes versions de pnpm partout : CI, local, Docker
- `.pnpm-approve-builds.json` supprimé (artefact pnpm 11 non lu par pnpm 10)
- `pnpm-workspace.yaml` supprimé (réécrit par pnpm 11 avec du junk, inutile pour ce projet mono-package)
- Bloc `kit.vitePlugin.inspector` retiré de `svelte.config.js`
- Suppression dans CI : `|| true` sur install, `pnpm exec vite build`, `pnpm config set verify-deps-before-run false`, `continue-on-error: true` sur Type Check
- `lint-frontend` et `test-frontend` gardent leur `|| true` : ils ont des bugs réels (deps eslint manquantes, incompat Svelte 5 + testing-library) à traiter dans une PR séparée (cf. STATE.md follow-ups)
- À surveiller : si SvelteKit pousse pnpm 11+ exigé, on remontera le pin

**Reproductibilité**
```bash
cd apps/frontend
pnpm install --frozen-lockfile     # exit 0
pnpm run build                     # ✓ built in ~10s
```

---

## ADR-014 — Migration `python-jose` → `PyJWT`

**Date** : 2026-05

**Contexte**
`actions/dependency-review-action@v4` (PR check GitHub) bloque le merge sur `ecdsa@0.19.2 — Minerva timing attack on P-256 (HIGH)`. `ecdsa` est tiré comme transitive dep par `python-jose`. Filum n'utilise PAS ECDSA (HS256 = HMAC symétrique pour JWT, Ed25519 via `cryptography` pour signatures de fiches) → CVE non exploitable, mais bloquant côté process.

**Options envisagées**
- Allowlist le CVE (rejetée : la lib `python-jose` est aussi peu maintenue ; on stocke une dette sans valeur)
- Migrer vers `authlib` (rejetée : surdimensionné, on n'utilise que encode/decode)
- **Migrer vers `PyJWT`** (retenue : standard de fait, API identique à jose, mainteneurs actifs)

**Justifications**
- API identique : `jwt.encode(payload, secret, algorithm='HS256')` et `jwt.decode(token, secret, algorithms=['HS256'])` — 0 changement de logique
- Exception hierarchy plus propre : `jwt.InvalidTokenError` est parent de `ExpiredSignatureError`, `InvalidSignatureError`, `DecodeError` → couvre les 3 cas testés en une seule clause
- Pas de transitive deps cryptographiques inutiles (ecdsa, pyasn1, rsa supprimés)
- Type hints natifs : suppression d'un `# type: ignore` dans `auth.py`

**Conséquences**
- 4 fichiers modifiés : `pyproject.toml`, `uv.lock`, `app/services/auth.py`, `tests/unit/test_auth.py`
- `uv.lock` : -65 lignes (suppression de ecdsa, pyasn1, rsa)
- mypy + ruff propres
- Dependency Review CI passe (plus de CVE haute sévérité)
- Aucun changement de comportement runtime

---

## ADR-015 — Déploiement Railway via intégration GitHub native (pas de workflow CD)

**Date** : 2026-05

**Contexte**
Le workflow `cd.yml` initial ne fonctionnait pas :
- YAML invalide : `workflow_dispatch:` était au top-level au lieu d'être nesté sous `on:` → la CI rejetait le fichier au parsing (0 jobs, 0s runtime)
- `railway-devrel/railway-actions@v1` n'existe pas sur le marketplace GitHub (fiction d'un LLM lors du scaffolding initial)
- Variables d'env passées en UPPERCASE (`DATABASE_URL`, etc.) contradictoire avec ADR-010 → silent fallback aux defaults
- Scope démesuré pour un MVP : staging + production avec 10 secrets distincts

**Options envisagées**
- Réécrire `cd.yml` from scratch avec le CLI Railway (`@railway/cli`) ou `bervProject/railway-app` (rejetée : duplique ce que Railway fait nativement)
- Utiliser GitHub Actions pour build une image Docker puis Railway pour la pull (rejetée : 2 sources de vérité, latence)
- **Intégration GitHub native de Railway** (retenue) : Railway watch le repo, build et deploy automatiquement à chaque push sur main

**Configuration Railway adoptée**
- Service backend lié à `Mathias-PP/filum`, branch `main`
- **Root Directory** : `apps/backend`
- **Builder** : Dockerfile (auto-détection `apps/backend/Dockerfile`)
- **Wait for CI** : enabled — Railway attend que GitHub Actions soit vert avant de déployer
- **Healthcheck Path** : `/health`
- **Port** : injecté via `$PORT` dans le `CMD` Docker (`${PORT:-8000}`)
- Postgres plugin Railway lié via référence `${{Postgres.DATABASE_URL}}`
- Domaine généré : `filum-production-07bb.up.railway.app`

**Variables d'env Railway**
Toutes en lowercase (ADR-010) :
```
database_url           = ${{Postgres.DATABASE_URL}}
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
backend_base_url       = https://filum-production-07bb.up.railway.app
frontend_base_url      = http://localhost:5173 (à update quand frontend déployé)
cors_origins           = ["http://localhost:5173"]
debug                  = false
```

`google_*`, `wayback_api_key`, `duckdb_path`, `api_v1_prefix`, `database_pool_size`, `database_max_overflow` : non configurés, defaults dans `config.py` suffisent.

**Conséquences**
- 1 fichier workflow en moins (`cd.yml` supprimé)
- Pas de secrets Railway dans GitHub Actions à gérer
- Logs de déploiement dans le dashboard Railway (meilleure UX que GHA pour ce cas)
- Migrations Alembic auto-exécutées au boot via le `CMD` Docker
- Le port dynamique impose un patch Dockerfile (`${PORT:-8000}`)
- La référence Postgres expose un URL sans `+asyncpg` → un `field_validator` dans `config.py` coerce automatiquement (`postgresql://` → `postgresql+asyncpg://`)
- Si on veut un jour un workflow déclencheur (release tags, smoke tests post-deploy), il faudra le réécrire depuis zéro avec le CLI Railway

**Validation**
```
curl https://filum-production-07bb.up.railway.app/health
→ {"status":"ok","version":"0.1.0"}

curl https://filum-production-07bb.up.railway.app/health/database
→ {"status":"ok","database":"connected"}
```

---

## ADR-016 — Graphe interactif D3 + relation `Source.parent_source_id`

**Date** : 2026-05

**Contexte**
La vision (`.docs/00-vision.md` lignes 50-59) et le product spec (`.docs/01-product-spec.md` lignes 96-101) promettent une "carte interactive des sources" inspirée de Pappers et Obsidian comme l'un des trois angles d'effet wow du MVP. La page publique livrée ne montrait qu'une liste accordion plate. Par ailleurs la "structure du raisonnement" (qui cite qui) n'était pas matérialisée en BDD.

**Options envisagées**
- Bibliothèque tierce type `vis-network` ou `cytoscape.js` (rejetée : poids + opacité du rendu, contrôle fin du design system difficile)
- Rendu statique côté serveur via Mermaid ou Graphviz (rejetée : pas d'interaction, pas de drag/zoom, valeur perçue inférieure)
- **D3.js v7 force-directed simulation + composant Svelte 5 dédié** (retenue)
- Stocker la lineage des sources en BDD via `Source.parent_source_id` (FK self-référente), pour que le graphe soit data-driven et que la "provenance/lineage" du projet soit matérialisée (retenue)

**Justifications**
- D3 v7 déjà installé en dépendance directe (avec `@types/d3`) → pas de nouvelle dette technique
- Contrôle fin du rendu (couleurs design system, taille par `authority_level`, halo pivot, dimming au hover, animation cascade) impossible avec une lib clé-en-main sans surcharger
- `parent_source_id` matérialise la promesse "structure du raisonnement" et permet une visualisation hiérarchique (sources de premier niveau près du centre, sources de second niveau en périphérie, plus petites, reliées en pointillés à leur parent)
- Compatible CSR-only (`ssr=false` dans `+layout.ts`) → pas besoin de guard browser

**Implémentation**
- Migration Alembic 003 : `op.add_column('sources', 'parent_source_id')` nullable + index
- `app/models/source.py` : champ + relationship auto-référentielle `parent`
- `app/schemas/source.py` : champ exposé sur `SourceBase`/`Create`/`Update`/`Response`
- `apps/frontend/src/lib/api/types.ts` : `Source.parent_source_id: string | null`
- `apps/frontend/src/lib/components/SourceGraph.svelte` (~310 lignes) : simulation D3, drag, zoom/pan/reset, cascade, légende, ResizeObserver
- `apps/frontend/src/lib/components/SourceDetailPanel.svelte` (~140 lignes) : side panel desktop / bottom sheet mobile, Escape, navigation vers le parent
- `apps/frontend/src/lib/utils/source-colors.ts` : single source of truth des couleurs (réutilisée par `SourceTypeBadge`)
- Seed `apps/backend/app/scripts/seed_demo.py` : remplace le placeholder par 14 sources réelles sur la neuroscience de la mémoire + 6 arêtes `parent_source_id`. Nouveau slug `memoire-et-cerveau` ; l'ancienne fiche `filum-demo` reste en BDD (orpheline mais signée) pour ne pas casser une éventuelle URL externe

**Garantie cryptographique**
La payload canonical_hash signée par `CardService.publish_card` (et vérifiée par `verify_card`) **N'inclut PAS** `parent_source_id`. La relation de citation est purement structurelle / graphique. Les signatures Ed25519 existantes sur les fiches déjà publiées restent valides après la migration.

**Conséquences**
- Page publique enfin alignée avec la vision : graphe au-dessus de la fold, panneau latéral au clic, sources de sources en périphérie, identité visuelle cohérente
- +1 migration (003), +3 fichiers frontend, +1 utilitaire de couleurs
- Bundle Vercel +80 KB minifié (d3 force/drag/zoom/selection) — acceptable pour MVP, tree-shaking actif
- L'index `ix_sources_parent_source_id` accélère la résolution d'éventuelles requêtes "qui cite X ?"
- Aucun changement de comportement runtime sur les endpoints existants ; tests existants non impactés (le champ est nullable et optionnel)

## ADR-018 — OpenGraph dynamique avec Pillow (backend)

**Date** : 2026-05-13

**Contexte**
Les fiches publiques avaient des meta tags `og:title`, `og:description`, mais pas `og:image`. Les aperçus de liens sur les réseaux (Twitter/X, Discord, LinkedIn) et les moteurs IA (Perplexity, SearchGPT) affichaient un lien nu sans visuel. Le développeur demande d'implémenter les images OG dynamiques.

**Options envisagées**
- `@vercel/og` / Satori + resvg-js côté frontend (SvelteKit server endpoint) — rejeté car nécessite `@sveltejs/adapter-vercel` explicite et dépendances lourdes (satori, resvg-js)
- Service externe comme `og-image.vercel.app` (rejeté : dépendance tierce, pas de contrôle)
- Backend Python avec Pillow (retenue)

**Justifications**
- Pillow est simple, stable, sans runtime complexe (pas de navigateur headless, pas de WASM)
- Railway (backend) peut servir des images PNG statiques sans problème
- Police DejaVu Serif disponible sur Ubuntu/Railway (fallback interne si absente)
- Le endpoint `GET /api/v1/og?title=&creator=` est simple à cache-CDN (Cache-Control à ajouter plus tard)
- Permet un contrôle fin du design (couleurs, typo, layout) sans passer par du HTML+CSS+rendering

**Implémentation**
- `app/services/og_image.py` : `generate_og_image(title, creator)` → bytes PNG (Pillow)
- Fond sombre #0F172A (slate-900), accent #3B82F6 (blue-500), texte blanc
- Titre centré en DejaVu Serif Bold 48px, wrapper à 30 caractères
- Créateur en subtitle 24px, footer "filum.app — bibliographie vérifiable"
- `app/api/v1/endpoints/og.py` : route `GET /og` avec paramètres `title` (required) et `creator` (optional)
- Frontend : `og:image` et `twitter:image` pointent vers `{API_BASE}/api/v1/og?title=...&creator=...`

**Conséquences**
- +1 dépendance backend : `Pillow>=12.2.0` (~12 MB installé)
- +2 fichiers backend (service + endpoint)
- +1 fichier frontend modifié (meta tags sur la fiche publique)
- Image générée à la volée (pas de cache pour l'instant — à ajouter si le trafic augmente)
- Les polices DejaVu sont présentes sur Railway (Ubuntu) et en local — si absentes, Pillow utilise un fallback

## ADR-019 — La signature porte sur le lien créateur·ice ↔ contenu, plus sur la fiche bibliographique

**Date** : 2026-05-14

**Contexte**
Le MVP signe chaque fiche bibliographique au moment du `publish` : `canonical_hash` + `signature` Ed25519 sur `BiblioCard` (titre + sources + métadonnées canonicalisées via RFC 8785). Conséquence implicite acceptée jusqu'ici : la fiche devient immuable ; toute modification invaliderait la signature et nécessiterait dé-publication / re-publication, donc en pratique elle est figée.

L'utilisateur (Mathias) constate que ce modèle est contre-productif :
- Les fiches sont des documents vivants. Corriger une coquille, ajouter une source plus tard, raffiner une annotation : autant de gestes légitimes que l'immuabilité bloque.
- Ce qui compte vraiment, ce que les usagers tiers veulent vérifier, ce n'est pas la composition exacte de la bibliographie à un instant T mais : « tel·le créateur·ice revendique-t-il·elle bien tel contenu original (vidéo, article, podcast) à telle date ? »

**Décision**
La crypto Ed25519 / SHA-256 / RFC 8785 est conservée mais l'objet signé change. **Un seul type d'objet attesté** : le **lien créateur·ice ↔ contenu**, sous forme d'un triplet `(creator_id, content_url, attested_at)`, signé. Cela prouve « tel·le créateur·ice revendique telle URL comme contenu mien à telle date ».

Les fiches bibliographiques (`BiblioCard`) **redeviennent mutables** : modification libre tant que le créateur est authentifié. Suppression des colonnes `canonical_hash`, `signature`, `signed_at` du contrat de signature (`published_at` peut rester pour l'horodatage UX, sans rôle cryptographique).

Le **profil créateur·ice n'est PAS signé** en tant que tel. Seule sa clé publique est exposée publiquement pour permettre la vérification des attestations qu'il·elle a émises. L'identité Filum reste portée par l'authentification (Google OAuth) et la possession démontrée de la clé privée.

**Justifications**
- Aligne le produit sur le besoin réel (vérifier la paternité d'un contenu) plutôt que sur un fantasme d'immuabilité bibliographique
- Décolle la crypto du flux d'édition : on peut éditer une fiche autant qu'on veut sans rien resigner
- Simplifie le modèle mental : « ce que Filum garantit, c'est mon lien à un contenu, pas mon brouillon de bibliographie »
- Modèle à un seul type d'objet signé : plus simple à implémenter et à expliquer qu'un système à deux types (profil + content_link)
- Ouvre la voie naturelle à la collaboration sur les fiches (Phase 2)

**Conséquences code (à implémenter dans PR backend dédiée, non incluse dans #31)**
- Nouvelle table `content_attestations` : `(id, user_id, content_url, attested_at, canonical_hash, signature)`. Unicité sur `(user_id, content_url)` à discuter (un même créateur revendique-t-il une URL une seule fois, ou peut-il la re-revendiquer ultérieurement ?)
- Suppression de la signature sur `biblio_cards` : migration `006_remove_card_signature` qui dropte `canonical_hash`, `signature`, `signed_at` (et garde `published_at` sans rôle crypto)
- Endpoint `POST /cards/{id}/publish` redevient un simple flip de statut, plus de crypto
- Nouvel endpoint `POST /attestations/content` (création) + `GET /attestations/{id}/verify` (vérification publique)
- Liaison `BiblioCard.content_url` → `ContentAttestation` : à exposer dans la fiche publique pour afficher l'attestation correspondante
- Refonte de `seed_demo.py` : plus de re-signature de fiche, à la place une attestation de contenu pour la vidéo démo « Mémoire et cerveau »
- Frontend types `BiblioCard`/`PublicCard` : supprimer `canonical_hash`/`signature`/`signed_at` (ou garder `null`-ables le temps de la migration). Ajouter un type `ContentAttestation`
- Tests : `test_canonical_hash.py` / `test_crypto.py` rebasculer sur les attestations de contenu
- Specs `.docs/01..04, 08` : sections crypto à réécrire (objet signé, schéma, API)
- `agent/PITFALLS.md` item 1.3 : la règle « ne jamais modifier le payload signé » s'applique maintenant aux attestations de contenu

**Conséquences user-facing (incluses dans PR #31)**
- Page `/security` réécrite : un seul type d'objet signé expliqué (le lien créateur·ice ↔ contenu)
- Pages `/`, `/features`, `/about`, `/roadmap` : reformulation « attestation de contenu », plus de mention d'immuabilité de fiche
- Fiche publique `@{creator}/{card}` : footer ne montre plus la signature hash de la fiche ; affiche « Contenu revendiqué par son créateur·ice » avec lien vers `/security`. La date affichée est `published_at` (sans rôle crypto)
- FAQ « Puis-je modifier une fiche publiée ? » supprimée (réponse devient « oui »)

**Transition**
La prod tourne encore avec l'ancien schéma. Le frontend de PR #31 ne *lit* plus `card.signature` / `card.signed_at` ; les champs restent renvoyés par l'API mais ignorés. Pas de casse côté prod. La PR backend dédiée fera la migration descendante propre et ajoutera la table `content_attestations`.

---

## ADR-020 — Refonte de la taxonomie des sources en 3 axes orthogonaux

**Date** : 2026-05-14

**Contexte**

L'enum `source_type` du MVP mélange deux dimensions distinctes :
- des **catégories** de contenu : `peer-reviewed`, `press`, `institutional`, `original`
- des **formats** de média : `video`, `image`

Conséquences observées :
- Confusion à l'usage : où classer une vidéo de chercheur sur YouTube ? Sous `video` (format) ou sous `peer-reviewed` (autorité) ? Aucun choix n'est satisfaisant.
- Le graphe public coloré par `source_type` mixe des signaux hétérogènes, le lecteur ne sait pas si la couleur encode la nature de l'auteur, le format ou la catégorie.
- Le champ legacy `authority_level` (`high`/`medium`/`low`) survit sans usage UI et porte un jugement non vérifiable, identifié comme dette dans STATE.md.
- Cosmétique : le texte d'accueil utilise « contenu original que vous revendiquez » alors que `original` est aussi un type de source — collision sémantique.

Le projet étant pré-MVP (seules données = seed + comptes dev), une refonte agressive sans backfill complexe est encore possible. Une fois des créateurs onboardés, ce sera très coûteux à corriger.

**Options envisagées**

1. **Renommage simple sur un seul axe** : remplacer les 6 valeurs par 6 valeurs cohérentes sur un seul axe épistémique. Migration légère. Rejeté : ne résout pas le problème de fond (mélange format/catégorie/auteur).
2. **Hybride** : 1 axe principal obligatoire (~6 valeurs simples) + 3 champs optionnels riches (format, catégorie détaillée, type d'auteur). Lisibilité préservée par défaut. Rejeté par l'utilisateur : préférence pour la rigueur explicite à l'entrée.
3. **3 axes orthogonaux tous obligatoires** : `format`, `category`, `author_kind`. Graphe coloré par `author_kind`. **Retenue.**

**Décision**

Trois colonnes obligatoires sur `Source`, valeurs en base = strings kebab-case (cohérent avec ADR-010 sur la lowercase) :

- `format` (5 valeurs) : `texte`, `video`, `image`, `audio`, `data`
- `category` (12 valeurs) : `article-scientifique`, `preprint`, `article-presse`, `communique`, `documentaire`, `interview`, `podcast`, `blog`, `post-social`, `livre`, `page-web`, `notes`
- `author_kind` (9 valeurs) : `chercheur`, `media`, `institution-publique`, `gouvernement`, `ecole`, `laboratoire`, `entreprise`, `asso`, `individu`

Le **graphe est coloré par `author_kind`**, dimension la plus informative pour la confiance épistémique (« qui dit ça ? »). Format et catégorie apparaissent en badges neutres dans le panneau de détail de chaque source.

`source_type` et `authority_level` sont **supprimés** (migration 007).

**Justifications**
- Sépare des axes orthogonaux : on peut décrire un podcast de chercheur (`format=audio`, `category=podcast`, `author_kind=chercheur`) sans devoir choisir une seule étiquette.
- Aligne la couleur du graphe sur la dimension de confiance, signal principal pour un lecteur tiers.
- Élimine `authority_level` (jugement non-vérifiable) au profit d'une description structurelle (qui est l'auteur).
- Pré-MVP = fenêtre acceptable pour rompre la compatibilité.

**Conséquences code**
- Migration Alembic `007_taxonomy` : add 3 colonnes nullable → backfill via mapping → ALTER NOT NULL → drop `source_type` + `authority_level`. ID ≤ 32 chars, pas de `op.create_index` redondant (cf. CLAUDE.md pièges).
- Modèles + schémas + endpoints backend mis à jour ; seed_demo.py réécrit.
- Frontend : `source-colors.ts` → `author-colors.ts` (palette 9), `SourceTypeBadge` éclaté en `AuthorKindBadge` + `FormatBadge` + `CategoryBadge`, `SourceGraph` coloré par `author_kind`, formulaire de création passe d'1 dropdown à 3.
- Bug latent corrigé en parallèle : `sources.py:138` ne passait pas `parent_source_id` au constructeur `Source(...)`, le champ était silencieusement ignoré à la création via API (le seed le contournait par insertion directe). Documenté en `agent/PITFALLS.md`.
- Garde `sources.py:124` (interdit l'ajout de source sur fiche publiée) retirée pour être cohérent avec ADR-019 (fiches mutables). L'attestation existante reste valide pour sa version horodatée — une politique de re-attestation automatique sera traitée en ADR-021 si nécessaire.
- Page d'accueil : suppression du mot « contenu » dans « chaque contenu original que vous revendiquez » → « chaque création que vous revendiquez » (collision sémantique avec l'ex-`source_type=original`).

**Mapping backfill (best-effort, pré-MVP donc tolérant)**

| Ancien `source_type` | → format | → category | → author_kind |
|---|---|---|---|
| `peer-reviewed` | texte | article-scientifique | chercheur |
| `institutional` | texte | communique | institution-publique |
| `press` | texte | article-presse | media |
| `video` | video | documentaire | media |
| `image` | image | page-web | individu |
| `original` | texte | notes | individu |

Le seed est réécrit derrière avec des valeurs réelles ; les comptes dev peuvent éditer manuellement.

**Follow-ups (hors scope de cette PR)**
- Alignement `BiblioCard.platform` / `BiblioCard.content_type` avec la nouvelle taxonomie (ADR séparé).
- Re-attestation automatique des fiches publiées modifiées (ADR futur).
- Suggestion automatique de taxonomie depuis l'URL extractor (DOI → `category=article-scientifique`, `author_kind=chercheur`).
- Multi-parents pour `Source.parent_source_id` (passer à une table de jonction si demande utilisateur).

---

## ADR-021 — Renommage du projet : Filum → Philum

**Date** : 2026-05-15

**Statut** : **Décidé, non exécuté.** Implémentation à planifier dans une PR dédiée (cf. ADR-022 qui est lié).

**Contexte**

Le nom « Filum » était provisoire (cf. ADR-008). Au moment de chercher un domaine pour la mise en ligne MVP, recherche WHOIS et DNS sur le 2026-05-15 :

| Domaine | Statut | Coût d'acquisition |
|---|---|---|
| `filum.com` | Parqué « Coming Soon » sur Linode (squatteur) | 500-3000 € (négociation auprès du propriétaire) |
| `filum.fr` | Vendu explicitement par Dovendi (revendeur NL) | 300-1500 € |
| `filum.app` | Parking OVH, propriétaire inconnu | 100-500 € (whois requis) |
| `philum.fr` | **Libre, 5,10 € la 1re année / ~7 €/an ensuite** (offert avec Public Cloud Infomaniak) | ~7 €/an |
| `philum.app` | **Libre, ~12-15 €/an** | ~12-15 €/an |

Aucun des trois `filum.*` n'est récupérable sans payer une rançon (300 à 3000 €). Les variantes orthographiques (`filum.eu`, `filum.science`, `filum.io`, etc.) sont moins lisibles ou plus chères que `philum.*`.

**Décision**

Renommer le projet de **Filum** en **Philum**.

Rationale produit : « Philum » se rapproche de **phylum** (rang taxonomique en biologie) et évoque les **arbres phylogénétiques** — métaphore directement alignée avec la promesse de Filum/Philum (cartographier les liens de citation entre sources comme on cartographie l'évolution des espèces). Le glissement orthographique est donc significatif, pas cosmétique : il **renforce** le storytelling produit au lieu de le diluer.

Domaines à acquérir :
- **Primaire** : `philum.fr` (~7 €/an, offert 1re année avec compte Public Cloud Infomaniak — cf. ADR-022)
- **Défensif (à acquérir si budget OK)** : `philum.app` (~12-15 €/an) pour bloquer l'usurpation et préparer l'éventuelle bascule en TLD international plus tard

**Justifications**
- Évite une dépense one-shot de 300 à 3000 € pour récupérer `filum.fr` ou `filum.com`
- `philum` est conceptuellement plus riche que `filum` (lien direct avec phylogénie / taxonomie / arbre des sources)
- TLD `.fr` cohérent avec le choix d'hébergement souverain européen (Infomaniak Suisse, cf. ADR-022)
- Le `.fr` n'est pas un blocage à l'international : pattern standard (BlaBlaCar, Doctolib, Qonto) consiste à démarrer sur `.fr` puis acquérir `.com` plus tard et basculer le canonique. `philum.com` semble libre et restera acquérable à ~12 €/an quand le besoin se présentera.

**Conséquences (à exécuter dans la PR de renommage)**

Renommage textuel dans le repo. Aucune logique applicative impactée — c'est uniquement de la chaîne de caractères. Estimation ~15-25 fichiers à toucher :

- `CLAUDE.md` : titre, mentions de « Filum », « filum.app » dans la roadmap → « Philum », « philum.fr »
- `README.md` : titre, badges, description, URL démo
- `STATE.md` : URL prod, URL démo, titre projet
- `DECISIONS.md` : préface ; les ADR antérieurs gardent leur formulation « Filum » historique (c'est leur datation qui les rend cohérents)
- `CHANGELOG.md` : préface
- `agent/PITFALLS.md`, `agent/README.md`, `agent/memory/PROJECT_SNAPSHOT.md`
- `.docs/00-vision.md`, `01-product-spec.md`, `02-tech-architecture.md`, `04-api-design.md`, `05-design-system.md`, `08-security.md`, `09-naming.md`, `10-mvp-completion-plan.md`, `11-critique-and-improvements.md`, `12-next-steps.md`
- `apps/backend/app/scripts/seed_demo.py` : `lea-marchand.filum.app` → `lea-marchand.philum.fr` (2 occurrences dans les notes Léa Marchand)
- `apps/backend/pyproject.toml` : nom du package `filum-api` → `philum-api`
- `apps/frontend/package.json` : nom `filum-frontend` → `philum-frontend`
- `apps/frontend/src/app.html`, `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `src/routes/about/+page.svelte` : titre, footer « © Filum » → « © Philum », mentions
- `apps/frontend/src/routes/about/+page.svelte` : ajouter une **section dédiée « Pourquoi Philum ? »** expliquant le clin d'œil aux phylums biologiques et aux arbres phylogénétiques (storytelling produit pour les visiteurs curieux)
- `apps/frontend/src/lib/components/Logo.svelte` : à voir si le logo SVG mentionne « F » ou « Filum » ; ajuster si oui (probablement aucun changement car c'est un dessin abstrait)
- `apps/frontend/src/routes/security/+page.svelte`, `features/+page.svelte`, `roadmap/+page.svelte` : mentions « Filum » dans le copy
- `apps/frontend/src/routes/+error.svelte`, `privacy/+page.svelte` : titres et copy
- `infra/` : si template Caddyfile / Dockerfile mentionnent un nom, à mettre à jour
- Variables d'environnement Railway / Vercel : `frontend_base_url`, `backend_base_url` à mettre à jour quand le domaine est branché

**Stratégie de migration en deux temps** : (1) rename code-only sans changer encore l'URL prod (PR ~15 min, frontend reste sur `filum-eight.vercel.app`), (2) achat domaine `philum.fr` + branchement DNS quand prêt (peut être aligné avec ADR-022 ou indépendant).

**Migration des données utilisateurs** : aucune. À ce stade pré-MVP, les comptes dev acceptent un re-login sur le nouveau domaine. Si plus tard des users vrais existent, prévoir une redirection 301 `filum-eight.vercel.app` → nouveau domaine + un mail d'annonce.

---

## ADR-022 — Cible de migration hébergement : Infomaniak Public Cloud (planifiée)

**Date** : 2026-05-15

**Statut** : **Décidé, non exécuté.** Migration mise en attente le 2026-05-15 quand les crédits Railway sont revenus de manière inattendue ($4.86 / 28 jours restants). Conserver la cible Infomaniak comme plan de bascule pour quand Railway deviendra payant.

**Contexte**

Le 2026-05-14, les crédits free Railway sont passés à $0.00. Tentative de migration vers une plateforme gratuite alternative. Le 2026-05-15, les crédits Railway sont revenus à $4.86 (probablement re-crédit mensuel automatique du Hobby Plan, à confirmer côté billing dashboard). Décision : on reste sur Railway pour les ~28 jours restants mais on **fige les choix de migration** pour pouvoir basculer rapidement quand le besoin se représente (fin du free tier, pic de coûts, ou décision de souveraineté).

**Comparaison réalisée le 2026-05-15**

| Solution | Free réel ? | Setup | Verdict |
|---|---|---|---|
| Render free + Neon free | ✅ Oui mais cold start ~30 s après 15 min idle | Très simple | Plan B rapide pour bascule d'urgence sans budget |
| Oracle Cloud Always Free (ARM Ampere) | ✅ Oui à vie, mais pénurie ARM fréquente | Sysadmin nu | Bon technique mais piège « Out of capacity » |
| Hetzner CX22 | ❌ Payant ~4 €/mois | Setup VPS classique | Très bon rapport qualité/prix mais Allemagne |
| Scaleway DEV1-S | ❌ Payant ~5 €/mois | Console moderne FR | Bon souverain FR |
| **Infomaniak Public Cloud (retenu)** | ❌ Payant **~5-8 €/mois** estimés pour Filum | OpenStack standard | **300 € de crédits offerts sur 3 mois** = ~30+ mois gratuits effectifs pour la taille de Filum |
| Infomaniak VPS Cloud | Payant 24,92 €/mois forfait minimum | Console web | Surdimensionné pour Filum, et ne profite pas des 300 € de crédits |
| Clever Cloud | Payant ~15 €/mois | PaaS souverain FR `git push` | Plus cher mais zéro sysadmin |
| Wix / Lovable / Base44 | — | — | **Inadaptés** : builders no-code propriétaires, demandent de réécrire Filum from scratch dans leur runtime fermé. Lock-in total. Rejetés. |
| Monarobase, PulseHeberg, Ikoula | Payant ~5 €/mois | VPS classique | OK techniquement mais aucun avantage face à OVH/Scaleway/Infomaniak |

**Décision**

Cibler **Infomaniak Public Cloud (OpenStack)** comme prochaine étape d'hébergement quand le budget Railway s'épuise.

**Justifications**
- **300 € de crédits offerts sur 3 mois** lors de l'inscription : couvre largement les besoins MVP de Philum pendant la première année effective
- **Datacenters Tier 3+ en Suisse** (Genève, Zurich), 100% hydroélectrique
- **Souveraineté européenne forte** : pas un GAFAM, pas de Cloud Act US, infrastructure développée et possédée par les fondateurs et employés d'Infomaniak
- **Compatibilité technique 100%** avec la stack Filum/Philum (Docker, Postgres, Caddy, FastAPI async, Alembic — tout ça tourne sur Ubuntu standard sans adaptation)
- **API OpenStack** + ecosystem standard (Terraform, Ansible) → portable, pas de lock-in propriétaire
- **Service Database managé** (Postgres) disponible quand on voudra externaliser la base
- **Object Storage S3-compatible** (Swift) disponible pour backups + futurs uploads de contenu (cf. axe A R2 envisagé)
- **Bande passante gratuite** (sauf Object Storage > 10 To/mois)
- **Pas d'engagement**, résiliable mensuellement, facturation à l'usage
- **Domaine `philum.fr` offert** la 1re année avec le compte Public Cloud (~7 €/an ensuite)

**Architecture cible décidée**

```
philum.fr (Infomaniak Domain) ──DNS──► Cloudflare DNS (gratuit)
                                              │
                ┌─────────────────────────────┴───────────────────┐
                │                                                  │
        ┌───────▼─────────┐                              ┌────────▼─────────┐
        │ filum-eight     │                              │ Public Cloud     │
        │ .vercel.app     │                              │ Infomaniak       │
        │ → philum.fr     │                              │ Datacenter D3    │
        │ (Frontend)      │                              │ Genève           │
        └─────────────────┘                              │ ┌──────────────┐ │
                ▲                                         │ │ Caddy (443)  │ │
                │ HTTPS                                   │ │ ↓ proxy      │ │
                ▼                                         │ │ Backend:8000 │ │
            Utilisateur                                   │ │ Postgres:5432│ │
                                                          │ │ (Docker)     │ │
                                                          │ └──────────────┘ │
                                                          └──────────────────┘
                                                          IP publique IPv4 dédiée
                                                          Ubuntu 22.04 LTS
```

**Choix techniques figés** :
- **Instance** : la plus petite Nova disponible (~2 vCPU + 4 Go RAM + 20 Go SSD root, à confirmer dans le calculateur Infomaniak au moment du provisioning)
- **Volume Block additionnel** : 20 Go pour Postgres data (séparation root / data, snapshots indépendants), ~0,50 €/mois
- **OS** : Ubuntu 22.04 LTS
- **Région** : Genève (DC3) ou Zurich (équivalents)
- **Database** : **Postgres en container Docker** sur la même instance pour démarrer (0 € marginal). Migration vers Database Service managé Infomaniak quand la charge le justifie (dump + restore).
- **Domaine** : `philum.fr` (5,10 € la 1re année, ~7 €/an ensuite, offert avec compte Public Cloud)
- **DNS** : Cloudflare DNS (gratuit) pour routage et flexibilité, ou Infomaniak DNS si tout-en-un préféré
- **HTTPS** : Caddy + Let's Encrypt automatique
- **Frontend** : Vercel maintenu pour le MVP. Migration éventuelle vers la VM Infomaniak ou Pages Infomaniak en phase 2 si on veut full souverain.
- **Backups** : snapshot quotidien du volume Postgres via cron, plus tard upload vers Swift Object Storage Infomaniak
- **Auto-deploy** : GitHub Actions qui SSH la VM et fait `git pull && docker compose pull && docker compose up -d`

**Coût annuel estimé après les 3 mois de crédits**
- Compute (Nova small) : ~5-8 €/mois → **~70-100 €/an**
- Volume Block (20 Go Postgres) : ~0,50 €/mois → ~6 €/an
- Domaine `philum.fr` : 7 €/an
- Domaine défensif `philum.app` (optionnel) : ~12-15 €/an
- **Total : ~85 à 130 €/an** selon options

**Plan de bascule (à exécuter quand Railway s'épuise ou par décision)**

1. Créer compte Infomaniak, profiter des 300 € de crédits
2. Acheter `philum.fr` + éventuellement `philum.app` défensif
3. Provisionner instance Nova Ubuntu 22.04
4. Setup serveur : Docker + Caddy + UFW + fail2ban + unattended-upgrades
5. Cloner repo Philum, créer `infra/docker-compose.prod.yml` + `infra/Caddyfile` + `.env`
6. Lancer la stack (backend + Postgres en container)
7. Configurer DNS `api.philum.fr` → IP Infomaniak
8. Caddy obtient certificat Let's Encrypt automatique
9. Seed démo : `docker compose exec backend python -m app.scripts.seed_demo`
10. Mettre à jour Vercel `PUBLIC_API_BASE_URL` → `https://api.philum.fr`
11. Ajouter URL callback dans Google OAuth Console
12. Ajouter cron quotidien `pg_dump` + Swiss Backup ou Object Storage
13. Configurer GitHub Actions pour auto-deploy sur push `main`
14. Désactiver Railway (ou laisser tourner en mode standby zero-traffic le temps de vérifier)

**Conséquences code (à exécuter dans la PR de migration, pas celle-ci)**
- `infra/docker-compose.prod.yml` (nouveau)
- `infra/Caddyfile` (nouveau, template avec domaine final)
- `infra/setup.sh` (nouveau, script idempotent setup serveur)
- `infra/backup.sh` + cron template
- `apps/backend/.env.example` à jour
- `.github/workflows/deploy-infomaniak.yml` (auto-deploy)
- `STATE.md` + `CHANGELOG.md` mis à jour
- Suppression du Dockerfile / config Railway-spécifique si présents

**Dépendance avec ADR-021** : si le rename Philum est exécuté avant la migration (recommandé), tout le repo + variables d'env utiliseront déjà `philum` partout, et la migration n'a plus qu'à brancher le nouveau domaine. Si non, on peut migrer d'abord avec `filum-eight.vercel.app` qui pointe vers la nouvelle backend, puis renommer dans une PR séparée.

---

<!--
## ADR-NNN — Titre court

**Date** : YYYY-MM

**Contexte**
...

**Options envisagées**
...

**Justifications**
...

**Conséquences**
...
-->


## ADR-017 - Itu00e9ration 2 : indicateurs structuru00e9s, extraits, SSR fiche publique, refonte panneau

**Date** : 2026-05-12

**Contexte**

Apru00e8s la du00e9mo de neuroscience (itu00e9ration 1), quatre faiblesses bloquaient un usage MVP cru00e9dible : (1) un cube gu00e9nu00e9rique en guise de logo, (2) une cartographie sans nom d'auteur et un panneau collu00e9 au bord droit, (3) un jugement implicite via 'Autoritu00e9 u00e9levu00e9e/moyenne/faible' qui n'a aucun fondement vu00e9rifiable, (4) une page publique 100 % CSR, donc invisible aux bots SEO et aux moteurs IA (Perplexity, SearchGPT, Claude).

**Du00e9cisions**

1. **Indicateurs typu00e9s par type de source** plutu00f4t qu'un niveau d'autoritu00e9 fourre-tout. Colonnes flat : 'citations_count', 'impact_factor', 'subscribers_count', 'views_count'. Affichu00e9es sous forme de chips neutres. La colonne 'authority_level' n'est plus utilisu00e9e par l'UI mais reste en base (pas de migration destructive, et pas d'impact sur le 'canonical_hash').
2. **Table du00e9diu00e9e 'source_excerpts'** (FK CASCADE, position, text, suggested_by_ai). Pru00e9fu00e9ru00e9e u00e0 un JSONB sur 'sources' pour : indexabilitu00e9, contrainte 'NOT NULL' sur le texte, u00e9volution future vers un picker IA sans migration de schema.
3. **'conflict_of_interest' TEXT nullable**. Affichu00e9 _uniquement_ s'il est renseignu00e9 (jamais 'Aucun conflit') pour ne pas du00e9nigrer par omission.
4. **Renommage 'Pivot' -> 'Source clu00e9'** avec tooltip 'Source structurante du raisonnement'. 'Pivot' restait jargonnant et asymu00e9trique vis-u00e0-vis du reste de l'interface.
5. **SSR uniquement sur la fiche publique** ('+page.ts' avec 'ssr = true', surcharge le 'ssr = false' du '+layout.ts'). Le D3 est chargu00e9 cu00f4tu00e9 client via dynamic import ; le rendu serveur produit le HTML statique (sources + JSON-LD) que les bots et IA peuvent lire sans exu00e9cuter JS.
6. **JSON-LD Article + Person + citations[]** dans '<svelte:head>'. Crucial pour le GEO : Perplexity, SearchGPT, Claude.ai lisent prioritairement le JSON-LD avant le DOM.
7. **Panneau de du00e9tail ancru00e9 au nu0153ud cliquu00e9** plutu00f4t que collu00e9 au bord droit de la fenu00eatre. Largeur ru00e9duite (320px), positionnement contextuel, fallback bottom-sheet sur mobile (< 600px).

**Non-du00e9cisions (explicit)**

- Le 'canonical_hash' payload n'est PAS modifiu00e9. Les nouveaux champs restent hors signature pour pru00e9server la validitu00e9 des fiches du00e9ju00e0 publiu00e9es.
- Pas de picker IA pour les excerpts dans cette itu00e9ration : 'suggested_by_ai' est seedu00e9 u00e0 'false', le champ est lu00e0 pour la future feature.
- Pas de mode privu00e9 ni connectivitu00e9 Zotero/Obsidian/Notion : seulement un doc spec ('.docs/09-private-mode-and-integrations.md').

**Consu00e9quences**

- Toutes les fiches du00e9ju00e0 publiu00e9es restent vu00e9rifiables : le payload signu00e9 est inchangu00e9.
- La page publique devient indexable par Google et lisible par les moteurs IA.
- L'ajout futur d'un champ visible doit systu00e9matiquement se demander : 'rentre-t-il dans la signature ou pas ?' (par du00e9faut, non).
