# `apps/analytics` — dbt sur DuckDB

Projet dbt qui transforme les données d'usage Philum en modèles analytiques. **Statut : inerte en runtime prod**. Compilé par la CI pour valider les SQL, exécuté à la main quand une question analytique se pose.

## Ce que ça fait, en une phrase

Prend les tables transactionnelles Postgres (via un dump ponctuel ou une réplique DuckDB) et les transforme en modèles `staging/`, `marts/`, `analytics/` pour répondre à des questions d'usage sans requêter la prod.

## Comment le lancer en local

```bash
cd apps/analytics
pip install -r requirements.txt
dbt deps
dbt compile        # vérifie SQL + refs (ce que fait la CI)
dbt run            # exécute contre le profil `filum_duckdb` (cf. profiles.yml)
dbt test
```

Le fichier `profiles.yml` pointe sur un DuckDB local par défaut.

## Où vivent les choses

| Sous-dossier | Rôle |
|---|---|
| `models/staging/` | Un fichier par table source, renommage/typage, pas de logique métier |
| `models/marts/` | Modèles orientés use-case (créateur, fiche, source, extrait) |
| `models/analytics/` | Rollups (nombre de fiches par créateur, sources par catégorie, etc.) |
| `models/sources.yml` | Déclarations des tables sources et de leurs colonnes |

## CI

Un job `Analytics Check` (voir `.github/workflows/analytics.yml`) exécute `dbt compile` à chaque push pour attraper les régressions de refs et de SQL avant merge.

## Notes

- Aucun modèle n'est exécuté en production automatiquement. Si une question analytique récurrente émerge, elle sera d'abord un modèle ad-hoc ici, puis promue en tableau de bord ou en endpoint API.
- Cf. `.docs/03-data-model.md` pour le schéma transactionnel source.
