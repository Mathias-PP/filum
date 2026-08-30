# Intégration des quatre dépôts audités

> **Pour l'agent qui exécute.** Une PR à la fois : merger, déployer, vérifier en
> prod, passer à la suivante. Français partout. Aucun tiret cadratin, nulle part
> (prose, code, commentaires, commits, corps de PR). Jamais `python -m pytest`,
> toujours `uv run pytest` depuis `apps/backend`.

## D'où vient ce plan

Quatre dépôts lus en entier, deux audits écrits : [`10-externes`](../audit/10-externes/CONTEXT.md)
(book-to-skill, open-notebook, OmniRoute) et [`11-graph-memory`](../audit/11-graph-memory/CONTEXT.md)
(graph-memory-starter). Ce plan ne reprend que ce qui a survécu à la lecture du
code. Ce qui a été écarté est listé en fin de document, pour qu'une session
future ne le repropose pas.

Cinq PR, aucune ne dépend d'une autre. L'ordre est celui du rapport valeur sur
risque, pas celui des dépôts.

| # | Branche | Origine | Taille |
|---|---|---|---|
| 1 | `feat/texte-tiers-assaini` | book-to-skill | S, livrée le 2026-08-30 (#612) |
| 2 | `fix/echec-jamais-vide` | open-notebook | annulée : déjà fait, voir la section |
| 3 | `fix/graph-memory-rappel-honnete` | graph-memory-starter, lot A | M |
| 4 | `feat/recherche-fusion-rrf` | graph-memory-starter, `rag/search.py` | M |
| 5 | `feat/agent-repli-fournisseur` | OmniRoute | M |

---

## Commandes de référence

```bash
# Backend, depuis apps/backend
rm -f test.db && CI=true uv run pytest tests/unit tests/integration -q
uv run ruff check . && uv run ruff format . && uv run mypy app --ignore-missing-imports
CI=true uv run python -m app.scripts.export_openapi

# Frontend, depuis apps/frontend
pnpm run check && pnpm run lint && pnpm test
pnpm run generate:api
npx prettier --write <fichier>

# PR (le token n'a pas read:org, --body-file echoue : passer --body)
gh pr create --title "..." --body "..." --base main
gh pr view <n> --json statusCheckRollup \
  --jq '[.statusCheckRollup[]|select(.state!="SUCCESS" and .state!="SKIPPED")]|length'
gh pr merge <n> --squash

# Deploiement VM
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  "sudo -n -u mathias_pinault bash -c 'cd ~/filum && git pull --ff-only origin main'"
ssh -i ~/.ssh/id_ed25519 mathias.pinault@philum-api.duckdns.org \
  "sudo -n bash -c 'cd /home/mathias_pinault/filum/infra/oracle && \
   docker compose -f docker-compose.micro.yml up -d --build backend'"
curl -s https://philum-api.duckdns.org/health
```

---

# PR 1 : `feat/texte-tiers-assaini`

**Ce que le dépôt apporte.** `book_to_skill/sanitize.py` répond à une question
que Philum n'a jamais posée : un texte tiers peut porter des caractères que le
modèle lit et que personne ne voit. Zéro largeur, contrôles bidirectionnels
(Trojan Source, CVE-2021-42574), remplisseurs Hangul, bloc de balises
`U+E0000-E007F`, sélecteurs de variation, contrôles d'annotation interlinéaire.
Le bloc de balises seul suffit à cacher une charge ASCII entière derrière un
caractère qui s'affiche normalement.

Philum lit du texte tiers à deux endroits, et ne l'assainit à aucun. C'est le
cas d'usage le plus direct qui soit : `fetch_url` verse le texte d'une page
arbitraire dans le contexte du modèle.

**La leçon du dépôt, au-delà du code :** le prédicat est exposé
(`is_invisible_codepoint`) parce que l'extracteur et le scanner doivent partager
exactement la même définition. Deux listes qui divergent laissent passer ce que
l'autre signale. Philum reprend ce choix : un seul module, une seule table.

**À ne pas recopier :** le fichier source porte de la redondance
(`_ANNOTATION_FORMAT_CODEPOINTS` et `_ANNOTATION_CODEPOINTS` déclarent deux fois
`U+FFF9-FFFB`, et `_DEPRECATED_FORMAT_RANGE` redouble `U+206A-206F` déjà
présent). La version Philum est dédupliquée.

**Fichiers**
- Créer : `apps/backend/app/services/texte_invisible.py`
- Modifier : `apps/backend/app/services/document_text.py:130` (`extract_text`)
- Modifier : `apps/backend/app/api/v1/endpoints/excerpts.py:185` (`_texte_de_la_source`)
- Modifier : `apps/backend/app/agent_tools/web.py:31` (`_rechercher`)
- Test : `apps/backend/tests/unit/test_texte_invisible.py`

- [x] **1.1 Le module**

```python
"""Retire d'un texte tiers les caracteres que le modele lit et que nul ne voit.

Un texte recupere sur le web ou depose par un tiers peut porter des points de
code qui ne rendent rien a l'ecran mais qui entrent tels quels dans le contexte
du modele. L'humain qui relit et l'agent qui execute ne lisent alors pas la meme
chose, ce qui est exactement la condition d'une injection par document.

Le predicat est expose separement de la fonction de nettoyage : tout appelant
qui veut signaler plutot que retirer doit partager la meme definition, sinon les
deux couches divergent et laissent passer ce que l'autre signale.
"""

from __future__ import annotations

# Espaceurs de largeur nulle et joncteurs. Ne rendent rien, donc le texte place
# entre eux est invisible a la lecture et lisible par le modele.
_LARGEUR_NULLE = frozenset({
    0x00AD, 0x034F, 0x061C, 0x180E, 0x200B, 0x200C, 0x200D,
    0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF,
})

# Controles bidirectionnels, la classe Trojan Source (CVE-2021-42574). Ils ne
# changent pas la suite de caracteres que le modele lit, ils changent l'ordre
# que l'humain voit. Les ecritures droite a gauche ne sont pas touchees :
# l'algorithme Unicode derive la direction des caracteres eux-memes.
_BIDIRECTIONNELS = frozenset({
    0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
    0x2066, 0x2067, 0x2068, 0x2069,
})

# Lettres de largeur nulle. Ce ne sont pas des controles de format, donc un
# filtre par categorie les manque, et ce ne sont pas des espaces, donc la
# normalisation des blancs les garde.
_REMPLISSEURS_HANGUL = frozenset({0x115F, 0x1160, 0x3164, 0xFFA0})

# Controles d'annotation interlinéaire : un moteur de rendu conforme masque ce
# qui est place entre l'ancre et le terminateur.
_ANNOTATION = frozenset({0xFFF9, 0xFFFA, 0xFFFB})

_PONCTUELS = _LARGEUR_NULLE | _BIDIRECTIONNELS | _REMPLISSEURS_HANGUL | _ANNOTATION

# Plages. Le bloc de balises et les selecteurs de variation portent chacun une
# charge arbitraire : une suite de selecteurs apres n'importe quel caractere
# encode 256 valeurs par position, en ne rendant rien du tout. Les controles de
# format obsoletes et les controles de portee musicale completent la liste.
_PLAGES = (
    (0x206A, 0x206F),    # formats obsoletes, symmetric swapping, digit shapes
    (0xFE00, 0xFE0F),    # selecteurs de variation 1 a 16
    (0x1D173, 0x1D17A),  # ligatures et phrases musicales
    (0xE0000, 0xE007F),  # bloc de balises
    (0xE0100, 0xE01EF),  # selecteurs de variation 17 a 256
)


def est_invisible(point_de_code: int) -> bool:
    """Vrai si le point de code ne rend rien et doit etre retire."""
    if point_de_code in _PONCTUELS:
        return True
    return any(bas <= point_de_code <= haut for bas, haut in _PLAGES)


def assainir(texte: str) -> tuple[str, int]:
    """Rend le texte sans ses caracteres invisibles, et combien ont ete retires."""
    retires = sum(1 for c in texte if est_invisible(ord(c)))
    if not retires:
        return texte, 0
    return "".join(c for c in texte if not est_invisible(ord(c))), retires
```

Le coût du retrait est assumé et il est faible : perdre `U+200D` casse les
séquences emoji composées, perdre les sélecteurs de variation retire l'indice de
présentation emoji contre texte. Sur de la prose citée, aucun des deux ne porte
de sens.

- [x] **1.2 Brancher les trois entonnoirs**

`extract_text` (dépôt de fichier), juste avant la vérification de `MAX_CHARS` :
le texte assaini est celui qui compte, pas celui qui est reçu.

`_texte_de_la_source` : sept points de retour. Ne pas les assainir un par un.
Renommer le corps en `_texte_de_la_source_brut`, et faire de
`_texte_de_la_source` une enveloppe qui appelle `assainir` une fois. Un seul
passage, aucune branche à oublier plus tard. Journaliser en `info` quand des
caractères sont retirés, avec l'URL et le nombre.

`_rechercher` dans `web.py` : titres et extraits viennent d'une API tierce et
partent au modèle sans passer par `_texte_de_la_source`.

- [x] **1.3 Tests**

- `test_bloc_de_balises_retire` : une charge ASCII encodée en `U+E0041`
  et suivantes disparaît entièrement.
- `test_override_bidirectionnel_retire` : `U+202E` retiré.
- `test_arabe_intact` : un texte arabe sans contrôle explicite ressort identique
  et le compteur vaut zéro.
- `test_compteur` : `assainir` rend le nombre exact de caractères retirés.
- `test_texte_propre_rend_le_meme_objet` : compteur à zéro, pas de recopie.
- `test_les_deux_entonnoirs_assainissent` : `extract_text` sur un `.txt` piégé,
  et `_texte_de_la_source` avec `_html_scrape` simulé rendant du texte piégé.

- [x] **1.4 Vérifier, commit, PR, merge, déployer.**

Vérification prod : `fetch_url` sur une page connue, la réponse ne doit pas
changer visiblement. C'est un correctif silencieux, son effet se lit dans les
journaux.

---

# PR 2 : `fix/echec-jamais-vide` (ANNULÉE, rien à faire)

**Ce que le dépôt apporte.** `open_notebook/utils/error_classifier.py` range les
échecs d'un fournisseur dans un petit ensemble fermé de causes, chacune portant
un message destiné à l'utilisateur. Le principe qui compte est en amont du
fichier : **une recherche qui échoue ne rend jamais une liste vide.** Une liste
vide dit « ce corpus ne contient rien là-dessus », et le modèle, entendant cela,
comble en fabriquant. Une erreur dit « je n'ai pas pu chercher », et le modèle
s'arrête ou change de voie.

## Annulée le 2026-08-30, après vérification

**Philum porte déjà tout ce que cette PR prévoyait, et le porte mieux que le
dépôt dont elle s'inspirait.** La prémisse écrite ci-dessus était fausse : elle
supposait que `embed()` rendant `None` faisait rendre `[]`. Rien n'est livré.

| Ce qui était prévu | Ce qui existe déjà |
|---|---|
| distinguer le vide constaté du vide subi | `excerpt_search.rechercher:174-181` rend `None` pour « n'a pas pu chercher » et `[]` pour « a cherché, rien trouvé ». Le commentaire de `ExcerptSearchResponse.available` (`endpoints/excerpt_search.py:48-53`) énonce exactement le principe qu'on croyait importer |
| interdire de combler quand la recherche web est absente | `web.py:124-134`, qui va plus loin : il dit pourquoi combler serait sans effet, et l'outil n'est même pas exposé au modèle sans fournisseur configuré (`web_tools:194-204`) |
| une recherche en panne rend une erreur, pas une liste | `web.py:135-138` |
| classer les échecs amont | `agent_providers._classify:488-523`, meilleur que `error_classifier.py` : priorité au code d'erreur du corps sur le cadrage HTTP, et conservation du message brut du fournisseur au lieu de le noyer dans une reformulation |

**Le seul reste réel :** `_classify` ne sert qu'à l'endpoint de test de clé. La
boucle de chat reconstruit ses propres messages (`agent.py:466`, `:502`, `:732`).
C'est une duplication, mais c'est le terrain de la PR 5, qui a besoin de cette
classification pour rendre son verdict de repli. Repliée là, pas traitée seule.

**À ne pas reprendre :** la discipline de citation d'open-notebook vit
entièrement dans ses gabarits Jinja, c'est-à-dire nulle part. Philum vérifie le
verbatim dans le code (`excerpt_anchor.ancrer`), ce qui est strictement meilleur.
Ne pas remplacer du code par du prompt.

**Fichiers**
- Modifier : `apps/backend/app/services/excerpt_search.py`
- Modifier : `apps/backend/app/agent_tools/web.py:95` (`_execute_web_search`)
- Modifier : `apps/backend/app/mcp_server/tools.py` (l'outil de recherche d'extraits)
- Test : `apps/backend/tests/unit/test_recherche_echec.py`

- [ ] **2.1 Distinguer les trois états d'une recherche**

Une recherche rend l'un de trois états, jamais un quatrième :

| État | Signification | Ce que l'outil rend |
|---|---|---|
| `resultats` | la requête a abouti, voici ce qui correspond | la liste, éventuellement vide |
| `indisponible` | la recherche n'a pas pu tourner | une erreur nommant la cause |
| `non_configure` | la capacité n'existe pas sur ce serveur | une erreur qui le dit et interdit de combler |

Aujourd'hui, `embed()` qui rend `None` (modèle d'embedding absent ou en panne)
fait rendre une liste vide par `excerpt_search`. C'est le cas exact à corriger :
il faut lever, pas rendre `[]`.

- [ ] **2.2 Les messages nomment la suite**

Reprendre le ton déjà en place dans `_pourquoi_illisible` (`web.py:119-148`), qui
est le meilleur exemple du dépôt : dire la cause, dire si insister sert, dire
quoi faire, et interdire explicitement l'invention. Étendre ce ton aux trois
états ci-dessus.

Pour `non_configure` sur la recherche web, le message doit être :
« Recherche web non configurée sur ce serveur. Dites-le au créateur. Ne
proposez pas de sources tirées de votre mémoire. »

- [ ] **2.3 Tests**

- `test_embedding_indisponible_leve` : `embed` simulé rendant `None`, la
  recherche lève au lieu de rendre `[]`.
- `test_corpus_sans_correspondance_rend_liste_vide` : le vide constaté reste un
  résultat valide, pas une erreur.
- `test_recherche_web_non_configuree_dit_de_ne_pas_inventer`.

- [ ] **2.4 Vérifier, commit, PR, merge, déployer.**

---

# PR 3 : `fix/graph-memory-rappel-honnete`

Lot A de l'audit 11, plus les corrections de portée. Sans regret quel que soit le
sort futur du graphe, parce qu'il corrige un rappel aujourd'hui faux.

**Fichiers**
- Modifier : `apps/backend/app/services/graph_memory.py`
- Modifier : `apps/backend/app/services/agent.py:1236-1259`
- Modifier : `apps/backend/app/mcp_server/server.py:760` (`rebuild_graph`)
- Test : `apps/backend/tests/unit/test_graph_memory.py`

- [x] **3.1 Défaut 1 : le repli sémantique est du code mort**

`graph_memory.py:255-277` lit une colonne `embedding` que `:153-156` n'écrit
jamais. Le `WHERE embedding IS NOT NULL` filtre donc toute la table, après un
appel réseau, sous un `except` silencieux.

**Décision : retirer la branche.** La remplir supposerait d'embarquer chaque nom
d'entité, pour un graphe dont la valeur reste à établir (défaut 7). Retirer
supprime un appel réseau par rappel et une illusion de repli. Le laisser tel quel
n'était pas une option.

- [x] **3.2 Défaut 2 : le slug, pas l'UUID**

`:39` et `:287` injectent `r.source_card_id`, un UUID. Le modèle lit
`(7c9a1f2e-...)` là où il devrait lire `(les-mitochondries)`. Joindre
`biblio_cards` dans `WALK_SQL` et rendre le slug.

- [x] **3.3 Défauts 3 et 4 : le nœud CARD issu du titre**

`:136-138` crée un nœud nommé par le titre de la fiche, alors que `:163` et
`:197` rattachent les arêtes au nœud nommé par le slug. Nommer une fiche par son
titre amorce donc sur un nœud sans arête, et rend `no memory matches` alors que
le graphe porte la réponse. L'alias créé en `:138` vaut le nom du nœud, c'est un
non-opérateur.

Correction : un seul nœud CARD, identifié par le slug, et le titre devient un
alias réel qui pointe vers lui.

- [x] **3.4 Défaut 5 : l'amorçage**

`:222-237` cherche par sous-chaîne, avec un `OR` sur tous les mots de la requête
et aucun mot vide retiré. Le dépôt (`src/recall.py:67`) cherche par mot entier.
Conséquence chez Philum : la requête « quelles sources de la fiche » amorce sur
tout nœud contenant « de », c'est-à-dire à peu près tous.

Correction : mot entier, mots vides français et anglais retirés, longueur
minimale de trois caractères.

- [x] **3.5 Défaut 6 : le vocabulaire déclaré**

`:16-29` déclare 7 types d'entité et 11 prédicats. Le constructeur en écrit 4 et
3. Réduire les constantes à ce qui est réellement écrit. Coût nul, et cela évite
qu'une session future croie disposer d'un vocabulaire qui n'existe pas.

- [x] **3.6 Défaut 8 : la durée fabriquée et le contexte non borné**

`agent.py:1250` écrit `(rappel automatique, 2 ms)` en dur, alors que `Facts.ms`
porte la mesure. Utiliser la mesure. Borner le nombre de faits injectés, en
disant combien ont été écartés plutôt qu'en tronquant en silence.

Traduire au passage les chaînes de `Facts.as_text()` (`:67`, `:69`), restées en
anglais depuis le portage, dans un projet qui est en français partout.

- [x] **3.7 Défaut 9 : `rebuild_graph` est globalement destructif**

`graph_memory.py:86-88` vide les trois tables, `server.py:760-771` expose
l'opération à tout compte authentifié. Tout utilisateur peut donc vider et
reconstruire le graphe de tous.

Le graphe ne porte que des fiches publiées et publiques, donc ce n'est pas une
fuite : c'est un déni de service et une reconstruction non sollicitée.

Il n'existe pas de notion de superutilisateur sur `User`, et en inventer une
pour un seul outil coûterait une migration et un modèle de permissions que rien
d'autre ne réclame. Correction retenue : un délai de cinq minutes entre deux
reconstructions (`ReconstructionTropRecenteError`), et un libellé qui dit que le
graphe est global. Le délai supprime le vrai dommage, qui est le coût répété ;
le libellé supprime la surprise.

- [x] **3.8 Tests, commit, PR, merge, déployer.**

Vérification prod : `recall_memory` sur le titre d'une fiche publiée doit rendre
des faits, et les identifiants affichés doivent être des slugs.

**Ce que cette PR ne tranche pas.** Le défaut 7 reste ouvert : les trois arêtes
du graphe sont toutes des clés étrangères, la chaîne la plus longue fait deux
sauts pour un parcours réglé à trois. Le graphe redouble une jointure SQL. Le
trancher (retirer, ou lui donner des arêtes qu'une jointure ne donne pas) est une
décision, pas un travail, et elle appartient à l'utilisateur.

---

# PR 4 : `feat/recherche-fusion-rrf`

**Ce que le dépôt apporte.** `rag/search.py:60-67`, huit lignes, `K = 60` :
chaque jambe de recherche classe ses résultats, et le score fusionné d'un
document est la somme des `1 / (K + rang)` sur les jambes où il apparaît. Pas de
calibration, pas de seuil à régler, et surtout aucune comparaison entre des
scores qui ne sont pas commensurables.

Philum a déjà les deux jambes et ne les fusionne pas :

| Jambe | Où | Comment |
|---|---|---|
| sémantique | `excerpt_search.py:52`, `:219` | cosinus, seuillé à 0.60 |
| lexicale | `tools_write.py:1380-1403` | `ILIKE`, trié par date |

Elles ne se voient pas. Un extrait qui contient exactement le mot cherché mais
dont le sens est loin de la requête sort de l'une et pas de l'autre, et
réciproquement. Le tri par date de la jambe lexicale est arbitraire.

**Ce qui compte autant que la fusion :** le dépôt rend `found_by`, c'est-à-dire
quelle jambe a trouvé quoi. Sans cela, la fusion est une boîte noire de plus.
Avec, l'utilisateur voit pourquoi un extrait est remonté.

**Fichiers**
- Créer : `apps/backend/app/services/fusion_rangs.py`
- Modifier : `apps/backend/app/services/excerpt_search.py`
- Modifier : `apps/backend/app/mcp_server/tools_write.py:1380-1403`
- Test : `apps/backend/tests/unit/test_fusion_rangs.py`

- [x] **4.1 Le mécanisme**

```python
K_RANG = 60
"""Constante du rang reciproque, reprise telle quelle de la litterature.

Elle amortit l'ecart entre les premieres places : passer du rang 1 au rang 2
coute peu, ce qui evite qu'une seule jambe tres sure impose son ordre. Aucune
calibration sur notre corpus ne la justifie, et aucune n'est necessaire :
c'est precisement l'interet de la methode, qui ne compare jamais deux scores
issus d'echelles differentes.
"""
```

La fusion prend des listes ordonnées d'identifiants, rend les identifiants
triés par score décroissant, et pour chacun l'ensemble des jambes qui l'ont
trouvé. Elle ne connaît ni extraits ni embeddings : elle est testable seule.

- [x] **4.2 Le seuil sémantique reste**

`SIMILARITE_MINIMALE = 0.60` est une mesure faite sur le corpus de production, et
son commentaire (`excerpt_search.py:39-51`) documente pourquoi le plancher
initial de 0.30 ne coupait rien. La fusion s'applique **après** le seuil, pas à
sa place : un extrait sémantiquement hors sujet ne doit pas remonter au seul
motif qu'il est premier de sa liste.

Symétriquement, la jambe lexicale garde son `ILIKE` mais perd son tri par date,
qui n'ordonne rien de pertinent. Elle rend l'ordre du plus grand nombre
d'occurrences.

- [x] **4.3 `found_by` remonte jusqu'à l'appelant**

Ajouter le champ au `Resultat` de `excerpt_search.py:62-81` et à la réponse de
l'outil MCP. Valeurs possibles : `sens`, `mots`, ou les deux.

- [x] **4.4 Tests**

- `test_rrf_recompense_l_accord` : un identifiant présent dans les deux jambes
  au rang 2 passe devant un identifiant premier d'une seule jambe.
- `test_rrf_jambe_vide` : une jambe vide ne change pas l'ordre de l'autre.
- `test_found_by_nomme_les_deux_jambes`.
- `test_seuil_semantique_applique_avant_fusion`.

- [x] **4.5 Vérifier, commit, PR, merge, déployer.**

**Ce qui n'est pas repris de ce dépôt.** La distillation à l'écriture (générer
les questions auxquelles un extrait répond, gardées par une citation exacte
vérifiée deux fois) est le troisième manque identifié par l'audit 11. Elle est
réelle mais elle ajoute un appel de modèle par extrait et un champ en base :
chantier à cadrer séparément, pas à glisser ici.

---

# PR 5 : `feat/agent-repli-fournisseur`

**Ce que le dépôt apporte.** OmniRoute résout le problème que Philum a
aujourd'hui : que faire quand un fournisseur refuse. Trois fichiers courts
portent l'essentiel.

`nonRetryableUpstream.ts` (100 lignes) : la liste fermée des erreurs amont qu'il
ne faut **ni** réessayer **ni** faire payer à la clé suivante. Une clé invalide,
une requête malformée, un refus de filtrage de contenu : basculer sur une autre
clé ne fait que reproduire l'échec, et compte à tort un incident contre une clé
saine. C'est la distinction que Philum n'a pas.

`cooldownCap.ts` (26 lignes) : le temps d'écart après incident croît, mais il est
plafonné. Sans plafond, une panne de dix minutes met une clé au repos pour des
heures.

`emergencyFallback.ts` : chaque décision de repli est une union discriminée qui
**porte sa raison**. Le repli n'est jamais silencieux, il est toujours
explicable.

**État de Philum.** `agent.py` gère déjà le 429 avec `retryDelay`
(`:401-405`, `:696-735`), le repli 400 vers le mode bloquant (`:739`) et le retry
5xx (`:891-909`). Mais `agent_providers.resoudre_defaut` (`:318`) choisit **un**
fournisseur, et s'il refuse, le tour échoue. L'utilisateur a plusieurs clés
configurées et l'agent n'en essaie qu'une.

**Ce qui est explicitement écarté.** OmniRoute fait 2405 lignes rien que pour son
`accountFallback.ts`, avec un scoring multifactoriel de sélection de compte.
C'est une échelle de plateforme multi-locataires. Philum a trois fournisseurs et
un utilisateur par session : reprendre le scoring serait de la complexité sans
objet. On prend la classification, le plafond, et la raison portée. Rien d'autre.

**Fichiers**
- Créer : `apps/backend/app/services/agent_repli.py`
- Modifier : `apps/backend/app/services/agent_providers.py:488` (`_classify`)
- Modifier : `apps/backend/app/services/agent.py` (`_appel_provider`, `boucle`)
- Modifier : `apps/frontend/src/lib/components/chat/` (affichage de l'événement)
- Test : `apps/backend/tests/unit/test_agent_repli.py`

- [x] **5.1 Classer l'échec amont**

```python
class Verdict(StrEnum):
    REESSAYER = "reessayer"      # 5xx, timeout reseau : la meme cle, plus tard
    REPLIER = "replier"          # 429, quota epuise : une autre cle, maintenant
    ABANDONNER = "abandonner"    # cle invalide, requete malformee, filtrage
```

`ABANDONNER` est la valeur qui manque aujourd'hui, et c'est celle qui compte : un
401 sur une clé révoquée ne doit pas faire tourner les deux autres clés pour
échouer trois fois au lieu d'une, ni marquer les clés saines comme fautives.

Chaque verdict porte une `raison` en français, destinée à être lue.

- [x] **5.2 Repos plafonné**

Après un `REPLIER`, la clé est mise au repos pour un temps croissant, plafonné à
15 minutes. En mémoire de processus, pas en base : Philum tourne sur un seul
conteneur, et persister un état de santé transitoire coûterait une migration pour
rien. Le noter dans le commentaire, pour qu'un futur passage en multi-instance
sache où regarder.

- [x] **5.3 La boucle essaie les clés du créateur**

`resoudre_defaut` rend aujourd'hui un fournisseur. Ajouter `ordonner_pour_chat`,
qui rend la liste des fournisseurs du créateur, le défaut en tête, les clés au
repos en queue. `_appel_provider` parcourt la liste selon le verdict.

- [x] **5.4 Le repli se voit**

Nouvel événement SSE `repli_fournisseur`, portant le fournisseur quitté, celui
pris, et la raison. Affiché dans le fil comme une ligne discrète, pas comme une
erreur : l'agent a continué.

**Attention à l'invariant.** `agent/audit/_core/invariants.txt` fige 12 événements
SSE. En ajouter un le fait passer à 13 : mettre à jour le fichier et la ligne du
tableau de bord de `agent/audit/CONTEXT.md` dans le même commit, sinon la porte
G8 devient rouge, ce qui est le comportement voulu.

- [x] **5.5 Tests**

- `test_401_abandonne_sans_essayer_les_autres_cles`.
- `test_429_replie_sur_la_cle_suivante`.
- `test_repos_plafonne_a_quinze_minutes`.
- `test_toutes_les_cles_epuisees_rend_une_erreur_qui_les_nomme`.
- `test_evenement_repli_porte_la_raison`.

- [x] **5.6 Vérifier, régénérer openapi et `generated.ts`, prettier, commit, PR, merge, déployer.**

---

## Écarté, et pourquoi

Pour qu'une session future ne le repropose pas.

| Élément | Dépôt | Motif |
|---|---|---|
| Le reste de `book_to_skill` (découpage, génération de skill) | book-to-skill | hors sujet : Philum ne génère pas de skills |
| La discipline de citation par gabarit Jinja | open-notebook | Philum vérifie le verbatim dans le code, ce qui est meilleur ; ne pas remplacer du code par du prompt |
| Le cadrage « recherche duale » de l'audit 10 | open-notebook | relecture faite : le dépôt ne fait pas ce que l'audit lui prête |
| `accountFallback.ts` (2405 lignes), scoring multifactoriel | OmniRoute | échelle plateforme multi-locataires, sans objet pour trois fournisseurs |
| Le tableau d'évaluation et le « 3.1x retrieval quality » | graph-memory-starter | le graphe est construit sur `corpus/` curé, la recherche tourne sur `corpus-before/` désordonné : l'écart mesure deux effets à la fois. Ne jamais citer ce chiffre |
| L'argument des 187 étoiles | tous | un décompte d'étoiles n'établit rien ; seule la lecture du code décide |
| Distillation à l'écriture, mémoire de session | graph-memory-starter | manques réels mais chantiers à cadrer, hors de ce plan |
| Le sort du graphe (défaut 7) | graph-memory-starter | décision de l'utilisateur, pas travail d'implémentation |

---

## Vérification après chaque merge

1. `cd apps/backend && rm -f test.db && CI=true uv run pytest tests/unit tests/integration -q`
2. `uv run ruff check .` puis `uv run ruff format .` puis `uv run mypy app --ignore-missing-imports`
3. `cd apps/frontend && pnpm run check && pnpm run lint && pnpm test` si le front a bougé
4. CI verte (zéro job en échec) avant merge
5. Après déploiement, `curl -s https://philum-api.duckdns.org/health`
6. Le test manuel nommé dans la PR

## Pièges déjà payés

- **Formater avant commit** : `ruff format` côté backend, `prettier` sur
  `generated.ts` et les `.svelte`, sinon Lint casse.
- **Contrat API** : régénérer `openapi.json` puis `generated.ts` dans le **même**
  commit dès qu'un endpoint bouge, sinon `test_openapi_sync` échoue. Vérifier le
  saut de ligne final de `openapi.json`.
- **`test.db` périmé** fait échouer les tests : `rm -f test.db` d'abord.
- **Jamais de session `AsyncSession` partagée entre coroutines** : dans un flux
  SSE, écrire en base après `await`, jamais pendant.
- **Svelte 5** : pas de `@const` hors bloc, pas de self-assignment, plus de
  modificateurs d'événement.
- **Le token `gh` n'a pas `read:org`** : passer `--body`, pas `--body-file`.
- **Les invariants de l'audit sont volontairement fragiles** : les mettre à jour
  dans le commit qui les change.

---

# Bilan, le 2026-08-30

Les quatre PR livrables sont en production. La PR 2 reste annulée, ses cases
volontairement vides : rien n'y a été fait parce que rien n'y était à faire.

| PR | Livrée | Ce qui est en prod |
|---|---|---|
| 1 | #612 | l'assainissement du texte tiers que le modèle lit |
| 2 | annulée | Philum portait déjà tout, et mieux |
| 3 | #613 | le rappel du graphe dit ce qu'il porte, avec ses vrais mots |
| 4 | #614 | les mots et le sens cherchent ensemble, et disent lequel a trouvé |
| 5 | #615 | la clé suivante prend le relais, et le repli se voit |

## Ce que l'exécution a appris

**La CI a rattrapé ce que les tests ciblés laissaient passer.** La jambe
lexicale de la PR 4, écrite en SQL textuel, comparait `c.user_id` à
`str(user_id)`, soit la forme à tirets. Le projet stocke ses clés en
hexadécimal nu sous SQLite : `search_my_excerpts` ne trouvait plus rien, et
seul le test de bout en bout le voyait. La leçon tient en une ligne : **le SQL
textuel perd le typage des clés, l'ORM le garde.** La requête sémantique voisine
dort sur le même défaut, mais son SQL doit rester textuel pour porter `<=>`, et
ses tests coupent avant la base faute de pgvector.

**Un invariant d'audit avait dérivé sans que personne le voie.**
`INV_EVENEMENTS_SSE` annonçait 12 ; le compte réel valait 13 depuis #581, qui
avait ajouté `controle_relance` sans toucher au fichier. La PR 5 le porte à 14 et
documente les deux dérives. `check_inventaire.sh` ne l'avait pas signalé parce
qu'il échoue plus tôt, sur G0 : dix fichiers manquent au CSV d'inventaire, dont
neuf antérieurs à ce plan.

## Ce qui reste ouvert

- **G0 de l'audit est rouge** et le masque : dix fichiers absents du CSV
  d'inventaire (`agent/audit/inventaire.csv`), dont `objectif.py`,
  `excerpt_search.py`, `source_existence.py`, `token_meter.py`. Tant que G0
  échoue, les invariants ne sont jamais vérifiés. Régénérer l'inventaire.
- **`agent_providers._classify` et `agent_repli.classer` font le même travail**
  à deux endroits, le premier pour le test de clé, le second pour le repli. La
  PR 2 l'avait noté ; la PR 5 n'a pas fusionné les deux pour ne pas mêler un
  refactor à une fonctionnalité.
- **`Repos` vit en mémoire de processus.** Un passage en multi-instance le
  casserait en silence : chaque instance apprendrait la panne de son côté.
