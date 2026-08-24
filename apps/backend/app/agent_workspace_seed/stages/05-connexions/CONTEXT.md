---
contract: "Contrat de l'etape 05 : confirmer les connexions au graphe des fiches."
layer: L2
---

# 05-connexions

## Scope

Confirmer ou retirer les connexions du graphe Philum : fiches que celle-ci cite (`outgoing`) et fiches qui la citent (`incoming`).

## Inputs

| Source                               | File                                                | Section                                                                                   | Why                                  |
| ------------------------------------ | --------------------------------------------------- | ----------------------------------------------------------------------------------------- | ------------------------------------ |
| Preuve d'existence                   | `../01-brief/output/<slug>-card.json`               | Champ `id`                                                                                | Cible des appels connexion           |
| Catalogue des sources                | `../02-sources-collectees/output/<slug>-sources.md` | Notes des `find_cards_citing` déjà faites                                                 | Point de départ                      |
| Signature tools MCP                  | `../../shared/philum-mcp.md`                        | Lignes `list_connections`, `confirm_connection`, `remove_connection`, `find_cards_citing` | Appels stricts                       |
| Règle « pas de suggestion pendante » | `../../shared/garde-fous.md`                        | « Sur le graphe »                                                                         | Chaque suggestion doit être tranchée |

## Process

1. **Suggestions automatiques** : `mcp__philum__list_connections(card_slug)` rend `outgoing` (fiches que celle-ci cite) et `incoming` (fiches qui la citent, lecture seule).
2. **Élargissement manuel** : pour les sources sans suggestion, essayer :
   - `mcp__philum__find_cards_citing(url)` : fiches Philum qui citent la même URL.
   - `mcp__philum__search_cards(query="<mot-clé>")` : fiches sur le même thème.
3. **Verdict par suggestion `outgoing`** :
   - Confirmer : `mcp__philum__confirm_connection(card_slug, source_id)`.
   - Retirer : `mcp__philum__remove_connection(card_slug, source_id)`.
4. **Incoming** : rien à trancher, ces connexions sont dans la bibliographie d'autres créateurs. Les noter.

## Outputs

| Artifact                | Location                      | Format                                                                  |
| ----------------------- | ----------------------------- | ----------------------------------------------------------------------- |
| Verdicts des connexions | `output/<slug>-connexions.md` | Markdown : deux sections `outgoing` et `incoming`, un verdict par ligne |

## Checkpoints

| After Step | Agent Presents                                                    | Human Decides                                 |
| ---------- | ----------------------------------------------------------------- | --------------------------------------------- |
| 1          | Liste des suggestions automatiques avec extrait de la fiche cible | Confirmer ou retirer chaque suggestion        |
| 2          | Fiches candidates trouvées manuellement                           | Ajouter comme sources connectées si pertinent |

## Audit

| Check                      | Pass Condition                                                                |
| -------------------------- | ----------------------------------------------------------------------------- |
| Aucune suggestion pendante | Chaque entrée `outgoing` a un verdict `confirmée` ou `retirée` (jamais vide)  |
| Fiches confirmées lisibles | Ouvrir chaque fiche confirmée via `get_card`, vérifier titre et slug attendus |
| Incoming noté              | Chaque `incoming` figure dans `<slug>-connexions.md` même sans action         |
