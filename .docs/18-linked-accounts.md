# Comptes plateformes liés (YouTube, Instagram, X, TikTok)

> Exploration d'implémentation demandée le 2026-07-19. Objectif produit : le compte
> Philum devient le hub d'identité du créateur — il centralise et affiche ses
> connexions aux plateformes où il publie.

---

## Pourquoi

1. **Crédibilité de la fiche publique** : un badge "chaîne YouTube vérifiée" sur
   `/@slug` renforce le lien créateur ↔ contenu, qui est précisément ce que
   Philum signe (ADR-019 : triplet `(creator_id, content_url, attested_at)`).
2. **Pré-remplissage** : une fois la chaîne connectée, on peut lister les vidéos
   du créateur et proposer une fiche par vidéo (réduction massive de la friction).
3. **Boucle de distribution** : à terme, publier automatiquement le lien de la
   fiche dans la description de la vidéo (YouTube Data API `videos.update`).

---

## Trois niveaux d'implémentation

### v0 — Liens déclaratifs (effort : S, faisable immédiatement)

Le créateur saisit ses URLs de profils dans les réglages ; elles s'affichent
sur sa page publique. Aucune vérification.

- **Modèle** : table `linked_accounts` (voir schéma ci-dessous), `verified_at = NULL`.
- **API** : `GET/PUT /api/v1/users/me/linked-accounts` + exposition read-only
  dans le payload public du créateur.
- **Frontend** : section "Mes plateformes" dans le dashboard + rangée d'icônes
  sur `/@slug`.
- **Risque** : usurpation possible (n'importe qui peut déclarer n'importe quelle
  chaîne) → afficher sans badge "vérifié".

### v1 — Vérification de propriété sans OAuth (effort : M)

Deux méthodes complémentaires, aucune app review requise :

1. **rel=me / lien retour** (méthode Mastodon) : le créateur place l'URL de son
   profil Philum dans la bio de sa chaîne/compte. Philum scrape la page publique
   (ou l'API oEmbed) et vérifie la présence du lien → `verified_at` renseigné,
   `verification_method = 'backlink'`.
   - YouTube : le lien apparaît dans l'onglet "À propos" (scrapable, ou via
     `channels.list` avec une simple clé API, quota gratuit 10 000 unités/jour).
   - X : bio accessible via scraping léger (l'API payante n'est pas nécessaire
     pour une seule page) — fragile mais suffisant en pré-MVP.
   - Instagram/TikTok : bio publique scrapable, anti-bot plus agressif → tenter,
     fallback sur v0 non vérifié.
2. **Code unique dans la bio** : Philum génère `philum-verify-a1b2c3`, le
   créateur le colle temporairement dans sa bio, Philum vérifie puis il peut le
   retirer. Plus robuste que le backlink quand la plateforme réécrit les URLs.

### v2 — OAuth complet (effort : L, dépendances externes)

| Plateforme | Mécanisme | Prérequis | Difficulté |
|---|---|---|---|
| **YouTube** | Google OAuth existant + scope `youtube.readonly` | Aucun nouveau client — on étend le client OAuth déjà en prod | **Faible** — à faire en premier |
| **X** | OAuth 2.0 PKCE, scope `users.read` | Compte développeur (free tier très limité) | Moyenne |
| **TikTok** | Login Kit (`user.info.basic`) | App review TikTok (délai en semaines) | Moyenne-haute |
| **Instagram** | Meta Graph API (Business/Creator account requis) | App review Meta + business verification | **Haute** |

- **Tokens** : chiffrés AES-GCM avec la `master_encryption_key` existante
  (même mécanique que les clés privées Ed25519). Refresh tokens en base,
  access tokens jamais loggés.
- **YouTube d'abord** : le client Google OAuth est déjà configuré ; ajouter le
  scope incrémental au flow de liaison (pas au login — sinon friction à
  l'inscription). `channels.list(mine=true)` donne l'ID de chaîne → vérification
  forte + import possible des vidéos.

---

## Schéma de données proposé

```sql
CREATE TABLE linked_accounts (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR NOT NULL,          -- 'youtube' | 'instagram' | 'x' | 'tiktok' | 'twitch' | 'site'
    url VARCHAR NOT NULL,               -- URL publique du profil
    handle VARCHAR,                     -- @nom affiché
    verified_at TIMESTAMPTZ,            -- NULL = déclaratif (v0)
    verification_method VARCHAR,        -- 'backlink' | 'bio-code' | 'oauth'
    oauth_token_encrypted BYTEA,        -- v2 uniquement, AES-GCM
    created_at TIMESTAMPTZ NOT NULL,
    UNIQUE (user_id, platform, url)
);
```

Payload signé des attestations **inchangé** (contrainte ADR-019 : immuable).
La vérification de compte est une méta-donnée du profil, pas de l'attestation.

---

## Recommandation

1. **Maintenant** : v0 (liens déclaratifs) — petit, visible, zéro dépendance.
2. **Ensuite** : v1 backlink pour YouTube (clé API simple, quota gratuit).
3. **Quand un ambassadeur YouTube est actif** : v2 OAuth YouTube (scope
   incrémental sur le client existant) + import des vidéos.
4. **Meta/TikTok OAuth** : seulement sur demande d'un créateur concerné —
   l'app review ne vaut pas le coût avant.
