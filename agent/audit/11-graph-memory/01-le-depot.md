# 01. Relevé du dépôt graph-memory-starter

> Relevé fichier par fichier, fait en clonant le dépôt et en lisant chaque fichier. Toute ligne de code citée ici a été lue. Les chiffres externes viennent de l'API GitHub, pas d'une mémoire d'entraînement.

## Identité

| Champ | Valeur, relevée le 2026-08-30 |
|---|---|
| Dépôt | `Glitch-Cat-Club/graph-memory-starter` |
| Description | « Knowledge graph memory for AI assistants: three SQLite tables, one recursive query, one prompt hook. » |
| Licence | MIT |
| Langage | Python, sans dépendance obligatoire hors `fastembed` (optionnel) |
| Étoiles / forks | 187 / 14 |
| Taille | 42 Ko, 53 fichiers |
| Créé / poussé | 2026-08-16 / 2026-08-30 |
| Commit lu | `496a6e9d9b9578943ec5ed34c2780de5a0fa5510` |

Dépôt jeune et actif. Le compte d'étoiles est faible : ce n'est pas un projet établi, c'est une démonstration de conception. Son intérêt tient à la conception, pas à son adoption, et rien ici ne doit être repris au motif que « 187 personnes l'ont étoilé ».

## Ce que le dépôt est

Trois couches indépendantes, empilables, chacune branchée par un hook de prompt Claude Code.

```
src/      le graphe    : 3 tables SQLite, 1 requête récursive, parcours par du code
rag/      le sémantique: index chunks + FTS5 + vecteurs, 2 jambes fusionnées en RRF
digest/   la mémoire   : chaque session fermée devient une note que le RAG retrouve
```

La thèse du dépôt tient en une phrase de son README (ligne 171) : **« Spend intelligence at build; answer from structure. »** Dépenser le modèle au moment d'écrire, répondre depuis la structure. Tout le reste en découle.

---

## Couche 1 : le graphe (`src/`)

### Le schéma, en entier

`src/schema.sql`, 6 lignes, reproduit intégralement :

```sql
CREATE TABLE entities  (id TEXT PRIMARY KEY,   -- uuid5(type + normalised name)
                        name TEXT, type TEXT,
                        description TEXT, source_doc TEXT);
CREATE TABLE relations (source_id TEXT, target_id TEXT,
                        predicate TEXT, source_doc TEXT);
CREATE TABLE aliases   (entity_id TEXT, alias TEXT);
```

À noter, parce que ce sont des choix et non des oublis : aucune clé étrangère, aucun index, aucun horodatage, aucune colonne de confiance ou de score. Trois tables plates. Chaque arête et chaque entité porte son `source_doc` : **toute assertion du graphe sait de quel document elle vient.**

### L'identité d'un nœud est calculée, pas attribuée

`src/build_graph.py:11-18` :

```python
def normalise(name: str) -> str:
    return name.lower().strip().replace(" ", "_")

def entity_id(type_: str, name: str) -> str:
    key = f"{type_}:{normalise(name)}"
    return str(uuid.uuid5(uuid.NAMESPACE_OID, key))
    # "Ops Manager" in doc 1 and doc 4 -> the same node. No ML, no lookup.
```

C'est le point le plus transposable du dépôt. L'identifiant est un hash du couple (type, nom normalisé). Conséquences directes :

- La déduplication est gratuite et exacte. Deux documents qui nomment la même entité produisent la même ligne, sans résolution d'entités, sans modèle, sans table de correspondance.
- La construction est idempotente : mêmes entrées, même base, au bit près. Le fichier le dit en première ligne : « Deterministic: same input, same db. »
- Le prix est assumé : deux entités homonymes de même type fusionnent à tort, et une faute de frappe crée un nœud distinct. Les alias sont la soupape.

### La construction, en deux passes

`build_graph.py:22-65`. La base est **supprimée puis reconstruite** à chaque exécution (`DB.unlink(missing_ok=True)`, ligne 22). Passe 1 : tous les nœuds de tous les documents, en `INSERT OR IGNORE`. Passe 2 : les arêtes et les alias, dont les extrémités sont résolues par nom normalisé contre l'index construit en passe 1.

Le traitement des arêtes orphelines mérite d'être noté (`build_graph.py:50-51`, puis `63-65`) : une arête dont une extrémité est inconnue n'est pas insérée, elle est **collectée puis affichée nommément** en fin de construction.

```
skipped edge in supplier-notes.md: Dee --[approved_by]--> Q2 renewals (unknown endpoint)
```

Elle n'est ni insérée silencieusement, ni ignorée silencieusement. C'est la même famille de garde que les refus de Philum qui montrent la liste de ce qui existe.

### La lecture : une requête récursive, zéro appel de modèle

`src/recall.py`, dont l'en-tête dit : « Pure SQLite, no model call anywhere in this file. This is the code that runs inside the prompt hook, so it has to be deterministic and fast. »

Amorçage (`recall.py:60-69`) : une entité devient graine quand **son nom ou l'un de ses alias apparaît dans la question**, en correspondance de mot entier (`\b...\b`). Pas d'embedding, pas de modèle, pas de flou.

Le parcours (`recall.py:16-36`) :

```sql
WITH RECURSIVE walk(entity_id, depth) AS (
  SELECT id, 0 FROM entities WHERE id IN ({seeds})
  UNION
  SELECT CASE WHEN r.source_id = w.entity_id
              THEN r.target_id ELSE r.source_id END,
         w.depth + 1
  FROM relations r JOIN walk w
    ON w.entity_id IN (r.source_id, r.target_id)
  WHERE w.depth < ?
)
SELECT e1.name, r.predicate, e2.name, r.source_doc,
       MIN((SELECT MIN(depth) FROM walk WHERE entity_id = r.source_id),
           (SELECT MIN(depth) FROM walk WHERE entity_id = r.target_id)) AS near
FROM relations r
JOIN entities e1 ON e1.id = r.source_id
JOIN entities e2 ON e2.id = r.target_id
WHERE r.source_id IN (SELECT entity_id FROM walk)
  AND r.target_id IN (SELECT entity_id FROM walk)
ORDER BY near
```

Quatre détails de conception, tous délibérés :

1. `UNION` et non `UNION ALL` : les cycles du graphe ne bouclent pas, la déduplication est faite par SQLite.
2. Le parcours est **non orienté** (le `CASE` suit l'arête dans les deux sens), ce qui est ce qu'on veut d'une mémoire : « qui approuve X » et « X est approuvé par qui » doivent trouver la même arête.
3. Seules les arêtes dont **les deux** extrémités sont dans le parcours sont rendues, ce qui coupe la frange de bruit à la profondeur maximale.
4. Le tri par `near`, la profondeur du plus proche des deux bouts, fait remonter d'abord ce qui touche la question. La troncature `top_k` coupe donc le plus lointain, jamais le plus pertinent.

Paramètres par défaut : `hops=3`, `top_k=8` (`recall.py:72`).

### Le rendu, et le refus

`recall.py:45-57`. Le résultat est mis en texte aligné, chaque triplet suivi de son document source, puis un bloc `where:` porte les descriptions des entités impliquées. Le commentaire de la ligne 54 dit pourquoi ce bloc existe : « The conditions live on the entities, not the edges - carry them. » Le graphe porte la structure, la description porte les conditions (montants, dates, fenêtres).

Et quand rien ne correspond (`recall.py:48`) :

```
memory: 0 facts recalled in 2 ms
(no memory matches for this prompt)
```

Le tableau des cas de test du README (ligne 139) en fait un cas nominal, pas un échec : « Who is in charge when the boss is away? | no memory matches | outside the vocabulary; **fails loudly, never guesses** ».

### L'ontologie est fermée avant d'écrire

`extract-prompt.md`, 17 lignes, reproduit ici pour l'essentiel :

```
Entity types: PERSON, ROLE, POLICY, PROCESS, DOCUMENT
Relationships: approved_by, held_by, delegates_to, part_of, references

Rules:
- Use the most complete form of each name. Add short forms as aliases.
- Put conditions (amounts, dates, time windows) in the entity description.
- Extract only facts stated in the document.
- Every edge endpoint must appear in nodes.
```

Cinq types, cinq prédicats, fixés avant la rédaction du premier document. Le README (ligne 116) est explicite : « Ontology: a closed vocabulary, fixed before writing any doc. » La dernière règle (« every edge endpoint must appear in nodes ») est ce qui rend le rejet d'arête de `build_graph.py:50` détectable plutôt que normal.

Le format de sortie, vérifié sur `extraction/refund-policy.json` :

```json
{"source_doc": "refund-policy.md",
 "nodes": [{"name": "Refund approvals", "type": "POLICY",
            "description": "Refunds over £500 need Ops Manager sign-off; under £500 any agent processes within 48h, original payment method only"}],
 "edges": [{"source": "Refund approvals", "predicate": "approved_by", "target": "Ops Manager"}],
 "aliases": [{"entity": "Refund approvals", "alias": "refunds"}]}
```

Le montant seuil est dans la `description`, pas dans une colonne. Le graphe ne raisonne pas sur 500 : il amène au modèle la phrase qui contient 500, et le modèle lit.

---

## Couche 2 : le RAG (`rag/`)

### Découpe

`rag/build_index.py:63-95`. La découpe suit les titres du document (`^#{1,3} `), pas une fenêtre fixe. `CHUNK_BUDGET = 1600` caractères, « roughly 400 tokens » (ligne 17). Une section trop longue est repliée en groupes de lignes dans le budget, sans jamais perdre son titre : chaque morceau garde le titre de sa section.

Chaque morceau conserve `file`, `section`, `start_line`, `end_line`, ce qui permet à la recherche de rouvrir le fichier et d'afficher les lignes autour du résultat.

### Le libellé fait partie de ce qui est indexé

`build_index.py:160-162` :

```python
label = f"[{rel} § {section}]"
row = (rel, section, s, e, text, "chunk")
docs.append((label + "\n" + text, row))
```

Le libellé `[fichier § section]` est **préfixé au texte avant l'embedding et avant l'indexation plein texte**. Le `rag/README.md:20-22` le dit : « The label is part of what gets embedded and keyword-indexed. » Un morceau sait donc d'où il vient, et cette provenance participe à sa propre trouvabilité.

### Deux jambes, fusionnées par rang

`rag/search.py`. Jambe mot-clé (`search.py:28-37`) : FTS5, BM25, après retrait d'une liste de 30 mots vides, les termes joints en `OR`, limite 10. Jambe sens (`search.py:40-57`) : cosinus sur tous les vecteurs, parcours séquentiel intégral, top 10.

La requête d'embedding porte le préfixe d'instruction propre à BGE (`search.py:18`) :

```python
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge query instruction
```

Détail facile à manquer et coûteux à ignorer : ce modèle attend une instruction différente côté requête et côté document. L'omettre dégrade le rappel sans rien signaler.

La fusion (`search.py:60-67`) est une **reciprocal rank fusion**, huit lignes :

```python
def fuse(legs):
    scores, found_by = {}, {}
    for name, ids in legs.items():
        for rank, rowid in enumerate(ids):
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (K + rank)
            found_by.setdefault(rowid, []).append(name)
    ranked = sorted(scores, key=scores.get, reverse=True)
    return ranked, found_by
```

`K = 60`. La RRF ne compare aucun score : elle n'additionne que des inverses de rangs. C'est précisément ce qui permet de fusionner un BM25 et un cosinus, deux échelles sans commune mesure, sans avoir à les calibrer. Et `found_by` conserve **quelle jambe a trouvé quoi**, information rendue à l'écran (`search.py:75`) : `legs: keyword+meaning`.

### Dégradation annoncée

`build_index.py:198-209` et `search.py:41-43` : sans `fastembed` installé, la jambe sens est absente et le programme l'écrit (`meaning leg off (pip install fastembed), keyword only`). Il ne se tait pas et ne fait pas semblant. Modèle utilisé par défaut : `BAAI/bge-small-en-v1.5`, 384 dimensions, 67 Mo, CPU, sans clé.

Les vecteurs sont normalisés à l'écriture puis stockés en blob `float32` (`build_index.py:204-206`), ce qui rend le cosinus à la lecture un simple produit scalaire.

### La distillation, et sa garde d'ancrage

C'est le mécanisme le plus intéressant de la couche, et le plus proche des préoccupations de Philum.

`rag/distil-prompt.md` demande, pour chaque note, le format exact :

```
source: <the note's file name>
- <a question someone would search for months later>
- <another, phrased the way they would actually ask>
summary: <one line>
rule: <the rule or resolution, if the note contains one>
quote: "<one quote from the note, copied exactly, that proves the answer>"
```

et se termine par : « **If no exact quote proves the answer, produce nothing.** »

La garde n'est pas laissée au modèle. Elle est vérifiée **deux fois, en code**, aux deux bouts de la chaîne :

- à la production, `rag/distil.py:128-133` : pas de question ou pas de citation, l'entrée est rejetée et nommée ; puis `if normalise(quote) not in normalise(body)` rejette et nomme.
- à l'indexation, `rag/build_index.py:170-175`, le même contrôle est refait contre le fichier source :

```python
# grounding check: the quote must appear in the source, word for word
if not source.is_file() or normalise(quote) not in normalise(source.read_text(encoding="utf-8")):
    dropped += 1
    print(f"dropped {path.name}: quote not found in {entry.get('source', '?')}")
    continue
```

`normalise` (`build_index.py:124-125`) est `" ".join(text.split())` : la comparaison est insensible aux espaces et aux retours à la ligne, à rien d'autre. Ni casse, ni accents, ni ponctuation ne sont neutralisés. C'est un choix strict.

Détail d'architecture qui vaut d'être copié : le format est lu et écrit par la **même fonction**, `parse_entry`, importée par `distil.py` depuis `build_index.py`. Le commentaire (`build_index.py:100-101`) dit pourquoi : « distil.py checks its own output through this, so the writer and the reader can never drift into two spellings of the format. »

### Idempotence par empreinte

`distil.py:152-159` : l'état vit dans `distilled/.state.json`, clé = chemin relatif de la note, valeur = sha256 du contenu lu. Une note inchangée est sautée. Aucune file d'attente, aucun état `pending/processing/failed` : l'empreinte suffit à savoir ce qui reste à faire.

### L'isolement du processus enfant

`distil.py:46-56` mérite d'être lu en entier, c'est une garde subtile :

```python
def child_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["MEMORY_STARTER_CHILD"] = "1"
    return env
```

Les variables `CLAUDE*` sont retirées pour que l'enfant ne se croie pas imbriqué dans la session qui l'a lancé, et un marqueur maison est posé pour que le hook de fin de session **reconnaisse son propre appel et ne le digère pas** (`digest/session_end.py:152`). Sans ce marqueur, le digest se digérerait lui-même. L'appel tourne en outre dans un dossier temporaire vide (`distil.py:76`), « so the child reads what we hand it and nothing else: no project, no settings, no hooks of ours firing inside it ».

### Le hook de rappel, borné et silencieux

`rag/recall_hook.py`. `TOP = 5`, `BUDGET = 1500` caractères au total, `PER_HIT = 280` par résultat. Les résultats sont coupés **entiers** (`block()`, ligne 46 : « Whole hits only, never a half one »). Et il ne bloque jamais : pas d'index, pas de résultat, ou n'importe quelle exception, il n'imprime rien et sort en 0.

Coût mesuré et annoncé par le `rag/README.md:95-97` : processus neuf à chaque prompt, donc chargement du modèle avant chaque question, « about 0.9 seconds with the meaning leg, under 0.1 without it ».

---

## Couche 3 : le digest (`digest/`)

Trois hooks : `SessionEnd` et `PreCompact` vers `session_end.py`, `SessionStart` vers `session_start.py`.

### Le filtrage est du code, pas un jugement de modèle

`digest/session_end.py`, en-tête : « **Code does the filtering, so nothing is judged out by mistake.** What survives is your words and the replies. Tool calls, results, file dumps, thinking and anything this file does not recognise are dropped. »

`turns()` (`session_end.py:76-112`) applique une politique de **rejet par défaut**. Sont écartés : `isSidechain` (la parole propre d'un sous-agent), tout type autre que `user`/`assistant`, les porteurs de résultat d'outil (`toolUseResult is not None`), `isMeta`, `isCompactSummary`, les blocs non textuels, les `<system-reminder>` par expression régulière, et une liste explicite de 16 préfixes d'événements écrits par le harnais et non par l'humain (`INJECTED`, lignes 30-47).

Le README (ligne 87) insiste sur la nature de ce choix : « What is kept from a session is not a dial, it is code. »

### La coupe

`filtered()` (`session_end.py:115-126`) : les 30 derniers tours, coupés à 15 000 caractères **en gardant la fin**, et la coupe est ramenée au début d'un tour entier :

```python
cut = text.find("\n\n**")  # start at a whole turn, never mid sentence
```

En dessous de 5 tours, la session n'est pas une mémoire et rien n'est produit.

### Le nommage du fichier en attente

`session_end.py:176-180`, avec son motif écrit :

```python
# the stamp matters: one long session can close twice, once before a
# compaction and once at the end, and neither half may overwrite the other
safe = re.sub(r"[^A-Za-z0-9_-]+", "-", session_id)[:64] or "session"
staged = common.PENDING / f"{safe}-{datetime.now():%Y%m%d-%H%M%S}.md"
```

### Deux modes

`session` : le texte filtré attend dans `digest/pending/`, et la session suivante le confie à un sous-agent d'arrière-plan (`session_start.py:50-63`), de sorte que l'utilisateur n'attend jamais. `headless` : un processus détaché est lancé immédiatement (`session_end.py:129-148`, avec `DETACHED_PROCESS` sous Windows et `start_new_session` ailleurs).

Dans les deux cas la promesse est la même, écrite en en-tête : « This hook returns in well under a second and always exits 0. **A session is never held up by its own memory.** » Toute exception est écrite dans `digest/log/digest.log` par `note_failure()` (`common.py:62-70`), fonction dont le contrat est de ne jamais lever elle-même.

Rien n'est perdu sur échec : `headless_run.py` en-tête, « the staged file stays where it is and the reason lands in digest/log/digest.log, so the next run can try again ».

### La voix de l'entrée

`digest/digest-prompt.md`. Structure imposée : `What happened`, `Decisions`, `Lessons`, `Facts`, `Open loops`, `For the index`. Cette dernière est explicitement destinée à la machine : « Dense, for the machine. Exact names, exact identifiers, exact paths. No style rules apply in here at all. »

Trois règles de ce prompt sont directement transposables :

- « **Grounded or dropped. Every line traces to the text below. If it is not in there it does not go in.** »
- « Say when the session was thin. A short session gets a short entry that says so. **A thin session written up as though it were complete is worse than no entry, because it looks like the whole of what happened.** »
- « What lands is permanent. The log is appended to, never edited. »

### Les réglages

`digest/config.json`, sept lignes, avec les valeurs par défaut doublées en code (`common.py:15-23`) de sorte qu'un fichier cassé n'arrête jamais le digest (`common.py:26-35`).

| Clé | Défaut | Effet |
|---|---|---|
| `mode` | `session` | `session` ou `headless` |
| `min_turns` | 5 | en dessous, la session n'est pas une mémoire |
| `max_turns` | 30 | combien de la session est lu |
| `max_chars` | 15000 | budget de caractères, la fin gardée |
| `model` | `sonnet` | quel modèle écrit l'entrée |
| `log_dir` | `daily` | dossier de destination dans les notes |
| `distil` | `true` | l'entrée alimente-t-elle l'index |

---

## Les mesures annoncées, et ce qu'elles valent

Le README publie un tableau d'évaluation (lignes 152-159) : une question à trois sauts, trois modèles, deux conditions.

| Modèle | Condition | Résultat | Sauts | Appels d'outil | Contexte lu |
|---|---|---|---|---|---|
| Fable 5 | recherche | correct | 3/3 | 6 | ~780 tokens |
| Fable 5 | graphe | correct | 3/3 | 0 | ~400 tokens |
| Sonnet | recherche | correct | 3/3 | 13 | ~1180 tokens |
| Sonnet | graphe | correct | 3/3 | 0 | ~400 tokens |
| Haiku | recherche | **faux** | 1/3 | 5 | ~660 tokens |
| Haiku | graphe | correct | 3/3 | 0 | ~400 tokens |

**Ce tableau n'est pas une comparaison propre, et il faut le dire avant d'en tirer quoi que ce soit.** Les deux conditions ne tournent pas sur le même corpus.

Vérification faite en listant les fichiers et en lisant les champs `source_doc` : les huit fichiers de `extraction/*.json` nomment `customer-support-sop.md`, `delegation-memo.md`, `incident-response.md`, `onboarding-process.md`, `org-chart.md`, `refund-policy.md`, `supplier-payments.md`, `tooling-inventory.md`, qui sont exactement les huit fichiers de `corpus/`. Le graphe est donc construit sur `corpus/`, huit documents modélisés à front matter. La condition « recherche » tourne, elle, sur `corpus-before/`, douze documents non structurés.

Or `corpus-before/` contient un piège délibéré que `corpus/` ne contient pas : `refunds-policy-2024-superseded.md`, qui énonce un seuil de 250 £ avec approbation d'un directeur, en contradiction avec la règle courante de 500 £. Le seul fichier du dépôt à contenir « 250 » est celui-là.

Le `rag/README.md:48-49` affirme pourtant : « The corpus is ../corpus-before, the same twelve messy docs the graph was built from. » C'est contredit par les `source_doc` des fichiers d'extraction. Une des deux affirmations est fausse, et ce sont les fichiers qui font foi.

**Ce qui survit à cette objection**, et qui reste solide :

- Zéro appel d'outil et zéro aller-retour dans la condition graphe. Ce n'est pas une question de corpus : le parcours a lieu avant l'invocation du modèle.
- Le coût d'injection est **fixe quelle que soit la taille du corpus** (~400 tokens), là où la lecture par recherche croît avec lui. C'est une propriété de la conception, pas une mesure.
- La latence de rappel, 2 ms, est plausible pour une requête récursive SQLite sur un graphe de cette taille.

**Ce qui ne survit pas** : la conclusion que le graphe fait mieux raisonner un petit modèle. Le Haiku de la condition recherche devait démêler deux politiques contradictoires dans douze documents ; celui de la condition graphe lisait huit documents curés d'où la contradiction avait été retirée. L'écart 1/3 contre 3/3 mesure les deux effets à la fois, et le dépôt ne fournit pas de quoi les séparer.

De même, le `rag/README.md:27` annonce « 3.1x retrieval quality over the standard build » sans définir la métrique, sans publier le jeu de test et sans livrer de harnais d'évaluation. Ce chiffre n'est pas reproductible depuis le dépôt. À ne pas citer.

---

## Ce que le dépôt ne fait pas

À relever pour ne pas prêter au dépôt des capacités qu'il n'a pas, erreur commise dans l'audit précédent.

| Absent | Constat |
|---|---|
| Mise à jour incrémentale du graphe | `build_graph.py:22` supprime la base et la reconstruit intégralement |
| Suppression, versionnement, historique | aucune colonne de date, aucun `deleted_at`, aucune trace de révision |
| Multi-utilisateur, isolement des données | mono-utilisateur, un fichier SQLite local, aucune notion de propriétaire |
| Index sur les tables du graphe | aucun `CREATE INDEX` dans `schema.sql` |
| Index vectoriel | `search.py:45-56` parcourt tous les vecteurs en Python à chaque requête |
| Résolution d'entités approchée | strictement le nom normalisé et les alias déclarés, aucun flou |
| Extraction automatisée | `extract-prompt.md` est un prompt à passer à la main ; aucun script ne l'exécute |
| Tests | aucun fichier de test dans le dépôt |
| Conflits, contradictions entre documents | aucun mécanisme ; deux documents contradictoires produisent deux arêtes coexistantes |

Le dernier point est le plus important si l'on envisage de transposer : le graphe n'a **aucune notion de fraîcheur ni de préséance**. C'est justement le piège que `corpus-before/` tend à la recherche, et que la modélisation manuelle a retiré du corpus du graphe plutôt que de le résoudre.

---

_Relevé le 2026-08-30, par clonage du dépôt au commit `496a6e9` et lecture de la totalité de ses 53 fichiers. Chiffres externes via l'API GitHub le même jour._
