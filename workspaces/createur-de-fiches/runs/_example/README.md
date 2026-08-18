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
