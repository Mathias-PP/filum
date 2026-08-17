# 09 — Mode privé et intégrations (Zotero / Obsidian / Notion)

> Spec dédiée, **non implémentée**. Sert de pierre angulaire pour les itérations 3+. Signale que **Philum n'est pas un remplaçant de Zotero, c'est un compagnon**.

---

## Mode privé

Aujourd'hui, toute fiche Philum est publique dès `publish`. L'itération 3 introduit un mode privé : une fiche est créée et conservée par son auteur sans être indexée publiquement.

- **Modèle** : ajouter un enum `visibility: 'public' | 'private' | 'unlisted'` sur `BiblioCard` (défaut `public` pour conserver le comportement actuel).
- **Endpoints** :
  - `GET /api/v1/me/cards/private` — liste les fiches privées du user authentifié (cookie session).
  - `GET /api/v1/me/cards/{id}` — détail d'une fiche privée, refuse si `visibility != 'private'` ou si pas owner.
- **Signature** : les fiches privées sont signées comme les publiques (`Ed25519`) ; la signature reste vérifiable hors-ligne. La visibilité **ne rentre pas** dans le `canonical_hash` (pas de re-signature si l'utilisateur bascule public ↔ privé).
- **UI** : un toggle « visibilité » dans `/dashboard/cards/{slug}/edit` (futur).

---

## Connectivité Zotero

Zotero est l'outil de référence pour la gestion bibliographique académique. Philum se positionne en **compagnon** :

- **Lecture (phase 1)** : import via export RIS / BibTeX. L'utilisateur uploade son fichier d'export Zotero ; Philum crée une carte privée par item ou regroupe en une seule.
- **Écriture (phase 2)** : push d'une fiche Philum vers une collection Zotero via l'API Zotero v3 (token utilisateur stocké chiffré côté Philum).
- **Sync (phase 3, à discuter)** : sync bidirectionnel des annotations. À évaluer selon retours utilisateurs.

---

## Connectivité Obsidian

- **Export `.md`** d'une fiche Philum vers le coffre Obsidian de l'utilisateur, avec frontmatter YAML compatible Dataview :
  ```yaml
  ---
  filum_id: <uuid>
  filum_url: https://philum.app/@user/card-slug
  signature: <ed25519-signature>
  signed_at: <iso8601>
  sources: 14
  ---
  ```
- Le corps `.md` reprend titre + description + liste des sources avec lien Philum stable.

---

## Connectivité Notion

- Push d'une fiche Philum vers une page Notion d'une base sélectionnée par l'utilisateur, via le SDK Notion officiel et un Integration token utilisateur (chiffré côté Philum, même schéma que les keypairs).
- Champs mappés : titre, auteurs, description, URL Philum, signature.

---

## Modèle utilisateur — extensions

```
users
├── id (existing)
├── …
└── integrations
    ├── zotero_token (encrypted, nullable)
    ├── notion_token (encrypted, nullable)
    └── obsidian_vault_path (text, nullable, client-stored, never sent server-side)
```

Ces tokens suivent le même schéma de chiffrement que `encrypted_private_key` (AES-GCM avec la `master_encryption_key`).

---

## Hors scope de cette spec

- OAuth direct vers Zotero (à évaluer ; pour MVP-3 un PAT utilisateur suffit).
- Sync temps réel.
- Détection automatique des doublons entre Philum et Zotero.
