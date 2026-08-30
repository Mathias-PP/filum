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
| G6 frontend | lib/agent, chat UI, routes | ✅ **VERTE** (check_lot.sh vert, 2026-08-26) le 2026-08-26 — 12 fichiers / 3 093 LOC, preuves `06-interface-chat/` |
| G7 tests + prod | 16+ fichiers de tests, workspace ICM, état VM | ✅ **VERTE** (check_lot.sh vert, 2026-08-26) le 2026-08-26 — 103 fichiers documentés, preuves `07-tests-et-prod/` |
| G8 assemblage global | rejeu de toutes les portes + routage + spot-check 10 % | ✅ **VERTE** (rejeu G1→G7 vert, spot-check 10% 57/57 OK, routage 80 liens OK) le 2026-08-26, preuve `_core/preuves/G8_vert_2026-08-26.md` |

**Invariants regelés le 2026-08-31** (`_core/invariants.txt`, commit `9114558`) : 43 outils MCP · 33 endpoints · 14 événements SSE · 15 variables d'env · 204 fichiers · 28 451 LOC périmètre. Toute évolution du code qui change ces nombres doit faire l'objet d'une mise à jour documentée ici.

Attention : la porte G0 ne compare **jamais** ces nombres au code. Son test (e) vérifie seulement que les quatre invariants sont présents et entiers. Une dérive de compteur passe donc les portes sans bruit, et c'est ainsi que les trois écarts ci-dessous ont vécu plusieurs jours. Le seul garde-fou automatique est le LOC périmètre, borné à ±5 % de la baseline.

Évolutions documentées depuis le gel du 2026-08-25 :

- **12 → 13 événements SSE, en #581** (`feat(agent): redemande la reponse quand une action annoncee n'a pas ete faite`). Ajout de `controle_relance`. La mise à jour de l'invariant avait été omise : le compte réel valait 13 depuis cette PR alors que le fichier annonçait toujours 12. Constaté et corrigé le 2026-08-30.
- **13 → 14 événements SSE, le 2026-08-30.** Ajout de `repli_fournisseur`, émis par `agent.boucle` quand une clé refuse et qu'une autre prend le relais. Le créateur qui a configuré trois clés n'en voyait essayer qu'une ; le repli silencieux, lui, serait indistinguable d'une panne, d'où l'événement plutôt qu'un simple changement de clé.
- **31 → 33 endpoints, en #603** (`feat(workspace): les evolutions du modele arrivent enfin, sans ecraser vos editions`). Deux routes ajoutées au domaine workspace. Là encore la mise à jour de l'invariant avait été omise ; constaté et corrigé le 2026-08-30.
- **191 → 202 fichiers inventoriés, le 2026-08-30.** Onze fichiers manquaient au CSV, dont neuf antérieurs au travail du jour, et parmi eux `app/services/agent_sessions.py`, un service du noyau qui n'avait jamais été inventorié. Les lignes ont été **ajoutées** au CSV plutôt que régénérées : `gen_inventaire.sh` remet tous les `statut` à `todo`, ce qui aurait effacé la progression de lecture de 154 fichiers déjà `verifie`. La baseline LOC passe de 24 046 à 25 777 et la bande de référence de `check_inventaire.sh` suit.
- **202 → 204 fichiers et 25 777 → 28 451 LOC, le 2026-08-31** (commit `9114558`). Deux fichiers manquaient : `tests/unit/test_agent_recherche_web.py` (arrivé en #617) et `alembic/versions/057_lane_secours_modele_distinct.py`. Ce dernier était **invisible pour la porte** : `gen_inventaire.sh` ne découvre pas les migrations, il les filtre par une liste de numéros écrite à la main (ligne 60), où 057 ne figurait pas. Le numéro y a été ajouté ; toute migration future du périmètre agent devra l'être aussi, sans quoi elle échappera à G0 en silence.
- **Le saut de 2 674 LOC n'est pas dû au travail du 2026-08-31.** Le regel du 2026-08-30 avait mis à jour le total sans recalculer les `loc` de chaque ligne : la baseline 25 777 était dérivée d'un CSV périmé, et le périmètre réel valait déjà environ 28 451. Toutes les lignes ont cette fois été recalculées depuis le disque (`loc`, `sha256`, `symboles`), les `statut` préservés. La dérive vient des PR #575 à #615, principalement `test_agent_loop.py` (+573), `services/agent.py` (+466), `test_agent_chat_api.py` (+185), `ChatPanel.svelte` (+133), `tools_write.py` (+130). Leçon : un regel qui touche `invariants.txt` sans repasser sur les lignes du CSV **fabrique** l'écart qu'il prétend mesurer, et la bande ±5 % le couvre pendant des jours.

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
  06-interface-chat / 07-tests-et-prod/   ← ✅ G6 verte + ✅ G7 verte : [CONTEXT.md](06-interface-chat/CONTEXT.md) / [CONTEXT.md](07-tests-et-prod/CONTEXT.md)
  09-deepseek-harness/      ← ✅ audit Philum vs deepseek-harness (bugs, faisabilité, plans, UI, patterns)
  10-externes/              ← audit 3 dépôts externes → Philum (OmniRoute/repli, open-notebook/recherche duale, book-to-skill/Unicode)
  11-graph-memory/          ← audit graph-memory-starter : déjà porté dans graph_memory.py, 9 défauts du portage, 3 manques (RRF, distillation, mémoire de session)
```

## Pour un agent qui arrive sur le repo

1. Lire ce fichier → choisir le domaine qui t'intéresse dans l'arborescence.
2. Toute question « que fait X ? » doit trouver sa réponse en ≤ 2 clics depuis [`AGENTS.md`](../../AGENTS.md) ; si ce n'est pas le cas, c'est un défaut de cette documentation, pas ta faute — signale-le.
3. Si tu modifies le code agent : relance `gen_inventaire.sh` puis la porte concernée — les sha256 et ancres qui ne suivent pas rendront les portes rouges, c'est voulu.
