# Outils MCP read-only (`tools.py`)

## apps/backend/app/mcp_server/tools.py
Lu intégralement : oui (258/258 lignes) · sha256: 26f3e288a813 · date: 2026-08-25

Fonctions pures (session en paramètre) pour rester testables sans protocole MCP (`apps/backend/app/mcp_server/tools.py:4`). Réponses volontairement compactes : l'IA cliente ne charge que les nœuds qu'elle visite.

### Filtre `_PUBLIC` — `apps/backend/app/mcp_server/tools.py:32`

Filtre persistent appliqué à TOUS les outils read-only :
```
status == "published" & visibility == "public" & deleted_at IS NULL
```
`visibility` tranche (pas `status` : une fiche peut être achevée et signée sans être offerte au monde). Le MCP ne vérifiait pas `visibility` au départ et livrait le titre, la description et la bibliographie complète de fiches privées (bug corrigé).

### Symboles (5)

- `_arete_vers_une_fiche` — `apps/backend/app/mcp_server/tools.py:39` — l'adresse `{creator, slug}` de la fiche Philum qu'une source désigne, si elle est publique et non supprimée. L'unique arête fiche→fiche qui fait du corpus un graphe. Revérifie le statut au moment de la lecture (un lien posé quand la fiche citée était publique peut devenir invalide).
- `search_cards` — `apps/backend/app/mcp_server/tools.py:58` — recherche full-text dans les fiches publiques (titre, description, auteur du contenu, créateur, titre/auteurs des sources). Accent-indifférent via `correspond()`. Limite : 1–25. Rend `[{creator, slug, title}]`.
- `get_card` — `apps/backend/app/mcp_server/tools.py:91` — détail compact d'une fiche publiée et publique + ses sources (sans extraits). `null` si brouillon ou privé. Les sources arrivent avec `linked_card` (arête fiche→fiche).
- `get_source` — `apps/backend/app/mcp_server/tools.py:138` — source publique avec TOUS ses extraits verbatim (texte, contexte, statut de vérification, ancres). Le seul outil qui donne le texte des extraits. `null` si source supprimée ou fiche non publique.
- `find_cards_citing` — `apps/backend/app/mcp_server/tools.py:214` — fiches publiques citant une URL ou un DOI. Les variantes d'écriture (www., http, barre finale, paramètres de campagne) sont repliées via `url_variants`. Les DOI sont aussi cherchés dans les URLs et vice-versa. Le lien `linked_card` résolu permet de rapprocher deux écritures d'URL pour le même travail.
