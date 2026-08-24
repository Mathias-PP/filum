# 2026-08-21 — Étude : gestion multi-providers et modèles gratuits dans les grands harness

> **Objet** : étude approfondie de la façon dont quatre projets majeurs de type « harness »
> gèrent le support de **plusieurs fournisseurs de modèles (providers)** et comment ils
> proposent des **modèles gratuits** à leurs utilisateurs. Cible : nourrir les évolutions
> Phase 4+ du harness BYOK Philum (choix de providers, catalogue de modèles, offre « sans clé »).
>
> **Projets étudiés** (docs vérifiées au 2026-08-21) :
>
> - `anomalyco/opencode` — https://opencode.ai/docs/providers, /docs/zen
> - `nousresearch/hermes-agent` — https://hermes-agent.nousresearch.com/docs/integrations/providers
> - `openclaw/openclaw` — https://docs.openclaw.ai/concepts/model-providers
> - `deepseek-ai/deepseek-harness` (dsh) — docs/architecture.md, docs/config-catalog.md

---

## 1. Tableau de synthèse

| Projet           | Surface d'intégration                                   | Catalogue de modèles                           | Auth supportées                                                                                           | Modèles gratuits                                                                                           |
| ---------------- | ------------------------------------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| **opencode**     | Vercel AI SDK (75+ providers) + registre **models.dev** | Dynamique (registry) + Zen curé                | Clé API, OAuth abonnements (Claude Pro/Max, ChatGPT, Copilot, GitLab Duo, DigitalOcean), endpoints custom | Zen : 7 modèles « Free » ; locaux Ollama/LM Studio/llama.cpp ; OpenCode Free (keyless, côté Hermes)        |
| **hermes-agent** | Dossier `providers/`, adaptateurs par provider          | Statique par provider + guides                 | Clé API, OAuth (Nous Portal, Codex, Copilot device-code, Claude Max), OpenRouter, endpoints custom nommés | OpenCode Free (**keyless anonyme**), NVIDIA clé gratuite, HuggingFace 0,10 $/mois offerts, guides « free » |
| **openclaw**     | Plugins `registerProvider(...)` (~30 officiels)         | Publié par chaque plugin                       | Clé API (+ rotation env), OAuth (ChatGPT/Codex, SuperGrok/X Premium, MiniMax, OpenRouter), CLI runtimes   | Locaux (Ollama, LM Studio, vLLM, SGLang, llama.cpp managé) ; Zen/Go comme providers                        |
| **dsh**          | Plugins Cordis, adaptateur sur `ctx.llm`                | Défini dans l'adaptateur (V4 Flash/Pro/Vision) | `apiKeyEnv` par route (DeepSeek ou multi via pi-ai)                                                       | Aucun propre ; prix DeepSeek off-peak                                                                      |

---

## 2. opencode — registre central + passerelle curée (Zen)

### 2.1 Architecture providers

- **75+ providers** via l'écosystème Vercel AI SDK ; le catalogue vivant est le registre externe **models.dev** (métadonnées : contexte, prix, capacités). Le binaire n'embarque pas les modèles, il les découvre.
- Connexion utilisateur : commande `/connect` dans la TUI → la clé est stockée dans `~/.local/share/opencode/auth.json` (jamais dans le projet).
- **Provider custom universel** : tout endpoint compatible OpenAI s'ajoute en config avec le package npm `@ai-sdk/openai-compatible` + `baseURL` + map de modèles. C'est la porte d'entrée pour Ollama, LM Studio, llama.cpp, vLLM (locaux = gratuits, souvent auto-détectés zéro-config sur localhost).
- **OpenRouter** supporté nativement avec options de routage provider.

### 2.2 OAuth « réutilisation d'abonnement »

`/connect` propose des flux OAuth qui réutilisent des abonnements grand public existants :
Claude Pro/Max, ChatGPT Plus/Pro (OAuth Codex), GitHub Copilot (device flow), GitLab Duo, DigitalOcean. L'utilisateur paie déjà son abonnement → coût marginal nul pour lui.

### 2.3 OpenCode Zen — la passerelle curée

- Gateway propriétaire optionnel : liste de modèles **testés/benchmarkés** avec leurs équipes et providers, vendus **au coût** (« no markup », « no lock-in », « pas de downgrade vers un provider moins cher »).
- **Multi-protocole** derrière une seule clé : `/zen/v1/responses` (OpenAI Responses), `/zen/v1/messages` (Anthropic), `/zen/v1/chat/completions` (OpenAI-compatible), `/zen/v1/models/<id>` (Google). Chaque modèle déclare son protocole.
- Fonctions équipe : rôles admin/member, **limites mensuelles** par workspace/membre, auto-reload du solde, contrôle d'accès par modèle (ex. désactiver un modèle qui collecte les données), **BYOK interne** (utiliser ses propres clés OpenAI/Anthropic pour ces modèles, facturés directement par eux).
- Cycle de vie explicite : table de **dépréciation** datée par modèle.

### 2.4 Les modèles gratuits de Zen (7)

`big-pickle`, `x-preview-f-free` (Ox Alpha Free), `mimo-v2.5-free`, `hy3-free`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free`, `muse-spark-1.2-contributor-free` — tous gratuits en input/output/cache-read. Trois mécanismes distincts :

1. **Stealth preview / loss-leader** : modèles « stealth » ou en collecte de feedback, gratuits temporairement (données pouvant servir à l'amélioration du modèle — exception à la zero-retention).
2. **Endpoints d'essai NVIDIA** : usage logged, « trial use only », pas de données confidentielles.
3. **Contributor tier** : tarif très réduit/gratuit **en échange du droit d'entraîner** sur les prompts/completions (Meta).

---

## 3. hermes-agent — le plus grand éventail d'authentifications

- Organisation en **dossier `providers/`**, un adaptateur par fournisseur ; doc unique très dense.
- **Abonnements via OAuth** : Nous Portal (JWT `inference:invoke` auto-rotatifs), OpenAI Codex OAuth, GitHub Copilot (device code), Anthropic OAuth (Claude Max ; Claude Pro explicitement non supporté).
- **Agrégateurs** : OpenRouter (une clé → centaines de modèles), blockrun/free (« Free models only »).
- **Gratuité par crédits** : HuggingFace (crédit gratuit ~0,10 $/mois), NVIDIA build.nvidia.com (clé gratuite).
- **`opencode-free`** : provider **keyless** (alias `free`) — requêtes anonymes sans aucune clé, idéal pour essayer l'outil sans friction.
- **Endpoints custom** : endpoint ad-hoc OpenAI-compatible (Ollama local détecté zéro-config) **ou** providers custom nommés via dict `providers:` dans config.yaml.
- **Résilience** : chaînes **Fallback Providers** (ordre de repli entre providers/modèles) et **Credential Pools** (plusieurs clés pour un même provider).
- Guides dédiés type « run-nemotron-3-ultra-free » : le gratuit est un parcours documenté, pas un cache-misère.

## 4. openclaw — providers = plugins, tout le reste est générique

- Séparation stricte : OpenClaw garde la **boucle d'inférence générique** ; chaque provider est un **plugin** (`registerProvider(...)`) qui possède onboarding, catalogue, mapping env-var, normalisation transport, classification de failover, refresh OAuth, usage, profils de reasoning.
- Références de modèles `provider/model` ; config centrale : `agents.defaults.model.primary` + **fallbacks ordonnés** + **utility model** (modèle bon marché pour les tâches utilitaires comme les titres de session — opencode fait pareil avec Haiku/Nano/Flash).
- **Rotation de clés normalisée** : `<PROVIDER>_API_KEYS` (liste), `_API_KEY_1..n`, override live `OPENCLAW_LIVE_<PROVIDER>_KEY` ; rotation **uniquement sur rate-limit (429)**, échec immédiat sinon.
- ~30 plugins officiels : OpenAI (défaut `gpt-5.6-sol`), Anthropic, ChatGPT/Codex OAuth, Google (clé AI Studio / Vertex ADC / runtime Gemini CLI), Z.AI, MiniMax/Qwen/Volcengine/BytePlus (**coding plans** avec OAuth), xAI (SuperGrok/X Premium OAuth), OpenRouter (OAuth ou clé), HuggingFace, NVIDIA, Groq, Cerebras, DeepInfra, Together, Novita, Ollama Cloud, Vercel AI Gateway, ClawRouter, Chutes, Venice… et **OpenCode Zen (`opencode`) + Go (`opencode-go`) comme providers de première classe** — preuve que les gateways curées deviennent une brique standard de l'écosystème.
- **Providers custom** via `models.providers.<id>` : `{baseUrl, apiKey, api: "openai-completions"|"anthropic-messages", models[], timeoutSeconds}` + bloc `compat` de capacités déclarées (images, developer role…). Règles de façonnage proxy : suppression du role `developer`, des beta headers Anthropic et des headers d'attribution sur les routes non natives.
- **Runtimes locaux gratuits** en plugins bundle : llama.cpp (serveur managé qui installe/supervise llama-server + GGUF), LM Studio (API native découverte/auto-load), Ollama, vLLM, SGLang.
- UI : Settings → Model Providers avec bouton **Test connection** (sonde réelle catégorisant auth/quota/billing/timeout) ; garde-fous réseau (`allowPrivateNetwork`, trust d'origine exacte pour LAN/tailnet).

## 5. dsh (deepseek-harness) — minimalisme plugin

- Tout est plugin Cordis ; l'adaptateur LLM s'enregistre sur `ctx.llm`. Composition par couches : bundles de profil → `cordis.patch.yml` → patch home → `--patch`.
- Config utilisateur : deux YAML hot-watchés sous `~/.dsh` : `settings.yaml` et `.credentials.yaml` ; modèle par défaut = entrée `{provider, model}`.
- Deux adaptateurs livrés : `dsh-llm-deepseek` (clé via `DEEPSEEK_API_KEY`, `baseURL` overridable, `retryPolicy`, catalogue V4 Flash/Pro/Vision Exp) et `dsh-llm-pi-ai` — routeur **multi-provider** bâti sur `@earendil-works/pi-ai` (dict `providers:` avec `apiKeyEnv` par route). Pas d'offre gratuite propre ; DeepSeek joue lui-même l'argument prix (off-peak).

---

## 6. Patterns transverses (ce que les 4 projets partagent)

1. **L'OpenAI-compatible est la lingua franca.** Un seul chemin de requête chat-completions suffit ; tout provider exotique se ramène à `baseUrl + clé`. Deuxième protocole utile : `anthropic-messages` ; l'API Responses OpenAI émerge (Zen, openclaw).
2. **Catalogue dynamique > catalogue codé en dur.** Registre externe (models.dev), `/v1/models` distant (Zen), catalogue publié par plugin (openclaw), ou discovery locale (LM Studio/Ollama). Personne ne hardcode sa liste complète ; en revanche tous proposent une **liste courte recommandée/curée**.
3. **Échelle d'authentification complète** : clé API → OAuth d'abonnement grand public (réutilise ce que l'utilisateur paie déjà) → gateway keyless → runtime local. Plus un harness monte cette échelle, plus l'onboarding est frictionless.
4. **Le gratuit existe sous 5 formes** : (a) stealth/preview gratuits temporaires, (b) crédits d'essai (HF, NVIDIA), (c) contributor tier (données contre tokens), (d) gateway keyless anonyme, (e) **runtimes locaux** (seule forme vraiment illimitée et privée). Caveat constant : les modèles gratuits ont presque toujours un caveat de confidentialité/logging.
5. **Résilience** : fallback chains ordonnées (hermes, openclaw), rotation de clés limitée aux 429 (openclaw), credential pools (hermes), retryPolicy (dsh). Le « utility model » bon marché pour tâches auxiliaires est un pattern récurrent.
6. **Sécurité** : SSRF/private-network opt-in pour les baseUrl custom (openclaw), headers d'attribution uniquement sur routes natives, stockage credentials hors du repo/projet.

## 7. Recommandations pour Philum (Phase 4+, non engagées)

1. **Ne rien changer maintenant** : notre surface unique `url_chat()` (OpenAI-compatible) est exactement le consensus des 4 projets. Les kinds `openai`/`anthropic`/`custom` actuels couvrent le besoin.
2. **Ajouter le kind `openrouter`** (une clé → centaines de modèles) : meilleur ratio effort/valeur pour le BYOK ; c'est le seul agrégateur présent chez les 4.
3. **Ajouter la détection locale Ollama** (`http://localhost:11434`, zéro clé) : seule offre « gratuite » honnête, privée et illimitée ; trivial via kind `custom` + préremplissage.
4. **Offre « sans clé » pour démo** : plutôt que proxifier soi-même, documenter/route vers une gateway keyless existante (type `opencode-free`) avec avertissement confidentialité — évite d'assurer coûts/abus côté Philum.
5. **Catalogue** : interroger `{baseUrl}/v1/models` pour peupler le sélecteur (avec liste courte statique recommandée), plutôt qu'un enum codé en dur.
6. **Différer** : rotation de clés, credential pools, fallback chains — utiles seulement à l'échelle ; garder un simple retry (déjà en place) et un plafond de tours/tokens (fait).
