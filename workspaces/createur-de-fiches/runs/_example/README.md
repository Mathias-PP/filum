# Run d'exemple

Ce dossier est un **modèle**. Ne pas travailler dedans.

Pour créer une vraie fiche :

```
cp -r workspaces/createur-de-fiches/runs/_example workspaces/createur-de-fiches/runs/<slug>
```

Puis :

1. Éditer `runs/<slug>/00-brief.md`.
2. Passer les étapes `stages/01-brief/` à `stages/07-publication/` dans l'ordre.
3. Le trigger `status` (documenté dans le CONTEXT.md racine du workspace) scanne les `output/` pour dire où tu en es.

## À quoi ressemble un `output/` rempli

Regarder `stages/02-sources-collectees/output/exemple-memoire-sommeil-sources.md` et `exemple-memoire-sommeil-ids.json` : forme concrète de ce qui doit sortir d'une étape terminée. C'est le seul dossier `output/` pré-rempli du modèle ; les autres étapes suivent le même patron (voir `stages/0N-.../CONTEXT.md` section `Outputs`).
