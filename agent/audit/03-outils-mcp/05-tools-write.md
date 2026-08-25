# Outils MCP d'écriture (`tools_write.py`)

## apps/backend/app/mcp_server/tools_write.py
Lu intégralement : oui (1876/1876 lignes, 2 tranches 1-940 / 941-1876) · sha256: dfcf2f950f8a · date: 2026-08-25

40 outils d'écriture déléguant au même modèle que le REST — une seule fois la logique métier, une seule fois les invariants (unicité du slug, propriété de la ressource, capacité maximale, dédup de source par identité du contenu) (`apps/backend/app/mcp_server/tools_write.py:7`).

### Constants

- `_EXTRAITS_MAX_PAR_SOURCE`=12 (`apps/backend/app/mcp_server/tools_write.py:48`) — borne identique à l'endpoint REST.
- `_MAX_CONTENT_TEXT`=500 000 chars (`apps/backend/app/mcp_server/tools_write.py:514`) — un roman entier ; au-delà, un corpus → découpage en fiches.
- `CONTENU_MAX`=20 000 chars (`apps/backend/app/mcp_server/tools_write.py:1119`) — plafond du transcript rendu par `get_my_card` (une vidéo dépasse souvent les 100k).

### Fonctions internes

- `_valeur_enum` — `apps/backend/app/mcp_server/tools_write.py:60` — valide une valeur contre un `Enum` et rend la valeur canonique. Lève `ToolError` avec la liste des valeurs acceptées si hors vocabulaire. Suggère le bon champ si la valeur appartient à un enum voisin (`_ENUMS_VOISINS`, ligne 51). Leçon de la fiche créatine (2026-08-21) : les colonnes `format`/`category`/`author_kind`/`stance` sont des VARCHAR libres en base — une valeur invalide s'inscrit sans erreur puis fait échouer toute relecture.
- `_valeur_date` — `apps/backend/app/mcp_server/tools_write.py:94` — parse `2016`, `2016-03`, `2016-03-15` ; chaine vide → None ; format illisible → `ToolError`.
- `_fiche_du_createur` — `apps/backend/app/mcp_server/tools_write.py:117` — résout `(user, slug)` → `BiblioCard` ; refuse de dire « existe mais pas à vous » (fuite d'existence).
- `_identite` — `apps/backend/app/mcp_server/tools_write.py:134` — clé d'identité d'une source : `doi:<key>` en priorité, `url:<normalisée>` sinon.
- `_identites_deja_citees` — `apps/backend/app/mcp_server/tools_write.py:143` — ensemble des clés d'identité déjà présentes dans une fiche, pour dédup en amont.
- `_source_du_createur` — `apps/backend/app/mcp_server/tools_write.py:150` — résout `(user, source_id)` → `Source` ; même discrétion que `_fiche_du_createur`.
- `_extraits_a_la_volee` — `apps/backend/app/mcp_server/tools_write.py:357` — ajoute les extraits fournis avec `add_source` (aller-retour unique) ; les échecs ne dopent pas la source.
- `_prelever_ou_refuser` — `apps/backend/app/mcp_server/tools_write.py:400` — wrappers `prelever_dans_la_source` / `PassageIntrouvableError` → `ToolError`.
- `_poser_le_verdict` — `apps/backend/app/mcp_server/tools_write.py:408` — inscrit le statut de vérification sur l'extrait au moment de la création (pas laissé à `verify_excerpts`).

### Catalogue exhaustif — 40 outils d'écriture

**Légende** :
- **Cat** = Catégorie (create : création, mutate : mutation, listing : consultation privée, lifecycle : corbeille/import, attestation : crypto, batch : opérations groupées)
- **Approuvé** = l'outil passe par `est_sensible` et requiert l'approbation humaine (apps/backend/app/services/agent.py:868)
- **Effet DB** = tables écrites

#### Création (4 outils)

| # | Outil | Ligne | Effet DB | Pièges |
|---|---|---|---|---|
| 1 | `create_card` | :176 | `biblio_card` INSERT | `card_kind='sujet'` interdit `content_url`/`content_authors`/`platform`/`content_type`. Slug vérifié unicité (pas de contrainte en base) |
| 2 | `add_source` | :244 | `source` INSERT | DOI seul → déduit `https://doi.org/...` pour l'URL. Déjà citée (clé identité) → refuse. Archives manuelles : `archive_status="archived"`, sinon `"pending"` |
| 3 | `add_excerpt` | :424 | `source_excerpt` INSERT | `text` est le passage à retrouver (pas le contenu) : le serveur relit la page. Garde-fou anti hors-contexte : extrait court commençant par pronom/démonstratif sans `contexte` → refuse. Limité à 12 extraits/source |
| 4 | `set_content_text` | :517 | `biblio_card.content_text` UPDATE | `confirm_publication_rights=true` obligatoire. Fiche `sujet` → refuse. Borne 500k chars |

#### Publication (1 outil, approuvé)

| # | Outil | Ligne | Effet DB | Approuvé |
|---|---|---|---|---|
| 5 | `publish_card` | :565 | `biblio_card.status` → `published` | **oui** — refuse si fiche `contenu` sans `content_url` |

#### Mutation (8 outils)

| # | Outil | Ligne | Notes |
|---|---|---|---|
| 6 | `update_card` | :609 | `card_kind='sujet'` efface URL/authors/platform/type. Refuse si `content_text` non vide. Slug immuable |
| 7 | `update_source` | :709 | URL immuable (`delete_source` + `add_source` pour changer). `archive_url` vide → reset `pending` |
| 8 | `delete_source` | :785 | **Approuvé** — soft-delete, ligne conservée pour citations/attestations |
| 9 | `delete_excerpt` | :802 | **Approuvé** — suppression PHYSIQUE irréversible. `excerpt_id` = UUID, pas position |
| 10 | `update_excerpt` | :834 | Modifier `text` repasse par la relecture de la page |
| 11 | `verify_excerpts` | :895 | Relit chaque extrait vs la page. Verdicts : `found`, `moved`, `missing`, `unreadable`. `provided_text` pour pages anti-bot (NASA ADS, Semantic Scholar) |
| 12 | `confirm_connection` | :1056 | Fige un `linked_card_id` suggéré par le serveur |
| 13 | `remove_connection` | :1087 | Retire le lien fiche→fiche, conserve la source |

#### Listing (5 outils)

| # | Outil | Ligne | Portée |
|---|---|---|---|
| 14 | `list_my_cards` | :1182 | Fiches de l'utilisateur, max 200, `total` + `truncated` |
| 15 | `get_my_card` | :1122 | Fiche complète brouillon compris, `content_text` tronqué à 20k |
| 16 | `list_sources` | :1220 | Sources d'une fiche dans l'ordre d'affichage |
| 17 | `search_my_excerpts` | :1254 | Full-text dans les extraits de l'utilisateur |
| 18 | `list_deleted_cards` | :1677 | Corbeille, max 200 |

#### Cycle de vie & import (7 outils)

| # | Outil | Ligne | Notes |
|---|---|---|---|
| 19 | `delete_card` | :1294 | Soft-delete + sources. Reversible via `restore_card` (90j retention) |
| 20 | `restore_card` | :1309 | Sort de la corbeille |
| 21 | `archive_sources` | :1324 | Passe `archive_status=pending` pour le worker Wayback |
| 22 | `suggest_excerpts` | :1344 | LLM propose des extraits verbatim, déjà vérifiés contre le texte |
| 23 | `annotate_excerpt` | :1418 | LLM suggère titre + contexte pour un extrait donné |
| 24 | `chunk_text` | :1447 | Découpe un texte long en chunks candidats |
| 25 | `import_from_content_url` | :1515 | Extrait les sources depuis `content_url` (bouton UI) |

#### Outils réseau (2 outils)

| # | Outil | Ligne | Notes |
|---|---|---|---|
| 26 | `get_youtube_transcript` | :1475 | Transcript YouTube via API interne |
| 27 | `get_url_metadata` | :1488 | Meta (titre, description, auteurs, date). Garde SSRF (`assert_url_is_safe` dans un thread) |

#### Attestations & citations (5 outils)

| # | Outil | Ligne | Approuvé |
|---|---|---|---|
| 28 | `create_content_attestation` | :1564 | **oui** — signature Ed25519 du `content_url`. Refuse si pas de `content_url` |
| 29 | `get_attestation` | :1590 | non |
| 30 | `verify_attestation` | :1611 | non — rend `valid` + raison |
| 31 | `list_incoming_citations` | :1635 | non — `is_new` pour les nouvelles depuis dernière consultation |
| 32 | `mark_citations_seen` | :1667 | non |

#### Batch & parsers (3 outils)

| # | Outil | Ligne | Notes |
|---|---|---|---|
| 33 | `add_sources_batch` | :1699 | N sources en un appel. Chaque échec → `failed` avec raison, le lot continue |
| 34 | `create_claim_request` | :1806 | Revendique une fiche seed (demande manuelle, admin transfère) |
| 35 | `parse_biblio` | :1841 | Parse BibTeX/CSL/markdown/texte libre. Enrichit avec parseur citations nues + LLM |

### Outils passant par `est_sensible` (approuvables)

`publish_card`, `delete_source`, `delete_excerpt`, `create_content_attestation`, `archive_sources`, `delete_card` — ces outils émettent `approval_request` avant exécution (cf. lot 2.1, `_executer_tour`).
