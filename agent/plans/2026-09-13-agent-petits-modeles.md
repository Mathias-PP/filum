# L'agent avec de petits modèles : ce qui peut encore s'améliorer

> Établi le 2026-09-13, après les lots 1 à 5 du diagnostic « arthrose »
> (`2026-09-13-conversations-arthrose-diagnostic.md`). Chaque constat dit s'il
> est **mesuré** (en base de prod, ou par un script sur le code de `main`),
> **lu** (dans le code) ou **à vérifier**.

Les conversations « arthrose » ont tourné sur `ministral-8b-latest` (A) et sur la
lane gratuite par défaut (B). Les lots précédents ont corrigé ce qui était faux
quel que soit le modèle. Ce document porte sur l'autre moitié : **ce que la
configuration de l'agent demande à un petit modèle, et qu'il ne peut pas tenir**.

---

## Ce qu'un petit modèle reçoit aujourd'hui

**Mesuré** (script sur `main`, agents livrés dans `agent_workspace_seed/agents/`) :

| Agent | Outils | Schémas d'outils | Contexte `shared/` et étapes | Prompt d'agent |
|---|---|---|---|---|
| **assistant** (défaut) | **34** | **27 584 car.** | **42 144 car.** | 358 car. |
| bibliographe | 11 | 10 928 | 31 034 | 422 |
| extracteur | 12 | 8 963 | 16 525 | 543 |
| rechercheur | 6 | 2 661 | 24 959 | 1 373 |
| questionneur | 6 | 2 828 | 5 023 | 1 628 |
| publicateur | 9 | 5 262 | 7 754 | 342 |

Les deux conversations utilisaient l'assistant par défaut (`agent_slug` vide).
Avant la question, le modèle reçoit donc environ **70 000 caractères**
d'instructions et de schémas : la première réponse de A compte **16 789 jetons
de prompt** (**mesuré**). Les schémas les plus lourds : `add_source` 3 556 car.,
`update_source` 2 257, `create_card` 1 836.

**Mesuré**, appels d'outils des deux sessions :

| | A (ministral 8B) | B (lane gratuite) |
|---|---|---|
| `add_excerpt` | 83 appels, **79 échecs** | 8 appels, 6 échecs |
| `fetch_url` | 3 appels, **20 019 car.** en moyenne, 24 493 max | 9 appels, 8 373 car. en moyenne, 25 457 max |
| `web_search` | 2 appels, 7 410 car. en moyenne | 3 appels, 8 684 car. |
| `verify_excerpts` | 26 appels | 3 appels |
| `get_source`, `get_card` | 3 appels qui rendent `null` | |
| `fiche_etapes`, `fiche_state` | **0** | **0** |
| Réponses de l'assistant | 27, dont deux de 9 115 et 21 159 car. | 4 |

Chaque lecture de page ajoute en moyenne 20 000 caractères au contexte, et le
plafond d'un résultat d'outil est `TOOL_RESULT_MAX = 120_000` (**lu**). Au
troisième `fetch_url`, les consignes du début pèsent peu face au texte lu.

---

## Propositions, par ordre d'effet attendu

### 0. Mesurer avant de régler

Rien aujourd'hui ne dit si un changement de prompt aide ou nuit : le constat
passe par une conversation réelle relue à la main.

**Proposition** : un banc d'essai rejouable depuis le poste de développement
(jamais depuis la VM). Dix demandes fixes, dont « comment prévenir l'arthrose ? »,
chacune jouée sur les modèles des lanes gratuites. On relève :

- la part d'`add_excerpt` refusés ;
- la part de sources portant au moins un extrait ;
- les jetons de prompt du premier appel ;
- la durée du tour et le nombre d'appels ;
- les annonces non tenues (`controle_relance`).

Chaque proposition ci-dessous se juge sur ces chiffres.

### 1. Un tour coupé à 5 minutes, même détaché : un bug

**Lu** : `BOUCLE_TIMEOUT = 300.0` (`services/agent.py:83`) enveloppe toute la
boucle. Le tour de B a duré 309 s : il aurait été coupé même sans Vercel. Depuis
#652, le tour vit sans le client, et « Arrêter » passe par le serveur.

**Proposition** : relever ce mur (par exemple 20 minutes). La borne réelle reste
`agent_max_tours` avec sa pause « Continuer ».

### 2. Un profil « petit modèle » qui allège le contexte

C'est le levier le plus fort. Les recommandations de Mistral pour Ministral 3 8B
disent de limiter les outils au minimum nécessaire. Pour les petits modèles, le
contexte doit tenir en quelques milliers de jetons, pas en dix-sept mille.

**Propositions** :

1. **Déclarer la taille du modèle** : un champ `profil` (`petit` ou `grand`) sur
   la lane et sur la clé, déduit du nom quand il est connu (`8b`, `flash`,
   `mini`, `small`).
2. **Un contexte réduit en profil petit** : au lieu de huit fichiers `shared/`
   (42 000 car.), un seul fichier `shared/essentiel.md` de moins de 2 000 car. Il
   porte les règles qui ont échoué en vrai : copier un verbatim, ne rien affirmer
   sans outil, une position exige un extrait. Les autres fichiers restent
   lisibles par `fs_read` à la demande.
3. **Des descriptions d'outils courtes en profil petit** : la première phrase de
   la docstring et les valeurs acceptées, rien de plus. Le détail (cas limites,
   historique) part dans le message d'erreur, au moment où il sert.
4. **La mémoire graphe injectée automatiquement coupée en profil petit** : 12
   faits ajoutés au prompt sont du bruit pour un modèle qui peine déjà à suivre
   ses consignes. `recall_memory` reste appelable.

Ordre de grandeur visé pour l'assistant en profil petit : moins de 15 000
caractères avant la question, au lieu de 70 000.

### 3. Des résultats d'outils à la taille d'une fenêtre de lecture

**Mesuré** : 20 000 caractères par `fetch_url`, 8 000 à 10 000 par `web_search`.

**Propositions** :

1. **`fetch_url` rend une page, pas un livre** : en profil petit, le titre, un plan
   (intertitres), et une fenêtre de 4 000 caractères, avec `page` pour lire la
   suite. Pour citer, `find_passage` va chercher lui-même dans le texte complet :
   le modèle n'a plus besoin de tout avoir sous les yeux.
2. **`web_search` rend cinq résultats** au lieu de huit, avec des extraits de 300
   caractères.
3. **Les anciens résultats d'outils élagués plus tôt** : la compaction existe
   (`BUDGET_HISTORIQUE = 96 000`), mais en profil petit le texte d'une page déjà
   exploitée peut être remplacé par une ligne (« page lue, 3 extraits posés »)
   dès l'appel suivant.

### 4. Un déroulé de fiche piloté par le serveur, pas par le modèle

**Mesuré** : `fiche_etapes` et `fiche_state` n'ont jamais été appelés. Un petit
modèle ne découvre pas seul un déroulé en sept étages décrit dans un fichier.
Les agents d'étape existent (`rechercheur`, `extracteur`...), mais le créateur
reste sur l'assistant.

**Propositions** :

1. **Reconnaître la demande « fais une fiche sur X »** et proposer, ou lancer, le
   déroulé guidé au lieu de l'assistant généraliste.
2. **Chaque étape n'expose que ses outils**, cinq ou six au plus, et le serveur
   passe à l'étape suivante quand la condition de sortie est remplie :
   - **recherche** : des sources candidates, dont au moins une qui nuance ;
   - **sources** : `add_source` sans position ;
   - **extraits** : pour chaque source, `find_passage` puis `add_excerpt` ;
   - **positions** : `update_source` avec la position, qui exige désormais un
     extrait ;
   - **bilan**.
3. **La recherche de ce qui nuance devient une étape**, dont le résultat est
   déclaré même vide (« aucune source contraire trouvée sur ces trois requêtes »).
   La règle existe dans `shared/chercher-la-contradiction.md` ; en profil petit,
   elle ne se lit pas, elle s'exécute.

### 5. Chaque réponse d'outil dit quoi faire ensuite

Un grand modèle déduit l'étape suivante, un petit la lit.

**Propositions** :

1. **Un champ `suite` dans les réponses d'écriture**. Par exemple, `add_source`
   rend « Suite : `find_passage(source_id="…", query="…")` pour poser un extrait
   de cette source ».
2. **Plus de `null` muet** : `get_source` et `get_card` ont rendu `null` trois
   fois (**mesuré**). `get_card` ignore les brouillons. Un résultat vide doit
   nommer l'outil qui répond : `get_my_card` pour une fiche du créateur,
   `list_sources` pour les identifiants valides.
3. **Les identifiants d'une conversation rappelés au modèle** : une ligne tenue
   par le serveur dans le prompt (« fiche en cours : `prevention-arthrose` ;
   sources : 1 OMS `3f2a…`, 2 Inserm `9c1b…` ») évite les identifiants tronqués
   ou inventés.

### 6. Une réponse finale construite sur les faits

**Mesuré** : des réponses de 9 115 et 21 159 caractères dans A, qui répètent le
plan. Le bilan calculé par le serveur existe depuis #652, sous la réponse.

**Proposition** : en profil petit, la réponse finale suit un gabarit court, et
ses données viennent de la base et non de la mémoire du tour :

- ce qui a été fait ;
- pour chaque source, l'extrait posé ;
- ce qui n'a pas été trouvé ;
- les limites.

Le modèle rédige seulement la phrase d'introduction et les limites.

### 7. Le choix et le réglage du modèle

- **Température** : 0 aujourd'hui (**lu**). C'est conforme aux recommandations
  de Mistral pour la variante Instruct (moins de 0,1). Une variante Reasoning de
  Ministral 3 8B existe, recommandée à 0,7 : à tester au banc, pas à supposer.
- **GLM-4.7-Flash** : MoE de 30 milliards de paramètres dont environ 3 actifs, et
  un mode de réflexion entrelacé pensé pour enchaîner les outils. **À vérifier**
  dans la documentation Z.ai : ce mode est-il actif par défaut sur l'API, faut-il
  le demander, et `format_chat_payload` le transmet-il ?
- **Recommandation par agent** : le champ `model_hint` des agents existe et n'est
  pas utilisé. Il pourrait avertir qu'un modèle 8B choisi pour créer une fiche
  refusera beaucoup d'extraits, et proposer la lane la plus capable.

### 8. Ce qui reste des lots précédents

- Exiger une mise en situation quand la langue de l'extrait diffère de celle de
  la fiche.
- Faire de la recherche de ce qui nuance une étape obligatoire (voir 4.3).

---

## Découpage proposé

| # | Contenu | Pourquoi dans cet ordre |
|---|---|---|
| 1 | Mur de 5 minutes relevé (1) | bug, une ligne |
| 2 | Banc d'essai (0) | juger la suite sur des chiffres |
| 3 | Profil petit : contexte réduit, descriptions courtes, graphe coupé (2) | le levier le plus fort, mesurable tout de suite |
| 4 | Résultats d'outils fenêtrés (3) | le contexte qui gonfle en cours de tour |
| 5 | `suite`, plus de `null` muet, identifiants rappelés (5) | petits changements, effet direct sur les boucles |
| 6 | Déroulé guidé de fiche, dont l'étape de nuance (4) | le plus gros chantier |
| 7 | Réponse finale sur gabarit (6), réglages de modèle (7) | après le banc |

## Sources externes

- [Ministral 3 8B Instruct, carte du modèle](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512) : température, outils en nombre minimal
- [Ministral 3 8B Reasoning](https://huggingface.co/mistralai/Ministral-3-8B-Reasoning-2512)
- [GLM-4.7-Flash, architecture et réflexion entrelacée](https://llm-stats.com/posts/d9649b05-087d-4cbf-a45a-166ce2451e78)
- [GLM-4.7-Flash, fiche Lambda](https://lambda.ai/inference-models/zai-org/glm-4.7-flash)
