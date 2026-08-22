# Benchmark et analyse d'autres solutions

Ce dossier consolide les études faites sur des solutions externes (repos GitHub, produits SaaS,
méthodologies) évaluées comme sources possibles d'inspiration pour Philum. Chaque étude est un
fichier daté ; ce README sert d'index et de tableau de synthèse.

**Règles** :

- Une étude par solution (ou par grappe cohérente). Datée à sa création, jamais réécrite en
  place ; une révision majeure crée un nouveau fichier daté qui explicite ce qu'elle remplace.
- Chaque étude se termine par un **verdict** : ADOPTÉ / À COPIER / À SURVEILLER / REJETÉ, et
  la ligne correspondante dans ce README est mise à jour au moment du merge.
- Aucune étude n'oblige à agir : elles nourrissent les décisions produit, pas plus.
- Ce qui est déjà en place dans le code n'est pas re-proposé : chaque étude commence par
  vérifier l'état existant (`agent/research/2026-08-21-a-copier-adapter-ameliorer-harness.md`
  fait ça pour le harness BYOK, à imiter).

**Comment lire les verdicts** :

- **ADOPTÉ** : au moins un mécanisme a été intégré dans Philum (avec référence au commit / PR).
- **À COPIER** : décision prise d'intégrer, pas encore fait.
- **À SURVEILLER** : intéressant, à revisiter quand un besoin le rendra prioritaire.
- **REJETÉ** : évalué et écarté, avec la raison. Utile pour ne pas re-proposer.

---

## Tableau de synthèse

Solutions étudiées, par catégorie, avec la ou les études qui les traitent. Une même solution
peut apparaître dans plusieurs études sous des angles différents.

### Harness d'agent LLM (patterns transposables)

| Solution | Nature | Verdict Philum | Étude(s) |
|---|---|---|---|
| **rakazo** | Bots persistants BYOK Postgres/Electron/Expo, Apache-2.0 | ADOPTÉ (patterns : secrets AES-256-GCM, credentials BYOK, run state machine, approbation hybride, idempotence, compaction) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md) |
| **deepseek-harness** | Harness d'agent local-first (Node), MIT | À SURVEILLER (couche multi-provider `pi-ai`, seam de credentials, approval fail-closed ; non embarqué — décision produit 2026-08-20) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md), [harness-agent-philum](2026-08-20-harness-agent-philum.md) |
| **digipair** | Framework de raisonnement basé sur fichiers JSON (PINS) | À SURVEILLER (langage JSON typé + merge hiérarchique de configs) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md) |
| **ecc** | Pack d'agents/skills/hooks pour harness de codage, MIT | À COPIER (patterns : GateGuard, regex-vs-LLM, memory vault, AgentShield ; pas le code) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md) |
| **firetower-cloud/firetower** | Control plane Rust pour agents de dev multi-hôte, AGPL-3.0 | À COPIER (approval inbox + notification hors-app, effort S) — reste hors périmètre | [firetower](2026-08-22-firetower.md) |

### Provider registry, catalogue de modèles, mode gratuit

| Solution | Nature | Verdict Philum | Étude(s) |
|---|---|---|---|
| **opencode** | Vercel AI SDK (75+ providers) + registre `models.dev` + Zen (7 modèles gratuits) | À COPIER (métadonnées de modèles depuis `/models` d'OpenRouter, priorité P1) | [providers-multi-modeles-gratuits](2026-08-21-providers-multi-modeles-gratuits.md), [a-copier-adapter-ameliorer](2026-08-21-a-copier-adapter-ameliorer-harness.md) |
| **hermes-agent** (nousresearch) | Intégrations providers documentées | À SURVEILLER | [providers-multi-modeles-gratuits](2026-08-21-providers-multi-modeles-gratuits.md) |
| **openclaw** | ~30 plugins providers, `allowPrivateNetwork`, `Test connection`, rotation 429 | ADOPTÉ (garde SSRF, test avec `provider_message`) + À COPIER (protocole par kind, rotation 429) | [providers-multi-modeles-gratuits](2026-08-21-providers-multi-modeles-gratuits.md), [a-copier-adapter-ameliorer](2026-08-21-a-copier-adapter-ameliorer-harness.md) |
| **cherry-studio** | Client desktop multi-provider AGPL-3.0 (community) / Enterprise privé, support Ollama/LM Studio | À COPIER (débloquer runtimes locaux en self-host/dev — attention nuance prod). Support local exposé à l'utilisateur écarté pour Philum SaaS (voir doc) | [cherry-studio-modeles-locaux](2026-08-21-cherry-studio-modeles-locaux.md) |

### Méthodologie ICM (workspace éditorial)

| Solution | Nature | Verdict Philum | Étude(s) |
|---|---|---|---|
| **ICM** (Interpretable Context Methodology) | Conventions « la structure de dossiers orchestre l'agent », MIT | ADOPTÉ (le workspace `createur-de-fiches` est un ICM ; page `/dashboard/workspace` livrée PR #532) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md) |
| **icm-architect** | Skill de construction/restructuration d'espaces ICM, MIT | À SURVEILLER (10 invariants + walk test + 6 formes, utile pour valider les workspaces hébergés) | [comparatif-six-repos](2026-08-20-comparatif-six-repos.md) |

### Modèles économiques (comment les autres facturent l'IA embarquée)

| Solution | Nature | Verdict Philum | Étude(s) |
|---|---|---|---|
| **18 produits comparés** (Cursor, Copilot, Windsurf, Zed, Replit, Notion AI, Linear, Slack, M365 Copilot, ChatGPT, Claude, Perplexity, Poe, OpenRouter, Jasper, etc.) | Cinq patterns économiques observés (BYOK pass-through, forfait plat avec caps, add-on à seat, crédits mesurés, freemium+overage) | À COPIER — Positionnement **BYOK pass-through + mode découverte plafonné sponsorisé** ; éviter forfait plat inclusif (perte assurée), effort-based (opacité toxique), add-on à seat (adoption 2-3 %). Voir 5 recommandations dans l'étude. | [modeles-economiques-agents-ia-payants](2026-08-22-modeles-economiques-agents-ia-payants.md) |

### Outils de recherche scientifique (positionnement produit, pas archi)

| Solution | Nature | Verdict Philum | Étude(s) |
|---|---|---|---|
| **ResearchRabbit** | Découverte de littérature par graphes, refonte 2025 (suppression du force-directed non trié) | REJETÉ comme brique, ADOPTÉ comme leçon produit (borner l'affichage, mode à axes signifiants) | [outils-chercheurs](2026-08-03-outils-chercheurs.md) |
| **SciSpace** | Assistant recherche IA, palier « Verified Report » à 70 $/mois | REJETÉ (produit des références fabriquées, précision ~0.40, opaque) — trou du marché à occuper par Philum | [outils-chercheurs](2026-08-03-outils-chercheurs.md) |
| Autres (Elicit, Consensus, Scite, Semantic Scholar, etc.) | Outils IA de synthèse de littérature | À SURVEILLER, positionnement documenté | [outils-chercheurs](2026-08-03-outils-chercheurs.md) |

---

## Études

Par ordre chronologique inverse (la plus récente en tête). Chaque fichier est autonome et
peut être lu sans lire les autres ; les études qui affinent ou nuancent un rapport plus
ancien le disent en tête.

- [2026-08-22 — Workspace Philum : audit valeur, seed manquant, proposition multi-agents](2026-08-22-workspace-refonte-multi-agents.md)
- [2026-08-22 — Modèles économiques des produits qui embarquent une IA payante](2026-08-22-modeles-economiques-agents-ia-payants.md)
- [2026-08-22 — firetower-cloud/firetower : control plane pour agents de codage](2026-08-22-firetower.md)
- [2026-08-21 — Cherry Studio et modèles « en local » sur Philum](2026-08-21-cherry-studio-modeles-locaux.md)
- [2026-08-21 — Du comparatif providers à l'action : copier / adapter / améliorer pour le harness Philum](2026-08-21-a-copier-adapter-ameliorer-harness.md)
- [2026-08-21 — Étude : gestion multi-providers et modèles gratuits dans les grands harness](2026-08-21-providers-multi-modeles-gratuits.md)
- [2026-08-20 — Comparatif six repos : ce qu'on copie / adapte pour le harness BYOK Philum](2026-08-20-comparatif-six-repos.md)
- [2026-08-20 — Rapport : intégrer un harness d'agent dans Philum](2026-08-20-harness-agent-philum.md)
- [2026-08-03 — Étude : outils de recherche et valeur pour Philum](2026-08-03-outils-chercheurs.md)

---

## Comment ajouter une nouvelle étude

1. Créer un fichier `YYYY-MM-DD-nom-court.md` dans ce dossier.
2. Commencer par un bloc `> **Objet** : …` et `> **Verdict** : …`.
3. Documenter ce que la solution fait, comparer point par point avec l'existant Philum, et
   sortir une liste d'actions concrètes (chacune avec effort et priorité) plutôt qu'un pavé.
4. Vérifier tout ce qui est cité contre le code source de la solution (pas la doc marketing)
   à la date de l'étude, et le préciser en tête (les repos évoluent vite).
5. Ajouter la ligne correspondante dans le tableau de synthèse ci-dessus, avec un verdict.
6. Ne pas mettre à jour les études anciennes ; en créer une nouvelle si l'analyse évolue.
