# Étape 5 : Connexions au graphe Philum

**Reads**
- `runs/<slug>/01_brief/card.json` (`card_slug`).
- `runs/<slug>/02_sources-collectees/sources.md` (notes des `find_cards_citing` déjà faites).
- `_system/philum-mcp.md` (comment appeler `search_cards`, `get_card`, `find_cards_citing`).

**Does**
1. **Suggestions automatiques** : le serveur détecte déjà que certaines sources sont des fiches Philum publiées. Récupérer la liste via `GET /api/v1/cards/{card_id}/connections` (endpoint qui rend `outgoing` + `incoming`).
2. **Élargissement manuel** : pour les sources sans suggestion automatique, essayer :
   - `mcp__philum__find_cards_citing(url)` : les fiches Philum qui citent la même URL.
   - `mcp__philum__search_cards(query="<mot-clé de la source ou du sujet>")` : les fiches qui parlent du même thème.
3. **Verdict par suggestion** : pour chaque connexion suggérée, deux options :
   - **Confirmer** via `POST /api/v1/cards/{card_id}/connections/{source_id}/confirm`.
   - **Retirer** via `DELETE /api/v1/cards/{card_id}/connections/{source_id}`.
   Ne pas laisser une suggestion pendante : c'est un « je n'ai pas voulu trancher », état interdit pour publier (voir `_system/garde-fous.md`).
4. **Cas incoming** : si des fiches d'autres créateurs citent une des sources de la fiche en cours, elles apparaissent en `incoming`. Rien à faire : ces connexions existent, ne sont pas modifiables ici, mais leur existence rend la fiche plus lisible dans le graphe.

**Writes**
- `runs/<slug>/05_connexions/connexions.md` : une entrée par suggestion, avec verdict (`confirmée` | `retirée`) et raison courte. Deux sections : `outgoing` (que la fiche cite) et `incoming` (qui cite la fiche).

**Human gate**
L'utilisateur ouvre `connexions.md` et vérifie :
- Chaque suggestion a un verdict tranché.
- Les fiches confirmées sont bien celles qu'il voulait citer (pas de faux-positif).
- Les incoming sont notées, pas modifiées.

L'étape 6 démarre après validation.
