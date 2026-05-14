# 12 — Prochaines étapes (post-MVP, 2026-05-14)

> Document opérationnel maintenu après stabilisation du MVP (publish prod opérationnel). Lit-le après [`STATE.md`](../STATE.md) et [`10-mvp-completion-plan.md`](./10-mvp-completion-plan.md).
>
> Les jalons MVP M1+M2+M3 sont terminés. Le bug critique du publish (résisté à 3 PRs avant fix root cause via tz-aware datetime, cf. PR #36) est résolu. La plateforme est exploitable end-to-end : Google OAuth → création fiche → ajout sources → publication signée → consultation publique.
>
> Ce document fixe le **chemin critique** des 3-6 prochains mois. Il décrit aussi les **arbitrages d'architecture** majeurs qui sont à trancher.

---

## 1. Trois axes de travail parallélisables

### Axe A — Réduire la dépendance aux plateformes (souveraineté du contenu)

**Constat.** Aujourd'hui Filum suppose que le contenu original (vidéo, article, podcast) vit sur une plateforme tierce (YouTube, Substack, Spotify, etc.). Le créateur cite son URL et Filum atteste la paternité via signature. **Problème** : si la plateforme supprime, censure ou perd le contenu, l'attestation pointe vers un trou.

**Vision.** Filum doit pouvoir héberger directement les contenus originaux, sans devenir une plateforme de distribution. Le créateur garde le contrôle, Filum stocke + sert les fichiers, et l'attestation de contenu (ADR-019) pointe vers l'URL Filum (ou un mix Filum + URL externe).

### Axe B — Archivage proactif et redondant des sources

**Constat.** Wayback Machine est branché sur `POST /sources` mais (1) c'est best-effort (~10 req/min), (2) Wayback peut rater (page dynamique, JS lourd, paywall), (3) pas de fallback. La promesse Filum « les sources sont pérennes » repose actuellement sur un service tiers gratuit unique.

**Vision.** Pipeline d'archivage multi-cible : Wayback Machine en priorité, Archive.today en backup, snapshot HTML+screenshot stocké en propre chez Filum pour les URLs sensibles. Statut visible côté fiche.

### Axe C — Refonte backend post-pivot ADR-019

**Constat.** ADR-019 a redéfini la signature cryptographique : plus sur la fiche bibliographique mais sur le triplet `(creator_id, content_url, attested_at)`. **Le code backend est encore à l'ancien modèle** : la table `biblio_cards` a toujours `canonical_hash`/`signature`/`signed_at`, et `publish_card` les remplit. Le frontend ignore ces champs (PR #32) mais le backend ne les a pas dropés.

**Vision.** Migration `006_create_content_attestations + drop_card_signature`, refonte endpoint publish (devient flip de statut + création d'une attestation), endpoint `POST /attestations/content` exposé, endpoint `GET /attestations/{id}/verify` public.

---

## 2. Axe A — Stockage cloud du contenu original

### 2.1 Hypothèses produit à valider

- Les créateurs (en priorité vulgarisateurs scientifiques) **veulent-ils** héberger leur contenu chez Filum, ou bien Filum doit-il rester un index/pointeur ?
- À quel volume parle-t-on ? Une vidéo YouTube fait 50-500 Mo. Un article 1-10 Mo. Un podcast 30-100 Mo.
- Filum doit-il servir la lecture/streaming, ou juste stocker un fichier téléchargeable ?

Avant de coder, **interview 3 créateurs cibles** sur ces points. Sans validation, on risque de construire du stockage coûteux pour personne.

### 2.2 Comparatif fournisseurs (free-tier first, ADR-style)

| Fournisseur | Free tier | Egress | Decentralisé | Verdict pour Filum |
|---|---|---|---|---|
| **Cloudflare R2** | 10 GB stockage + 1M ops/mois | **0$ egress** | non | ⭐ recommandé. S3-compatible, zero egress = critique pour servir du contenu. Pas de vendor lock-in. |
| **Backblaze B2** | 10 GB stockage | 1 GB/jour gratuit puis 0.01$/GB | non | Bon backup secondaire. Plus mature que R2 pour la durabilité. |
| **AWS S3** | 5 GB 12 mois | 0.09$/GB (cher) | non | À éviter en MVP : payant rapidement, egress prohibitif si Filum prend. |
| **IPFS public + Pinata/web3.storage** | 1 GB pinning | gratuit | oui | Aligné avec mission Filum (décentralisation), mais latence + complexité opérationnelle élevées. À évaluer en phase 2 comme couche additionnelle, pas remplacement. |
| **Internet Archive** | illimité | gratuit | partiellement | API d'upload existe (`internetarchive` lib Python). Excellent pour archivage long terme mais pas pour streaming live. À combiner avec R2. |

**Reco MVP** : **R2 comme stockage principal**, **Internet Archive comme miroir d'archivage long terme**. Implémentation découplée pour ajouter B2 ou IPFS plus tard sans refonte.

### 2.3 Découpage technique

1. **ADR-020 — Stockage R2 comme blob store officiel**
   - Configurer bucket R2 + clés API
   - Service Python `BlobStorage` (interface) avec impl `R2BlobStorage` et `InternetArchiveBlobStorage`
   - Migration `007_add_content_files` : table `content_files (id, user_id, content_url FK→content_attestations, storage_url, mime_type, size_bytes, checksum_sha256, uploaded_at)`
2. **Endpoint `POST /uploads/initiate`** : retourne URL pré-signée R2 (PUT direct, pas de proxy backend) + un upload_id
3. **Endpoint `POST /uploads/complete`** : crée la `content_attestation` et la `content_file` une fois l'upload R2 confirmé
4. **Frontend** : composant `<ContentUploader>` qui upload directement sur R2 (URL pré-signée), affiche progress, gère gros fichiers
5. **Service `MirrorService` (background task)** : après upload R2, miroir asynchrone vers Internet Archive via la lib `internetarchive`. Statut visible côté fiche.

**Coût estimé** : 10 GB R2 free tier = ~20 vidéos courtes ou ~1000 articles. Zero egress = on peut servir le contenu directement depuis Filum sans surcoût. Au-delà du free tier : ~0.015$/GB stockage, toujours zero egress.

### 2.4 Sécurité

- Limites strictes : taille max 500 Mo par fichier en MVP, 1 Go/utilisateur (anti-abus)
- Scan antimalware via ClamAV (Lambda ou worker R2 ?) avant exposition publique
- Vérification du checksum SHA-256 côté backend après upload (cohérence avec attestation crypto)
- Pas d'exécution côté serveur (jamais de PHP/JS exécuté depuis le bucket)
- Headers `Content-Disposition: attachment` pour les types non-streaming (PDF, etc.) si on veut éviter qu'un fichier malveillant s'ouvre dans le navigateur

---

## 3. Axe B — Archivage proactif multi-cible

### 3.1 État actuel

- `WaybackService` (`apps/backend/app/services/wayback.py`) appelle `https://web.archive.org/save/{url}` en `asyncio.create_task` après ajout d'une source
- Statut stocké dans `Source.archive_status` ∈ {pending, archived, failed}
- Pas de retry, pas de fallback, pas de visibilité publique sur les échecs

### 3.2 Cible

| Service | Rôle | API |
|---|---|---|
| Wayback Machine | Source primaire (réseau de confiance, déjà branché) | `GET /save/{url}` |
| Archive.today (archive.ph) | Backup, capture les JS-heavy pages que Wayback rate | `POST /submit/?url={url}` (rate-limité, headless OK) |
| Snapshot HTML + screenshot Filum | Dernier recours pour les pages que ni Wayback ni Archive.today ne capturent (paywall, intranet sensible) | Playwright headless dans worker, stocké sur R2 |

### 3.3 Découpage

1. **Refacto `WaybackService` → `ArchiveOrchestrator`** : essaie Wayback, puis Archive.today si échec après 30s, puis snapshot Playwright si toujours rien après 2 min. Retry exponentiel par source : 1h, 6h, 24h, 7j.
2. **Migration `008_add_archive_attempts`** : table `archive_attempts (id, source_id FK, provider, attempted_at, status, archive_url, error_msg)`. Permet de tracer toutes les tentatives.
3. **Job cron Railway** : 1×/jour, retry tous les `pending`/`failed` < 7 jours. Hors fenêtre = abandon explicite + statut `archive_status='unarchivable'`.
4. **Frontend** : badge visible sur chaque source (icône + tooltip) avec lien vers l'archive réelle. Statut "non archivable" rendu honnêtement.
5. **Endpoint public** `GET /sources/{id}/archive` : retourne le meilleur archive disponible (URL + provider + date) pour qu'un consommateur tiers (lecteur, agent IA) puisse résoudre.

### 3.4 Considérations

- Wayback Machine n'aime pas le bruit : respecter `Retry-After`, headers `User-Agent` propres
- Archive.today rate-limite agressivement : pas plus de 1 req/30s/IP, et certaines IPs Cloud Provider sont bannies. Test avant prod.
- Playwright pour snapshot Filum-hosted = +500 Mo Docker image. À isoler dans un worker dédié, pas dans le container principal.

---

## 4. Axe C — Refonte backend post-ADR-019

### 4.1 Migration `006_content_attestations_and_drop_card_signature`

- `CREATE TABLE content_attestations (id, user_id FK, content_url, attested_at, canonical_hash, signature, created_at)`
- `ALTER TABLE biblio_cards DROP COLUMN canonical_hash, DROP COLUMN signature, DROP COLUMN signed_at` (`published_at` reste pour l'horodatage UX)
- Index `(user_id, content_url)` non-unique (un même créateur peut re-attester ultérieurement si l'URL change de canonique)

### 4.2 Service `AttestationService`

- `create_content_attestation(user_id, content_url) → ContentAttestation` : RFC 8785 canonicalise le triplet, SHA-256, signe Ed25519, stocke
- `verify_attestation(attestation_id) → {valid: bool, reason?: str}` : re-calcule hash, vérifie signature avec clé publique du créateur

### 4.3 Endpoints

- `POST /attestations/content` (authentifié) — corps : `{content_url}`. Crée une attestation pour le user courant.
- `GET /attestations/{id}` (public) — retourne l'attestation + hash + signature + clé publique
- `GET /attestations/{id}/verify` (public) — exécute la vérification et retourne `{valid, hash, signature_check}`
- `POST /cards/{id}/publish` simplifié : flip statut `draft → published`, optionnellement crée une `ContentAttestation` pour `card.content_url` si non existante.

### 4.4 Refonte `seed_demo.py`

- Plus de re-signature de fiche au seed
- À la place : créer une `ContentAttestation` pour la vidéo démo de `example`
- Supprimer toute lecture de `card.canonical_hash` / `card.signature` côté code

### 4.5 Frontend cleanup

- Retirer définitivement les champs `canonical_hash`, `signature`, `signed_at` de `apps/frontend/src/lib/api/types.ts`
- Adapter `CardResponse` et `PublicCard` schemas

---

## 5. Hors chemin critique mais qui mûrit

- **Tests E2E Playwright** : couvrir le golden path login → create card → add source → publish → public view. Indispensable avant de toucher au pipeline crypto.
- **Sentry** : à brancher quand on aura un vrai trafic. Avant ça, `/health/publish-diagnose` et les logs Railway suffisent.
- **Import Zotero / BibTeX / Obsidian** : grosse valeur d'usage mais bloqué tant que `content_attestations` n'est pas en place (sinon on importe sans pouvoir attester).
- **Plugin navigateur** : utile mais second ordre. À faire après que 3-5 créateurs actifs aient demandé.
- **Domain `filum.app`** : à acheter dès qu'on a un premier ambassadeur prêt à publier. Pas avant.

---

## 6. Ordre d'exécution recommandé

1. **Axe C (1-2 semaines)** : refonte backend post-ADR-019. Indispensable car bloque tout le reste (import, attestation par URL, etc.). Bonne nouvelle : c'est local, pas de prod-risk au-delà de la migration.
2. **Axe B (1 semaine)** : multi-target archive. Le snapshot Filum-hosted (Playwright) peut être reporté ; Wayback + Archive.today couvrent déjà 95 % des cas.
3. **Validation produit (1 semaine)** : interviewer 3 créateurs cibles sur l'hypothèse Axe A (auto-hébergement contenu). Si OUI → axe A. Si NON → re-prioriser sur import Zotero / plugin navigateur.
4. **Axe A (2-3 semaines si validé)** : R2 + Internet Archive + endpoint upload.

**Ne pas tout faire en parallèle**. Solo dev + assistance IA = un axe à la fois.

---

## 7. Anti-features confirmées

Inchangé depuis `10-mvp-completion-plan.md` §5 : pas de Sentry/Plausible avant signal utilisateur, pas de domaine custom avant 5 créateurs actifs, pas de C2PA avant phase 3, pas de MCP server avant API publique stable.

S'ajoute :
- **Pas d'IA générative pour produire des bibliographies** : Filum n'est pas Perplexity. La valeur produit = sourçage humain + traçabilité, pas génération automatique.
- **Pas de social features** (commentaires, follows, like) : ce n'est pas un réseau social, c'est une infrastructure.

---

*Document à actualiser après chaque axe livré. Si un axe est invalidé (interview produit négative, blocage technique majeur), le marquer explicitement plutôt que de le laisser en l'état.*
