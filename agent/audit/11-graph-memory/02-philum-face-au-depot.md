# 02. Philum face au dépôt : ce qui est déjà là, ce qui est cassé, ce qui manque

> Toute affirmation de ce document porte son ancre `chemin:ligne` et a été vérifiée en lisant le fichier. Rien n'est inféré du nom d'un symbole.

## Le fait qui change tout : le portage a déjà eu lieu

Le dépôt `graph-memory-starter` n'est pas à importer. **Il a déjà été porté dans Philum**, et le portage porte sa propre signature dans le code.

| Preuve | Ancre |
|---|---|
| Commentaire d'ontologie qui nomme le dépôt | `app/services/graph_memory.py:15` : `# Ontologie fermée Philum (STARTER: 5 types → Philum 7)` |
| `entity_id()` identique au caractère près | `graph_memory.py:51-57` contre `src/build_graph.py:11-18` |
| La requête récursive, adaptée à PostgreSQL | `graph_memory.py:31-48` (`LEAST(...)` au lieu du `MIN` imbriqué de SQLite, `:hops` en paramètre lié, tables `graph_entities`/`graph_relations`) |
| `Facts.as_text()` identique, y compris ses chaînes anglaises | `graph_memory.py:66-75` contre `src/recall.py:45-57` |
| Docstring de `build_graph` qui cite le dépôt | `graph_memory.py:81` : `2 passes comme STARTER` |
| Deux outils MCP exposés | `app/mcp_server/server.py:743` `recall_memory`, `:760` `rebuild_graph` |
| Injection automatique à chaque tour d'agent | `app/services/agent.py:1236-1259` |
| Deux migrations dédiées | `alembic/versions/053_graph_memory.py`, `054_graph_trgm.py` |

L'injection est faite avant l'appel du modèle, exactement selon la thèse du dépôt (`agent.py:1236-1259`) :

```python
# Le walk est fait en SQL avant l'appel — 0 tool call, 0 hops par le modele.
graph_ctx = ""
try:
    from app.services.graph_memory import recall as graph_recall
    ...
    facts = await graph_recall(db, q, hops=3)
    if facts.triples:
        graph_ctx = ("\n\n---\n## Mémoire graphe (rappel automatique, 2 ms)\n"
                     + facts.as_text() + "\n")
except Exception:  # nosec B110
    pass
messages.insert(0, {"role": "system", "content": systeme + workspace_ctx + graph_ctx})
```

La question utile n'est donc plus « qu'importer », mais **« qu'est-ce que le portage a raté, et qu'a-t-il laissé derrière lui »**. C'est l'objet des deux sections qui suivent.

Note d'infrastructure : `054_graph_trgm.py` crée l'extension `pg_trgm` et deux index GIN trigrammes, sur `lower(name)` de `graph_entities` et sur `lower(alias)` de `graph_aliases`. L'amorçage par `LIKE` est donc indexé. Ce n'est pas un défaut de performance qui suit, ce sont des défauts de justesse.

---

## Les neuf défauts du portage

Classés par valeur de la correction, pas par gravité théorique.

### 1. Le repli sémantique est du code mort

`recall()` bascule sur une recherche vectorielle quand l'amorçage lexical ne rend rien (`graph_memory.py:255-277`) :

```python
"SELECT id FROM graph_entities WHERE embedding IS NOT NULL ORDER BY embedding OPERATOR(...) ..."
```

Or **`build_graph()` n'écrit jamais la colonne `embedding`**. Les seuls `GraphEntity(...)` construits (`graph_memory.py:153-156`) portent `id`, `name`, `type`, `description`, `source_card_id`. Un grep de `embedding` dans `graph_memory.py` rend deux occurrences, toutes deux dans la requête de lecture ci-dessus. Aucun autre fichier du backend n'écrit cette colonne (`graph_entities` n'apparaît que dans 5 fichiers : le service, le modèle, `models/__init__.py`, et les migrations 053 et 054).

`WHERE embedding IS NOT NULL` filtre donc la totalité de la table. La branche coûte un appel `embed()` réseau, puis rend systématiquement zéro graine. Elle est de surcroît sous un `except Exception: pass`, donc l'échec est invisible.

Deux issues honnêtes, à trancher : remplir la colonne à la construction, ou retirer la branche. La garder telle quelle est le pire des trois.

### 2. Un UUID est injecté dans le contexte du modèle à la place d'un nom lisible

`Facts.as_text()` (`graph_memory.py:71`) rend chaque triplet suivi de son document source entre parenthèses. Dans le dépôt, ce champ est `source_doc`, un nom de fichier lisible (`refund-policy.md`). Dans Philum, c'est `r.source_card_id` (`graph_memory.py:39`), converti en chaîne à `graph_memory.py:287` : `str(r[3]) if r[3] else ""`.

Le modèle reçoit donc des lignes de la forme :

```
Les mitochondries --[cites]--> EFSA 2011   (7c9a1f2e-4b83-4d51-9a02-1f6b8e3c5d47)
```

Un UUID ne cite rien, ne se vérifie pas, n'apporte aucune information au modèle et consomme du contexte. La fiche a un `slug`, déjà utilisé comme nom de nœud (`graph_memory.py:136`). C'est lui qu'il faut joindre. Cela rejoint la règle maison de ne jamais afficher d'UUID.

### 3. Un nœud CARD orphelin est créé à partir du titre

`graph_memory.py:136-138` :

```python
add_node(card.slug, "CARD", card.description or card.title or "", card.id)
add_node(card.title, "CARD", card.description or "", card.id)
aliases.append((entity_id("CARD", card.slug), card.slug))
```

Deux nœuds `CARD` sont créés par fiche, un pour le slug et un pour le titre, avec des `entity_id` différents puisque la normalisation ne fait que minuscule et espaces vers soulignés. Or **toutes les arêtes sont construites depuis `entity_id("CARD", card.slug)`** (`graph_memory.py:163`, `:197`). Le nœud issu du titre n'a donc aucune arête, et aucun alias ne le relie au nœud du slug.

Conséquence mesurable : une question qui nomme la fiche par son titre amorce sur un nœud isolé, le parcours ne trouve rien, et le rappel rend `no memory matches` alors que le graphe contient la réponse. Le titre devrait être un **alias** du nœud slug, pas un second nœud.

### 4. L'unique alias est un non-opérateur

`graph_memory.py:138` pose l'alias `card.slug` sur l'entité `entity_id("CARD", card.slug)`. L'alias est identique au nom du nœud. Il ne peut rien faire trouver que le nom ne trouve déjà.

Autrement dit, **Philum n'a aujourd'hui aucun alias réel**, alors que les alias sont la soupape que le dépôt prévoit explicitement contre la rigidité de l'identité calculée (voir `01-le-depot.md`, section « L'identité d'un nœud est calculée »). Le titre de fiche (défaut 3), les noms d'auteurs sous leurs formes courtes, les acronymes de sources sont les candidats naturels.

### 5. L'amorçage est inversé et trop permissif

Le dépôt cherche **le nom de l'entité dans la question**, en mot entier (`src/recall.py:67`) :

```python
if re.search(rf"\b{re.escape(text.lower())}\b", q):
```

Philum fait l'inverse (`graph_memory.py:222-237`) : il extrait les mots de 4 caractères ou plus de la question, puis cherche **chaque mot comme sous-chaîne dans les noms d'entités** :

```python
words = [w for w in re.findall(r"\w{4,}", question.lower()) if len(w) >= 4]
conds = " OR ".join(f"lower(name) LIKE :w{i}" for i in range(len(words)))
params = {f"w{i}": f"%{w}%" for i, w in enumerate(words)}
```

Trois effets, tous indésirables :

- **Sous-chaîne, pas mot entier.** « note » amorce sur toute entité contenant « notes », « annoté », « dénoter ».
- **`OR` sur tous les mots.** Une question de vingt mots amorce sur l'union de vingt requêtes larges. Le parcours part alors d'un large échantillon quasi arbitraire du graphe, et le `top_k=8` tranche dans un ensemble dont la pertinence n'a jamais été évaluée.
- **Aucun mot vide n'est retiré.** « pour », « dans », « cette », « avec », « leur » passent le filtre des 4 caractères et amorcent. Le dépôt, lui, maintient une liste de 30 mots vides pour sa jambe mot-clé (`rag/search.py:21-25`).

Le commentaire de `graph_memory.py:223` justifie la bascule par la performance (`<50 ms même à 5k entités, vs 1.6s en Python`). L'objectif est légitime, la formulation SQL aussi ; c'est la **direction de la correspondance** qui est fausse. Chercher en SQL le nom d'entité comme mot entier dans la question est faisable et conserve le gain.

### 6. Le vocabulaire déclaré est très au-delà du vocabulaire écrit

`graph_memory.py:16-29` déclare 7 types et 11 prédicats. `build_graph()` en écrit :

| Déclaré | Réellement construit |
|---|---|
| 7 types : PERSON, ROLE, CARD, SOURCE, CONCEPT, POLICY, PROCESS | 4 : CARD (`:136`), PERSON (`:141`, `:148`), SOURCE (`:145`), CONCEPT (`:150`) |
| 11 prédicats | 3 : `cites` (`:173`), `authored_by` (`:186`), `references` (`:204`) |

ROLE, POLICY, PROCESS ne sont jamais instanciés. `supports`, `contradicts`, `part_of`, `held_by`, `delegates_to`, `attests`, `mentions`, `created_by` ne sont jamais écrits. `add_node` refuse tout type hors de l'ensemble (`graph_memory.py:128`), donc l'ensemble est un garde-fou utile, mais il décrit une ambition, pas un état.

Le risque n'est pas fonctionnel, il est documentaire : quiconque lit ces constantes croit que le graphe porte des contradictions et des délégations. Il ne porte que « fiche cite source », « source écrite par personne », « source renvoie à fiche ».

### 7. Le graphe redouble ce qu'une jointure SQL donne déjà, et aucune chaîne n'est assez longue pour justifier un parcours

Les trois arêtes construites sont exactement les clés étrangères existantes : `Source.biblio_card_id`, `Source.authors`, `Source.linked_card_id`. Une jointure de deux tables rend la même information, à jour, sans reconstruction.

Le dépôt se justifie par une question à trois sauts (`corpus/` : politique → rôle → personne → délégation). Dans Philum, la plus longue chaîne construite est fiche → source → personne, soit deux sauts, dont le second est directement lisible dans `Source.authors`. `hops=3` parcourt donc au-delà de ce que le graphe contient de structure : au troisième saut il redescend vers les autres sources du même auteur, ce qui est un voisinage, pas une chaîne de raisonnement.

C'est le défaut le plus structurant, et il conditionne les autres : **tant que le graphe ne porte pas d'arête qu'une jointure ne donne pas, corriger les défauts 1 à 6 améliore un mécanisme dont la valeur reste à établir.** Les prédicats déjà déclarés et non écrits (`supports`, `contradicts`, `attests`) sont précisément ceux qui produiraient des chaînes que SQL ne donne pas. Ils demandent en revanche une extraction, donc un modèle, donc une garde d'ancrage : c'est le sujet du document 03.

### 8. Le contexte injecté n'est pas borné, et annonce une durée fabriquée

`agent.py:1236-1259` insère `facts.as_text()` en entier dans le message système. Aucune limite de caractères. Avec `top_k=8` triplets et un bloc `where:` portant les descriptions de toutes les entités impliquées, la taille dépend de la longueur des descriptions de fiches, qui n'est pas bornée.

Le dépôt, lui, borne son hook : `TOP = 5`, `BUDGET = 1500` caractères, `PER_HIT = 280`, résultats coupés entiers (`rag/recall_hook.py`).

Par ailleurs l'en-tête injecté est la chaîne littérale `## Mémoire graphe (rappel automatique, 2 ms)`. Les 2 ms sont écrits en dur dans le code, alors que `Facts` porte la mesure réelle dans `self.ms` et que `as_text()` l'imprime déjà à sa première ligne. Le modèle reçoit donc, à chaque tour, une durée affirmée qui n'a pas été mesurée. C'est exactement le motif que les dernières PR ont rendu mécaniquement impossible du côté des sources : une affirmation sans mesure.

### 9. `rebuild_graph` est globalement destructif et ouvert à tout compte authentifié

`build_graph()` commence par vider les trois tables sans condition (`graph_memory.py:86-88`) :

```python
await db.execute(text("DELETE FROM graph_aliases"))
await db.execute(text("DELETE FROM graph_relations"))
await db.execute(text("DELETE FROM graph_entities"))
```

L'outil MCP `rebuild_graph` (`server.py:760-771`) exige une authentification et rien de plus : `await exiger_utilisateur(db)`. N'importe quel utilisateur connecté peut donc vider et reconstruire le graphe de **tous** les utilisateurs. Sa docstring dit « Requiert authentification (sinon un tiers pourrait declencher des reconstructions a la demande) », ce qui montre que le risque a été vu mais traité comme un problème de charge, pas de portée.

Deux aggravations : la reconstruction ne lit que les fiches publiées et publiques (`graph_memory.py:94-98`), donc la portée du graphe est globale et non par utilisateur, sans que rien ne le dise à la lecture ; et il n'existe aucun déclenchement automatique à la publication d'une fiche, donc le graphe est périmé entre deux appels manuels de l'outil.

---

## Les trois manques réels que le dépôt comble

Distincts des défauts ci-dessus : il ne s'agit plus de réparer le portage, mais de reprendre ce qui n'a pas été repris.

### A. La fusion par rang réciproque, absente de tout Philum

Philum a deux recherches d'extraits, et aucune ne fusionne :

- **Sémantique pure** : `app/services/excerpt_search.py`, cosinus avec `SIMILARITE_MINIMALE = 0.60` (`:52`, appliqué `:219`). Un extrait pertinent qui ne partage aucun vocabulaire avec la requête passe ; un extrait qui contient exactement le terme cherché mais dont le vecteur est loin est écarté sous le seuil.
- **Lexicale pure** : `app/mcp_server/tools_write.py:1380-1403`, `search_my_excerpts`, un `ILIKE '%...%'` sur `SourceExcerpt.text`, trié par `created_at desc`. Aucun classement par pertinence : le tri est chronologique.

Le dépôt fusionne les deux jambes en huit lignes sans calibrer aucune échelle (`rag/search.py:60-67`, `K = 60`), et conserve `found_by`, donc **quelle jambe a trouvé quoi**, information rendue à l'écran.

Pour Philum, la RRF a une propriété qui vaut plus que le gain de rappel : elle rend affichable la raison d'une remontée. « Trouvé par le mot et par le sens » est une information que l'utilisateur peut lire, et qui se rattache directement à la promesse de traçabilité du produit.

Le seuil `0.60` et le tri chronologique de `search_my_excerpts` deviendraient tous deux inutiles sous une fusion par rang, puisque la RRF ne compare pas de scores.

### B. La distillation à l'écriture, gardée par une citation verbatim

Le dépôt transforme chaque note, **au moment de l'écrire**, en une petite fiche interrogeable : deux ou trois questions telles qu'on les poserait des mois plus tard, un résumé d'une ligne, une règle, et une citation exacte qui prouve la réponse (`rag/distil-prompt.md`). Le prompt se clôt sur « If no exact quote proves the answer, produce nothing », et la garde est **vérifiée deux fois en code**, à la production (`rag/distil.py:128-133`) et de nouveau à l'indexation contre le fichier source (`rag/build_index.py:170-175`).

Philum possède déjà toute la machinerie d'ancrage verbatim : `app/services/excerpt_anchor.py` avec `SEUIL = 0.75` (`:42`, appliqué `:166` par `SequenceMatcher`), et `excerpt_insertion.py` avec `SEUIL_TYPOGRAPHIQUE = 0.95` (`:49`). Ce qui manque n'est pas la vérification, c'est **la génération des questions d'accès**. Un extrait est aujourd'hui trouvable par son texte et par son vecteur, jamais par la question à laquelle il répond.

La double vérification aux deux bouts de la chaîne est le point à copier tel quel : une garde à l'écriture seule se contourne par une modification ultérieure, ce qui est exactement le cas d'`update_excerpt`, dont la purge de `verified_at` est déjà au plan.

Détail à ne pas re-proposer : le dépôt préfixe le libellé `[fichier § section]` au texte avant embedding (`rag/build_index.py:160-162`). **Philum le fait déjà**, `app/services/embeddings.py:52-66`, `texte_a_embedder()` joint titre, contexte et verbatim, avec une docstring qui explique précisément pourquoi. C'est un point de convergence, pas un manque.

### C. La mémoire de session, qui survit à la session

`digest/` fait de chaque session fermée une note que l'index retrouve. Trois propriétés valent d'être retenues, indépendamment de toute décision d'implémentation :

1. **Le filtrage est du code, en rejet par défaut** (`digest/session_end.py:76-112`). Rien n'est écarté par un jugement de modèle. Ce qui n'est pas explicitement reconnu est écarté.
2. **Une session maigre produit une entrée qui dit qu'elle est maigre** (`digest/digest-prompt.md`), ou rien du tout en dessous de 5 tours. Le prompt le motive : une session mince rédigée comme si elle était complète est pire que pas d'entrée du tout.
3. **Rien n'est bloquant** : le hook rend la main en moins d'une seconde et sort toujours en 0 ; l'échec part dans un journal (`digest/common.py:62-70`).

Philum n'a rien d'équivalent. `app/services/agent_sessions.py` élague les contenus longs (`ELAGAGE_SEUIL = 2_000`, `:38`, appliqué `:115`) à l'intérieur d'une requête. Rien ne survit à la session, et la PR 4 du plan en cours (compaction de contexte) traite le même symptôme sans produire de mémoire durable.

C'est le manque le plus ambitieux des trois, et le seul dont la valeur pour Philum reste à démontrer : la mémoire de session sert un agent de développement travaillant seul sur des notes personnelles, pas nécessairement un agent multi-utilisateur qui écrit des fiches publiques. À traiter comme une piste, pas comme un acquis.

---

## Ce qui est déjà présent et ne doit pas être re-proposé

| Élément du dépôt | Équivalent Philum |
|---|---|
| Identité de nœud content-addressed | `graph_memory.py:51-57`, identique |
| Parcours récursif non orienté, tri par profondeur | `graph_memory.py:31-48`, adapté à PostgreSQL |
| Ontologie fermée avant écriture | `graph_memory.py:16-29`, déclarée (voir défaut 6 pour l'écart) |
| Rappel injecté avant l'appel, zéro appel d'outil | `agent.py:1236-1259` |
| Échec bruyant hors vocabulaire | `graph_memory.py:69`, `(no memory matches for this prompt)` |
| Libellé joint au texte avant embedding | `embeddings.py:52-66`, `texte_a_embedder()` |
| Vérification qu'une citation figure verbatim dans sa source | `excerpt_anchor.py:42`, `:166` |

---

_Rédigé le 2026-08-30. Chaque ancre `chemin:ligne` a été ouverte et lue ; aucune n'est déduite d'un nom de symbole ou d'un résultat de recherche._
