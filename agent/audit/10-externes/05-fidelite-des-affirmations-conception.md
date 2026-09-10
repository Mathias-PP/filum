# Conception 05. Fidélité des affirmations : ce que Philum doit construire, et pourquoi il peut le faire mieux qu'ARS

> Suite de [`04-ars-claim-audit.md`](./04-ars-claim-audit.md). Cette note ne rapporte plus ce qu'ARS fait, elle décide ce que Philum fait. ARS est sous CC BY-NC 4.0 : **aucune ligne de son code, ni son prompt, ne peut être reprise**. Ce qui suit décrit des mécanismes en français, à réécrire de zéro.

> Lecture faite le 2026-09-10 des deux côtés : ARS `scripts/claim_audit_pipeline.py` (1609 lignes), `claim_audit_finalizer.py`, `_claim_audit_constants.py`, `claim_audit_calibration.py`, `academic-pipeline/agents/claim_ref_alignment_audit_agent.md` ; Philum `models/source_excerpt.py`, `models/biblio_card.py`, `services/llm.py`, `services/excerpt_anchor.py`, `services/excerpt_insertion.py`, `mcp_server/tools_write.py`.

> **Décisions arrêtées après cette note**, en [`06-modules-de-contexte-agent.md`](./06-modules-de-contexte-agent.md) : le jeu doré est reporté, le juge part en production en état « non mesuré » déclaré, son verdict reste privé au créateur, et le vocabulaire de verdict esquissé au §5 est remplacé par celui du §6.4 de la fiche 06 (pertinence, puis vérifiabilité, puis position ; aucun score numérique).

---

## 1. La thèse

ARS et Philum ne sont pas au même endroit du problème, et c'est ce qui rend la reprise intéressante plutôt qu'imitative.

ARS audite **au moment de la rédaction, contre le web vivant**. Quand son juge est appelé, on ne sait pas encore si la source est lisible. D'où la moitié de sa machinerie : trois méthodes d'échec de récupération routées sans juge (`claim_audit_pipeline.py:1245-1256`), quatre des classes de sa matrice de sévérité consacrées à distinguer un paywall d'une référence fabriquée et d'une panne d'outil (`claim_audit_finalizer.py:110-161`), une règle de prudence dédiée pour interdire au juge de conclure « non soutenu » quand il n'a simplement pas retrouvé le passage (`claim_ref_alignment_audit_agent.md:171`).

Philum a **déjà tranché ce problème, et séparément**. Le verbatim est stocké en base, il a été confronté à la page à l'insertion (`excerpt_insertion.py:49`, `SEUIL_TYPOGRAPHIQUE = 0.95`, la paraphrase est refusée), il porte trois sélecteurs d'ancrage (`source_excerpt.py:56-58`) et un verdict de présence à quatre états posé par du code déterministe (`found`, `moved`, `missing`, `unreadable`, `tools_write.py:1035-1038`).

Conséquence directe, et c'est la thèse de cette note : **Philum peut poser au modèle la seule question qu'un modèle sait traiter, et rien d'autre.** Pas « va lire cette source et dis-moi si elle dit ça », mais « voici un passage dont la présence est établie, voici ce qu'on lui fait dire, est-ce fidèle ». La question devient close, l'entrée est locale, l'appel est déterministe et donc cachable, et toute la casuistique de récupération d'ARS n'a pas à exister.

---

## 2. Trois questions, et où Philum en est vraiment

| Question | ARS | Philum aujourd'hui |
|---|---|---|
| **Q1.** La source existe-t-elle et vaut-elle quelque chose ? | quatre index bibliographiques, rétractation croisée, signaux consultatifs | oui, partiellement : `extractors/retraction.py` (Crossref seul), `open_access.py`, oracles PMC / EuropePMC / Wikipedia / YouTube |
| **Q2.** Le passage cité est-il réellement dans la source ? | correspondance de sous-chaîne exacte, sinon on passe l'extrait entier au juge avec un tag | **oui, et mieux** : refus de la paraphrase à l'insertion, repêchage à deux étages (`excerpt_anchor.py:115-166`), aveu d'échec explicite (`ancrer()` rend `None`), quatre verdicts persistés |
| **Q3.** Le passage soutient-il ce qu'on lui fait dire ? | juge LLM, cinq verdicts, décomposition imposée, matrice de sévérité | **rien** |

Sur Q3, Philum a deux niveaux qu'ARS ne distingue pas, parce qu'ARS n'a pas leur équivalent en base :

**Q3a, la mise en situation contre le verbatim.** Un extrait porte un `title` et un `context` (500 caractères), champs de prose libre séparés du verbatim par une décision explicite du modèle de données : « la citation doit rester exactement ce que la source dit, la mise en situation exactement ce qu'elle n'a pas dit » (`source_excerpt.py:41-46`). Rien ne vérifie que cette mise en situation est fidèle au passage qu'elle situe. Or `annotate_excerpt` (`tools_write.py:1536`) la fait écrire par un modèle, et `annotated_by_ai` existe précisément parce que « la prose générée côtoie ici du verbatim ». C'est le point où une surenchère se glisse : un extrait qui dit « suggère » annoté « démontre ».

**Q3b, le texte de la fiche contre ses extraits.** `content_text` (`biblio_card.py:122`) est rendu tel quel sur la fiche publique. Les sources et leurs extraits sont listés à côté. **Aucun lien entre une phrase du texte et l'extrait censé l'étayer.** C'est l'équivalent des `uncited_assertions` d'ARS, et c'est le plus gros manque : une fiche peut affirmer proprement des choses que ses sources vérifiées ne disent pas, et tout l'appareil de vérification en sortirait vert.

Q3a est un chantier borné et livrable seul. Q3b demande d'abord une décision de produit qui n'est pas prise : faut-il pouvoir rattacher une affirmation du texte à un extrait ? Cette note traite Q3a en détail et pose Q3b comme préalable de conception, pas comme tâche.

---

## 3. Ce qu'on prend chez ARS, et comment on le fait autrement

### 3.1 La sortie du juge : leur cicatrice est notre déclaration

ARS demande au juge un format clé/valeur en texte (`claim_ref_alignment_audit_agent.md:216-224`), puis le rattrape à la main. Il en résulte : un validateur de forme de 80 lignes, une garde explicite contre un verdict non-string qui levait `TypeError: unhashable type` (`claim_audit_pipeline.py:311`), trois fonctions de validation pour un même invariant dont les frontières sont documentées par des commentaires de post-mortem (`_claim_audit_constants.py:46-113`), et une règle de coercition qui rabat tout indice de défaut inconnu sur la classe la plus fréquente (`claim_audit_pipeline.py:589-598`).

Philum n'a rien de tout cela à écrire. `services/llm.py:91` (`_appel_json`) demande déjà `response_format: json_schema` construit depuis un modèle Pydantic, avec `temperature: 0`, repli sur `json_object` quand un fournisseur refuse le schéma, et une règle écrite : « rien n'est accepté sur la foi du mode demandé », le parsing valide dans les deux cas. Un verdict typé `Enum` et une liste de sous-affirmations typée sont **une déclaration de dix lignes**, pas une couche de défense.

Décision : le verdict est un modèle Pydantic, les énumérations sont des `Enum` Python comme le sont déjà `SourceCategory` ou `SourceStance`. Un indice hors ensemble n'est pas coercé, il est **impossible**. La leçon d'ARS survit sous une autre forme : ne jamais accepter une valeur du modèle sans qu'un type la borne.

### 3.2 Le motif de blocage doit préexister à l'appel

C'est le meilleur mécanisme d'ARS, `claim_audit_pipeline.py:321-332` : sur un verdict de violation, le code exige un identifiant de contrainte et vérifie qu'il appartient à l'ensemble réellement déclaré par l'auteur. Un identifiant inventé ne devient pas un blocage, il devient une panne de juge. Autrement dit **le modèle ne peut pas fabriquer le motif de sa propre sanction**.

Chez Philum, ce principe ne se code pas en `if` : il devient une contrainte d'intégrité. Tout verdict pointe l'extrait par sa clé étrangère ; un extrait qui n'existe pas ne s'insère pas. Le principe est le même, la mécanique disparaît dans le schéma de base. C'est très exactement le patron déjà tenu par `est_sensible` (`agent_tools/philum.py`), qui rattrape `update_card(visibility="public")` parce que sinon l'approbation se contournerait en changeant d'outil.

### 3.3 Une panne d'outil ne produit jamais un verdict favorable

La règle la plus chèrement payée d'ARS. Elle apparaît quatre fois dans leur code, et l'une de ces occurrences est une cicatrice datée : avant la v3.8.2, une panne du juge était silencieusement substituée en « pas de violation », ce qui éteignait les contrôles bloquants (`claim_audit_pipeline.py:1438`). Une autre exige qu'une récupération réussie porte un extrait non vide, faute de quoi le juge pourrait déclarer « soutenu » sans texte source (`claim_audit_pipeline.py:470-476`).

Philum tient déjà la convention correspondante dans son modèle de données, et il faut la prolonger telle quelle : `verified_status = None` veut dire « jamais relu », « un état à afficher tel quel, pas à combler par un défaut qui ferait passer l'extrait pour vérifié » (`source_excerpt.py:59-62`). `_appel_json` rend `None` et ne lève jamais : un `None` doit donner **absence de verdict**, jamais « fidèle ».

### 3.4 La décomposition en sous-affirmations, et la métrique de ce qu'on perd

ARS impose de casser l'affirmation en sous-affirmations atomiques et de juger chacune avant de choisir le verdict, avec le motif écrit : ne pas réduire une affirmation composée à un contrôle binaire (`claim_ref_alignment_audit_agent.md:193-197`). C'est ce qui attrape le cas réel, « le score a monté **et** l'effet tient sur toutes les tranches d'âge », dont la moitié seulement est dans l'extrait.

Le raffinement à reprendre absolument est ailleurs, et c'est la plus belle idée du dépôt. ARS normalise le verdict partiel en « non soutenu », ce qui rend invisible à la métrique agrégée un juge qui aurait cessé de décomposer : il répondrait « non soutenu » nu et resterait vert. Ils ont donc ajouté une sous-métrique qui ne compte le cas comme réussi que si le juge rend le bon verdict **et** une décomposition bien formée (`claim_audit_calibration.py:359-392`).

La règle générale, à écrire une fois pour toutes dans Philum : **dès qu'on normalise deux états en un seul label, il faut une métrique sur la propriété perdue.**

### 3.5 L'ambigu est un verdict, pas un échec

ARS interdit de forcer un jugement ambigu vers « non soutenu », avec un motif métrique : cela gonfle le taux de faux positifs (`claim_ref_alignment_audit_agent.md:26`). Chez Philum le motif est plus fort que métrique. Un faux « non soutenu » n'est pas une ligne de rapport, c'est **une accusation portée contre un créateur sur une fiche publique**. Le verdict d'indécision doit être de première classe, affichable, et ne doit jamais dégrader l'affichage d'une fiche.

Corollaire, qui est déjà la position de Philum et qu'il faut réaffirmer : **on avertit, on ne bloque pas.** La porte terminale d'ARS, ses cinq classes non acquittables, son refus d'accuser réception d'un avertissement grave (`claim_audit_finalizer.py:428-456`), tout cela suppose un artefact à refuser. Philum publie une fiche. Il n'y a rien à bloquer, et bloquer une publication sur un jugement de modèle serait exactement le contraire du lien de confiance qu'il installe.

### 3.6 Ce qu'il ne faut surtout pas reproduire

| Défaut d'ARS | Preuve | Décision Philum |
|---|---|---|
| La classe de faute est encodée en préfixe dans la prose de justification puis réextraite par expression régulière en aval, avec repli silencieux | `claim_audit_finalizer.py:107`, `:147-152` | tout signal est un **champ**, jamais un préfixe de texte libre. Corollaire : le budget de 2000 caractères et sa machinerie de troncature n'ont pas lieu d'être |
| La sévérité est calculée deux fois : émise en triplets, puis re-discriminée, avec des exceptions sur combinaison imprévue | `claim_audit_finalizer.py:158-161`, `:220-224` | émettre directement la sévérité et son motif. Dans un service web, une exception sur une ligne malformée fait tomber la requête entière |
| Une constante de couplage déclarée en double, dans deux fichiers, avec un commentaire demandant de les synchroniser | `claim_audit_pipeline.py:83` et `claim_audit_finalizer.py:55` | un seul point de déclaration |
| Un identifiant sentinelle faux, conçu pour satisfaire un motif de schéma | `_claim_audit_constants.py:19` | un champ nullable et un booléen explicite |
| Des compteurs locaux au run (`UA-001`) qui ne sont pas uniques en base multi-utilisateurs | `claim_audit_pipeline.py:1523` | des UUID, comme partout ailleurs dans Philum |
| Un verdict unique où l'axe contrainte écrase l'axe alignement, ce qui perd le second signal alors qu'il a été calculé | priorité écrite `claim_ref_alignment_audit_agent.md:179` | deux champs orthogonaux plutôt qu'un verdict à priorité |
| Un taux rendu à `0.0` sur dénominateur nul alors que le docstring annonce une sémantique `nan` : l'écart est dans la promesse écrite, pas dans le résultat, puisque le dénominateur est reporté à côté et lève l'ambiguïté | `claim_audit_calibration.py:288-301` | garder la règle d'ARS, aucune mesure sans son dénominateur affiché à côté, et ne rien documenter d'autre que ce que le code rend |

---

## 4. Les cinq avantages structurels de Philum, à ne pas gaspiller

1. **La présence est tranchée avant, par du code.** La confusion la plus fréquente de ce genre de système, « je n'ai pas retrouvé le passage donc la source ne le dit pas », est structurellement impossible ici. ARS a besoin de deux règles de prompt pour l'interdire ; Philum n'a pas besoin de la règle, il a besoin de ne jamais fusionner les deux étapes.
2. **La sortie contrainte est native.** `_appel_json` plus Pydantic remplacent trois validateurs et une table de coercition.
3. **L'objet audité a une identité stable en base.** Ni sentinelle, ni compteur local au run, ni jointure sur une clé de citation.
4. **On sait déjà où est le risque.** `suggested_by_ai` et `annotated_by_ai` disent quelles annotations viennent d'un modèle. L'audit se cible là d'abord, ce qui divise le coût par un facteur qu'aucune stratégie d'échantillonnage n'atteindrait.
5. **La convention du « jamais relu » est déjà écrite et tenue.** Le verdict de fidélité s'y range sans inventer de vocabulaire.

---

## 5. Esquisse pour Q3a, la fidélité de la mise en situation

Forme, pas code. À écrire de zéro.

**L'unité auditée** est le couple (verbatim, mise en situation), c'est-à-dire un extrait dont `context` ou `title` est renseigné. Elle est locale : rien à récupérer sur le réseau au moment du jugement.

**La question posée** est close : la mise en situation attribue-t-elle au passage plus, moins, ou autre chose que ce qu'il dit. Quatre issues suffisent, et il faut résister à en ajouter : fidèle, surenchère (le passage suggère, l'annotation affirme), hors sujet (l'annotation parle d'autre chose), indécis. La décomposition en sous-affirmations tourne avant, pour les mises en situation composées, et le détail est conservé : c'est lui, et non le verdict, qui rend le résultat lisible et contestable par le créateur.

**Ce qui est persisté** : le verdict, sa justification en une phrase, la décomposition, le modèle qui a jugé, la date, et l'empreinte du prompt. Sur l'extrait, comme `verified_status`, avec la même convention de nullité.

**Le cache** est indexé par un condensat de ce qui entre dans la décision : verbatim, mise en situation, identité du modèle, empreinte du prompt. L'idée à reprendre telle quelle est celle-ci : **l'empreinte du prompt fait partie de la clé**, ce qui rend l'invalidation mécanique et ne repose sur aucune discipline humaine (`_claim_audit_constants.py:146`), avec le repli fermé quand l'empreinte est inconnue.

**L'affichage** dit ce qu'il sait et rien de plus. Une surenchère se montre au créateur avec le passage et son annotation côte à côte : c'est un service rendu, pas une sanction. Jamais de badge qui dégrade la fiche sur un jugement de modèle.

**La mesure** vient avant le déploiement, pas après. Un jeu de cas étiquetés à la main, la forme d'ARS étant bonne à reprendre (un fichier par cas, un manifeste qui déclare la distribution attendue et les seuils, une porte qui contrôle l'agrégat **et** chaque classe, parce qu'une régression sur une seule classe passait chez eux avant correction, `_eval_threshold_gate.py:36-42`). Avec trois corrections de leurs faiblesses, que leur propre protocole ne relève pas :

- **Assez de cas pour que le seuil veuille dire quelque chose.** ARS mesure un taux de faux positifs à seuil 0,10 sur trois observations : un seul faux positif donne 0,33. Ce n'est pas un seuil, c'est du bruit. Attention ici à la mémoire « jamais de quotas arbitraires » : ce n'est pas un plafond décrété, c'est la puissance statistique minimale pour que la mesure existe, et elle se justifie par le seuil visé.
- **Un vrai modèle avant de dire calibré.** Chez ARS, l'intégration continue fait juger un bouchon parfait, et le dépôt l'écrit lui-même : cela prouve la tuyauterie, pas la calibration (`test_claim_audit_calibration.py:148`).
- **La variance test-retest.** ARS écarte l'ensembling au motif que l'appel est court et la forme contrainte. L'argument ne tient pas : la brièveté ne dit rien de la stabilité, et c'est précisément la frontière la plus subjective qui doit être la plus instable. Deux passes sur le même jeu coûtent presque rien et disent si le verdict est reproductible.

Une quatrième mesure, qu'ARS n'a pas et qui serait chez eux le meilleur indicateur précoce de dérive : **compter les sorties refusées par le schéma**. Chez Philum, `_appel_json` rend `None` sur schéma refusé ou parsing invalide ; ce compteur est gratuit et il monte avant que la qualité ne tombe.

**Ce qui rend ce chantier tenable** : Q3a ne touche pas la publication, ne bloque rien, ne demande aucune migration de fond au delà de quelques colonnes sur l'extrait, et se mesure avant d'être allumé. Ordre de grandeur, jeu de cas étiquetés compris : deux à trois jours, dont la moitié en curation.

---

## 6. Q3b, à décider avant d'être planifié

Rattacher une phrase de `content_text` à l'extrait qui l'étaye est le vrai sujet, et c'est une décision de produit avant d'être une tâche. Trois questions ouvertes, dans cet ordre :

1. Le créateur veut-il poser ce lien à la main, ou attend-il qu'il soit proposé ? Philum a déjà les deux briques : la recherche d'extraits par le sens est en production, et `suggest_excerpts` propose des candidats déjà vérifiés contre le texte.
2. Que fait-on d'une affirmation sans extrait ? ARS l'émet en avis non bloquant. Pour Philum la réponse par défaut doit être la même, et il faut résister à l'idée d'un score de couverture : la valeur n'est pas le nombre de sources, et un ratio d'étayage serait exactement le chiffre qu'on optimiserait au détriment du sens.
3. Est-ce visible du public, ou est-ce un outil d'écriture pour le créateur ? Tant que la réponse n'est pas tranchée, aucune ligne de code n'est justifiée.

---

## 7. Ce que cette note ne fait pas

- Elle ne planifie pas Q3b, faute des trois décisions ci-dessus.
- Elle ne traite pas Q1 : la rétractation croisée et la péremption d'une vérification restent les apports B et C de la fiche 04, indépendants de celle-ci.
- Elle ne propose aucun code, aucun prompt, aucune structure recopiée d'ARS. Elle décrit des mécanismes à réécrire.
- Elle n'a pas lu le front de Philum, ni `extractors/semantic_scholar.py`.

---

_Rédigé le 2026-09-10, après lecture ligne à ligne des quatre modules d'audit d'ARS et du modèle de données de Philum. ARS reste sous CC BY-NC 4.0 : idées reprises, code jamais._
