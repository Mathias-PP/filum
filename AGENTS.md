# Instructions pour agents IA autres que Claude Code

Ce fichier est destiné aux agents (Aider, Codex CLI, Continue, Cursor, opencode, etc.) qui ne reconnaissent pas automatiquement `CLAUDE.md`.

**Il ne contient rien en propre.** Toutes les règles vivent dans les fichiers autoritaires ci-dessous. Le maintenir en doublon dériverait — l'anti-pattern classique des deux entry files qui se contredisent.

---

## Lire dans cet ordre

1. [`CLAUDE.md`](./CLAUDE.md) — les mêmes règles s'appliquent, plus la table de routage.
2. [`agent/README.md`](./agent/README.md) — point d'entrée du système d'instructions pour travail autonome multi-sessions (protocole de démarrage, limites strictes, articulation avec le reste du repo).
3. [`agent/references/CODING_GUIDE.md`](./agent/references/CODING_GUIDE.md) — stack, principes, conventions.
4. [`STATE.md`](./STATE.md) — état réel du projet à l'instant T.

---

## Configuration runtime déjà en place

- [`opencode.json`](./opencode.json) — config opencode (instructions + matrice bash)
- [`agent/CONFIG.md`](./agent/CONFIG.md) — traduction des règles pour chaque agent supporté

---

*Ce projet est conçu pour être co-développé par plusieurs agents IA. La discipline documentaire est ce qui garantit la cohérence : une source par sujet, tout le reste route.*
