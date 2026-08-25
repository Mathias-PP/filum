# La boucle modèle ↔ outils (`agent.py`)

## apps/backend/app/services/agent.py
Lu intégralement : oui (1074/1074 lignes, 2 tranches 1-537 / 538-1074) · sha256: f016990c6ccd · date: 2026-08-25

Doctrine en tête de fichier : **sécurité, pas délégation** — clé déchiffrée ici et envoyée uniquement à l'endpoint du provider (jamais en SSE ni log), bornes dures, actions sensibles suspendues derrière approbation, outils exécutés avec le `user` authentifié du contexte (`apps/backend/app/services/agent.py:8`).

Constantes module :

- `MAX_TOURS` = `settings.agent_max_tours`, `MAX_TURN_TOKENS` = `settings.agent_max_turn_tokens` figés au chargement du module (`apps/backend/app/services/agent.py:61`) ; `_TIMEOUT`=60 s par appel HTTP ; `TOOL_RESULT_MAX`=120 000 chars plafonnant un résultat d'outil sérialisé (`apps/backend/app/services/agent.py:66`).
- `_SYSTEME` (`apps/backend/app/services/agent.py:68`) — prompt système généraliste : « agis, ne planifie pas », interdiction de fabriquer source/auteur/date/URL, verbatim strict des extraits, corriger avant supprimer, ne pas répéter un appel en erreur.
- `_PRIMING_MAX` = 40 000 chars pour le contexte workspace injecté (`apps/backend/app/services/agent.py:89`).
- `_MARQUEURS_CONTEXTE_SATURE` (`apps/backend/app/services/agent.py:95`) — 7 fragments relevés en prod (OpenAI, Anthropic, Google, Mistral, llama.cpp) identifiant un refus pour fenêtre saturée.
- `_RETRY_MAX_ATTENTE_S`=60 s et `_BACKOFF_5XX`=(2 s, 5 s) (`apps/backend/app/services/agent.py:298`,`302`).

### Symboles (20)

**Détection et diagnostics**

- `_est_contexte_sature` — `apps/backend/app/services/agent.py:106` — True si l'erreur provider contient un marqueur de fenêtre saturée.
- `_diagnostic_vide` — `apps/backend/app/services/agent.py:783` — message actionnable sur réponse vide : `length` → tokens de pensée Gemini comptés dans le budget (conseil : modèle sans raisonnement ou budget plus grand), `content_filter` → reformuler, sinon renoncement.

**Contexte injecté au prompt système**

- `_priming_workspace` — `apps/backend/app/services/agent.py:112` — charge `shared/` entier (généraliste) ou les chemins demandés par l'agent nommé (contexte divisé par 5 à 10) ; chemin absent ignoré ; chaîne vide si workspace non amorcé ; plafond `_PRIMING_MAX`.
- `_titre_source` — `apps/backend/app/services/agent.py:148` — (titre, nb extraits) d'une source ; fallback identifiant tronqué.
- `_titre_fiche` — `apps/backend/app/services/agent.py:165` — titre d'une fiche du créateur ; fallback slug.
- `_etat_avant_publication` — `apps/backend/app/services/agent.py:176` — décrit ce que la fiche porte RÉELLEMENT au moment de publier (nb sources, extraits retrouvés) : « Publier la fiche X ? » n'apprend rien, l'état oui.
- `_resume_approbation` — `apps/backend/app/services/agent.py:232` — résout UUID/slugs en titres lisibles pour 7 outils sensibles (`delete_source`, `delete_excerpt`, `delete_card`, `publish_card`, `update_card→public`, `create_content_attestation`, `archive_sources`) ; échec → phrase générique, jamais de blocage.

**Types de callbacks**

- `Approuver` / `Emitter` — `apps/backend/app/services/agent.py:276` / `:278` — signatures du callback d'approbation (request_id, outil, args → bool) et de l'émetteur SSE (dict sérialisable).

**Parsing transport**

- `_texte_message` — `apps/backend/app/services/agent.py:281` — concatène les parts `{text}` d'un contenu en liste, sinon str.
- `_extraire_retry_delay` — `apps/backend/app/services/agent.py:305` — lit `retryDelay:"43s"` du RetryInfo Google (corps parfois enveloppé dans une liste) ; observé en prod 2026-08-21.
- `_extraire_message_erreur` — `apps/backend/app/services/agent.py:335` — message texte d'un corps d'erreur OpenAI-compat (5 formes) ; duplique volontairement une partie de `_detail_provider` car l'import créerait un cycle via les tests.
- `_parse_blocking_response` — `apps/backend/app/services/agent.py:360` — statut ≠200 → erreur française enrichie du message provider (429 formulé « quota ou limite de débit »), 200 → délègue à l'adaptateur lot 1.
- `_parse_sse_stream` — `apps/backend/app/services/agent.py:384` — parsing flux OpenAI-compat avec 3 cas de prod gérés : SSE standard ; Cerebras JSON nu sans préfixe `data:` (ligne 409) ; fragmentation Gemini des tool_calls réassemblée par index. Règles conservatrices documentées lignes 441-456 après le bug prod 2026-08-22 (`fs_readfs_readfs_readfiche_etapes`) : `name` ATOMIQUE (affectation, ligne 491), `arguments` concaténés, nouveau `name` non vide sans index = nouvel appel (lignes 463-474). Préserve `extra_content` (thought_signature Gemini thinking) lignes 501-509.
- `_emettre_en_un_bloc` — `apps/backend/app/services/agent.py:521` — pousse le texte complet d'une réponse non-streamée via `on_delta` (repli 400, provider qui répond JSON malgré `stream=True`) : le client doit voir le texte arriver.
- `_dispatcher_sse` — `apps/backend/app/services/agent.py:539` — anthropique natif → adaptateur lot 1, sinon parser local.
- `_traiter_reponse_flux` — `apps/backend/app/services/agent.py:550` — arbre de statuts : 429 avec retryDelay ≤60 s → attente + UN retry ; 400 → repli bloquant (payload sans `stream`) ; 200 → stream selon Content-Type ; autre → erreur.

**Nettoyage multi-providers**

- `_nettoyer_messages` — `apps/backend/app/services/agent.py:627` — réduit chaque message au contrat OpenAI commun (`_CHAMPS_MESSAGE_STANDARDS` ligne 624) pour qu'une session ouverte chez A continue chez B : retire `extra_content` SAUF retour vers Gemini (Mistral répondrait 422 `extra_forbidden`, ligne 689) ; filtre les tool_calls de nom inconnu et les messages `tool` orphelins (Gemini 400 « invalid argument », bug prod 2026-08-22) ; drop les assistants fantômes sans tool_calls valides ni texte.

**Appel et boucle**

- `_appel_provider` — `apps/backend/app/services/agent.py:714` — déchiffre la clé (`_decrypt`), construit URL+headers (lot 1), nettoie l'historique avec les noms d'outils valides du tour, POST streaming avec backoff 502/503/504 ([2 s, 5 s], ligne 752-773) ; erreurs réseau/JSON rendues en string, jamais levées.
- `_message_tool` — `apps/backend/app/services/agent.py:825` — message `tool` avec `tool_call_id` OBLIGATOIRE (Gemini rejette HTTP 400 INVALID_ARGUMENT sans, vérifié en prod 2026-08-21) ; sérialisation `default=str`, troncature `TOOL_RESULT_MAX`.
- `_executer_tour` — `apps/backend/app/services/agent.py:840` — pour chaque tool_call : émettre `tool_call`, si sensible émettre `approval_request` → attendre verdict → `approval_resolved`, exécuter (ou dict d'erreur si refus), émettre `tool_result`, appender le message tool (id synthétisé `call_<hex>` si le provider n'en a pas fourni).
- `boucle` — `apps/backend/app/services/agent.py:911` — le point d'entrée. Ordre exact : construire/filtrer le registre selon `agent_def.tools` → priming workspace selon `agent_def.context` → prompt système enrichi du rôle de l'agent nommé → **rappel graphe mémoire** en SQL (import tardif `graph_memory.recall`, hops=3, dernier message user, échec silencieux, lignes 946-967) → insertion system en tête → compaction préventive (budget 96k, événement `contexte_compacte`) → boucle 1..quota_tours : appel provider ; string d'erreur → rejeu UNIQUE si fenêtre saturée (compaction à 6k, flag `rejeu_fait` ne consommant pas la passe préventive) puis `error`+return ; pas de tool_calls → texte ? `done` : diagnostic vide + `error` ; sinon append assistant + `_executer_tour`. Après quota : compaction finale + `continuation` (pause/reprise, PAS une erreur). Toute exception → log + `error` visible.

Effets de bord : réseau sortant vers le provider ; écritures DB par les outils (via ToolContext) ; mutation in-place de `messages` (documentée) ; aucun secret dans les événements SSE (la clé ne sort jamais du module).
