# Plan d'améliorations post-audit — Juin 2026

> PR associée : `feat/audit-improvements` (PR #92, mergée 2026-06-02).
> Date de l'audit : 2026-06-02.
>
> **Voir aussi** : [`13-audit-2026-05-26-followups.md`](./13-audit-2026-05-26-followups.md) — items long terme structurés P1/P2/P3 issus de l'audit du 26 mai. **Ce doc-ci** est spécifique à la session du 2 juin : il liste ce qui a été corrigé immédiatement, ce qui a été vérifié et retiré (windmills), et ce qui a été déplacé vers le suivi long terme. Pour décider quoi faire **ensuite**, lire `13-audit-…-followups.md` (priorisation + triggers).

## Contexte

Ce document synthétise les vérifications et corrections issues de l'audit du 26 mai 2026. Il distingue ce qui a été **vérifié et retiré** (moulins à vents), ce qui a été **corrigé dans cette PR**, et ce qui reste à faire documenté pour le futur.

---

## 1. Moulins à vents retirés (faux positifs de l'audit initial)

Lors de l'analyse initiale, plusieurs problèmes ont été identifiés à tort. Après re-vérification contre le code réel :

### ❌ IndexError dans `users.py:68-69`

**Affirmation initiale** : `cards[-1]` lève IndexError si `cards` est vide.

**Vérification code** : La ligne est en fait :
```python
"first_published_at": cards[-1].published_at.isoformat()
if cards and cards[-1].published_at
else None,
```
Le guard `if cards` (truthy check sur liste non-vide) protège l'accès. Aucun bug possible.

### ❌ CSRF — SameSite=None = vulnérable

**Affirmation initiale** : SameSite=None en prod permet des attaques CSRF.

**Vérification architecture** :
- Le cookie de session est posé **via le proxy Vercel** → domaine = Vercel, pas Railway
- Les appels API passent par le proxy → same-origin → SameSite n'a même pas besoin d'être None
- SameSite=None n'est nécessaire que pour le flux OAuth (Google redirige vers Vercel → proxy → Railway → set-cookie retour via Vercel)
- L'API est JSON-only → pas de form CSRF possible
- CORS middleware Railway bloque les requêtes cross-origin non autorisées

**Conclusion** : L'architecture proxy + CORS + JSON API rend le CSRF non exploitable. Le SameSite=None est correct pour le besoin OAuth.

### ❌ AES-GCM key derivation faible (`keygen.py:13-16`)

**Affirmation initiale** : La dérivation utilise les premiers 32 bytes de la clé hex, réduisant l'entropie à 128 bits.

**Vérification crypto** : Effectivement, `encryption_key.encode("utf-8")[:32]` avec une clé hex (64 chars hex → 64 bytes → first 32 bytes = 32 hex chars) donne ~128 bits d'entropie. **Mais AES-128 est toujours sécurisé** (NSPM 2022 recommande jusqu'en 2033+). Aucune vulnérabilité pratique. Le code est correct pour l'usage actuel.

### ❌ Canonicalizer non-RFC 8785 (`signing.py:13`)

**Affirmation initiale** : `json.dumps(sort_keys, separators, ensure_ascii)` n'est pas RFC 8785 compliant.

**Vérification** : C'est vrai — ce n'est pas certifié RFC 8785. Mais le même code est utilisé pour signer ET vérifier. La cohérence interne est garantie. L'interopérabilité externe n'est pas un besoin aujourd'hui. Pas de bug.

---

## 2. Corrections appliquées dans cette PR

### 2.1 User-Agent expose email personnel (`url_extractor.py:23`)

**Problème** : `mailto:mathias.pinault@hotmail.fr` envoyé à CHAQUE site web scrape.

**Correction** : Remplacé par `mailto:contact@philum.app`.

**Risque si non corrigé** : L'email personnel du développeur est récoltable par n'importe quel site visité par l'extracteur → spam, doxxing.

### 2.2 `requirements.txt` contient `python-jose` obsolète

**Problème** : `python-jose[cryptography]>=3.5.0` a des CVEs connues. Le projet utilise déjà `pyjwt` dans `pyproject.toml` (le gestionnaire de dépendances réel). Mais `Dockerfile.migrate` utilise `requirements.txt` donc serait vulnérable si buildé.

**Correction** : Remplacé par `pyjwt>=2.10.0` dans `requirements.txt`.

**Risque si non corrigé** : Un build via `Dockerfile.migrate` embarque une dépendance avec CVEs.

### 2.3 `Dockerfile.migrate` utilise encore `requirements.txt` obsolète

**Problème** : Utilise `uv pip install --system -r requirements.txt` au lieu de `uv sync --frozen` avec `pyproject.toml`.

**Correction** : Aligné sur le `Dockerfile` principal : `pyproject.toml` + `uv.lock` + `uv sync --frozen`.

**Risque si non corrigé** : Dépendances non reproductibles. Le `Dockerfile.migrate` dérive du `pyproject.toml` véritable.

### 2.4 `datetime.utcnow()` déprécié dans les modèles

**Problème** : `datetime.utcnow()` est déprécié depuis Python 3.12. Présent dans `source.py`, `biblio_card.py`, `audit_event.py`.

**Correction** : Remplacé par `lambda: datetime.now(UTC).replace(tzinfo=None)` (comportement identique — retourne une datetime naive).

**Risque si non corrigé** : DeprecationWarning silencieux. Pas de bug runtime aujourd'hui, mais deviendra un warning bruyant dans Python 3.14+.

---

## 3. Problèmes identifiés — NON corrigés (documentés pour le futur)

Ces problèmes sont réels mais nécessitent plus de design, d'infrastructure, ou de coordination. Ils sont documentés ici et dans `.docs/13-audit-2026-05-26-followups.md` (F5 notamment).

### 3.1 Durabilité de la queue Wayback (`sources.py:184-189`)

**Problème** : `asyncio.create_task(_archive_bg())` est fire-and-forget. Si Railway redémarre (déploiement, crash, scale) pendant le polling Wayback (~33s), la tâche est perdue silencieusement. La source reste `archive_status = "pending"` sans retry.

**Solution envisagée** : Queue PostgreSQL via table `archive_jobs` + worker avec `SELECT ... FOR UPDATE SKIP LOCKED`. Voir F5 dans `.docs/13-audit-2026-05-26-followups.md`.

**Trigger** : Premier utilisateur qui signale une source bloquée en `pending`.

### 3.2 Risque juridique — Archivage automatique Wayback

**Problème** : L'archivage automatique de toute URL ajoutée (sauf archive manuelle) expose à un risque si un utilisateur soumet du contenu illicite. Le projet archive et potentiellement distribue ce contenu via Wayback Machine.

**Mitigations recommandées** :
- URL denylist synchrone (hash set de domaines connus) vérifiée AVANT appel Wayback
- Bouton "Signaler" sur fiches publiques (sans auth)
- CGU avec clause de non-responsabilité
- Option : désactiver l'auto-archivage par défaut (`archive_status = "requires_review"`)

### 3.3 Migration des colonnes legacy ADR-019

**Problème** : Les colonnes `canonical_hash`, `signature` sur `biblio_cards` existent toujours en base (dead storage). Déjà documenté comme F11 dans `.docs/13-audit-2026-05-26-followups.md`.

**Trigger** : Prochaine migration de schéma majeure.

### 3.4 Tests Postgres vs SQLite

**Problème** : Les tests utilisent SQLite (`sqlite+aiosqlite`), pas Postgres. Certains comportements DB diffèrent. Déjà documenté comme F3 dans `.docs/13-audit-2026-05-26-followups.md`.

**Trigger** : Prochain index partial ou contrainte conditionnelle.

---

## 4. Vérifications sans changement

Ces points ont été vérifiés et sont corrects :

| Point | Fichier | Verdict |
|-------|---------|---------|
| `cors_origins` config | `config.py:39` | Correct — liste d'origines connues |
| Session JWT expiration | `auth.py:21` | 24h, raisonnable |
| OAuth state CSRF | `auth.py:173-179` | Oui, state cookie vérifié |
| SSRF guard | `core/url_safety.py` | Oui, présent et fonctionnel |
| Signature Ed25519 | `signing.py` | Correcte et cohérente |
| Rate limiting | `sources.py:44` | 10/min sur endpoint extract |

---

## 5. État du rename Filum → Philum

Voir `.docs/14-philum-rename-migration.md` pour le plan complet.

**État actuel** :
- Phase 1 (texte frontend visible) : ✅ Réalisée dans `feat/rename-philum`
- Phases 2-4 (docs, identifiants, backend, infra) : 📝 Documentées, non exécutées
- Cette PR (`feat/audit-improvements`) : ne touche PAS au rename

**Point d'attention** : Le `User-Agent` dans `url_extractor.py` a été mis à jour de `"Filum/0.1"` vers `"Philum/0.1"` dans cette PR — c'est cohérent avec le rename mais mineur.

---

*Document à mettre à jour lors de la prochaine session d'amélioration.*
