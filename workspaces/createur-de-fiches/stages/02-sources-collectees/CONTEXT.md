# 02-sources-collectees

## Scope

Collecter, enrichir et poser les sources de la fiche, sans les annoter (annotation = étape 03).

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Brief propre | `../01-brief/output/<slug>-brief.md` | Full file | Thèse, sources connues, `content_url` |
| Preuve d'existence | `../01-brief/output/<slug>-card.json` | Champ `slug` | Cible des `add_source` |
| Squelette d'une source | `../../_core/templates/source.md` | Full file | Structure |
| Signature `add_source` | `../../shared/philum-mcp.md` | Ligne `add_source` de la table Écriture | Champs autorisés |
| Garde-fous | `../../shared/garde-fous.md` | « Sur les auteurs » et « Sur les métadonnées » | Pas d'invention |

## Process

1. **Collecte brute** : lister les sources à documenter avec URL et intitulé provisoire. Deux voies :
   - Extraction depuis `content_url` via `POST /api/v1/cards/{card_id}/sources/extract` (endpoint REST, pas de tool MCP).
   - Sources déjà nommées dans le brief : y ajouter.
2. **Enrichissement** : pour chaque source, chercher les métadonnées manquantes via une source d'autorité (Crossref pour articles scientifiques, la source elle-même pour presse ou web).
3. **Filtrage éditorial** : retirer les sources sans rapport avec la thèse ou en doublon. Consigner dans `<slug>-rejetees.md` pourquoi.
4. **Pose côté prod** : pour chaque source retenue, appeler `mcp__philum__add_source` avec la signature stricte. NE PAS poser `stance` ni `annotation` maintenant.
5. **Pivots** : marquer 1 à 3 sources en `is_pivot=True` (celles qui portent la thèse).
6. **Graphe déjà là** : pour chaque source, appeler `mcp__philum__find_cards_citing(url)` et noter les résultats dans `<slug>-sources.md` pour l'étape 05.

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Catalogue des sources | `output/<slug>-sources.md` | Markdown (une entrée par source, format template) |
| Mapping index -> UUID | `output/<slug>-ids.json` | JSON `{ "1": "<uuid>", "2": "<uuid>", ... }` |
| Sources écartées | `output/<slug>-rejetees.md` | Markdown (une entrée par source retirée avec raison) |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Liste enrichie complète, mise en évidence des DOI manquants | Compléter à la main les DOI que l'agent n'a pas trouvés |
| 3 | `<slug>-rejetees.md` : sources écartées avec raison | Confirmer les rejets ou réintégrer |
| 5 | Liste des sources marquées `is_pivot=True` | Ajuster : au plus 3, celles qui portent la thèse |

## Audit

| Check | Pass Condition |
|---|---|
| Métadonnées non inventées | Chaque DOI présent est vérifié dans Crossref ; chaque date vient de la source |
| Auteurs institutionnels intacts | Une institution (« American Nuclear Society ») figure telle quelle, pas décomposée en initiales |
| Nombre de pivots | 1 ≤ pivots ≤ 3 |
| Cohérence UUID | Chaque source retenue a une entrée dans `<slug>-ids.json` |
