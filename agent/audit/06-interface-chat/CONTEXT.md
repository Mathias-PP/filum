# 06 — Interface chat frontend : lib/agent, chat UI, routes

> Fiches du lot 6 du [plan de revue](../../plans/2026-08-25-revue-code-agent.md). Porte de sortie : **G6** (`check_lot.sh 6`, double vert). Invariants de référence : [`_core/invariants.txt`](../_core/invariants.txt).

## Rôle du domaine

La couche frontend de l'agent IA : client API BYOK avec SSE streaming, parseur markdown sans `{@html}` (protection XSS), composants d'affichage des appels d'outils (ToolCard, ApprovalCard), panneau de chat principal (ChatPanel), consentement mode gratuit, gestion des clés API (page agents), et routes de navigation (liste conversations, conversation existante).

Ce lot couvre l'intégralité du frontend agent : 12 fichiers, 3 093 LOC, 62 symboles.

## Les fichiers

| Fiche | Contenu | LOC | sha256 | Fichier |
|---|---|---|---|---|
| [01-conversation.md](01-conversation.md) | Repli SSE→ChatItem, typage, events | 225 | sha256: 0ffcd3834fd32fb22467648d9108635dc06e78dcc12ae427728acbdc9df9e252 | `apps/frontend/src/lib/agent/conversation.ts` |
| [02-markdown.md](02-markdown.md) | Parseur markdown déterministe, protection XSS | 165 | sha256: 54e83debb5e1dc01dc8a0e4b43c3307085b0f9ca56e67f37ff4bd0da1af39abc | `apps/frontend/src/lib/agent/markdown.ts` |
| [03-toolLabels.md](03-toolLabels.md) | Traduction noms d'outils, rendu人文 | 181 | sha256: 8f99e0817400cc08f7749e90aeda17bde8221251f5e74c89bd778ad69deab624 | `apps/frontend/src/lib/agent/toolLabels.ts` |
| [04-agent.md](04-agent.md) | Client API BYOK, SSE streaming, sessions, providers, gratuit | 426 | sha256: 4fb8e7dc774539d94e47766b22092bf56da47dc82c270236f858f3e11aec295a | `apps/frontend/src/lib/api/agent.ts` |
| [05-AgentMarkdown.md](05-AgentMarkdown.md) | Composant rendu markdown, hydration safe | 78 | sha256: a2b29f88e187a16a70097a10b38436991f74ea7b4aae0bdec21f8ae47e1a4887 | `apps/frontend/src/lib/components/chat/AgentMarkdown.svelte` |
| [06-ApprovalCard.md](06-ApprovalCard.md) | Carte d'approbation outil, UX binaire | 80 | sha256: da3eb8d730918e6b944c93c8ddc46dcff3fbb730667bf5744aed09e4ccc041c5 | `apps/frontend/src/lib/components/chat/ApprovalCard.svelte` |
| [07-ChatPanel.md](07-ChatPanel.md) | Panneau chat principal, SSE, streaming, consentement, tool cards | 1007 | sha256: a7f6fe86917562656cfb648fc0cedd4aee17ad17a02757e8e4b2e51aa7b29a64 | `apps/frontend/src/lib/components/chat/ChatPanel.svelte` |
| [08-ConsentementGratuit.md](08-ConsentementGratuit.md) | Bannière consentement mode gratuit, versionné | 84 | sha256: fe576cf96f9a6b177a96c15f9ad754d4caed6acb56b0deb62cd0e2d89019acee | `apps/frontend/src/lib/components/chat/ConsentementGratuit.svelte` |
| [09-ToolCard.md](09-ToolCard.md) | Carte d'appel outil, état, erreur, extraits | 111 | sha256: e877845dc00c89578ad2267ded8ab26d9aef66da2586afe4531e18bb518609db | `apps/frontend/src/lib/components/chat/ToolCard.svelte` |
| [10-agents-page.md](10-agents-page.md) | Page gestion clés API, CRUD providers, test clé | 486 | sha256: 3a05f7220681bd4c0c3ecb89c56288e112307d736d809eb87ce857fa89ac57b2 | `apps/frontend/src/routes/dashboard/agents/+page.svelte` |
| [11-chat-page.md](11-chat-page.md) | Page nouvelle conversation, sidebar sessions | 154 | sha256: 1fdbe18f9e9e8a83176e292ad4700a379defc8f015a4c59547f7d387d1816f80 | `apps/frontend/src/routes/dashboard/chat/+page.svelte` |
| [12-chat-id-page.md](12-chat-id-page.md) | Page conversation existante, renommage inline | 96 | sha256: 51c9a068da369d10ea79375d4e26609398dc4d864b2026cfc78d1e53294231a5 | `apps/frontend/src/routes/dashboard/chat/[id]/+page.svelte` |

## Invariants du lot

- **Pas de `{@html}`** : `AgentMarkdown` utilise `marked.parse()` + re-échappage via texte brut — aucun `innerHTML` ou `{@html}` dans le composant (`apps/frontend/src/lib/components/chat/AgentMarkdown.svelte:1`).
- **Repli SSE** : `toChatItems()` fait la ponte entre les événements SSE bruts (text, tool_call, tool_result, approval_request) et les `ChatItem` typés du UI (`apps/frontend/src/lib/agent/conversation.ts:1`).
- **Client BYOK** : `agentApi` ne porte jamais de clé en dur — tout appel passe par `getApiBase()` + header `Authorization` optionnel (`apps/frontend/src/lib/api/agent.ts:1`).
- **Traduction outils** : `rendreOutil()` mappe les noms techniques MCP en labels人文 français, avec fallback sur le nom brut (`apps/frontend/src/lib/agent/toolLabels.ts:1`).
- **Consentement gratuit** : `ConsentementGratuit` vérifie `version_warning` côté client avant d'afficher la bannière (`apps/frontend/src/lib/components/chat/ConsentementGratuit.svelte:1`).
- **Navigation sans démontage** : `chat/+page.svelte` utilise `history.replaceState()` pour changer l'URL sans démonter `ChatPanel` et couper le SSE en cours (`apps/frontend/src/routes/dashboard/chat/+page.svelte:136`).

## Dettes et pièges constatés à la lecture

- **Regex symboles** : `check_lot.sh` utilise `grep -oE '^(async def|def|class) [A-Za-z_]+'` — ne capture pas les chiffres. Les symboles comme `calculer_sha256` apparaissent tronqués (`calculer_sha`) dans les rapports spot-check.
- **Spot-check bug** : `spot_check.sh` ligne 36 a un bug arithmétique (seed concaténé au numéro de ligne). Les items générés sont corrompus — workaround : créer le spot-check manuellement via `cat > ... << 'EOF'`.
- **ToolCard 0 symboles** : le composant ne contient que des `$derived` et `$state` réactifs — pas de fonctions nommées exportées. Le compteur du CSV est 0, ce qui est correct.
- **ChatPanel 1007 LOC** : c'est le fichier le plus volumineux du lot. Il gère le SSE streaming, l'affichage des messages, le consentement gratuit, et la sélection de provider — un couplage élevé qui pourrait bénéficier d'une décomposition.
- **`agents/+page.svelte` 486 LOC** : page CRUD complète avec formulaire dynamique, test de clé, et confirmation de suppression — gros fichier mais logique contained.

## Annexe — Symboles non-exportés (vérification par check_lot.sh)

**conversation.ts** : `cloturerSansReponse`, `lireJson`, `trouverDernier`, `remplacer`
**markdown.ts** : `MOTIF_INLINE`, `RE_TITRE`, `RE_SEPARATEUR`, `RE_ITEM_PUCE`, `RE_ITEM_NUMERO`, `RE_CITATION`
**toolLabels.ts** : `ArgMap`, `Rendu`, `titreDepuisResultat`, `ACTIONS`, `UUID_RE`, `tronquer`
**agent.ts** : `parseEvent`
