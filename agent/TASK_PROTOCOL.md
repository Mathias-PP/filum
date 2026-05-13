# TASK_PROTOCOL — cycle de vie d'une tâche pour un agent autonome

> Comment l'agent identifie ce qu'il a à faire, suit sa progression, et termine proprement. Conçu pour qu'**un agent puisse abandonner et reprendre** sans perte de contexte.

---

## 0. Principe directeur

L'agent doit pouvoir répondre à tout instant à ces trois questions, sans demander au développeur :

1. **Où j'en suis ?** (jalon courant, sous-tâche courante, fichiers touchés)
2. **Qu'est-ce qu'il me reste à faire ?** (sous-tâches à venir dans le jalon, jalons suivants)
3. **Qu'est-ce que je ne dois PAS faire ?** (anti-features, limites strictes, pièges)

Les réponses sont dans les fichiers du repo, jamais dans la mémoire de l'agent (qui meurt à la fin de la session).

---

## 1. Démarrage de session

### 1.1 Si c'est la première fois sur ce repo

1. Lire [`README.md`](../README.md) (vue d'ensemble)
2. Lire [`agent/README.md`](./README.md) (point d'entrée agent)
3. Lire [`agent/memory/PROJECT_SNAPSHOT.md`](./memory/PROJECT_SNAPSHOT.md) (contexte condensé)
4. Lire [`STATE.md`](../STATE.md) (état réel)
5. Lire [`.docs/10-mvp-completion-plan.md`](../.docs/10-mvp-completion-plan.md) (jalon courant)
6. Lire [`PITFALLS.md`](./PITFALLS.md) en entier

### 1.2 Si c'est une reprise (même journée ou session précédente)

1. Lire [`STATE.md`](../STATE.md) — c'est la source de vérité
2. `git status && git branch` — où suis-je ?
3. `git log --oneline -10` — qu'est-ce qui a bougé ?
4. `git fetch origin && git log origin/main..HEAD` — quelle est ma divergence avec main ?
5. Si une branche est en cours : `gh pr list --head <ma-branche>` — y a-t-il une PR ouverte ?
6. Si je vois un fichier modifié non-commité : comprendre pourquoi avant de continuer.

### 1.3 Annonce du plan

Avant d'écrire le moindre code ou commande mutante, produire dans la conversation :

```
**Plan**
- [ ] Étape 1 : <description courte>
- [ ] Étape 2 : <description courte>
- [ ] Étape 3 : <description courte>

Branche cible : `<feat/...>`
Risques : <1-2 phrases>
```

Le développeur peut interrompre. Silence prolongé = aller-y prudemment.

---

## 2. Pendant l'exécution

### 2.1 Journal de bord en cours de session

L'agent maintient, pour son propre suivi pendant la session :
- Une **liste de tâches courantes** (via l'outil TaskList si disponible, sinon dans un commentaire de PR draft).
- L'**état de chaque tâche** : `pending`, `in_progress`, `done`, `blocked`.
- Pour `blocked` : décrire le blocage et ce qui le débloquerait.

Si une tâche prend > 3 commits ou > 30 min de travail effectif sans avancée mesurable, l'agent **doit** s'arrêter et faire le point avec le développeur.

### 2.2 Cycle commit

```
1. Faire un changement cohérent (1 fichier ou 1 groupe de fichiers liés)
2. Lancer le check pertinent (lint, format, test)
3. git add <chemins explicites>           # JAMAIS git add .
4. git commit -m "<conventional commit>"
5. Si le commit casse quelque chose → revert immédiat, comprendre, recommencer
```

### 2.3 Découverte d'un piège nouveau

Si pendant la session l'agent rencontre une erreur dont la cause n'est pas dans [`PITFALLS.md`](./PITFALLS.md) :

1. La comprendre (cause racine, pas symptôme)
2. La fixer
3. **Ajouter une entrée dans `PITFALLS.md`** dans la même PR
4. Si la cause est subtile : ajouter aussi un ADR dans `DECISIONS.md`

### 2.4 Modification de scope en cours de route

Si l'agent réalise qu'une sous-tâche dépasse le scope initial :

1. **Ne pas** continuer en empilant. Stopper.
2. Décrire dans la conversation : « la sous-tâche X révèle un problème plus large, voici les options. »
3. Attendre arbitrage du développeur.

---

## 3. Fin de session

### 3.1 Avant de pousser

Checklist obligatoire :

- [ ] CI locale équivalente verte (lint, format, tests pertinents)
- [ ] Pas de fichier non lié dans le staging (`git diff --staged --stat`)
- [ ] Pas de secret en clair (cf. [`SECURITY.md`](./SECURITY.md) § 1)
- [ ] Commit messages en conventional commits
- [ ] Pas plus de 10 commits sur la branche (sinon : trop gros, splitter)

### 3.2 Push + PR

```bash
git push origin <ma-branche>
gh pr create --title "<type>: <description>" --body "$(cat <<'EOF'
<template de description, cf. GIT_WORKFLOW.md>
EOF
)"
```

### 3.3 Mise à jour de la mémoire projet

Si l'état réel du projet a changé (feature livrée, fix prod, déploiement), mettre à jour :

- [`STATE.md`](../STATE.md) — section « Phase courante » et « Prochaines étapes » + datestamp
- [`CHANGELOG.md`](../CHANGELOG.md) si la PR ajoute/change une feature visible
- [`DECISIONS.md`](../DECISIONS.md) si une décision non triviale a été prise
- [`.docs/10-mvp-completion-plan.md`](../.docs/10-mvp-completion-plan.md) si un jalon est complété

Ces mises à jour vont dans la **même PR** que le changement.

### 3.4 Rapport de session

Dans la dernière réponse de la session, l'agent produit :

```
**Session terminée**

PR ouverte : #<num> — <titre>
Branche : <feat/...>
État CI : <pending / 8/8 verts / X échecs>

Fait :
- ...

À valider par humain :
- merge de la PR (ne pas merger sans relire)
- éventuels secrets à configurer dans Railway / Vercel

Bloqueurs restants :
- ...

Pour la prochaine session :
- ...
```

---

## 4. Cas particuliers

### 4.1 La session expire / l'agent crashe en cours

À la reprise (même agent ou autre) :

1. Lire `STATE.md` (état réel)
2. `git status` (état local)
3. Si une branche existe avec des changements non poussés :
   - Vérifier les commits non poussés : `git log origin/<branche>..HEAD`
   - Si c'est cohérent : continuer le push
   - Si c'est désaligné : demander au développeur
4. Si une PR existe en draft : la reprendre en draft, pas en créer une nouvelle

### 4.2 Conflit avec une autre PR / un commit du développeur

```
git fetch origin
git rebase origin/main
# Résoudre les conflits
git push --force-with-lease origin <ma-branche>
```

Si le conflit est non trivial : stopper et demander.

### 4.3 La CI échoue après push

1. `gh run list --branch <ma-branche> --limit 3`
2. `gh run view <run-id> --log-failed`
3. Identifier la cause (souvent dans `PITFALLS.md`)
4. Fix → push → re-vérifier
5. Si l'échec n'est pas dans `PITFALLS.md` : l'ajouter avant le merge

### 4.4 Le développeur change d'avis en cours de session

Accepter le pivot, mais documenter :

```
Pivot accepté : <ancien plan> → <nouveau plan>.
Branche actuelle <ma-branche> : <abandonnée / continuée / mergée partiellement>.
```

Ne pas perdre le travail déjà fait sans le commit, même sur une branche destinée à être abandonnée (utile pour référence future).

---

## 5. Anti-patterns du protocole

- ❌ Commencer à coder sans plan
- ❌ Empiler 15 commits sur une branche avant d'ouvrir une PR
- ❌ Sauter la lecture de `STATE.md` parce que « je connais déjà le projet »
- ❌ Mettre à jour `STATE.md` dans une PR séparée du changement (désynchronisation garantie)
- ❌ Pousser un fix « rapide » sur main pour éviter le passage par PR
- ❌ Marquer une tâche « done » alors que les tests ne passent pas
- ❌ Inventer des fichiers ou des fonctions qui n'existent pas (vérifier avant de référencer)

---

## 6. Indicateurs de qualité d'une session

Une bonne session laisse derrière elle :
- 1 (ou max 2) branches avec des PR claires
- `STATE.md` à jour
- 0 fichier non-commité orphelin
- 0 entrée TODO dans le code sans issue associée
- `PITFALLS.md` enrichi si un nouveau cas a été rencontré
- Un rapport clair dans la conversation finale

Une mauvaise session laisse :
- 3+ branches abandonnées
- `STATE.md` désynchronisé
- des `// TODO: comprendre ça` dans le code
- des commits « WIP » sur main
- un développeur qui doit deviner ce qui s'est passé

---

*Ce protocole est la colonne vertébrale de l'autonomie. Sans lui, l'agent devient un assistant qui demande tout, plus qu'un pair qui exécute.*
