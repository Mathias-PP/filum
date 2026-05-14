# 01 — Spécifications produit du MVP

> ⚠️ **Pivot ADR-019 (2026-05-14)** : les sections « signature de fiche » et « immuabilité de la fiche publiée » de ce document sont obsolètes. La signature porte désormais sur le **lien créateur·ice ↔ contenu** (triplet `(creator_id, content_url, attested_at)`). Les fiches bibliographiques sont mutables. Voir `DECISIONS.md` ADR-019. Réécriture intégrale du document à la PR de bascule backend.

> ⚠️ **Refonte taxonomie ADR-020 (2026-05-14)** : toute mention de `source_type` (`peer-reviewed`, `institutionnel`, `presse`, `matériel original`, `vidéo`, `image`) dans ce document est **obsolète**. La taxonomie est désormais sur 3 axes orthogonaux : `format` (texte/video/image/audio/data), `category` (12 valeurs : article-scientifique, preprint, article-presse, communique, documentaire, interview, podcast, blog, post-social, livre, page-web, notes) et `author_kind` (9 valeurs : chercheur, media, institution-publique, gouvernement, ecole, laboratoire, entreprise, asso, individu). Le graphe est coloré par `author_kind`. Voir `DECISIONS.md` ADR-020.

> Ce document décrit les fonctionnalités du MVP de Filum, les scénarios utilisateurs, et les écrans. Il est la référence produit pendant toute la phase 1.

---

## Périmètre du MVP

**Inclus** :
- Authentification OAuth Google
- Création de fiche bibliographique avec sources entrées manuellement
- Page publique de fiche avec graphe interactif et liste de sources
- Page-identité créateur (version minimale)
- Snapshots automatiques des URLs via Wayback Machine
- Signature Ed25519 et hash SHA-256 réels
- OpenGraph dynamique pour le partage
- Export PDF de la fiche

**Exclus du MVP (prévu phases ultérieures)** :
- OAuth multi-plateforme (YouTube, X, ORCID) — phase 2
- Extraction automatique de sources depuis du texte par IA — phase 2
- Import Zotero/BibTeX/RIS — phase 3
- Intégration complète C2PA — phase 3
- Embed widget pour sites tiers — phase 2
- API publique pour agents IA / MCP server — phase 3
- Analytics avancés, alertes, droit de réponse — phases payantes
- Archivage propre via Puppeteer/Playwright — phase 3

---

## Personas

### Persona principal — Léa, vulgarisatrice climat

Léa, 31 ans, fait des vidéos YouTube et des posts X de vulgarisation climat. 184k abonnés YouTube, 42k followers X. Elle passe une journée complète à sourcer chaque vidéo : elle lit les études primaires, croise plusieurs sources institutionnelles, parfois mène une interview originale. Quand elle publie, elle met les liens en description, mais elle sait que personne ne les clique.

**Sa douleur** : son travail de sourçage est invisible, donc non récompensé. Quand on l'attaque sur les réseaux pour une affirmation, elle n'a pas de moyen rapide de pointer vers la pile de sources qui la fondent. Elle redoute la prochaine vidéo polémique.

**Ce qu'elle espère de Filum** : que son sérieux soit enfin visible. Que ses sources soient archivées pour que personne ne puisse contester qu'elle les a bien utilisées. Que son audience trouve la consultation des sources désirable, pas fastidieuse.

### Persona secondaire — Marc, lecteur sérieux

Marc, 38 ans, ingénieur, abonné à Léa. Il aime ses vidéos mais a parfois des doutes — est-ce que les chiffres avancés sont solides ? Il clique rarement sur les liens en description, par flemme.

**Ce qu'il espère de Filum** : un moyen rapide et visuel de juger de la solidité du contenu, sans devoir cliquer sur 11 liens.

### Persona tertiaire — Sami, fact-checker professionnel

Sami travaille pour CheckNews. Il enquête sur la viralité d'un contenu, doit remonter à ses sources, vérifier qu'elles n'ont pas été déformées.

**Ce qu'il espère de Filum** : un moyen de remonter aux sources, de comparer la version archivée à la version vivante d'un article, de tracer la filiation entre les contenus.

---

## Parcours utilisateur principal

### Parcours du créateur (Léa)

**Étape 1 — Inscription**
Léa visite `filum.app`. Page d'accueil simple. Bouton "Créer ma première fiche". Elle est invitée à se connecter avec Google. Premier consentement OAuth. Elle saisit son pseudonyme (`@lea-c`), son rôle (vulgarisatrice climat), accepte les CGU.

**Étape 2 — Création de fiche, vide**
Elle arrive sur son tableau de bord, vide. Bouton "Nouvelle fiche". Formulaire en deux étapes :
- Étape A : titre du contenu, plateforme principale (YouTube, blog, podcast, autre), URL canonique du contenu, brève description
- Étape B : ajout des sources, une par une, via un formulaire (titre, URL, type [peer-reviewed, institutionnel, presse, matériel original], date, annotation contextuelle, indicateur "source pivot" oui/non)

**Étape 3 — Archivage des sources**
À mesure qu'elle ajoute des URLs, Filum lance en arrière-plan une requête vers Wayback Machine pour archiver chaque URL. Indicateur de progression visible. En moins d'une minute, toutes les sources sont archivées.

**Étape 4 — Génération de la fiche**
Elle clique "Publier la fiche". Filum génère :
- Hash SHA-256 du contenu de la fiche (sources + métadonnées)
- Signature Ed25519 avec la clé associée à son compte
- Horodatage simple en MVP (pas d'horodatage qualifié eIDAS en phase 1)
- URL publique stable : `filum.app/@lea-c/arctique-2026`

**Étape 5 — Partage**
Sur la page de confirmation, Léa voit :
- Sa page publique avec aperçu
- Trois boutons : "Copier le lien", "Partager", "Voir l'aperçu OpenGraph"
- Code embed à venir en phase 2

Elle copie le lien et le colle dans la description de sa vidéo YouTube.

### Parcours du lecteur (Marc)

**Étape 1 — Arrivée**
Marc clique sur le lien Filum dans la description de la vidéo. La page publique s'ouvre.

**Étape 2 — Découverte de la fiche**
Au-dessus de la fold :
- Titre du contenu (en serif, élégant)
- Identité de Léa (vérifiée Google)
- Bandeau de statistiques (4 chiffres : nombre de sources, peer-reviewed, archivées, fiches connexes)

Au milieu de la page :
- **Le graphe interactif des sources.** Marc voit immédiatement la structure du raisonnement de Léa. Il peut cliquer sur un nœud, voir s'ouvrir une fiche compacte avec titre, auteur, date, tags. Il glisse, zoome, explore.

En dessous :
- Liste détaillée des sources, triable par centralité/date/type
- Chaque source est dépliable (annotation contextuelle, extraits utilisés, liens vers snapshot et version vivante)

**Étape 3 — Vérification**
Marc clique sur une source dépliée, ouvre le snapshot archivé. Il lit le passage en question. Il revient à la fiche. Sa confiance dans le contenu de Léa augmente.

### Parcours du fact-checker (Sami)

Sami fait la même chose que Marc, mais en mode plus systématique. Il compare la version archivée à la version vivante de plusieurs sources. Il télécharge le PDF de la fiche pour archiver son enquête. Il pourra utiliser l'API publique pour des recherches automatisées en phase 3.

---

## Écrans détaillés

### E1 — Page d'accueil publique (`/`)

**Contenu**
- Bandeau haut : logo Filum, lien "Découvrir", lien "Se connecter", bouton "Créer une fiche"
- Hero : pitch en une phrase + sous-pitch en deux lignes + bouton "Voir un exemple"
- Section "Comment ça marche" : 3 étapes illustrées (sourcer, signer, partager)
- Section "Exemples de fiches publiques" : 3-4 fiches en avant (créateurs initiaux)
- Footer : à propos, code source GitHub, mentions légales, contact

**Comportement**
- Si connecté, "Se connecter" → "Mon tableau de bord"
- Bouton "Créer une fiche" → flux OAuth si déconnecté

### E2 — OAuth Google + onboarding

**Contenu**
- Page intermédiaire pendant OAuth Google
- Après retour Google, formulaire de complétion :
  - Pseudonyme (obligatoire, unique, valide en URL slug)
  - Rôle/description courte (optionnel, max 80 chars)
  - Avatar (par défaut initiales sur fond coloré, upload optionnel)
  - Acceptation CGU + politique de confidentialité

**Comportement**
- Validation côté client + serveur du slug
- Création utilisateur en base
- Génération de la paire de clés Ed25519 associée

### E3 — Tableau de bord (`/dashboard`)

**Contenu**
- En-tête : avatar + pseudo + bouton "Nouvelle fiche"
- Liste des fiches créées (par défaut, vide en MVP)
- Chaque fiche : titre, URL publique, date de publication, nombre de vues (phase 2), boutons Modifier/Voir/Partager
- Lien "Ma page-identité publique"

**Comportement**
- Limité à 10 fiches par mois en plan gratuit (mais en MVP, illimité — à instrumenter pour mesurer)
- Tri par date décroissante

### E4 — Nouvelle fiche, étape A (`/dashboard/new`)

**Contenu**
- Champ titre du contenu
- Champ URL canonique du contenu (YouTube, blog, etc.)
- Sélecteur de plateforme (YouTube, podcast, blog/article, X/Bluesky, autre)
- Champ description courte (optionnel)
- Bouton "Suivant"

### E5 — Nouvelle fiche, étape B (`/dashboard/new/sources`)

**Contenu**
- Liste vide initialement, bouton "Ajouter une source"
- Formulaire d'ajout d'une source :
  - URL (obligatoire)
  - Titre (auto-rempli si possible via fetch de la page, sinon manuel)
  - Auteurs (texte libre)
  - Date de publication de la source
  - Type (sélecteur : peer-reviewed, institutionnel, presse, matériel original)
  - Annotation contextuelle (texte libre, optionnel, max 500 chars — "pourquoi je cite cette source")
  - Toggle "Source pivot" (oui/non — sources les plus structurantes du raisonnement)
- Au-dessus, indicateur de progression d'archivage Wayback ("3/5 sources archivées")
- Boutons "Précédent", "Publier la fiche"

**Comportement**
- À l'ajout d'une URL, requête asynchrone vers Wayback pour archiver
- Validation : au moins 1 source pour publier
- Sauvegarde brouillon automatique toutes les 30 secondes

### E6 — Page publique de fiche (`/@pseudo/slug`)

C'est l'écran le plus important. Voir la maquette visuelle validée précédemment.

**Contenu (de haut en bas)**
- Bandeau supérieur discret : `fiche bibliographique · filum.app/@lea-c/arctique-2026`
- Titre du contenu en serif, élégant
- Identité du créateur (avatar, nom, badge "vérifié Google", description courte, date)
- Bandeau de statistiques (4 chiffres clés)
- **Graphe interactif des sources** (zone principale, ~360px de hauteur)
  - Nœuds colorés par type
  - Taille proportionnelle à la centralité
  - Liens entre nœuds montrant la filiation
  - Halo sur le nœud central (la vidéo)
  - Au clic sur un nœud, fiche compacte qui s'ouvre
- Légende sous le graphe (4 types de sources + indication de taille)
- Liste détaillée des sources
  - Tri par centralité/date/type
  - Chaque source dépliable
- Bandeau d'authenticité (signature, horodatage, snapshots)
- Actions : Partager, Embarquer (placeholder phase 2), Exporter PDF

**Comportement**
- Page statique générée côté serveur (SSR) pour SEO et OpenGraph
- Graphe interactif côté client (Svelte)
- OpenGraph riche : image dynamique générée à la volée

### E7 — Page-identité du créateur (`/@pseudo`)

**Contenu**
- Avatar grand format, nom, description courte, comptes externes liés (en phase 2 : YouTube, X)
- Statistiques globales : nombre de fiches publiées, nombre total de sources, nombre total de citations
- Liste chronologique des fiches publiées
- Section "Mes positions" (champ libre, à venir en phase 2)
- Section "Droit de réponse" (à venir en phase 2)

**Comportement**
- Page statique générée côté serveur
- Cache invalidé à chaque publication de fiche
- JSON-LD/Schema.org riche pour l'indexation par les IA

### E8 — Page d'erreur, mentions légales, à propos

À traiter de manière standard, sans surinvestissement design.

---

## Features priorisées

| ID | Feature | Priorité | Estimation |
|---|---|---|---|
| F01 | OAuth Google + création utilisateur | P0 | 0.5j |
| F02 | Modèle de données + migrations | P0 | 0.5j |
| F03 | Création de fiche (CRUD basique) | P0 | 1j |
| F04 | Ajout/suppression de sources | P0 | 0.5j |
| F05 | Archivage Wayback Machine asynchrone | P0 | 0.5j |
| F06 | Hash + signature Ed25519 de la fiche | P0 | 0.5j |
| F07 | Page publique de fiche (statique + graphe) | P0 | 1.5j |
| F08 | Page-identité créateur (basique) | P1 | 0.5j |
| F09 | OpenGraph dynamique | P1 | 0.5j |
| F10 | Export PDF de la fiche | P2 | 0.5j |
| F11 | Tableau de bord créateur | P1 | 0.5j |
| F12 | Page d'accueil publique | P1 | 0.5j |
| F13 | Modèles dbt + analytics | P1 | 0.5j |
| F14 | Tests et documentation | P0 | 0.5j |

**Total estimé** : 8-9 jours pour un solo développeur assisté IA. **Sur 7 jours, certaines features P2 sont reportées.**

---

## Critères de succès du MVP

Le MVP est considéré réussi si :

1. **Au moins 3 créateurs cibles** (vulgarisateurs scientifiques) ont créé une fiche utilisable
2. **Au moins une fiche** a été partagée par son créateur sur ses canaux publics
3. **Au moins 100 vues** cumulées sur les fiches publiques en 30 jours
4. **Le développeur** peut faire une démo de 5 minutes convaincante à un prospect ou recruteur

---

*Pour l'architecture technique, voir [`02-tech-architecture.md`](./02-tech-architecture.md).*
