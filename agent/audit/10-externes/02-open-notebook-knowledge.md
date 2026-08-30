# Audit 02. open-notebook → Philum : gestion des connaissances

> [open-notebook](https://github.com/lfnovo/open-notebook) : Alternative self-hébergée à NotebookLM. Stack : FastAPI, SurrealDB, LangGraph, Next.js 16 avec React 19. MIT, créé en octobre 2024.

> **Vérifié le 2026-08-30.** Le dépôt et la stack sont confirmés dans `pyproject.toml` et `frontend/package.json`. Le compte d'étoiles annoncé était faux : **37 932**, pas 27k. Le « 27k » de la première rédaction était celui de book-to-skill, recopié ici.

---

## 1. Ce qu'open-notebook fait

### Architecture centrale

```
Source (PDF, Web, YouTube, Text) → Parseur content-type-aware
  → Source Insight (extraction structurée via LLM)
  → Chunking → Embeddings (mean-pooled par chunk)
  → Indexation (SurrealDB : notes + vecteurs)
  → Recherche dual : vecteur → texte (fallback automatique)
  → LLM Citation : [source:abc123] dans les réponses
```

### Modèle de données

```
Source
├── id, name, content_type, location
├── SourceInsight[] (extraction LLM structurée)
│   ├── name, content, insight_type, source_id
├── SourceEmbedding[] (1 vecteur par chunk)
│   ├── embedding (768d), chunk_text, source_id
└── Link[] (relations entre sources)

Notebook
├── id, name
├── Source[] (arêtes : même source dans plusieurs notebooks)
├── NotebookInsight[]
└── NotebookEmbedding[]
```

### Fichiers clés

| Fichier | Rôle |
|---|---|
| `open_notebook/domain/notebook.py` | Modèle de données (Source, Note, SourceInsight, SourceEmbedding) |
| `open_notebook/domain/db.py` | Interactions DB (CRUD, liens, vecteurs) |
| `open_notebook/utils/chunking.py` | Chunking content-type-aware |
| `open_notebook/utils/embedding.py` | Mean pooling, batch embedding |
| `open_notebook/graphs/ask.py` | Pipeline RAG 3 étapes |
| `open_notebook/graphs/research.py` | Recherche dual vecteur→texte |
| `commands/embedding_commands.py` | File d'attente async pour l'indexation |
| `prompts/ask/*.jinja` | Prompts de citation |

---

## 2. Patterns pertinents pour Philum

### Pattern 1 : Citations structurées `[source:uuid]`

**Concept** : Les réponses du LLM contiennent des références vers les sources via des IDs `[source:abc123]`. Le frontend les convertit en liens cliquables.

**Pipeline** :
1. Les sources ont un `Source.id` (SurrealDB UUID)
2. Lors du RAG, le contexte injecté contient `[source:{id}]` pour chaque chunk
3. Le LLM apprend à citer ces IDs dans ses réponses
4. Le frontend parse `[source:...]` et affiche des liens cliquables

**Application Philum** :
- Les sources Philum ont déjà un `source.id` (UUID)
- L'agent MCP pourrait injecter `[source:{id}]` dans le contexte
- Le frontend pourrait parser ces IDs et afficher des liens

### Pattern 2 : Chunking content-type-aware

**Concept** : Le chunking dépend du type de contenu, pas d'une taille fixe.

```python
def chunk_source(source):
    if source.content_type == "html":
        chunks = chunk_by_headers(source.content)  # h1, h2, h3
    elif source.content_type == "markdown":
        chunks = chunk_by_headers(source.content)  # #, ##, ###
    else:
        chunks = chunk_recursive(source.content, ["\n\n", "\n", "."])  # recursive character splitter
    return chunks
```

**Application Philum** :
- Les sources Philum sont de type `Article` (texte brut, markdown, HTML)
- Le chunking pourrait détecter les headers HTML/markdown AVANT le LLM
- Réduit le coût de l'extraction (moins de tokens à traiter)

### Pattern 3 : Recherche dual vecteur→texte

**Concept** : La recherche essaie d'abord la similarité cosinus. Si trop peu de résultats (< seuil), elle fallback sur la recherche texte.

```python
async def research(query):
    # Étape 1 : recherche vectorielle
    vector_results = await vector_search(query, top_k=10)
    if len(vector_results) >= MIN_RESULTS:
        return vector_results
    
    # Étape 2 : fallback texte
    text_results = await text_search(query, top_k=10)
    return merge_dedupe(vector_results, text_results)
```

**Application Philum : le seul gain net de cette fiche.** La recherche sémantique existe en REST (`api/v1/endpoints/excerpt_search.py`), la recherche texte existe en MCP (`mcp_server/tools_write.py:1380`, `search_my_excerpts`, ILIKE en `:1399`). L'agent, qui passe par le MCP, n'a donc accès qu'à la recherche la moins capable des deux : il ne retrouve un extrait que s'il en devine les mots exacts. Faire tomber `search_my_excerpts` sur le chemin sémantique quand le ILIKE ne rend rien lui ouvre ce que le REST sait déjà faire, sans nouvelle infrastructure.

### Pattern 4 : Command queue async

**Concept** : Le traitement lourd (embedding, extraction) est découpé en tâches stockées en DB avec état (`pending`, `processing`, `completed`, `failed`).

```python
class Command:
    id: str
    command: str  # "embed_source", "create_insight", etc.
    status: str   # pending, processing, completed, failed
    details: dict
    created_at: datetime
```

**Application Philum : à écarter.** L'absence de file n'est pas un oubli. `services/excerpt_indexing.py:1-11` dit que l'indexation est idempotente et se rejoue sans dommage, précisément pour n'avoir aucune file à tenir. Une file d'attente avec états ajoute une table, un worker, une reprise sur panne et un endpoint de statut, pour remplacer une propriété qui rend tout cela inutile. À rouvrir seulement si une indexation perdue est mesurée en production, pas avant.

### Pattern 5 : Embeddings mean-pooled

**Concept** : Un document long est découpé en chunks, chaque chunk a un vecteur. La recherche retourne les chunks les plus pertinents.

```python
def mean_pool(vectors: list[list[float]]) -> list[float]:
    """Moyenne de tous les vecteurs → 1 vecteur par document."""
    return [sum(col)/len(col) for col in zip(*vectors)]
```

**Application Philum : aucune, et c'est une bonne nouvelle.** La première rédaction affirmait qu'un long article donnait un seul vecteur moyenné sur tout le texte. C'est faux : `services/embeddings.py:52-66` compose titre, contexte et texte d'**un extrait**, et `services/excerpt_indexing.py:58-100` pose un vecteur par extrait. Philum est donc déjà au grain fin que le mean pooling cherche à approcher. L'appliquer ici serait une régression : moyenner des vecteurs dilue ce que chacun distinguait.

---

## 3. Ce qui n'est PAS pertinent pour Philum

| Pattern open-notebook | Pourquoi pas |
|---|---|
| SurrealDB | Philum utilise PostgreSQL + pgvector : pas de changement |
| LangGraph (workflow stateful) | Philum a déjà un agent loop simple : pas besoin de state machine |
| Notebook concept | Philum n'a pas de "carnet de notes", ses entités sont les sources |
| Transformations réutilisables (prompt templates) | Philum a déjà les outils MCP : pas de besoin |
| Provider abstraction (Esperanto) | Philum gère déjà 9 providers proprement |

---

## 4. Plan d'implémentation recommandé

### Phase A : Citations structurées (2 jours)

| # | Tâche | Fichiers Philum |
|---|---|---|
| A1 | Ajouter `[source:{id}]` dans le contexte injecté par les outils MCP | `tools_write.py` |
| A2 | Modifier les prompts de l'agent pour apprendre à citer `[source:uuid]` | `agent.py` (system prompt) |
| A3 | Parser `[source:...]` dans le frontend et afficher des liens | `AgentMarkdown.svelte` |
| A4 | Ajouter un tooltip ou popover avec les métadonnées de la source | `AgentMarkdown.svelte` |

### Phase B : Recherche dual (1 jour)

| # | Tâche | Fichiers Philum |
|---|---|---|
| B1 | Ajouter une option `fallback=true` au tool `search_excerpts` | `tools_write.py` |
| B2 | Si vectoriel retourne < 3 résultats, essayer ILIKE automatiquement | `excerpt_search.py` |
| B3 | Fusionner et dédupliquer les résultats | `excerpt_search.py` |

### Phase C : file d'indexation : abandonnée

Voir le patron 4 : l'indexation est idempotente par conception, la file remplacerait une propriété qui la rend inutile.

**Ordre révisé : B avant A.** La recherche duale est petite, sans surface d'API nouvelle, et corrige une asymétrie que l'agent subit à chaque tour. Les citations demandent une convention de format, un prompt qui l'enseigne, un parseur côté front et un rendu : c'est le double du travail pour un gain d'affichage, à décider une fois B en production.

---

## 5. Patterns à copier directement

1. **Repli vecteur puis texte** : un `if len(results) < N` et la requête sémantique déjà écrite en REST
2. **Citations `[source:uuid]`** : format standard, mais le coût est côté front et côté prompt, pas côté format

Le mean pooling, donné ici en troisième, est retiré : Philum embarque déjà un vecteur par extrait, moyenner serait perdre de la précision.

---

## 6. Risques

| Risque | Mitigation |
|---|---|
| Le LLM ne cite pas toujours les sources | Enrichir le system prompt avec des exemples de citation |
| Le parsing `[source:...]` est fragile | Utiliser une regex robuste `\[[\w:-]+\]` |
| Le chunking par headers peut créer des sections trop courtes | Seuil minimum de 200 caractères par chunk |

---

_Audit réalisé le 2026-08-30. Source : https://github.com/lfnovo/open-notebook_
