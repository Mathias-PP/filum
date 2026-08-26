# Agents nommés — lecture seule (`agent_definitions.py`)

## apps/backend/app/api/v1/endpoints/agent_definitions.py
Lu intégralement : oui (68/68 lignes) · sha256: 24280658ff0b · date: 2026-08-25

Aucun POST/PATCH/DELETE : un agent est un fichier `agents/<slug>.yaml` du workspace. Le créer, l'éditer ou le supprimer passe par les endpoints workspace (lot 4.7), ce qui évite deux chemins d'écriture pour un même objet (`apps/backend/app/api/v1/endpoints/agent_definitions.py:4`).

### Routes (2)

| Méthode | Route | Fonction | Description |
|---|---|---|---|
| `GET` | `/agent/definitions` | `lister_agents` | Liste les agents valides + rejetés (fichiers invalides) |
| `GET` | `/agent/definitions/{slug}` | `obtenir_agent` | Détail d'un agent par slug |

### Symbole

- `_to_read` — `apps/backend/app/api/v1/endpoints/agent_definitions.py:27` — convertit `AgentDefinition` (service) en `AgentDefinitionRead` (schéma Pydantic), incluant `tools_absents` (outils référencés mais inconnus du registre) et `path` (chemin du fichier YAML).
