# CONFIG — paramètres techniques par agent

> Ce fichier explique comment les règles décrites dans [`PERMISSIONS.md`](./PERMISSIONS.md) sont **traduites en config** pour chaque agent supporté. Maintenir aligné avec les fichiers de config réels.

---

## Vue d'ensemble

Les règles d'autorisation existent **deux fois** :
1. **En clair** dans `PERMISSIONS.md` (pour l'humain et pour l'agent qui lit en début de session)
2. **En config** dans le fichier propre à chaque agent (pour le runtime qui filtre les actions)

Si l'un dérive de l'autre, c'est `PERMISSIONS.md` qui gagne. Il faut alors mettre à jour la config.

---

## opencode (Big Pickle, opencode.ai)

**Fichier** : [`../opencode.json`](../opencode.json) à la racine.

**Format** : JSON. Schéma officiel `https://opencode.ai/config.json`.

**Champs utilisés** :
- `instructions` : liste ordonnée de fichiers chargés au démarrage de session. Place ici les fichiers que l'agent doit voir avant d'agir.
- `permission.edit` : `allow` | `ask` | `deny` pour les modifications de fichiers
- `permission.webfetch` : idem pour les fetch HTTP
- `permission.bash` : objet pattern → décision. Les patterns plus spécifiques l'emportent sur `*`.
- `_comments` : champ libre pour documenter — opencode l'ignore.

**Lancement** :
```bash
cd <repo>
opencode
# La config opencode.json est lue automatiquement.
```

**Politique appliquée** (résumé) :
- Lecture, lint, format, test, build, fetch d'URLs whitelistées → `allow`
- Modification du repo → `allow` (l'agent peut éditer librement, le contrôle est sur le push)
- `git push origin main` (toutes variantes) → `deny`
- `gh pr merge` → `ask`
- Ajout de dépendance, rebase, reset, docker, kill → `ask`
- `rm`, `sudo`, `chown`, `pkill` → `deny`
- Toute commande non listée → `ask`

---

## Claude Code (Anthropic CLI)

**Fichier** : [`../CLAUDE.md`](../CLAUDE.md) (chargé automatiquement) + éventuelle config dans `~/.claude/settings.json` (personnelle, pas dans le repo).

**Permissions** : gérées par Claude Code via son propre système de permission modes (`acceptAll`, `acceptEdits`, etc.) + hooks éventuels. Pas de fichier de permissions dédié dans le repo.

**Politique projet** : décrite dans `CLAUDE.md` (section « Choses à ne PAS faire » et « Pièges Alembic à éviter »).

**Mémoire auto** : si activée localement, située dans `~/.claude/projects/<projet>/memory/MEMORY.md`. Personnelle, ne pas commit.

---

## Aider

**Fichier** : `.aider.conf.yml` (à créer si l'agent est utilisé).

**Politique recommandée** :
```yaml
# .aider.conf.yml (non commité par défaut, à créer localement si Aider est utilisé)
read:
  - AGENTS.md
  - CLAUDE.md
  - agent/README.md
  - agent/PERMISSIONS.md
  - agent/PITFALLS.md
  - agent/memory/PROJECT_SNAPSHOT.md
  - STATE.md
auto-commits: false        # l'humain valide les commits
dirty-commits: false
gitignore: true
# Pas d'option de filtrage bash dans Aider — l'humain valide chaque commande.
```

**Note** : Aider valide chaque commande shell devant l'humain. Pas de matrice de permission native. Les règles de `PERMISSIONS.md` doivent être appliquées par l'humain à la main.

---

## Cursor

**Fichier** : `.cursorrules` (texte plat) à la racine, si l'agent est utilisé.

**Politique recommandée** : pointer vers les règles agent.

```
Lire au démarrage :
- AGENTS.md
- CLAUDE.md
- agent/README.md
- agent/PERMISSIONS.md
- agent/PITFALLS.md
- agent/memory/PROJECT_SNAPSHOT.md
- STATE.md

Règles strictes :
- Jamais git push sur main directement
- Jamais gh pr merge sans validation humaine
- Jamais de secret en clair
- Jamais modifier .docs/00..09 sans demande explicite
- Toujours conventional commits
- Toujours via PR vers main
```

Cursor n'a pas de matrice de permission bash native. L'humain valide chaque commande.

---

## Continue.dev

**Fichier** : `.continue/config.json`. Format propriétaire. Voir doc officielle.

Politique : pointer vers les fichiers agent dans les `slashCommands` ou `customRules`.

---

## Codex CLI (OpenAI)

Pas de fichier de config standard dans le repo. L'agent lit `AGENTS.md` à la racine — c'est le format compatible.

---

## Ajouter un nouvel agent

1. Identifier le format de config de l'agent (fichier, syntaxe).
2. Traduire les règles de [`PERMISSIONS.md`](./PERMISSIONS.md) dans ce format.
3. Créer le fichier de config à l'emplacement attendu.
4. Documenter ici (section dédiée).
5. Tester : lancer l'agent en mode dry-run sur une tâche triviale (lire un fichier, ouvrir une branche).

---

## Vérification d'alignement

À faire après toute modification de `PERMISSIONS.md` :

- [ ] `opencode.json` mis à jour si une règle change
- [ ] Section opencode de ce fichier mise à jour
- [ ] Sections Aider / Cursor mises à jour si elles existent en config réelle dans le repo

---

*Cette page documente les **traductions techniques** des règles agent. Les **règles elles-mêmes** vivent dans `PERMISSIONS.md`.*
