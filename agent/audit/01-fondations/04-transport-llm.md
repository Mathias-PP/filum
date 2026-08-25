# Transport LLM : les deux voies d'appel aux modèles

L'agent parle aux modèles par deux voies indépendantes :

1. **Voie serveur** (`services/llm.py`) — tâches bibliographiques internes, via `litellm_base_url`, alias de tâche comme nom de modèle. Ne lève jamais : rend `None` en cas de pépin.
2. **Voie BYOK** (`services/llm_adapters.py` + boucle lot 2) — le chat agent sur la clé du créateur ; adaptateurs de protocole OpenAI-compat / Anthropic natif.

---

## apps/backend/app/services/llm.py
Lu intégralement : oui (715/715 lignes) · sha256: 872b43feeb30 · date: 2026-08-25

Unique point de contact LLM du backend pour les tâches serveur. Le backend n'appelle jamais un provider directement : il parle au point d'entrée configuré avec un **alias de tâche** comme nom de modèle (`apps/backend/app/services/llm.py:1`). Si `litellm_base_url` est vide, toute la couche est désactivée et chaque appel rend None.

Constantes et état module :

- `_TIMEOUT` = 45 s, `_MAX_INPUT_CHARS` = 40 000 — tronquer borne le coût et reste sous les free tiers (`apps/backend/app/services/llm.py:25`).
- `derniere_panne` — `apps/backend/app/services/llm.py:37` — ce que le provider a dit au dernier échec, pour la sonde de diagnostic ; la couche ne levant jamais, ce motif ne survit nulle part hors des logs sinon.

### Symboles (27)

**Mécanique d'appel**

- `_retenir_panne` — `apps/backend/app/services/llm.py:40` — garde alias + statut HTTP + message (tronqué à 400) du dernier échec, clé master expurgée.
- `url_chat` — `apps/backend/app/services/llm.py:49` — construit l'URL chat : racine **sans chemin** (proxy nu type `http://litellm:4000`) → préfixe `/v1` ; racine **avec chemin** (provider direct, ex. Gemini `/v1beta/openai`) → concaténation directe, car ajouter `/v1` donnerait un 404 muet.
- `resoudre_modele` — `apps/backend/app/services/llm.py:63` — en mode proxy l'alias part tel quel (LiteLLM résout) ; en visée directe c'est `llm_direct_model` qui tranche, sinon l'appel serait 404 modèle inconnu.
- `modeles_candidats` — `apps/backend/app/services/llm.py:74` — liste ordonnée [direct/fallbacks] à essayer : le quota gratuit Gemini se compte par modèle/jour, un quota épuisé coûte un appel perdu, pas la journée. En mode proxy, liste réduite à l'alias.
- `_appel_json` — `apps/backend/app/services/llm.py:91` — le cœur : POST temperature=0, sortie contrainte `json_schema` ; si le schéma Pydantic (anyOf/$defs) est refusé en 400 → repli `json_object` avec schéma recopié dans la consigne (`apps/backend/app/services/llm.py:139`) ; 404/429 → modèle suivant de la liste candidate (`apps/backend/app/services/llm.py:146`) ; tout autre statut est terminal (une clé refusée ne s'améliore pas sur un second modèle). Rend le contenu texte brut — la validation est TOUJOURS en aval, rien n'est accepté sur la foi du mode demandé.

**Extraction de métadonnées (alias `metadata-extract`)**

- `LlmSourceMetadata` — `apps/backend/app/services/llm.py:163` — title/authors/published_at/description/format/category/author_kind, tous optionnels : le LLM ne doit jamais inventer une valeur absente.
- `_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:179` — règles strictes anti-invention, titre sans nom de site ni séparateur « | ».
- `parse_metadata_content` — `apps/backend/app/services/llm.py:192` — validation JSON ; une valeur d'enum hors taxonomie ne jette pas tout : champs enum retirés puis revalidation (`apps/backend/app/services/llm.py:198`).
- `extract_metadata` — `apps/backend/app/services/llm.py:698` — appel public ; l'appelant (extracteur heuristique) reste source de vérité.

**Bibliographies (alias `biblio-parse`)**

- `LlmUrlClassification` — `apps/backend/app/services/llm.py:645` — modèle de sortie de la classification d'URL : un seul champ `type` ; une valeur hors ensemble autorisé est rendue None par l'appelant.


- `LlmBiblioRef` / `LlmBiblioRefs` — `apps/backend/app/services/llm.py:213` / `apps/backend/app/services/llm.py:224` — une référence / une liste.
- `_BIBLIO_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:228` — recopie verbatim url/doi, jamais fabriquer.
- `parse_biblio_content` — `apps/backend/app/services/llm.py:239` — même tolérance enum (category retirée par ref si invalide).
- `parse_reference_block` — `apps/backend/app/services/llm.py:273` — fallback UNE référence (bloc <500 chars, cap dur 2000) quand regex a trouvé DOI/URL mais Crossref a échoué.
- `parse_bibliography` — `apps/backend/app/services/llm.py:317` — extraction d'une bibliographie collée en texte libre.
- `classify_url_type` — `apps/backend/app/services/llm.py:666` — classification d'URL trouvée dans un contenu : `source|promo|social|other` (badge UI preview, l'utilisateur tranche toujours) ; contexte adjacent fortement aidant ; valeur hors ensemble → None.

**Transcriptions (alias `biblio-parse`, prompt dédié)**

- `_TRANSCRIPT_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:337` — parole transcrite bruitée : ne relever QUE ce qui est réellement nommé, url/doi presque toujours null, ignore les mentions vagues.
- `split_transcript` — `apps/backend/app/services/llm.py:359` — découpe ≤30 000 chars sur frontière de mot, plafond 8 morceaux (`_TRANSCRIPT_CHUNK_CHARS`/`_TRANSCRIPT_MAX_CHUNKS`, ligne 355) : une heure de parole ~50 k chars dépasserait sinon le plafond d'entrée et perdrait la seconde moitié silencieusement.
- `extract_mentioned_works` — `apps/backend/app/services/llm.py:375` — parallélise les morceaux via asyncio.gather, fusionne ; résultat = suggestion à valider, jamais autoritative.
- `_extract_works_from_chunk` — `apps/backend/app/services/llm.py:396`.

**Extraits citables (alias `excerpt-suggest`)**

- `LlmExcerpts` — `apps/backend/app/services/llm.py:407`.
- `_EXCERPT_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:411` — verbatim strict, 2→5 extraits, ≥15 mots, un extrait doit rester intelligible détaché (étendre vers l'amont si pronom sans référent).
- `parse_excerpts_content` — `apps/backend/app/services/llm.py:433`.
- `suggest_excerpts` — `apps/backend/app/services/llm.py:440` — accepte `context` (fiche du créateur ≤500) et `existing_excerpts` (≤10, tronqués 300) pour ne pas reproposer ce qui est déjà cité. L'appelant DOIT vérifier que chaque extrait apparaît dans la source (anti-hallucination).

**Intitulés de passages**

- `LlmChunkTitles` — `apps/backend/app/services/llm.py:487`.
- `_CHUNK_TITLE_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:491` — repérage 2→6 mots, pas un résumé ; chaîne vide plutôt qu'intitulé approximatif.
- `_titre_recevable` — `apps/backend/app/services/llm.py:514` — None si >8 mots (`_MAX_TITLE_MOTS` ligne 508) ou vide ; un titre trop long est REFUSÉ, pas tronqué (couper produirait un intitulé faux plutôt qu'une absence claire).
- `suggest_chunk_titles` — `apps/backend/app/services/llm.py:526` — None plutôt qu'à-peu-pres : règle tenue en #317/#323/#327.
- `normalize_chunk_titles` — `apps/backend/app/services/llm.py:553` — aligne strictement sur les passages (un modèle bavard ne doit pas décaler les intitulés suivants).

**Mise en situation d'extrait**

- `LlmAnnotation` — `apps/backend/app/services/llm.py:575` — `title` + `context` (UNE phrase ≤40 mots qui situe le passage hors de son document ; antécédents des pronoms nommés en clair obligatoires).
- `_ANNOTATION_SYSTEM_PROMPT` — `apps/backend/app/services/llm.py:580`.
- `suggest_annotation` — `apps/backend/app/services/llm.py:600` — entourage ≤6000 chars fourni si disponible ; proposition à valider, jamais un acquis ; context tronqué à 500 (`_MAX_CONTEXT_CHARS` ligne 511).

Effets de bord : réseau sortant uniquement (httpx), écriture de `derniere_panne` en mémoire process. Aucun accès DB.

---

## apps/backend/app/services/llm_adapters.py
Lu intégralement : oui (365/365 lignes) · sha256: f0e0ec7eb829 · date: 2026-08-25

Adaptateurs de protocole BYOK. Le reste du code (boucle, testeur) travaille toujours en structures OpenAI-like ; la conversion est confinée ici (`apps/backend/app/services/llm_adapters.py:1`).

- `_PROTOCOLE` — `apps/backend/app/services/llm_adapters.py:17` — table kind→protocole : seul `anthropic` a un traitement natif, les 8 autres kinds (openai, deepseek, gemini, groq, openrouter, mistral, cerebras, custom) sont openai-compat.

### Symboles (10)

- `protocole_pour` — `apps/backend/app/services/llm_adapters.py:30` — lookup avec repli "openai" pour kind inconnu.
- `_url_openai` — `apps/backend/app/services/llm_adapters.py:39` — même règle que `url_chat` : chemin présent → `/chat/completions` direct, racine nue → `/v1/chat/completions`.
- `url_et_headers` — `apps/backend/app/services/llm_adapters.py:45` — Anthropic : `{base}/v1/messages` + headers `x-api-key` et `anthropic-version: 2023-06-01` ; OpenAI-compat : Bearer.
- `_messages_vers_anthropic` — `apps/backend/app/services/llm_adapters.py:60` — conversion messages : system extraits et joints (`\n\n`), messages `tool` accumulés puis regroupés en UN bloc user `tool_result` (Anthropic exige l'alternance user/assistant, ligne 93 et flush final ligne 130), tool_calls assistant convertis en blocs `tool_use` (arguments JSON re-parsés, fallback `{}` si invalides).
- `_tools_vers_anthropic` — `apps/backend/app/services/llm_adapters.py:136` — `parameters` → `input_schema`.
- `format_chat_payload` — `apps/backend/app/services/llm_adapters.py:152` — payload POST complet selon protocole ; temperature=0 des deux côtés, `stream` optionnel (défaut True).
- `parse_blocking_response` — `apps/backend/app/services/llm_adapters.py:195` — dispatch bloquant → tuple (message_openai_like, finish_reason, usage) ou string d'erreur.
- `_parse_openai_blocking` — `apps/backend/app/services/llm_adapters.py:205` — choices[0].message ; corps inattendu → message d'erreur explicite (pas d'exception).
- `_parse_anthropic_blocking` — `apps/backend/app/services/llm_adapters.py:218` — blocs text/tool_use → message OpenAI-like ; map stop_reason : end_turn→stop, tool_use→tool_calls, max_tokens→length ; usage input/output_tokens renommés prompt/completion.
- `parse_sse_stream_anthropic` — `apps/backend/app/services/llm_adapters.py:265` — lit le flux SSE Anthropic ligne à ligne : `message_start` (usage initial), `content_block_start` (ouvre un tool_call par index), `content_block_delta` (text_delta → callback `on_delta` awaitable + accumulation ; input_json_delta → arguments partiels concaténés), `message_delta` (stop_reason + usage final), `message_stop`/`[DONE]` (fin). StreamError réseau → string d'erreur. Reconstruit le message complet en fin de flux.

Pièges notés à la lecture :

- Le repli "openai" pour un kind inconnu est volontaire mais silencieux : un nouveau ProviderKind ajouté dans le schéma sans entrée dans `_PROTOCOLE` partira en openai-compat sans erreur (`apps/backend/app/services/llm_adapters.py:31`).
- Les erreurs de parsing rendent des strings, pas des exceptions : l'appelant (boucle lot 2) doit traiter `isinstance(résultat, str)` comme échec provider.
