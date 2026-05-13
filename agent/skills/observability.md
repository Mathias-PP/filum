# Skill: Observabilité

> Quand l'utiliser : ajouter ou améliorer logs, monitoring, gestion d'erreurs runtime, sondes.

## Contexte

MVP minimaliste : logs Railway/Vercel uniquement, pas de Sentry ni Plausible (payants au-delà du tier gratuit). L'agent doit améliorer la visibilité sans ajouter de dépendance externe payante.

## État actuel

- ✅ `/health` et `/health/database` opérationnels
- ⚠️ Logs Railway = logs Python stdout, peu structurés
- ❌ Pas de Sentry → erreurs frontend invisibles
- ❌ Pas de monitoring uptime tiers
- ❌ Pas de tableau de bord centralisé

## Checklist d'exécution

### Améliorer les logs backend (sans dep externe)

1. Si `structlog` n'est pas déjà branché, l'ajouter (cf. `.docs/02-tech-architecture.md` qui le mentionne).
2. Configurer un logger structuré JSON pour la prod :
   ```python
   import structlog
   structlog.configure(
     processors=[
       structlog.contextvars.merge_contextvars,
       structlog.processors.add_log_level,
       structlog.processors.TimeStamper(fmt="iso"),
       structlog.processors.JSONRenderer(),
     ],
   )
   ```
3. Middleware FastAPI qui ajoute `request_id` (UUID) + `path` + `user_id` (si présent) au contexte, log la durée et le status.
4. **Ne jamais logger** : tokens, cookies, headers Authorization, clés privées, PII en clair (cf. [`../SECURITY.md`](../SECURITY.md) § 6).

### Capturer les erreurs frontend (sans Sentry)

Pattern proposé pour MVP :
1. Backend : nouvel endpoint `POST /api/v1/_log/client-error` (no-auth, rate-limited à 60/h/IP).
2. Body : `{ message: string, stack?: string, url: string, user_agent: string }`.
3. Le endpoint loggue côté backend avec niveau `warning`.
4. Frontend : `window.onerror` + `window.onunhandledrejection` qui POST vers cet endpoint (best-effort, fail silently).
5. Permet de voir les erreurs prod dans les logs Railway sans coût externe.

### Healthcheck enrichi

`/health` actuel retourne `{status, version}`. Possible d'enrichir avec :
- `/health/database` (existe déjà)
- `/health/wayback` — ping `https://archive.org/wayback/available?url=https://example.com` avec timeout 5s
- `/health/google` — ping `https://accounts.google.com/.well-known/openid-configuration` avec timeout 5s

Mais : pas d'urgence MVP. À ajouter quand un problème prod réel sera survenu.

### Métriques business simples

Sans Plausible, on peut quand même mesurer :
- Compteur de vues par fiche (incrément côté backend dans la route SSR)
- Compteur de fiches créées / publiées (déjà en table)
- Endpoint admin (auth required) `/api/v1/_metrics` qui retourne ces compteurs en JSON

### Uptime monitoring externe (gratuit)

Options gratuites :
- **UptimeRobot** : 50 monitors gratuits, check toutes les 5 min, notif email
- **Better Stack** (Logtail) : free tier 10 monitors
- **Cron-job.org** : pour pings réguliers

Pour MVP : ajouter UptimeRobot sur `/health`. Pas de dep code-side, juste config dans leur dashboard.

## Pièges spécifiques

- **Logger un token / cookie** : violation `SECURITY.md` § 6. Ne pas le faire, jamais.
- **Trop de logs en prod** : explose le quota Railway. Niveau `INFO` max en prod, `DEBUG` uniquement local.
- **Endpoint `_log/client-error` non rate-limited** : vecteur d'inondation de logs. Rate limit obligatoire.
- **Sentry / Plausible / Datadog en MVP** : violation budget zéro. Refuser leur ajout tant que pas de signal utilisateur.
- **Sondes qui appellent des services externes sans timeout** : peut bloquer la route si Wayback est down.

## Fichiers à connaître

- `apps/backend/app/main.py` — config middleware
- `apps/backend/app/api/v1/endpoints/health.py` — sondes
- `apps/backend/app/core/config.py` — settings

## Pour aller plus loin

- `.docs/02-tech-architecture.md` section « Observabilité »
- `.docs/11-critique-and-improvements.md` section 4.E
- Jalon M3 dans `.docs/10-mvp-completion-plan.md`
