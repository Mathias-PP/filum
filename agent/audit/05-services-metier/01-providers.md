# 05-01 — Providers (BYOK, chiffrement, cache, test clé)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_providers.py` (608 l., 21 symboles).
> sha256: 3f40d049cd9e7213841069810a488fd00543f0fea83dba210a3161ecc50bfd08

## Rôle

CRUD complet des providers BYOK : création, lecture, mise à jour, suppression, test de clé, liste de modèles (cache 15 min). Chiffrement des clés en AES-GCM via Fernet. Validation des URLs contre SSRF. 5 formes de réponse testées en production.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `AgentProviderError` | `apps/backend/app/services/agent_providers.py:68` | Erreur métier : payload invalide, doublon |
| `AgentProviderNotFoundError` | `apps/backend/app/services/agent_providers.py:72` | Provider introuvable ou pas au bon créateur |
| `_invalider_cache_modeles` | `apps/backend/app/services/agent_providers.py:56` | Retire les entrées cache d'un provider (tous créateurs) |
| `_invalider_cache_modeles_tout` | `apps/backend/app/services/agent_providers.py:63` | Vide tout le cache (tests) |
| `_key_manager` | `apps/backend/app/services/agent_providers.py:137` | Instancie `KeyManager` avec la clé de chiffrement |
| `_decrypt` | `apps/backend/app/services/agent_providers.py:141` | Déchiffre une clé API chiffrée |
| `_to_read` | `apps/backend/app/services/agent_providers.py:145` | Convertit `AgentProvider` en `AgentProviderRead` |
| `_resolve_base_url` | `apps/backend/app/services/agent_providers.py:159` | Assainit la base_url (SSRF) et rend l'URL à enregistrer |
| `_get_owned` | `apps/backend/app/services/agent_providers.py:179` | Rend un provider owned par le créateur, lève `NotFound` |
| `_clear_default` | `apps/backend/app/services/agent_providers.py:196` | Efface les marques is_default existantes |
| `lister` | `apps/backend/app/services/agent_providers.py:208` | Listage par créateur |
| `creer` | `apps/backend/app/services/agent_providers.py:217` | Création avec chiffrement, doublon, cache |
| `mettre_a_jour` | `apps/backend/app/services/agent_providers.py:250` | Mise à jour partielle avec invalidation cache |
| `supprimer` | `apps/backend/app/services/agent_providers.py:294` | Suppression avec invalidation cache |
| `obtenir_pour_chat` | `apps/backend/app/services/agent_providers.py:305` | Provider spécifique pour le chat |
| `resoudre_defaut` | `apps/backend/app/services/agent_providers.py:318` | Provider par défaut du créateur |
| `tester` | `apps/backend/app/services/agent_providers.py:332` | Appel minimal (1 token, ping) — ne lève jamais |
| `_detail_provider` | `apps/backend/app/services/agent_providers.py:391` | Texte exact renvoyé par le fournisseur (5 formes) |
| `_extraire_code_erreur` | `apps/backend/app/services/agent_providers.py:463` | Code d'erreur normalisé depuis le corps HTTP |
| `_classify` | `apps/backend/app/services/agent_providers.py:488` | Cadrage lisible d'un test de clé (code > HTTP > brut) |
| `lister_modeles` | `apps/backend/app/services/agent_providers.py:526` | Modèles auxquels ce compte a droit, avec cache TTL 15 min |

## Invariants

- `_MODELES_TTL_SECS = 15 * 60` (`apps/backend/app/services/agent_providers.py:52`) : TTL cache modèles en mémoire process.
- `_modeles_cache` (`apps/backend/app/services/agent_providers.py:53`) : `(creator_id, provider_id) -> (resultat, expiration)`.
- `_TIMEOUT = 20.0` (`apps/backend/app/services/agent_providers.py:43`) : timeout HTTP pour les appels fournisseur.
- `_CADRAGES` (`apps/backend/app/services/agent_providers.py:438`) : 5 codes HTTP mappés (400, 401, 403, 404, 429).
- `_CADRAGES_CODE` (`apps/backend/app/services/agent_providers.py:450`) : 9 codes d'erreur normalisés par les fournisseurs.
- `_detail_provider()` (`apps/backend/app/services/agent_providers.py:391`) : 5 formes de réponse testées en prod (OpenAI, Gemini, Mistral, Cerebras, HTML brut).
- `tester()` (`apps/backend/app/services/agent_providers.py:332`) : ne lève jamais — retourne un `AgentProviderTestResult` classifiable.
- `lister_modeles()` (`apps/backend/app/services/agent_providers.py:526`) : seuls les résultats `source == "provider"` sont mis en cache.

## Dettes

- `_resolve_base_url()` (`apps/backend/app/services/agent_providers.py:159`) : les défauts intégrés (`PROVIDER_DEFAULT_BASE_URLS`) sont des constantes de confiance — ne pas modifier sans revue SSRF.
- `_detail_provider()` (`apps/backend/app/services/agent_providers.py:391`) : ne lève jamais — un test de clé qui plante en lisant un corps d'erreur ne diagnostique plus rien.
- `_clear_default()` (`apps/backend/app/services/agent_providers.py:196`) : itère tous les providers du créateur — O(n) acceptable car n est petit.
