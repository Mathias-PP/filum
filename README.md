# Filum

> Infrastructure ouverte de provenance et de filiation pour le contenu numérique.

**Filum** est un outil qui permet à tout créateur de contenu (vidéo, article, podcast, post long) de transformer sa bibliographie en une fiche publique interactive : sources organisées par type et autorité, archivées de manière horodatée, reliées entre elles dans un graphe navigable.

À l'ère de l'IA générative qui brouille les pistes de l'authenticité, Filum n'est pas un outil de détection de faux. C'est un **label qualité** pour les créateurs qui prennent le temps de bien sourcer leur travail.

---

## Pour qui ?

- **Vulgarisateurs scientifiques** (cible primaire) qui veulent rendre leur rigueur visible
- **Journalistes indépendants** qui veulent prouver leur sourçage et le protéger dans le temps
- **Chercheurs** qui veulent partager leurs bibliographies sous forme navigable
- **Experts grand public** qui veulent une page-identité officielle dont ils gardent la main

---

## En quoi consiste le MVP

Voir [`.docs/01-product-spec.md`](.docs/01-product-spec.md) pour le détail des features.

En résumé, le MVP permet à un créateur :

1. De s'authentifier avec son compte Google
2. De créer une fiche de bibliographie pour un de ses contenus en y ajoutant ses sources
3. De recevoir une page publique stable (`filum.app/[créateur]/[contenu]`) qui présente sa bibliographie sous forme de graphe interactif et de liste éditoriale
4. De partager cette page (via OpenGraph riche, embed dans d'autres sites, export PDF)

Et permet à n'importe qui :

5. De consulter une fiche publique, naviguer dans le graphe de sources, lire les annotations, accéder aux snapshots archivés

---

## Pour démarrer (développeur)

```bash
# Cloner et installer
git clone <repo> filum
cd filum
make setup       # installe les dépendances backend + frontend
make seed        # peuple la BDD avec des données de démonstration
make dev         # lance backend (FastAPI :8000) + frontend (SvelteKit :5173)
```

Voir [`.docs/02-tech-architecture.md`](.docs/02-tech-architecture.md) pour le détail de l'architecture.

---

## Documentation du projet

Tous les fichiers de spec sont dans [`.docs/`](.docs/). Ils sont conçus pour être lus par un humain ou par un agent IA assistant (Claude Code, Aider, etc.).

| Document | Contenu |
|---|---|
| [`00-vision.md`](.docs/00-vision.md) | Le projet en une page, principes fondateurs, ce qu'il n'est pas |
| [`01-product-spec.md`](.docs/01-product-spec.md) | Features du MVP, scénarios utilisateurs, écrans |
| [`02-tech-architecture.md`](.docs/02-tech-architecture.md) | Stack, structure du code, déploiement |
| [`03-data-model.md`](.docs/03-data-model.md) | Schéma de base de données, modèles dbt |
| [`04-api-design.md`](.docs/04-api-design.md) | Endpoints REST, contrats |
| [`05-design-system.md`](.docs/05-design-system.md) | Couleurs, typographie, composants, inspirations |
| [`06-roadmap.md`](.docs/06-roadmap.md) | Plan jour par jour de la semaine 1, puis phases 2-6 |
| [`07-open-questions.md`](.docs/07-open-questions.md) | Arbitrages non tranchés |
| [`08-glossary.md`](.docs/08-glossary.md) | Glossaire technique et institutionnel |

Documents vivants à maintenir au fil du projet :

| Fichier | Rôle |
|---|---|
| [`STATE.md`](STATE.md) | État courant du projet (à mettre à jour chaque session de travail) |
| [`DECISIONS.md`](DECISIONS.md) | Log chronologique des décisions importantes |
| [`CHANGELOG.md`](CHANGELOG.md) | Historique des versions |

---

## Conventions pour l'assistance IA

Filum est conçu pour être développé en partie avec l'assistance d'agents IA (Claude Code en priorité, Aider en secours).

- [`CLAUDE.md`](CLAUDE.md) — instructions et contraintes pour Claude Code (lu automatiquement)
- [`AGENTS.md`](AGENTS.md) — instructions équivalentes pour d'autres agents (Aider, Codex, etc.)

Les deux fichiers contiennent l'essentiel des règles à respecter pour rester cohérent avec le projet.

---

## Stack technique en bref

- **Backend** : Python 3.12 + FastAPI + SQLAlchemy + Alembic
- **Bases de données** : PostgreSQL (transactionnel) + DuckDB (analytique)
- **Transformations data** : dbt-core sur DuckDB
- **Frontend** : SvelteKit + TypeScript + Tailwind CSS
- **Crypto** : `cryptography` (Python) pour hash SHA-256 et signatures Ed25519
- **Archivage de sources** : API Wayback Machine d'Internet Archive
- **Identité** : OAuth Google en MVP (puis YouTube, X, ORCID en phase 2)
- **Déploiement** : Railway (backend + Postgres) + Vercel ou Netlify (frontend)
- **Migration souveraine prévue** : Scaleway en phase 3

---

## Cause et neutralité

Filum est conçu comme un commun numérique. Le cœur du projet (signature, bibliographie publique, archivage) est gratuit pour les créateurs individuels. La monétisation porte sur des fonctionnalités annexes (analytics, alertes, archivage premium) et sur les services aux organisations.

Pas de publicité, pas de tracking intrusif. La neutralité éditoriale est une condition d'acceptation par les médias indépendants et les institutions.

Voir le [manifeste fondateur](.docs/MANIFESTE.md) pour la vision complète à long terme (à importer dans `.docs/`).

---

*Document maintenu par l'auteur du projet. Version 0.1 — pré-MVP.*
