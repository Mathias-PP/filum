# 05-02 — Gratuit (lanes, rotation, cooldown, consentement)

> **Fiche du lot 5.** [CONTEXT.md](CONTEXT.md) · [Retour au plan](../../plans/2026-08-25-revue-code-agent.md) · **Porte de sortie : G5**.
> **Fichier :** `apps/backend/app/services/agent_gratuit.py` (420 l., 19 symboles).
> **SHA256 :** `6e72c48a56434a0ea1a8f23537b2de9a741df5e314d1aa0173bd0fe4257f4717`

## Rôle

Mode gratuit par rotation de lanes Z.ai : cooldown après 429, quota quotidien, consentement versionné, catalogue de modèles gratuit. Gestion du switch automatique entre lanes.

## Symboles

| Symbole | Ligne | Rôle |
|---|---|---|
| `ErreurQuotaGratuit` | `apps/backend/app/services/agent_gratuit.py:60` | Exception quand le quota gratuit est épuisé |
| `LaneActive` | `apps/backend/app/services/agent_gratuit.py:68` | NamedTuple d'une lane retenue par le routeur (lane + provider transient) |
| `cle_lane` | `apps/backend/app/services/agent_gratuit.py:75` | Rend la clé API d'une lane depuis les settings |
| `mode_disponible` | `apps/backend/app/services/agent_gratuit.py:88` | Le mode existe-t-il sur cette instance ? |
| `_maintenant` | `apps/backend/app/services/agent_gratuit.py:49` | UTC sans fuseau, pour colonnes TIMESTAMP WITHOUT TIME ZONE |
| `_chiffrer_cle` | `apps/backend/app/services/agent_gratuit.py:94` | Chiffre une clé API pour construire un provider transient |
| `_provider_transient` | `apps/backend/app/services/agent_gratuit.py:100` | Construit le provider éphémère portant la clé serveur |
| `etat_consentement` | `apps/backend/app/services/agent_gratuit.py:124` | État exposé à l'UI : disponible ? actif ? fournisseur actuel ? |
| `est_consentant` | `apps/backend/app/services/agent_gratuit.py:150` | Vérifie si l'utilisateur a consenti à la version courante |
| `liste_modeles` | `apps/backend/app/services/agent_gratuit.py:160` | Catalogue proposable, annoté de l'état des lanes connues |
| `definir_modele_primaire` | `apps/backend/app/services/agent_gratuit.py:188` | Pointe la lane primaire (`zai`) sur un modèle du catalogue |
| `donner_consentement` | `apps/backend/app/services/agent_gratuit.py:206` | Enregistre le consentement, refuse une version inconnue |
| `retirer_consentement` | `apps/backend/app/services/agent_gratuit.py:220` | Supprime le consentement de l'utilisateur |
| `choisir_lane` | `apps/backend/app/services/agent_gratuit.py:232` | Première lane utilisable : active, avec cle, hors quota et hors cooldown |
| `consommer_requete` | `apps/backend/app/services/agent_gratuit.py:260` | +1 requête sur la lane du jour |
| `signaler_echec` | `apps/backend/app/services/agent_gratuit.py:283` | Pose un cooldown sur la lane (rate limit, erreur fournisseur) |
| `verifier_quota_utilisateur` | `apps/backend/app/services/agent_gratuit.py:319` | Rend le nombre de messages restants, lève `ErreurQuotaGratuit` |
| `consommer_message_utilisateur` | `apps/backend/app/services/agent_gratuit.py:340` | Incrémente atomiquement le compteur quotidien |
| `tester_lane` | `apps/backend/app/services/agent_gratuit.py:372` | Ping minimal de la lane qui servirait le prochain tour |

## Invariants

- `VERSION_WARNING = "2026-08-23-v1"` (`apps/backend/app/services/agent_gratuit.py:35`) : tout changement de fond exige un re-consentement.
- `COOLDOWN_MINUTES = 10` (`apps/backend/app/services/agent_gratuit.py:38`) : cooldown après 429.
- `MODELES_GRATUITS` (`apps/backend/app/services/agent_gratuit.py:43`) : 2 modèles Z.ai uniquement — jamais de modèle payant sur la clé gratuite.
- `_maintenant()` (`apps/backend/app/services/agent_gratuit.py:49`) : UTC sans timezone, nécessaire pour les colonnes `TIMESTAMP WITHOUT TIME ZONE` de Postgres.
- `choisir_lane()` (`apps/backend/app/services/agent_gratuit.py:232`) : route par position asc, filtre cooldown + rpd_cap.
- `tester_lane()` (`apps/backend/app/services/agent_gratuit.py:372`) : n'incrémente PAS les compteurs — diagnostic, pas un tour.

## Dettes

- `liste_modeles()` (`apps/backend/app/services/agent_gratuit.py:160`) : filtre `zai%` en dur dans le LIKE — si un fournisseur non-Z.ai est ajouté, il faudra adapter.
- `definir_modele_primaire()` (`apps/backend/app/services/agent_gratuit.py:188`) : lève `ValueError` brut — pas d'exception métier dédiée.
