# Interface de l'agent : diagnostic complet

> Établi le 2026-09-11 sur `main` à `e4749c3`, en lisant le code de
> `lib/components/chat/`, `routes/dashboard/chat/` et des endpoints agent, et en
> mesurant la page de production dans un navigateur à 1536 × 695 px. Aucun
> message n'a été envoyé à l'agent pendant le diagnostic. Seule écriture : un
> `PATCH` de la conversation « test 3 » avec son titre inchangé, pour savoir si
> le renommage marche côté serveur.

Chaque point dit comment il a été établi : **reproduit** (vu dans le
navigateur), **mesuré**, **lu** (certain à la lecture du code) ou **probable**.

---

## 1. Bugs

### B1. Les conversations nommées « disparaissent »

Quatre défauts cumulés, tous dans le front. Le serveur renomme correctement :
`PATCH /agent/sessions/{id}` rend 200 (**mesuré**).

1. **La liste de gauche n'est jamais rechargée** (**lu**). `sessions` est chargé
   une fois dans `onMount` de `routes/dashboard/chat/+page.svelte`. Une
   conversation créée ensuite n'y apparaît qu'au rechargement de la page.
2. **« Nouvelle » ne crée pas de nouvelle conversation après une première**
   (**reproduit**). À la création, `onsession` réécrit l'adresse avec
   `history.replaceState` natif, que le routeur de SvelteKit ignore. Au clic sur
   « Nouvelle », l'adresse revient à `/dashboard/chat` mais le composant n'est
   pas remonté : `ChatPanel` garde le `sessionId` précédent. Le message suivant
   part donc dans l'ancienne conversation, et le nom saisi n'est jamais appliqué
   puisqu'il ne l'est qu'à la création (`titreInitial`). Conséquence
   **probable** : les deux conversations examinées n'en portent pas la trace.
3. **L'échec du renommage est avalé** (**lu**) : `.catch(() => null)` dans
   `envoyer()`.
4. **La page d'une conversation n'a pas de liste** (**lu**) :
   `routes/dashboard/chat/[id]/+page.svelte` n'affiche ni la barre de gauche, ni
   « Nouvelle ». On ne navigue d'une conversation à l'autre qu'en revenant en
   arrière.

Correctif : un seul `+layout.svelte` pour `/dashboard/chat` qui porte la liste,
la route `[id]` en enfant, la navigation par `goto` ou le `replaceState` de
`$app/navigation`, une liste rafraîchie à chaque création et renommage, et un
nom modifiable en place dans l'en-tête.

### B2. Un JSON long élargit la conversation jusqu'à 22 000 px

**Reproduit** sur la page de liste en injectant un résultat d'outil de
3 000 caractères : la colonne passe de **672 px à 21 736 px**, et la page à
**22 307 px** de large pour un écran de 1 536.

- La grille `lg:grid-cols-[16rem_1fr]` : `1fr` vaut `minmax(auto, 1fr)`, donc la
  colonne s'étire à la largeur minimale de son contenu.
- Les `<pre>` de `ToolCard` et d'`ApprovalCard`, ainsi que les blocs de code
  d'`AgentMarkdown`, ne font pas de retour à la ligne.

Sur la page d'une conversation, la colonne tient mais le `<pre>` défile en
interne sur **23 239 px** : une ligne JSON y fait 3 226 caractères (**mesuré**).
C'est illisible dans les deux cas.

Correctif : `minmax(0, 1fr)` et `min-w-0` sur toute la chaîne, `pre` en
`whitespace-pre-wrap` avec coupure des mots longs, et, mieux, une vue
structurée (clé : valeur, valeurs longues repliées) à la place du JSON brut.

### B3. Des noms techniques restent affichés

- `get_my_card` s'affiche tel quel (**reproduit**). Manquent aussi
  `fiche_state`, `fiche_etapes`, `definir_objectif`, `avancer_phase` (**lu**,
  confronté au catalogue de `agent_tools/`).
- **L'en-tête des groupes affiche toujours le nom brut** : « 6× search_cards »,
  « 10× delete_excerpt », huit groupes de ce type dans une seule conversation
  (**reproduit**).
- `ApprovalCard` affiche `{tool}` en police machine dans les deux variantes.
- Accents manquants : « Lit les metadonnees » (**reproduit**), « Ecrit le
  contenu », « Cree une attestation », « Ecrit le fichier ».

Correctif structurel : un test qui échoue dès qu'un outil du catalogue serveur
n'a pas de libellé, un repli qui n'affiche jamais un nom à tiret bas, et des
libellés au pluriel pour les groupes (« Supprime 10 extraits »).

### B4. « Réessayer » n'est pas un nouvel essai

**Lu.** Le bouton appelle `continuer()`, qui envoie le message littéral
« continue ». Si l'erreur est survenue avant la création de la session, cela
ouvre une nouvelle conversation intitulée « continue ». Il doit renvoyer le
dernier message de l'utilisateur.

### B5. L'interface peut rester bloquée sur « Arrêter »

**Lu.** Les boutons « Continuer » et « Réessayer » font `continuer();
enCours = true;`. Quand `continuer()` sort tout de suite (reprise en cours),
`enCours` reste vrai sans flux derrière : la zone de saisie affiche « Arrêter »
pour toujours, jusqu'au rechargement.

### B6. N'importe quel compte change le modèle gratuit de tout le monde

**Lu.** `PUT /agent/mode-gratuit/modele` documente « toute l'instance » et
n'exige que `get_current_user`. Le sélecteur est montré à chaque utilisateur.
C'est un défaut de sécurité, pas seulement d'interface : réserver l'écriture à
l'administrateur, et ne montrer qu'une lecture aux autres.

### B7. Écarté à la vérification

Le libellé « Publier » sur l'approbation de `update_card` semblait faux. Il est
juste : `update_card` ne demande une approbation que lorsqu'il rend la fiche
publique (`est_sensible`, `agent_tools/philum.py`).

### B8. Un résultat en attente au rechargement s'affiche en échec

**Lu.** `depuisMessages` clôt tout appel sans résultat avec « Aucun résultat
reçu », y compris quand le serveur est encore en train de terminer le tour.
Rouvrir une conversation active montre des échecs qui n'en sont pas.

### B10. « 30 messages restants aujourd'hui » est faux

Le chiffre vient de `agent_gratuit_daily_quota_messages = 30`
(`core/config.py`). Le serveur ne décompte un message que si le tour se termine
pendant que la page reste connectée (`agent_chat.py`, après `_persister_tour`),
et le restant est lu avant de compter le message en cours. **Mesuré en
production**, sur des conversations toutes en mode gratuit :

| Jour | Envoyés | Décomptés |
|---|---|---|
| 24 août | 14 | 12 |
| 27 août | 8 | 2 |
| 30 août | 9 | 1 |
| 31 août | 6 | 1 |
| 10 sept. | 3 | 0 |
| 11 sept. | 1 | 0 |

Décision de l'utilisateur, le 2026-09-11 : un chiffre faux ne s'affiche pas.
L'affichage est retiré. Le plafond lui-même n'est pas touché : il ne se
déclenche jamais puisqu'il sous-compte, et le rendre exact bloquerait les jours
chargés (59 messages le 23 août). Sa suppression ou sa correction est une
décision à part.

### B9. Tirets cadratins dans l'interface

**Lu.** Le message de réussite du test du mode gratuit sépare « OK » et le nom
du modèle par un tiret cadratin (`ChatPanel.svelte`, `testerGratuit`).

---

## 2. Espace et hiérarchie

Mesures faites à 1536 × 695 px.

| Ce qui est mesuré | Valeur |
|---|---|
| Largeur de la colonne de conversation, page de liste | **672 px, 44 % de l'écran** |
| Largeur utile, page d'une conversation (`max-w-3xl`) | 720 px |
| Hauteur du fil, page de liste | **348 px, 50 % de l'écran** |
| Hauteur du fil, page d'une conversation | 426 px |
| Défilement de la page entière sous le chat | 66 px, dû au pied de page du site |

Au-dessus du fil, sur la page de liste, se succèdent jusqu'à neuf blocs : le
titre « Agent », la phrase d'état, le champ de nom, la barre des sélecteurs, la
description de l'agent, les messages de test, l'objectif. En dessous : le bouton
« Nouveaux messages », la ligne d'usage, la bannière du mode gratuit (trois
lignes), la zone de saisie.

Cible : **le fil occupe au moins 80 % de la hauteur**. Pour y arriver :

1. **Une mise en page d'application** sur `/dashboard/chat` : pas de pied de
   page du site, barre de navigation compacte, liste à gauche repliable, fil au
   centre, zone de saisie ancrée en bas.
2. **Le texte à largeur de lecture, le reste à pleine largeur.** Autour de
   48 rem pour la prose, les cartes d'outils et les tableaux peuvent aller au
   delà.
3. **Les réglages dans la zone de saisie**, comme chez Claude et ChatGPT : une
   pastille « GLM 4.5 Flash » qui ouvre un menu (agent, clé, modèle, test, mode
   gratuit). La ligne de réglages permanente disparaît.
4. **Le nom de la conversation dans l'en-tête**, modifiable en place. Plus de
   champ dédié.
5. **La bannière du mode gratuit réduite à une pastille** (« Mode gratuit ·
   30 restants ») dont le détail s'ouvre au clic. L'avertissement complet reste
   au consentement, où il est déjà.
6. **L'usage dans un survol** de la pastille de modèle, en français (« 12 k
   jetons envoyés, 3 k reçus »), et non « prompt · completion ».
7. **Mobile** : sous `lg`, la liste de 24 conversations passe au-dessus du fil
   et repousse la saisie hors de l'écran (**lu**). Il faut un tiroir.

---

## 3. Lecture des actions de l'agent

- **Un mur de cartes.** Une conversation compte 64 cartes d'outils, dont des
  groupes de 10 et 11 suppressions affichés carte par carte (**mesuré**). Un
  groupe doit être replié par défaut sur une ligne (« Supprime 11 extraits ·
  terminé ») et se déplier au clic.
- **Un résumé d'activité par tour**, replié : « 23 actions : 6 fiches lues,
  11 extraits supprimés, 1 échec ». C'est ce que Claude fait avec ses étapes, et
  qui garde le fil lisible.
- **Les arguments en vue structurée**, pas en JSON brut : « Source : Revisiting
  the Warburg effect », « Texte : … (1 240 caractères, voir tout) ». Le JSON
  reste accessible derrière un lien.
- **Les tableaux Markdown ne sont pas pris en charge** (**lu**, aucune règle dans
  `lib/agent/markdown.ts`). Un tableau de l'agent s'affiche en barres
  verticales.
- **Aucun bouton pour copier** un message, un bloc de code ou un extrait.
- `aria-live="polite"` sur tout le fil : un lecteur d'écran lit chaque jeton
  reçu (**lu**). Annoncer la fin du tour, pas le flux.

---

## 4. Ce que Claude et ChatGPT font, et que Philum ne fait pas

| Geste | Pourquoi il compte |
|---|---|
| Modifier et renvoyer son dernier message | corriger une consigne sans tout retaper |
| Régénérer une réponse | le modèle gratuit se trompe souvent |
| Liste groupée par date, recherche dans les conversations | 24 conversations déjà, sans repère |
| Renommer et supprimer depuis la liste, conversation active surlignée | aujourd'hui, renommer n'existe que dans la page d'une conversation |
| Brouillon gardé par conversation | un texte en cours se perd à la navigation |
| Focus automatique dans la saisie, Échap pour arrêter, raccourci de nouvelle conversation | le clavier ne sert qu'à Entrée |
| Coller une adresse ou déposer un fichier dans la saisie | la première amorce demande une URL, sans aide pour la donner |
| Mentionner une fiche (`@`) ou choisir un agent (`/`) depuis la saisie | aujourd'hui, un menu déroulant en haut |

Les amorces remplissent la saisie sans y placer le curseur, et « Crée une fiche
pour cette vidéo YouTube : » attend une URL que rien n'invite à coller.

---

## 5. Ce qui dépasserait Claude et ChatGPT

**Le panneau de fiche vivante.** Claude a ses artefacts, ChatGPT son canevas :
la conversation produit un objet, affiché à côté. Chez Philum, cet objet existe
déjà : c'est la fiche. Pendant que l'agent ajoute des sources et pose des
extraits, la fiche se met à jour dans un panneau à droite, avec les verdicts de
relecture, les rétractations et les archives. Chaque carte d'outil devient
cliquable et amène à la source ou à l'extrait concerné dans ce panneau.

C'est le seul geste de cette liste qu'aucun des deux ne peut copier, parce qu'ils
n'ont pas d'objet vérifié à montrer.

---

## 6. Découpage proposé

| # | Contenu | Taille |
|---|---|---|
| 1 | **Bugs** : B1 (layout partagé, navigation, liste rafraîchie, nom en place), B2 (débordement), B3 (libellés et test de complétude), B4, B5, B6 (garde administrateur), B8, B9, B10 (compteur retiré) | M |
| 2 | **Espace** : mise en page d'application, réglages dans la saisie, pastille du mode gratuit, fil à 80 %, tiroir mobile | M |
| 3 | **Lecture des actions** : groupes repliés, résumé d'activité, vue structurée des arguments, tableaux Markdown, copie, région vivante | M |
| 4 | **Confort** : modifier et renvoyer, régénérer, liste par date avec recherche, brouillons, raccourcis, collage d'URL | M |
| 5 | **Panneau de fiche vivante**, demandé par l'utilisateur le 2026-09-11 : un panneau qui s'ouvre à droite en mode agent, montre le fil et la page de la fiche côte à côte, et met la fiche à jour à chaque action de l'agent | L |

La PR 1 corrige ce qui est faux aujourd'hui et ne change pas l'apparence. Les
PR 2 à 5 la supposent mergée.

---

## 7. Avancement

**PR 1, #641** : mergée et déployée le 2026-09-11. **Validée en production** sur
la conversation « supprime les doublons » : barre latérale présente et
conversation active surlignée, aucun nom technique, groupes au pluriel
(« Supprime 11 extraits »), aucun débordement horizontal.

Piège payé au déploiement : la configuration est sensible à la casse
(`case_sensitive=True` dans `core/config.py`). Posée en `AGENT_ADMIN_EMAILS`, la
variable arrivait dans le conteneur mais le champ restait vide, et le
propriétaire perdait le choix du modèle. Elle s'écrit `agent_admin_emails`,
comme les autres lignes du `.env`.

**PR 2, #642** (place à l'écran) et **PR 3, #643** (lecture des actions) :
ouvertes, empilées.

**PR 4** (confort) : deux écarts au diagnostic, assumés.

- **« Modifier et renvoyer » devient « Reprendre ».** Le message revient dans la
  zone de saisie et part comme un nouveau message. L'historique n'est pas
  réécrit : l'agent a peut-être écrit en base pendant ce tour, et un historique
  tronqué le lui cacherait.
- **« Régénérer » n'est pas fait.** Rejouer un tour relancerait ses écritures :
  une source ajoutée le serait deux fois. « Réessayer », après une erreur, reste
  la seule relance, et seulement pour un tour qui a échoué.
