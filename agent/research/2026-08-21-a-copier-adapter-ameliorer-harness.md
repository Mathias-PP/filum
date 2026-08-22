# 2026-08-21 — Du comparatif providers à l'action : copier / adapter / améliorer pour le harness Philum

> **Objet** : transformer l'étude `2026-08-21-providers-multi-modeles-gratuits.md`
> (opencode/Zen, hermes-agent, openclaw, dsh) en liste d'actions concrètes pour le
> harness BYOK Philum, **vérifiées contre le code actuel** (main @ #511 : #508 chat UI +
> réglages, #509 orchestrateur fiche, #510/#511 erreurs classifiées + cache /models).
>
> **Méthode** : chaque item cite le projet source, le fichier Philum concerné, un
> ordre de grandeur d'effort et une priorité. Ce qui existe déjà est listé en tête
> pour ne pas le re-recommander.

---

## 0. Ce que Philum fait DÉJÀ (ne pas re-proposer)

| Capacité | Fichier | Équivalent étudié |
|---|---|---|
| 9 kinds dont **openrouter**, gemini, groq, mistral, cerebras, custom | `schemas/agent_provider.py` (`ProviderKind`) | openclaw ~30 plugins ; Philum couvre l'essentiel |
| Clés chiffrées AES-GCM au repos, forme masquée en sortie | `models/agent_provider.py`, `_api_key_masked` | **Mieux qu'opencode** (auth.json en clair) |
| Garde SSRF sur base_url fournie | `agent_providers.py:_resolve_base_url` | openclaw `allowPrivateNetwork` |
| Test de clé avec message actionnable + `provider_message` brut | `tester()` + `_classify` (#511) | openclaw « Test connection » |
| Classification par code d'erreur (`insufficient_quota` vs `rate_limit_exceeded`…) | `_CADRAGES_CODE` (#511) | unique parmi les 4 ! |
| Catalogue vivant `GET /models` + cache TTL 15 min + warm-on-test + repli statique | `lister_modeles()` + `MODELES_SUGGERES` | models.dev / `/zen/v1/models` |
| Surface Anthropic native en repli du test | `tester()` (400/404 → `/v1/messages`) | Zen multi-protocole (partiel) |
| Notice de souveraineté des données + pays d'hébergement par provider | `DATA_SCOPE_NOTICE`, `PROVIDER_META` | **Philum en avance** sur les 4 |
| Sessions persistées, approbation outils (futures 300 s), workspace ICM en base, orchestrateur fiche par étapes | `agent_sessions.py`, `agent_approvals.py`, `agent_workspace.py`, `agent_fiche.py` | — |

---

## 1. Tableau de synthèse priorisé

| # | Action | Source | Effort | Priorité |
|---|---|---|---|---|
| A1 | Débloquer les runtimes locaux derrière la garde SSRF (**utile en self-host/dev ; voir nuance prod**) | openclaw/hermes/opencode | S | P0 (self-host) |
| A2 | Streaming token-réel dans `_appel_provider` | les 4 | M | **P0** |
| A3 | Retry 429/5xx avec backoff dans la boucle | openclaw (rotation 429), dsh `retryPolicy` | S | P1 |
| A4 | Protocole par kind (`openai-completions` \| `anthropic-messages`) partagé test/chat | openclaw `api:`, Zen endpoints | M | P1 |
| A5 | Métadonnées de modèles (contexte, prix) depuis `/models` d'OpenRouter | Zen pricing, models.dev | S-M | P1 |
| P1 | Usage tokens persisté + estimation de coût par session | openclaw usage, Zen | S-M | P1 |
| A11 | **Mode découverte sans clé** (essai sponsorisé Philum, transparent, plafonné) | décision produit 2026-08-21 ; gateways étudiées | M | P1-P2 |
| A6 | Capture de `context_length_exceeded` → troncature/compaction auto | openclaw `contextTokens` | M | P2 |
| A7 | Chaîne de fallback ordonnée entre providers du créateur | hermes Fallback, openclaw failover | M | P2 |
| A8 | Onboarding « premier provider » avec parcours gratuits documentés | hermes guides free, openclaw onboard | S | P2 |
| A9 | Marquage « recommandés » dans le sélecteur (curation à la Zen) | Zen | S | P3 |
| A10 | Latence mesurée dans le résultat de test | openclaw Test connection | XS | P3 |
| — | OAuth abonnements (si autorisé fournisseur), rotation multi-clés simple, utility model, registre models.dev | hermes/openclaw/Cherry Studio | variés | arbitrés (voir §4) |

---

## 2. COPIER (presque tel quel)

### A1 — Autoriser le loopback pour les base_url de provider (P0, effort S)
**Constat vérifié** : `url_safety.py:_ip_is_safe` rejette `is_loopback`/`is_private`, et
`_resolve_base_url` applique ce garde à *toute* base_url fournie ⇒ **Ollama
(`http://localhost:11434/v1`), LM Studio (`:1234`), vLLM sont impossibles aujourd'hui**,
même via kind `custom`. Or c'est LA seule offre gratuite illimitée et privée chez les
quatre projets (Ollama y est détecté zéro-config).
**Copie du pattern openclaw** : opt-in explicite et *ciblé* — un flag par provider
(ex. colonne `allow_local: bool`, défaut false) ou règle « loopback toléré uniquement
pour `base_url` de provider, jamais pour le fetch web ». Le garde SSRF de
`fetch_url`/sources reste strict sans exception.
**Fichiers** : `app/core/url_safety.py` (paramètre `allow_loopback=False`),
`app/services/agent_providers.py:_resolve_base_url`, migration légère si colonne.
**Garde-fou** : ne jamais élargir aux plages RFC1918 par défaut ; message d'erreur
explicite quand un utilisateur tente localhost aujourd'hui.
**Nuance prod (arbitrage 2026-08-21, cf. étude Cherry Studio)** : le backend Philum
tourne sur une VM distante — l'Ollama de la machine de l'utilisateur final est
*joignable ni en loopback ni en RFC1918 depuis la VM*, opt-in ou pas. A1 sert donc aux
instances **self-hostées/développement** (backend co-localisé), pas au SaaS. Pour
l'utilisateur final du SaaS, le chemin réaliste « modèles locaux » est le **tunnel HTTPS
public** via kind `custom` (marche dès aujourd'hui) — analyse complète dans
`2026-08-21-cherry-studio-modeles-locaux.md`. Priorité ramenée à « P0 self-host » : le
travail reste petit et utile, mais ne débloque pas l'usage local des créateurs du SaaS.

### A3 — Retry borné sur 429/5xx (P1, effort S)
openclaw ne réessaie **que** sur rate-limit (règle saine : les autres échecs sont
immédiats) ; dsh a un `retryPolicy` par adaptateur. Philum : dans `_executer_tour`,
si HTTP 429 ou 502/503/504 → 1 retry après backoff court (ex. 2 s puis 5 s, lu depuis
`Retry-After` si présent), sinon erreur classifiée existante. Pas de rotation de clés
(§4). **Fichier** : `app/services/agent.py`.

### A8 — Parcours « premiers pas » avec options gratuites honnêtes (P2, effort S)
hermes documente des guides dédiés (« run X free ») ; les tiers gratuits à clé simple
marchent dès aujourd'hui chez Philum : **Gemini AI Studio (tier gratuit), Groq, Cerebras,
OpenRouter (modèles `:free`)**, et NVIDIA NIM via `custom`
(`https://integrate.api.nvidia.com/v1`). Copier l'idée : un encart dans la page Réglages
(#508) listant ces 4-5 options avec « clé gratuite disponible », sans rien proxifier.
**Fichiers** : UI settings + `MODELES_SUGGERES` (préremplir groq/cerebras/openrouter,
vides aujourd'hui).

### A9/A10 — Curation et sonde (P3, effort XS-S)
- Marquer 2-3 modèles « recommandés » par kind dans le sélecteur (la liste vivante
  reste la source) — pattern Zen « tested & verified ».
- Ajouter la latence mesurée au `AgentProviderTestResult` (openclaw affiche latence ;
  une ligne : `monotonic()` autour de l'appel).

## 3. ADAPTER (concept transposé avec modifications)

### A2 — Vrai streaming (P0, effort M)
**Constat vérifié** : `_appel_provider` fait un POST bloquant et rend le message complet ;
les événements `message_delta` SSE sont synthétisés après coup. Les quatre projets
streament nativement. **Adaptation** : `"stream": true` + parsing SSE ligne par ligne
(`choices[].delta.content`, `delta.tool_calls` fragmentés à réassembler),
re-émission `message_delta` au fil de l'eau via la queue asyncio existante de
`endpoints/agent_chat.py`. Attention spécificités : Gemini/OpenAI diffèrent sur les
fragments de tool_calls (le fix #512 `tool_call_id` montre que la tolérance des
providers est faible — bien tester Gemini + Mistral + Cerebras). Repli : si le provider
échoue sur `stream:true`, retomber sur le mode bloquant actuel.

### A4 — Protocole par kind, partagé entre test et chat (P1, effort M)
Aujourd'hui le test Anthropic sait basculer en natif `/v1/messages` mais **pas**
`_appel_provider` (uniquement `url_chat()` OpenAI-compat) : un compte Anthropic qui
refuse la surface compat casse au premier vrai tour, après un test pourtant vert.
Copier la leçon openclaw/Zen : déclarer le protocole par provider
(`api: "openai-completions" | "anthropic-messages"`), un seul adaptateur de
requête/réponse utilisé par `tester()` ET `_appel_provider()` (et plus tard
`lister_modeles`). Gemini reste sur sa surface OpenAI (`/v1beta/openai`), déjà correct.

### A5 — Enrichir le catalogue avec les métadonnées disponibles (P1, effort S-M)
`lister_modeles` garde seulement les `id`. Or **OpenRouter renvoie contexte + prix par
modèle** dans `/models`, et Zen/models.dev montrent la valeur utilisateur de ces
métadonnées (choisir un modèle = arbitrer coût/fenêtre). Adaptation minimale : garder
`{id, context_length?, pricing?}` quand présents, afficher « 128k · $0,15/M » dans le
sélecteur ; stockage souple (JSONB) plutôt que colonnes. Ne rien inventer pour les
providers qui ne servent que des ids.

### P1(usage) — Persister l'usage et estimer le coût (P1, effort S-M)
`_appel_provider` récupère déjà `usage` mais le jette. openclaw rapporte l'usage par
tour ; Zen facture/affiche par requête. Pour un produit BYOK, montrer « cette session :
X tokens ≈ $Y » construit la confiance. Adaptation : colonnes `usage_json` sur
`agent_messages` (ou table dédiée), agrégat par session côté API, estimation € via les
prix d'A5 quand connus (sinon absent, jamais inventé).

### A6 — Gérer `context_length_exceeded` en amont (P2, effort M)
Le code est déjà classifié (#511) mais subi. openclaw porte `contextTokens` par modèle
et borne l'input. Adaptation : à réception de ce code, tronquer l'historique
(`historique_pour_modele` garde déjà une fenêtre ?) et rejouer le tour une fois, avec
événement informatif ; à terme, compaction type rakazo (résumé des vieux tours).

### A7 — Fallback ordonné (P2, effort M)
hermes (Fallback Providers) et openclaw (failover + cooldown) replient sur un second
provider/modèle. Adaptation Philum : liste optionnelle `fallback_provider_id` (un seul
niveau suffit au début) résolue comme `resoudre_defaut` ; déclenchement uniquement sur
erreurs « provider mort » (401/404/429 quota/5xx), jamais sur erreur d'outil. Reporter
si l'usage réel ne le demande pas.

### A11 — Mode découverte « essai sans clé » sponsorisé Philum (P1-P2, effort M)
**Décision produit (échange du 2026-08-21)** : offrir un essai temporaire sans friction
pour tester l'outil avant de brancher sa propre clé — avec transparence totale sur la
solution utilisée, avertissement confidentialité calme et factuel (conséquences réelles
et limitées à ce qui transite dans l'échange Philum), puis conversion vers BYOK/gratuits.
Design proposé :
- **Pseudo-provider serveur `decouverte`** : jamais stocké comme provider du créateur ;
  actif tant que le créateur n'a aucun provider fonctionnel ; quota strict par compte
  (ex. 15 messages/jour + plafond tokens/jour) et garde-fous anti-abus (compte vérifié,
  une session agent à la fois).
- **Routage à coût marginal ~zéro** : comptes Philum sur les **tiers gratuits**
  (Gemini AI Studio, Groq, Cerebras) — vérifier au cas par cas les ToS de chaque tier
  avant prod (certains sont formulés « prototypage/dev ») ; repli payant dérisoire si
  besoin : DeepSeek V4 Flash off-peak (~0,22 $/M tokens input).
- **Transparence** : bannière permanente dans le chat « Mode découverte — vos échanges
  transitent par [fournisseur du jour] » ; réutiliser `DATA_SCOPE_NOTICE` ; mention
  factuelle du régime de rétention du fournisseur (ex. « peut utiliser vos échanges pour
  améliorer son modèle ») sans dramatisation.
- **Conversion** : à épuisement du quota, écran « Connectez votre clé » avec parcours
  gratuits (A8) et BYOK ; le mode découverte reste disponible en file d'attente/journée.
- **Fichiers** : settings (flag + quotas), `agent_chat.py` (résolution pseudo-provider),
  UI bannière + écran de conversion, table quotas + reset quotidien.

---

## 4. ARBITRAGES (mis à jour après discussion produit du 2026-08-21)

| Pattern étudié | Arbitrage |
|---|---|
| **OAuth abonnements** | **À faire, uniquement quand autorisé par le fournisseur.** Officiellement supportés : OpenAI (OAuth Codex/ChatGPT), GitHub Copilot (device flow), GitLab Duo, DigitalOcean. Zone grise → exclu : Anthropic (pas de programme tiers officiel ; Claude Max consommé via OAuth conçu pour Claude Code). Effort L (device flows, refresh token, hétérogénéité) : planifier après A1-A5, provider par provider. |
| **Rotation de clés / credential pools** | **Ni interdit ni complexe — différé sur signal.** Complexité réelle mais modérée (S-M) : N clés chiffrées par provider (table fille ou JSONB), rotation **uniquement sur 429** (règle openclaw : tout autre échec est immédiat), affichage masqué de N clés. La valeur est prouvée chez les grands clients : Cherry Studio embarque « multiple-key rotation » officiellement (« avoid rate-limit issues »), openclaw normalise `<PROVIDER>_API_KEYS`. Elle se matérialise surtout sur les **tiers gratuits très limités** (Groq/Gemini) — donc pertinente *après* A8/A11 qui vont concentrer ce trafic. Déclencheur recommandé : fréquence des 429 constatée en prod > seuil, ou demande utilisateur. |
| **Utility model** | **Pas d'utilité aujourd'hui car aucune tâche annexe facturée.** Définition : appels LLM hors de la conversation principale — générer le titre d'une session (opencode route ça vers Haiku/Nano/Flash ; Philum le fait localement via `titre_depuis_message`), compaction/résumé de l'historique (arrivera avec A6), futur tagging/résumé automatique de sources. Règle sous-jacente : ne pas faire payer le modèle coûteux du créateur pour de la plomberie. À re-décider dès que A6 entre en chantier. |
| **Gateway keyless proxifiée** | **Sort du « ignoré » → devient A11 (§3)** suite décision produit : essai sponsorisé, transparent, plafonné, avec conversion. |
| **Registre externe type models.dev** | **Go, mais en léger et après A5.** Concrètement : models.dev est un registre open-source (équipe opencode/sst) exposant un JSON public décrivant des centaines de modèles — fenêtre de contexte, prix input/output/cache, capacités (tools/vision), classés par fournisseur. Intégration minimale : fetch quotidien côté serveur + cache, enrichissement du sélecteur quand `/models` du fournisseur renvoie des ids nus (cas OpenAI/Groq/Cerebras), matching par famille d'id (`gpt-5*`, `claude-opus-*`…) avec dégradation silencieuse si indisponible ou id inconnu. Ne JAMAIS bloquer un modèle faute de fiche. Si A5 (métadonnées natives OpenRouter) suffit à l'UX, models.dev devient optionnel. |
| **Plugins provider à la openclaw (`registerProvider`)** | Inchangé : notre enum `ProviderKind` + dict de métadonnées joue le même rôle pour 9 kinds ; séparer en plugins quand on dépassera ~15 kinds. |

## 5. Ordre d'attaque suggéré (mis à jour)

1. **A2** (streaming) — plus grosse amélioration perceptible ; banc d'essai providers avec le fix #512 (Gemini).
2. **A3 + A10** (retry + latence) — robustesse à coût dérisoire, même PR possible.
3. **A4** (protocole par kind) — fiabilise Anthropic bout-en-bout.
4. **A5 + usage/coût** — transparence BYOK (coût réel de session).
5. **A11 + A8** (mode découverte + parcours gratuits) — acquisition sans friction, même épopée produit.
6. **A1** (loopback self-host) + page doc « brancher votre Ollama via tunnel » (cf. étude Cherry Studio).
7. **A9** (curation), puis **models.dev** si A5 insuffisant.
8. **A6/A7** — selon usage réel ; A6 réouvre la question utility model.
9. **OAuth** — provider par provider, uniquement ceux qui l'autorisent officiellement.

*Document mis à jour le 2026-08-21 après arbitrage produit ; écrits en lecture seule du dépôt (aucun commit — PR #512 sous le contrôle d'un autre agent).*
