# 10 — Plan de complétion du MVP (zéro budget)

> Document opérationnel destiné à un agent autonome (Claude Code, opencode/Big Pickle, Aider…) ou au développeur humain. Il définit ce qui sépare l'état actuel d'un MVP qu'on peut **démontrer en live et offrir à un premier cercle d'utilisateurs créateurs**.
>
> Lis d'abord [`STATE.md`](../STATE.md) (état vérifié) et [`00-vision.md`](./00-vision.md). Ce document ne remplace pas le roadmap historique ([`06-roadmap.md`](./06-roadmap.md)) — il en extrait le chemin critique du moment.

---

## 1. Critère d'arrêt « MVP complet »

Un MVP est **complet** quand chacune de ces six affirmations est vraie :

1. Un créateur tiers (pas le développeur) peut s'authentifier via **Google OAuth** depuis `https://filum-eight.vercel.app` sans intervention manuelle.
2. Une fois connecté, il peut créer une fiche bibliographique de bout en bout (`/dashboard/new` → ajout sources → publication) **sans assistance**.
3. Le formulaire de saisie d'URL pré-remplit les métadonnées via l'extracteur backend (`GET /sources/extract`).
4. La fiche publiée est visible publiquement à `https://filum-eight.vercel.app/@<slug>/<card-slug>` avec graphe D3, signature Ed25519 vérifiable, JSON-LD SSR.
5. Les routes `/dashboard*` redirigent vers le login si l'utilisateur n'est pas authentifié (auth guard).
6. Une démonstration de 5 minutes (login → création fiche → publication → consultation publique) est reproductible sans bug bloquant ni intervention dans la BDD.

**Hors MVP** (assumé pour plus tard) : export PDF, OpenGraph image dynamique, page-identité enrichie, OAuth multi-provider, intégrations Zotero/Obsidian/Notion, MCP server, domaine `filum.app`.

---

## 2. État courant (synthèse vérifiée)

| Brique | État | Bloque MVP ? |
|---|---|---|
| Backend déployé Railway | ✅ live, `/health` OK | — |
| Frontend déployé Vercel | ✅ live, fiche démo visible | — |
| Modèles + migrations Alembic 001-004 | ✅ appliquées en prod | — |
| Signature Ed25519 + canonical hash | ✅ vérifiable sur fiche démo | — |
| Page publique avec graphe D3 + SSR + JSON-LD | ✅ | — |
| Extracteur URL backend (`GET /sources/extract`) | ✅ Crossref + HTML scraping | — |
| Routes `/dashboard/new` + `/dashboard/new/[card_id]/sources` | ✅ scaffold | — |
| **OAuth Google end-to-end** | ❌ credentials non configurés, cookies en `samesite=lax` | **OUI** |
| **Auth guard sur `/dashboard*`** | ✅ `+layout.ts` redirige vers `/` si non connecté | — |
| **Extracteur branché dans le formulaire frontend** | ✅ appel `/sources/extract` au blur de l'URL en étape 2 | — |
| Rate limiting sur endpoints publics | ❌ slowapi présent mais non câblé | Risque (DoS) |
| Observabilité (logs, erreurs, uptime) | ⚠️ logs Railway uniquement, pas de Sentry | Recommandé |
| Test du flow auth end-to-end | ❌ | Recommandé |

Source de vérité unique : [`STATE.md`](../STATE.md) section « Prochaines étapes par priorité ». Ce document doit rester aligné avec lui ; en cas de désaccord, **STATE.md gagne**.

---

## 3. Chemin critique (ordre d'exécution recommandé)

Trois jalons. Chaque jalon = une PR auto-suffisante (mergée avant d'attaquer la suivante). Les PR sont indépendantes mais chaque sous-tâche **dans** une PR doit être cohérente.

### Jalon M1 — OAuth Google opérationnel cross-origin

**Objectif** : un utilisateur tiers peut se connecter, atterrit avec un cookie session valide reconnu par le backend Railway depuis le frontend Vercel.

**Pré-requis humain (le développeur, pas l'agent)** :
- Créer un projet OAuth dans la Google Cloud Console
- Récupérer `client_id`, `client_secret`
- Déclarer la redirect URI : `https://filum-production-07bb.up.railway.app/api/v1/auth/google/callback`
- Configurer dans Railway les variables d'env (en **lowercase**, ADR-010) :
  - `google_client_id`
  - `google_client_secret`
  - `google_redirect_uri`

**Travail agent / dev (FAIT — PR #— `feat/oauth-google-end-to-end`)** :
1. ✅ Vérifié : `authlib` non nécessaire (PyJWT 2.10+ gère JWKS nativement via `PyJWKClient`, httpx + cryptography déjà présents).
2. ✅ Implémenté :
   - `GET /api/v1/auth/google/login` → redirige vers Google avec `state` token CSRF en cookie HttpOnly
   - `GET /api/v1/auth/google/callback` → vérifie state, échange code → id_token, vérifie signature Google via JWKS, crée/retrouve User, signe cookie session HS256
3. ✅ **Bascule des cookies** : `samesite` conditionnel sur `settings.debug` (dev = `lax`, prod = `none + secure=True`).
4. ✅ Frontend : bouton « Continuer avec Google » sur `/` (page d'accueil) + page `/auth/callback` qui hydrate le store `auth` + redirige vers `/dashboard`.
5. ⏳ Test manuel en local avec ngrok ou via prod : nécessite credentials Google Cloud Console configurés par l'humain.
6. ✅ `cors_origins` inchangés (déjà OK : `["https://filum-eight.vercel.app","http://localhost:5173"]`).

**Critères de done** :
- `curl -c cookies.txt https://filum-production-07bb.up.railway.app/api/v1/auth/google/login` retourne une 302 vers `accounts.google.com`.
- Après login réel via le navigateur, `GET /api/v1/auth/me` retourne 200 avec les infos user.
- Logout fonctionne (`POST /api/v1/auth/logout`).
- Au moins 1 test d'intégration sur `/auth/me` avec un cookie mocké (déjà partiellement présent, vérifier qu'il passe avec la nouvelle config).

**Risques** :
- `samesite=none, secure=True` plus restrictif → toute origine non-HTTPS casse. **Mitiger** : conditionner sur `settings.debug` (dev = `lax`, prod = `none`).
- Google rejette les redirect URIs non HTTPS. Ne pas tester via `http://`.
- Cookie pas envoyé en cross-origin : vérifier `withCredentials: true` ou `credentials: 'include'` dans le client API frontend (`apps/frontend/src/lib/api/`).

**Estimation** : 4-6h de travail focus.

---

### Jalon M2 — Auth guard + branchement extracteur dans le formulaire

**Objectif** : un utilisateur connecté peut créer une fiche complète depuis le frontend sans toucher au backend manuellement. Un utilisateur non connecté est redirigé vers la page de login.

**Travail (FAIT — 2026-05-13, commit `132ea13`)** :
1. ✅ **Auth guard `/dashboard*`** : `+layout.ts` dans `apps/frontend/src/routes/dashboard/` — lit `parent().user` et `throw redirect(302, '/')` si non connecté.
2. ✅ **Branchement extracteur** : dans `dashboard/new/[card_id]/sources/+page.svelte`, sur `onblur` du champ URL, `GET /api/v1/sources/extract?url=...` → pré-remplit titre + auteurs. Silent fail si erreur réseau ou API.
3. ✅ **UX** : spinner dans le champ URL pendant l'extraction. Les champs titre/auteurs sont réinitialisés si l'URL change.
4. ⏳ **Validation frontend** (URL valide, titre non vide) — non fait, reporté à l'itération UX suivante.
5. ⏳ Test du flow complet — dépend des credentials Google Cloud configurés.

**Critères de done** :
- Visiter `/dashboard/new` non connecté → redirige vers `/`.
- Visiter `/dashboard/new` connecté → formulaire visible.
- Coller une URL → 1-3s après, titre/auteur pré-remplis.
- Publier → arrive sur `/@<slug>/<card-slug>` avec graphe.

**Estimation** : 3-4h.

---

### Jalon M3 — Durcissement minimal pour ouverture publique

**Objectif** : ouvrir l'accès à 3-5 premiers créateurs sans risque opérationnel grave.

**Travail** :
1. ✅ **Rate limiting** : `slowapi` branché sur `GET /sources/extract` (10 req/min/IP) et `POST /cards` (20 req/h/IP). `Limiter` défini dans `app/core/rate_limit.py` pour éviter imports circulaires.
2. ✅ **Logs structurés** : middleware FastAPI qui log chaque requête avec `request_id` (UUID tronqué), méthode, path, status, durée (ms). Header `X-Request-ID` présent sur chaque réponse.
3. ⏳ **Erreurs en prod** : `global_exception_handler` déjà présent avec `exc_info=True`. Alerte email Railway à investiguer.
4. ⏳ **README + page d'accueil** : ajouter encart bêta privée.
5. ⏳ **Backup BDD** : documenter la procédure.

**Critères de done** :
- Spam `GET /sources/extract` → 429 après 10 req.
- Logs Railway lisibles, grep-ables.
- Procédure de backup documentée.

**Estimation** : 4-5h.

---

## 4. Contraintes free-tier — ce qui peut casser

Le projet doit tourner **gratuitement** jusqu'à validation produit. Limites à surveiller :

| Service | Limite tier gratuit | Risque MVP | Stratégie de mitigation |
|---|---|---|---|
| Railway (backend + Postgres) | $5 crédit/mois, sleep si inactivité | Backend qui s'endort → premier hit lent. Postgres limité à ~1 GB | Garder l'instance « hobby » au minimum ($5/mois) si possible ; sinon accepter le cold start. Ne PAS stocker de blobs (PDF, images) en BDD. |
| Vercel (frontend) | 100 GB BW/mois, builds illimités | OK pour < 100k pageviews | Mettre des `Cache-Control: public, max-age=60` sur les pages publiques. |
| Wayback Machine API | ~10-15 req/min | Si un utilisateur ajoute 20 sources d'un coup, on dépasse | Queue asynchrone (déjà en place via `asyncio.create_task`) + retry exponentiel. |
| Google OAuth | Pratiquement illimité gratuit | — | — |
| Crossref API | Pas de limite stricte, mais courtoisie (`mailto:` requis dans User-Agent) | Faible | Bien renseigner le User-Agent (`Filum/0.1 (mailto:mathias@...)`). |
| GitHub Actions | 2000 min/mois pour le compte gratuit | OK avec CI actuelle (~5 min/run × ~50 runs/mois) | Si on monte, exclure les chemins doc-only via `paths-ignore`. |
| Dependabot | Gratuit | — | — |

**Règle d'or** : aucune dépendance payante (Sentry, Plausible, Logflare, AWS) avant validation des hypothèses utilisateurs (cf. `.docs/00-vision.md`).

---

## 5. Anti-features (à NE PAS implémenter avant la complétion MVP)

L'agent doit refuser d'implémenter ces features tant que les 3 jalons ne sont pas mergés, même si le code semble facile :

- Export PDF (charge Playwright, ~200 MB image Docker)
- OpenGraph image dynamique (Pillow + génération à la volée — utile mais non bloquant)
- Page-identité enrichie (`/@slug` minimal suffit en MVP)
- Mode privé / unlisted (cf. `09-private-mode-and-integrations.md`, spec uniquement)
- Intégrations Zotero/Obsidian/Notion (idem)
- Multi-provider OAuth (YouTube, X, ORCID)
- Extraction IA depuis du texte collé
- Embed widget
- MCP server
- Domaine `filum.app` (acheter quand on a 5 utilisateurs réels — pas avant)
- dbt models en runtime (le `dbt compile` en CI suffit pour le portfolio)
- Sentry / Plausible (attendre signal utilisateur)

**Pourquoi cette discipline** : chaque feature non-MVP retarde l'inflexion « est-ce que des créateurs adoptent ? ». Une fois la réponse oui ou non, on saura quoi prioriser ensuite. Avant cette réponse, tout dev supplémentaire est de la spéculation.

---

## 6. Comment l'agent doit utiliser ce document

À chaque démarrage de session :

1. Lire `STATE.md` (état réel)
2. Lire ce document (chemin critique)
3. Identifier le **jalon courant** (M1, M2, M3) en croisant les deux
4. Identifier la **sous-tâche courante** (numérotée dans le jalon)
5. Ouvrir le skill correspondant dans [`agent/skills/`](../agent/skills/) si la sous-tâche le justifie (OAuth → `oauth-google.md`, etc.)
6. Travailler sur une branche dédiée (cf. [`agent/GIT_WORKFLOW.md`](../agent/GIT_WORKFLOW.md))
7. À la fin : mettre à jour `STATE.md`, ouvrir une PR, **ne pas merger** sans validation humaine

**Critère de cohérence** : si l'agent termine un jalon, il met à jour ce document (`10-mvp-completion-plan.md`) en cochant la tâche et en notant la date + le numéro de PR. Le document doit refléter la réalité.

---

## 7. Après la complétion MVP — premiers pas

Une fois M1+M2+M3 mergés et un premier créateur ambassadeur onboardé :

- **Mesurer** : ajouter un compteur de vues simple sur les fiches publiques (incrément côté backend, pas de tracking externe).
- **Documenter** : 1 page utilisateur sur `filum.app` (ou Notion public) « Comment créer ta première fiche ».
- **Réévaluer** : confronter le retour des 3-5 premiers créateurs aux hypothèses du `.docs/00-vision.md` section « La phase MVP ». Si désalignement, pivoter avant d'ajouter des features.

C'est uniquement à ce stade que les features de phase 2 (OAuth YouTube, extraction IA, OpenGraph dynamique) ont du sens.

---

*Maintenir ce document à jour. Si un jalon devient obsolète (fait, abandonné, repensé), le marquer explicitement. Ne pas créer un `12-…md` qui parlerait du même sujet ; éditer celui-ci.*
