# Capabilities & Workflows — ce que l'agent peut faire

> Complément fonctionnel aux fiches techniques [`04-tools-read.md`](04-tools-write.md) et [`05-tools-write.md`](05-tools-write.md). Ces fiches décrivent le code ; ce document décrit **l'intention** — ce que l'agent peut réaliser, dans quel ordre, et avec quels outils.

---

## 1. Capacités par intention

### Créer une fiche

L'agent peut créer une fiche Philum de bout en bout, depuis un contenu source (vidéo, article, podcast) ou une question bibliographique.

| Étape | Outil | Ce qui se passe |
|---|---|---|
| 1. Créer la fiche | `create_card` | Définit le `card_kind` (`contenu` ou `sujet`), le titre, la description, et la `content_url` (obligatoire pour `contenu`). Rend le slug et l'URL publique future. |
| 2. Remplir le transcript | `set_content_text` | Pose le texte complet du contenu (transcript vidéo, article, etc.). `confirm_publication_rights=true` obligatoire. Borne : 500k chars. |
| 3. Importer les sources | `import_from_content_url` | Extrait automatiquement les références citées dans la `content_url` (bouton UI « Extraire les sources »). Rend une liste de candidats — l'agent choisit lesquels ajouter. |
| 4. Parser du texte biblio | `parse_biblio` | Si l'agent a du texte biblio brut (BibTeX, markdown, copié-collé), le parse et enrichit avec LLM. |
| 5. Ajouter les sources | `add_source` | Pose chaque source avec ses métadonnées (titre, auteurs, DOI, journal, category, stance, etc.). Déduplique par DOI/URL. |
| 6. Ajouter des extraits | `add_excerpt` | Pose un verbatim dans une source. Le serveur **relit la page** pour vérifier que le passage existe — le texte fourni est le passage à retrouver, pas le contenu. Max 12 extraits/source. |
| 7. Suggérer des extraits | `suggest_excerpts` | Le LLM propose des candidats de verbatim à partir du texte de la source. Chaque candidat est vérifié contre la page réelle (anti-hallucination). |
| 8. Annoter un extrait | `annotate_excerpt` | Le LLM suggère un titre et un contexte pour un extrait donné, avant de le poser. |
| 9. Découper un texte | `chunk_text` | Découpe un texte long en chunks candidats pour l'extraction d'extraits. |
| 10. Vérifier les extraits | `verify_excerpts` | Relit chaque extrait vs la page live. Verdicts : `found`, `moved`, `missing`, `unreadable`. Accepte `provided_text` pour les pages anti-bot. |
| 11. Signer le contenu | `create_content_attestation` | Signature Ed25519 du `content_url` — preuve cryptographique de l'engagement initial. **Approuvé.** |
| 12. Archiver les sources | `archive_sources` | Passe les sources en `pending` pour le worker Wayback. **Approuvé.** |
| 13. Publier | `publish_card` | Passe la fiche de `draft` à `published`. Refuse si `contenu` sans `content_url`. **Approuvé.** |

### Modifier une fiche existante

| Action | Outil | Notes |
|---|---|---|
| Éditer les métadonnées | `update_card` | Titre, description, card_kind, content_url, visibility, etc. Slug immuable. |
| Ajouter/Modifier/Supprimer une source | `add_source` / `update_source` / `delete_source` | URL immuable sur `update_source` — pour changer l'URL, supposer puis recréer. `delete_source` est approuvé. |
| Ajouter/Modifier/Supprimer un extrait | `add_excerpt` / `update_excerpt` / `delete_excerpt` | `delete_excerpt` est **physiquement irréversible** (pas de soft-delete). Approuvé. |
| Gérer les connexions | `list_connections` / `confirm_connection` / `remove_connection` | Le serveur suggère des liens fiche→fiche via `linked_card` ; l'agent confirme ou retire. |

### Gérer le cycle de vie

| Action | Outil | Notes |
|---|---|---|
| Lister ses fiches | `list_my_cards` | Max 200, avec `total` et `truncated`. |
| Voir le détail d'une fiche | `get_my_card` | Brouillon compris, content_text tronqué à 20k. Montre `excerpts_verified` / `excerpts_unreadable` par source. |
| Lister les sources | `list_sources` | Dans l'ordre d'affichage, avec IDs pour mutation. |
| Chercher dans ses extraits | `search_my_excerpts` | Full-text dans les extraits de l'utilisateur. |
| Supprimer (corbeille) | `delete_card` | Soft-delete + sources. Reversible 90j. **Approuvé.** |
| Restaurer | `restore_card` | Sort de la corbeille. |
| Voir la corbeille | `list_deleted_cards` | Max 200. |

### Explorer le graphe public

| Action | Outil | Notes |
|---|---|---|
| Chercher des fiches | `search_cards` | Full-text public : titre, description, auteurs, créateur, sources. Accent-indifférent. |
| Voir une fiche publique | `get_card` | Détail compact + sources (sans extraits). Rend `linked_card` pour chaque source. |
| Voir une source publique | `get_source` | Seul outil qui donne le texte des extraits verbatim. |
| Trouver qui cite une source | `find_cards_citing` | Par URL ou DOI. Normalise les variantes (www, http, trailing slash, query params). |
| Identifier qui parle | `whoami` | Rend `{creator, display_name}` du token porteur. |

### Suivre les citations

| Action | Outil | Notes |
|---|---|---|
| Voir qui cite mes fiches | `list_incoming_citations` | `is_new` pour les entrées depuis la dernière consultation. |
| Marquer comme lu | `mark_citations_seen` | Efface les `is_new`. |

### Attestations & vérification

| Action | Outil | Notes |
|---|---|---|
| Créer une attestation | `create_content_attestation` | Signature Ed25519. **Approuvé.** |
| Vérifier une attestation | `verify_attestation` | Rend `valid` + raison. |
| Lire une attestation | `get_attestation` | Lecture publique par ID. |

### Réseau & métadonnées

| Action | Outil | Notes |
|---|---|---|
| Transcript YouTube | `get_youtube_transcript` | Via API interne. |
| Métadonnées URL | `get_url_metadata` | Titre, description, auteurs, date. SSRF protégé. |

### Graphe mémoire (STARTER, non exposé par défaut)

| Action | Outil | Notes |
|---|---|---|
| Interroger le graphe | `recall_memory` | Seed entities depuis une question, traverse N hops, rend triples + fiche source. SQL pur, ~2ms. |
| Reconstruire le graphe | `rebuild_graph` | Reconstruction déterministe depuis toutes les fiches publiques. Pas de LLM. |

### Revendiquer une fiche

| Action | Outil | Notes |
|---|---|---|
| Demander le transfert | `create_claim_request` | Pour les fiches « seed » (auto-générées, sans propriétaire). Processus manuel admin. |

---

## 2. Workflows canoniques

### Workflow A — Créer une fiche depuis une vidéo YouTube

```
1. get_youtube_transcript(url="https://youtube.com/watch?v=...")   → transcript
2. create_card(card_kind="contenu", content_url=url, titre=..., description=...)
3. set_content_text(slug=..., text=transcript, confirm_publication_rights=true)
4. import_from_content_url(content_url=url)                        → candidats
5. add_source(slug=..., title=..., url=..., doi=..., ...)          × N (pour chaque candidat retenu)
6. add_excerpt(slug=..., source_id=..., text="...", contexte="...") × N
7. verify_excerpts(slug=..., source_id=...)                        → verdicts
8. create_content_attestation(slug=...)                            → attestation_id
9. publish_card(slug=...)
```

### Workflow B — Créer une fiche bibliographique (sans contenu source)

```
1. create_card(card_kind="sujet", titre="...", description="...")
2. parse_biblio(text=...)                                          → références structurées
3. add_source(slug=..., ...)                                       × N
4. add_excerpt(slug=..., source_id=..., text="...", contexte="...") × N
5. verify_excerpts(slug=..., source_id=...)
6. publish_card(slug=...)
```

### Workflow C — Enrichir une fiche existante

```
1. get_my_card(slug=...)                                           → état actuel
2. list_sources(slug=...)                                          → sources existantes
3. search_my_excerpts(slug=..., q="...")                           → extraits existants
4. add_source(slug=..., ...)                                       → nouvelle source
5. suggest_excerpts(slug=..., source_id=..., text=...)             → candidats d'extraits
6. add_excerpt(slug=..., source_id=..., text=candidat.text)        × N
7. annotate_excerpt(slug=..., excerpt_id=..., text=...)            → titre + contexte suggérés
8. update_excerpt(slug=..., excerpt_id=..., titre=..., contexte=...)
9. verify_excerpts(slug=..., source_id=...)
```

### Workflow D — Explorer et relier le graphe

```
1. search_cards(q="topic")                                         → fiches pertinentes
2. get_card(creator=..., slug=...)                                  → détail + sources
3. get_source(creator=..., slug=..., source_id=...)                → extraits verbatim
4. find_cards_citing(url="...") ou find_cards_citing(doi="...")
5. list_connections(slug=...)                                       → liens sortants/entrants
6. confirm_connection(slug=..., source_id=...)                      → fige un lien
```

### Workflow E — Gestion de la corbeille

```
1. list_deleted_cards()                                             → fiches supprimées
2. restore_card(slug=...)                                           → restauration
```

### Workflow F — Découvrir et importer depuis une URL

```
1. get_url_metadata(url="...")                                     → métadonnées
2. import_from_content_url(content_url=url)                        → candidats de sources
3. create_card(card_kind="contenu", content_url=url, ...)
4. add_source(slug=..., ...)                                       × N
```

---

## 3. Contraintes transversales

| Contrainte | Valeur | Source |
|---|---|---|
| Extraits max par source | 12 | `_EXTRAITS_MAX_PAR_SOURCE` (`tools_write.py:48`) |
| Taille max content_text | 500 000 chars | `_MAX_CONTENT_TEXT` (`tools_write.py:514`) |
| Rendu tronqué get_my_card | 20 000 chars | `CONTENU_MAX` (`tools_write.py:1119`) |
| Filtre public (read-only) | `status=published & visibility=public & deleted_at IS NULL` | `_PUBLIC` (`tools.py:32`) |
| Rétention corbeille | 90 jours | `delete_card` (`tools_write.py:1294`) |
| Auth MCP | `verify_aud=False` | `auth.py:42` |

---

## 4. Outils requiring approval (human-in-the-loop)

Ces outils émettent un `approval_request` SSE avant exécution — l'utilisateur doit approuver :

| Outil | Raison |
|---|---|
| `publish_card` | Rend la fiche publique |
| `delete_source` | Suppression visible |
| `delete_excerpt` | Suppression physique irréversible |
| `create_content_attestation` | Signature cryptographique |
| `archive_sources` | Déclenche un archivage Wayback |
| `delete_card` | Suppression de la fiche + sources |

---

## 5. Glossaire outil → intention

| Si tu veux... | Outil(s) |
|---|---|
| Créer une fiche | `create_card` |
| Ajouter du texte à une fiche | `set_content_text` |
| Ajouter des références | `add_source`, `add_sources_batch`, `import_from_content_url`, `parse_biblio` |
| Ajouter des verbatim | `add_excerpt`, `suggest_excerpts`, `annotate_excerpt`, `chunk_text` |
| Vérifier que les extraits sont encore là | `verify_excerpts` |
| Publier | `publish_card` |
| Signer cryptographiquement | `create_content_attestation` |
| Archiver les sources | `archive_sources` |
| Chercher dans le graphe public | `search_cards`, `get_card`, `get_source`, `find_cards_citing` |
| Voir mes fiches | `list_my_cards`, `get_my_card` |
| Voir les sources d'une fiche | `list_sources` |
| Chercher dans mes extraits | `search_my_excerpts` |
| Gérer les liens fiche→fiche | `list_connections`, `confirm_connection`, `remove_connection` |
| Supprimer / restaurer | `delete_card`, `restore_card`, `list_deleted_cards` |
| Éditer | `update_card`, `update_source`, `update_excerpt` |
| Supprimer un extrait | `delete_excerpt` (irréversible) |
| Supprimer une source | `delete_source` |
| Voir qui me cite | `list_incoming_citations`, `mark_citations_seen` |
| Vérifier une attestation | `verify_attestation`, `get_attestation` |
| Obtenir des métadonnées | `get_url_metadata`, `get_youtube_transcript` |
| Identifier qui je suis | `whoami` |
| Interroger le graphe mémoire | `recall_memory`, `rebuild_graph` (STARTER) |
| Revendiquer une fiche seed | `create_claim_request` |
