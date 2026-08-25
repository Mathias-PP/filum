# 2026-08-21 — Cherry Studio et modèles « en local » sur Philum

> **Objet** : à la demande produit, étude de Cherry Studio (`cherryhq/cherry-studio`,
> docs communautaires + fiche entreprise) pour (a) en tirer ce qui est copiable pour le
> harness BYOK Philum, (b) trancher la faisabilité de **brancher des modèles locaux
> (Ollama/LM Studio) sur Philum**.
>
> **Sources** : README GitHub (AGPL-3.0 community / Enterprise privé),
> `docs.cherry-ai.com` (page Ollama, présentation features). Vérifié le 2026-08-21.
> Complète `2026-08-21-a-copier-adapter-ameliorer-harness.md` (nuance apportée à A1).

---

## 1. Cherry Studio en bref

Client desktop **Electron** (Windows/Mac/Linux), « poste de travail IA tout-en-un » :

- **Providers** : services cloud majeurs (OpenAI, Gemini, Anthropic, Azure…), services
  web (Claude.ai, Perplexity, Poe…), et **modèles locaux via Ollama et LM Studio**.
- Gestion unifiée des providers : agrégation de modèles, **récupération automatique de
  la liste de modèles en un clic**, providers custom compatibles OpenAI/Gemini/Anthropic,
  et **rotation multi-clés** (« avoid rate-limit issues ») — voir arbitrage §4 du doc d'action.
- Agents (« Work » : fichiers, commandes, multi-étapes), MCP, bases de connaissances
  locales, multi-modèles simultanés sur une même question.
- Argument sécurité explicite : « usage 100 % local ; combiné aux modèles locaux,
  évite toute fuite de données ».
- Édition **Enterprise** : déploiement privé, gestion centralisée des modèles (cloud +
  modèles privés auto-hébergés), comptes employés, bases partagées — modèle « admin
  configure, les employés consomment sans rien configurer ».
- Licence : **AGPL-3.0** (community). ⇒ Le _code_ n'est pas incorporable dans Philum
  sans mise en conformité AGPL ; on s'inspire des **patterns**, pas du code.

## 2. Comment le local fonctionne chez Cherry Studio

La clé de voûte : **l'application tourne sur la machine de l'utilisateur**. L'app
parle directement à `http://localhost:11434` (Ollama) ou `:1234` (LM Studio). Pas de
SSRF, pas de CORS, pas de Private Network Access : une app native n'a aucune de ces
contraintes. Config documentée (page Ollama) :

1. Installer/lancer Ollama, télécharger un modèle (`ollama run llama3.2`).
2. Dans Cherry Studio : Settings → Model Services → Ollama → activer le provider.
3. Clé API **optionnelle** (champ vide ou n'importe quoi) ; adresse API par défaut
   `http://localhost:11434/` ; option _keep-alive_ (libère le modèle après N minutes
   d'inactivité) ; ajout/gestion manuelle des modèles téléchargés.

UX à retenir : zéro friction après installation d'Ollama, découverte des modèles,
aucune clé requise.

## 3. Le mur architectural pour Philum (et les 4 options)

**Philum est une application web où c'est le BACKEND (VM e2-micro) qui appelle les
providers** (`_appel_provider`). L'Ollama de l'utilisateur tourne sur _sa_ machine :
le backend distant ne peut joindre ni son loopback ni son réseau privé — quel que soit
l'opt-in SSRF. Conséquence directe : **A1 (loopback) ne sert qu'aux instances
self-hostées/développement** (backend co-localisé), pas aux créateurs du SaaS.

| Option                                                   | Principe                                                                                                                         | Faisabilité                                                                                                                                                                                                                                                                                                                                                                                                                                                 | Verdict                                                                                                                                                 |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **a) Tunnel HTTPS public**                               | L'utilisateur expose son Ollama via cloudflared/ngrok/Tailscale Funnel → URL HTTPS publique → kind `custom` Philum pointe dessus | **Marche dès aujourd'hui** (URL publique = passe `assert_url_is_safe`) ; frictions : installer l'outil + lancer une commande ; caveats : quick tunnels = URL changeante, et **exposition** : l'Ollama devient joignable publiquement pendant le tunnel (préférer tunnel avec auth/Access, URL aléatoire, durée courte ; le documenter clairement)                                                                                                           | ✅ Court terme : page doc « Brancher votre Ollama sur Philum » step-by-step. Aucun code requis (éventuellement un preset UI + accepter clé placeholder) |
| **b) Direct navigateur → localhost**                     | Le frontend (dans le navigateur de l'utilisateur, même machine) appelle lui-même `http://localhost:11434/v1/chat/completions`    | Deux obstacles : (i) **Private Network Access** : Chrome exige un préflight avec `Access-Control-Allow-Private-Network: true` que Ollama ne renvoie pas (`OLLAMA_ORIGINS` couvre CORS simple, pas PNA) — support inégal selon navigateurs/versions ; (ii) **architecture** : la boucle d'agent vit côté serveur (outils → DB, approbations, SSE) ⇒ il faudrait déléguer chaque tour d'inférence au navigateur (protocole callback lourd, streaming fragile) | ❌ Court terme. À surveiller (maturation PNA), réévaluer si demande forte                                                                               |
| **c) Philum self-hosté**                                 | docker-compose sur la machine/petit serveur de l'utilisateur ⇒ backend co-localisé avec Ollama                                   | A1 (opt-in loopback) suffit alors ; cible niche dev/équipes                                                                                                                                                                                                                                                                                                                                                                                                 | ✅ Via A1, priorité self-host                                                                                                                           |
| **d) App desktop Philum** (Electron, à la Cherry Studio) | App native sur la machine ⇒ localhost trivial, UX zéro-friction égale à Cherry Studio                                            | Projet produit majeur hors scope actuel                                                                                                                                                                                                                                                                                                                                                                                                                     | 🔭 Vision long terme ; garder en tête que c'est le seul chemin vers le « 100 % local grand public »                                                     |

**Conclusion locale** : pour le SaaS, la réponse honnête aujourd'hui est l'option (a)
— ça fonctionne immédiatement, avec une doc soignée et des avertissements d'exposition ;
pas de kind `ollama` dédié en SaaS (le kind `custom` couvre exactement ce cas).

## 4. Ce qu'on copie quand même de Cherry Studio (patterns, pas code — AGPL)

1. **Rotation multi-clés** : mainstream chez un client grand public populaire — renforce
   l'arbitrage §4 du doc d'action (différé mais justifié, déclencheur = signal 429).
2. **Clé optionnelle/placeholder** : notre validation exige `api_key` non vide
   (`min_length=1`) — gênant pour Ollama/tunnel qui ignore la clé. Copier : préremplir
   un littéral neutre (« ollama ») quand le kind/endpooint n'exige pas de clé, plutôt
   que forcer l'utilisateur à inventer une fausse clé.
3. **Récupération de modèles en un clic** : déjà fait chez Philum (`lister_modeles`)
   — validation externe de notre design.
4. **Presets visuels de providers** (carte par service avec logo, statut, adresse par
   défaut) : notre page Réglages #508 peut s'en inspirer pour la carte « Modèle local
   (avancé) » pointant vers la doc tunnel.
5. **Keep-alive et options spécifiques Ollama** : sans objet pour Philum (backend
   distant, connexions courtes) — ignorer.
6. **Pattern Enterprise « admin configure, l'équipe consomme »** : pertinent plus tard
   si Philum ouvre des espaces équipes (gestion centralisée des providers d'une orga).
   Noter, ne pas chiffrer.

## 5. Synthèse décisionnelle

- **Modèles locaux sur Philum SaaS** : oui via **tunnel + kind custom**, dès maintenant,
  moyennant documentation ; sinon impossible depuis le backend distant — à ne pas
  promettre dans l'UI tant que la doc tunnel n'existe pas.
- **A1 recentré** : self-host/dev uniquement (P0 self-host, non-bloquant SaaS).
- **Browser-direct** : non à court terme (PNA + architecture callback).
- **Desktop Philum** : vision long terme, seul égal réel de l'expérience Cherry Studio.
- **Copier** : rotation multi-clés (différée), clé placeholder, presets UI, doc tunnel
  inspirée du guide Ollama de Cherry Studio.

_Document écrit en lecture seule du dépôt (aucun commit — PR #512 sous le contrôle d'un autre agent)._
