# 05 — Services métier : providers, gratuit, discovery, définitions, fiche, workspace

> Fiches du lot 5 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G5** (`check_lot.sh 5`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

La logique métier derrière les endpoints (lot 4) et la boucle (lot 2) : providers BYOK (chiffrement AES-GCM, cache modèles 15 min, SSRF), mode gratuit (rotation de lanes Z.ai avec cooldown et quota), mode découverte (clé serveur DeepSeek sponsorisée), agents nommés (fichiers YAML du workspace, validation), orchestrateur de fiche (7 étages ICM séquentiels), workspace ICM hébergé (filesystem logique en base, seed du template, normalisation de chemins).

## Les fichiers

| Fiche | Contenu | LOC | sha256 | Fichier |
|---|---|---|---|---|
| [01-providers.md](01-providers.md) | CRUD BYOK, chiffrement, cache modèles, test clé, souveraineté | 608 | sha256: 3f40d049cd9e7213841069810a488fd00543f0fea83dba210a3161ecc50bfd08 | `apps/backend/app/services/agent_providers.py` |
| [02-gratuit.md](02-gratuit.md) | Lanes Z.ai, rotation, cooldown, consentement versionné, catalogue modèles | 420 | sha256: 6e72c48a56434a0ea1a8f23537b2de9a741df5e314d1aa0173bd0fe4257f4717 | `apps/backend/app/services/agent_gratuit.py` |
| [03-workspace.md](03-workspace.md) | Filesystem logique, normalisation chemins, seed, frontmatter, meta | 320 | sha256: 2aa6731fd250a1021a2fa5492507a80f79b57ad16ade83cc369cd2bab9005a6a | `apps/backend/app/services/agent_workspace.py` |
| [04-definitions.md](04-definitions.md) | Agents nommés YAML, validation, `tools_absents`, tri builtin | 192 | sha256: d46d5c009b4711b0053a1a3158a617ff0ef67f818aae4464cc55ccaa1ce725df | `apps/backend/app/services/agent_definitions.py` |
| [05-fiche.md](05-fiche.md) | Orchestrateur 7 étages ICM, reprise `depuis`, compte rendu séquentiel | 211 | sha256: 0c19cff5bb3c66fdde3c6ae8baaae8ed1ac55f53e9b7481bfc7c89d3c70c37d9 | `apps/backend/app/services/agent_fiche.py` |
| [06-discovery.md](06-discovery.md) | Clé serveur DeepSeek, quota découverte, provider transient | 142 | sha256: 7fba2a223658c059d98b54f6eebafdeeac5f8a572cdbf9f87caf01342b15cdf6 | `apps/backend/app/services/agent_discovery.py` |

## Invariants du lot

- **Cache modèles** : TTL 15 min (`_MODELES_TTL_SECS=900`) en mémoire process, invalidé sur toute mutation/suppression du provider (`apps/backend/app/services/agent_providers.py:52`).
- **SSRF** : `_resolve_base_url` appelle `assert_url_is_safe` pour les URLs utilisateur ; les défauts intégrés (`PROVIDER_DEFAULT_BASE_URLS`) sont des constantes de confiance (`apps/backend/app/services/agent_providers.py:163`).
- **Consentement gratuit** : `VERSION_WARNING="2026-08-23-v1"` — tout changement de fond exige un re-consentement (`apps/backend/app/services/agent_gratuit.py:35`).
- **Cooldown lane** : `COOLDOWN_MINUTES=10` après 429 (`apps/backend/app/services/agent_gratuit.py:38`).
- **Modèles gratuits** : `MODELES_GRATUITS` (2 entrées : `glm-4.7-flash`, `glm-4.5-flash`, Z.ai uniquement) — jamais de modèle payant sur la clé gratuite (`apps/backend/app/services/agent_gratuit.py:43`).
- **Workspace** : racines fermées `ALLOWED_ROOTS=("shared","stages","_core","runs","setup","agents")` + `ALLOWED_TOP_FILES=("AGENTS.md","CONTEXT.md")`, `_PATH_MAX=500`, `_CONTENT_MAX=1_000_000` (`apps/backend/app/services/agent_workspace.py:29-36`).
- **Étages ICM** : `ETAPES` = 7 étages séquentiels (brief → sources → annotations → extraits → connexions → relecture → publication) (`apps/backend/app/services/agent_fiche.py:54`).

## Dettes et pièges constatés à la lecture

- `_maintenant()` (`apps/backend/app/services/agent_gratuit.py:49`) : UTC sans timezone, nécessaire pour les colonnes `TIMESTAMP WITHOUT TIME ZONE` de Postgres (erreur « can't subtract offset-naive and offset-aware datetimes » prod-only).
- `seed()` (`apps/backend/app/services/agent_workspace.py:287`) : idempotent, ne jamais écraser un fichier modifié — ne fait qu'insérer les chemins absents.
- `_parse_frontmatter` (`apps/backend/app/services/agent_workspace.py:93`) : les YAML pourris et les délimiteurs ouverts sans fermeture rendent `({}, content)` sans exception.
- Le mode gratuit et le mode découverte partagent le même compteur `AgentDiscoveryQuota` mais ont des plafonds distincts dans les settings (`apps/backend/app/services/agent_gratuit.py:14`).
- `tester()` (`apps/backend/app/services/agent_providers.py:332`) ne lève jamais : retourne un `AgentProviderTestResult` classifiable. Sur succès, chauffe le cache modèles avec `refresh=True`.
- `_detail_provider` (`apps/backend/app/services/agent_providers.py:391`) gère 5 formes de réponse testées en prod (OpenAI, Gemini, Mistral, Cerebras, HTML brut).
