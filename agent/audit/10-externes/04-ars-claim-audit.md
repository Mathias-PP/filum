# Audit 04. ARS → Philum : ancrage des citations, jugement de soutien, mesure d'erreur

> [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) (ARS), v3.21.2 selon le badge de son `README.md`. Suite de skills Claude Code pour la recherche académique, 440 fichiers Python et 983 markdown. Auteur : Cheng-I Wu.

> **Avertissement de licence, à lire avant toute reprise.** ARS est sous **CC BY-NC 4.0** (`LICENSE:1-4`, `package.json:9`), licence non commerciale et non conçue pour du logiciel. Aucune ligne de ce dépôt ne peut être recopiée dans Philum. Ce qui suit ne transfère que des **idées et des dispositions d'architecture**, jamais du code.

> **Vérifié le 2026-09-10** par lecture des fichiers cités, des deux côtés. Les affirmations sur Philum ont été recontrôlées à la main après le rapport des agents explorateurs, comme l'exige la correction de l'audit 10 du 2026-08-30.

> **Suites.** Cette fiche couvre l'ancrage, le jugement de soutien et la mesure d'erreur. Une seconde lecture d'ARS, le même jour, en a ramené quatre mécanismes de plus (vérification croisée entre modèles, isolement de la vérité terrain, posture « non mesuré » déclarée, vocabulaire de verdict fermé) ainsi que ses skills de contexte. Ils sont documentés en [`06-modules-de-contexte-agent.md`](./06-modules-de-contexte-agent.md), §5 et §6, et ne sont pas repris ici.

---

## 1. Pourquoi ce dépôt et pas un autre

ARS travaille sur le même problème que Philum, dans un autre monde. Philum demande à un créateur de contenu grand public de déclarer ses sources et d'en tirer des extraits verbatim, puis va lire la page pour vérifier que l'extrait s'y trouve. ARS accompagne un chercheur qui rédige un article, et vérifie que ses citations existent, qu'elles pointent vers un endroit précis, et depuis la v3.8 que la source dit bien ce que l'auteur lui fait dire.

C'est ce dernier point qui n'a aucun équivalent chez Philum, et c'est le seul écart de fond que cet audit ramène. Sur l'ancrage lui-même, la comparaison tourne à l'avantage de Philum, ce qui vaut d'être écrit noir sur blanc plutôt que déduit.

---

## 2. Ce qu'ARS fait, et où c'est écrit

### 2.1 La citation à trois couches

Forme d'émission, `docs/design/2026-05-12-ars-v3.7.3-claim-faithfulness-and-contaminated-source-spec.md:84` :

```
<texte visible> <!--ref:slug--><!--anchor:<kind>:<value>-->
```

Couche 1, la prose. Couche 2, le slug bibliographique (v3.7.1). Couche 3, l'ancre. Cinq `kind` tabulés lignes 89 à 95 : `quote` (verbatim URL-encodé, 25 mots au plus), `page`, `section`, `paragraph`, `none`. La spec qualifie elle-même `paragraph` de plus fragile des ancres structurelles (ligne 94), et `none` est interdit en production.

Le contrôle est un **lint de forme sur du markdown**, `scripts/check_v3_7_3_three_layer_citation.py` : regex d'ancre ligne 42, plafond de 25 mots ligne 47, refus d'une valeur vide ligne 194, refus du `--` brut dans une valeur (il fermerait le commentaire HTML) ligne 217, ancres orphelines lignes 269 à 283. Le fichier écrit lui-même son périmètre, lignes 26 à 28 : il ne vérifie pas que la valeur de l'ancre est fidèle à la source.

Quand la page a bougé, ARS ne dégrade pas : correspondance de sous-chaîne exacte, et en cas d'échec l'extrait entier part au juge avec un tag `[anchor_quote_unlocated]`, sans que le manque de localisation suffise à déclarer la citation non soutenue (`academic-pipeline/agents/claim_ref_alignment_audit_agent.md:164-171`).

### 2.2 Le jugement de soutien

Le verdict est rendu par un modèle, en un appel par citation, sur un prompt canonique délimité par `JUDGE-PROMPT-CANONICAL-START/END` (`claim_ref_alignment_audit_agent.md:183-226`). Décomposition en sous-affirmations imposée avant le verdict (lignes 193 à 198), verdict dans une énumération fermée : `SUPPORTED`, `UNSUPPORTED`, `AMBIGUOUS`, `PARTIAL`, `VIOLATED`.

Tout le reste est déterministe, et c'est là que se trouve la leçon. `scripts/claim_audit_pipeline.py:273-353` valide la sortie du juge : dictionnaire mal formé, clés manquantes, verdict hors énumération, et ligne 328 le rejet d'un identifiant de contrainte **hallucinée**, absent du jeu actif. Toute panne devient une classe de faute nommée (`judge_timeout`, `judge_parse_error`, `judge_api_error`, lignes 356 à 399). Un `PARTIAL` mal formé n'est jamais rabattu sur `UNSUPPORTED` : il devient une erreur d'analyse.

La sévérité, elle, n'appartient pas au modèle : `scripts/claim_audit_finalizer.py:59-78` déclare les noms d'annotation, toutes sévérités confondues, et cinq d'entre eux seulement sortent avec `gate_refuse: True`, aux lignes 131, 138, 212, 218 et 252. `ars_mark_read_clears` (lignes 428 à 455) refuse ensuite qu'on les acquitte à la main.

Détail élégant : la version du prompt est un SHA-256 qui sert de clé de cache (`scripts/_claim_audit_constants.py:146`). Éditer le prompt invalide le cache mécaniquement, sans discipline humaine.

### 2.3 La mesure d'erreur

Jeu doré : `scripts/fixtures/claim_audit_calibration/gold_set.json`, tableau JSON plat de 25 tuples (17 d'alignement, 8 de contrainte). Chaque tuple porte `claim_text`, `ref_text_excerpt`, `anchor{kind,value}`, `expected_judgment`. Le `CHANGELOG.md:934` annonce encore 20 : trace historique, le protocole `academic-pipeline/references/claim_audit_calibration_protocol.md:22` dit 25.

Runner `scripts/claim_audit_calibration.py` : seuils `FNR < 0.15` et `FPR < 0.10` lignes 44 et 45, exigence d'au moins trois tuples `NOT_VIOLATED` pour que le FPR soit mesurable (ligne 142), agrégats et mesure un-contre-tous par classe lignes 452 à 476, plus un sous-indicateur `partial_support.miss_rate` qui attrape un juge ayant cessé de décomposer.

**Piège de lecture, et ARS le dit lui-même** : en intégration continue le juge est un bouchon (`scripts/test_claim_audit_calibration.py:148`, « only proves tooling correctness on a perfect-mirror stub »). Le seuil garde l'outillage, pas la qualité du modèle.

Le harnais général est ailleurs : `evals/README.md:22-32`, un `manifest.yaml` par tâche, un fichier JSON par cas, et une porte `scripts/_eval_threshold_gate.py:26-58` qui contrôle **les deux axes**, agrégat et par classe, parce qu'une régression sur une seule classe passait auparavant.

### 2.4 La frontière déterministe / modèle, poussée jusqu'au bout

Le mode révision par patch est le meilleur exemple du dépôt. `scripts/ars_anchorize_draft.py` possède deux choses que le modèle ne touche jamais : l'attribution des identifiants de bloc (`<!--block:BNNNN-->`, `max(existant) + 1`, jamais renuméroté, lignes 64 à 82) et le calcul des hachages. Le contrat `shared/contracts/patch/block_manifest.schema.json:5` en donne le motif sans détour : ce manifeste est la seule source de hachage légitime, parce qu'un modèle à qui l'on demande un SHA-256 en invente un.

Le modèle n'émet plus qu'un document de patch, chaque opération recopiant son `old_hash` depuis le manifeste. `scripts/ars_apply_revision_patch.py` valide tout avant de toucher au disque (hachage de base contre les octets réels, existence des blocs, `old_hash` courant, unicité de la cible), puis découpe par plage d'octets et recopie verbatim ce qui n'était pas nommé. Un seul `old_hash` périmé rejette **tout** le patch (`scripts/test_ars_apply_revision_patch.py:500`).

Même doctrine dans la garde d'écriture `scripts/ars_write_scope_guard.py` : Bash refusé en bloc pour un agent de bucket A, avec la justification qu'aucune liste noire de commandes shell n'est décidable depuis une chaîne (lignes 9 à 25) ; `realpath` et jamais `abspath`, sous peine d'aveuglement aux liens symboliques (lignes 122 à 129) ; un outil d'écriture sans `file_path` est **refusé**, pas ignoré, pour interdire le fail-open silencieux (lignes 352 à 362) ; et `render_hook_output` n'émet jamais `allow`, parce qu'une garde qui n'ajoute que des refus ne doit pas court-circuiter les autres permissions.

### 2.5 Sources contaminées et chaîne de confiance

La liste des signaux est fermée, et plus étroite que le mot ne le laisse croire : `preprint_post_llm_inflection`, `semantic_scholar_unmatched`, `openalex_unmatched`, `crossref_unmatched`, `arxiv_unmatched`, `retraction_status`, `tortured_phrase_match` (`shared/contracts/passport/bibliographic_integrity_signal.schema.json`). **Ni éditeur prédateur, ni citation circulaire, ni détection de contenu généré par IA.**

Deux disciplines valent d'être retenues :

- **Une API dégradée n'est jamais lue comme un feu vert.** `scripts/contamination_signals.py` rend `None` et l'omission est elle-même enregistrée en `api_degraded` (lignes 202 et 548 à 590).
- **Trois classes épistémiques** dans `shared/bibliographic_integrity_signals.md:18-40` : `deterministic_fact`, `heuristic_advisory`, `process_attestation`, avec `check_status` et `finding` **indépendants**, et obligation d'afficher « non résolu » pour tout `not_checked`, `unknown` ou `degraded`.

Sur la rétractation (`docs/design/2026-08-08-651-retraction-status-spec.md`), ARS croise OpenAlex (`is_retracted`) et Crossref (`updated-by` / `update-to`), exige un DOI et interdit l'appariement par titre (lignes 46 à 48), réduit un désaccord entre les deux résolveurs à `disputed` plutôt qu'à un verdict, met en cache 30 jours (lignes 74 à 81), et ne bloque que sur opt-in explicite (lignes 86 à 99).

Sur la divulgation IA, la décision est de **ne rien mettre dans les données** (`docs/design/2026-05-14-ai-disclosure-schema-decision.md:70`), au motif que les quatre référentiels visés n'ont aucun champ commun. Faiblesse assumée ligne 74 : l'audit dépend alors du moteur de rendu.

---

## 3. État existant Philum, vérifié dans le code le 2026-09-10

| Capacité | Philum | Preuve |
|---|---|---|
| Sélecteurs d'ancrage persistés | oui, trois champs | `models/source_excerpt.py:56-58` (`anchor_prefix`, `anchor_suffix`, `anchor_offset`), nullables et documentés comme tels |
| Repêchage d'un passage dans une page qui a bougé | oui, deux étages | `services/excerpt_anchor.py` : citation exacte départagée par le voisinage (lignes 115 à 131), puis approche `SequenceMatcher` (ligne 151), `SEUIL = 0.75` ligne 42 |
| Aveu d'échec explicite | oui | `ancrer()` rend `None` plutôt qu'une position inventée (`excerpt_anchor.py:171-184`) |
| Verdict de présence | oui, quatre états | `verified_status` (`found` / `moved` / `missing` / `unreadable`), plus `verified_text_source` qui distingue la page publique d'un texte fourni (`models/source_excerpt.py:63-65`) |
| Refus d'une paraphrase à l'insertion | oui | `services/excerpt_insertion.py:49` (`SEUIL_TYPOGRAPHIQUE = 0.95`), appliqué ligne 131 |
| Origine IA d'un contenu | oui, en données | `suggested_by_ai`, `annotated_by_ai` (`models/source_excerpt.py`) |
| Rétractation | oui, **Crossref seul** | `models/source.py:154-156`, `extractors/retraction.py:112` (`api.crossref.org`) ; aucun appel OpenAlex dans le fichier |
| Péremption d'une vérification | **non** | `retraction_checked_at` et `oa_checked_at` existent (`models/source.py:156`, `:166`), aucune constante de péremption ni re-vérification trouvée |
| Jugement « la source soutient-elle ce qu'on lui fait dire » | **non** | Philum vérifie qu'un extrait est dans la page, jamais que l'annotation est fidèle à l'extrait |
| Jeu doré, FNR / FPR mesurés | **non** | aucun `gold_set` ni `FNR` dans `app/` ni `tests/` |
| Précondition de version sur une écriture d'agent | **non** | aucun `if_match`, `expected_hash` ou `etag` dans `mcp_server/tools_write.py` |
| Approbation humaine des actions sensibles | oui | `agent_tools/philum.py`, `SENSITIVE_TOOLS`, et `est_sensible` rattrape `update_card(visibility="public")` |

---

## 4. Ce qui se transfère

| Apport | Ce qu'il ferme | Coût |
|---|---|---|
| **A. Jeu doré d'ancrage, avec seuils mesurés** | `SEUIL = 0.75` et `SEUIL_TYPOGRAPHIQUE = 0.95` sont posés sans mesure publiée. Une trentaine de cas `{texte_page, extrait, attendu}` en JSON, un runner qui rend le taux de faux `found` et de faux `missing`, une porte sur les deux axes comme `_eval_threshold_gate.py:36-42`. Le juge étant déterministe, aucun modèle n'est requis et aucun bouchon n'est à inventer. | ~1 jour |
| **B. Croiser la rétractation sur deux résolveurs, et dire le désaccord** | Philum n'interroge que Crossref. OpenAlex est gratuit. Un désaccord se réduit en `disputed`, jamais en verdict. Philum sait déjà déclarer un état non vérifiable. | ~1 à 2 jours |
| **C. Péremption datée d'une vérification** | `retraction_checked_at` existe et ne périme jamais. Un verdict de plus de N jours doit s'afficher comme périmé et ne peut alimenter aucun badge. Attention à la mémoire « jamais de quotas arbitraires » : la fenêtre se justifie par le rythme des avis de rétractation, elle ne se décrète pas. | ~0,5 jour au modèle, plus l'ordonnancement |
| **D. Précondition de version sur les écritures d'agent** | `update_card` et `update_excerpt` sont des réécritures où le modèle peut altérer ce qu'il n'avait pas à toucher. Le serveur rend un jeton d'état, l'agent le recopie, le backend rejette **tout** l'appel si l'état a bougé. Contrôle de concurrence optimiste classique, mais motivé ici par la distorsion du modèle, pas par la course entre utilisateurs. | ~1 à 2 jours |

Et deux règles à coût quasi nul, à écrire une fois pour toutes :

- **Ne jamais demander à un modèle une valeur qu'une machine peut calculer**, lui fournir la valeur, exiger la recopie, échouer bruyamment sur une copie fausse (`block_manifest.schema.json:5`).
- **Fail-closed sur l'ambiguïté.** Un argument de forme inattendue se refuse, il ne s'ignore pas (`ars_write_scope_guard.py:352-362`). Philum tient déjà cette ligne avec `est_sensible` ; elle mérite d'être un contrat de revue plutôt qu'un réflexe.

---

## 5. Écarté, avec le motif

| Idée | Motif du rejet |
|---|---|
| Les cinq classes HIGH-WARN et la porte terminale | Elles supposent un artefact final à refuser. Philum publie une fiche, il n'y a rien à bloquer, et bloquer une publication contredirait « avertir, ne pas bloquer » |
| Heuristique « préprint postérieur à 2024 » | Stigmatise une catégorie entière sans preuve individuelle, et Philum n'est pas académique |
| Phrases torturées | Dépend d'une liste qu'ARS lui-même refuse de redistribuer, et ne dit rien d'une vidéo ou d'un billet |
| Les quatre référentiels de divulgation IA (PRISMA-trAIce, ICMJE, Nature, IEEE) | Politique de revues académiques. La part utile, distinguer ce qui vient d'un modèle de ce qui vient de la source, est déjà en base |
| Lint markdown des marqueurs `<!--anchor:-->` | Philum stocke ses sélecteurs en base, pas dans de la prose |
| Ancre `paragraph` | La spec ARS la dit fragile elle-même (ligne 94), et `excerpt_anchor.py` a déjà tranché contre l'offset seul |
| Le mode révision par patch dans sa forme complète | Ancrage markdown, sidecar sur disque, CLI en deux phases : du plugin local. Seul le principe se transpose, en apport D |
| Garde `PreToolUse` en hook shell | Philum est un service FastAPI multi-utilisateurs, l'équivalent existe déjà en `est_sensible` |
| Contamination par index bibliographique non apparié | `extractors/semantic_scholar.py` existe côté Philum mais n'a pas été lu dans cet audit. À trancher séparément, hors de cette fiche |

---

## 6. Ce que cet audit ne prétend pas

- Le front Philum n'a pas été lu.
- `extractors/semantic_scholar.py`, `open_access.py` et les oracles (`europepmc`, `pmc`, `wikipedia`, `youtube`) n'ont pas été lus : aucune affirmation ici ne porte sur eux.
- Aucun chiffre externe au dépôt local n'est cité (étoiles, téléchargements). La version v3.21.2 vient du badge du `README.md` de la copie lue, pas de l'API GitHub.
- Les seuils FNR / FPR d'ARS gardent son outillage, pas la qualité de son juge : le dépôt l'écrit, et cet audit ne prétend pas davantage.

---

_Rédigé le 2026-09-10. Copie d'ARS lue en local, licence CC BY-NC 4.0 : idées reprises, code jamais._
