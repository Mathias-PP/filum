# 17 — Stratégie LLM : cascade de free tiers routée par tâche

> Décision du 2026-07-16. Objectif : couvrir tous les besoins IA du MVP (extraction de
> métadonnées, recherche web, validation Wayback, construction du graphe, signaux de
> véracité) pour **0 €/mois**, sans dépendre d'un fournisseur unique, avec une politique
> de sensibilité des données par tâche. Toutes les limites de free tier ci-dessous ont
> été vérifiées le 16/07/2026 (elles bougent vite : re-vérifier avant toute implémentation).

---

## 1. Principes

1. **Un seul point d'entrée dans le code Philum.** Le backend parle à un endpoint
   OpenAI-compatible unique (LiteLLM self-hosted). Aucun SDK propriétaire dans
   `app/services/`. Le choix du modèle est de la **configuration**, pas du code.
2. **Routage par tâche, pas par modèle.** Chaque appel déclare un alias logique
   (`metadata-extract`, `web-search`, `wayback-match`, `graph-build`, `fact-signals`).
   LiteLLM mappe l'alias vers une cascade de modèles avec fallback automatique.
3. **Politique de sensibilité.** Les tâches ne manipulant que du contenu web public
   peuvent utiliser n'importe quel provider (y compris Zhipu direct). Les tâches
   touchant des données créateur (emails, analytics, claims) sont restreintes aux
   providers EU/US. La frontière est déclarée dans la config du routeur, pas laissée
   au bon vouloir du code appelant.
4. **La fiabilité vient de la contrainte, pas du modèle.** Constat des benchmarks 2026
   (Structured Output Benchmark, LLMStructBench) : la taille du modèle ne prédit pas
   la qualité d'extraction structurée (Phi-4 14B > GPT-5 en value accuracy). Ce qui
   compte : mode structured output natif (<2 % d'erreur) + validation Pydantic +
   retry. Jamais de « prompt JSON » nu (10-20 % d'erreur).
5. **Le LLM propose, la crypto dispose.** Aucune sortie LLM n'entre dans un payload
   signé (ADR-019) sans validation. Les métadonnées extraites sont éditables par le
   créateur avant attestation. Philum n'affiche jamais un verdict « vrai/faux » généré.

---

## 2. Free tiers vérifiés (2026-07-16)

| Provider | Modèles utiles | Limites free tier | Pièges connus |
|---|---|---|---|
| **Google AI Studio** | Gemini 3 Flash | 1 500 req/j, 10 RPM, sans CB | ⚠️ Activer le billing sur le projet GCP **supprime silencieusement** le free tier. Reset quota à minuit heure Pacifique. |
| | Gemini 2.5 Pro | 50 req/j, 5 RPM | Réservé au rôle « juge » (fact-signals). |
| **Mistral La Plateforme** | Mistral Small 3, Mistral Large, Codestral | ~1 Md tokens/mois, tous modèles | Tier « Experiment » : officiellement évaluation, pas production. Limites exactes dans Admin Console → Limits (plus publiées). Hébergé EU 🇪🇺. |
| **Groq** | Llama 3.3 70B, etc. | 30 RPM, 1 000–14 400 req/j selon modèle, sans CB | Limites au niveau organisation. Developer tier (ajout CB, 0 €) = 10× les limites. |
| **Cerebras** | Llama 3.3, Qwen3 32B/235B | 1 M tokens/j, 30 RPM, sans CB | ⚠️ **Contexte plafonné à 8 192 tokens** sur le free tier → inutilisable pour du HTML long, OK pour comparaisons courtes. |
| **OpenRouter** | 23+ modèles `:free` dont GLM-5.2 | 20 RPM ; 50 req/j → **1 000 req/j à vie** après un achat unique de 10 $ | Les 10 $ n'expirent jamais. Le 20 RPM ne se débloque pas. |
| **Zhipu (z.ai)** | GLM-4.7-Flash, GLM-4.5-Flash | Gratuits (input + output) sur l'API officielle | Provider chinois : réservé aux tâches « public only ». GLM-5.2 lui-même est open-weight MIT et servi par des hébergeurs US/EU via OpenRouter. |

**Dimensionnement MVP** : ~5 000 extractions/mois ≈ 3,5 M tokens. Chaque tier ci-dessus
suffit **seul**. La cascade sert la résilience (quota épuisé, panne, modèle retiré),
pas le volume.

---

## 3. Les cinq tâches et leurs cascades

### 3.1 `metadata-extract` — URL → titre / auteur / date / DOI / type

- **Entrée** : HTML nettoyé (readability) + schéma Pydantic. Données publiques.
- **Sensibilité** : aucune → tous providers autorisés.
- **Cascade** : Gemini 3 Flash → Mistral Small 3 → GLM-4.7-Flash (Zhipu).
- **Contraintes** : structured output natif obligatoire ; tronquer le HTML à ~30 k
  tokens (le titre/auteur est presque toujours dans le premier tiers) ; Cerebras exclu
  (8 k de contexte).
- **Bottleneck attendu** : les 10 RPM de Gemini. Mitigation : file d'attente côté
  backend (l'extraction n'est pas synchrone avec la requête HTTP utilisateur — job
  asyncio + statut `pending` sur la source, pattern déjà utilisé pour Wayback).

### 3.2 `web-search` — retrouver auteurs / créateurs / contenus

- **Entrée** : nom ou URL partielle. Données publiques.
- **Cascade** : Gemini 3 Flash **avec Google Search grounding natif** (seul free tier
  avec recherche web intégrée) → fallback : API de recherche dédiée (Exa/Tavily,
  free tiers limités) + n'importe quel modèle pour synthétiser.
- **Règle** : préférer « API de recherche + LLM synthétiseur » à « LLM qui cherche » —
  plus déterministe, plus traçable (on garde les URLs des résultats bruts).
- **Bottleneck** : le grounding consomme le même quota 1 500 req/j que 3.1. Si les
  deux tâches montent en volume, dédier une clé/projet Google par tâche (limites par
  projet, pas par compte).

### 3.3 `wayback-match` — snapshot fonctionnel et correspondant

- **D'abord du code, pas du LLM** : l'API CDX de Wayback fournit snapshots + status
  codes ; un hash/score de similarité (trafilatura + rapidfuzz ou simhash) valide la
  correspondance dans 90 %+ des cas sans aucun appel LLM.
- **Le LLM n'intervient qu'en zone grise** (similarité 0,5–0,9) : « ce snapshot
  correspond-il au contenu attendu ? » — comparaison de deux extraits courts.
- **Cascade** : Llama 3.3 70B via Groq → Cerebras (ici 8 k tokens suffisent) →
  Mistral Small 3.
- **Bottleneck** : le rate limit de **Wayback lui-même** (~15 req/min sur CDX),
  pas le LLM. La queue durable F5 (audit 13) reste le vrai chantier.

### 3.4 `graph-build` — classification taxonomie + liens entre sources

- **Entrée** : métadonnées déjà extraites (3.1). Classification 3 axes ADR-020
  (`format`/`category`/`author_kind`) + suggestions de liens.
- **Sensibilité** : contenu de fiche pré-publication → **EU/US uniquement** (une fiche
  brouillon n'est pas publique).
- **Cascade** : Mistral Small 3 (function calling + enums stricts) → Gemini 3 Flash →
  Qwen3 32B via Cerebras (entrées courtes, OK).
- **Contraintes** : les trois axes sont des enums fermés → le structured output ne
  peut physiquement pas sortir une valeur hors taxonomie. Validation Pydantic +
  1 retry avec le message d'erreur en contexte, puis fallback `unknown` + flag UI.
- **Bottleneck** : la cohérence inter-sources d'une même fiche (deux sources du même
  auteur classées différemment). Mitigation : classifier la fiche en un seul appel
  batch (toutes les sources dans le prompt), pas source par source.

### 3.5 `fact-signals` — signaux de véracité (jamais un verdict)

- **Sortie produit** : des signaux (concordance entre sources, présence peer-review,
  cohérence des dates), jamais « vrai/faux ». Le bandeau de stats reste factuel.
- **Sensibilité** : la plus haute (réputation du créateur en jeu) → **EU/US
  uniquement, jamais Zhipu direct**.
- **Architecture** : multi-modèles avec vote — les benchmarks 2026 montrent qu'interroger
  plusieurs modèles bat n'importe quel modèle seul (~+8 %, framework UAF). Taux
  d'hallucination 2026 : 15–52 % selon modèles ; aucun modèle seul n'est fiable.
- **Cascade/panel** : Gemini 3 Flash + GLM-5.2 (via hébergeur US/EU sur OpenRouter) +
  Mistral Large. Accord 3/3 = signal fort ; désaccord = pas de signal affiché.
  Gemini 2.5 Pro (50 req/j) en juge de départage si besoin.
- **Statut** : post-MVP. À n'activer qu'avec l'instrumentation du moment défensif
  (doc 16, priorité 1) pour mesurer si le signal est consulté.

---

## 4. Implémentation technique

### 4.1 Topologie

```
Backend FastAPI ──(OpenAI SDK, base_url=http://localhost:4000)──▶ LiteLLM proxy
                                                                     │ config.yaml
                                       ┌──────────────┬──────────────┼──────────────┐
                                       ▼              ▼              ▼              ▼
                                  Google AI      Mistral API      Groq         OpenRouter
                                  (Gemini)       (EU)             Cerebras     (GLM-5.2, :free)
                                                                               Zhipu (flash, public only)
```

LiteLLM tourne **sur la même VM que l'API** (container Docker à côté d'uvicorn,
~150-200 MB RAM). Pas de réseau supplémentaire, pas de coût.

### 4.2 Config LiteLLM (squelette)

```yaml
# infra/litellm/config.yaml
model_list:
  # --- metadata-extract (public : tous providers) ---
  - model_name: metadata-extract
    litellm_params: { model: gemini/gemini-3-flash, api_key: os.environ/gemini_api_key }
  - model_name: metadata-extract
    litellm_params: { model: mistral/mistral-small-latest, api_key: os.environ/mistral_api_key }
  - model_name: metadata-extract
    litellm_params: { model: openai/glm-4.7-flash, api_base: https://api.z.ai/v1, api_key: os.environ/zhipu_api_key }

  # --- graph-build (EU/US uniquement) ---
  - model_name: graph-build
    litellm_params: { model: mistral/mistral-small-latest, api_key: os.environ/mistral_api_key }
  - model_name: graph-build
    litellm_params: { model: gemini/gemini-3-flash, api_key: os.environ/gemini_api_key }

  # ... web-search, wayback-match, fact-signals sur le même modèle

router_settings:
  routing_strategy: simple-shuffle    # les entrées de même model_name = pool fallback
  num_retries: 2
  timeout: 45
  fallbacks:
    - { metadata-extract: [] }        # fallback intra-pool automatique
litellm_settings:
  drop_params: true                   # tolère les params non supportés par un provider
```

Le côté appelant ne connaît que l'alias :

```python
# app/services/llm.py — l'UNIQUE point de contact LLM du backend
from openai import AsyncOpenAI
client = AsyncOpenAI(base_url=settings.litellm_base_url, api_key=settings.litellm_master_key)

async def extract_metadata(html: str) -> SourceMetadata:
    resp = await client.chat.completions.create(
        model="metadata-extract",
        messages=[...],
        response_format={"type": "json_schema", "json_schema": SourceMetadata.model_json_schema()},
    )
    return SourceMetadata.model_validate_json(resp.choices[0].message.content)
```

### 4.3 Variables d'environnement (lowercase, ADR-010)

```
litellm_base_url, litellm_master_key,
gemini_api_key, mistral_api_key, groq_api_key,
cerebras_api_key, openrouter_api_key, zhipu_api_key
```

### 4.4 Gestion des quotas et backpressure

- **Jamais d'appel LLM dans le chemin synchrone d'une requête HTTP.** Job asynchrone +
  statut `pending/extracted/failed` sur la source (même pattern que Wayback).
- LiteLLM gère les 429 par fallback vers le provider suivant du pool. Si tout le pool
  est épuisé : la source reste `pending`, retry par le worker (backoff), jamais
  d'erreur utilisateur.
- Budgets LiteLLM (`max_budget` par clé virtuelle) = garde-fou si un tier gratuit se
  met à facturer (le piège Gemini/billing).
- Métrique à logger dès le jour 1 : `provider_used`, `latency`, `fallback_depth` par
  tâche — c'est ce qui dira quand un tier sature réellement.

---

## 5. Bottlenecks anticipés et seuils de bascule

| Bottleneck | Seuil | Réponse |
|---|---|---|
| 10 RPM Gemini (extract + search sur le même quota) | Pics de seed & claim (batch de fiches) | Clés/projets Google séparés par tâche ; lisser via la queue. |
| Contexte 8 k Cerebras | Structurel | Cerebras cantonné aux tâches à entrées courtes (3.3, 3.4). |
| Free tier Mistral « pas pour la production » | Croissance ou clarification CGU | Basculer Mistral en payant en premier (~0,2 $/M input Small) : le plus aligné souveraineté EU, coût trivial au volume Philum. |
| Un tier gratuit disparaît / se dégrade (cf. Big Pickle : stealth temporaire) | Événement externe | C'est la raison d'être de la cascade : retirer une ligne de config, zéro code. |
| Volume > ~50 k extractions/mois | Traction réelle | À ce stade il y a des revenus (doc 16) ; passer les tâches critiques en payant, garder la cascade gratuite en fallback inversé. |
| RGPD / données créateur dans les prompts | Dès la vague 1 (analytics premium) | La frontière de sensibilité (§1.3) est déjà dans la config ; ajouter la redaction PII (Portkey open-source Apache 2.0 depuis mars 2026, ou middleware LiteLLM) avant d'envoyer toute donnée non publique. |

## 6. Ce qu'on ne fait PAS

- Pas de SDK provider-spécifique dans le backend (tout passe par l'alias LiteLLM).
- Pas de fine-tuning, pas de self-hosting de modèle (une VM 1-12 GB ne le permet pas
  et le besoin n'existe pas).
- Pas de verdict de vérité généré par LLM affiché à l'utilisateur.
- Pas de données créateur (emails, claims, analytics, brouillons) vers Zhipu direct.
- Pas d'appel LLM synchrone dans une route HTTP.
