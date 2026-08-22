# 2026-08-22 — Workspace Philum : audit valeur, seed manquant, proposition multi-agents

> **Objet** : le workspace `/dashboard/workspace` a été livré en PR #532 comme un
> éditeur générique de fichiers Markdown adossé aux endpoints `/agent/workspace/*`.
> Cet audit répond à trois questions posées par l'utilisateur :
> 1. À quoi sert-il vraiment ? Quelle est sa valeur pour un créateur ?
> 2. Y a-t-il des fichiers de config d'agent qui devraient exister d'origine ?
> 3. Le workspace peut-il devenir un espace de choix / personnalisation d'agents
>    spécialisés (recherche web, construction de fiche, bibliographie, extraits) ?
>
> **Verdict** : la valeur actuelle est **réelle mais invisible**. Le seed complet existe
> déjà côté serveur (18 fichiers ICM « créateur-de-fiches »), mais l'UI le présente
> comme un arbre de fichiers Markdown sans contexte, sans hiérarchie de lecture, sans
> agents nommés. **Trois manques à combler** : (a) rendre visible ce que chaque fichier
> fait dans la conversation avec l'agent, (b) introduire la notion **d'agent** comme
> unité éditoriale au-dessus du fichier, (c) rendre les templates copiables au clic
> plutôt qu'à la main.

---

## 0. Conformité à ICM (référence `RinDig/icm-architect`, vérifiée 2026-08-22)

Toute proposition de cette étude respecte les invariants et le vocabulaire ICM :

- **Layer 0 — Routing** : `AGENTS.md` (identité + folder map + triggers).
- **Layer 1 — Routing** : `CONTEXT.md` racine (routing task-type → stage).
- **Layer 2 — Control point** : `stages/*/CONTEXT.md` (contrat d'étape : inputs,
  process, outputs, human checks).
- **Layer 3 — Factory (stable)** : `shared/`, `_core/templates/`, `_core/audit/`
  (rules, voice, schemas, templates ; stables entre runs).
- **Layer 4 — Product (per-run)** : `runs/<slug>/stages/0N-*/output/` (nouveaux
  à chaque fiche).

**Règles de nommage** appliquées ci-dessous :

- Kebab-case pour les fichiers machine-facing (`style-redactionnel.md`, pas
  `VoixCreateur.md`).
- Préfixe `_` pour les dossiers meta (« about the workspace, not of the work »)
  → `_core/` respecté.
- Numérotation `NN-nom` pour les folders quand la séquence importe → `stages/01-brief/`.
- **Pas de vocabulaire marketing** : « Voix éditoriale » ou « Règles de la
  maison » sont proscrits. Les noms doivent rester **déclaratifs et auditables**.
- **Un fait, un endroit** : pas de duplication. Le nom du fichier est le titre
  affiché dans l'UI ; l'UI ne réinvente pas de libellé.

Ces règles orientent la §3.1 et la §5.

---

## 1. Ce que le workspace fait aujourd'hui (état vérifié 2026-08-22)

### 1.1 Le seed embarqué

Dossier `apps/backend/app/agent_workspace_seed/` (18 fichiers) inséré au premier accès
d'un créateur via `assurer_workspace()` :

```
AGENTS.md                             (point d'entrée + folder map + triggers)
CONTEXT.md                            (routing task-type → stage)
shared/
  ├── philum-mcp.md                   (inventaire des tools MCP + auth)
  ├── principes-editoriaux.md         (5 propriétés d'une bonne fiche)
  ├── garde-fous.md                   (ce que l'agent refuse)
  ├── style-redactionnel.md                (style, longueurs, typographie)
  └── pieges-vecus.md                 (erreurs passées)
stages/
  ├── 01-brief/CONTEXT.md
  ├── 02-sources-collectees/CONTEXT.md
  ├── 03-annotations/CONTEXT.md
  ├── 04-extraits/CONTEXT.md + references/verification-doi.md
  ├── 05-connexions/CONTEXT.md
  ├── 06-relecture/CONTEXT.md
  └── 07-publication/CONTEXT.md
_core/
  ├── templates/{brief,source,extrait}.md
  └── audit/audit_fiche.py
```

### 1.2 Ce que l'agent en fait à chaque tour

Dans `agent.py:_priming_workspace()`, à l'ouverture d'une conversation :

```python
result = await db.execute(
    select(WorkspaceFile).where(
        WorkspaceFile.creator_id == creator_id,
        WorkspaceFile.path.startswith("shared/"),   # ⚠ shared/ seulement
    ).order_by(WorkspaceFile.path)
)
```

**Seul `shared/` est injecté dans le prompt système**, plafonné à 40 000 caractères.
Les `stages/*/CONTEXT.md`, `_core/templates/`, `AGENTS.md`, `CONTEXT.md` ne sont **jamais
lus par l'agent au démarrage** : ils ne servent que si le modèle appelle explicitement
`fs_read(path)` — ce qu'il fait rarement, faute d'y être invité.

### 1.3 La valeur réelle actuelle

- **Voix éditoriale imposée** (`style-redactionnel.md` : pas de cadratins, français, longueurs).
- **Garde-fous rappelés** (`garde-fous.md` : refus des extraits inventés).
- **Principes éditoriaux** (`principes-editoriaux.md` : 5 propriétés d'une bonne fiche).
- **Inventaire MCP** (`philum-mcp.md` : quand utiliser quel outil).

**Ce qui n'apparaît pas dans le prompt et n'est donc pas activé** : les 7 stages du
pipeline de fiche, les templates de brief/source/extrait, le folder map, le routing
task-type.

## 2. Diagnostic : trois manques structurels

### 2.1 Le workspace est présenté comme un système de fichiers Markdown générique

L'UI livrée en PR #532 est un arbre + un éditeur. C'est correct pour la config avancée,
mais **le créateur qui ouvre `/dashboard/workspace` pour la première fois ne comprend
pas ce qu'il regarde** :

- Quel fichier est lu quand ?
- Que se passe-t-il si je modifie `style-redactionnel.md` vs `philum-mcp.md` ?
- Pourquoi 18 fichiers ? Que se passerait-il si j'en supprimais 15 ?

Une bonne UI de config met **le sens avant la structure**. Le sens ici : « voici les
règles que l'agent suit ; vous pouvez les modifier ou les remplacer ».

### 2.2 L'agent ignore 60 % du seed au démarrage

`_priming_workspace()` charge `shared/` mais rien d'autre. Consequences :

- Le **pipeline en 7 stages** (`stages/*`) n'est jamais évoqué par l'agent qui parle
  au créateur. Le créateur ne bénéficie pas de la méthodologie séquentielle prévue.
- Les **templates** (`_core/templates/`) ne sont pas connus. L'agent ne dit jamais
  « je vais partir du template brief.md », il improvise à chaque tour.
- `AGENTS.md` et `CONTEXT.md`, qui devraient orienter l'agent vers le bon fichier
  selon la demande, ne sont jamais lus proactivement.

C'est un décalage entre l'intention (le seed ICM est riche et bien pensé) et
l'exécution (l'agent n'en voit que le quart).

### 2.3 Il n'y a qu'un agent, monolithique

Aujourd'hui, `/dashboard/chat` = un agent, avec un prompt système fixe, tous les outils
Philum + MCP + web, et le contexte `shared/*.md`. Pour un créateur qui veut :

- **Chercher des sources sur un sujet** → même agent, tous les outils, contexte fiche.
- **Vérifier un DOI ou une date** → même agent, même contexte.
- **Rédiger l'annotation d'une source** → même agent, même contexte.
- **Faire relire une fiche** → même agent, même contexte.

Chaque tour paie le coût de charger un contexte de ~40k tokens qui parle de 5 tâches
distinctes. Les modèles sont bons, mais un agent focalisé sur une tâche fait moins
d'erreurs, coûte moins de tokens, et parle plus clairement.

## 3. Proposition : refonte en trois strates

### 3.1 Strate 1 — Fichiers de configuration (déjà existants, à rendre visibles)

**Contrainte** : les noms doivent respecter la méthodologie ICM
(`RinDig/icm-architect`, référence vérifiée 2026-08-22) — kebab-case, sobre,
déclaratif, jamais marketing. La règle du repo : « avoid marketing language ;
favor declarative, auditable names » et « one home per fact ; a link beats a copy ».

Le seed actuel (`shared/style-redactionnel.md`, `shared/garde-fous.md`, etc.) est déjà
en français kebab-case. L'UI ne doit **pas les renommer** ; elle doit les
**afficher tels quels** avec une phrase de contrat pour chacun. Le nom du fichier
est le nom dans l'UI. Une fois cette règle posée, la sobriété est mécanique :
c'est l'auteur du fichier qui l'a nommé, pas la couche présentation.

| Fichier (nom = titre UI) | Une phrase de contrat |
|---|---|
| `shared/style-redactionnel.md` | Style, longueurs, typographie de tout texte que l'agent écrit. |
| `shared/principes-editoriaux.md` | Cinq propriétés d'une fiche que l'agent vise. |
| `shared/garde-fous.md` | Actions que l'agent refuse d'exécuter. |
| `shared/philum-mcp.md` | Référence des outils MCP Philum et de leur usage. |
| `shared/pieges-vecus.md` | Erreurs passées à ne pas répéter. |
| `_core/templates/brief.md` | Squelette de brief à copier pour démarrer une fiche. |
| `_core/templates/source.md` | Squelette d'une entrée source. |
| `_core/templates/extrait.md` | Squelette d'un extrait vérifié. |
| `stages/01-brief/CONTEXT.md` … `stages/07-publication/CONTEXT.md` | Contrat d'entrée / process / sortie d'une étape du pipeline. |

**Organisation UI** : trois sections empilées, chacune n'est qu'un regroupement
visuel (rien n'est renommé, rien n'est déplacé) :

```
Références (L3 factory)
  shared/style-redactionnel.md          — Style, longueurs, typographie…
  shared/principes-editoriaux.md   — Cinq propriétés d'une fiche…
  shared/garde-fous.md             — Actions que l'agent refuse…
  shared/philum-mcp.md             — Référence des outils MCP…
  shared/pieges-vecus.md           — Erreurs passées…

Modèles (L3 factory, copiables)
  _core/templates/brief.md         — Squelette de brief…
  _core/templates/source.md        — Squelette d'une source…
  _core/templates/extrait.md       — Squelette d'un extrait…

Pipeline (L2 contrats d'étape)
  stages/01-brief/CONTEXT.md       — Contrat de l'étape 01…
  … (jusqu'à 07-publication)
```

Les libellés « Références », « Modèles », « Pipeline » suivent le vocabulaire
ICM (L3 factory / L3 factory / L2) — sobres, catégoriels. Chaque ligne est un
**chemin** suivi de sa **phrase de contrat** (extraite du premier paragraphe du
fichier ou d'un frontmatter `contract:`). L'utilisateur voit tout de suite ce
que chaque fichier fait, sans renommage inventé.

### 3.2 Strate 2 — Agents nommés (nouveau concept à introduire)

Introduire un objet `Agent` en base : un enregistrement par créateur qui référence
un **prompt système**, une **liste d'outils autorisés**, un **contexte** (fichiers du
workspace à injecter), et un **modèle recommandé**.

**Agents à seeder par défaut** :

| Agent | Rôle | Outils | Contexte |
|---|---|---|---|
| **Assistant général** | Répond à tout, celui qu'on a aujourd'hui | Tous | `shared/*` |
| **Rechercheur** | Trouve des sources sur un sujet, vérifie qu'elles existent | `web_search`, `fetch_url`, `find_cards_citing`, `get_url_metadata`, `import_from_content_url` | `shared/philum-mcp.md`, `stages/02-sources-collectees/*` |
| **Bibliographe** | Ajoute, valide, enrichit les sources d'une fiche | `add_source`, `update_source`, `add_sources_batch`, `parse_biblio`, `list_sources` | `shared/philum-mcp.md`, `shared/style-redactionnel.md`, `stages/02-sources-collectees/*`, `_core/templates/source.md` |
| **Extracteur** | Identifie, verbatim, positionne les extraits | `suggest_excerpts`, `add_excerpt`, `verify_excerpts`, `update_excerpt`, `annotate_excerpt` | `shared/garde-fous.md` (bloc « Sur les extraits »), `stages/04-extraits/*`, `_core/templates/extrait.md` |
| **Rédacteur de fiche** | Écrit brief, description, connexions | `create_card`, `update_card`, `set_content_text` | `shared/style-redactionnel.md`, `shared/principes-editoriaux.md`, `stages/01-brief/CONTEXT.md`, `_core/templates/brief.md` |
| **Relecteur** | Audit final avant publication | `get_card`, `list_sources`, `search_my_excerpts`, `verify_excerpts` (lecture seule) | `shared/principes-editoriaux.md`, `stages/06-relecture/CONTEXT.md` |
| **Publicateur** | Valide, publie, atteste | `publish_card`, `create_content_attestation`, `archive_sources` | `stages/07-publication/CONTEXT.md`, `shared/garde-fous.md` |

**Effets concrets** :

- Un agent avec 5 outils au lieu de 40 fait moins d'erreurs de choix d'outil (le bug
  Gemini du 2026-08-22 vient partiellement de ça).
- Le contexte injecté par tour tombe de ~40k à 3-8k tokens → coût inference divisé
  par 5-10.
- Le créateur qui dit « je veux ajouter des sources » choisit **Bibliographe** dans
  un sélecteur, l'agent démarre focalisé, la confusion diminue.

### 3.3 Strate 3 — Sous-agents (dispatching interne)

Un agent « chef d'orchestre » qui reste **Assistant général** mais qui, sur demande
complexe (« fais-moi une fiche sur les thrips »), délègue à ses sous-agents en séquence :

1. **Rédacteur de fiche** crée le brouillon.
2. **Rechercheur** propose 5-10 sources candidates.
3. **Bibliographe** ajoute celles validées par le créateur.
4. **Extracteur** propose des verbatim pour chaque source pivot.
5. **Relecteur** produit un verdict.

C'est le pipeline `stages/` mais orchestré par l'agent, avec approbation humaine
entre chaque étape (déjà en place via `SENSITIVE_TOOLS`). Techniquement, chaque
sous-agent est une conversation courte scopée, dont le résultat est injecté dans
le contexte de l'agent parent.

**Décision** : cette strate est prématurée. Livrer d'abord les strates 1 et 2, mesurer
l'usage sur 3-4 semaines, puis décider si la 3 apporte quelque chose que « lancer
manuellement l'agent Bibliographe puis l'agent Extracteur » ne fait pas déjà mieux.

## 3.4 Formats de fichier : Markdown, YAML, JSON — quand chacun

**Principe ICM** (invariant #8) : « Plain text, linkable, queryable » →
**Markdown + YAML frontmatter**. C'est le socle. Le JSON n'apparaît pas dans
la référence ICM ; l'HTML jamais. Trois raisons pratiques d'en écarter certains :

- **JSON** : plus verbeux que YAML, moins lisible par un humain, pas d'ancres
  ni de commentaires, aucun gain fonctionnel sur YAML pour de la config.
  À réserver à l'inter-op API (payloads).
- **HTML** : hors sujet. Un fichier de config LLM ne rend rien à un navigateur.

**Ce qui reste en Markdown pur** (le contenu que le LLM ingère dans son contexte) :

- `shared/style-redactionnel.md`, `principes-editoriaux.md`, `garde-fous.md`,
  `pieges-vecus.md`, `philum-mcp.md` : prose lue par l'agent au tour 0.
- `stages/*/CONTEXT.md` : contrat d'étape lu par l'agent quand il exécute cette
  étape.
- `_core/templates/*.md` : squelettes copiés dans les runs.

Le Markdown est le format le plus efficace en tokens pour du texte lu par un LLM :
pas de bruit syntaxique, structure sémantique via `#` et listes qui améliore
mesurablement la compréhension du modèle.

**Ce qui gagne en frontmatter YAML dans un fichier Markdown** (métadonnées
machine-parseables sans casser la lecture humaine ni la lecture LLM) :

```markdown
---
contract: "Style, longueurs, typographie de tout texte que l'agent écrit."
layer: L3
usedBy: [assistant, redacteur, bibliographe, extracteur, relecteur]
lastVerified: 2026-08-22
---
# La voix : ce qu'un texte Philum sonne
...
```

Effets :

- **UI** : la phrase de contrat affichée sous chaque fichier ne vient plus du
  premier paragraphe (fragile), mais du champ `contract:` (contrat explicite).
- **Rétro-index** : la liste « Utilisé par » de chaque fichier de `shared/` est
  déduite du `usedBy:` des agents, ou du sens inverse : chaque agent liste ses
  `context_paths`, on inverse en base pour afficher.
- **Audit** : `lastVerified:` permet de flagger les fichiers non revus depuis N
  mois, sans quoi le seed vieillit silencieusement.
- **Sha du contenu** vs **layer déclaré** : détecte les fichiers copiés qui ont
  divergé du seed ou été rangés dans la mauvaise strate.

Le frontmatter YAML est déjà supporté par ICM (`references/core.md`) — c'est le
mode canonique. Aucune innovation, on s'en sert enfin.

**Ce qui gagne en YAML pur** (config structurée, jamais ingérée verbatim par le
LLM — parsée par le backend puis composée dans le prompt) :

- **Définitions d'agent** (§3.2) : un fichier par agent sous `agents/*.yaml`.
  Un YAML est plus lisible qu'un enregistrement en base pour ce cas d'usage
  (édition à la main possible, versionnable par run, testable en isolation),
  et le backend le charge une fois, valide contre un schéma Pydantic, met en
  cache. Cela évite aussi une migration Alembic dédiée : `agent_definitions`
  peut rester **fichier-first**, en base seulement quand un créateur clone
  un builtin pour le personnaliser (le fichier YAML seedé sert de default,
  la ligne DB vit uniquement en cas d'override).

Exemple `agents/bibliographe.yaml` :

```yaml
slug: bibliographe
name: Bibliographe
contract: "Ajoute, valide et enrichit les sources d'une fiche."
layer: L2                              # agent = control point du workflow
model:
  hint: gemini-3.6-flash               # plus léger qu'un flagship
  fallback: [claude-sonnet-4.6, gpt-4o-mini]
allowed_tools:
  - add_source
  - update_source
  - add_sources_batch
  - parse_biblio
  - list_sources
  - get_source
  - fetch_url                          # pour vérifier une URL avant d'ajouter
context_paths:
  - shared/philum-mcp.md
  - shared/style-redactionnel.md
  - stages/02-sources-collectees/CONTEXT.md
  - _core/templates/source.md
system_prompt: |
  Tu es le Bibliographe Philum. Ton seul rôle est d'ajouter et de valider
  les sources d'une fiche. Ne crée pas d'extraits, ne publie pas la fiche.
  Vérifie chaque URL avant l'ajout via fetch_url. Refuse d'inventer un DOI,
  une date, un auteur : absence > invention.
guardrails:
  refuse_if:
    - "add_source without prior fetch_url on the same URL in this turn"
```

Effets :

- **Fiabilité** : le schéma validé écarte les typos (outil inconnu, path
  workspace invalide) au chargement, pas à l'exécution.
- **Amélioration de réponse** : `allowed_tools` étroit + `context_paths` étroit
  = fenêtre de contexte réduite = moins d'hallucinations d'outils (le bug
  Gemini du 2026-08-22 en est un cas), coût inference divisé.
- **Agnosticité provider** : `model.hint` + `model.fallback` séparent le rôle
  du modèle ; changer de provider en cours d'année ne casse aucun agent.
- **Versionnable** : un agent est un fichier lu par les humains, review-able
  en PR, testable en isolation.

**Ce qui gagne en JSON** : rien pour la config Philum. Cas d'usage restreints :

- Payloads d'appel MCP / OpenAPI : déjà en JSON par contrat externe.
- Export d'un agent pour partage entre créateurs : YAML → JSON à l'export si
  un client tiers l'exige, mais Philum reste YAML en interne.

**Récapitulatif** :

| Type de contenu | Format | Pourquoi |
|---|---|---|
| Prose lue par le LLM (prompt, principes, voix, garde-fous) | Markdown | Densité tokens, structure sémantique |
| Métadonnées d'un fichier (contract, layer, usedBy) | Frontmatter YAML | Machine-parseable sans casser la lecture |
| Définition d'agent (outils, contexte, modèle, prompt) | YAML pur | Config structurée, validée, versionnable |
| Contrat de stage (inputs, process, outputs, human checks) | Markdown + frontmatter YAML | Contrat lu par le LLM + méta indexable |
| Squelette copié dans un run | Markdown | Édition humaine directe |
| Payload API externe (MCP, provider LLM) | JSON | Contrat externe imposé |
| Rendu visuel | HTML | Non applicable ici |

**Conséquence pratique pour la Phase 1** : ajouter le frontmatter YAML aux 12
fichiers du seed existant (2 champs minimum : `contract`, `layer`). Le backend
parse le frontmatter, l'expose au frontend qui affiche la phrase de contrat sous
chaque fichier. Effort : 2-3 h. Aucun changement de schéma DB.

---

## 4. Backend : ce qu'il faut changer

### 4.1 Modèle `AgentDefinition`

Nouveau modèle (créateur-scopé), aliasé sur le workspace pour la persistance :

```python
class AgentDefinition(Base):
    __tablename__ = "agent_definitions"
    id: UUID
    creator_id: UUID
    slug: str                    # "assistant", "rechercheur", "bibliographe"...
    name: str                    # "Assistant général"
    description: str
    system_prompt: str           # peut référencer des fichiers workspace via {{shared/style-redactionnel.md}}
    allowed_tools: list[str]     # ["web_search", "fetch_url", ...]
    context_paths: list[str]     # ["shared/style-redactionnel.md", "stages/02-*/CONTEXT.md"]
    default_model_hint: str | None
    is_builtin: bool             # seed non modifiable, remplaçable
    is_active: bool
```

Seed initial : les 7 agents de la table §3.2. `is_builtin=True` empêche la suppression
mais l'utilisateur peut cloner un builtin (`fork_agent`) pour le personnaliser.

### 4.2 Modification de `boucle()`

Signature actuelle :

```python
async def boucle(db, user, provider, messages, emit, approuver, *, transport=None,
                 registre=None, modele=None): ...
```

Ajout d'un paramètre `agent_def: AgentDefinition | None = None`. Si fourni :

- Le prompt système = `agent_def.system_prompt` interpolé (`{{path}}` remplacé par le
  contenu du fichier workspace).
- Le registre est filtré à `agent_def.allowed_tools`.
- Le contexte injecté = `agent_def.context_paths` au lieu de `shared/*`.

Si `agent_def is None`, comportement actuel préservé (rétrocompat).

### 4.3 Endpoints

- `GET /agent/definitions` : liste des agents (builtin + créateur).
- `POST /agent/definitions` : créer / cloner un agent.
- `PATCH /agent/definitions/{id}` : éditer (refusé sur builtin, autorisé sur clones).
- `DELETE /agent/definitions/{id}` : soft-delete (jamais sur builtin).
- Endpoint chat existant `POST /agent/chat` : nouveau champ `agent_slug` optionnel.

### 4.4 Migration

- Nouvelle table `agent_definitions`.
- Seed idempotent : au premier accès d'un créateur, insérer les 7 builtins s'ils
  n'existent pas.
- `agent_sessions` gagne une colonne `agent_slug` nullable → chaque session est
  associée à un agent (ou `null` = assistant général par défaut, comportement actuel).

## 5. Frontend : ce qu'il faut changer

### 5.1 Page `/dashboard/workspace` refactorée

Deux onglets en tête :

**Onglet « Agents »** (nouveau, par défaut)

- Liste des 7 agents avec badge « Livré avec Philum » ou « Personnalisé ».
- Chaque carte montre : nom, description, nombre d'outils, contexte injecté (résumé).
- Boutons : « Cloner », « Éditer » (sur clones seulement), « Ouvrir une conversation
  avec cet agent » (raccourci vers `/dashboard/chat?agent=rechercheur`).
- Bouton « Nouvel agent » : formulaire nom + description + prompt + outils cochés
  + fichiers de contexte cochés.

**Onglet « Fichiers »** (l'actuel, avancé)

- Arbre + éditeur inchangés.
- Header pédagogique : « Ces fichiers configurent le comportement de vos agents.
  Modifier `style-redactionnel.md` change la manière d'écrire de tous les agents qui
  l'incluent dans leur contexte. »
- Chaque fichier de `shared/` affiche : « Utilisé par : Assistant général,
  Bibliographe, Relecteur » (déduit des `context_paths` des agents).

### 5.2 Page `/dashboard/chat` : sélecteur d'agent

Sous les sélecteurs clé/modèle existants, ajouter un sélecteur **Agent** avec les
7 builtins + clones du créateur. Défaut : « Assistant général ». Changer d'agent en
cours de conversation démarre une nouvelle session (les contextes sont incompatibles).

Le nom de l'agent apparaît dans l'en-tête de la conversation à côté du titre.

## 6. Feuille de route recommandée

**Phase 1 (S)** — Rendre visible ce qui existe déjà :
- Onglet « Fichiers » avec les groupes par fonction (§3.1), sans changer le backend.
- Header pédagogique + descriptions par fichier.
- Effort : 1-2 j frontend, 0 backend.

**Phase 2 (M)** — Introduire les agents nommés :
- Modèle `AgentDefinition` + migration + seed 7 builtins.
- Modification de `boucle()` pour filtrer registre et contexte selon l'agent.
- Endpoints CRUD + sélecteur frontend.
- Effort : 4-6 j full-stack.

**Phase 3 (M-L, différée)** — Personnalisation :
- Cloner et éditer des agents.
- Interpolation `{{path}}` dans les prompts système.
- Effort : 3-4 j.

**Phase 4 (à évaluer)** — Sous-agents et orchestration :
- Décider seulement après avoir mesuré l'usage réel des agents de la phase 2.
- Ne pas construire une architecture d'orchestration avant d'avoir la preuve que
  le pipeline manuel « je change d'agent à chaque étape » est insuffisant.

## 7. Ce qu'il ne faut pas faire

- **Créer un builder no-code d'agents avant d'avoir 7 agents utilisés en prod.**
  Le builder est un problème d'UX qu'on résout après le problème produit.
- **Empiler des agents sans mesurer.** Chaque agent qu'on ajoute est un chemin de
  plus à documenter, tester, maintenir. Sept sont probablement 2 de trop.
- **Faire porter au workspace la logique d'appel des sous-agents.** Le workspace
  reste un espace de configuration ; l'orchestration vit dans `agent.py`.
- **Remplacer l'assistant général.** Il reste le point d'entrée par défaut pour tout
  créateur qui ne veut pas choisir. Les agents spécialisés sont des raccourcis, pas
  des remplacements.

## 8. Ce que cet audit change côté priorité produit

Aujourd'hui la page `/dashboard/workspace` est livrée mais **sous-utilisée par le seed
lui-même** (60 % du contenu n'atteint jamais le prompt de l'agent). La Phase 1
ci-dessus est le minimum viable pour que la valeur du seed devienne perceptible ;
la Phase 2 est ce qui transforme le workspace d'éditeur de fichiers en **panneau de
configuration d'agents**, ce qui est la vraie proposition de valeur que le nom
« workspace » promet déjà.

Décision suggérée : commencer par la Phase 1 dans la foulée de la PR #532, décider
de la Phase 2 après avoir vu comment les 2-3 premiers créateurs de test utilisent
l'onglet « Fichiers ».
