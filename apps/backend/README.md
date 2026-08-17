# `apps/backend` — API et serveur MCP Philum

FastAPI async + SQLAlchemy 2 + Alembic. Sert l'API REST publique et le serveur MCP (Model Context Protocol) sur le même processus.

## Ce que ça fait, en une phrase

Persiste les créateurs, les fiches, les sources, les extraits et les attestations cryptographiques ; expose l'API REST (`/api/v1/`) que consomme le frontend ; expose un serveur MCP (`/mcp/`) que consomment les agents IA en lecture et en écriture.

## Comment le lancer en local

```bash
cd apps/backend
uv sync --all-extras
cp ../../.env.example .env          # remplir en lowercase, cf. ADR-010
uv run alembic upgrade head
uv run uvicorn app.main:app --reload # écoute sur http://localhost:8000
```

Tests, lint, typecheck :

```bash
CI=true uv run pytest tests/unit -q
CI=true uv run pytest tests/integration -q
uv run ruff format app tests
uv run ruff check app
uv run mypy app
```

Sur Windows, préfixer par `CI=true` pour que les tests d'intégration passent (cf. mémoire projet locale).

**Couverture de code** (opt-in, non activée par défaut pour ne pas ralentir la boucle locale) :

```bash
CI=true uv run pytest tests/ --cov=app --cov-report=term-missing
CI=true uv run pytest tests/ --cov=app --cov-report=html   # ouvre htmlcov/index.html
```

La CI produit systématiquement le rapport (HTML + XML téléchargeables comme artefact du job `Test Backend`, résumé dans le `GITHUB_STEP_SUMMARY`). Pas de seuil bloquant pour l'instant — la mesure est publiée, on gate quand le chiffre sera stabilisé.

## Où vivent les choses

| Sous-dossier            | Rôle                                                                                                                                                                                                                                                                            |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app/main.py`           | Point d'entrée FastAPI, montage du router API et du MCP                                                                                                                                                                                                                         |
| `app/core/`             | `config.py` (pydantic-settings, `case_sensitive=True`)                                                                                                                                                                                                                          |
| `app/db/`               | `database.py` (session async), `text_search.py` (contient, unaccent-safe)                                                                                                                                                                                                       |
| `app/models/`           | Modèles SQLAlchemy (`User`, `BiblioCard`, `Source`, `SourceExcerpt`, `ContentAttestation`, `AuditEvent`, `FeedEvent`, `ClaimRequest`, `LinkedAccount`, `ExcerptEmbedding`)                                                                                                      |
| `app/schemas/`          | Schémas Pydantic (contrats API)                                                                                                                                                                                                                                                 |
| `app/api/v1/endpoints/` | Routers REST : `auth`, `cards`, `sources`, `excerpts`, `users`, `imports`, `discover`, `feed`, `claim`, `linked_accounts`, `attestation`                                                                                                                                        |
| `app/services/`         | Logique métier : `auth`, `card`, `card_graph`, `card_link`, `card_search`, `content_identity`, `citations`, `citation_styles`, `csl`, `export`, `import_parsers`, `wayback`, `embeddings`, `excerpt_indexing`, `llm`, `og_image`, `source_enrichment`, `chunker`, `attestation` |
| `app/crypto/`           | Hash SHA-256, signature Ed25519, keygen, chiffrement AES-GCM                                                                                                                                                                                                                    |
| `app/extractors/`       | Oracles d'extraction : `wikipedia_oracle`, `pmc_oracle`, `grobid`, `section_detector`, `body_links`, `ref_dedup`, `ref_scorer`, `open_access`, `retraction`, `semantic_scholar` (cf. `.docs/17-llm-strategy.md`)                                                                |
| `app/mcp_server/`       | Serveur MCP FastMCP : `server.py` (déclaration des tools), `tools.py` (lecture), `tools_write.py` (écriture), `auth.py` (identification par JWT)                                                                                                                                |
| `app/scripts/`          | Seed de démo, backfills ponctuels                                                                                                                                                                                                                                               |
| `alembic/versions/`     | Migrations de schéma (numérotation `NNN_desc` ≤ 32 caractères, cf. `agent/PITFALLS.md` §1.1)                                                                                                                                                                                    |
| `tests/unit/`           | Tests unitaires (SQLite)                                                                                                                                                                                                                                                        |
| `tests/integration/`    | Tests d'intégration (SQLite via `CI=true`)                                                                                                                                                                                                                                      |

## Contrat API et MCP

- REST : `/api/v1/docs` (Swagger) en local et en prod (`https://philum-api.duckdns.org/api/v1/docs`)
- MCP : `POST /mcp/` (Streamable HTTP), init + `notifications/initialized` + `tools/call`. Auth par `Authorization: Bearer <JWT>` obtenu via `POST /api/v1/auth/mcp-token`.

## Déploiement

Docker Compose sur VM GCP e2-micro, Postgres via Supabase, TLS via Caddy DuckDNS. Cf. `infra/oracle/` et ADR-028.

## Références

- Règles techniques stables : [`../../agent/references/CODING_GUIDE.md`](../../agent/references/CODING_GUIDE.md)
- Pièges déjà payés : [`../../agent/PITFALLS.md`](../../agent/PITFALLS.md)
- Skills spécialisés : [`../../agent/skills/`](../../agent/skills/) (Alembic, backend-FastAPI, OAuth Google, rate-limiting, observabilité, CI/CD)
