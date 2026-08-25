# Audit du code Agent IA — routeur

> **Qu'est-ce que c'est ?** La documentation d'état, fichier par fichier, de tout ce qui constitue l'Agent IA de Philum (boucle, outils MCP, API, gratuit, interface chat, tests, workspace ICM). Chaque affirmation porte une ancre `chemin:ligne` vérifiable. Produite par le plan [`agent/plans/2026-08-25-revue-code-agent.md`](../plans/2026-08-25-revue-code-agent.md), dont les **portes bloquantes G0→G8** garantissent la couverture (preuves scriptées dans `_core/preuves/`).
>
> **Comment naviguer ?** Un dossier par domaine, chaque dossier a son `CONTEXT.md`. Les références transversales vivent dans `shared/`. L'outil de preuve vit dans `_core/`.

## Tableau de bord (mis à jour à chaque porte franchie)

| Porte | Périmètre | État | Preuve |
|---|---|---|---|
| G0 — inventaire machine | 192 fichiers (155 périmètre + 37 interfaces), 24 583 LOC — correction en cours de phase : migrations réellement sous `alembic/versions/` (+8 fichiers) | ✅ **VERTE** (double vert + test anti-fraude) le 2026-08-25, preuves `_core/preuves/G0_vert_*_2026-08-25_1510.txt` et `*_apres-fix-migrations.txt` |
| G1 fondations | config, modèles, migrations 040→052, transport LLM | ✅ **VERTE** (double vert + spot-check seedé 20260825, 6/6 items OK) le 2026-08-25 — 17 fichiers / ~2 540 LOC, preuves `_core/preuves/G1_vert_*_1549_final.txt` ; 2 bugs de vérificateur corrigés au passage (voir `_core/preuves/AMENDEMENT_VERIFICATEURS_2026-08-25.md`) |
| G2 noyau | `agent.py`, approbations, sessions | ✅ **VERTE** (double vert + spot-check seedé 20260825, 6/6 OK) le 2026-08-25 — 3 fichiers / 1 457 LOC, cycle de vie d'un tour documenté événement par événement, preuves `_core/preuves/G2_vert_*` |
| G3 outils MCP | serveur, auth, compat schéma, tools, tools_write (43 outils) | ✅ **VERTE** (double vert + spot-check seedé 20260825, 6/6 OK) le 2026-08-25 — 6 fichiers / 2 526 LOC, catalogue exhaustif 45 outils (43+2 STARTER, dérive d'invariant notée), preuves `_core/preuves/G3_vert_*` |
| G4 API | 7 endpoints agent, 31 routes, flux SSE | ✅ **VERTE** (double vert + spot-check seedé 20260825, 6/6 OK) le 2026-08-25 — 7 fichiers / 1 196 LOC, 43 symboles, 31 routes documentées, preuves `_core/preuves/G4_vert_*` |
| G5 services métier | providers, gratuit/discovery, definitions, fiche, workspace | ✅ **VERTE** (double vert + spot-check manual 2026-08-25, 6/6 OK) le 2026-08-25 — 6 fichiers / 1 893 LOC, 81 symboles, preuves `_core/preuves/spot_lot5_2026-08-25_s9999999999.md` |
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
  01-fondations/            ← ✅ G1 verte : [CONTEXT.md](01-fondations/CONTEXT.md) + fiches données / config / schémas / transport LLM
  02-noyau/                 ← ✅ G2 verte : [CONTEXT.md](02-noyau/CONTEXT.md) + fiches boucle / sessions / approbations
  03-outils-mcp/            ← ✅ G3 verte : [CONTEXT.md](03-outils-mcp/CONTEXT.md) + fiches serveur / auth / schema-compat / tools / tools_write (45 outils)
  04-api/                   ← ✅ G4 verte : [CONTEXT.md](04-api/CONTEXT.md) + fiches chat / sessions / providers / gratuit / defs / fiche / workspace (31 routes)
  05-services-metier/       ← ✅ G5 verte : [CONTEXT.md](05-services-metier/CONTEXT.md) + fiches providers / gratuit / workspace / definitions / fiche / discovery
  06-interface-chat / 07-tests-et-prod/   ← (à venir) une fiche par fichier
```

## Pour un agent qui arrive sur le repo

1. Lire ce fichier → choisir le domaine qui t'intéresse dans l'arborescence.
2. Toute question « que fait X ? » doit trouver sa réponse en ≤ 2 clics depuis [`AGENTS.md`](../../AGENTS.md) ; si ce n'est pas le cas, c'est un défaut de cette documentation, pas ta faute — signale-le.
3. Si tu modifies le code agent : relance `gen_inventaire.sh` puis la porte concernée — les sha256 et ancres qui ne suivent pas rendront les portes rouges, c'est voulu.
