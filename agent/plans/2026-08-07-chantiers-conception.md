# Plan — chantiers de conception (2026-08-07)

Ce document liste les chantiers ouverts non triviaux, avec pour chacun le
problème observé, la solution retenue, les fichiers touchés et les tests à
écrire. Chaque chantier est autonome : une PR par chantier.

---

## Chantier 1 — Compatibilité agents conversationnels (ChatGPT, Claude, Gemini)

### Problème observé (2026-08-07)

Un utilisateur a fourni à ChatGPT l'URL `/@mathias-pinault/ca-sert-a-quoi-de-dormir.md`.
Le crawler ChatGPT a répondu qu'il ne pouvait pas récupérer la page et a lancé
une recherche Web au lieu d'un fetch direct. Vérification indépendante par curl :

- `GET .../ca-sert-a-quoi-de-dormir.md` → **200 OK**, `Content-Type: text/markdown; charset=utf-8`, corps markdown propre
- `GET .../ca-sert-a-quoi-de-dormir` → **200 OK**, `Content-Type: text/html`, contenu SSR complet (7 sources, titres, DOI présents dans le HTML)
- `robots.txt` : `Allow: /`, sitemap déclaré
- `llms.txt` : documente les points d'entrée machine
- HTML head : `<link rel="alternate" type="text/markdown" href=".../*.md" />`
- Header HTTP : `Link: <...md>; rel="alternate"; type="text/markdown"` (ajouté 2026-08-07)

Autrement dit, Philum coche déjà toutes les cases documentées. Le problème est
côté ChatGPT : sa couche de browsing interprète les URLs contenant `@` comme
la partie `user@host` de la RFC 3986 et bascule en mode recherche.

### Solution en trois couches (défensive)

#### Couche A — URL alternative sans `@` (implémentée le 2026-08-07)

Nouvelles routes :
- `/c/<createur>/<fiche>.md` → sert le markdown directement, `Link: rel="canonical"` vers `/@<createur>/<fiche>.md`
- `/c/<createur>/<fiche>` → 301 vers `/@<createur>/<fiche>`

Documentée dans `llms.txt`. La forme sans `@` évite le déclenchement des
heuristiques `user@host` sans changer l'URL canonique.

#### Couche B — Content negotiation via `Accept` (à faire)

Sur la route canonique `/@<createur>/<fiche>`, respecter `Accept: text/markdown` :

```ts
// apps/frontend/src/routes/@[creator]/[card]/+page.server.ts (à créer)
export const load: PageServerLoad = async ({ fetch, params, request, setHeaders }) => {
  const accept = request.headers.get('accept') || '';
  if (accept.includes('text/markdown') && !accept.includes('text/html')) {
    // Servir le markdown depuis l'export API. Retourner un Response direct
    // n'est pas possible depuis load() ; utiliser +server.ts avec dispatch
    // sur la méthode Accept en amont, OU réserver Accept-based à une route
    // dédiée `/@/<creator>/<card>` (sans /) qui accepte les deux.
  }
  // ...
};
```

**Contrainte SvelteKit :** un fichier `+page.server.ts` ne peut pas retourner
un `Response` arbitraire depuis `load`. Deux approches :

1. Créer un `+server.ts` **à la place** du `+page.svelte` et dispatcher en
   fonction de `Accept`. Trop invasif — casserait la SSR HTML.
2. Un middleware hook dans `hooks.server.ts` qui intercepte les requêtes vers
   `/@:creator/:card` avec `Accept: text/markdown` et réécrit vers `.md`.
   **Retenu.** ~20 lignes, isolé, testable.

#### Couche C — Structured `application/vnd.philum+json` (à faire)

Format proposé par ChatGPT lui-même dans la conversation :

```json
{
  "@type": "Article",
  "title": "...",
  "summary": "...",
  "creator": { "slug": "...", "display_name": "..." },
  "content_url": "...",
  "published_at": "...",
  "sources": [
    {
      "url": "...", "title": "...", "authors": "...",
      "published_at": "...", "doi": "...",
      "archive_url": "...", "retracted": false,
      "stance": "supports|contextualizes|refutes|null"
    }
  ]
}
```

Ce format n'existe pas encore. L'export `?format=json` du backend renvoie déjà
une structure proche ; il suffit d'exposer un nouveau content-type sur la même
route et de l'annoncer dans `llms.txt`. Effort : 1 h.

### Fichiers touchés (couches B + C)

- Créer : `apps/frontend/src/hooks.server.ts` (dispatch `Accept: text/markdown`)
- Modifier : `apps/backend/app/api/v1/endpoints/cards.py` — nouveau `format=philum` dans l'endpoint d'export
- Modifier : `apps/frontend/src/routes/llms.txt/+server.ts` — annoncer `Accept: application/vnd.philum+json`

### Tests

- `apps/frontend/tests/hooks.server.test.ts` — un mock request avec `Accept: text/markdown` sur `/@x/y` doit produire une réponse markdown
- Intégration : `curl -H "Accept: text/markdown" /@x/y` renvoie le markdown
- Backend : `apps/backend/tests/integration/test_export_philum_json.py` — schema stable

---

## Chantier 2 — Pipeline d'extraction agnostique (7 étages)

**FAIT.** Livré le 2026-07-23 sous ADR-030 (commit `389a291`), affiné dans plusieurs PR entre le 2026-07-23 et le 2026-08-05.

Ce plan (2026-08-07) le listait par erreur comme « pending » parce que
`.claude/plans/effervescent-foraging-lollipop.md` avait pris la valeur d'un
plan futur alors qu'il servait de spec au travail déjà réalisé.

État réel en prod :
- 7 étages implémentés dans `apps/backend/app/api/v1/endpoints/imports.py`
- Modules dédiés : `section_detector.py`, `wikipedia_oracle.py`, `ref_dedup.py`, `ref_scorer.py`
- Réponse enrichie : `extraction_confidence`, `refs_from_oracle`, `refs_from_enrichment`, `refs_dropped_validation`, `refs_dropped_scoring`, `refs_dropped_s2_hallucination`
- Frontend affiche le badge de confiance dans `sources/+page.svelte`
- 61 tests unitaires + intégration sur Frontiers 651547 → objectif 152 refs tenu

**Ajout 2026-08-07 (nuit)** : résolution DOI Nature/bioRxiv/medRxiv depuis l'URL éditeur. Nature `nrn3667` produisait 0 ref parce que le site bloque le scraping et que le DOI n'était pas dérivé de l'URL. Corrigé dans `url_extractor._extract_doi`.

---

## Chantier 3 — Extraction Nature.com et sites anti-scraping

### Problème observé (2026-08-07)

Sur `https://www.nature.com/articles/nrn3667` :
- Le pipeline actuel : « Ce site a refusé la lecture automatique de la page. »
- Copier-coller texte libre : « 0 référence importée » (avant fix du 2026-08-07)
- Import RIS : fonctionne mais dates masquées (fix déployé 2026-08-07)

### Solutions

#### 3a — Détection anti-scraping explicite (à faire)

Améliorer le message d'échec pour distinguer :
- Timeout / DNS → « Le site n'a pas répondu à temps »
- 403 / 429 / 999 → « Le site a refusé la lecture automatique. Sur Nature,
  utilisez le bouton *Cite* → *Download citation* pour obtenir un `.ris`. »

Fichier : `apps/backend/app/api/v1/endpoints/imports.py` (fonction
`parse_content_url`) — remonter le statut HTTP dans le message.

#### 3b — Parseur texte-libre robuste (fait le 2026-08-07)

`parse_freetext_citations` dans `apps/backend/app/services/import_parsers.py`
reconnaît le format Nature/Science « Auteurs. Titre. Journal Vol, Pages
(Année). ». Testé sur 5 échantillons réels.

#### 3c — Playwright worker (différé, cf. `agent/DECISIONS.md`)

La VM e2-micro (1 GB RAM total) ne peut pas héberger Chromium (500-800 MB en
pointe). Voie d'intégration : worker Cloud Run dédié, appelé par le backend.
Hors scope MVP.

---

## Chantier 4 — Feed chronologique public

**Spec existante :** `.docs/20-profils-et-feed.md` (posée le 2026-08-06).

Registre chronologique strict des publications de fiches. Pas algorithmique,
pas de likes, entrées immuables. Modèle esquissé :

```sql
CREATE TABLE feed_events (
  id UUID PRIMARY KEY,
  kind TEXT NOT NULL,        -- 'card_published' en v1
  actor_id UUID REFERENCES users,
  card_id UUID REFERENCES biblio_cards,
  occurred_at TIMESTAMP NOT NULL
);
```

Effort : 2 j (migration + endpoint `GET /api/v1/feed` + page `/feed`).

Question ouverte (Q-feed-1) : que faire quand une fiche publiée passe en
privé ? Marquer l'entrée « dépubliée » (proposé) vs la retirer (rejeté).

---

## Chantier 5 — Recherche de créateurs

**Spec existante :** `.docs/20-profils-et-feed.md`.

Endpoint : `GET /api/v1/discover/creators?q=&limit=&offset=`.
Retourne `{slug, display_name, avatar_url, published_cards_count, verified_accounts[]}`.

Indexation : `display_name`, `username`, `User.bio` (colonne à exposer).
Jamais : fiches privées, brouillons, email, comptes non vérifiés.

UI : onglet « Créateurs » sur `/discover` ou route `/discover/creators`.

Effort : 1 j (endpoint + tests + onglet).

---

## Chantier 6 — Audits persona (backlog #74-#77)

Créer et auditer une fiche pour chacun des personas :
- **Journaliste** : article de presse d'investigation (Mediapart, Le Monde, Reuters)
- **Vulgarisateur** : vidéo YouTube longue avec biblio en description
- **Écrivain** : essai de blog long format (Substack)
- **Institution** : rapport gouvernemental PDF (OMS, INSERM, Cour des comptes)

Objectif : révéler les impasses UX propres à chaque type de contenu. Chaque
audit → un ticket de bug avec repro.

Effort : 0.5 j par persona.

---

## Chantier 7 — Audit visiteur (backlog #78)

Auditer le parcours d'un visiteur non authentifié :
- Contraste (WCAG AA sur tous les textes et icônes)
- Lisibilité mobile (portrait 375×667, paysage tablette)
- Charge cognitive du graphe sur écrans tactiles
- Boutons de partage, export, réclamer une fiche

Outils : Lighthouse mobile + audit manuel dans devtools mobile.
Effort : 0.5 j.

---

## Priorisation suggérée

| Ordre | Chantier | État |
|---|---|---|
| ~~P0~~ | 1B + 1C (content nego + JSON structuré) | ✅ fait 2026-08-07 (PR #291) |
| ~~P1~~ | 2 (pipeline extraction v2) | ✅ fait 2026-07-23 (ADR-030) + fix DOI éditeur 2026-08-07 |
| ~~P2~~ | 3a (détection anti-scraping) | ✅ fait 2026-08-07 (PR #291) |
| ~~P3~~ | 4 + 5 (feed + recherche créateurs) | ✅ fait 2026-08-07 (PR #291) |
| P4 | 6 (audits persona) | Pending — nécessite créer du vrai contenu |
| P5 | 7 (audit visiteur) | Pending — nécessite test mobile |

## Hors scope de ce plan (par choix explicite)

- Notifications push/e-mail basées sur le feed
- Abonnements entre créateurs
- Modération du feed
- Cloud Run worker Playwright (attendre premier retour utilisateur qui justifie le coût)
- Types de compte organisation (spec dans `.docs/19-preuve-autorat.md` §3)
