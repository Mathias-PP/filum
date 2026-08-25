# Mode gratuit — consentement, test, modèles (`agent_mode_gratuit.py`)

## apps/backend/app/api/v1/endpoints/agent_mode_gratuit.py
Lu intégralement : oui (108/108 lignes) · sha256: 40ecf4fe0c73 · date: 2026-08-25

Le mode lui-même ne se règle PAS ici : c'est le chat (lot 4.1) qui l'utilise quand l'utilisateur a consenti et qu'une lane est disponible. Ces endpoints exposent l'état et le consentement versionné.

### Routes (6)

| Méthode | Route | Fonction | Description |
|---|---|---|---|
| `GET` | `/agent/mode-gratuit` | `etat_mode_gratuit` | Disponible sur cette instance ? Actif pour cet utilisateur ? |
| `PUT` | `/agent/mode-gratuit` | `donner_consentement` | Active le mode (version exacte du warning exigée) |
| `DELETE` | `/agent/mode-gratuit` | `retirer_consentement` | Désactive le mode |
| `POST` | `/agent/mode-gratuit/tester` | `tester_mode_gratuit` | Ping la lane qui servirait le prochain tour (hors quota) |
| `GET` | `/agent/mode-gratuit/modeles` | `lister_modeles_gratuits` | Catalogue des modèles gratuits (primaire/secours) |
| `PUT` | `/agent/mode-gratuit/modele` | `definir_modele_gratuit` | Choix du modèle primaire (toute l'instance, secours inchangé) |

### Schemas

- `ConsentementGratuit` (`apps/backend/app/api/v1/endpoints/agent_mode_gratuit.py:22`) — `{version: str}` (1-40 chars) — version exacte du warning de consentement.
- `ChoixModele` (`apps/backend/app/api/v1/endpoints/agent_mode_gratuit.py:75`) — `{model: str}` (1-120 chars) — modèle du catalogue gratuit.

### Pièges

- `donner_consentement` exige la version exacte du warning : `ValueError` → 400 avec code `version_warning_inconnue`, message « rechargez la page ».
- `definir_modele_gratuit` ne touche pas le secours : la rotation s'en sert automatiquement quand le primaire répond 429/surcharge.
