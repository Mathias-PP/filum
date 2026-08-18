# Étape 2 : Sources collectées

**Reads**
- `runs/<slug>/01_brief/brief.md` (thèse, sources déjà connues, content_url).
- `runs/<slug>/01_brief/card.json` (`card_slug`).
- `_templates/source.md` (structure d'une source).
- `_system/philum-mcp.md` (comment appeler `add_source`, quels champs vérifiés).
- `_system/garde-fous.md` (pas d'invention de DOI/date/auteur).

**Does**
1. **Collecte brute** : lister les sources à documenter, avec URL et intitulé provisoire. Deux voies :
   - **Extraction depuis `content_url`** : appeler `POST /api/v1/cards/{card_id}/sources/extract` (endpoint REST, pas de tool MCP dédié). L'extracteur lit la page et rend les liens sortants avec un score.
   - **Sources déjà nommées dans le brief** : y ajouter.
2. **Enrichissement** : pour chaque source, chercher les métadonnées manquantes via une source d'autorité :
   - Article scientifique : Crossref (`https://api.crossref.org/works/{doi}`) ou OpenAlex.
   - Article de presse, communiqué, page web : lire la source elle-même, ne rien deviner qui n'y figure.
3. **Filtrage éditorial** : retirer les sources sans rapport avec la thèse, ou en doublon. Une source retirée est un geste, pas un oubli : noter dans `sources.md` pourquoi elle a été retirée.
4. **Pose côté prod** : pour chaque source retenue, appeler `mcp__philum__add_source` avec la SIGNATURE STRICTE (voir `_system/philum-mcp.md`). NE PAS poser `stance` ni `annotation` maintenant : c'est l'étape 3.
5. **Pivots** : marquer 1 à 3 sources en `is_pivot=True` (celles qui portent la thèse). Voir `_system/principes-editoriaux.md`.
6. **Graphe déjà là** : pour chaque source, appeler `mcp__philum__find_cards_citing(url)` : si une fiche Philum cite déjà cette URL, en prendre note dans `sources.md` pour l'étape 05.

**Writes**
- `runs/<slug>/02_sources-collectees/sources.md` : une entrée par source, structurée selon `_templates/source.md`, dans l'ordre où elles apparaîtront dans la fiche.
- `runs/<slug>/02_sources-collectees/ids.json` : mapping `{source_index → source_id_uuid}` pour l'étape 4 (extraits).
- `runs/<slug>/02_sources-collectees/rejetees.md` : sources écartées avec la raison. Trace éditoriale, pas déchet.

**Human gate**
L'utilisateur ouvre `sources.md`, vérifie :
- Métadonnées exactes (DOI présent quand il existe, dates justes, auteurs bien orthographiés).
- Bon ordre éditorial : les pivots sont en premier ou en position visible.
- Aucune source qui ne mérite pas d'y être (regarder `rejetees.md` pour vérifier les choix).

Correction possible ici même : rééditer `sources.md`, puis relancer les `add_source` manquants ou modifier via UI. L'étape 3 démarre après validation.
