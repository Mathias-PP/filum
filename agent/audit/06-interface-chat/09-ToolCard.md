# 06-09 — ToolCard.svelte (carte d'appel outil)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/components/chat/ToolCard.svelte` (111 l., 0 symboles).
> sha256: e877845dc00c89578ad2267ded8ab26d9aef66da2586afe4531e18bb518609db

## Rôle

Carte d'affichage d'un appel d'outil : nom traduit, état (En cours / Terminé / Échec), erreur éventuelle, extrait vérifié (found/unreadable), bilan extraits (posés/écartés). Expandable pour voir le JSON brut des args et du résultat.

## Symboles

Aucun symbole nommé exporté — le composant utilise uniquement des `$state` et `$derived` réactifs (ouvert, echoue, etat, raison, rendu, extrait, verdict, bilanExtraits).

## Invariants

- **Pas de `{@html}`** : le rendu de l'extrait utilise `{extrait.texte}` en texte brut — pas de risque d'injection.
- **Expandable** : l'état `ouvert` contrôle l'affichage du JSON brut — fermé par défaut (pas de surcharge DOM inutile).
- **`rendreOutil()`** : importé depuis `toolLabels.ts` — la traduction est déléguée, pas en dur dans la card.

## Dettes

- 0 symboles nommés : le compteur du CSV est 0, ce qui est correct — le composant est purement déclaratif.
- Le JSON brut affiché en `<pre>` n'est pas échappé explicitement — `{JSON.stringify(args, null, 2)}` est sûr car `JSON.stringify` échappe les caractères spéciaux.
