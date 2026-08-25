# 05-05 — Fiche (orchestrateur 7 étages ICM)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_fiche.py` (211 l., 7 symboles).

## Rôle

Orchestrateur de la fiche ICM : 7 étapes séquentielles (brief → sources → annotations → extraits → connexions → relecture → publication), reprise `depuis`, compte rendu séquentiel. Gestion de la progression et des erreurs.

## Architecture

- `ETAPES` : tuple des 7 étages (brief, sources, annotations, extraits, connexions, relecture, publication).
- `_ETAPES_CIBLE` : dict des cibles par étape (nombre d'items attendu).
- `FicheProgression` : modèle de progression (étape courante, étapes terminées, erreurs).
- `FicheResultat` : résultat final (succès, étapes réussies, erreurs, contenu).

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `ETAPES` | 54 | 7 étages ICM |
| `_ETAPES_CIBLE` | 62 | Cibles par étape |
| `FicheProgression` | 72 | Modèle progression |
| `FicheResultat` | 82 | Modèle résultat |
| `orchestrer_fiche` | 95 | Orchestrateur principal |
| `_executer_etape` | 130 | Exécution d'une étape |
| `_formater_compte_rendu` | 165 | Compte rendu séquentiel |

## Flux typique (orchestration)

1. `orchestrer_fiche` → initialise `FicheProgression` → itère sur `ETAPES`.
2. Pour chaque étape : `_executer_etape` → appelle le LLM → stocke le résultat → met à jour la progression.
3. En cas d'erreur : `_executer_etape` lève `FicheErreur` → `orchestrer_fiche` catch → ajoute l'erreur à la progression → continue.
4. `_formater_compte_rendu` → génère le compte rendu final des 7 étages.

## Dettes et pièges

- `ETAPES` (`apps/backend/app/services/agent_fiche.py:54`) : tuple immuable — ajouter un étage exige de modifier `_ETAPES_CIBLE` et `_formater_compte_rendu`.
- `_ETAPES_CIBLE` (`apps/backend/app/services/agent_fiche.py:62`) : les cibles sont hardcodées — ne pas modifier sans test en prod.
- `_executer_etape` (`apps/backend/app/services/agent_fiche.py:130`) : lève `FicheErreur` sur erreur — ne jamais catch silencieusement.
- `_formater_compte_rendu` (`apps/backend/app/services/agent_fiche.py:165`) : génère le compte rendu final — ne pas modifier le format sans impact frontend.
