# Instructions pour agents IA

Ce fichier est le point d'entrée pour tout agent (Claude Code, OpenAI Codex, Cursor, Aider, Continue, opencode, Google Jules, etc.). **Il route, il ne contient pas.** Chaque question ci-dessous pointe vers le fichier autoritaire.

---

## Le projet en deux phrases

Philum est une infrastructure ouverte qui permet aux créateurs de contenu (vulgarisateurs scientifiques d'abord, puis journalistes et chercheurs) de transformer leur bibliographie en une fiche publique navigable, avec sources horodatées et signées cryptographiquement. La vision long terme est de devenir la couche standard de citation du web à l'ère de l'IA générative.

Pour le détail : [`README.md`](./README.md) → [`.docs/00-vision.md`](.docs/00-vision.md) → [`.docs/01-product-spec.md`](.docs/01-product-spec.md) → [`.docs/02-tech-architecture.md`](.docs/02-tech-architecture.md).

---

## Où aller selon la question

| Question                                             | Fichier                                                                                                       |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Quel est l'état réel de la prod ?                    | [`STATE.md`](./STATE.md) section « État production vérifié »                                                  |
| Qu'est-ce que je dois faire ensuite ?                | [`STATE.md`](./STATE.md) section « Prochaines étapes par priorité »                                           |
| Stack, principes de code, nommage, structure du repo | [`agent/references/CODING_GUIDE.md`](./agent/references/CODING_GUIDE.md)                                      |
| Décisions techniques passées (ADRs)                  | [`DECISIONS.md`](./DECISIONS.md)                                                                              |
| Erreurs déjà payées à ne pas reproduire              | [`agent/PITFALLS.md`](./agent/PITFALLS.md)                                                                    |
| Workflow git, PRs, merges                            | [`agent/GIT_WORKFLOW.md`](./agent/GIT_WORKFLOW.md)                                                            |
| Permissions et sécurité de l'agent                   | [`agent/PERMISSIONS.md`](./agent/PERMISSIONS.md), [`agent/SECURITY.md`](./agent/SECURITY.md)                  |
| Tâche spécialisée (Alembic, OAuth, Svelte...)        | [`agent/skills/`](./agent/skills/)                                                                            |
| Session autonome multi-sessions                      | [`agent/README.md`](./agent/README.md) point d'entrée du système agent                                        |
| Créer une fiche Philum de bout en bout               | [`workspaces/createur-de-fiches/AGENTS.md`](./workspaces/createur-de-fiches/AGENTS.md) workspace ICM 7 étapes |
| Question produit non tranchée                        | [`.docs/07-open-questions.md`](.docs/07-open-questions.md)                                                    |

---

## Contrat de continuité

Si tu modifies l'état réel du projet (feature livrée, fix prod, déploiement), **mets à jour `STATE.md`** avant de fermer la session. Décision technique non triviale → une entrée dans `DECISIONS.md`.

C'est ce qui permet à toi-même (ou à un autre agent) de reprendre efficacement à la session suivante.

---

## Limites strictes (non négociables, même autorisées ponctuellement)

- Jamais de `git push` direct sur `main`. Toujours via PR.
- Jamais de modification de `.docs/00` à `.docs/09` sans demande explicite.
- Jamais de secret en commit.
- Jamais de modification de la forme du payload signé d'une `content_attestation` sans ADR (cf. `agent/PITFALLS.md` §1.3).
- Détail complet : [`agent/README.md`](./agent/README.md) section « Limites strictes ».

---

## En cas de doute

1. Lire le fichier `.docs/` pertinent (souvent `01-product-spec.md` ou `02-tech-architecture.md`).
2. Si l'ambiguïté persiste, ajouter une entrée dans [`.docs/07-open-questions.md`](.docs/07-open-questions.md) et choisir l'option la plus simple en attendant.
3. Le mentionner explicitement dans la réponse à l'utilisateur.

---

_Ce fichier évolue avec le projet. Si une règle te paraît dépassée ou bloquante, signale-le._
