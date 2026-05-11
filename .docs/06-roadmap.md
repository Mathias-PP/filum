# 06 — Feuille de route

> Plan détaillé de la semaine 1 (MVP), puis phases 2 à 5.

---

## Avant de commencer la semaine 1 — préparation

À faire dans les heures qui précèdent le jour 1 :

- [ ] Installer WSL2 si pas encore fait (Windows) ou s'assurer d'un Linux/macOS prêt
- [ ] Installer `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`) — package manager Python ultra rapide
- [ ] Installer `pnpm` (`npm install -g pnpm`)
- [ ] Installer Postgres 16 localement (ou utiliser Docker)
- [ ] Créer le repo GitHub privé `filum`, cloner localement
- [ ] Importer les specs dans `/.docs` et les fichiers racine (`CLAUDE.md`, `AGENTS.md`, etc.)
- [ ] Acheter le domaine `filum.app` (Cloudflare Registrar recommandé)
- [ ] Créer un projet OAuth Google dans la Console Google Cloud (client ID + secret)
- [ ] Créer un compte Railway, lier au GitHub
- [ ] Créer un compte Vercel ou Netlify, lier au GitHub
- [ ] Vérifier que Claude Code est installé et fonctionnel dans le terminal WSL

**Temps estimé** : 2-3 heures (essentiellement de l'attente sur les inscriptions et installations).

---

## Semaine 1 — jour par jour

### Jour 1 — Squelette du projet et base de données

**Matin (3-4h)**
- Initialiser le mono-repo
- Setup backend FastAPI minimal (`apps/backend/`) avec `uv`
- Setup frontend SvelteKit minimal (`apps/frontend/`) avec `pnpm`
- Setup dbt project (`apps/analytics/`)
- Créer le `Makefile` à la racine avec les targets `setup`, `dev`, `test`, `lint`, `seed`
- Configurer `.env.example` complet

**Après-midi (3-4h)**
- Définir les modèles SQLAlchemy : `User`, `BiblioCard`, `Source`, `AuditEvent`
- Configurer Alembic
- Créer la première migration
- Tester la migration up/down
- Premier commit "feat: project skeleton + initial schema"

**Livrable jour 1** : repo Git avec squelette, BDD locale qui marche, premier `make dev` qui démarre backend et frontend.

---

### Jour 2 — OAuth Google et utilisateurs

**Matin (3-4h)**
- Endpoint `GET /api/v1/auth/login` (redirige vers Google)
- Endpoint `GET /api/v1/auth/callback` (callback Google)
- Création utilisateur en BDD à la première connexion
- Génération de la paire de clés Ed25519 lors de la création utilisateur
- Stockage chiffré de la clé privée (Fernet avec clé maître en env var)

**Après-midi (3-4h)**
- Endpoint `GET /api/v1/auth/me` (utilisateur courant)
- Endpoint `POST /api/v1/auth/logout`
- Page d'onboarding frontend (`/onboarding`) avec choix du slug
- Endpoint `PATCH /api/v1/users/me` pour mettre à jour le profil
- Tests des routes auth

**Livrable jour 2** : un utilisateur peut se connecter avec Google, choisir un slug, voir un profil basique.

---

### Jour 3 — CRUD fiches et sources

**Matin (3-4h)**
- Endpoint `POST /api/v1/cards` (créer fiche en brouillon)
- Endpoint `PATCH /api/v1/cards/{id}` (modifier)
- Endpoint `GET /api/v1/me/cards` (mes fiches)
- Validations Pydantic strictes

**Après-midi (3-4h)**
- Endpoint `POST /api/v1/cards/{id}/sources` (ajouter source)
- Endpoint `PATCH /api/v1/sources/{id}` (modifier)
- Endpoint `DELETE /api/v1/sources/{id}` (supprimer)
- Frontend : tableau de bord créateur (`/dashboard`)
- Frontend : formulaire de création de fiche (étape A — métadonnées)

**Livrable jour 3** : un créateur connecté peut créer une fiche brouillon avec ses métadonnées.

---

### Jour 4 — Archivage Wayback et signature

**Matin (3-4h)**
- Service `WaybackArchiver` : fonction asynchrone qui appelle l'API Wayback
- À chaque création de source, lancer le job d'archivage en background (`asyncio.create_task`)
- Mise à jour de `archive_status` et `archive_url`
- Frontend : formulaire d'ajout de sources avec indicateur d'archivage en temps réel (polling)

**Après-midi (3-4h)**
- Service `CardSigner` : canonicalisation RFC 8785 + hash SHA-256 + signature Ed25519
- Endpoint `POST /api/v1/cards/{id}/publish`
- Endpoint `GET /api/v1/cards/{creator_slug}/{card_slug}/verify`
- Tests crypto

**Livrable jour 4** : une fiche peut être complétée avec sources archivées, signée, publiée.

---

### Jour 5 — Page publique et graphe interactif

**Journée entière (6-7h)**
- Endpoint `GET /api/v1/cards/{creator_slug}/{card_slug}` (lecture publique)
- Route SvelteKit `/[creator_slug]/[card_slug]` avec SSR
- Layout de la page publique selon la maquette validée
- Composant `BiblioGraph` :
  - Calcul du layout force-directed avec D3.js
  - Rendu SVG des nœuds et edges
  - Interactions : click, drag, zoom
  - Fiche compacte qui s'ouvre au clic
- Composant `SourceList` :
  - Liste avec dépliage in-place
  - Tri par centralité/date/type
- Composant `StatsBanner`

**Livrable jour 5** : la page publique fonctionne, est belle, le graphe est interactif.

---

### Jour 6 — OpenGraph, page-identité, polish

**Matin (3-4h)**
- Endpoint `GET /api/v1/cards/{creator_slug}/{card_slug}/og.png` (image OpenGraph générée avec Pillow)
- Meta tags OpenGraph et Twitter Card sur les pages publiques
- Endpoint `GET /api/v1/users/{slug}` (page-identité)
- Route SvelteKit `/@[slug]` avec SSR

**Après-midi (3-4h)**
- Endpoint `GET /api/v1/cards/{id}/pdf` (export PDF, génération via Playwright)
- Page d'accueil publique `/`
- Polish général : transitions, états de chargement, états vides

**Livrable jour 6** : produit complet et beau, prêt pour démo.

---

### Jour 7 — dbt, déploiement, démo

**Matin (3-4h)**
- Setup dbt project avec quelques modèles
- Script Python qui charge Postgres → DuckDB
- Quelques modèles dbt simples (staging + 2-3 marts)
- Tests dbt
- Mise à jour `STATE.md` et `CHANGELOG.md`

**Après-midi (3-4h)**
- Configuration Railway pour le backend
- Déploiement automatique sur push GitHub
- Configuration Vercel ou Netlify pour le frontend
- Configuration domaine `filum.app`
- Test end-to-end en production
- Création d'une fiche de démonstration

**Livrable jour 7** : produit déployé, accessible publiquement, une fiche de démonstration en ligne.

---

## Réalisme et marges

Le plan ci-dessus suppose ~7h de travail focus par jour, soit ~50h sur la semaine. C'est intense. Marges prévues :

- Si du retard prend le jour 5 (le plus risqué), réduire les ambitions du graphe : moins d'interactions, plus simple. Garder le wow visuel principal.
- Si du retard prend le jour 6, reporter l'export PDF en semaine 2.
- Si du retard prend le jour 7, déployer manuellement en backend, frontend sur Vercel marche en 30 secondes.

**Ce qui n'est pas négociable** : avoir un produit déployé avec une fiche publique de démonstration le dimanche soir.

---

## Phase 2 — semaines 2 à 4 (consolidation)

### Semaine 2 — extraction IA + autres providers

- Intégration d'un appel LLM (Claude API ou Mistral) pour extraire automatiquement des sources depuis un texte collé
- OAuth supplémentaires : YouTube (via Google), X
- Page-identité enrichie avec comptes liés
- Premiers retours utilisateurs (Léa, Hugo, etc.)

### Semaine 3 — pérennité et qualité

- Sentry pour le tracking d'erreurs
- Plausible Analytics
- Snapshots propres via Playwright (alternative à Wayback en cas de panne)
- Tests E2E avec Playwright
- Backup automatique de la BDD

### Semaine 4 — premiers ambassadeurs

- Démarchage actif des 5 premiers vulgarisateurs cibles
- Création de 5-10 fiches de référence sur leurs sujets
- Premières publications publiques
- Documentation pour les utilisateurs

---

## Phase 3 — mois 2-3 (montée en exigence)

- Intégration C2PA via `c2pa-rs` (Rust binding ou réimplémentation Python)
- Horodatage qualifié eIDAS (TSA partenaire : Universign ou Certinomis)
- Embed widget pour sites tiers
- Import Zotero/BibTeX/RIS
- MCP server pour agents IA
- API publique de vérification documentée
- Premier contact avec Internet Archive pour partenariat formel

---

## Phase 4 — mois 4-6 (premiers revenus)

- Lancement des paliers payants (Pro créateur)
- Intégration CMS (WordPress, Ghost, Substack)
- API enterprise avec SLA
- Premières discussions avec médias institutionnels
- Application au C2PA Conformance Program

---

## Phase 5 — mois 6-12 (infrastructure publique)

- Création de la fondation
- Premiers financements publics européens (NLnet, NGI)
- Migration vers Scaleway pour la production souveraine
- Première version anglaise du registre
- Adhésion W3C Credentials Working Group

---

## Mesures de succès à chaque phase

**Fin de phase 1 (semaine 1)** : produit déployé, une fiche de démo, démo de 5 min convaincante.

**Fin de phase 2 (mois 1)** : 5-10 créateurs ambassadeurs actifs, 20+ fiches publiées, 1000+ vues cumulées.

**Fin de phase 3 (mois 3)** : 50+ créateurs, 200+ fiches, premiers contrats institutionnels en discussion, intégration C2PA opérationnelle.

**Fin de phase 4 (mois 6)** : premiers revenus (1k€-5k€/mois), 200+ créateurs actifs, 1 média institutionnel client.

**Fin de phase 5 (mois 12)** : fondation créée, financement public sécurisé pour 18 mois, 1000+ créateurs, narrative médiatique installée.

---

*Pour les questions ouvertes, voir [`07-open-questions.md`](./07-open-questions.md).*
