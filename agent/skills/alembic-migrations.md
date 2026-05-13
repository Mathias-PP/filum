# Skill: Alembic migrations

> Quand l'utiliser : tout changement de schéma BDD (nouvelle table, colonne, index, contrainte).

## Contexte

Les migrations Alembic ont déjà coûté plusieurs crash-loops Railway au projet. Le système est sensible : une migration qui throw → DDL rollback → version_num pas avancée → boot suivant retry → boucle. Ce skill capture les règles dures.

## Checklist d'exécution

1. **Vérifier l'état actuel** : `cd apps/backend && uv run alembic current` (doit retourner la dernière révision sur main).
2. **Créer la révision** : `uv run alembic revision --autogenerate -m "ajoute <truc>"`. Vérifier immédiatement le fichier généré (autogenerate peut inventer des choses).
3. **Vérifier le nommage** : le fichier `apps/backend/alembic/versions/<id>_*.py` doit avoir un `revision = "00X_<courte>"` avec **`len(id) ≤ 32`**. Si autogenerate a généré un hash, **renommer manuellement** la variable `revision` (et le filename) en `00X_<sujet-court>`. Convention : incrémenter le numéro depuis la dernière migration.
4. **Vérifier le `down_revision`** : doit pointer vers la migration précédente correcte.
5. **Pas de double index** : si `Column(..., ForeignKey(...), index=True)` dans `create_table()`, **ne pas** ajouter un `op.create_index('ix_<table>_<col>', ...)` ensuite. L'index est déjà créé par `index=True`.
6. **Écrire le `downgrade`** : symétrique. Tester `alembic downgrade -1` en local.
7. **Test local** :
   ```bash
   cd apps/backend
   uv run alembic upgrade head
   uv run alembic downgrade -1
   uv run alembic upgrade head
   ```
   Doit passer 3 fois sans erreur.
8. **Si la migration ajoute un champ à `sources` ou `biblio_cards`** : vérifier qu'il **n'entre pas** dans le `canonical_hash` payload (cf. `apps/backend/app/services/card.py` lignes 96-105 et 161-169, et `apps/backend/app/scripts/seed_demo.py`). Si vraiment nécessaire → ADR explicite + plan de re-signature.
9. **Commit** : `feat(db): migration 00X — <description>`.
10. **PR** : décrire le changement de schéma, la migration up/down, les implications sur les fiches signées.

## Pièges spécifiques

- **Revision id > 32 char** → `StringDataRightTruncationError` → rollback → crash-loop. Cf. `PITFALLS.md` 1.1.
- **Double `create_index`** → `DuplicateTableError` → rollback. Cf. `PITFALLS.md` 1.2.
- **Champ dans `canonical_hash`** → signatures des fiches passées invalidées. Cf. `PITFALLS.md` 1.3.
- **`datetime.utcnow()`** → utiliser `datetime.now(UTC).replace(tzinfo=None)`. Cf. `PITFALLS.md` 1.5.
- **`down_revision` faux** → la migration ne sera pas exécutée. Toujours vérifier.

## Fichiers à connaître

- `apps/backend/alembic.ini` — config
- `apps/backend/alembic/env.py` — branchement engine async
- `apps/backend/alembic/versions/` — migrations existantes (lire les dernières comme exemples)
- `apps/backend/app/models/` — modèles SQLAlchemy de référence
- `apps/backend/app/services/card.py` — canonical_hash payload (NE PAS modifier sans ADR)

## Pour aller plus loin

- ADR-010 (env vars lowercase)
- ADR-012 (SQLite + aiosqlite pour les tests)
- ADR-016 (`Source.parent_source_id` exemple complet)
- ADR-017 (itération 2 — exemple de migration non destructive)
