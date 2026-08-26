# Aplatissement `anyOf` pour validateurs Gemini (`schema_compat.py`)

## apps/backend/app/mcp_server/schema_compat.py
Lu intégralement : oui (39/39 lignes) · sha256: cefa864b1839 · date: 2026-08-25

### Symbole unique

- `aplatir_nullable` — `apps/backend/app/mcp_server/schema_compat.py:19` — remplace récursivement tout `anyOf: [T, {"type": "null"}]` par `T`. Ne mute jamais l'entrée. Les vraies unions (deux variantes non nulles) sont laissées intactes.

**Pourquoi** : le validateur Gemini refuse `anyOf`, or fastmcp le produit pour tout paramètre annoté `X | None = None`, soit la totalité des paramètres optionnels des outils Philum. Résultat côté client : « Provided JSON is invalid or does not contain any tools » et aucun des 45 outils n'apparaît (`apps/backend/app/mcp_server/schema_compat.py:6`).

**Appelé depuis** : `server.py:outil()` — aplati sur les `parameters` de chaque tool enregistré (`apps/backend/app/mcp_server/server.py:48`).
