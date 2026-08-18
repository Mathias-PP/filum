# Outils MCP Philum : inventaire et quand les utiliser

Tous les outils sont préfixés `mcp__philum__`. Un token est obtenu via `POST /api/v1/auth/mcp-token` depuis un navigateur connecté, puis passé en `Authorization: Bearer`.

## Lecture (pas de compte requis)

| Outil | À l'étape | Quand |
|---|---|---|
| `search_cards(query, limit)` | 05 | Trouver les fiches Philum qui parlent d'un sujet proche. |
| `get_card(creator, slug)` | 05 | Ouvrir une fiche voisine pour vérifier qu'elle est bien celle qu'on veut citer. |
| `get_source(source_id)` | 04, 06 | Vérifier les extraits verbatim d'une source déjà indexée. |
| `find_cards_citing(url, limit)` | 02, 05 | Voir qui d'autre cite une URL avant de la citer soi-même. Indispensable pour ne pas doublonner une fiche existante et pour construire les connexions. |

## Écriture (compte + token requis)

| Outil | À l'étape | Ordre de la seule signature autorisée |
|---|---|---|
| `whoami()` | 01 | Vérifier avant tout que le token identifie bien l'utilisateur du brief. Refuser si ambigu. |
| `create_card(slug, title, content_url?, description?, content_authors?, platform?, content_type?, visibility?)` | 01 | Crée un brouillon. Signature stricte : `visibility="public"` par défaut. |
| `add_source(card_slug, url?, title?, authors?, doi?, category?, author_kind?, format?, stance?, annotation?, journal?, archive_url?)` | 02 puis 03 | Deux passes : une pour poser la source, une pour l'annoter et poser sa position (`stance`). |
| `add_excerpt(source_id, text, title?, context?)` | 04 | Un extrait par appel. `context` obligatoire dès que `text` contient un pronom référentiel ou fait moins de 15 mots (garde-fou serveur, refuse sinon). |
| `set_content_text(card_slug, text, confirm_publication_rights)` | 01 ou 07 | Ne l'appeler QUE si le brief a coché `oui` explicite. Passer `confirm_publication_rights=True` engage la responsabilité du compte. |
| `publish_card(slug)` | 07 | Rend la fiche publique. Ne bascule au public qu'une fois : republier n'est jamais un événement de feed. |

## Ce qu'il faut savoir avant d'appeler chaque écriture

- **Pas d'invention** : chaque champ passé est soit vérifié (DOI depuis Crossref/OpenAlex, dates depuis la source elle-même) soit laissé vide. Vide se lit « je ne sais pas » ; une valeur inventée se lit « je sais et j'affirme » : le contraire de ce que Philum sert.
- **`stance`** : `appuie`, `nuance-contredit`, `mentionne`, `contexte`. Absent = position non déclarée. C'est une position de silence, pas de neutralité.
- **`is_pivot`** : réservé aux sources qui portent la thèse centrale. Trois pivots maximum par fiche : au-delà, la notion perd son sens.
- **Ordre d'appel** : `create_card` → `add_source` (N fois) → `add_excerpt` (M fois par source clé) → `set_content_text` (optionnel) → étape 05 (connexions manuelles côté UI ou via `find_cards_citing`) → `publish_card`.

## Ce que ces outils ne font pas et qu'il faut donc faire à côté

- **Extraction depuis une URL de contenu** : passe par l'UI (`/dashboard/new/{card_id}/sources`, bouton « Extraire ») ou par l'endpoint REST `POST /api/v1/cards/{id}/sources/extract`. Pas de tool MCP dédié.
- **Suggestion d'extraits par le LLM** : idem, endpoint REST `POST /api/v1/sources/{id}/excerpts/suggest`. Le tool MCP `add_excerpt` pose un extrait déjà décidé, il ne suggère pas.
- **Confirmation des connexions** : passe par l'UI `/dashboard/new/{card_id}/connexions` (l'étape 3 du wizard). Les connexions détectées automatiquement y attendent une confirmation.

## Erreurs typiques et ce qu'elles disent

- `ToolError("Identifiant de source invalide")` : `source_id` n'est pas un UUID. Retourner à la sortie de `add_source` pour récupérer le bon.
- `ToolError("Extrait trop court et referentiel...")` : le garde-fou serveur a refusé. Élargir l'extrait ou fournir `context`.
- `ToolError("Aucune fiche <slug> chez <username>")` : le slug de la fiche est faux, ou le token identifie un autre utilisateur. `whoami` d'abord.
