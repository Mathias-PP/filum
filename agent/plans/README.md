# `agent/plans/` — plans d'implémentation actifs

Un plan vit ici tant qu'un agent est en train de le dérouler. Une fois exécuté (ou abandonné), il est déplacé dans `_archive/` avec sa date en préfixe.

## Convention

- **Actif** : `agent/plans/YYYY-MM-DD-slug.md`. L'agent qui l'exécute doit pouvoir en lire l'entête et savoir où il en est (checkboxes, section « État courant »).
- **Archivé** : `agent/plans/_archive/YYYY-MM-DD-slug.md`. Snapshot historique, non exécutable tel quel — le code a probablement bougé depuis.
- **Un plan sans mise à jour depuis > 30 jours** est présumé archivé, à déplacer.

## Où est le vrai « qu'est-ce que je fais ensuite »

`STATE.md` à la racine du repo, section « Prochaines étapes par priorité ». C'est là que vit la file d'attente, pas ici. Un plan est le **plan d'exécution** d'un item de STATE.md ; s'il n'y a pas d'item courant, il n'y a pas de plan actif.

## Archive

Voir `_archive/` pour les plans passés (waitlist + claim + MCP read-only de juillet 2026, graphe/identité/profils de début août 2026, chantiers de conception 2026-08-07). Ces plans ont été exécutés en tout ou partie ; leur trace vit dans `STATE.md` et les PRs GitHub, pas dans les checkboxes ici (qui n'ont jamais été cochées — les plans étaient lus, exécutés, et le suivi passait par le journal `STATE.md`).
