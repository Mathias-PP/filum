# 06-02 — markdown.ts (parseur markdown, protection XSS)

> **Fiche du lot 6.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G6**.
> **Fichier :** `apps/frontend/src/lib/agent/markdown.ts` (165 l., 4 symboles).
> sha256: 54e83debb5e1dc01dc8a0e4b43c3307085b0f9ca56e67f37ff4bd0da1af39abc

## Rôle

Parseur markdown déterministe pour l'affichage des réponses de l'agent. Convertit le markdown brut en HTML échappé — pas de `{@html}` côté Svelte, protection XSS native. Définit les types `Segment` et `Bloc`, et les fonctions `segmentsInline()` et `analyser()`.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `Segment` | `apps/frontend/src/lib/agent/markdown.ts:13` | Type union des segments inline (texte, gras, italique, lien, code) |
| `Bloc` | `apps/frontend/src/lib/agent/markdown.ts:20` | Type union des blocs (paragraphe, titre, code, liste, citation, séparateur) |
| `segmentsInline` | `apps/frontend/src/lib/agent/markdown.ts:39` | Parse une ligne en segments inline (gras, italique, liens, code) |
| `analyser` | `apps/frontend/src/lib/agent/markdown.ts:77` | Parse le markdown complet en blocs structurés |

## Invariants

- **Pas de `{@html}`** : tout HTML est échappé avant insertion dans le DOM — aucun risque d'injection via le contenu agent.
- `segmentsInline()` (`apps/frontend/src/lib/agent/markdown.ts:39`) : pure function, pas de side-effect.
- `analyser()` (`apps/frontend/src/lib/agent/markdown.ts:77`) : pure function, déterministe.
- `securiserUrl()` (`apps/frontend/src/lib/agent/markdown.ts:30`) : valide les URLs des liens (pas de `javascript:`).

## Dettes

- Le parseur est maison (pas de `marked` ou `markdown-it`) — fonctionnel mais ne couvre pas toute la spec CommonMark.
