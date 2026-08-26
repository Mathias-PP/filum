# Serveur FastMCP et enregistrement des outils (`server.py`)

## apps/backend/app/mcp_server/server.py
Lu intégralement : oui (758/758 lignes) · sha256: a43760bc4d8e · date: 2026-08-25

Point d'entrée du serveur MCP Philum : instance `mcp` de type `FastMCP("philum")` (`apps/backend/app/mcp_server/server.py:15`). Le `instructions` (`apps/backend/app/mcp_server/server.py:16`) guide l'agent : navigate comme un graphe, l'écriture exige un compte, `whoami` pour vérifier le token.

**Application HTTP** : `mcp_http_app = mcp.http_app(path="/")` (`apps/backend/app/mcp_server/server.py:758`) — le sous-serveur FastMCP monté sur `/mcp`.

### Le décorateur `outil()` — `apps/backend/app/mcp_server/server.py:30`

Enregistre une fonction comme outil MCP via `mcp.tool()(fn)`, puis aplatie le schéma des paramètres via `aplatir_nullable` (lot 3.3) sur le composant interne `mcp._local_provider._components["tool:<nom>@"]`. Ceci contourne le fait que fastmcp produit des `anyOf` pour tout `X | None = None` — injoinable par le validateur Gemini (`apps/backend/app/mcp_server/server.py:32-37`). Les `output_schema` ne sont PAS touchés : un outil rendant légitimement `None` échouerait s'ils étaient aplatis.

### Session DB
`_session()` (`apps/backend/app/mcp_server/server.py:54`) : fabrique une `AsyncSession` via `async_session_maker()`. Chaque outil l'utilise en context manager (`async with _session() as db`).

### Catalogue des 45 outils enregistrés

**Lecture seule** (5 outils, `apps/backend/app/mcp_server/tools.py`) :

| # | Outil | Ligne | Description |
|---|---|---|---|
| 1 | `search_cards` | :58 | Recherche full-text fiches publiques (titre, description, sources) |
| 2 | `get_card` | :72 | Détail compact d'une fiche + sources (sans extraits) |
| 3 | `get_source` | :84 | Source avec tous ses extraits verbatim |
| 4 | `find_cards_citing` | :95 | Fiches citant une URL/DOI (arêtes du graphe) |
| 5 | `whoami` | :108 | Identité du porteur du token |

**Écriture — Création & mutation** (outils P1) :

| # | Outil | Ligne | Approuvable |
|---|---|---|---|
| 6 | `create_card` | :122 | non |
| 7 | `add_source` | :166 | non |
| 8 | `add_excerpt` | :226 | non |
| 9 | `set_content_text` | :257 | non |
| 10 | `publish_card` | :286 | **oui** (publication) |
| 11 | `update_card` | :305 | non |
| 12 | `update_source` | :343 | non |
| 13 | `delete_source` | :387 | **oui** (suppression) |
| 14 | `delete_excerpt` | :397 | **oui** (suppression irréversible) |
| 15 | `update_excerpt` | :407 | non |
| 16 | `verify_excerpts` | :434 | non |
| 17 | `list_connections` | :457 | non |
| 18 | `confirm_connection` | :469 | non |
| 19 | `remove_connection` | :485 | non |

**Écriture — Import, aide LLM, listing, archivage, cycle de vie** (P2) :

| # | Outil | Ligne |
|---|---|---|
| 20 | `list_my_cards` | :502 |
| 21 | `get_my_card` | :510 |
| 22 | `list_sources` | :518 |
| 23 | `search_my_excerpts` | :526 |
| 24 | `delete_card` | :534 |
| 25 | `restore_card` | :542 |
| 26 | `archive_sources` | :550 |
| 27 | `suggest_excerpts` | :558 |
| 28 | `annotate_excerpt` | :581 |
| 29 | `chunk_text` | :597 |
| 30 | `get_youtube_transcript` | :605 |
| 31 | `get_url_metadata` | :613 |
| 32 | `import_from_content_url` | :621 |

**Écriture — Attestations, citations, batch, claim, parsers** (P3) :

| # | Outil | Ligne | Approuvable |
|---|---|---|---|
| 33 | `create_content_attestation` | :639 | **oui** (signature cryptographique) |
| 34 | `get_attestation` | :652 | non |
| 35 | `verify_attestation` | :660 | non |
| 36 | `list_incoming_citations` | :668 | non |
| 37 | `mark_citations_seen` | :676 | non |
| 38 | `list_deleted_cards` | :684 | non |
| 39 | `add_sources_batch` | :692 | non |
| 40 | `create_claim_request` | :704 | non |
| 41 | `parse_biblio` | :715 | non |

**Graphe mémoire (STARTER, non exposé par défaut)** :

| # | Outil | Ligne | Note |
|---|---|---|---|
| 42 | `recall_memory` | :727 | Import retardé `graph_memory.recall`, 3 tables, 1 requête récursive |
| 43 | `rebuild_graph` | :744 | Import retardé `graph_memory.build_graph`, rebuild déterministe |

**Total** : 43 + 2 outils = **45** (voir dérive invariant dans CONTEXT.md).
