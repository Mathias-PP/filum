# Plan : parité MCP ↔ UI + hardening du workspace créateur-de-fiches

## Contexte

Cette session a fait émerger deux blocages majeurs pour qu'un agent (Claude Code, opencode, Codex, Cursor) puisse créer et corriger des fiches Philum en autonomie complète, avec la même qualité qu'un humain via l'UI.

**Bloc 1 : le workspace `workspaces/createur-de-fiches/` a des angles morts.**
L'agent opencode + DeepSeek a réussi à fabriquer une fiche sur WEST/ITER, mais a dû découvrir seul plusieurs pièges (URL immuable après création, DELETE retourne 204 sans corps JSON, position des sources non modifiable, 403 anti-bot ScienceDirect, plafond `text` d'extrait à 1000 caractères) parce qu'aucun de ces points n'était documenté dans `shared/philum-mcp.md`. Il a aussi « corrigé » des tirets cadratins d'une source ANS en virgules, ce qui falsifie le verbatim : l'ambiguïté « pas de cadratins » (règle éditoriale du projet) vs. « verbatim préservé » (règle Philum) n'est pas tranchée.

**Bloc 2 : le serveur MCP ne couvre que 10 des 55 endpoints REST du backend.**
Un agent MCP-only ne peut pas modifier une fiche après création, retirer une source ou un extrait, relire ses extraits vs. la page (le bouton « Relire la source » de l'UI, qui aurait rendu les extraits de la fiche CEA vérifiés), utiliser l'extraction auto, les suggestions LLM, gérer les connexions du graphe, archiver via Wayback, signer une attestation Ed25519, voir sa liste de fiches, ou chercher dans ses extraits. **28 fonctions manquent** pour la parité complète MCP ↔ UI.

L'utilisateur a validé : parité totale (P1+P2+P3), avec **le workspace fixé en premier** pour que la documentation puisse ensuite incorporer les nouveaux tools au fur et à mesure de leur ajout.

**Résultat visé** : un agent recevant une consigne « crée-moi une fiche Philum sur le sujet X » a tout ce qu'il faut, dans un langage clair, pour aller jusqu'à la publication + relecture + connexions + attestation, sans réinventer les pièges et sans devoir passer par des appels REST manuels hors MCP.

---

## Séquence des PRs

Cinq PRs, une par chantier, mergées et déployées en série pour éviter les cascades de conflits.

| PR  | Chantier                                    | Fichiers                                                                        | Poids           |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------- | --------------- |
| A   | Hardening workspace créateur-de-fiches      | 6 fichiers `workspaces/createur-de-fiches/`                                     | Docs            |
| B   | MCP P1 — mutations essentielles             | `mcp_server/tools_write.py`, `server.py`, tests, `shared/philum-mcp.md`         | Backend + tests |
| C   | MCP P2 — extract, suggest, archive, listing | Mêmes fichiers, +10 tools                                                       | Backend + tests |
| D   | MCP P3 — attestations, citations, batch     | Mêmes fichiers, +10 tools                                                       | Backend + tests |
| E   | Consolidation workspace post-parité         | `shared/philum-mcp.md` + retrait des workarounds REST des `stages/*/CONTEXT.md` | Docs            |

---

## Chantier A — Hardening du workspace créateur-de-fiches

**But** : rendre le workspace utilisable par un agent qui n'a jamais lu le repo backend, sans redécouvrir les pièges.

### Fichiers à modifier

- **`workspaces/createur-de-fiches/AGENTS.md`** : ajouter une section « Démarrer une fiche » en tête (avant la routing table). Trois lignes actionnables : `cp -r runs/_example runs/<slug>` → remplir `00-brief.md` → lancer `stages/01-brief/`. Sans cette section, un agent doit lire quatre fichiers pour trouver son point d'entrée.

- **`workspaces/createur-de-fiches/shared/style-redactionnel.md`** : trancher la règle des tirets cadratins. Formulation retenue :

  > Pas de cadratins (`—`), sauf s'il y en a dans le verbatim exact. Autrement dit : interdits dans toute prose éditoriale (titre, description, annotation, titre d'extrait, `context`, commentaires), préservés dans le champ `text` d'un extrait quand la source les utilise. Remplacer un cadratin par une virgule dans un verbatim falsifie ce que la source a écrit.

- **`workspaces/createur-de-fiches/shared/philum-mcp.md`** : enrichir la section « Ce que les tools MCP NE FONT PAS » avec les vrais endpoints REST à appeler manuellement (jusqu'à ce que le chantier B/C/D les wrappe). Ajouter une nouvelle section « Gotchas » listant : URL immuable après `add_source`, DELETE retourne 204 sans corps JSON, position des sources = ordre d'insertion (pas de reorder), `text` d'extrait plafonné à 1000 caractères, la dédup par URL/DOI de `add_source` (un second appel avec les mêmes URL/DOI met à jour la source existante au lieu d'en créer une).

- **Nouveau : `workspaces/createur-de-fiches/shared/pieges-vecus.md`** : capitaliser les erreurs de la session opencode et de futures sessions. Modèle : une entrée par piège avec « Symptôme » / « Cause » / « Résolution ». Cinq entrées de départ :
  1. URL d'IOP ne correspond pas au DOI (coquille inventée par le fetch d'origine) → toujours vérifier `URL contient DOI` ou faire un HEAD sur l'URL avant `add_source`.
  2. 403 anti-bot sur ScienceDirect / IOP → utiliser l'endpoint `verify` avec `ProvidedText` en payload (l'agent atteste que le texte fourni est celui de la source).
  3. `add_excerpt` refuse un texte > 1000 caractères → couper au niveau d'une phrase (jamais en milieu), poser plusieurs extraits si nécessaire.
  4. Extrait posé avec cadratins remplacés par virgules → falsification du verbatim. Voir `style-redactionnel.md` § « Cadratins et verbatim ».
  5. `add_source` appelé deux fois avec la même URL ne double pas la source, il la met à jour → utiliser ce comportement volontairement pour poser l'annotation après le premier passage.

- **`workspaces/createur-de-fiches/stages/03-annotations/CONTEXT.md`** : préciser à l'étape 3 du Process que le second `add_source` (avec `annotation` et `stance`) exploite la dédup par URL/DOI et met à jour la source existante ; aucun doublon créé. Sans cette précision, un agent peut soit hésiter soit passer par `update_source` (qui n'existe pas encore en MCP à ce stade).

- **`workspaces/createur-de-fiches/runs/_example/`** : ajouter un sous-dossier `stages/02-sources-collectees/output/` contenant un `exemple-memoire-sommeil-sources.md` court (3 sources dont 1 pivot, format complet) et un `exemple-memoire-sommeil-ids.json` correspondant. Un agent débutant a besoin de voir la forme concrète d'une étape terminée. Ajouter un pointeur explicite dans le README `_example` : « Regarde `stages/02-.../output/` pour la forme d'une étape terminée ».

### Vérification

- Grep sur le workspace : `grep -r "—" workspaces/createur-de-fiches` retourne uniquement les 3 mentions dans des règles d'audit citées entre backticks (déjà connu).
- Grep sur le workspace : `grep -r "3 pivot\|max.{0,20}pivot" workspaces/createur-de-fiches` retourne 0 (résidu potentiel de la PR 489 déjà mergée, à re-vérifier).
- Walk test cold : un agent qui n'a jamais lu le workspace ouvre `AGENTS.md`, arrive sur la section « Démarrer une fiche » en tête et sait quoi faire en < 30 secondes.

---

## Chantier B — MCP P1 : mutations essentielles (8 tools)

**But** : rendre possible la correction d'une fiche après création. Règle le cas CEA (extraits non relus) et supprime la nécessité du rebuild qu'opencode voulait faire.

### Fichiers à modifier

- **`apps/backend/app/mcp_server/tools_write.py`** : ajouter 4 tools de mutation.
  - `update_card(db, user, *, slug, title=None, description=None, content_url=None, content_authors=None, platform=None, content_type=None, visibility=None)` : PATCH cible. Réutilise `_fiche_du_createur(db, user, slug)` pour lever `ToolError` si non-propriétaire (helper existant, ligne 44). Setattr sur chaque champ non-None, `await db.commit()`. Retourne dict compact `{slug, title, description, ...}`.
  - `update_source(db, user, *, source_id, annotation=None, stance=None, is_pivot=None, category=None, author_kind=None, title=None, authors=None, journal=None, doi=None, format=None, archive_url=None)` : PATCH source. Réutilise le pattern `_owned_source` (à créer si absent, calquer sur `_get_owned_source` de `excerpts.py` ligne 150). Interdit de changer `url` (documenté dans la docstring, l'endpoint REST refuse déjà).
  - `delete_source(db, user, *, source_id)` : soft-delete. `SET source.deleted_at = now()`, `await db.commit()`. Vérification propriétaire via `_owned_source`.
  - `delete_excerpt(db, user, *, source_id, excerpt_id)` : DELETE physique (l'endpoint REST fait `db.delete(excerpt)`, ligne 271 de `excerpts.py`). Même pattern de vérification.

- **`apps/backend/app/mcp_server/tools.py`** ou nouveau `tools_verify.py` : ajouter 4 tools de vérification et graphe.
  - `verify_excerpts(db, user, *, source_id, provided_text=None)` : POST /excerpts/verify équivalent. Réutilise `_get_owned_source` + `ancrer()` de `excerpt_anchor.py`. Retourne la liste des `ExcerptCheck` (dict `{excerpt_id, status: found|moved|missing|unreadable, start, end, context_before, context_after}`) + `text_source: fetched|provided`. Le paramètre `provided_text` permet à l'agent d'attester le texte quand la page est bloquée anti-bot (cas ScienceDirect/IOP).
  - `list_connections(db, user, *, card_slug)` : GET /cards/{id}/connections équivalent. Vérification via `_fiche_du_createur`. Retourne `{outgoing: [...], incoming: [...]}` avec pour chaque connexion `{source_id, source_title, source_url, card_id, card_title, card_slug, card_creator_slug, confirmed}`.
  - `confirm_connection(db, user, *, card_slug, source_id)` : POST /connections/{id}/confirm. SET `source.link_confirmed_at = now()`. Vérification propriétaire de la fiche parent + de la source appartenant à cette fiche.
  - `remove_connection(db, user, *, card_slug, source_id)` : DELETE /connections/{id}. SET `source.linked_card_id = None` (garde la source, retire le lien, comportement de `card_connections.py` ligne 170).

- **`apps/backend/app/mcp_server/server.py`** : déclarer chacun des 8 nouveaux tools avec `@mcp.tool()`, wrap qui obtient `db` et `user` (via `exiger_utilisateur(db)`) puis appelle la fonction correspondante de `tools_write.py`/`tools_verify.py`. Suivre le patron des 5 tools d'écriture existants (ligne exacte à copier depuis `add_source` par exemple).

- **`apps/backend/tests/unit/test_mcp_tools_write.py`** (ou fichier séparé `test_mcp_tools_mutations.py` selon la longueur) : 16 tests, deux par tool.
  - Happy path : l'action réussit et modifie l'état côté DB comme attendu.
  - Non-propriétaire refusé : un second user tente l'action sur une ressource du premier user, `ToolError` levée avec message qui ne révèle pas l'existence de la ressource (voir helper `_fiche_du_createur`).
  - Un test spécifique pour `verify_excerpts` avec `provided_text` non-vide : vérifie que `text_source == "provided"` dans la réponse.

- **`workspaces/createur-de-fiches/shared/philum-mcp.md`** : ajouter les 8 nouveaux tools dans la table « Écriture » avec signatures exactes, retirer de la section « Ce que les tools MCP NE FONT PAS » les entrées maintenant couvertes.

### Vérification

- `CI=true uv run pytest tests/unit/test_mcp_tools_write.py -q` : les 16 nouveaux tests passent.
- Suite complète : `CI=true uv run pytest tests/unit tests/integration -q` : 0 regression, count > 1381 tests actuels.
- Openapi.json non impacté (les tools MCP ne sont pas exposés en HTTP).

---

## Chantier C — MCP P2 : extraction, LLM, archivage, listing (10 tools)

**But** : rendre l'agent capable de tout ce qu'un humain fait via l'UI côté extraction, aide LLM et gestion.

### Tools à ajouter

Dans `tools_write.py`, `tools.py` ou fichiers dédiés selon regroupement (`tools_import.py`, `tools_llm.py`, `tools_read.py` proposés) :

1. `import_from_content_url(db, user, *, card_slug, provided_text=None)` : équivalent bouton « Extraire les sources ». POST /import/from-content-url. Retourne la liste des sources extraites avec score, sans les poser (l'agent décide ensuite lesquelles `add_source`).
2. `get_youtube_transcript(db, user, *, url)` : POST /import/youtube-transcript. Retourne `{transcript, language}`.
3. `get_url_metadata(db, user, *, url)` : POST /import/url-metadata. Retourne titre, auteur, date.
4. `suggest_excerpts(db, user, *, source_id, provided_text=None, include_annotation=True, include_existing=True, include_card_context=True)` : POST /excerpts/suggest. Le LLM propose des extraits. Signature identique à l'endpoint REST (PR #474 a introduit les 3 flags).
5. `annotate_excerpt(db, user, *, source_id, excerpt_text, provided_text=None)` : POST /excerpts/annotate. Le LLM suggère titre + `context` pour un extrait donné.
6. `chunk_text(db, user, *, source_id, provided_text, chunk_size=None)` : POST /excerpts/chunk. Découpe un texte long en chunks candidats (utile quand la source est massive).
7. `archive_sources(db, user, *, source_ids)` : POST /sources/archive. Déclenche l'archivage Wayback pour la liste.
8. `list_my_cards(db, user, *, status=None, limit=20)` : GET /cards. Retourne la liste des fiches du user.
9. `list_sources(db, user, *, card_slug)` : GET /sources?card_id=. Sources d'une fiche.
10. `search_my_excerpts(db, user, *, query, limit=20)` : GET /excerpts/search. Recherche full-text dans les extraits du user.

Plus deux tools de cycle de vie : 11. `delete_card(db, user, *, slug)` : soft-delete (rejoint la corbeille). 12. `restore_card(db, user, *, slug)` : sortir de la corbeille.

### Fichiers modifiés

- `apps/backend/app/mcp_server/*.py` : 12 tools nouveaux (P2 dépasse les 10 initialement annoncés à cause de delete_card/restore_card qui sont logiquement dans la même vague).
- `apps/backend/tests/unit/test_mcp_tools_*.py` : 24 tests (happy path + non-propriétaire pour chacun).
- `workspaces/createur-de-fiches/shared/philum-mcp.md` : ajout des 12 nouveaux tools.

### Vérification

- Tests MCP verts.
- Suite complète verte.
- Verification manuelle sur la prod : un agent appelle `import_from_content_url` sur une URL YouTube réelle, reçoit la liste des sources extraites.

---

## Chantier D — MCP P3 : attestations, citations entrantes, batch, claim (10 tools)

**But** : couvrir les fonctions restantes (attestations cryptographiques, sociabilité, batch d'efficacité).

### Tools à ajouter

1. `create_content_attestation(db, user, *, card_slug, ...)` : POST /attestations/content. Signature Ed25519 du contenu de la fiche. Payload figé (voir `shared/garde-fous.md` : « jamais de modification de la forme du payload signé sans ADR »).
2. `get_attestation(db, user, *, attestation_id)` : GET /attestations/{id}.
3. `verify_attestation(db, user, *, attestation_id)` : GET /attestations/{id}/verify. Vérifie la signature.
4. `list_incoming_citations(db, user)` : GET /cards/citations. Qui me cite.
5. `mark_citations_seen(db, user)` : POST /cards/citations/seen.
6. `add_sources_batch(db, user, *, card_slug, sources)` : POST /sources/batch. Poser plusieurs sources en un appel (efficacité pour les fiches longues).
7. `create_claim_request(db, user, *, card_id, message=None)` : POST /cards/{id}/claim-requests. Revendique une fiche « seed » (créée par extraction sans compte).
8. `upload_content_text_file(db, user, *, card_slug, file_content, filename, confirm_publication_rights)` : POST /cards/{id}/content-text/upload. Variante de `set_content_text` avec fichier binaire (PDF, DOCX, ODT, TXT, MD ; le backend fait l'extraction).
9. `parse_biblio(db, user, *, text, format=None)` : POST /import/parse. Parser BibTeX/CSL/RIS collé.
10. `paste_biblio(db, user, *, text)` : POST /import/paste. Parser une bibliographie collée en texte libre.

Plus `list_deleted_cards(db, user)` (GET /cards/deleted) pour compléter le cycle de vie corbeille.

### Fichiers modifiés

- `apps/backend/app/mcp_server/*.py` : 11 tools nouveaux.
- `apps/backend/tests/unit/test_mcp_tools_*.py` : 22 tests.
- `workspaces/createur-de-fiches/shared/philum-mcp.md` : ajout final.

### Vérification

- Tests MCP verts.
- Suite complète verte.
- Un agent MCP-only peut désormais réaliser un cycle complet : create_card → import_from_content_url → add_source (batch) → add_excerpt → verify_excerpts → annotate_excerpt → set_content_text → list_connections → confirm_connection → create_content_attestation → publish_card. Sans jamais toucher à un endpoint REST.

---

## Chantier E — Consolidation finale du workspace

**But** : après les 28 nouveaux tools MCP livrés, retirer du workspace toutes les mentions d'endpoints REST à appeler manuellement.

### Fichiers modifiés

- **`workspaces/createur-de-fiches/shared/philum-mcp.md`** : la section « Ce que les tools MCP NE FONT PAS » se réduit à quelques cas résiduels (Discover public, feed public, OG images). Le reste doit maintenant renvoyer aux tools MCP correspondants.

- **`workspaces/createur-de-fiches/stages/02-sources-collectees/CONTEXT.md`** : remplacer les appels REST manuels par les nouveaux tools (`import_from_content_url`, `add_sources_batch`).

- **`workspaces/createur-de-fiches/stages/04-extraits/CONTEXT.md`** : appeler `suggest_excerpts` et `verify_excerpts` en MCP au lieu de REST.

- **`workspaces/createur-de-fiches/stages/05-connexions/CONTEXT.md`** : `list_connections`, `confirm_connection`, `remove_connection` en MCP.

- **`workspaces/createur-de-fiches/stages/07-publication/CONTEXT.md`** : optionnel — ajouter une étape « signer avec `create_content_attestation` avant `publish_card` » pour les fiches qui veulent la couche cryptographique.

- **`workspaces/createur-de-fiches/shared/pieges-vecus.md`** : retirer les entrées désormais couvertes par des tools MCP (par exemple, plus besoin de rappeler que verify prend `ProvidedText` puisque le tool `verify_excerpts` le prend en paramètre).

### Vérification

Walk test final : un agent qui débarque et lit `AGENTS.md` peut, sans jamais faire d'appel REST manuel, réaliser une fiche complète et vérifiée. Toutes les étapes du pipeline (01 à 07) sont couvertes par les tools MCP annoncés dans `shared/philum-mcp.md`.

---

## Fichiers critiques à connaître avant d'exécuter

- `apps/backend/app/mcp_server/tools_write.py` : contient le pattern exact à copier. `_fiche_du_createur` (ligne 44) est le helper à réutiliser pour la vérification propriétaire.
- `apps/backend/app/mcp_server/server.py` : contient `exiger_utilisateur(db)` qui décode le Bearer JWT et rend l'user. À utiliser dans chaque wrapper `@mcp.tool()`.
- `apps/backend/app/mcp_server/auth.py` : mécanique du token JWT MCP.
- `apps/backend/app/api/v1/endpoints/excerpts.py` : contient `_get_owned_source` (ligne 150) à répliquer/adapter pour les tools qui touchent aux sources.
- `apps/backend/app/api/v1/endpoints/cards.py` : contient la logique PATCH cards (ligne 269-298) qui devient la source du tool `update_card`.
- `apps/backend/app/api/v1/endpoints/sources.py` : contient PATCH sources (ligne 610-660) pour `update_source`, DELETE (ligne 670-680) pour `delete_source`.
- `apps/backend/app/services/excerpt_anchor.py` : `ancrer(Selecteurs)` utilisé par `verify_excerpts`.
- `apps/backend/app/services/card_link.py` : `effective_linked_card_id` pour la logique de connexion.
- `apps/backend/tests/unit/test_mcp_tools_write.py` : contient le pattern de test à copier.

## Estimation de charge

- Chantier A : 1-2h, 1 PR docs.
- Chantier B : 3-4h, 1 PR (~250 lignes de code + ~200 lignes de tests).
- Chantier C : 3-4h, 1 PR.
- Chantier D : 3-4h, 1 PR.
- Chantier E : 1-2h, 1 PR docs.

Total : ~15h de travail effectif, 5 PRs, réparties sur plusieurs sessions selon disponibilité. Chaque PR est mergeable indépendamment et Vercel/GCP redéploient automatiquement à chaque merge sur main.
