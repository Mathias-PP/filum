# `agent/` — Système d'instructions pour agents autonomes

> Ce dossier est le **point d'entrée** pour tout agent autonome (opencode/Big Pickle, Aider, Cursor, Continue, Claude Code en mode plan, etc.) opérant sur le repo Filum.
>
> Claude Code dispose déjà de [`CLAUDE.md`](../CLAUDE.md) chargé automatiquement. `AGENTS.md` à la racine est l'équivalent pour les autres outils. Ce dossier `agent/` **complète** ces deux fichiers avec un mode opératoire structuré pour le **travail autonome multi-sessions**, où l'agent doit savoir où il en est sans réinventer le contexte à chaque démarrage.

---

## Quand lire ce dossier

| Situation | Lire |
|---|---|
| Première fois sur le projet | `agent/README.md` (ce fichier) → puis suivre le protocole ci-dessous |
| Reprise d'une session | `agent/TASK_PROTOCOL.md` (chapitre « Reprise ») |
| Question de permission | `agent/PERMISSIONS.md` |
| Question de git workflow | `agent/GIT_WORKFLOW.md` |
| Question de sécurité | `agent/SECURITY.md` |
| Avant tout commit | `agent/PITFALLS.md` (erreurs vécues à ne pas reproduire) |
| Tâche spécialisée (Alembic, OAuth, SvelteKit…) | `agent/skills/<nom>.md` |
| Besoin de contexte projet condensé | `agent/memory/PROJECT_SNAPSHOT.md` |

---

## Protocole de démarrage de session (obligatoire)

À exécuter **dans cet ordre**, sans sauter d'étape :

1. **Lire la mémoire condensée** : [`memory/PROJECT_SNAPSHOT.md`](./memory/PROJECT_SNAPSHOT.md) — donne la vision en 3 minutes.
2. **Lire l'état réel** : [`../STATE.md`](../STATE.md) section « État production vérifié » et « Prochaines étapes par priorité ».
3. **Lire le plan MVP** : [`../.docs/10-mvp-completion-plan.md`](../.docs/10-mvp-completion-plan.md) — identifier le jalon courant (M1, M2 ou M3) et la sous-tâche courante.
4. **Lire les pièges** : [`PITFALLS.md`](./PITFALLS.md) — internaliser les erreurs déjà payées par le projet.
5. **Vérifier l'état distant** : `git fetch origin && git status && git log --oneline origin/main..HEAD`. Si la branche locale a divergé du remote, comprendre pourquoi avant d'agir.
6. **Vérifier la prod (si la tâche touche au backend)** : `curl -s https://filum-production-07bb.up.railway.app/health` → doit retourner `{"status":"ok","version":"0.1.0"}`.
7. **Annoncer le plan** : produire un plan court en réponse au développeur (3-7 étapes) **avant** d'exécuter quoi que ce soit qui modifie le repo. Attendre validation tacite (silence prolongé = aller-y prudemment) ou explicite.

Si tu sautes une étape, tu te mettras dans une situation que `STATE.md` ou `PITFALLS.md` te disent déjà comment éviter.

---

## Carte du dossier `agent/`

```
agent/
├── README.md                  # ce fichier
├── PERMISSIONS.md             # ce que l'agent peut/ne peut pas faire
├── GIT_WORKFLOW.md            # branches, PR, jamais de merge sur main
├── SECURITY.md                # secrets, scope, sandbox
├── PITFALLS.md                # erreurs déjà payées — ne pas reproduire
├── TASK_PROTOCOL.md           # cycle de vie d'une tâche
├── memory/
│   ├── INDEX.md               # index de la mémoire référencée
│   └── PROJECT_SNAPSHOT.md    # contexte projet condensé (3 min de lecture)
└── skills/
    ├── README.md              # index des skills disponibles
    ├── alembic-migrations.md
    ├── frontend-svelte.md
    ├── backend-fastapi.md
    ├── oauth-google.md
    ├── rate-limiting.md
    ├── ci-cd.md
    └── observability.md
```

---

## Articulation avec les autres fichiers du repo

```
┌────────────────────────────────────────────────────────────┐
│   Le développeur humain (Mathias)                          │
│   - Spec : .docs/*.md                                      │
│   - État : STATE.md (à jour à chaque session)              │
│   - Décisions : DECISIONS.md (historique ADRs)             │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          │ confie une tâche
                          ▼
┌────────────────────────────────────────────────────────────┐
│   L'agent (opencode/Big Pickle, Aider, Claude Code…)       │
│                                                            │
│   Lecture obligatoire au démarrage :                       │
│     1. agent/README.md (ce fichier)                        │
│     2. agent/memory/PROJECT_SNAPSHOT.md                    │
│     3. STATE.md (état réel)                                │
│     4. .docs/10-mvp-completion-plan.md (jalon courant)     │
│                                                            │
│   Référence permanente :                                   │
│     - agent/PERMISSIONS.md (avant chaque action sensible)  │
│     - agent/GIT_WORKFLOW.md (avant chaque op git)          │
│     - agent/PITFALLS.md (avant chaque commit)              │
│                                                            │
│   À la demande :                                           │
│     - agent/skills/<nom>.md (pour une tâche spécialisée)   │
│     - .docs/*.md (pour la spec produit)                    │
│     - CLAUDE.md / AGENTS.md (règles globales)              │
└─────────────────────────┬──────────────────────────────────┘
                          │
                          │ produit
                          ▼
┌────────────────────────────────────────────────────────────┐
│   Sortie attendue                                          │
│     - Code sur une branche `feat/...` ou `fix/...`         │
│     - Tests qui passent en local                           │
│     - PR ouverte (jamais mergée sans validation humaine)   │
│     - Mise à jour de STATE.md si l'état réel a changé      │
│     - Mise à jour de DECISIONS.md si décision non triviale │
└────────────────────────────────────────────────────────────┘
```

---

## Limites strictes (non négociables)

Ces règles ne peuvent JAMAIS être contournées, même si le développeur semble les autoriser dans une conversation ponctuelle. En cas de doute, refuser et demander confirmation explicite.

1. **Jamais de `git push` sur `main` directement.** Toujours via PR.
2. **Jamais de `gh pr merge`** sans une validation humaine explicite dans la conversation courante.
3. **Jamais de modification non-testable.** Si tu ne peux pas vérifier qu'un changement marche (test, curl, build), tu signales l'incertitude au lieu de prétendre que c'est fait.
4. **Jamais de secret en commit.** Toute clé, token, mot de passe → `.env` (gitignored) et `.env.example` mis à jour avec un placeholder.
5. **Jamais de migration Alembic destructive** sans plan de rollback documenté dans la PR.
6. **Jamais de changement du `canonical_hash` payload** des fiches signées (cf. `PITFALLS.md`).
7. **Jamais d'ajout de dépendance** sans justification dans la conversation.
8. **Jamais de modification de `.docs/00` à `.docs/09`** sans demande explicite. Ce sont des spécifications de référence figées. Les documents `10-…md` et au-delà (créés *par* l'agent et le dev) sont éditables.

---

## En cas de blocage

1. Ne pas inventer. Ne pas masquer. Ne pas livrer un fix partiel en prétendant qu'il est complet.
2. Documenter le blocage dans `STATE.md` (section « bloqué : … »).
3. Ouvrir une PR draft avec le travail partiel + une description claire de ce qui manque.
4. Reporter au développeur dans la réponse de la session.

---

*Ce dossier `agent/` évolue avec le projet. Toute amélioration de procédure découverte au fil du travail doit être consignée ici (par l'agent lui-même si pertinent, via une PR de type `docs:`).*
