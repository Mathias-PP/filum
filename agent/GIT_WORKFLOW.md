# GIT_WORKFLOW

> Règles git et devops pour un agent autonome sur Filum. Le projet est solo + IA assistante : pas de room pour des branches fantômes ou des merges sauvages.

---

## Vérité de base

- `main` est la branche de production. Railway et Vercel y redéploient automatiquement à chaque push (cf. ADR-015).
- **Push sur `main` = déploiement immédiat en prod**. Toujours via PR squash-merge.
- Une CI rouge ≠ une CI à ignorer. Si la CI casse, on fixe avant tout autre travail.

---

## Quand créer une branche, quand ne pas en créer

### Créer une branche ✅

Toute modification qui rentre dans **au moins** une de ces catégories :

- Ajout/modification de logique métier (feat:, fix:)
- Ajout/modification d'une migration Alembic
- Changement de schéma frontend (composant, route, store)
- Modification d'un workflow CI
- Changement de dépendance majeure
- Documentation structurelle (`.docs/`, `agent/`, `CLAUDE.md`, `AGENTS.md`)

### Ne pas créer une branche, mais éditer en local + commit sur la branche courante ⚠️

Uniquement si :
- L'agent est explicitement en train de finaliser une branche existante.
- Le commit corrige un bug qui empêche le test local de la même branche.

### Travailler en local sans commit 🛑

Pour de l'exploration brouillon. Mais **ne jamais** laisser une session se terminer avec des modifications non-commitées sans avertir le développeur.

---

## Nomenclature des branches

| Préfixe | Usage | Exemple |
|---|---|---|
| `feat/` | Nouvelle fonctionnalité | `feat/oauth-google-callback` |
| `fix/` | Correction de bug | `fix/wayback-rate-limit-retry` |
| `docs/` | Documentation pure (aucun code) | `docs/agent-autonomy-and-mvp-strategy` |
| `chore/` | Maintenance, deps, CI | `chore/bump-vite-plugin-svelte-vitest` |
| `refactor/` | Réorganisation sans changement de comportement | `refactor/services-card-split` |
| `test/` | Ajout de tests uniquement | `test/auth-integration-cookie-flow` |

**Format** : `<préfixe>/<sujet-court-kebab-case>`. Max 50 caractères au total.

**Une branche = un objectif unique**. Si tu te retrouves à mélanger un feat OAuth avec une refacto crypto, c'est deux branches.

---

## Anti-multiplication des branches

- **Ne pas créer une branche par fichier** modifié. Une branche = un objectif logique.
- **Ne pas créer une branche « exploration »** qui ne sera pas mergée. Préférer un commit dans un fichier `scratch/` gitignored ou un commit `chore: WIP` clairement marqué.
- **Ne pas garder des branches mergées localement**. Après merge de PR :
  ```bash
  git checkout main
  git pull origin main
  git branch -d <branche-mergée>
  ```
- **Ne pas relancer une PR pour un changement de virgule**. Si tu viens d'ouvrir une PR et tu vois un typo, push le fix sur la même branche.

---

## Cycle de vie d'une PR (cas standard)

```
1. git fetch origin
2. git checkout -b feat/X origin/main
3. [travail]
4. uv run ruff format app/        # backend, AVANT chaque commit (cf. PITFALLS)
   pnpm run lint && pnpm run format
5. uv run pytest tests/ -v        # ou tests pertinents
   pnpm run check
6. git add <fichiers ciblés, jamais git add .>
7. git commit -m "feat: <description impérative ≤ 50 char>"
8. git push origin feat/X
9. gh pr create --title "feat: ..." --body "<voir template ci-dessous>"
10. Vérifier que la CI passe (8 jobs verts)
11. ARRÊT. Attendre validation humaine pour le merge.
```

---

## Template de description de PR

```markdown
## Motivation

[1-3 phrases : pourquoi cette PR existe. Lien vers le jalon de
.docs/10-mvp-completion-plan.md ou l'issue.]

## Changements

- [bullet list des changements clés, fichier(s) touchés entre parenthèses]
- ...

## Tests

- [comment c'est testé : pytest, vitest, curl, manuel]
- [résultat : ex. "41 tests verts"]

## Vérifications avant merge

- [ ] CI 8/8 verte
- [ ] Pas de nouveau secret commité (scan TruffleHog clean)
- [ ] Pas de migration destructive sans plan de rollback
- [ ] STATE.md mis à jour si l'état réel change
- [ ] DECISIONS.md mis à jour si décision non triviale
- [ ] PITFALLS.md mis à jour si un nouveau piège a été rencontré

## Points d'attention

[Ce que le reviewer doit regarder en priorité. Ex: bascule cookie samesite,
nouvelle dep, refacto sensible.]

## Captures d'écran (si UI)

[obligatoire pour toute modif visible côté frontend]
```

---

## Vérification AVANT `gh pr merge`

**Cette section est issue d'un cas vécu** : un commit de fix poussé en dernier n'a pas été inclus dans le squash. Cause exacte non élucidée. Procédure obligatoire :

```bash
git fetch origin
git log --oneline origin/<ma-branche> -5
# Comparer avec ta vue locale et la diff sur l'UI GitHub.
# Si un commit manque côté origin → re-pousser puis attendre la CI.
gh pr view <numéro> --json commits
# Vérifier que le dernier commit est bien celui que tu attends.
```

Si TOUT est aligné ET que tu as une validation humaine explicite :

```bash
gh pr merge <numéro> --squash --delete-branch
```

Le `--delete-branch` est obligatoire (anti-multiplication). Le `--squash` est obligatoire (un commit propre par PR sur `main`).

---

## Anticipation : avant de pousser, est-ce que ça passera la CI ?

8 jobs sur main, tous doivent rester verts :

| Job | Comment l'anticiper en local |
|---|---|
| Security Scan (Trivy + TruffleHog) | `git diff --staged` : aucun token, clé, mot de passe |
| Lint Backend (ruff) | `cd apps/backend && uv run ruff check .` puis `uv run ruff format .` |
| Type Check Backend (mypy) | `cd apps/backend && uv run mypy app/ --ignore-missing-imports` |
| Test Backend (pytest) | `cd apps/backend && uv run pytest tests/ -v` (⚠️ ne passe pas sur Windows — voir `PITFALLS.md`) |
| Lint Frontend (eslint+prettier) | `cd apps/frontend && pnpm run lint` |
| Test Frontend (vitest) | `cd apps/frontend && pnpm run test` |
| Build Frontend (vite, frozen lockfile) | `cd apps/frontend && pnpm install --frozen-lockfile && pnpm run build` |
| Analytics Check (dbt compile) | `cd apps/analytics && uv run dbt compile` |

**Règle** : avant `git push`, lancer au minimum le lint et le format. Idéalement, lancer aussi les tests pertinents au scope de la PR.

---

## Gestion des conflits avec `main`

Si pendant que tu travailles, `main` avance :

```bash
git fetch origin
git rebase origin/main
# Résoudre les conflits fichier par fichier.
# Pour chaque conflit :
#   git add <fichier>
#   git rebase --continue
git push --force-with-lease origin <ma-branche>
```

Préférer `rebase` à `merge` pour garder un historique linéaire. Préférer `--force-with-lease` à `--force` (rejette si quelqu'un d'autre a pushé entretemps).

---

## Cas particuliers

### Migration Alembic en cours dans une PR concurrente

Si une autre PR ajoute une migration `00X_...` et la tienne aussi : conflit logique sur l'ID. Résoudre en :
1. Rebase sur main
2. Renommer ta migration en `00X+1_...`
3. Mettre à jour le `down_revision` de ta migration
4. Tester `alembic upgrade head` en local

### Branche que tu n'as pas créée

Si tu reprends une branche existante (ex: PR draft du dev) :
1. `git fetch origin && git checkout <branche>`
2. `git log --oneline -10` pour comprendre l'état
3. Lire la description de la PR
4. **Ne pas force-push** sans demander, même si tu as le droit techniquement.

### CI rouge

1. `gh run list --branch <ma-branche> --limit 3`
2. `gh run view <run-id> --log-failed`
3. Identifier la cause exacte (souvent dans `PITFALLS.md`)
4. Fix → push → vérifier
5. Ne **jamais** désactiver un check juste pour faire passer

---

## Re-trigger d'une CI sans changement

Parfois utile (ex: timeout réseau) :

```bash
git commit --allow-empty -m "ci: retrigger"
git push origin <ma-branche>
```

---

## Hygiène des commits

- Un commit = un changement cohérent. Pas de « tout en vrac ».
- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`, `ci:`, `perf:`, `data:`).
- Titre impératif, ≤ 50 char, sans point final.
- Corps optionnel pour les changements complexes (≤ 72 char par ligne).
- **Jamais** de mention « Co-authored-by » de l'agent IA. Le commit est attribué au développeur, l'agent est un outil.
- Pas de signature crypto GPG sauf demande explicite.

---

## Anti-patterns à refuser

- ❌ `git commit --amend` après push sur une branche partagée
- ❌ `git push --force` sans `--force-with-lease`
- ❌ `git rebase -i` interactif (l'agent ne peut pas répondre à l'éditeur)
- ❌ Mélanger doc + code dans une même PR si la doc est conséquente — splitter
- ❌ Branche dont le nom ne dit rien (`feat/wip`, `fix/stuff`)
- ❌ Mettre plus de 10 commits sur une branche feature avant PR — c'est qu'elle est trop grosse

---

## Référence : conventions internes Filum

- CLI git via WSL uniquement (`git` Windows pas dans le PATH).
- `gh` CLI authentifié via WSL.
- `_commit_msg.txt` gitignored — utiliser `git commit -F _commit_msg.txt && rm _commit_msg.txt` pour des messages multi-lignes complexes.

---

*Toute violation de ce workflow constatée doit être consignée dans `PITFALLS.md` avec la cause racine pour ne plus la reproduire.*
