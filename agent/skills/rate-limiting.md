# Skill: Rate limiting

> Quand l'utiliser : ajouter du rate limiting à un endpoint public sensible (extracteur, publish, login, archivage).

## Contexte

`slowapi` est déjà dépendance du projet mais **pas branché**. Sans rate limit, l'extracteur public (`GET /sources/extract`) est un vecteur DoS et de coût Wayback/Crossref non maîtrisé. Bloquant pour ouverture publique (jalon M3).

## Checklist d'exécution

### Setup global (à faire une fois)

1. Dans `apps/backend/app/main.py`, importer et configurer `slowapi` :
   ```python
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   from slowapi.errors import RateLimitExceeded
   from slowapi.middleware import SlowAPIMiddleware

   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
   app.add_middleware(SlowAPIMiddleware)
   ```
2. Importer `limiter` dans les endpoints qui en ont besoin.

### Application par endpoint

| Endpoint | Limite proposée | Clé |
|---|---|---|
| `GET /sources/extract` | 10/min | IP |
| `POST /cards` | 20/h | user_id (authentifié) |
| `POST /cards/{id}/publish` | 10/h | user_id |
| `GET /auth/google/login` | 30/min | IP |
| `POST /auth/logout` | 60/min | IP |

Pattern par endpoint :
```python
@router.get("/extract")
@limiter.limit("10/minute")
async def extract(request: Request, url: HttpUrl):
    ...
```

⚠️ `request: Request` **obligatoire** dans la signature même si non utilisé — sinon `slowapi` ne peut pas lire l'IP.

### Tests

- Spam un endpoint en local : `for i in {1..15}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/sources/extract?url=...; done` → doit voir des `429` après la limite.
- Test pytest avec `TestClient` : envoyer N+1 requêtes, vérifier que la dernière est 429.

### Comportement attendu côté frontend

- Recevoir 429 = afficher un message « trop de requêtes, réessayez dans X secondes » sans crasher.
- Pour l'extracteur : silent fail si 429, l'utilisateur saisit manuellement.

## Pièges spécifiques

- **Oublier `request: Request`** dans la signature → `slowapi` ne fonctionne pas, pas d'erreur explicite.
- **Rate limit en clé `IP` derrière un proxy** : Railway/Vercel mettent l'IP réelle dans `X-Forwarded-For`. `get_remote_address` la lit déjà, mais à vérifier en prod.
- **Rate limit trop agressif** : casse la démo. Tester avec un compte normal avant de mettre en prod.
- **Pas de rate limit sur le login** : permet le brute force. Mais sur OAuth (pas de password), c'est moins critique. Garder une limite raisonnable pour ne pas griller les quotas Google.
- **Storage par défaut = mémoire** : reset au redéploiement Railway. Acceptable en MVP. Pour persister : Redis (overkill pour MVP).

## Fichiers à connaître

- `apps/backend/pyproject.toml` — `slowapi` déjà listée
- `apps/backend/app/main.py` — point de configuration
- `apps/backend/app/api/v1/endpoints/sources.py` — extracteur à protéger en premier
- `apps/backend/app/api/v1/endpoints/cards.py` — publish

## Pour aller plus loin

- Doc slowapi : https://slowapi.readthedocs.io/
- Jalon M3 dans [`../../.docs/10-mvp-completion-plan.md`](../../.docs/10-mvp-completion-plan.md)
