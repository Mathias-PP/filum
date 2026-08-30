# Audit 11. graph-memory-starter → Philum

> Passage au peigne fin du dépôt `Glitch-Cat-Club/graph-memory-starter`, lu en entier au commit `496a6e9`. Découverte décisive : **Philum a déjà porté ce dépôt** (`services/graph_memory.py`, `agent.py:1236-1259`, migrations 053 et 054). L'audit porte donc sur ce que le portage a raté, pas sur ce qu'il faudrait importer. Résultat : 9 défauts du portage, 3 manques réels, 1 tableau d'évaluation du dépôt qui ne tient pas.

---

## Dashboard

| Fichier | Contenu |
|---|---|
| [`01-le-depot.md`](./01-le-depot.md) | Relevé fichier par fichier des trois couches du dépôt (graphe, RAG, digest), et démolition de son tableau d'évaluation |
| [`02-philum-face-au-depot.md`](./02-philum-face-au-depot.md) | Preuve du portage, les 9 défauts, les 3 manques, ce qui est déjà là et ne doit pas être re-proposé |
| [`03-matiere-pour-le-plan.md`](./03-matiere-pour-le-plan.md) | 3 questions à trancher, 6 lots, ordre proposé, ce qu'il ne faut pas faire |

---

## Le dépôt en une ligne

Trois couches empilables, branchées par des hooks de prompt : `src/` un graphe en 3 tables SQLite parcouru par une requête récursive, `rag/` un index à deux jambes fusionnées en rang réciproque, `digest/` chaque session fermée devenue une note retrouvable. Thèse commune, `README.md:171` : **« Spend intelligence at build; answer from structure. »**

187 étoiles, 14 forks, MIT, 42 Ko, créé le 2026-08-16. Démonstration de conception jeune, pas projet établi. Ce qui vaut ici vaut par la lecture du code, jamais par l'adoption.

---

## Preuve que le portage a déjà eu lieu

| Preuve | Ancre |
|---|---|
| Commentaire qui nomme le dépôt | `services/graph_memory.py:15` : `# Ontologie fermée Philum (STARTER: 5 types → Philum 7)` |
| `entity_id()` identique | `graph_memory.py:51-57` contre `src/build_graph.py:11-18` |
| Requête récursive adaptée à PostgreSQL | `graph_memory.py:31-48` |
| `Facts.as_text()` identique, chaînes anglaises comprises | `graph_memory.py:66-75` |
| Injection avant l'appel du modèle | `services/agent.py:1236-1259` |
| Outils MCP | `mcp_server/server.py:743` `recall_memory`, `:760` `rebuild_graph` |
| Migrations | `053_graph_memory.py`, `054_graph_trgm.py` (pg_trgm + index GIN) |

---

## Les 9 défauts du portage

| # | Défaut | Ancre | Effet observable |
|---|---|---|---|
| 1 | Repli sémantique en code mort | `graph_memory.py:255-277` lit `embedding`, `:153-156` ne l'écrit jamais | `WHERE embedding IS NOT NULL` filtre toute la table ; un appel réseau pour zéro graine, sous un `except: pass` |
| 2 | UUID injecté au lieu du slug | `graph_memory.py:39`, `:287` | le modèle lit `(7c9a1f2e-...)` là où le dépôt lit `(refund-policy.md)` |
| 3 | Nœud CARD orphelin issu du titre | `graph_memory.py:136-138` vs `:163`, `:197` | nommer une fiche par son titre amorce sur un nœud sans arête : `no memory matches` alors que le graphe a la réponse |
| 4 | L'unique alias est un non-opérateur | `graph_memory.py:138` | l'alias vaut le nom du nœud ; Philum n'a aucun alias réel |
| 5 | Amorçage inversé et trop permissif | `graph_memory.py:222-237` vs `src/recall.py:67` | sous-chaîne au lieu du mot entier, `OR` sur tous les mots, aucun mot vide retiré |
| 6 | Vocabulaire déclaré très au-delà de l'écrit | `graph_memory.py:16-29` | 7 types déclarés, 4 construits ; 11 prédicats déclarés, 3 écrits |
| 7 | Le graphe redouble une jointure SQL | `graph_memory.py:173`, `:186`, `:204` | 3 arêtes, toutes des clés étrangères ; chaîne la plus longue à 2 sauts, `hops=3` |
| 8 | Contexte non borné, durée fabriquée | `agent.py:1250` | `## Mémoire graphe (rappel automatique, 2 ms)` en dur, alors que `Facts.ms` porte la mesure |
| 9 | `rebuild_graph` globalement destructif | `graph_memory.py:86-88`, `server.py:760-771` | tout compte authentifié vide et reconstruit le graphe de tous |

Le défaut 7 conditionne les autres : tant que le graphe ne porte pas d'arête qu'une jointure ne donne pas, corriger 1 à 6 améliore un mécanisme dont la valeur reste à établir.

---

## Les 3 manques réels

| Manque | Ce que le dépôt fait | Ce que Philum a | Ce qui manque |
|---|---|---|---|
| Fusion par rang réciproque | `rag/search.py:60-67`, 8 lignes, `K = 60`, sans calibration | cosinus pur seuillé (`excerpt_search.py:52`, `:219`) **et** ILIKE trié par date (`tools_write.py:1380-1403`) | la fusion, et `found_by` qui rend affichable quelle jambe a trouvé quoi |
| Distillation à l'écriture | questions d'accès gardées par une citation exacte, vérifiée **deux fois** (`distil.py:128-133`, `build_index.py:170-175`) | la vérification verbatim (`excerpt_anchor.py:42`, `:166`) | la génération des questions ; un extrait n'est jamais trouvable par la question à laquelle il répond |
| Mémoire de session | `digest/`, filtrage par code en rejet par défaut, jamais bloquant | `agent_sessions.py:38` élague dans la requête | rien ne survit à la session. Piste, valeur non établie pour du multi-utilisateur |

---

## Déjà présent, à ne pas re-proposer

| Élément du dépôt | Équivalent Philum |
|---|---|
| Identité de nœud content-addressed | `graph_memory.py:51-57`, identique |
| Parcours récursif non orienté, tri par profondeur | `graph_memory.py:31-48` |
| Rappel injecté avant l'appel, zéro appel d'outil | `agent.py:1236-1259` |
| Échec bruyant hors vocabulaire | `graph_memory.py:69` |
| Libellé joint au texte avant embedding | `embeddings.py:52-66`, `texte_a_embedder()` |
| Vérification verbatim d'une citation | `excerpt_anchor.py:42`, `:166` |

---

## Le tableau d'évaluation du dépôt ne tient pas

`README.md:152-159` compare trois modèles en condition « recherche » contre condition « graphe », et conclut qu'un petit modèle raisonne mieux avec le graphe (Haiku : 1/3 sauts contre 3/3).

Vérification faite en lisant les champs `source_doc` de `extraction/*.json` : ils nomment exactement les 8 fichiers de `corpus/`. Le graphe est construit sur ces 8 documents curés, la recherche tourne sur les 12 documents désordonnés de `corpus-before/`. Or `corpus-before/` contient `refunds-policy-2024-superseded.md`, seul fichier du dépôt à contenir « 250 », qui contredit la règle courante de 500 £. `rag/README.md:48-49` affirme le contraire des fichiers.

- **Survit** : zéro appel d'outil, coût d'injection fixe quelle que soit la taille du corpus. Propriétés de conception.
- **Ne survit pas** : la conclusion sur la qualité de raisonnement. L'écart mesure deux effets à la fois.
- **À ne jamais citer** : le « 3.1x retrieval quality » (`rag/README.md:27`), métrique non définie, jeu de test non publié.

---

## Trois questions à trancher avant tout plan

1. **Le graphe mérite-t-il d'exister sous sa forme actuelle ?** (défaut 7) Retirer, réparer à contenu constant, ou lui donner des arêtes qu'une jointure ne donne pas.
2. **Le repli sémantique : remplir `embedding` ou retirer la branche ?** (défaut 1) Le garder tel quel n'est pas une option.
3. **La portée du graphe est-elle globale ou par utilisateur ?** (défaut 9) Détermine si c'est une correction de sécurité ou de documentation.

---

## Ordre proposé

| Rang | Lot | Justification |
|---|---|---|
| 1 | A. Rendre le rappel honnête (slug, alias de titre, amorçage, bornage, durée réelle) | sans regret quel que soit le sort du graphe, et corrige un rappel aujourd'hui faux |
| 2 | D. Fusion par rang réciproque | indépendant du graphe, 8 lignes de mécanisme, bénéfice mesurable |
| 3 | C1, C2. Portée et droits de `rebuild_graph` | très petit, à ne pas laisser traîner |
| 4 | B (réduction). Aligner le vocabulaire déclaré sur l'écrit | coût nul |
| 5 | Question 1 tranchée | décision, pas travail |
| 6 | B (extraction), E. distillation, F. mémoire de session, C3. fraîcheur | chantiers à cadrer séparément |

Les rangs 1 à 4 forment un ensemble livrable. À partir du rang 5, il ne s'agit plus d'exécuter mais de décider.

---

_Relevé le 2026-08-30, par clonage du dépôt au commit `496a6e9` et lecture de ses 53 fichiers, puis vérification de chaque ancre Philum en ouvrant le fichier. Aucune estimation en jours : les lots 5 et 6 ne sont pas cadrés._
