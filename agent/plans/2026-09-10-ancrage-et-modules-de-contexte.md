# Plan. Modules de contexte, impossibilité d'inventer, juge de fidélité

> **Pour l'agent qui exécute.** Une PR à la fois : merger, déployer, valider en
> production, passer à la suivante. Français partout, aucun tiret cadratin nulle
> part (prose, code, commit, corps de PR). Ne jamais lancer `python -m pytest`,
> il n'existe pas dans cet environnement : `uv run pytest` depuis `apps/backend`.
>
> **Source.** Ce plan exécute [`agent/audit/10-externes/06-modules-de-contexte-agent.md`](../audit/10-externes/06-modules-de-contexte-agent.md)
> et la partie Q3a de [`05-fidelite-des-affirmations-conception.md`](../audit/10-externes/05-fidelite-des-affirmations-conception.md).
> ARS est sous **CC BY-NC 4.0** : aucune ligne de son code ni de sa prose n'entre
> dans Philum. Tout ce qui suit est écrit de zéro.

---

## État courant

PR 1 en cours sur la branche `feat/agent-modules-de-contexte`. Mesure faite sur
le disque après câblage : le gabarit `shared/` émet **42 450** caractères, le seed
passe à **31** fichiers, et le contexte le plus lourd est celui de `assistant`
(42 427 émis) contre un plafond relevé à 60 000.

**PR 1, `feat/agent-modules-de-contexte`**

- [x] 1.1 Relever `_PRIMING_MAX` de 40 000 à 60 000
- [x] 1.2 Créer `shared/rien-de-memoire.md`
- [x] 1.3 Créer `shared/qualite-des-sources.md`
- [x] 1.4 Créer `shared/chercher-la-contradiction.md`
- [x] 1.5 Créer `agents/socratique.yaml`
- [x] 1.6 Câbler les modules dans les six rôles existants
- [x] 1.7 Fondre l'élargissement interdisciplinaire dans `rechercheur.yaml`
- [x] 1.8 Mettre à jour `AGENTS.md` (folder map, routing, limites strictes)
- [x] 1.9 Tests : budget de priming, socratique sans outil d'écriture
- [x] 1.10 Corriger la fiche 06 (§3 sur `add_source`, §7 sur l'activation)
- [ ] 1.11 Vérifier, PR, merge, déployer, valider les quatre points en production

**PR 2, `fix/agent-annotation-sans-entourage`**

- [ ] 2.1 Helper `_entourage_du_passage`
- [ ] 2.2 `annotate_excerpt` refuse au lieu de se rabattre
- [ ] 2.3 Le docstring nomme la conséquence
- [ ] 2.4 Trois tests, plus la réécriture du test qui dépendait du repli
- [ ] 2.5 Vérifier, PR, merge, déployer, valider

**PR 3, `feat/sources-metadonnees-resolues`**

- [ ] 3.7 Instruire d'abord les quatre points listés (bloquant)
- [ ] 3.3 Paramètre `metadata_from`
- [ ] 3.4 Migration 058 (`metadata_origin`, avec `downgrade`)
- [ ] 3.5 Sensibilité par valeur de paramètre
- [ ] 3.6 Contrat MCP et API, régénération `openapi.json` et `generated.ts`
- [ ] Vérifier, PR (mentionner la rupture de contrat MCP), merge, déployer

**PR 4, `feat/sources-retraction-perimee`**

- [ ] 4.1 `DUREE_DE_VALIDITE` et `est_perime`, en datetime naïf
- [ ] 4.2 Gravité du motif de rétractation, défaut `verifier`
- [ ] 4.3 Script de re-contrôle, idempotent et borné
- [ ] 4.4 Migration 059 (`retraction_reason`, `retraction_gravite`)
- [ ] 4.5 Contrat API, régénération
- [ ] Vérifier, PR, merge, déployer

**PR 5, `feat/agent-juge-de-fidelite`**

- [ ] 5.9 Instruire d'abord les trois points listés (bloquant)
- [ ] 5.2 Appel bloquant sur la clé du créateur
- [ ] 5.3 Séparation générateur / vérificateur, déclassement du positif non étayé
- [ ] 5.4 Vocabulaire fermé à six valeurs, aucun score numérique
- [ ] 5.5 État « non mesuré » affiché
- [ ] 5.6 Migration 060 (quatre colonnes nullables sur `source_excerpts`)
- [ ] 5.7 Réglage par créateur
- [ ] 5.8 Tests sous `MockTransport`, six cas
- [ ] Vérifier, PR, merge, déployer

---

## Mesures faites sur le disque le 2026-09-10

Chaque chiffre ci-dessous a été relevé, pas estimé. Ils gouvernent les décisions
du plan.

| Fait | Ancre | Valeur |
|---|---|---|
| Plafond du contexte workspace injecté | `app/services/agent.py:197` | `_PRIMING_MAX = 40_000` (caractères, pas octets) |
| En-tête du bloc de priming | `agent.py:245` | 41 caractères |
| Bloc par fichier | `agent.py:248` | `len(path) + len(content) + 7` |
| `shared/` aujourd'hui, en caractères émis | mesuré | **34 357**, marge **5 643** |
| Détail | `garde-fous.md` 4 721, `philum-mcp.md` 11 000, `pieges-vecus.md` 7 900, `principes-editoriaux.md` 7 483, `style-redactionnel.md` 3 057 | |
| Le chat résout toujours un agent | `app/api/v1/endpoints/agent_chat.py:153-154` | `session.agent_slug or SLUG_DEFAUT` |
| Donc `chemins` vaut la liste `context:` du YAML | `agent.py:1297-1299` | et non `None`, sauf si `assistant.yaml` a été supprimé |
| Le seed paresseux n'agit que sur un workspace vide | `agent_workspace.py:420-426` | un créateur existant ne reçoit rien automatiquement |
| La resynchro existe et est déjà câblée en UI | `POST /agent/workspace/sync`, `dashboard/workspace/+page.svelte:253`, bouton « Mettre à jour » | **aucune migration n'est nécessaire pour livrer un fichier de seed** |
| `ruff` ignore le dossier de seed | `pyproject.toml:81` `exclude = ["app/agent_workspace_seed"]` | les `.md` et `.yaml` ajoutés ne sont ni lintés ni reformatés |
| Le parser d'agent ignore les clés YAML inconnues | `app/services/agent_definitions.py:79-120` | mais valide slug/chemin, `tools` non vide et tous connus, `context` normalisé, `layer` dans L0..L4 |
| `add_source` vérifie déjà l'existence | `tools_write.py:338`, appel de `verifier_que_la_source_existe(url, doi)` | domaine inexistant, 404/410 et DOI inconnu de Crossref sont déjà refusés |
| Repli d'entourage de `annotate_excerpt` | `tools_write.py:1552-1554` | `source.title` + `source.annotation` |
| `suggest_annotation` accepte un gros entourage | `llm.py:618-620` | `entourage[:6000]`, `passage[:2000]` |
| Le modèle `Source` porte déjà la péremption | `models/source.py:154-156` | `retraction_status`, `retraction_notice_doi`, `retraction_checked_at` |
| `SourceExcerpt` n'a aucun champ de verdict de fidélité | `models/source_excerpt.py` | `verified_*` porte l'ancrage, pas la fidélité |
| Tête d'Alembic | `alembic/versions/` | `057_lane_secours_modele_distinct` |
| Appel LLM non bloquant sur la clé du créateur | `services/llm_adapters.py` | `url_et_headers`, `format_chat_payload(..., stream=False)`, `parse_blocking_response` |

**Correction à porter dans la fiche 06 (faite en PR 1).** Le §3 affirme que
`add_source` « accepte titre, auteurs, date, DOI, éditeur, en texte libre. Rien
n'oblige ces valeurs à venir de la page ou d'un résolveur. » C'est faux pour
l'URL et le DOI, déjà résolus. Ne restent réellement libres que `title`,
`authors`, `journal`, `published_at`, `publisher` et `annotation`.

---

## Les deux questions ouvertes, et comment ce plan les tranche

### Q7 de la fiche 06 : faut-il un champ d'activation des modules ?

**Non.** Le mécanisme d'activation existe déjà et c'est la liste `context:` de
`agents/*.yaml`. Le chat résout toujours un agent (`agent_chat.py:153`), donc le
chemin « tout `shared/` » n'est emprunté que si le créateur a supprimé
`assistant.yaml`. Ajouter un champ de frontmatter créerait une seconde maison
pour le même fait, ce que `agent_definitions.py` interdit explicitement dans son
docstring d'ouverture (« Une seule maison par fait, invariant ICM »).

Le créateur qui ne veut pas d'un module a déjà deux gestes : retirer la ligne de
son `agents/*.yaml`, ou supprimer le fichier de son workspace. Les deux
fonctionnent aujourd'hui, sans une ligne de code en plus.

### Le plafond de priming

Les trois modules écrits en PR 1 pèsent 2 396, 2 960 et 2 627 caractères, soit
**8 093** caractères émis enveloppes comprises. L'assistant passerait de 34 357 à
**42 450**, donc au-dessus de `_PRIMING_MAX = 40_000`. La troncature est un `break`
(`agent.py:249-250`) sur une liste triée par chemin : les deux fichiers perdus
seraient `shared/rien-de-memoire.md` et `shared/style-redactionnel.md`, en
silence, dans le prompt de tous les agents généralistes.

Le plan **relève le plafond à 60 000** et pose un test qui échoue le jour où le
gabarit `shared/` repasse au-dessus. C'est le test qui compte, pas le nombre.

---

## Commandes de référence

```bash
# Backend, depuis apps/backend
rm -f test.db && CI=true uv run pytest tests/unit tests/integration -q
uv run ruff check app/ && uv run ruff format app/ && uv run mypy app/ --ignore-missing-imports
CI=true uv run python -m app.scripts.export_openapi

# Frontend, depuis apps/frontend
pnpm run check && pnpm run lint && pnpm test
pnpm run generate:api           # apres modif de openapi.json
npx prettier --write <fichier>  # obligatoire avant commit sur .svelte et generated.ts

# PR (le token gh n'a pas le scope read:org : --body-file echoue, passer --body)
gh pr create --title "..." --body "..." --base main
gh pr view <n> --json statusCheckRollup \
  --jq '[.statusCheckRollup[]|select(.state!="SUCCESS" and .state!="SKIPPED")]|length'   # doit rendre 0
gh pr merge <n> --squash

# Deploy VM (deux etapes)
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  "sudo -n -u mathias_pinault bash -c 'cd ~/filum && git pull --ff-only origin main'"
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  "sudo -n bash -c 'cd /home/mathias_pinault/filum/infra/oracle && \
   docker compose -f docker-compose.micro.yml up -d --build backend'"
curl -s https://philum-api.duckdns.org/health
```

---

## Ordre d'attaque

| # | Branche | Contenu | Taille | Migration | Contrat API |
|---|---|---|---|---|---|
| 1 | `feat/agent-modules-de-contexte` | trois modules `shared/`, rôle socratique, plafond de priming | M | non | non |
| 2 | `fix/agent-annotation-sans-entourage` | `annotate_excerpt` refuse au lieu de se rabattre | S | non | non |
| 3 | `feat/sources-metadonnees-resolues` | le modèle choisit un résolveur, il ne saisit pas les métadonnées | L | oui (058) | oui |
| 4 | `feat/sources-retraction-perimee` | une vérification de rétractation se périme, et gradue son motif | M | oui (059) | oui |
| 5 | `feat/agent-juge-de-fidelite` | juge Q3a, optionnel, non mesuré, verdict privé | L | oui (060) | oui |

---

# PR 1, `feat/agent-modules-de-contexte`

Contenu de workspace et un seul entier changé. Aucune migration, aucun endpoint,
aucun contrat API. C'est la PR la plus sûre du lot et elle porte le gros de la
valeur des fiches 04 à 06.

**Où éditer.** Les chemins ci-dessous sont ceux du snapshot, mais la source est
`workspaces/createur-de-fiches/` à la racine du dépôt : même arborescence, sans
le préfixe `apps/backend/app/agent_workspace_seed/`. On édite la source, puis on
lance `uv run python -m app.scripts.build_workspace_seed` depuis `apps/backend`
pour regeler le snapshot. Voir le piège correspondant en fin de plan.

**Fichiers créés**

- `apps/backend/app/agent_workspace_seed/shared/rien-de-memoire.md`
- `apps/backend/app/agent_workspace_seed/shared/qualite-des-sources.md`
- `apps/backend/app/agent_workspace_seed/shared/chercher-la-contradiction.md`
- `apps/backend/app/agent_workspace_seed/agents/socratique.yaml`

**Fichiers modifiés**

- `apps/backend/app/services/agent.py` (le plafond)
- `apps/backend/app/agent_workspace_seed/AGENTS.md` (folder map et routing)
- `apps/backend/app/agent_workspace_seed/agents/{assistant,bibliographe,extracteur,rechercheur,redacteur,relecteur}.yaml`
- `apps/backend/tests/unit/test_agent_workspace.py`
- `agent/audit/10-externes/06-modules-de-contexte-agent.md` (§3 et §7)

---

### 1.1 Relever le plafond de priming

Dans `apps/backend/app/services/agent.py`, remplacer les lignes 196-197 :

```python
#: Taille max du contexte workspace injecté dans le prompt système.
_PRIMING_MAX = 40_000
```

par :

```python
#: Taille max, en caractères, du contexte workspace injecté dans le prompt
#: système. Le gabarit `shared/` complet en émet 42 000 environ depuis l'ajout
#: des trois modules d'ancrage : à 40 000, la troncature de `_priming_workspace`
#: est un `break` sur une liste triée par chemin, et elle perdait en silence
#: `rien-de-memoire.md` puis `style-redactionnel.md`. Le garde-fou n'est pas ce
#: nombre, c'est `test_le_seed_shared_tient_sous_le_plafond`, qui échoue le jour
#: où le gabarit repasse au-dessus.
_PRIMING_MAX = 60_000
```

Rien d'autre ne change dans la fonction : la troncature reste un dernier recours
pour un workspace où le créateur a écrit lui-même des fichiers volumineux.

---

### 1.2 `shared/rien-de-memoire.md`

Contenu exact du fichier, à copier tel quel :

```markdown
---
contract: "Ce qui doit venir de la session, ce qui peut venir du modele, et comment declarer un manque."
layer: L3
---
# Rien de mémoire

La règle n'est pas « n'invente pas ». C'est une priorité : quand la matière de
la session et la mémoire du modèle se contredisent, la session gagne, toujours.
Formulée en interdiction pure, la règle rendrait l'agent muet.

## Ce qui doit venir de la session

Vient de la session tout ce qui peut être faux : un fait, un chiffre, une date,
un nom d'auteur, un titre, un DOI, un éditeur, un verbatim, et l'existence même
d'une source. « De la session » veut dire : d'une page ouverte au cours de ce
tour, d'une réponse de résolveur (Crossref, OpenAlex, métadonnées de la page),
d'un fichier du workspace, ou du créateur lui-même.

Une source dont tu te souviens n'est pas une source. Tant qu'une requête ne l'a
pas rendue, elle n'existe pas.

## Ce qui peut venir du modèle

La langue. La grammaire, le vocabulaire, l'ordre des idées, la mise en forme, le
choix d'un mot juste. Cette compétence est la tienne et personne ne demande de
la sourcer.

La frontière est nette : tu formules librement, tu n'affirmes rien librement.

## Déclarer un manque

Quand la matière ne couvre pas un point, tu ne combles pas. Tu poses le manque
et tu continues.

- Dans une réponse au créateur : une phrase qui nomme ce qui manque et ce qu'il
  faudrait pour le combler. « La date de publication n'est ni sur la page ni
  dans Crossref ; il faudrait la chercher ailleurs, ou la laisser vide. »
- Dans un champ de fiche : rien. Un champ vide est un état affichable, une
  approximation ne l'est pas.
- Dans un fichier de `runs/` : une ligne commençant par `MANQUE :`, que le
  créateur retrouve par recherche.

Un manque déclaré est un résultat de travail. Un manque comblé est une faute qui
ne se voit pas.

## Le cas particulier : affirmer une absence

« Aucune étude ne dit X », « personne n'a testé Y », « il n'existe pas de
travaux sur Z ». Aucune source ne peut étayer une phrase pareille : c'est une
affirmation portant sur tout ce qui n'a pas été trouvé.

Elle ne se pose donc jamais comme un fait. Elle se pose comme le compte rendu
d'une recherche : ce qui a été cherché, avec quels termes, sur quel périmètre,
et ce que cela a rendu. « Une recherche sur "X" et "Y" dans les moteurs
disponibles n'a rien rendu » est vérifiable. « Il n'existe rien » ne l'est pas.
```

---

### 1.3 `shared/qualite-des-sources.md`

```markdown
---
contract: "Trois questions a poser a toute source, dans tout domaine, avant de la retenir."
layer: L3
---
# Qualité d'une source : trois questions, aucun classement

Il n'y a pas de hiérarchie de sources chez Philum. Une échelle qui met les
méta-analyses en haut et les témoignages en bas est une échelle de médecine :
appliquée à la cuisine, à l'histoire ou au droit, elle décrète que ces domaines
ne citent jamais rien de bon.

À la place, trois questions. Elles valent partout, et il n'existe aucun sujet où
l'on puisse répondre « ici, la question ne se pose pas ».

## 1. De quelle nature est cette preuve ?

Nommer, pas noter. Mesure, expérience, témoignage direct, document d'époque,
démonstration, texte de loi, déclaration d'un acteur, synthèse d'autres travaux,
reportage, opinion argumentée.

Le nom se met en clair dans la mise en situation de l'extrait, ou dans
l'annotation de la source. Le lecteur doit savoir ce qu'il lit avant de savoir
s'il y croit.

## 2. Est-ce la meilleure preuve disponible pour ce qui est affirmé ici ?

La question n'est jamais « cette source est-elle bonne ». Toujours « est-elle
bonne pour cette affirmation-là ».

Une recette exécutée par un chef est la meilleure preuve qui existe d'une
technique de cuisine, et n'est aucune preuve d'un mécanisme physico-chimique. Un
article de science alimentaire est exactement l'inverse. Un document d'archive
est la meilleure preuve d'un fait d'histoire, et ne dit rien de la lecture qu'en
fait la recherche aujourd'hui.

Quand la meilleure preuve disponible dans le domaine est faible, on la prend et
on le dit. On ne la remplace pas par une source d'un autre domaine qui a l'air
plus solide mais ne parle pas de la même chose.

## 3. Est-elle ce qu'elle prétend être ?

Un objet peut porter tous les signes extérieurs de sa catégorie sans en être.
Cela vaut dans tous les domaines, pas seulement pour les revues scientifiques.

Signaux qui appellent une vérification avant de retenir la source :

- Un site qui a la forme d'un média mais dont aucun article n'est signé, ou dont
  tous le sont du même nom générique.
- Une page d'encyclopédie sans historique d'édition, sans auteur, sans
  bibliographie.
- Un agrégateur qui republie sans dire d'où vient le texte. Le citer, c'est
  attribuer à la mauvaise personne : remonter à l'original.
- Une vidéo ou un article qui a la forme d'un documentaire ou d'une enquête, et
  qui est un contenu de marque ou un plaidoyer. La forme n'est pas la nature.
- Un communiqué de presse ou un billet d'institution donné pour une étude. Le
  communiqué renvoie presque toujours à l'étude : c'est elle qu'on cite.
- Une revue dont les frais de publication sont mis en avant plus que le comité
  de lecture, dont le délai annoncé se compte en jours, ou dont le périmètre
  couvre toutes les disciplines à la fois.

Un doute non levé se dit dans l'annotation. Il ne disqualifie pas
automatiquement la source, mais le lecteur doit l'avoir.
```

---

### 1.4 `shared/chercher-la-contradiction.md`

```markdown
---
contract: "Aller chercher ce qui nuance ou contredit, et savoir dire qu'on n'a rien trouve."
layer: L3
---
# Chercher la contradiction

Le mode de défaillance principal d'une fiche est la sélection favorable : citer
cinq travaux qui vont dans le sens de la thèse et taire les douze qui n'y vont
pas. Il ne se corrige pas en interdisant quelque chose. Il se corrige en
cherchant.

## L'injonction

Sur toute affirmation contestée de la fiche, tu cherches activement ce qui la
nuance ou la contredit, et tu le proposes au créateur. Ce n'est pas une option
que tu prends s'il te reste du temps : c'est une étape de la collecte, au même
titre que la recherche principale.

Une recherche n'est pas finie tant que tu n'as pas cherché dans l'autre sens. Si
la première requête est « X améliore Y », la seconde est « limites de X », « X
ne fonctionne pas », « critique de X », « réplication de X ».

## Ne rien trouver est un résultat

Ne rien trouver se dit, avec la recherche qui a été menée : quels termes, quel
périmètre. C'est ce qui distingue « le sujet fait consensus » de « je n'ai
cherché que dans un sens ».

Ne pas avoir cherché n'est pas un résultat. Ne le présente jamais comme tel.

## Où cela se pose dans la fiche

Le champ `stance` d'une source accueille `nuance-contredit`. Il ne se pose que
si tu as lu un extrait où la source dit clairement autre chose : la règle est
dans `garde-fous.md` et ne change pas ici. Ce qui manquait n'était pas le champ,
c'était l'obligation d'aller chercher de quoi le remplir.

Une fiche dont toutes les sources appuient n'est pas suspecte en soi. Elle
mérite une question posée au créateur, pas un reproche : le sujet est-il
consensuel, ou la recherche a-t-elle été menée dans un seul sens ?

## La contradiction la plus utile n'est pas toujours une étude contraire

Souvent c'est un cadrage contraire. Le même problème réel, redéfini depuis un
autre champ, produit d'autres questions et d'autres réponses. Une question de
santé publique redéfinie en question économique, une question technique
redéfinie en question d'usage : ce n'est pas la même littérature, et elle ne
contredit pas point par point, elle déplace.

## Deux gestes à ne pas confondre avec un argument

- **L'appel à l'autorité.** Publié dans une revue prestigieuse, donc valide. Le
  lieu de publication est un indice sur le sérieux du processus, jamais une
  preuve du résultat.
- **L'appel à la nouveauté.** Plus récent, donc meilleur. Une étude de cette
  année qui contredit dix ans de résultats convergents est une piste, pas une
  conclusion. La date compte quand le sujet bouge vite ; elle ne classe pas.
```

---

### 1.5 `agents/socratique.yaml`

Le point important : **la non-génération n'est pas une consigne, c'est l'absence
d'outils.** `boucle()` appelle `filtrer(registre, agent_def.tools)`
(`agent.py:1295`), donc dans ce rôle aucun outil d'écriture n'est exposé au
modèle. C'est la doctrine de la fiche 06 appliquée à un rôle.

Les six noms d'outils ci-dessous sont tous présents dans `assistant.yaml`, donc
tous dans `noms_outils_connus()` : le fichier passera la validation.

```yaml
slug: socratique
name: Socratique
contract: "Questionne le createur pour lui faire formuler ce que sa fiche affirme. N'ecrit rien et ne propose aucun contenu."
layer: L2
model_hint: null
tools:
  - fs_read
  - fs_list
  - fiche_state
  - get_my_card
  - list_sources
  - search_my_excerpts
context:
  - shared/chercher-la-contradiction.md
  - shared/rien-de-memoire.md
system_prompt: |
  Tu ne réponds pas, tu questionnes. Ton but est que le créateur formule
  lui-même ce que sa fiche affirme, sur quoi cela repose, et ce qui la
  fragiliserait.

  Tu n'as aucun outil d'écriture. Ce n'est pas une consigne que tu pourrais
  contourner : dans ce rôle, rien ne peut être écrit en base.

  Pose une question à la fois, appuyée sur ce que le créateur vient de dire.
  Les quatre qui portent le plus loin :

  - À quelle question ce contenu répond-il, en une phrase ?
  - Qu'affirmes-tu exactement, et sur quoi cela repose-t-il ?
  - Quelle preuve te convaincrait du contraire ?
  - Comment quelqu'un qui pense l'inverse te réfuterait-il ?

  Non-génération stricte. Même après plusieurs tours sans que rien ne se
  dégage, tu ne proposes aucune thèse candidate, aucun angle, aucun titre,
  aucun exemple. Tu résumes ce que le créateur a exprimé, tu nommes ce qui
  reste ouvert, et tu continues de questionner. Proposer, ici, c'est mettre
  tes idées dans sa bouche et les lui faire prendre pour les siennes.

  Si le créateur demande explicitement des propositions, tu écris d'abord la
  ligne « Sortie du mode socratique. » seule sur sa ligne, puis tu réponds, et
  ce qui suit est présenté comme venant de toi. Tu ne sors jamais du mode en
  silence, et tu n'y rentres jamais en silence non plus.
```

---

### 1.6 Câbler les modules dans les rôles existants

Ce sont les seules listes `context:` à modifier. Ne toucher ni à `tools:` ni aux
`system_prompt` existants, sauf pour `rechercheur.yaml` au point 1.7.

| Fichier | Lignes à ajouter dans `context:` |
|---|---|
| `assistant.yaml` | `shared/rien-de-memoire.md`, `shared/qualite-des-sources.md`, `shared/chercher-la-contradiction.md` |
| `bibliographe.yaml` | `shared/rien-de-memoire.md`, `shared/qualite-des-sources.md` |
| `extracteur.yaml` | `shared/rien-de-memoire.md` |
| `rechercheur.yaml` | `shared/qualite-des-sources.md`, `shared/chercher-la-contradiction.md` |
| `redacteur.yaml` | `shared/rien-de-memoire.md` |
| `relecteur.yaml` | `shared/rien-de-memoire.md`, `shared/qualite-des-sources.md`, `shared/chercher-la-contradiction.md` |

`publicateur.yaml` n'est pas touché : il ne collecte ni ne rédige.

Après cette étape, le contexte le plus lourd est celui de `assistant`, à
**42 450** caractères émis, contre un plafond relevé à 60 000. Le chiffre est
mesuré sur les contenus exacts des points 1.2 à 1.4 : le retoucher change le
total, et c'est le test du point 1.9 qui le rattrape.

---

### 1.7 Fondre l'élargissement interdisciplinaire dans `rechercheur.yaml`

La fiche 06 §5.2 conclut que les patrons interdisciplinaires sont trop minces
pour un module `shared/` et doivent vivre dans le rôle. Remplacer le
`system_prompt` de `rechercheur.yaml` (lignes 18-29) par :

```yaml
system_prompt: |
  Tu cherches des sources. Tu n'as aucun outil d'écriture : tu proposes, le
  créateur décide, un autre agent enregistre.

  Une source proposée est toujours accompagnée de son URL, de son titre exact
  et d'une phrase disant ce qu'elle apporte au sujet. Tu ouvres chaque URL avec
  fetch_url avant de la proposer : une URL non ouverte n'est pas une source,
  c'est une hypothèse.

  Une recherche n'est pas finie tant que tu n'as pas cherché ce qui nuance ou
  contredit. Voir shared/chercher-la-contradiction.md.

  Quand une recherche rend peu de choses, tu élargis avant de conclure qu'il
  n'y a rien, par trois gestes dans cet ordre :

  1. Le même concept sous un autre nom. La notion existe souvent dans un champ
     voisin avec un autre vocabulaire ; ce vocabulaire ouvre un corpus entier
     que la première requête ne touchait pas.
  2. Le même problème redéfini. Un problème d'ingénierie reformulé en problème
     d'usage, un problème de santé en problème économique : la reformulation
     change les questions, donc les réponses trouvables.
  3. Les disciplines qui éclairent le même phénomène par une autre question.

  Ce que tu as élargi se dit avec les résultats : le créateur doit savoir que
  la source vient d'un autre champ, et par quel chemin.

  Si la recherche web n'est pas configurée, dis-le et arrête-toi. Ne remplace
  jamais un résultat de recherche par un souvenir d'entraînement.
```

---

### 1.8 Mettre à jour `AGENTS.md`

Deux blocs. Le folder map est déjà périmé : il ne liste pas `pieges-vecus.md`.
Remplacer les lignes 30-34 :

```
├── shared/                      (Layer 3 : références stables)
│   ├── philum-mcp.md            (inventaire des tools MCP)
│   ├── principes-editoriaux.md  (ce qui fait une bonne fiche)
│   ├── garde-fous.md            (ce que l'agent refuse)
│   └── style-redactionnel.md         (style, longueurs, mots interdits)
```

par :

```
├── shared/                      (Layer 3 : références stables)
│   ├── philum-mcp.md            (inventaire des tools MCP)
│   ├── principes-editoriaux.md  (ce qui fait une bonne fiche)
│   ├── garde-fous.md            (ce que l'agent refuse)
│   ├── pieges-vecus.md          (erreurs constatées en usage réel)
│   ├── rien-de-memoire.md       (ce qui vient de la session, et le manque déclaré)
│   ├── qualite-des-sources.md   (trois questions à toute source)
│   ├── chercher-la-contradiction.md (aller chercher ce qui nuance)
│   └── style-redactionnel.md    (style, longueurs, mots interdits)
```

Puis, dans la table Routing, ajouter trois lignes après « Vérifier ce qu'on ne
fait jamais » :

```
| Savoir d'où un fait a le droit de venir | `shared/rien-de-memoire.md` |
| Juger si une source vaut quelque chose ici | `shared/qualite-des-sources.md` |
| Trouver ce qui nuance ou contredit la fiche | `shared/chercher-la-contradiction.md` |
```

Enfin, dans « Limites strictes », remplacer la ligne :

```
- Jamais inventer un DOI, une date, un auteur, un extrait. Absence > invention.
```

par :

```
- Jamais inventer un DOI, une date, un auteur, un extrait. Absence > invention,
  et un manque se déclare au lieu de se combler (`shared/rien-de-memoire.md`).
```

---

### 1.9 Tests

Ajouter dans `apps/backend/tests/unit/test_agent_workspace.py`, à la fin du
fichier :

Le module y est importé sous l'alias `agent_workspace` (`from app.services import
agent_workspace`, ligne 5), et `fichiers_du_modele()` rend un **dict**
`chemin relatif → contenu` (`agent_workspace.py:287-293`), pas une liste. Le
test s'écrit donc ainsi, sans relire le disque :

```python
def test_le_seed_shared_tient_sous_le_plafond():
    """Le gabarit `shared/` doit tenir sous le plafond d'injection.

    `_priming_workspace` tronque par un `break` sur une liste triee par
    chemin : un depassement ne leve rien, il retire en silence les derniers
    fichiers de l'ordre alphabetique. Ce test est le seul garde-fou.
    """
    from app.services.agent import _PRIMING_MAX

    emis = len("\n\n---\n## Workspace éditorial du créateur\n")
    for chemin, contenu in agent_workspace.fichiers_du_modele().items():
        if chemin.startswith("shared/"):
            emis += len(f"\n### {chemin}\n{contenu}\n")
    assert emis <= _PRIMING_MAX, (
        f"Le gabarit shared/ emet {emis} caracteres pour un plafond de "
        f"{_PRIMING_MAX} : les derniers fichiers de l'ordre alphabetique "
        "seraient perdus en silence."
    )
```

Ce test est synchrone : ne pas le décorer de `@pytest.mark.asyncio`.

Ajouter dans `apps/backend/tests/unit/test_agent_definitions.py`. Ce fichier
importe déjà `agent_definitions` et pose `CONNUS = noms_outils_connus()` en
tête (lignes 5-9) : les réutiliser plutôt que de réimporter.

```python
def test_socratique_n_expose_aucun_outil_d_ecriture():
    """La non-generation du mode socratique est structurelle, pas promptee."""
    from app.agent_tools.philum import OUTILS_QUI_ECRIVENT

    chemin = "agents/socratique.yaml"
    contenu = (agent_definitions.SEED_DIR / chemin).read_text(encoding="utf-8")
    definition = parser(chemin, contenu, noms_connus=CONNUS)
    assert not set(definition.tools) & OUTILS_QUI_ECRIVENT
```

`OUTILS_QUI_ECRIVENT` est un `frozenset[str]` exporté à
`app/agent_tools/philum.py:78`, et `SEED_DIR` est réexporté par
`agent_definitions` (`from app.services.agent_workspace import SEED_DIR, ...`).
Les deux sont vérifiés sur le disque le 2026-09-10.

Ce test valide en même temps que le fichier YAML passe le parser : un slug qui
ne correspond pas au chemin, un outil inconnu ou un `context` hors workspace le
feront échouer ici plutôt qu'en production.

Le test `assert count >= 15` de `TestSeed` reste vrai : le seed passe de 27 à 31
fichiers.

---

### 1.10 Corriger la fiche 06

Dans `agent/audit/10-externes/06-modules-de-contexte-agent.md` :

- **§3, troisième puce de « Où la porte est encore ouverte »**, remplacer
  « `add_source` (`tools_write.py:338`) accepte titre, auteurs, date, DOI,
  éditeur, en texte libre. Rien n'oblige ces valeurs à venir de la page ou d'un
  résolveur. » par une formulation exacte : `add_source` appelle déjà
  `verifier_que_la_source_existe(url, doi)`, donc l'URL et le DOI passent par un
  résolveur ; restent libres `title`, `authors`, `journal`, `published_at`,
  `publisher` et `annotation`.
- **§7**, remplacer « Non tranché. À poser dans le plan. » par la décision et son
  motif : pas de champ d'activation, la liste `context:` de `agents/*.yaml` est
  le mécanisme, le chat résout toujours un agent, et un second mécanisme
  violerait « une seule maison par fait ».

---

### 1.11 Vérifier, livrer

```bash
cd apps/backend
rm -f test.db && CI=true uv run pytest tests/unit tests/integration -q
uv run ruff check app/ && uv run ruff format app/ && uv run mypy app/ --ignore-missing-imports
```

Aucun `openapi.json` à régénérer, aucun `generated.ts`, aucune commande
frontend : cette PR ne touche aucun endpoint.

Commit, PR, CI verte, merge, déploiement.

**Vérification en production, dans cet ordre.**

1. Ouvrir `/dashboard/workspace`, cliquer « Mettre à jour ». Les quatre nouveaux
   chemins doivent apparaître en `absent` puis être ajoutés. Sans ce geste, un
   créateur qui a déjà un workspace ne reçoit rien : `assurer_workspace` ne seed
   qu'un workspace vide (`agent_workspace.py:420-426`).
2. Ouvrir `/dashboard/agents` : « Socratique » doit être dans le sélecteur. S'il
   n'y est pas, le fichier a été rejeté par le parser, la raison est affichée
   dans la liste.
3. Démarrer une session sur l'agent Socratique et lui demander explicitement
   « propose-moi trois angles ». La réponse attendue commence par « Sortie du
   mode socratique. ». Vérifier surtout qu'aucun appel d'outil d'écriture
   n'apparaît dans le fil, quoi qu'il réponde.
4. Sur l'assistant, demander une fiche sur un sujet contesté et vérifier que la
   recherche est menée dans les deux sens.

---

# PR 2, `fix/agent-annotation-sans-entourage`

Ferme la deuxième porte du §3 de la fiche 06. Aujourd'hui, quand aucun
`provided_text` n'est fourni, `annotate_excerpt` fait rédiger la mise en
situation d'un passage à partir du seul titre de la source
(`tools_write.py:1552-1554`). Le modèle écrit donc ce qui entoure un passage sans
avoir lu ce qui l'entoure. C'est une fabrication rendue possible par une valeur
de repli.

**Fichier :** `apps/backend/app/mcp_server/tools_write.py`
**Tests :** `apps/backend/tests/unit/test_mcp_tools_write.py`

### 2.1 Un helper d'entourage

Ajouter juste au-dessus de `annotate_excerpt` :

```python
#: Nombre de caracteres pris de chaque cote du passage pour situer un extrait.
#: 1 200 couvre le paragraphe qui precede et celui qui suit dans la quasi
#: totalite des pages mesurees, et reste tres en dessous du `entourage[:6000]`
#: applique par `llm.suggest_annotation`.
_MARGE_ENTOURAGE = 1200


def _entourage_du_passage(page_text: str, passage: str) -> str:
    """Fenetre de texte autour du passage dans la page, ou chaine vide.

    Chaine vide quand la page n'a pas pu etre lue, ou quand le passage n'y
    figure pas : dans les deux cas l'appelant refuse. Annoter un passage
    absent de sa source serait annoter autre chose que la source.
    """
    from app.api.v1.endpoints.excerpts import verify_quote

    if not page_text or not passage.strip():
        return ""
    trouve = verify_quote(page_text, passage)
    if not trouve:
        return ""
    debut = max(0, trouve.start() - _MARGE_ENTOURAGE)
    fin = min(len(page_text), trouve.end() + _MARGE_ENTOURAGE)
    return page_text[debut:fin]
```

`verify_quote` est le même matcher que celui de `suggest_excerpts`
(`tools_write.py:1481`), donc la tolérance typographique est déjà la bonne et
n'est pas redéfinie ici.

### 2.2 Refuser au lieu de se rabattre

Remplacer le corps de `annotate_excerpt` (lignes 1549-1557) par :

```python
    from app.api.v1.endpoints.excerpts import _texte_de_la_source
    from app.services.llm import suggest_annotation as llm_annotate

    source = await _source_du_createur(db, user, source_id)
    entourage = (provided_text or "").strip()
    if not entourage:
        page_text, _refuse, _complet = await _texte_de_la_source(source.url)
        entourage = _entourage_du_passage(page_text, excerpt_text)
    if not entourage:
        raise ToolError(
            "Impossible de situer ce passage : la page n'a pas pu etre lue, ou "
            "le passage n'y figure pas. Une mise en situation ecrite sans le "
            "texte qui entoure le passage est une invention. Rouvrez la source, "
            "ou passez son texte dans `provided_text`."
        )
    annotation = await llm_annotate(excerpt_text, entourage)
    if annotation is None:
        return {"title": None, "context": None, "llm_enabled": False}
```

Le `return` final est inchangé.

### 2.3 Le docstring nomme la conséquence

Remplacer le docstring de `annotate_excerpt` par :

```python
    """Le LLM suggere un titre court et un `context` pour un extrait donne.

    A appeler apres avoir choisi le verbatim mais avant `add_excerpt`. A
    l'agent de valider ce qu'il pose ensuite.

    L'outil refuse si le texte qui entoure le passage n'est pas disponible :
    ni `provided_text`, ni page lisible ou le passage figure. Une mise en
    situation ecrite sans le texte qu'elle situe est une invention, pas une
    approximation.
    """
```

Rappel utile pour la suite : `_description()` (`app/agent_tools/philum.py:293`)
envoie le docstring **entier** au modèle, aplati sur une ligne. Ce paragraphe
sera donc lu par l'agent.

### 2.4 Tests

Trois cas, avec `monkeypatch` sur `_texte_de_la_source` et sur
`app.services.llm.suggest_annotation`, en suivant le style des tests existants
de `annotate_excerpt` dans le fichier (les lire avant d'écrire) :

- `test_annotate_refuse_sans_entourage` : `_texte_de_la_source` rend `("", ...)`,
  attendre un `ToolError` dont le message contient `provided_text`.
- `test_annotate_refuse_si_le_passage_n_est_pas_dans_la_page` : page non vide,
  passage absent, même `ToolError`.
- `test_annotate_prend_la_fenetre_autour_du_passage` : page longue contenant le
  passage, capturer l'`entourage` reçu par le faux `suggest_annotation`, vérifier
  qu'il contient le paragraphe précédent et le suivant, et qu'il ne contient pas
  un paragraphe situé à plus de `_MARGE_ENTOURAGE` du passage.

Un test existant qui s'appuyait sur le repli `source.title` échouera : c'est
attendu. Le réécrire pour passer `provided_text`, ne pas restaurer le repli.

### 2.5 Livrer

Pas de migration, pas de contrat API. Même séquence de vérification que 1.11,
sans les commandes frontend.

**Vérification en production.** Ouvrir une fiche dont une source est derrière un
mur anti-bot, demander à l'agent d'annoter un extrait sans lui donner le texte :
il doit refuser en nommant `provided_text`, et non produire une mise en situation.

---

# PR 3, `feat/sources-metadonnees-resolues`

C'est la porte principale du §3 de la fiche 06, et la plus lourde. Elle est
placée après les deux premières parce qu'elle change un contrat MCP public.

### 3.1 Le principe, en une phrase

Le modèle choisit **quel résolveur** fait foi pour les métadonnées d'une source.
Il ne saisit plus **quelles valeurs** elles portent. Ce que le résolveur choisi
ne rend pas reste vide, et le vide est un état affichable.

### 3.2 Pourquoi cette forme et pas un cache de candidats

La conception naturelle serait un outil `resolve_source()` rendant des candidats
identifiés, puis un `add_source(candidate_id=...)`. Elle est écartée : les
fonctions de `tools_write.py` servent **à la fois** le registre de l'agent et le
serveur MCP exposé aux clients externes. Un cache par tour vivrait sur
`ToolContext`, que le chemin MCP n'a pas. Il faudrait une table et une durée de
vie, pour un gain nul.

La forme retenue est sans état : `add_source` **relance le résolveur lui-même**
et remplit les champs à partir de sa réponse. Le paramètre du modèle est
l'origine, pas la valeur.

### 3.3 Le paramètre

`add_source` et `add_sources_batch` gagnent :

```python
metadata_from: str = "page"
```

avec l'énumération `page`, `crossref`, `openalex`, `createur`.

- `page`, `crossref`, `openalex` : `title`, `authors`, `published_at`,
  `journal`, `publisher` sont **remplis par le résolveur** et les valeurs passées
  par le modèle pour ces champs sont ignorées. Une valeur du modèle qui
  contredit le résolveur est **rendue dans le résultat de l'outil**, jamais
  écartée en silence : le modèle doit apprendre l'écart.
- `createur` : les valeurs passées sont acceptées telles quelles. C'est la porte
  de sortie légitime, quand le créateur dicte. Elle est ajoutée à
  `SENSITIVE_TOOLS` par un mécanisme par paramètre (voir 3.5) pour qu'elle
  demande une approbation nommée et soit visible.

`url`, `doi`, `category`, `author_kind`, `format`, `stance` et `annotation` ne
changent pas : les deux premiers sont déjà résolus
(`verifier_que_la_source_existe`), les autres sont des choix éditoriaux, pas des
faits.

### 3.4 Migration 058

`down_revision = "057_lane_secours_modele_distinct"`.

```python
op.add_column(
    "sources",
    sa.Column("metadata_origin", sa.String(20), nullable=True),
)
```

`downgrade()` fait le `drop_column` symétrique. Nullable, donc les lignes
existantes valent `NULL`, qui se lit « origine inconnue, posée avant la
règle ». Ne pas rétro-remplir : ce serait affirmer une origine qu'on ignore.

Le job `Migrations` de la CI joue `upgrade head` puis `downgrade -1 && upgrade
head` sur Postgres pgvector : le `downgrade` doit être écrit et testé
localement, pas seulement déclaré.

### 3.5 Sensibilité par valeur de paramètre

`est_sensible()` (`app/agent_tools/philum.py`) tranche aujourd'hui par nom
d'outil. Il faut une seconde table, par couple outil/paramètre/valeur :

```python
#: Appels sensibles non par l'outil mais par une de leurs valeurs. Poser des
#: metadonnees dictees par le createur est legitime ; le faire sans que le
#: createur l'ait dicte ne l'est pas, et seule une approbation nommee fait la
#: difference.
_SENSIBLE_PAR_VALEUR: dict[str, tuple[str, frozenset[str]]] = {
    "add_source": ("metadata_from", frozenset({"createur"})),
    "add_sources_batch": ("metadata_from", frozenset({"createur"})),
}
```

`est_sensible(nom, args)` gagne le second argument. **Relever tous les appelants
avant d'écrire** : la signature change et les tests d'approbation en dépendent.

### 3.6 Contrat MCP et API

- Ajouter `metadata_from` à `_ENUMS_PAR_PARAMETRE` pour que l'énumération parte
  dans le schéma JSON envoyé au modèle. La liste doit venir d'un enum Python, à
  poser dans `app/models/source.py` à côté de `SourceCategory`, jamais recopiée
  à la main : c'est ce qui garantit qu'elle ne divergera pas.
- Le docstring de `add_source` nomme la conséquence en première phrase, comme
  pour `annotate_excerpt`.
- `metadata_origin` remonte dans les schémas de lecture de source. Régénérer
  `openapi.json` puis `generated.ts` **dans le même commit**, sinon
  `test_openapi_sync` échoue. Vérifier le saut de ligne final de `openapi.json`,
  et passer `npx prettier --write` sur `generated.ts`.
- **Rupture de contrat MCP** : un client externe qui appelait `add_source` avec
  un `title` verra désormais celui du résolveur. À écrire en clair dans le corps
  de la PR.

### 3.7 À instruire avant d'écrire une ligne

Cette PR est la seule du plan dont les ancres n'ont pas toutes été relevées. À
faire d'abord, sans quoi le code ne passera pas du premier coup :

1. Lire `app/extractors/` en entier pour savoir quels résolveurs existent
   réellement, ce que chacun rend, et sous quelle forme. Le plan suppose
   Crossref et OpenAlex disponibles parce que `verifier_que_la_source_existe` et
   `extractors/retraction.py` les utilisent, mais leurs signatures n'ont pas été
   vérifiées.
2. Lire `get_url_metadata` pour savoir ce que rend l'origine `page`.
3. Relever tous les appelants de `est_sensible()`.
4. Relever tous les tests qui construisent une source par `add_source` avec un
   `title` explicite : ils changeront de comportement.

---

# PR 4, `feat/sources-retraction-perimee`

Apport C de la fiche 04, reconfirmé par la fiche 06 §5.3 depuis un second
endroit d'ARS. `retraction_checked_at` existe (`models/source.py:156`) et ne
périme jamais : une source vérifiée il y a dix-huit mois est affichée comme
vérifiée.

### 4.1 Une vérification a une durée de vie

Dans `app/extractors/retraction.py`, poser :

```python
#: Duree de validite d'un controle de retractation. Une retractation peut
#: tomber n'importe quand apres la publication : un controle fait une fois a
#: la pose ne dit rien de l'etat d'aujourd'hui. Quatre-vingt-dix jours est un
#: point de depart, pas une mesure : a revoir quand on aura observe le delai
#: reel entre retractation et apparition dans Crossref.
DUREE_DE_VALIDITE = timedelta(days=90)


def est_perime(checked_at: datetime | None) -> bool:
    """Vrai si le controle n'a jamais eu lieu, ou a expire."""
```

Le champ `retraction_checked_at` est naïf en base (`_utcnow_naive`) : comparer
avec un `datetime.now(UTC).replace(tzinfo=None)`, pas avec un aware. C'est la
source d'erreur la plus probable de cette PR.

### 4.2 Le motif de rétractation gradue l'action

La fiche 06 §5.3 relève qu'une rétractation n'est pas binaire. Une fabrication
de données impose de retirer la citation ; une erreur honnête demande de
vérifier si l'erreur touche ce qui était cité ; un litige d'auteurs ne change
rien aux résultats.

`classify_updates()` (`retraction.py:75`) rend déjà un `RetractionResult` : lui
ajouter le motif quand Crossref le donne, et un champ `gravite` à trois valeurs
(`retirer`, `verifier`, `sans_effet`). Un motif absent ou inconnu vaut
`verifier`, jamais `sans_effet` : le défaut prudent est celui qui demande un
regard humain.

Un affichage qui rendrait la rétractation binaire serait faux : c'est ce que
cette PR corrige côté données, et l'affichage suivra dans une PR frontend
séparée.

### 4.3 Le re-contrôle

Une commande sous `app/scripts/`, sur le modèle des scripts existants (les lire
avant d'écrire), qui parcourt les sources dont le DOI est posé et dont le
contrôle est périmé, et rejoue `check_retraction`. Idempotente, rejouable,
bornée par un `--limit` pour ne pas marteler Crossref.

Pas de file d'attente, pas d'états : `services/excerpt_indexing.py:1-11` a déjà
tranché cette question pour Philum, avec son motif écrit.

### 4.4 Migration 059

`down_revision = "058_..."`. Ajoute `retraction_reason` (String 200, nullable) et
`retraction_gravite` (String 20, nullable) sur `sources`, avec le `downgrade`
symétrique.

### 4.5 Contrat API

Les deux champs remontent dans les schémas de source. Régénérer `openapi.json`
et `generated.ts` dans le même commit, prettier sur `generated.ts`.

---

# PR 5, `feat/agent-juge-de-fidelite`

Q3a de la fiche 05 : la source dit-elle ce que l'annotation lui fait dire.
Périmètre strictement limité, par décision du créateur du 2026-09-10.

### 5.1 Les décisions déjà arrêtées

| Décision | Conséquence pour le code |
|---|---|
| Le juge ne juge que ce que l'IA a proposé | filtre sur `annotated_by_ai=True` ou `suggested_by_ai=True` |
| Il avertit, il ne bloque pas | aucun verdict n'empêche `publish_card` |
| Il est optionnel, activé par défaut | un réglage par créateur, pas un réglage serveur |
| Il utilise la clé du créateur, ou le mode gratuit | `AgentProvider` via `agent_providers.ordonner_pour_chat`, **jamais** `services/llm.py` qui utilise la clé serveur partagée |
| Si le modèle ne répond pas : message d'erreur, pas de blocage | l'échec est un état affiché, pas une exception qui remonte |
| Activé mais non exécuté : alerte à la publication | l'absence de verdict est elle-même un état à afficher |
| Le jeu doré est reporté | le juge part « non mesuré », et le dit |
| Le verdict est privé au créateur | aucune page publique, aucun endpoint non authentifié |

### 5.2 La plomberie d'appel, vérifiée

Le juge est un appel **bloquant**, hors de la boucle de streaming :

```python
url, headers = llm_adapters.url_et_headers(provider.provider, provider.base_url, cle)
payload = llm_adapters.format_chat_payload(
    provider.provider, modele, messages, [], max_tokens, stream=False
)
# ... httpx.post ...
resultat = llm_adapters.parse_blocking_response(provider.provider, data)
```

`_PROTOCOLE` de `llm_adapters.py` mappe `anthropic` sur son protocole propre et
les huit autres fournisseurs sur le protocole OpenAI : les neuf sont donc
couverts sans branche supplémentaire.

### 5.3 Le vérificateur n'est pas le générateur

Fiche 06 §6.1, et c'est la garde qui coûte le moins cher du plan. L'annotation
est produite par `services/llm.py` sur la clé serveur ; le juge tourne sur la
clé du créateur. **Ce sont déjà deux appels distincts sur deux clés distinctes**,
souvent deux familles de modèles. Il suffit de ne pas défaire cette propriété,
et de l'écrire dans le code pour que personne ne « simplifie » en réunifiant les
deux appels plus tard.

Détail à reprendre : un verdict **positif** rendu sans que le juge ait eu le
texte de la source sous les yeux est **déclassé**, parce que rien ne l'étaye. Un
verdict négatif, lui, survit. Un désaccord vaut toujours quelque chose, un
accord non étayé ne vaut rien.

### 5.4 Le vocabulaire de verdict

Fiche 06 §6.4. Trois règles, dans cet ordre, et la direction ne se pose que si
les deux premières sont franchies :

1. **Pertinence** : ce passage traite-t-il de ce que l'annotation lui fait dire ?
2. **Vérifiabilité** : le texte disponible permet-il de trancher ?
3. **Position** : soutient, contredit, mixte.

Énumération fermée à six valeurs : `soutient`, `contredit`, `mixte`,
`ne_traite_pas`, `preuve_insuffisante`, `ambigu`.

Trois interdits qui sont des règles de code, pas des conseils :

- **Une preuve absente n'est jamais `ne_traite_pas`.** Le silence de ce texte-ci
  n'est pas le silence de la littérature. Un juge qui n'a pas pu lire la page
  rend `preuve_insuffisante`.
- **Aucun score numérique nulle part.** Pas de champ flottant sur le modèle, pas
  de pourcentage dans l'interface. Un scalaire invite à la moyenne, et une
  moyenne de jugements catégoriels ne veut rien dire.
- **La portée de ce qui a été jugé se déclare** : `resume_seul`,
  `texte_integral`, `metadonnees_seules`. On ne prétend pas avoir jugé sur le
  texte intégral quand on n'a lu qu'un résumé.

### 5.5 La posture « non mesuré »

Le juge part en production sans mesure, et le dit. L'état affiché au créateur
porte la mention en clair, l'API la rend dans la réponse, et aucune page
publique ne s'en sert. Reprise entière de la posture d'ARS : livrer sans mesure
est acceptable, promettre sans mesure ne l'est pas.

Le jour où le jeu doré sera construit, la fiche 06 §6.2 pose la condition sans
laquelle la mesure ne voudrait rien dire : le corrigé n'entre jamais dans la
fenêtre du modèle jugé, et les invocations sont séparées, pas seulement les
consignes.

### 5.6 Migration 060

`down_revision = "059_..."`. Sur `source_excerpts` :

```python
op.add_column("source_excerpts", sa.Column("fidelity_verdict", sa.String(24), nullable=True))
op.add_column("source_excerpts", sa.Column("fidelity_scope", sa.String(24), nullable=True))
op.add_column("source_excerpts", sa.Column("fidelity_checked_at", sa.DateTime(), nullable=True))
op.add_column("source_excerpts", sa.Column("fidelity_note", sa.Text(), nullable=True))
```

Tous nullables, `downgrade` symétrique. `NULL` sur `fidelity_verdict` veut dire
« jamais jugé », un état à afficher tel quel, jamais comblé par un défaut qui
ferait passer l'extrait pour vérifié. C'est exactement la convention déjà posée
par le commentaire de `verified_at` dans `models/source_excerpt.py`.

Aucun champ numérique : voir 5.4.

### 5.7 Le réglage par créateur

Un booléen sur le créateur, pas sur le serveur. Instruire avant d'écrire : où
vivent les préférences de créateur aujourd'hui, et si un modèle de réglages
existe déjà, sinon la même migration 060 le pose.

### 5.8 Tests

`MockTransport` de httpx pour les appels de juge, sur le modèle des tests
existants de `services/agent.py` (les lire avant d'écrire). Cas à couvrir :

- Le juge n'est jamais appelé sur un extrait dont `annotated_by_ai` est faux.
- Un fournisseur qui ne répond pas laisse `fidelity_verdict` à `NULL` et rend un
  message d'erreur, sans lever.
- Un verdict positif rendu avec `scope=metadonnees_seules` est déclassé en
  `preuve_insuffisante`.
- Un verdict négatif rendu avec `scope=metadonnees_seules` survit.
- Une valeur hors de l'énumération fermée est rejetée, pas normalisée.
- `publish_card` réussit quel que soit le verdict, et l'alerte de publication
  apparaît quand le juge est activé mais qu'aucun verdict n'existe.

### 5.9 À instruire avant d'écrire

1. Où vivent les préférences par créateur.
2. Le point exact d'accroche du juge : à l'appel de `annotate_excerpt`, à
   `verify_excerpts`, ou en tâche déclenchée. Les trois ont des conséquences
   différentes sur la latence perçue.
3. Comment le verdict remonte dans l'interface d'édition de fiche.

---

## Vérification après chaque merge

1. `cd apps/backend && rm -f test.db && CI=true uv run pytest tests/unit tests/integration -q`
2. `uv run ruff check .` puis `uv run ruff format .` puis `uv run mypy app --ignore-missing-imports`
3. Si un endpoint a bougé : `CI=true uv run python -m app.scripts.export_openapi`, puis
   `cd apps/frontend && pnpm run generate:api && npx prettier --write src/lib/api/generated.ts`
4. Si le frontend a bougé : `pnpm run check && pnpm run lint && pnpm test`
5. CI verte, zéro job en échec, avant merge
6. Après déploiement : `curl -s https://philum-api.duckdns.org/health`
7. Test manuel de ce que la PR vient de livrer, comme décrit dans sa section

---

## Pièges déjà payés, à ne pas repayer

- **`app/agent_workspace_seed/` est un snapshot, pas la source.** La source est
  `workspaces/createur-de-fiches/` à la racine du dépôt, et
  `tests/unit/test_workspace_seed_sync.py` vérifie l'égalité octet à octet des
  deux arbres. Éditer le seed seul fait échouer deux tests. Le geste correct :
  éditer la source, puis `uv run python -m app.scripts.build_workspace_seed`
  depuis `apps/backend`. Le script **purge** le seed de tout fichier absent de la
  source, donc un fichier créé seulement dans le seed est supprimé sans bruit.
  Piège payé le 2026-09-10 sur la PR 1 ; il vaut pour toute PR qui touche au
  workspace.
- **La CI lint `app/`, pas `.`.** `uv run ruff check .` remonte 18 erreurs
  préexistantes dans `tests/` qui ne cassent rien. Les commandes exactes de la CI
  sont `ruff check app/`, `ruff format --check app/`, `mypy app/`.
- **Le seed ne rattrape pas les workspaces existants.** `assurer_workspace` ne
  seed qu'un workspace vide. Tout fichier de gabarit livré n'atteint un créateur
  déjà provisionné que par le bouton « Mettre à jour » de `/dashboard/workspace`.
- **La troncature de priming est silencieuse.** Elle ne lève rien, elle retire
  les derniers fichiers de l'ordre alphabétique. Le seul garde-fou est le test du
  point 1.9.
- **`ruff` ignore `app/agent_workspace_seed`.** Utile pour les `.md`, mais cela
  veut aussi dire qu'une erreur de syntaxe YAML dans un fichier d'agent ne sera
  vue qu'au chargement. Le test du point 1.9 la rattrape.
- **Guillemets courbes U+2018/U+2019 comme délimiteurs de chaîne** dans les
  fichiers Svelte : erreur de parsing ESLint. Délimiteurs toujours ASCII ; les
  apostrophes internes peuvent rester courbes.
- **Prettier et `ruff format` avant commit**, sinon Lint Backend et Lint Frontend
  cassent.
- **Contrat API** : `openapi.json` puis `generated.ts` dans le **même commit** dès
  qu'un endpoint bouge, sinon `test_openapi_sync` échoue. Vérifier le saut de
  ligne final de `openapi.json`.
- **Le job Migrations joue le `downgrade`.** Une migration sans `downgrade`
  symétrique casse la CI, pas la production.
- **`retraction_checked_at` est un datetime naïf.** Le comparer à un aware lève
  un `TypeError` à l'exécution, jamais au typage.
- **`test.db` périmé** fait échouer les tests : `rm -f test.db` d'abord.
- **Le token gh n'a pas `read:org`** : `--body-file` échoue, passer `--body`.
- **ARS est sous CC BY-NC 4.0.** Aucune ligne de son code, de ses prompts ou de
  sa prose. Les modules de la PR 1 sont écrits de zéro et doivent le rester.

---

_Rédigé le 2026-09-10, après relevé sur le disque de chaque ancre citée dans le
tableau de tête._
