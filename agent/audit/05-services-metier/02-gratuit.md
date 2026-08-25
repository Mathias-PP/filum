# 05-02 — Gratuit (lanes, rotation, cooldown, consentement)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_gratuit.py` (420 l., 19 symboles).

## Rôle

Mode gratuit par rotation de lanes Z.ai (glm-4.7-flash, glm-4.5-flash) : cooldown après 429, quota quotidien, consentement versionné, catalogue de modèles gratuit. Gestion du switch automatique entre lanes.

## Architecture

- `FreeLane` : dataclass d'une lane (nom, nom d'affichage, priorité, cooldown_until).
- `_LANES` : 2 lanes Z.ai (glm-4.7-flash priorité 1, glm-4.5-flash priorité 2).
- `FreeLaneState` : état persistant des lanes (cooldowns, quota) — sérialisé en JSON.
- `_COMPTEUR_KEY` : clé Redis pour le compteur quotidien.
- `_LANES_STATE_KEY` : clé Redis pour l'état des lanes.

## Symboles clés

| Symbole | Ligne | Rôle |
|---|---|---|
| `FreeLane` | 21 | Dataclass lane |
| `FreeLaneState` | 30 | État persistant lanes |
| `MODELES_GRATUITS` | 43 | 2 modèles Z.ai |
| `VERSION_WARNING` | 35 | Version consentement |
| `COOLDOWN_MINUTES` | 38 | Cooldown 10 min après 429 |
| `_LANES` | 25 | Liste 2 lanes |
| `FreeProviderError` | 55 | Exception métier |
| `_maintenant` | 49 | UTC sans tz |
| `_consentement_ok` | 61 | Vérifie version |
| `_est_en_cooldown` | 74 | Vérifie cooldown lane |
| `_marquer_cooldown` | 82 | Active cooldown |
| `_incrementer_compteur` | 95 | Incrémente quota |
| `_decrementer_compteur` | 110 | Décrémente quota |
| `_lire_etat_lanes` | 125 | Lecture état lanes |
| `_sauvegarder_etat_lanes` | 140 | Sauvegarde état lanes |
| `_prochaine_lane` | 158 | Sélection lane prioritaire |
| `resoudre_gratuit` | 200 | Orchestrateur principal |
| `catalogue_gratuit` | 260 | Liste modèles disponibles |
| `_lister_modeles_gratuit` | 280 | Récupère modèles Z.ai |
| `_quota_restant` | 300 | Calcule quota restant |
| `_quota_gratuit` | 320 | Quota configurable |

## Flux typique (resolution gratuit)

1. `_consentement_ok` → vérifie `X-Consent-Version` == `VERSION_WARNING`.
2. `_prochaine_lane` → filtre lanes sans cooldown → retourne la première disponible.
3. `_incrementer_compteur` → incrémente le compteur Redis.
4. En cas de 429 : `_marquer_cooldown` → cooldown 10 min sur la lane courante.
5. En fin de jour : `_decrementer_compteur` → remet le compteur à 0.

## Dettes et pièges

- `_maintenant()` (`apps/backend/app/services/agent_gratuit.py:49`) : UTC sans timezone, nécessaire pour les colonnes `TIMESTAMP WITHOUT TIME ZONE` de Postgres.
- Le mode gratuit et le mode découverte partagent le même compteur `AgentDiscoveryQuota` mais ont des plafonds distincts dans les settings.
- `VERSION_WARNING` (`apps/backend/app/services/agent_gratuit.py:35`) : tout changement de fond exige un re-consentement — ne jamais oublier de bump.
- `MODELES_GRATUITS` (`apps/backend/app/services/agent_gratuit.py:43`) : 2 modèles Z.ai uniquement — jamais de modèle payant sur la clé gratuite.
- `COOLDOWN_MINUTES=10` (`apps/backend/app/services/agent_gratuit.py:38`) : cooldown après 429 — ne pas baisser sous 5 min (limite Z.ai).
