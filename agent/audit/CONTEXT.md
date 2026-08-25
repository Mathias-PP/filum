# Audit du code Agent IA — routeur

> **Qu'est-ce que c'est ?** La documentation d'état, fichier par fichier, de tout ce qui constitue l'Agent IA de Philum (boucle, outils MCP, API, gratuit, interface chat, tests, workspace ICM). Chaque affirmation porte une ancre `chemin:ligne` vérifiable. Produite par le plan [`agent/plans/2026-08-25-revue-code-agent.md`](../plans/2026-08-25-revue-code-agent.md), dont les **portes bloquantes G0→G8** garantissent la couverture (preuves scriptées dans `_core/preuves/`).
>
> **Comment naviguer ?** Un dossier par domaine, chaque dossier a son `CONTEXT.md`. Les références transversales vivent dans `shared/`. L'outil de preuve vit dans `_core/`.

## Tableau de bord (mis à jour à chaque porte franchie)

| Porte | Périmètre | État | Preuve |
|---|---|---|---|
| G0 — inventaire machine | 184 fichiers (147 périmètre + 37 interfaces), 24 042 LOC | ✅ **VERTE** (double vert + test anti-fraude) le 2026-08-25 au commit `dae9cc0` | `_core/preuves/G0_vert_*_2026-08-25_1510.txt` |
| G1 fondations | config, modèles, migrations 040→052, transport LLM | ⬜ en attente | — |
| G2 noyau | `agent.py`, approbations, sessions | ⬜ en attente | — |
| G3 outils MCP | serveur, auth, compat schéma, tools, tools_write (43 outils) | ⬜ en attente | — |
| G4 API | 7 endpoints agent, 31 routes, flux SSE | ⬜ en attente | — |
| G5 services métier | providers, gratuit/discovery, definitions, fiche, workspace | ⬜ en attente | — |
| G6 frontend | lib/agent, chat UI, routes | ⬜ en attente | — |
| G7 tests + prod | 16+ fichiers de tests, workspace ICM, état VM | ⬜ en attente | — |
| G8 assemblage global | rejeu de toutes les portes + routage + spot-check 10 % | ⬜ en attente | — |

**Invariants gelés** (`_core/invariants.txt`) : 43 outils MCP · 31 endpoints · 12 événements SSE · 15 variables d'env. Toute évolution du code qui change ces nombres doit faire l'objet d'une mise à jour documentée ici.

## Arborescence (se remplit lot après lot)

```
agent/audit/
  CONTEXT.md                ← ce fichier
  _core/
    inventaire.csv          ← manifeste machine : type,lot,chemin,loc,sha256,symboles,statut
    invariants.txt          ← compteurs figés à date
    gen_inventaire.sh       ← régénère l'inventaire (à relancer après chaque évolution du code)
    check_inventaire.sh     ← porte G0
    check_lot.sh <1-7>      ← portes G1..G7 (bloquantes)
    spot_check.sh <lot>     ← sous-boucle anti-fraude (tirage seedé d'ancres)
    preuves/                ← rapports horodatés des portes
  shared/                   ← (à venir) contrats transversaux : SSE, variables env, catalogue outils
  01-fondations/ … 07-tests-et-prod/   ← (à venir) une fiche par fichier
```

## Pour un agent qui arrive sur le repo

1. Lire ce fichier → choisir le domaine qui t'intéresse dans l'arborescence.
2. Toute question « que fait X ? » doit trouver sa réponse en ≤ 2 clics depuis [`AGENTS.md`](../../AGENTS.md) ; si ce n'est pas le cas, c'est un défaut de cette documentation, pas ta faute — signale-le.
3. Si tu modifies le code agent : relance `gen_inventaire.sh` puis la porte concernée — les sha256 et ancres qui ne suivent pas rendront les portes rouges, c'est voulu.
