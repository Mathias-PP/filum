# 05-05 — Fiche (orchestrateur 7 étages ICM)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_fiche.py` (211 l., 7 symboles).
> sha256: 0c19cff5bb3c66fdde3c6ae8baaae8ed1ac55f53e9b7481bfc7c89d3c70c37d9

## Rôle

Orchestrateur de la fiche ICM : 7 étages séquentielles (brief → sources → annotations → extraits → connexions → relecture → publication), reprise `depuis`, compte rendu séquentiel. Chaque étage est une boucle d'agent autonome avec son `CONTEXT.md`.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `Etape` | `apps/backend/app/services/agent_fiche.py:40` | Dataclass d'un étage ICM (id, sortie, instructions) |
| `FicheError` | `apps/backend/app/services/agent_fiche.py:75` | Le run ne peut pas démarrer ou continuer |
| `_prefixe` | `apps/backend/app/services/agent_fiche.py:79` | Rend `runs/{slug}` |
| `etat` | `apps/backend/app/services/agent_fiche.py:83` | Où en est un run : quels étages ont déjà leur compte rendu |
| `_instructions` | `apps/backend/app/services/agent_fiche.py:101` | Lit le `CONTEXT.md` d'un étage depuis le workspace |
| `_amorce` | `apps/backend/app/services/agent_fiche.py:111` | Construit le prompt initial d'un étage |
| `lancer` | `apps/backend/app/services/agent_fiche.py:123` | Déroule les étages et écrit chaque compte rendu |

## Invariants

- `ETAPES` = 7 tuples `Etape` (`apps/backend/app/services/agent_fiche.py:54`) : brief → sources → annotations → extraits → connexions → relecture → publication. L'ordre est codé en dur.
- `_CADRE` (`apps/backend/app/services/agent_fiche.py:66`) : instructions système rappelées à chaque étage.
- `lancer()` (`apps/backend/app/services/agent_fiche.py:123`) : `depuis` reprend un run interrompu — les comptes rendus déjà écrits sont relus comme contexte.
- `lancer()` (`apps/backend/app/services/agent_fiche.py:123`) : une erreur émise par la boucle arrête le run (pas de continuation sur étage raté).

## Dettes

- `ETAPES` (`apps/backend/app/services/agent_fiche.py:54`) : tuple immuable — ajouter un étage exige de modifier `_amorce` et `lancer`.
- `_amorce()` (`apps/backend/app/services/agent_fiche.py:111`) : ne gère pas les cas limites (slug vide, content_url vide).
