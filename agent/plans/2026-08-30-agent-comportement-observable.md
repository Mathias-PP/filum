# Agent Philum : ce qui change ce que l'utilisateur voit

Plan issu d'une relecture vérifiée des audits `agent/audit/01` à `09` contre le
code réellement en place au 2026-08-30. La plupart des recommandations des
audits sont déjà livrées. Ce plan ne retient que les items dont la livraison
change le comportement observable de l'agent en production, dans l'ordre du
rapport effort sur effet.

## Ce qui est déjà livré, à ne pas refaire

Vérifié symbole par symbole dans le code :

- **A6 compteur de jetons** : `app/services/token_meter.py`, utilisé par
  `agent.py` via `ancre_du_dernier_appel`.
- **A23 relance routée par fournisseur** : inline dans `agent.py`
  (`_extraire_retry_after`, `_extraire_retry_delay` pour le `retryDelay` de
  Google, repli 502/503/504, gigue).
- **A25 garde d'approbation** : déplacée dans le passage obligé
  `registry.executer`.
- **B3/B19 session de base dédiée au flux SSE** : `async_session_maker()` dans
  `agent_chat.py`.
- **B13/A18 expiration d'approbation** avec compte à rebours dans l'interface.
- **F1 à F18** : tous les correctifs rapides d'accessibilité et de mise en page.
- **A15 compaction** : `compacter()` et `_elaguer_resultats()` sont en place. La
  phase de résumé par LLM prévue par l'audit a été **écartée volontairement**,
  la raison est écrite dans la docstring de `compacter()` : un appel de modèle
  dans le chemin de la requête, et surtout le risque que le modèle traite sa
  propre reformulation comme un fait. Ne pas rouvrir.

Reportés faute d'effet observable : A2 prompt en cascade, A16 assembleur de
blocs, A14 journal d'événements. C'est de la dette d'architecture, pas du
comportement.

---

## PR A — `fix/agent-sait-quel-jour-on-est` (XS)

**Le problème.** `_SYSTEME` interdit de « fabriquer une date de mémoire » et
aucune date n'est jamais donnée au modèle. Vérifié : la seule occurrence de
`datetime` dans `agent.py` sert à parser un en-tête `Retry-After`. L'agent date
donc au petit bonheur de son cutoff d'entraînement, sur un produit dont
l'argument est de ne rien inventer. C'est le pire rapport effort sur dégât de
toute la liste.

**Fichier :** `apps/backend/app/services/agent.py`
**Test :** `apps/backend/tests/unit/test_agent_loop.py`

- [ ] A.1 Dans `boucle()`, à l'endroit où `systeme = _SYSTEME` est assemblé,
      préfixer une ligne de contexte temporel : la date du jour en ISO et le
      fait que toute date postérieure au cutoff doit venir d'un outil, jamais de
      la mémoire. La date est calculée à l'appel, pas au chargement du module,
      sinon un processus qui vit plusieurs jours sert une date périmée.
- [ ] A.2 Test : deux appels à un jour d'écart rendent deux prompts différents
      (geler l'horloge via monkeypatch). Test : le prompt système contient la
      date du jour au format ISO.
- [ ] A.3 Suite, lint, types, commit, PR, merge, déploiement, vérification.

**Vérification en production :** demander à l'agent « quelle est la date
aujourd'hui », puis « cette source de 2024 est-elle récente ». Les deux
réponses doivent être ancrées sur la vraie date.

---

## PR B — `feat/agent-outils-en-parallele` (M)

**Le problème.** `agent.py` exécute les appels d'outils dans une boucle `for`
séquentielle, sous un unique `BOUCLE_TIMEOUT = 300.0` global. Cinq lectures de
sources s'enchaînent au lieu de partir ensemble, et un seul `fetch_url` lent
consomme le budget de tout le tour. C'est le seul changement de latence
perceptible du plan, et le mécanisme concret par lequel un tour de recherche
échoue à moitié.

**Fichiers :** `apps/backend/app/services/agent.py`,
`apps/backend/app/agent_tools/registry.py`
**Test :** `apps/backend/tests/unit/test_agent_outils_paralleles.py` (nouveau)

- [ ] B.1 **Timeout par outil d'abord**, parce qu'il est sûr et indépendant du
      reste. Envelopper chaque `executer(...)` dans un `asyncio.wait_for`. Le
      dépassement rend un résultat d'erreur lisible par le modèle (« l'outil n'a
      pas répondu en N secondes »), il ne tue pas le tour. Budget par défaut
      nettement sous `BOUCLE_TIMEOUT`, surchargeable par outil pour les lectures
      web qui sont légitimement lentes.

- [ ] B.2 **Parallélisme, avec deux gardes strictes.** Le lot d'appels d'un même
      message assistant part en `asyncio.gather` **seulement si** :
      1. aucun appel du lot n'est sensible au sens de `est_sensible()` : une
         approbation est une interaction humaine séquentielle, la paralléliser
         ferait apparaître plusieurs demandes concurrentes à l'écran ;
      2. aucun appel du lot n'écrit, au sens de `OUTILS_QUI_ECRIVENT` : deux
         écritures concurrentes partagent l'`AsyncSession` du contexte, ce qui
         est explicitement interdit dans ce dépôt.
      Autrement dit : les lectures partent ensemble, les écritures restent en
      file. C'est là que se trouve tout le gain, les tours lents sont des tours
      de lecture.

- [ ] B.3 L'ordre des messages `tool` rendus au modèle suit l'ordre des
      `tool_calls` du fournisseur, jamais l'ordre d'arrivée des résultats. Un
      lot désordonné casse la correspondance chez certains fournisseurs.

- [ ] B.4 Les événements SSE `tool_result` sont émis dans le même ordre, sinon
      l'interface affiche les cartes d'outil dans le désordre.

- [ ] B.5 Tests : un lot de trois lectures dont chacune dort 0,2 s se termine en
      moins de 0,4 s ; un lot contenant une écriture reste séquentiel ; un lot
      contenant un outil sensible reste séquentiel ; un outil qui dépasse son
      budget rend une erreur nommée et les autres résultats du lot arrivent
      quand même ; l'ordre des messages `tool` est celui des `tool_calls`.

- [ ] B.6 Suite, lint, types, commit, PR, merge, déploiement, vérification.

---

## PR C — `fix/chat-reprend-apres-coupure` (M)

**Le problème.** Aucun `Last-Event-ID` côté backend, aucune reprise côté
`lib/api/agent.ts`. Une coupure réseau pendant un tour vide l'écran alors que
`_persister_tour` a bien écrit le tour en base. L'utilisateur ne lit pas une
déconnexion, il lit une perte de données.

**Fichiers :** `apps/backend/app/api/v1/endpoints/agent_chat.py`,
`apps/frontend/src/lib/api/agent.ts`,
`apps/frontend/src/lib/components/chat/ChatPanel.svelte`

- [ ] C.1 Décider du niveau de garantie **avant d'écrire une ligne**. Rejouer un
      tour interrompu depuis un tampon serveur est une vraie machine à états.
      La version qui vaut le coût : à la reconnexion, le front relit la session
      par l'API et réaffiche le tour tel qu'il a été persisté. Pas de rejeu de
      jetons, pas de tampon en mémoire côté serveur, donc rien à perdre à un
      redéploiement. Si le tour était encore en cours au moment de la coupure,
      dire à l'utilisateur que la réponse continue côté serveur et se recharge.
- [ ] C.2 Le front distingue trois états : flux vivant, coupure en cours de
      reprise, échec définitif. Aujourd'hui il n'en affiche aucun.
- [ ] C.3 Tests, régénération du contrat si un point d'entrée bouge, prettier.
- [ ] C.4 Commit, PR, merge, déploiement, vérification en coupant le réseau
      pendant une réponse.

---

## PR D — `feat/agent-objectif-de-session` (M, version minimale)

**Le problème.** Aucun état d'objectif persistant : sur un tour long, l'agent
redérive son intention du seul historique, qui est justement ce que la
compaction ampute. L'audit chiffrait trois jours avec une `GoalBar.svelte` ; la
version qui produit l'effet observable est bien plus petite.

- [ ] D.1 Deux colonnes sur `agent_sessions` : objectif et phase courante.
      Migration.
- [ ] D.2 Deux outils, `definir_objectif` et `avancer_phase`, dans la couche
      outil. Ni l'un ni l'autre n'est sensible.
- [ ] D.3 L'objectif courant est injecté dans le prompt système à chaque tour,
      donc il survit à la compaction de l'historique.
- [ ] D.4 Affichage discret d'une ligne d'objectif dans le fil. Pas de barre
      dédiée tant que l'usage n'est pas mesuré.
- [ ] D.5 Tests, contrat, commit, PR, merge, déploiement.

---

## Écarté pour l'instant

**A9 tâches de fond.** Débloque la classe des travaux qui ne rentrent pas dans
un tour, mais c'est un modèle, une file, trois outils et une interface. À
reprendre seulement si, après la PR B, un tour continue de buter sur
`BOUCLE_TIMEOUT`. Le parallélisme peut suffire à faire disparaître le
symptôme.

**B2 approbations perdues au redémarrage.** Réel mais borné par
`DELAI_MAX = 300.0`. Coût de la persistance disproportionné devant une fenêtre
de cinq minutes.

**B6 résiduel `datetime.now().replace(tzinfo=None)`** dans `wayback.py` lignes
565, 567 et 651 : décale les dates d'archive du fuseau du serveur. Une ligne
chacune, à glisser dans la première PR qui touche ce fichier.

## Discipline

Une PR à la fois, mergée, déployée et vérifiée en production avant la suivante.
Français partout, aucun tiret cadratin. `uv run pytest` depuis `apps/backend`,
jamais `python -m pytest`. `rm -f test.db` avant chaque passage. `ruff format`
et prettier avant commit.
