# 07-02 — Workspace seed (template ICM)

> **Fiche du lot 7.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G7**.
> **Dossier :** `apps/backend/app/agent_workspace_seed/` (27 fichiers, ~1 200 LOC).

## Rôle

Le template du workspace ICM (Infrastructure de Création de Modeles) qui est servi aux nouveaux créateurs. Contient les agents YAML (assistant, bibliographe, extracteur, publicateur, rechercheur, redacteur, relecteur), les shared docs (garde-fous, philum-mcp, pieges-vecus, principes-editoriaux, style-redactionnel), les stages (01-brief → 07-publication), les templates (brief, extrait, source), et le script d'audit de fiche.

## Fichiers

### Racine
| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `apps/backend/app/agent_workspace_seed/AGENTS.md` | 79 | sha256: fedcca13a37c9d10f47e7ede3126a4750ab11dd909d6d62488fd91390e0f1821 | Instructions pour l'agent dans le workspace |
| `apps/backend/app/agent_workspace_seed/CONTEXT.md` | 41 | sha256: 270e8d25a1cf8b3f80f16652eade2ba70effc44358cb94a13459dfedb203f50a | Contexte du workspace ICM |

### Agents YAML
| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `apps/backend/app/agent_workspace_seed/agents/CONTEXT.md` | 50 | sha256: 23c2699ee66e9f77f0a34bb94544cc06cda1aa986a763d50aaf1b62f6b1094a3 | Contexte des agents |
| `apps/backend/app/agent_workspace_seed/agents/assistant.yaml` | 54 | sha256: ccc3e5bc1ef80a332ffd182e936b7b6c458354bebb42c59d6c9f64080a36d65c | Agent assistant généraliste |
| `apps/backend/app/agent_workspace_seed/agents/bibliographe.yaml` | 32 | sha256: 8b4d2da84ee4942858be1bea9f96ff2ce908653afb672a91ed0abdc0fc0b27bf | Agent bibliographe |
| `apps/backend/app/agent_workspace_seed/agents/extracteur.yaml` | 37 | sha256: effda9fb3c371b65857122e760cc899e8a0c67b234fb77b4bbb4e84ae2c5c1c1 | Agent extracteur de sources |
| `apps/backend/app/agent_workspace_seed/agents/publicateur.yaml` | 25 | sha256: 572ec00bbd61cabb6c7c0fc76951aa52a16ea716087ae968b6d362f8ccd37b83 | Agent publicateur |
| `apps/backend/app/agent_workspace_seed/agents/rechercheur.yaml` | 28 | sha256: 02ec5d1e53c4e0bfa2ce21c6337051cc32e06f343f98785dbd51dbd982d70d36 | Agent chercheur |
| `apps/backend/app/agent_workspace_seed/agents/redacteur.yaml` | 32 | sha256: 1f12d2065b26d633170f6732564d6f29558c2f6af5c7165b2c2e273e2f4696f9 | Agent rédacteur |
| `apps/backend/app/agent_workspace_seed/agents/relecteur.yaml` | 30 | sha256: 7a525958a45cec5b20933c4dc9d8ec53bf5077da9a28ab64bc726438f87e7215 | Agent relecteur |

### Shared docs
| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `apps/backend/app/agent_workspace_seed/shared/garde-fous.md` | 57 | sha256: 21b60c93ebd2697e0d468ca41074745ec83d4993db54516b19320499fd2fe03b | Garde-fous et limites de l'agent |
| `apps/backend/app/agent_workspace_seed/shared/philum-mcp.md` | 101 | sha256: cf999119590e512780eea310b224866c8a1ff6117ee52cee53188babe882284f | Documentation des outils MCP |
| `apps/backend/app/agent_workspace_seed/shared/pieges-vecus.md` | 127 | sha256: fb13862d3b7df692347f0f8359ca9c6f928cb407b2f1f162e3b3914abbffeda7 | Pièges vécus et lessons apprises |
| `apps/backend/app/agent_workspace_seed/shared/principes-editoriaux.md` | 71 | sha256: c3dce83b5b4462293098a12145102d8dbe6d608ca6083fcc681756e5002c702d | Principes éditoriaux |
| `apps/backend/app/agent_workspace_seed/shared/style-redactionnel.md` | 55 | sha256: 61729684dee193ee4318f90e4d1ad12434898ea2ccf58a7e2b130ea60ee4e441 | Style rédactionnel |

### Stages (01-brief → 07-publication)
| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `apps/backend/app/agent_workspace_seed/stages/01-brief/CONTEXT.md` | 50 | sha256: 688ee3f824b6a1bbd384548202e3ac6f0bee8e2d8363c6caa4725fd56589e3ee | Contexte stage brief |
| `apps/backend/app/agent_workspace_seed/stages/02-sources-collectees/CONTEXT.md` | 57 | sha256: e7b14a818a8e5da985979c75453cbefe1c3afa7d66037c017036f2bad40f4870 | Contexte stage sources |
| `apps/backend/app/agent_workspace_seed/stages/03-annotations/CONTEXT.md` | 49 | sha256: fc69f2a3e9b51323320375524e63d7d52637730a13dcca440c5c8f2640ee740b | Contexte stage annotations |
| `apps/backend/app/agent_workspace_seed/stages/04-extraits/CONTEXT.md` | 56 | sha256: f8ebb16f153343e9ce85ade9caf0236b55c927cf8dbaed5e5ed0e5857fb6702b | Contexte stage extraits |
| `apps/backend/app/agent_workspace_seed/stages/04-extraits/references/verification-doi.md` | 41 | sha256: 0e15ee7229b716583acea41404b2f5297fabcb6abb61a83be56a5cd1829242e1 | Référence vérification DOI |
| `apps/backend/app/agent_workspace_seed/stages/05-connexions/CONTEXT.md` | 50 | sha256: d34d1545b608dd4d3b27d486b8e81a924a52e40e972268feac3486be66313be6 | Contexte stage connexions |
| `apps/backend/app/agent_workspace_seed/stages/06-relecture/CONTEXT.md` | 57 | sha256: bd5b9cd19e1205420e6d6d2db9fb7e98ea8eaf27cae5450b2082f0d6be71b685 | Contexte stage relecture |
| `apps/backend/app/agent_workspace_seed/stages/07-publication/CONTEXT.md` | 54 | sha256: ab81e76eaa898cac8f7c919612589fb748ab5c735f0c93f5b41991ea52f2fc6c | Contexte stage publication |

### Templates + Audit
| Fichier | LOC | sha256 | Rôle |
|---|---|---|---|
| `apps/backend/app/agent_workspace_seed/_core/templates/brief.md` | 40 | sha256: 9c8b8a41c08e77d1eabd59dbf7658473e5a02acfec6edc941d5795fc08be325a | Template du brief |
| `apps/backend/app/agent_workspace_seed/_core/templates/extrait.md` | 18 | sha256: 38c6e771d498b9cca49f0cc1067d30dcbba6f927c535f8ad72abbca725984791 | Template d'extrait |
| `apps/backend/app/agent_workspace_seed/_core/templates/source.md` | 25 | sha256: 3ff2b975bb7efa8c8179c84994d1f17bdbe07b454b8b4ab7178968512005cdd7 | Template de source |
| `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py` | 214 | sha256: a17dacb856ba9866bd71db436e66e6eb43c1744fa34d64b9a46d9c60a26aa428 | Script d'audit de fiche publiée |

## Symboles (audit_fiche.py uniquement)

| Symbole | Ligne | Rôle |
|---|---|---|
| `out` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:39` | Affiche un message |
| `alert` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:43` | Enregistre et affiche une alerte |
| `fetch_json` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:48` | Requête HTTP GET + parse JSON |
| `crossref_title` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:58` | Récupère le titre depuis Crossref |
| `parse_brief_frontmatter` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:64` | Parse le frontmatter YAML d'un brief |
| `main` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:77` | Point d'entrée : audit complet |
| `finish` | `apps/backend/app/agent_workspace_seed/_core/audit/audit_fiche.py:204` | Affiche le verdict et exit(0) |

## Invariants

- **Seed idempotent** : `build_workspace_seed.py` ne écrase que les fichiers présents dans la source — les fichiers modifiés en base ne sont pas écrasés.
- **Audit standalone** : `audit_fiche.py` n'a aucune dépendance interne (que `urllib`, `json`, `re`, `argparse`) — il peut tourner hors du conteneur.
