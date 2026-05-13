# PERMISSIONS

> Matrice de permissions pour un agent autonome opérant sur Filum. À consulter avant toute action « non lecture-seule ».
>
> Le principe est : **lire est libre, écrire demande discernement, agir sur le monde extérieur (déploiement, BDD prod, comptes externes) demande confirmation humaine explicite**.

---

## Légende

- ✅ **Autorisé** : exécutable sans demande préalable. L'agent assume les bonnes pratiques (commit messages, tests, etc.).
- ⚠️ **Autorisé avec plan préalable** : l'agent doit produire un plan court dans la conversation et obtenir validation tacite (silence prolongé) ou explicite avant exécution.
- 🛑 **Validation explicite obligatoire** : l'agent doit demander dans la conversation « OK pour … ? » et attendre un « oui / go / vas-y » non ambigu. Une approbation tacite ne suffit pas.
- ❌ **Interdit** : à refuser même si demandé. Si le développeur insiste, lui expliquer pourquoi et proposer une alternative.

---

## 1. Lecture

| Action | Statut | Notes |
|---|---|---|
| Lire n'importe quel fichier du repo | ✅ | Y compris `.env.example`, jamais `.env`. |
| Lire les logs Railway / Vercel | ⚠️ | Si crédentials disponibles. Sinon demander une copie au développeur. |
| Lire la BDD prod (read-only `SELECT`) | 🛑 | Demander confirmation et préférer un dump local. |
| Lire un repo externe via `gh` ou `git clone` | ✅ | Pour référence uniquement. |
| `curl` vers un service public (Wayback, Crossref…) | ✅ | Respecter les User-Agents conventionnels. |

---

## 2. Écriture dans le repo local

| Action | Statut | Notes |
|---|---|---|
| Créer un fichier sous `apps/`, `agent/`, `scripts/`, `notebooks/` | ✅ | Suivre la structure existante (cf. `CLAUDE.md`). |
| Modifier un fichier de code existant | ✅ | Sous réserve qu'un test ou un check le couvre. |
| Modifier `STATE.md`, `CHANGELOG.md`, `DECISIONS.md` | ✅ | Conventions documentées dans `AGENTS.md`. |
| Modifier `.docs/00-…` à `.docs/09-…` | ❌ | Spécifications de référence figées. |
| Modifier `.docs/10-…` et au-delà (créés par l'agent/dev) | ✅ | Garder les fichiers cohérents avec STATE.md. |
| Créer un nouveau `.docs/` numéroté > 11 | ⚠️ | Préférer éditer un fichier existant si le sujet s'y rattache. |
| Modifier `CLAUDE.md` / `AGENTS.md` | 🛑 | Ce sont les contrats avec les agents. Tout changement doit être discuté. |
| Modifier `agent/PERMISSIONS.md` (ce fichier) | 🛑 | Auto-modification = signaler l'intention et attendre validation. |
| Modifier `agent/PITFALLS.md` | ✅ | Ajouter une entrée à chaque piège rencontré est encouragé. |
| Supprimer un fichier | ⚠️ | `git rm` plutôt que `rm`. Justifier dans le commit. |
| Renommer un fichier | ⚠️ | Vérifier les imports / liens cassés. |

---

## 3. Dépendances

| Action | Statut | Notes |
|---|---|---|
| Mettre à jour une dépendance existante via Dependabot PR | ✅ | Vérifier que la CI passe avant merge. |
| Ajouter une dépendance Python | 🛑 | Justifier dans la conversation. `uv add <pkg>` + lock + test. |
| Ajouter une dépendance Node | 🛑 | `pnpm add <pkg>` + lockfile commité. Pas de `pnpm add -g`. |
| Retirer une dépendance | ⚠️ | Vérifier qu'aucun import résiduel. |
| Changer la version de Python / Node | 🛑 | Stack non négociable (cf. `CLAUDE.md`). |
| Upgrade pnpm 10 → 11 | ❌ | Bloqué par ADR-013 et Q16 (`.docs/07-open-questions.md`). |

---

## 4. Git

| Action | Statut | Notes |
|---|---|---|
| `git checkout -b feat/...` ou `fix/...` ou `docs/...` | ✅ | Respecter `GIT_WORKFLOW.md`. |
| `git add` / `git commit` | ✅ | Conventional commits. Ne **pas** utiliser `--no-verify` sauf demande explicite. |
| `git push origin <branche-feature>` | ✅ | Jamais sur `main`. |
| `git push origin main` | ❌ | Toujours via PR squash-merge. |
| `git push --force` sur une branche perso | ⚠️ | OK si tu es seul dessus. Préférer `--force-with-lease`. |
| `git push --force` sur une branche partagée | ❌ | — |
| `git rebase` / `git merge` localement | ✅ | Préférer rebase sur main pour garder un historique propre. |
| `git reset --hard` | 🛑 | Demander confirmation. Sauvegarder l'état avant. |
| `gh pr create` | ✅ | Description claire, lien vers issue si pertinent. |
| `gh pr merge` | 🛑 | Toujours validation humaine explicite + voir `GIT_WORKFLOW.md`. |
| `git tag` | 🛑 | Les tags déclenchent éventuellement des actions. |
| Branche directement issue de `main` | ✅ | Toujours `git fetch origin && git checkout -b … origin/main`. |
| Travail sur `main` local | ❌ | Ne jamais éditer `main` directement, même en local. |

---

## 5. CI / Déploiement

| Action | Statut | Notes |
|---|---|---|
| Modifier un workflow `.github/workflows/*.yml` | 🛑 | Tout changement est sensible. Justifier. |
| `gh workflow run <name>` | ⚠️ | Si le workflow accepte `workflow_dispatch`. |
| `gh run rerun <id>` | ✅ | Re-trigger d'un run échoué. |
| Trigger un redéploiement manuel sur Railway | 🛑 | Railway redéploie auto sur push `main`. Demander si vraiment nécessaire. |
| Trigger un redéploiement sur Vercel | 🛑 | Idem. |
| Modifier les variables d'env Railway / Vercel | 🛑 | Action humaine via dashboard. L'agent ne peut pas. |
| Modifier `Dockerfile` / `docker-compose*.yml` | ⚠️ | Vérifier que le build passe en CI. |
| Modifier `pyproject.toml` / `package.json` (scripts) | ⚠️ | Tester localement avant push. |

---

## 6. Base de données

| Action | Statut | Notes |
|---|---|---|
| Créer une migration Alembic (`alembic revision`) | ✅ | Respecter strictement les règles de `agent/skills/alembic-migrations.md`. |
| Lancer `alembic upgrade head` en local | ✅ | — |
| Lancer `alembic upgrade head` en prod | 🛑 | Le `CMD` Docker Railway le fait au boot. L'agent n'a pas accès direct. |
| Lancer `alembic downgrade` en prod | ❌ | — |
| Modifier le schéma existant (DROP COLUMN, ALTER TYPE) | 🛑 | Plan de rollback obligatoire dans la PR. |
| `db.create_all()` en code (pas dans les tests) | ❌ | Toujours via Alembic. |
| Modifier `app/scripts/seed_demo.py` | ⚠️ | Vérifier que la fiche démo reste signable et que `canonical_hash` reste invariant. |
| Drop la BDD locale | ⚠️ | OK si tu peux la re-seeder. |

---

## 7. Comptes externes (OAuth, APIs)

| Action | Statut | Notes |
|---|---|---|
| Lire la doc API d'un service externe | ✅ | — |
| Appeler une API publique (Wayback, Crossref) | ✅ | Respecter rate limits. |
| Créer un projet OAuth Google / un compte tiers | ❌ | Action humaine, l'agent ne peut pas. |
| Configurer des secrets dans Railway/Vercel | ❌ | Action humaine. |
| Tester un OAuth flow en local avec ngrok | ⚠️ | Si crédentials de dev disponibles. |

---

## 8. Données utilisateur en prod

| Action | Statut | Notes |
|---|---|---|
| Lire des données utilisateur en prod | ❌ | RGPD. Demander un dump anonymisé si besoin. |
| Modifier des données utilisateur en prod | ❌ | — |
| Tester avec un compte créateur réel sans son consentement | ❌ | — |

---

## 9. Communication

| Action | Statut | Notes |
|---|---|---|
| Écrire un commit message | ✅ | Conventional commits. |
| Écrire la description d'une PR | ✅ | Inclure : motivation, changements clés, tests, points d'attention. |
| Mentionner @Mathias-PP dans une PR | ✅ | Si action attendue. |
| Ouvrir une issue GitHub | ⚠️ | Pour pousser une feature non demandée → préférer une suggestion dans la PR. |
| Écrire dans un autre repo | ❌ | Hors scope. |
| Envoyer un email / une notif | ❌ | Hors scope. |

---

## 10. Heuristiques quand un cas n'est pas listé

1. Est-ce réversible facilement (git revert, rebuild) ? → tendre vers ✅
2. Est-ce que ça touche `main`, la prod, des données utilisateur, ou des comptes externes ? → tendre vers 🛑
3. Est-ce que ça augmente la surface d'attaque (nouvelle dep, nouveau secret) ? → tendre vers 🛑
4. Est-ce que ça contredit un ADR ? → ❌ jusqu'à nouvel ADR
5. Est-ce que ça contredit `PITFALLS.md` ? → ❌
6. En vrai doute : demander dans la conversation. Le coût d'une question < coût d'une régression.

---

*Cette matrice est référencée par `agent/README.md` et utilisée par l'agent à chaque action. Si une règle te paraît trop restrictive ou pas assez, ouvre une PR `docs:` pour la modifier.*
