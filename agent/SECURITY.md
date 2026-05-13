# SECURITY — règles de sécurité pour l'agent autonome

> Complémentaire à [`../SECURITY.md`](../SECURITY.md) (qui décrit la politique sécurité du projet pour les humains) et à [`PERMISSIONS.md`](./PERMISSIONS.md) (matrice d'autorisations). Ici on traite spécifiquement des risques d'un agent qui exécute des commandes et écrit du code en autonomie.

---

## 1. Secrets — règle absolue

L'agent ne doit **jamais** :
- Lire `.env` (production ou dev). Lire `.env.example` est OK.
- Écrire un secret en clair dans le code, les commentaires, les logs, les commit messages, les descriptions de PR.
- Commit un secret même temporairement. Pas de « je le retire après ».
- Demander à l'utilisateur de coller un secret dans la conversation. Si une variable est nécessaire, expliquer où la configurer (Railway dashboard, Vercel env vars).

Avant chaque `git add` qui touche un fichier de config ou de code Python :

```bash
git diff --staged | grep -iE 'key|secret|token|password|bearer|api[_-]?key' | head -20
```

Si quelque chose ressort qui n'est pas un placeholder évident (`<your-key-here>`, `xxx`, `dummy`, `example`) → STOP et investiguer.

---

## 2. Scope d'action

L'agent opère **strictement** dans le repo Filum (`C:\Users\mathi\Documents\filum_project\filum` côté Windows, ou son équivalent WSL).

Sont interdites sans validation explicite :
- Modification de fichiers hors du repo (`~/.bashrc`, `~/.ssh/`, etc.)
- Installation de paquets globaux (`pip install --user`, `npm install -g`, `apt install`)
- Modification de la config système (registry Windows, services)
- Accès à d'autres repos du développeur

Lecture en dehors du repo : autorisée pour `git config --get`, `gh auth status`, `uv --version`, etc. Pas pour explorer `~/.config/` ou `~/Documents/`.

---

## 3. Surface réseau

L'agent peut :
- ✅ `curl` vers une URL publique documentée (API Wayback, Crossref, Google docs publics, GitHub raw)
- ✅ Cloner un repo public via `git clone`
- ✅ Appeler les endpoints publics de Filum (Railway prod) en lecture seule (`/health`, `/api/v1/@…/…`)

L'agent ne doit pas :
- ❌ Scanner des plages d'IP, faire du fingerprinting
- ❌ Envoyer des requêtes vers des services internes (RFC1918) sans demande explicite
- ❌ Faire des requêtes massives qui pourraient ressembler à un DoS
- ❌ Exfiltrer des données du repo vers un service tiers (paste.bin, gist, webhook)

---

## 4. Validation des entrées (côté code écrit par l'agent)

Toute nouvelle fonction qui reçoit une URL ou un identifiant utilisateur doit :
1. La typer avec Pydantic (`HttpUrl`, `EmailStr`, `constr(...)` selon le cas)
2. Refuser les schemes non-`https?` ou les hôtes RFC1918 (`127.0.0.1`, `10.*`, `192.168.*`, `169.254.*`)
3. Logger un warning (pas une erreur) si une entrée a été normalisée

Cf. la guard SSRF déjà en place sur `GET /sources/extract` (PR2 itération 3) — pattern à reproduire pour tout futur endpoint qui fetch une URL utilisateur.

---

## 5. Cryptographie — règles strictes

L'agent ne doit **jamais** :
- Réimplémenter un algo crypto à la main (AES, Ed25519, SHA…)
- Utiliser `os.urandom` directement pour générer une clé (préférer `cryptography.hazmat.primitives.asymmetric.ed25519.Ed25519PrivateKey.generate()`)
- Stocker une clé privée non chiffrée en base
- Réduire la longueur d'une signature ou d'un hash
- Modifier le `canonical_hash` payload (cf. `PITFALLS.md` 1.3)

L'agent doit :
- Préférer `cryptography` (déjà dans le projet) à `pycryptodome` (banni implicitement)
- Utiliser AES-GCM (ADR-009) pas Fernet
- Utiliser PyJWT (ADR-014) pas `python-jose`
- HS256 pour les JWT (clé partagée), Ed25519 pour les signatures de fiches

---

## 6. Logs

L'agent ne doit jamais logger :
- Tokens (JWT, OAuth access_token, refresh_token)
- Cookies session
- Headers `Authorization` ou `Cookie` complets
- Clés privées (encrypted ou non)
- PII utilisateur en clair (email, IP, nom)

Pattern recommandé :
```python
logger.info("user authenticated", extra={"user_id": user.id})  # OK
# PAS :
logger.info(f"user logged in with token {token}")  # JAMAIS
```

---

## 7. Tests et données

- Les fixtures de test doivent utiliser des données fictives évidentes (`alice@example.com`, `test-user-1`).
- Pas de dump de données prod dans les tests, même anonymisé, sans validation explicite.
- Pas de clé privée hardcodée dans les tests autre que celle générée à la volée dans le test lui-même.

---

## 8. Dépendances

Pour toute nouvelle dépendance (cf. `PERMISSIONS.md` § 3) :

1. Vérifier qu'elle est maintenue (commit récent dans les 12 derniers mois)
2. Vérifier qu'elle n'a pas de CVE haute sévérité ouverte
3. Préférer une dep avec peu de transitives (cf. ADR-014 sur `python-jose` → `PyJWT`)
4. Justifier le besoin dans la conversation et dans la PR
5. La CI `dependency-review-action` doit passer

---

## 9. Code écrit par l'agent — auto-revue sécurité

Avant chaque PR qui touche le backend, l'agent doit auto-checker :

- [ ] Tous les endpoints mutables ont `Depends(get_current_user)` (ou une auth équivalente)
- [ ] Aucun `f"SELECT ..."` avec interpolation directe — toujours via SQLAlchemy
- [ ] Aucun `subprocess.run(..., shell=True)` avec entrée utilisateur
- [ ] Aucun `eval()`, `exec()`, `compile()` avec entrée utilisateur
- [ ] Aucun nouveau pickle/marshal sur des données externes
- [ ] Aucun nouveau secret en clair dans le code ou les tests
- [ ] CORS, rate limit, validation Pydantic présents sur les nouveaux endpoints publics

Pour le frontend :

- [ ] Aucun `eval`, `new Function`
- [ ] `dangerouslySetInnerHTML` (équivalent Svelte : `{@html ...}`) uniquement avec contenu sanitizé
- [ ] Pas de token stocké dans `localStorage` (cookies HttpOnly only)

---

## 10. Reporting d'une vulnérabilité découverte par l'agent

Si l'agent identifie une vulnérabilité dans le code existant pendant une session :

1. **Ne pas** ouvrir une issue publique GitHub.
2. **Ne pas** la mentionner dans une PR publique sans la corriger en même temps.
3. Reporter au développeur dans la conversation, avec :
   - Localisation précise (`fichier:ligne`)
   - Vecteur d'attaque
   - Sévérité estimée
   - Proposition de fix
4. Laisser le développeur décider (créer une PR privée, contacter `security@filum.app`, ou autre).

---

## 11. Mode dégradé / refus

L'agent doit **refuser** (et expliquer pourquoi) si on lui demande de :
- Désactiver un check de sécurité (CSP, CORS, validation Pydantic) sans justification documentée
- Ajouter un `--no-verify` à un commit
- Désactiver un hook pre-commit
- Désactiver TruffleHog ou Trivy en CI
- Hardcoder un secret « temporairement »
- Bypass un rate limit pour un usage prod
- Logger un token « pour debug »
- Commit `.env`

Un refus poli + explication + proposition d'alternative est toujours préférable à une exécution silencieuse.

---

*Cette page complète `../SECURITY.md`. En cas de conflit, c'est cette page-ci qui s'applique pour l'agent autonome (plus restrictive).*
