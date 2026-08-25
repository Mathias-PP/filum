# 05-01 — Providers (BYOK, chiffrement, cache, test clé)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_providers.py` (608 l., 21 symboles).

## Rôle

CRUD complet des providers BYOK : création, lecture, mise à jour, suppression, test de clé, liste de modèles (cache 15 min). Chiffrement des clés en AES-GCM via Fernet. Validation des URLs contre SSRF. Gestion de 5 formes de réponse testées en production.

## Architecture

- `AgentProviderCreate` / `AgentProviderUpdate` : modèles Pydantic pour la création et la mise à jour.
- `AgentProviderFull` : modèle interne complet (clé déchiffrée, metadata DeepSeek,(LLM provider override).
- `_PROVIDER_DEFAULT_BASE_URLS` : dict de confiance des URLs par défaut (11 fournisseurs).
- `_detail_provider` : normalise les réponses de test en 5 formes (OpenAI, Gemini, Mistral, Cerebras, HTML brut).

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `ProviderCrudError` | 11 | Exception métier CRUD |
| `AgentProviderCreate` | 18 | Modèle création |
| `AgentProviderUpdate` | 44 | Modèle mise à jour |
| `AgentProviderFull` | 73 | Modèle interne complet |
| `ProviderModelEntry` | 109 | Entrée modèle |
| `ProviderModelsResult` | 114 | Résultat cache modèles |
| `AgentProviderTestResult` | 122 | Résultat test clé |
| `_chiffrer_cle` | 138 | Chiffrement AES-GCM |
| `_dechiffrer_cle` | 148 | Déchiffrement AES-GCM |
| `_resolve_base_url` | 163 | Résolution URL avec SSRF |
| `lister_providers` | 195 | Listage par workspace |
| `creer_provider` | 234 | Création avec doublon |
| `modifier_provider` | 297 | Mise à jour partielle |
| `supprimer_provider` | 313 | Suppression |
| `test_provider` | 332 | Test clé (5 formes) |
| `models` | 377 | Cache 15 min |
| `_detail_provider` | 391 | Normalisation réponse |
| `_PROVIDER_DEFAULT_BASE_URLS` | 15 | Dict 11 fournisseurs |
| `_MODELES_TTL_SECS` | 52 | TTL cache (900 s) |
| `_CACHE_MODABLES` | 53 | Cache mémoire process |

## Flux typique (création → usage)

1. `creer_provider` → chiffre la clé → insère dans `provider_definitions` → vide le cache modèles.
2. `models` → consulte le cache → si périmé : recharge via clé déchiffrée → met à jour le cache.
3. `test_provider` → déchiffre → appelle le LLM → retourne `AgentProviderTestResult`.

## Dettes et pièges

- `_maintenant()` (`apps/backend/app/services/agent_gratuit.py:49`) : UTC sans timezone, nécessaire pour les colonnes `TIMESTAMP WITHOUT TIME ZONE` de Postgres.
- `_resolve_base_url` appelle `assert_url_is_safe` pour les URLs utilisateur ; les défauts intégrés sont des constantes de confiance (`apps/backend/app/services/agent_providers.py:163`).
- Le cache modèles est en mémoire process, pas partagé entre workers — acceptable car les modèles changent rarement.
- `_detail_provider` gère 5 formes de réponse testées en prod (OpenAI, Gemini, Mistral, Cerebras, HTML brut) — ajouter une 6ème forme est risqué sans test en prod.
- `tester()` ne lève jamais : retourne un `AgentProviderTestResult` classifiable. Sur succès, chauffe le cache avec `refresh=True`.
