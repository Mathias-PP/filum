# Skill: OAuth Google (jalon M1)

> Quand l'utiliser : implémenter ou débugger le flow OAuth Google. C'est le **path critique** du jalon M1 de [`10-mvp-completion-plan.md`](../../.docs/10-mvp-completion-plan.md).

## Contexte

Aujourd'hui le projet a le scaffolding auth (cookies, JWT HS256, endpoint `/me`, `/logout`), mais **OAuth Google n'est pas branché**. Pas d'utilisateur tiers possible → bloqueur MVP. Cookies en `samesite=lax` → incompatible cross-origin Vercel ↔ Railway.

## Pré-requis humain (l'agent ne peut pas faire)

Le développeur doit :
1. Créer un projet OAuth dans Google Cloud Console
2. Récupérer `client_id` + `client_secret`
3. Déclarer la redirect URI : `https://filum-production-07bb.up.railway.app/api/v1/auth/google/callback`
4. Ajouter dans Railway les variables (en **lowercase**) :
   - `google_client_id`
   - `google_client_secret`
   - `google_redirect_uri`
5. Pour le dev local : redirect URI alternative `http://localhost:8000/api/v1/auth/google/callback` + ngrok HTTPS si besoin pour les tests (Google n'accepte pas http en prod).

L'agent doit refuser de continuer sans confirmation que ces 5 points sont faits.

## Checklist d'exécution (côté agent)

1. **Vérifier la lib** : `apps/backend/pyproject.toml` — `authlib` est-il déjà dep ? Si oui OK, sinon proposer l'ajout (justifier dans la PR).
2. **Endpoint `/auth/google/login`** : génère un `state` token (CSRF), stocke en cookie HttpOnly temporaire, redirige vers `https://accounts.google.com/o/oauth2/v2/auth?...`.
3. **Endpoint `/auth/google/callback`** : reçoit `code` + `state`, vérifie le `state`, échange le code contre un id_token via `https://oauth2.googleapis.com/token`, parse le JWT Google pour récupérer email + profile + sub, crée/retrouve l'utilisateur en BDD, génère un cookie session HS256.
4. **Bascule cookie `samesite=none, secure=True`** : `apps/backend/app/api/v1/endpoints/auth.py` ~128-152. Conditionner sur `settings.debug` :
   - `debug=True` (dev) → `samesite='lax', secure=False`
   - `debug=False` (prod) → `samesite='none', secure=True`
5. **Génération de la paire Ed25519** : à la première connexion d'un utilisateur, générer `private_key` + `public_key` et stocker la `private_key` chiffrée (AES-GCM avec `master_encryption_key`).
6. **Frontend** : ajouter un bouton « Continuer avec Google » sur `/` qui redirige vers `<backend>/api/v1/auth/google/login`. Page `/auth/callback` qui hydrate le store `auth`.
7. **`credentials: 'include'`** dans le client API frontend (`apps/frontend/src/lib/api/`) pour envoyer le cookie cross-origin.
8. **Mise à jour `cors_origins`** : déjà OK (`["https://filum-eight.vercel.app","http://localhost:5173"]`), mais vérifier.
9. **Tests** :
   - Unit : génération du state token, vérification du code échangé (mock httpx)
   - Integration : `TestClient` qui simule un callback avec un cookie mocké
10. **Test manuel** :
    - Local : `make backend` puis ouvrir `http://localhost:5173`, cliquer login, faire le flow réel avec un compte Google dev.
    - Prod : pousser, attendre redeploy Railway/Vercel, tester avec un compte Google réel.

## Critères de done (jalon M1)

- `curl https://filum-production-07bb.up.railway.app/api/v1/auth/google/login` → 302 vers `accounts.google.com`
- Après login navigateur, `GET /api/v1/auth/me` retourne 200 avec les infos user
- `POST /api/v1/auth/logout` invalide le cookie
- Au moins 1 test d'intégration sur `/auth/me` avec cookie mocké
- L'utilisateur a une paire Ed25519 générée et stockée chiffrée

## Pièges spécifiques

- **Cookie pas envoyé cross-origin** : oubli de `credentials: 'include'` côté frontend OU cookie en `samesite=lax`. Cf. `PITFALLS.md` 1.8.
- **`secure=True` casse le dev local** : conditionner sur `settings.debug`.
- **Google rejette les redirect URIs http** : utiliser HTTPS (prod) ou ngrok (dev).
- **`state` token non vérifié** : risque CSRF. Toujours vérifier `state` côté callback.
- **id_token Google non vérifié** : doit vérifier la signature contre les clés publiques Google JWKS. `authlib` le fait par défaut.
- **Safari ITP** : bloque les cookies tiers dans certains contextes. Tester sur Safari iOS dès cette PR.
- **Variables d'env UPPERCASE** : silencieusement ignorées. Tout en lowercase. Cf. `PITFALLS.md` 1.6.

## Fichiers à connaître

- `apps/backend/app/api/v1/endpoints/auth.py` — scaffolding existant à compléter
- `apps/backend/app/services/auth.py` — JWT HS256, hash
- `apps/backend/app/crypto/keygen.py` (si existe) — génération Ed25519
- `apps/backend/app/core/config.py` — `google_*` settings
- `apps/frontend/src/lib/api/auth.ts` — client API
- `apps/frontend/src/lib/stores/auth.ts` — store frontend

## Pour aller plus loin

- ADR-004 (Google OAuth seul en MVP)
- ADR-009 (AES-GCM pour stockage des clés)
- ADR-014 (PyJWT, pas python-jose)
- [`../../.docs/10-mvp-completion-plan.md`](../../.docs/10-mvp-completion-plan.md) — jalon M1
