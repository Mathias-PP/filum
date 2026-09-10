# Audit 10. Dépôts externes → Philum

> Analyse de quatre dépôts open-source à la recherche de ce que Philum n'a pas encore. Après vérification ligne à ligne, huit apports subsistent : repli d'un fournisseur vers un autre, transparence du routage, assainissement Unicode, recherche duale en MCP, puis, venus d'ARS, un jeu doré qui mesure les seuils d'ancrage, la rétractation croisée sur deux résolveurs, la péremption d'une vérification et la précondition de version sur les écritures d'agent. Le reste existait déjà ou avait été refusé avec motif.
>
> Deux notes de conception prolongent cet audit sans venir d'un dépôt : la [fiche 05](./05-fidelite-a-la-source-conception.md) sur le juge de fidélité à la source, la [fiche 06](./06-modules-de-contexte-agent.md) sur la doctrine « le modèle choisit, il ne saisit pas » et les modules de contexte à poser dans le workspace du créateur.

---

## Dashboard

| Repo | Objectif | Fichier |
|---|---|---|
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | Repli de fournisseur, transparence du routage | [`01-omniroute-fallback.md`](./01-omniroute-fallback.md) |
| [open-notebook](https://github.com/lfnovo/open-notebook) | Recherche duale, citations structurées | [`02-open-notebook-knowledge.md`](./02-open-notebook-knowledge.md) |
| [book-to-skill](https://github.com/virgiliojr94/book-to-skill) | Assainissement Unicode avant le contexte du modèle | [`03-book-to-skill-rag.md`](./03-book-to-skill-rag.md) |
| [academic-research-skills](https://github.com/Imbad0202/academic-research-skills) (ARS) | Ancrage des citations, jugement de soutien, mesure d'erreur. **CC BY-NC 4.0 : idées seulement, jamais de code** | [`04-ars-claim-audit.md`](./04-ars-claim-audit.md) |
| (conception, pas un dépôt) | Ce que Philum construit sur la fidélité à la source, et pourquoi il peut faire mieux qu'ARS | [`05-fidelite-a-la-source-conception.md`](./05-fidelite-a-la-source-conception.md) |
| (conception, pas un dépôt) | Rendre l'invention structurellement impossible, et les modules de contexte à ajouter au workspace du créateur | [`06-modules-de-contexte-agent.md`](./06-modules-de-contexte-agent.md) |

---

## Synthèse des gains attendus

| Gain | Source | Impact | Retenu ? |
|---|---|---|---|
| Repli d'un provider vers un autre | OmniRoute | le mode gratuit cesse de dépendre du seul Z.ai | oui |
| Transparence du routage (provider dans le SSE et l'interface) | OmniRoute | l'utilisateur voit quel provider a répondu | oui |
| Sanitisation Unicode | book-to-skill | ferme l'injection par caractères invisibles dans une page tierce | oui |
| Recherche duale vecteur puis texte | open-notebook | le MCP cesse d'être moins capable que le REST | oui |
| Citations structurées `[source:uuid]` | open-notebook | réponses cliquables vers les sources | à décider |
| Chunking sémantique multilingue | book-to-skill | aucun gain | non : `chunker.py` le fait déjà, et le dépôt cité n'a pas de chunking |
| Extraction déterministe sans LLM | book-to-skill | aucun gain | non : `chunker.py` est déjà déterministe, sans réseau ni clé |
| Jeu doré qui mesure `SEUIL = 0.75` et `SEUIL_TYPOGRAPHIQUE = 0.95` | ARS | deux seuils d'ancrage cessent d'être des choix non mesurés | oui |
| Rétractation croisée Crossref plus OpenAlex, désaccord rendu en `disputed` | ARS | `extractors/retraction.py` n'interroge qu'un résolveur | oui |
| Péremption datée d'une vérification | ARS | `retraction_checked_at` existe et ne périme jamais | oui |
| Précondition de version sur `update_card` / `update_excerpt` | ARS | le modèle ne peut plus réécrire en silence ce qu'il n'avait pas à toucher | oui |
| Jugement LLM « la source soutient-elle l'affirmation » | ARS | seul écart de fond, mais chantier à part entière | à décider |
| Porte terminale bloquant la publication | ARS | aucun | non : Philum avertit, il ne bloque pas |
| Doctrine « le modèle choisit, il ne saisit pas » | conception (fiche 06) | ferme les trois portes par lesquelles une invention entre encore : métadonnées libres de `add_source`, repli de `annotate_excerpt` sur `source.title` faute d'entourage, recherche web indisponible | oui |
| Vérification croisée entre modèles, verdict positif non étayé déclassé | ARS (fiche 06 §6.1) | un vérificateur qui partage la distribution du générateur partage ses angles morts | oui |
| Isolement de la vérité terrain hors du contexte du modèle jugé | ARS (fiche 06 §6.2) | condition pour que la mesure du juge veuille dire quelque chose, le jour où elle se fera | oui, avec le jeu doré |
| Posture « non mesuré » déclarée plutôt que tue | ARS (fiche 06 §6.3) | le juge part en production sans mesure, mais le dit ; verdict privé au créateur, aucune page publique ne s'en sert | oui |
| Vocabulaire de verdict fermé, pertinence puis vérifiabilité puis position, sans score numérique | ARS (fiche 06 §6.4) | une preuve manquante cesse d'être confondue avec un sujet non abordé | oui |
| `shared/rien-de-memoire.md`, `shared/qualite-des-sources.md`, `shared/chercher-la-contradiction.md` | conception (fiche 06 §4) | trois modules de contexte, un fichier chacun dans le workspace du créateur ; exigence identique quel que soit le domaine | oui |
| `agents/questionneur.yaml` | ARS (fiche 06 §4.4) | un rôle qui questionne jusqu'à ce que le créateur ait formulé son angle, puis propose du contenu qui sert cet angle, en annonçant la bascule | oui |
| Re-vérification périodique des rétractations sur les sources déjà citées | ARS (fiche 06 §5.3) | confirme l'apport « péremption datée » depuis une seconde source du dépôt | oui |
| Échelle en cinq degrés original → verbatim, et seuil des vingt mots consécutifs | ARS (fiche 06 §5.1) | grille de lecture pour Q3b : du verbatim présenté comme la prose du créateur dans `content_text` | oui |
| Verdict « ce texte est généré par une IA » | ARS (fiche 06 §5.1) | aucun | non : ARS le refuse explicitement, et Philum a des marqueurs d'origine, pas des devinettes |
| Pyramide des niveaux de preuve médicale à sept étages | ARS (fiche 06 §4.2) | aucun | non : exigence d'un seul domaine appliquée à tous ; remplacée par trois questions valables partout |
| Module de veille bibliographique | ARS (fiche 06 §5.3) | aucun | non : Philum documente ce qui est cité, il n'organise pas la veille d'un chercheur |

---

## État existant Philum (vérifié dans le code le 2026-08-30)

| Capacité | Existe ? | Preuve |
|---|---|---|
| Mode gratuit (rotation de lanes, quota, cooldown) | oui, Z.ai seul | `agent_gratuit.py:39` (`COOLDOWN_MINUTES = 10`), `models/agent_lane.py:12-67` |
| BYOK, 9 providers | oui | `schemas/agent_provider.py:10-19` |
| Retry 5xx/429 sur le même provider | oui | `services/agent.py:401-463` |
| Fallback d'un provider vers un autre | **non** | aucun appel de repli hors du provider de la session |
| Embeddings gemini-embedding-001, 768d | oui | `services/embeddings.py:74-87` |
| Recherche sémantique des extraits | oui, REST seul | `api/v1/endpoints/excerpt_search.py` |
| Recherche plein texte MCP | oui, ILIKE | `mcp_server/tools_write.py:1380` (`search_my_excerpts`), ILIKE en `:1399` |
| Recherche sémantique exposée en MCP | **non** | `search_my_excerpts` ne fait que du ILIKE |
| Graph memory | oui, 3 tables | `models/graph_memory.py`, migration `053` |
| Découpe d'un texte en extraits candidats | **oui** | `services/chunker.py`, déterministe, coupe aux frontières de phrase et de paragraphe, rend `start`/`end` |
| Index vectoriel HNSW | non, **par décision** | migration `036_excerpt_embeddings.py` : parcours séquentiel exact, index remis au jour où le volume l'exige |
| Sanitisation Unicode avant injection LLM | **non** | NFKD/NFKC existent en recherche (`db/text_search.py`) et en dédoublonnage (`extractors/ref_dedup.py`), pas sur le chemin du contexte |
| File d'indexation avec états | non, **par décision** | `services/excerpt_indexing.py:1-11` : indexation idempotente, rejouable, précisément pour ne pas tenir de file |
| Citations `[source:uuid]` dans les réponses | non | aucune occurrence du motif dans le dépôt |

---

## Corrections apportées à la première rédaction

Cet audit affirmait avoir été « réalisé en lisant l'intégralité des 3 repos et du codebase Philum ». La relecture a montré que plusieurs faits venaient d'une reconstitution plausible plutôt que d'une lecture. Ils sont corrigés ci-dessus et dans chaque fiche. Les cinq qui changeaient les conclusions :

| Affirmation d'origine | Réalité vérifiée | Conséquence |
|---|---|---|
| « Chunking de sources : n'existe pas » | `chunker.py` existe, déterministe, sans réseau ni clé | la phase la plus lourde du plan (3 jours) tombe |
| « book-to-skill fait du chunking sémantique multilingue » | aucun fichier du dépôt ne contient « chunk » ni « segment » | le patron numéro 1 à copier n'existe pas |
| « Philum traite des articles web, pas des PDF » | GROBID (`extractors/grobid.py`) et `pypdf` en dépendance | la partie PDF de book-to-skill n'est pas écartable pour cette raison |
| « Philum estime déjà les tokens via tiktoken » | `token_meter.py:14-18` écarte tiktoken avec un motif écrit | l'argument utilisé pour écarter un patron est faux |
| « Index HNSW : absent » présenté comme un manque | migration `036` le refuse avec un motif mesuré | ce n'est pas une dette, c'est un choix |

Chiffres externes corrigés : OmniRoute a 58 430 étoiles, un scoring à **12** facteurs (pas 15) et un `freeModelCatalog.ts` de **275** lignes (pas 455) ; open-notebook a **37 932** étoiles (pas 27k) ; book-to-skill a bien 27 224 étoiles, le « 27k » attribué à open-notebook y était recopié.

---

## Ordre d'exécution révisé

1. **OmniRoute (01), phases A et B** : le seul item qui débloque une panne en cours. Le mode gratuit est à l'arrêt sur le solde Z.ai, et sans repli vers un autre fournisseur il le reste.
2. **book-to-skill (03), phase C seule** : la sanitisation Unicode est une garde de sécurité de trente lignes sur un chemin où du texte tiers entre dans le contexte du modèle.
3. **open-notebook (02), phase B** : la recherche duale vecteur puis texte, pour que le MCP cesse d'être moins capable que le REST.
4. **open-notebook (02), phase A** : les citations `[source:uuid]`, à décider seulement après les trois précédentes.

Écartés : le chunking (existe), l'index HNSW (refusé avec motif), la file d'indexation (refusée avec motif), le mean pooling (Philum embarque un vecteur par extrait, moyenner un document entier serait une régression), le scoring multi-facteurs (trois providers, pas trois cent cinquante).

---

## Estimation révisée

| Phase | Effort |
|---|---|
| Fallback entre providers et transparence (01 A+B) | ~3 jours |
| Sanitisation Unicode (03 C) | ~0,5 jour |
| Recherche duale en MCP (02 B) | ~1 jour |
| Citations `[source:uuid]` (02 A), sous réserve | ~2 jours |
| **Total** | **~4,5 jours, 6,5 avec les citations** |

Le total de 16 jours de la première version comptait 8 jours d'audit déjà consommés et 3 jours de chunking déjà écrits.

---

_Rédigé le 2026-08-30, corrigé le même jour après vérification du code Philum ligne à ligne et des trois dépôts via l'API GitHub._
