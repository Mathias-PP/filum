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

## Ce qu'il faut savoir avant d'appeler chaque écriture

- **Pas d'invention** : chaque champ passé est soit vérifié (DOI depuis Crossref/OpenAlex, dates depuis la source elle-même) soit laissé vide. Vide se lit « je ne sais pas » ; une valeur inventée se lit « je sais et j'affirme ».
- **`stance`** : `appuie`, `nuance-contredit`, `mentionne`, `contexte`. Absent = position non déclarée. Silence, pas neutralité.
- **`is_pivot`** : réservé aux sources qui portent la thèse centrale. Trois pivots maximum par fiche.
- **Ordre d'appel** : `create_card` → `add_source` × N → `add_excerpt` × M par source clé → `set_content_text` (optionnel) → connexions (étape 05) → `publish_card`.

## Ce que les tools MCP NE FONT PAS et qu'il faut faire à côté

- **Extraction depuis une URL de contenu** : passe par l'endpoint REST `POST /api/v1/cards/{id}/sources/extract` (ou l'UI). Pas de tool MCP dédié.
- **Suggestion d'extraits par le LLM** : endpoint REST `POST /api/v1/sources/{id}/excerpts/suggest`. Le tool MCP `add_excerpt` pose un extrait déjà décidé, il ne suggère pas.
- **Confirmation des connexions** : endpoint REST `POST /api/v1/cards/{card_id}/connections/{source_id}/confirm` (ou l'UI `/dashboard/new/{card_id}/connexions`).

## Erreurs typiques

- `ToolError("Identifiant de source invalide")` : `source_id` n'est pas un UUID. Reprendre la sortie de `add_source` pour le bon.
- `ToolError("Extrait trop court et referentiel...")` : garde-fou serveur. Élargir l'extrait ou fournir `context`.
- `ToolError("Aucune fiche <slug> chez <username>")` : slug faux ou token identifie un autre utilisateur. `whoami` d'abord.
