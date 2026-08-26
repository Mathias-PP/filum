# Providers BYOK — CRUD, test, modèles, souveraineté (`agent_providers.py`)

## apps/backend/app/api/v1/endpoints/agent_providers.py
Lu intégralement : oui (189/189 lignes) · sha256: b4c0de66d954 · date: 2026-08-25

### Routes (7)

| Méthode | Route | Fonction | Rate-limit | Description |
|---|---|---|---|---|
| `GET` | `/agent/providers/meta` | `provider_meta` | non | Notice souveraineté (pays, périmètre données) + modèles recommandés |
| `GET` | `/agent/providers` | `lister_mes_providers` | non | Providers du créateur (clé masquée) |
| `POST` | `/agent/providers` | `creer_provider` | oui | Ajoute un provider (clé chiffrée en base) |
| `PATCH` | `/agent/providers/{provider_id}` | `mettre_a_jour_provider` | oui | Modifie un provider |
| `DELETE` | `/agent/providers/{provider_id}` | `supprimer_provider` | oui | Supprime un provider |
| `POST` | `/agent/providers/{provider_id}/test` | `tester_provider` | oui | Teste la clé (body optionnel `model` pour test ciblé) |
| `GET` | `/agent/providers/{provider_id}/models` | `lister_modeles_provider` | oui | Modèles disponibles (cache 15 min, `?refresh=true`) |

### Symboles (2)

- `get_http_client` — `apps/backend/app/api/v1/endpoints/agent_providers.py:46` — transport httpx injectable (MockTransport en tests), réseau par défaut. Injecté comme Dependency dans chat et test.
- `TestProviderBody` — `apps/backend/app/api/v1/endpoints/agent_providers.py:130` — corps optionnel pour le test : `model` permet de vérifier un couple clé+modèle spécifique (override de session).

### Pièges

- La clé n'est **jamais rendue en clair** après création : le service masque la valeur avant le retour.
- `lister_modeles_provider` interroge le fournisseur avec un cache serveur 15 min. `?refresh=true` force le rappel réseau (utile après activation d'un nouveau plan).
- `provider_meta` (`apps/backend/app/api/v1/endpoints/agent_providers.py:51`) est le seul endpoint sans auth implicite dans le router providers (pas de rate-limit non plus) : il rend la notice de souveraineté et les modèles recommandés de manière publique.
