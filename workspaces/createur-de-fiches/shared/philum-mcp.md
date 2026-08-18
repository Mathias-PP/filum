# Outils MCP Philum : inventaire et quand les utiliser

Tous les outils sont préfixés `mcp__philum__`. Un token est obtenu via `POST /api/v1/auth/mcp-token` depuis un navigateur connecté, puis passé en `Authorization: Bearer`.

## Lecture (pas de compte requis)

| Outil | Étape | Quand |
|---|---|---|
| `search_cards(query, limit)` | 05 | Trouver les fiches Philum qui parlent d'un sujet proche. |
| `get_card(creator, slug)` | 05 | Ouvrir une fiche voisine pour vérifier qu'elle est bien celle qu'on veut citer. |
| `get_source(source_id)` | 04, 06 | Vérifier les extraits verbatim d'une source déjà indexée. |
| `find_cards_citing(url, limit)` | 02, 05 | Voir qui d'autre cite une URL avant de la citer soi-même. Indispensable pour ne pas doublonner une fiche existante et pour construire les connexions. |

## Écriture (compte + token requis)

| Outil | Étape | Signature stricte |
|---|---|---|
| `whoami()` | 01 | Vérifier avant tout que le token identifie bien l'utilisateur du brief. Refuser si ambigu. |
| `create_card(slug, title, content_url?, description?, content_authors?, platform?, content_type?, visibility?)` | 01 | Crée un brouillon. `visibility="public"` par défaut. |
| `add_source(card_slug, url?, title?, authors?, doi?, category?, author_kind?, format?, stance?, annotation?, journal?, archive_url?)` | 02 puis 03 | Deux passes : une pour poser la source, une pour l'annoter et poser sa position (`stance`). |
| `add_excerpt(source_id, text, title?, context?)` | 04 | Un extrait par appel. `context` obligatoire dès que `text` contient un pronom référentiel ou fait moins de 15 mots (garde-fou serveur, refuse sinon). |
| `set_content_text(card_slug, text, confirm_publication_rights)` | 01 ou 07 | Ne l'appeler QUE si le brief a coché `oui` explicite. Passer `confirm_publication_rights=True` engage la responsabilité du compte. |
| `publish_card(slug)` | 07 | Rend la fiche publique. Ne bascule au public qu'une fois : republier n'est jamais un événement de feed. |
| `update_card(slug, title?, description?, content_url?, content_authors?, platform?, content_type?, visibility?)` | 01, 06 | Corrige les champs éditoriaux après création. Slug immuable (identifiant public). |
| `update_source(source_id, title?, authors?, doi?, journal?, category?, author_kind?, format?, stance?, annotation?, is_pivot?, archive_url?)` | 03, 06 | Corrige une source après création. URL immuable : pour la changer, `delete_source` puis `add_source`. |
| `delete_source(source_id)` | 06 | Soft-delete d'une source. La ligne reste en base pour préserver les références historiques. |
| `delete_excerpt(source_id, excerpt_id)` | 06 | Supprime physiquement un extrait. |
| `verify_excerpts(source_id, provided_text?)` | 04, 06 | Relit chaque extrait vs le texte de la page et pose `verified_status` (`found`/`moved`/`missing`/`unreadable`). `provided_text` obligatoire quand la page est bloquée anti-bot. |
| `list_connections(card_slug)` | 05 | Rend `outgoing` (fiches que celle-ci cite) et `incoming` (fiches qui la citent). |
| `confirm_connection(card_slug, source_id)` | 05 | Confirme qu'une source pointe bien vers la fiche Philum désignée. |
| `remove_connection(card_slug, source_id)` | 05 | Retire le lien fiche à fiche sans supprimer la source. |
| `list_my_cards(status?, limit)` | tout | Liste les fiches du créateur (`draft`, `published` ou les deux). |
| `list_sources(card_slug)` | 02, 06 | Liste les sources d'une fiche avec leurs ID (à réutiliser dans les tools de mutation). |
| `search_my_excerpts(query, limit)` | ponctuel | Cherche full-text dans les extraits du créateur. |
| `delete_card(slug)` | ponctuel | Soft-delete d'une fiche (rejoint la corbeille). |
| `restore_card(slug)` | ponctuel | Sort une fiche de la corbeille. |
| `archive_sources(source_ids)` | 02 | Déclenche l'archivage Wayback pour les sources listées. |
| `suggest_excerpts(source_id, provided_text?, include_annotation, include_existing, include_card_context)` | 04 | Le LLM propose des extraits verbatim (déjà vérifiés anti-hallucination). |
| `annotate_excerpt(source_id, excerpt_text, provided_text?)` | 04 | Le LLM suggère titre et `context` pour un extrait donné. |
| `chunk_text(source_id, text, size?)` | 04 | Découpe un texte long en chunks candidats. |
| `get_youtube_transcript(url)` | 02 | Récupère le transcript d'une vidéo YouTube. |
| `get_url_metadata(url)` | 02 | Titre, description, auteurs, date d'une URL. |
| `import_from_content_url(card_slug)` | 02 | Extrait auto des sources depuis `card.content_url` (équivalent bouton « Extraire les sources »). Ne pose pas, rend les candidates. |

## Ce qu'il faut savoir avant d'appeler chaque écriture

- **Pas d'invention** : chaque champ passé est soit vérifié (DOI depuis Crossref/OpenAlex, dates depuis la source elle-même) soit laissé vide. Vide se lit « je ne sais pas » ; une valeur inventée se lit « je sais et j'affirme ».
- **`stance`** : `appuie`, `nuance-contredit`, `mentionne`, `contexte`. Absent = position non déclarée. Silence, pas neutralité.
- **`is_pivot`** : réservé aux sources qui portent la thèse. Pas de plafond fixe : autant de pivots que la thèse compte de pans distincts (voir `principes-editoriaux.md`).
- **Ordre d'appel** : `create_card` → `add_source` × N → `add_excerpt` × M par source clé → `set_content_text` (optionnel) → connexions (étape 05) → `publish_card`.

## Ce que les tools MCP NE FONT PAS et qu'il faut faire à côté

Les fonctions ci-dessous existent dans l'UI et dans l'API REST mais n'ont pas encore de wrapper MCP (chantiers B/C/D en cours, voir `agent/plans/2026-08-18-parite-mcp-et-hardening-workspace.md`). En attendant, les appeler en REST avec le même token JWT (`Authorization: Bearer <token>`) sur `https://philum-api.duckdns.org/api/v1`.

**Reste à couvrir (chantier D)** :
- `POST /attestations/content`, `GET /attestations/{id}/verify` : attestations Ed25519 (signature cryptographique).
- `GET /cards/citations`, `POST /cards/citations/seen` : citations entrantes.
- `POST /sources/batch` : poser plusieurs sources en un appel.
- `POST /cards/{id}/claim-requests` : revendiquer une fiche seed.
- `POST /cards/{id}/content-text/upload` : upload de fichier binaire pour `content_text`.
- `POST /import/parse` (BibTeX/CSL/RIS), `POST /import/paste` : parsers de bibliographie.

## Gotchas mesurés

Autant de pièges déjà payés qu'il faut connaître avant d'agir. Détail dans `pieges-vecus.md`.

- **URL immuable après `add_source`.** Un `PATCH /sources/{id}` avec `url` est refusé. Pour corriger une URL fautive : `DELETE` puis nouveau `add_source`.
- **`add_source` dé-duplique par URL/DOI.** Un second appel avec le même URL/DOI (par exemple pour poser l'annotation après le premier passage) met à jour la source existante au lieu d'en créer une deuxième. Comportement volontaire, utilisé par le pipeline (étape 03 pose l'annotation via ce chemin).
- **Position des sources = ordre d'insertion.** Pas d'endpoint de reorder. Une fiche mal ordonnée nécessiterait un DELETE+POST de toutes les sources ; en pratique, l'ordre visible est peu critique (les pivots portent une étoile).
- **`text` d'extrait plafonné à 1 000 caractères** (`add_excerpt`). Un abstract scientifique long doit être coupé au niveau d'une phrase (jamais en milieu) et posé en plusieurs extraits.
- **`DELETE` retourne 204 sans corps JSON.** Un client qui essaie de parser la réponse comme JSON échoue. Traiter le status code, pas le body.
- **Fetch de source bloqué par un anti-bot** (ScienceDirect, IOP, PubMed) : le `verify` REST accepte un payload `{text: "..."}` que l'agent atteste être le texte de la source. Cas où l'agent a lu la source ailleurs (NASA ADS, Semantic Scholar, Crossref abstract) et veut valider malgré le 403 sur l'URL canonique.
- **URL et DOI ne correspondent pas toujours.** Un fetch d'origine peut poser une URL IOP qui pointe vers un autre article que celui du DOI. Toujours vérifier avant `add_source` que l'URL contient bien le DOI ou pointe vers le bon article.

## Erreurs typiques renvoyées par le serveur

- `ToolError("Identifiant de source invalide")` : `source_id` n'est pas un UUID. Reprendre la sortie de `add_source` pour le bon.
- `ToolError("Extrait trop court et referentiel...")` : garde-fou serveur. Élargir l'extrait ou fournir `context`.
- `ToolError("Aucune fiche <slug> chez <username>")` : slug faux ou token identifie un autre utilisateur. `whoami` d'abord.
