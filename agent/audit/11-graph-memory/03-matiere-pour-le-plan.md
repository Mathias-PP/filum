# 03. Matière pour le plan

> Ce document ne décide pas. Il range ce que les documents 01 et 02 ont établi sous la forme dont un plan a besoin : un lot, ce qu'il change, où, ce qu'il faut trancher avant, comment on saura que ça marche. Les estimations sont des ordres de grandeur, pas des engagements.

## Trois questions à trancher avant d'écrire un plan

Aucun lot ci-dessous ne se justifie seul si ces questions ne sont pas répondues.

**Q1. Le graphe mérite-t-il d'exister sous sa forme actuelle ?** Le défaut 7 du document 02 établit qu'il ne porte aujourd'hui que trois arêtes, toutes obtenables par une jointure de deux tables, et qu'aucune chaîne ne dépasse deux sauts. Trois issues : le retirer, le réparer à contenu constant, ou lui donner des arêtes qu'une jointure ne donne pas (`supports`, `contradicts`, `attests`). Les lots B et C ci-dessous supposent la deuxième ou la troisième.

**Q2. Le repli sémantique du rappel : remplir ou retirer ?** Défaut 1. Remplir `graph_entities.embedding` à la construction coûte un appel d'embedding par entité et rend la branche vivante. Retirer la branche supprime un appel réseau inutile par question sans amorce. La garder telle quelle n'est pas une option.

**Q3. La portée du graphe est-elle globale ou par utilisateur ?** Défaut 9. `build_graph()` ne lit que les fiches publiées et publiques, donc le graphe est un objet global, mais rien dans le code ni dans les docstrings ne l'énonce, et `rebuild_graph` laisse tout compte authentifié le reconstruire. Répondre à cette question détermine si le lot A est une correction de sécurité ou une clarification de documentation.

---

## Lot A. Rendre le rappel honnête

Le plus petit lot, le plus rentable, et **le seul qui soit sans regret quelle que soit la réponse à Q1** : il améliore le mécanisme s'il reste, il ne coûte rien de perdu s'il part.

| # | Ce qui change | Fichier |
|---|---|---|
| A1 | Le champ source du triplet devient le `slug` de fiche, plus l'UUID | `graph_memory.py:39` (SQL, joindre `biblio_cards`), `:287` |
| A2 | Le titre de fiche devient un **alias** du nœud slug, plus un second nœud CARD | `graph_memory.py:136-138` |
| A3 | Amorçage par nom d'entité en mot entier dans la question, plus par sous-chaîne inversée | `graph_memory.py:222-248` |
| A4 | L'en-tête injecté rend la mesure réelle, plus la chaîne « 2 ms » écrite en dur | `agent.py:1250` |
| A5 | Le contexte injecté est borné en caractères, coupé sur des triplets entiers | `agent.py:1236-1259`, motif `rag/recall_hook.py` |
| A6 | Q2 tranchée : la branche sémantique est remplie ou retirée | `graph_memory.py:255-277` et `:153-156` |

Sur A3, la contrainte de performance qui a motivé la formulation actuelle (`graph_memory.py:223`) reste valable et se conserve : la correspondance de mot entier peut rester en SQL, c'est sa **direction** qui doit s'inverser. Retirer les mots vides est le complément minimal ; le dépôt en maintient une liste de 30 (`rag/search.py:21-25`).

Sur A5, valeurs de référence du dépôt, à adapter et non à recopier : `TOP = 5`, budget total 1500 caractères, 280 par résultat, résultats coupés entiers (`rag/recall_hook.py`).

**Vérifiable par :** un test qui construit un graphe minimal, pose une question nommant une fiche **par son titre**, et exige un triplet en retour. Ce test échoue aujourd'hui (défaut 3). Un second test exige qu'aucune sortie de `as_text()` ne contienne de motif UUID.

**Ordre de grandeur :** faible, un fichier de service et une portion d'`agent.py`. Aucune migration.

---

## Lot B. Aligner le vocabulaire déclaré sur le vocabulaire écrit

Défaut 6. Deux directions opposées, et il faut choisir avant d'écrire une ligne :

- **Réduire** `ENTITY_TYPES` et `PREDICATES` à ce que `build_graph()` écrit réellement (4 types, 3 prédicats), et documenter que le reste est une extension future. Coût nul, effet immédiat sur la lisibilité, aucune promesse tenue.
- **Écrire** les prédicats manquants. C'est la seule voie qui répond à Q1 par la troisième issue. `supports`, `contradicts` et `attests` sont exactement les arêtes qu'une jointure ne donne pas, et donc les seules qui justifient un parcours récursif.

La seconde direction a un prix qu'il faut nommer : ces arêtes ne se déduisent d'aucune colonne, elles demandent une extraction par modèle, donc une garde d'ancrage. Le dépôt fournit le patron exact de cette garde (document 02, manque B) : le modèle ne produit rien sans citation exacte, et la citation est vérifiée **deux fois en code**, à la production et à l'indexation. Philum a déjà la moitié de cette garde (`excerpt_anchor.py:42`, `:166`).

**Lien avec l'existant :** un prédicat `supports` ou `contradicts` entre une source et une affirmation de fiche est très proche du grain « affirmation ↔ empan » validé par l'étude d'outils de recherche. Ce lot ne doit pas être planifié sans relire cette étude.

**Ordre de grandeur :** faible si réduction, important si extraction, et dans ce second cas il ne s'agit plus d'un lot mais d'un chantier à cadrer séparément.

---

## Lot C. Sécuriser et rafraîchir la reconstruction

Défaut 9, conditionné à Q3.

| # | Ce qui change | Fichier |
|---|---|---|
| C1 | `rebuild_graph` n'est plus déclenchable par tout compte authentifié | `server.py:760-771` |
| C2 | La portée globale du graphe est énoncée dans la docstring et dans le nom | `graph_memory.py:78-84`, `server.py:761-766` |
| C3 | Le graphe cesse d'être périmé entre deux appels manuels | à concevoir : reconstruction déclenchée à la publication, ou tâche périodique |

C3 est le seul point sans solution évidente. Une reconstruction intégrale à chaque publication est un coût qui croît avec le corpus ; une mise à jour incrémentale n'existe pas dans le dépôt (`src/build_graph.py:22` supprime et reconstruit), donc il n'y a rien à copier. À cadrer.

**Ordre de grandeur :** faible pour C1 et C2, indéterminé pour C3.

---

## Lot D. La fusion par rang réciproque

Manque A du document 02. **Indépendant du graphe** : ce lot se justifie même si Q1 est répondue par « retirer ».

État actuel : deux recherches, aucune fusion. `excerpt_search.py` est un cosinus pur seuillé à `SIMILARITE_MINIMALE = 0.60` (`:52`, `:219`) ; `search_my_excerpts` (`tools_write.py:1380-1403`) est un `ILIKE '%...%'` trié par `created_at desc`, donc sans classement par pertinence.

Ce que le dépôt apporte tient en huit lignes (`rag/search.py:60-67`, `K = 60`) et n'exige aucune calibration entre les deux échelles. Deux conséquences en cascade, à noter dans le plan parce qu'elles simplifient du code existant :

- Le seuil `0.60` perd sa raison d'être : la RRF classe, elle ne filtre pas sur un score absolu.
- Le tri chronologique de `search_my_excerpts` disparaît au profit d'un rang de pertinence.

Et une propriété à ne pas perdre en route : `found_by` conserve **quelle jambe a trouvé quoi** (`rag/search.py:75`, `legs: keyword+meaning`). C'est une information affichable, qui se rattache directement à la promesse de traçabilité du produit. Elle vaut, pour Philum, davantage que le gain de rappel.

**Vérifiable par :** un extrait contenant exactement le terme cherché mais dont le vecteur est sous le seuil actuel doit remonter. Un extrait sémantiquement proche sans terme commun doit remonter aussi. Aujourd'hui chaque cas échoue dans l'une des deux recherches.

**Ordre de grandeur :** modéré. La fonction de fusion est triviale ; le travail est dans l'unification des deux chemins d'appel et dans le rendu de la provenance.

---

## Lot E. La distillation à l'écriture

Manque B du document 02. Le plus prometteur et le plus délicat.

Idée : au moment où un extrait est enregistré, produire les questions auxquelles il répond, gardées par la citation verbatim qui les prouve. Un extrait devient alors trouvable par la question, et plus seulement par son texte et par son vecteur.

Ce que Philum a déjà, et qui doit être réutilisé et non refait :

- la vérification qu'une citation figure verbatim dans sa source : `excerpt_anchor.py:42` (`SEUIL = 0.75`), appliqué `:166` ;
- la composition titre + contexte + verbatim avant embedding : `embeddings.py:52-66`, avec une docstring qui explique déjà pourquoi un passage ne se suffit pas à lui-même.

Ce que le dépôt ajoute, et qu'il faut copier tel quel :

- **le format est lu et écrit par la même fonction** (`parse_entry`, importée par `rag/distil.py` depuis `rag/build_index.py`), de sorte que l'écrivain et le lecteur ne peuvent pas diverger sur deux orthographes du format ;
- **la garde est vérifiée deux fois**, à la production (`rag/distil.py:128-133`) et de nouveau à l'indexation contre la source (`rag/build_index.py:170-175`). Une garde à l'écriture seule se contourne par une modification ultérieure, ce qui est exactement le cas d'`update_excerpt` ;
- **l'idempotence par empreinte** (`rag/distil.py:152-159`, sha256 du contenu dans un état à plat), plutôt qu'une file avec des états `pending`/`processing`/`failed` ;
- **le rejet nommé** : ce qui est écarté est compté et affiché avec sa cause, jamais ignoré en silence.

Ce qui ne se transpose pas : le dépôt distille par appel à un sous-processus modèle en local, avec isolement des variables d'environnement (`rag/distil.py:46-56`). Philum a déjà une couche de fournisseurs ; l'isolement de processus est sans objet ici.

**Ordre de grandeur :** important. À cadrer comme un chantier, avec sa propre étude préalable.

---

## Lot F. La mémoire de session

Manque C du document 02. **À traiter comme une piste, pas comme un acquis.** Le dépôt sert un agent de développement travaillant seul sur des notes personnelles ; Philum est multi-utilisateur et produit des fiches publiques. La valeur n'est pas établie.

Trois propriétés à retenir quelle que soit la décision, parce qu'elles sont transposables hors de tout mécanisme de mémoire :

1. **Le filtrage est du code, en rejet par défaut** (`digest/session_end.py:76-112`). Rien n'est écarté par un jugement de modèle ; ce qui n'est pas explicitement reconnu est écarté.
2. **Une session maigre produit une entrée qui dit qu'elle est maigre**, ou rien en dessous de 5 tours. Le motif écrit : une session mince rédigée comme si elle était complète est pire que pas d'entrée du tout.
3. **Rien n'est bloquant** : sortie en moins d'une seconde, code de retour toujours 0, l'échec part dans un journal (`digest/common.py:62-70`).

À noter : la PR 4 du plan agent en cours (compaction de contexte) traite le même symptôme que ce lot, mais sans produire de mémoire durable. `agent_sessions.py:38` (`ELAGAGE_SEUIL = 2_000`) élague à l'intérieur d'une requête. Les deux ne doivent pas être planifiés en parallèle sans arbitrage.

---

## Ordre proposé, et pourquoi

| Rang | Lot | Justification de la place |
|---|---|---|
| 1 | A | Sans regret quelle que soit la réponse à Q1, petit, et corrige un rappel aujourd'hui faux |
| 2 | D | Indépendant du graphe, bénéfice mesurable, huit lignes de mécanisme |
| 3 | C1, C2 | Correction de portée, très petite, à ne pas laisser traîner |
| 4 | B (réduction) | Aligne la documentation sur le code, coût nul |
| 5 | Q1 tranchée | Décision, pas travail. Conditionne tout ce qui suit |
| 6 | B (extraction), E, F, C3 | Chantiers à cadrer séparément, chacun avec sa propre étude |

Les rangs 1 à 4 forment un ensemble cohérent et livrable. À partir du rang 5, il ne s'agit plus d'exécuter mais de décider.

---

## Ce qu'il ne faut pas faire

- **Citer le tableau d'évaluation du dépôt.** Document 01, section « Les mesures annoncées » : les deux conditions ne tournent pas sur le même corpus, et la condition graphe a été privée du document contradictoire. Ce qui survit est la propriété de conception (zéro appel d'outil, coût d'injection fixe), pas la conclusion sur la qualité de raisonnement.
- **Citer le « 3.1x retrieval quality »** (`rag/README.md:27`) : métrique non définie, jeu de test non publié, non reproductible.
- **Re-proposer le libellé joint au texte avant embedding** : `embeddings.py:52-66` le fait déjà.
- **Justifier une reprise par les 187 étoiles du dépôt.** C'est une démonstration de conception jeune, pas un projet établi. Ce qui vaut ici vaut par la lecture du code.
- **Empiler des règles de prompt** pour corriger un comportement dont la cause est dans la couche outil. Les défauts 2, 5 et 8 du document 02 sont des bugs de code, pas des défauts d'instruction.

---

_Rédigé le 2026-08-30, à partir des documents 01 et 02 du même dossier. Aucune décision n'est prise ici._
