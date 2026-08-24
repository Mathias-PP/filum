---
contract: "Contrat de l'etape 02 : collecter et enrichir les sources de la fiche."
layer: L2
---

# 02-sources-collectees

## Scope

Collecter, enrichir et poser les sources de la fiche, sans les annoter (annotation = étape 03).

## Inputs

| Source                 | File                                  | Section                                        | Why                                   |
| ---------------------- | ------------------------------------- | ---------------------------------------------- | ------------------------------------- |
| Brief propre           | `../01-brief/output/<slug>-brief.md`  | Full file                                      | Thèse, sources connues, `content_url` |
| Preuve d'existence     | `../01-brief/output/<slug>-card.json` | Champ `slug`                                   | Cible des `add_source`                |
| Squelette d'une source | `../../_core/templates/source.md`     | Full file                                      | Structure                             |
| Signature `add_source` | `../../shared/philum-mcp.md`          | Ligne `add_source` de la table Écriture        | Champs autorisés                      |
| Garde-fous             | `../../shared/garde-fous.md`          | « Sur les auteurs » et « Sur les métadonnées » | Pas d'invention                       |

## Process

1. **Collecte brute** : lister les sources à documenter avec URL et intitulé provisoire. Trois voies :
   - Extraction auto via `mcp__philum__import_from_content_url(card_slug)` : lit `content_url` et rend les références candidates scorées. Ne pose rien.
   - Sources déjà nommées dans le brief : y ajouter à la main.
   - Bibliographie collée : `mcp__philum__parse_biblio(text)` pour la parser en refs structurées.
2. **Enrichissement** : compléter les métadonnées manquantes. `mcp__philum__get_url_metadata(url)` pour titre/description/auteurs. Crossref pour DOI et référence complète.
3. **Filtrage éditorial** : retirer les sources sans rapport avec la thèse ou en doublon. Consigner dans `<slug>-rejetees.md` pourquoi.
4. **Pose côté prod** : pour un lot de 5+ sources, `mcp__philum__add_sources_batch(card_slug, sources)` en un appel (dedup automatique). Sinon `mcp__philum__add_source` un à un. NE PAS poser `stance` ni `annotation` maintenant.
5. **Pivots** : marquer en `is_pivot=True` autant de sources que la thèse en compte réellement, sans plafond arbitraire. Via `mcp__philum__update_source(source_id, is_pivot=True)`. Chaque pan distinct de la thèse mérite son pivot si un papier différent le porte. Voir `shared/principes-editoriaux.md`.
6. **Graphe déjà là** : pour chaque source, `mcp__philum__find_cards_citing(url)` et noter dans `<slug>-sources.md` pour l'étape 05.
7. **Vérification** : `mcp__philum__list_sources(card_slug)` pour lire l'état côté serveur et récupérer les UUID à réutiliser.

## Outputs

| Artifact              | Location                    | Format                                               |
| --------------------- | --------------------------- | ---------------------------------------------------- |
| Catalogue des sources | `output/<slug>-sources.md`  | Markdown (une entrée par source, format template)    |
| Mapping index -> UUID | `output/<slug>-ids.json`    | JSON `{ "1": "<uuid>", "2": "<uuid>", ... }`         |
| Sources écartées      | `output/<slug>-rejetees.md` | Markdown (une entrée par source retirée avec raison) |

## Checkpoints

| After Step | Agent Presents                                              | Human Decides                                                                                          |
| ---------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 2          | Liste enrichie complète, mise en évidence des DOI manquants | Compléter à la main les DOI que l'agent n'a pas trouvés                                                |
| 3          | `<slug>-rejetees.md` : sources écartées avec raison         | Confirmer les rejets ou réintégrer                                                                     |
| 5          | Liste des sources marquées `is_pivot=True`                  | Ajuster : celles qui portent réellement la thèse, autant qu'il en faut pour couvrir ses pans distincts |

## Audit

| Check                           | Pass Condition                                                                                  |
| ------------------------------- | ----------------------------------------------------------------------------------------------- |
| Métadonnées non inventées       | Chaque DOI présent est vérifié dans Crossref ; chaque date vient de la source                   |
| Auteurs institutionnels intacts | Une institution (« American Nuclear Society ») figure telle quelle, pas décomposée en initiales |
| Au moins un pivot               | pivots ≥ 1 (une fiche sans aucun pivot n'assume pas ce qu'elle affirme)                         |
| Cohérence UUID                  | Chaque source retenue a une entrée dans `<slug>-ids.json`                                       |
