# Journal des décisions

> Ce fichier consigne les décisions techniques et stratégiques importantes prises au fil du projet. Format inspiré des « Architecture Decision Records » (ADR).
>
> **Une entrée par décision.** Chaque entrée est datée, contient le contexte, l'option retenue, les alternatives écartées, et les conséquences.

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

*Pour ajouter une nouvelle décision, copier le template ci-dessous et incrémenter le numéro ADR.*

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
