# 2026-08-22 — firetower-cloud/firetower : control plane pour agents de codage

> **Objet** : évaluer si `firetower-cloud/firetower` (Rust + Next.js, AGPL v3, 6 stars,
> créé et maintenu actif au 2026-08-22) peut inspirer un ou plusieurs mécanismes du
> harness BYOK Philum.
>
> **Verdict** : projet **hors périmètre produit** (orchestrateur multi-hôte pour agents
> de développement) mais une seule idée mérite d'être piquée : le **pattern « approval
> inbox » avec notification hors-app**. Le reste (workers SSH, event log, mono-Docker
> Rust) est overkill pour l'échelle de Philum.

---

## 1. Firetower en bref

| Item        | Valeur                                                                              |
| ----------- | ----------------------------------------------------------------------------------- |
| URL         | https://github.com/firetower-cloud/firetower                                        |
| Licence     | AGPL-3.0                                                                            |
| Langage     | Rust (server/worker/CLI) + Next.js/TypeScript (web)                                 |
| Composants  | `ft-cli`, `ft-core`, `ft-proto`, `ft-server`, `ft-worker` + `web/`                  |
| Déploiement | Docker Compose mono-image, worker atteint via SSH / `docker exec` / stdin/stdout    |
| Slogan      | « Run any coding agent, on your own servers, from anywhere »                        |
| Cible       | Développeurs qui pilotent des agents Claude Code / autres depuis plusieurs machines |

**Modèle architectural annoncé** :

- **Control plane** : possède l'intention (hôtes, repos, credentials, planification).
- **Worker** : possède la réalité (event log, état). Écrit ses events **avant** de reporter, donc la session survit à une déconnexion.
- **Web** : présentée comme une **inbox** (boîte de réception) plutôt qu'un fleet monitor.

Le transport est abstrait : le worker lit des frames sur stdin/stdout. Peu importe qu'il tourne dans un `docker exec`, un `ssh`, ou un process enfant local.

## 2. Pertinence pour Philum, point par point

### 2.1 Approval inbox + notification hors-app — **la seule vraie idée à piquer**

Chez Firetower, un agent bloqué sur une décision humaine ne suspend pas la productivité de son utilisateur : la demande arrive dans une inbox web, et l'utilisateur y répond « depuis n'importe où ». La formulation dans le README est explicite : _« Agents block. You are the bottleneck. Firetower's job is to route their blocking to you — wherever you are — and get you back out fast. »_

**État Philum aujourd'hui** : un `approval_request` bloque le tour côté serveur ; l'utilisateur doit être sur l'onglet chat pour valider via `ApprovalCard`. S'il ferme l'onglet ou part 10 minutes, le tour reste suspendu et le stream SSE peut expirer. Pour les providers à quota strict (Gemini free tier), c'est une session perdue.

**Piste concrète** : sur émission d'un `approval_request`, envoyer une notification email (v1) puis web push (v2) avec un lien direct vers la carte d'approbation, TTL de la demande étendu (300 s → configurable). Peut-être aussi un rappel après N minutes.

**Effort** : S (email transactionnel via SMTP existant + template Markdown, endpoint dédié pour approuver depuis un lien signé).

**Priorité** : P1 — améliore réellement l'utilisation quotidienne, en particulier pour les agents longs.

### 2.2 Event log worker + reprise après déconnexion — piste théorique, coût prohibitif

Chez Firetower, la session survit à la coupure du client parce que le worker persiste les events **avant** de rapporter au control plane. Le control plane reconnecte plus tard et rejoue.

**État Philum aujourd'hui** : le tour SSE persiste **à la fin** dans `_persister_tour` (`agent_chat.py`). Si le client se déconnecte pendant le streaming, on peut argumenter que la boucle `boucle()` continue tant que le worker HTTP FastAPI n'est pas interrompu — mais le message assistant partiellement streamé n'est **pas** persisté tant que la boucle n'a pas rendu la main. Un simple reload de l'onglet en plein tour perd le contenu déjà émis.

**Piste théorique** : persister le tour de façon **incrémentale** (chaque `message_delta` en base ou en cache), permettre au client de se reconnecter avec `session_id + tour + offset` et rejouer les events manqués.

**Verdict** : refonte non triviale (schéma, endpoint de reprise SSE, coordination cache/base) pour un gain d'ergonomie marginal à l'échelle actuelle. À garder en veille, pas prioritaire.

### 2.3 Modèle « inbox » plutôt que « fleet monitor » — déjà fait

L'interface web comme boîte de réception d'items nécessitant une action est déjà le modèle mental du chat Philum (une carte d'approbation, une amorce, un résultat d'outil = un item). Rien à piquer côté UI.

### 2.4 Envelope encryption des credentials — déjà en place

Firetower revendique une chaîne de chiffrement enveloppe avec racine hors base. Philum a `KeyManager` (AES-GCM, clé maître hors base) depuis longtemps. Rien à piquer.

### 2.5 Workers SSH, transport stdin/stdout, mono-Docker Rust — hors sujet

Firetower est un orchestrateur multi-hôte pour agents de dev. Philum est un applicatif métier mono-serveur avec agent embarqué. Aucune brique n'est réutilisable.

## 3. Action recommandée

**Une seule action à mener**, sans urgence mais utile :

- **N1** : Notification email sur `approval_request`, avec lien signé vers la carte d'approbation, TTL configurable. **Effort S, Priorité P1.**

Le reste du projet Firetower est intéressant à connaître mais ne mérite pas d'inspiration architecturale pour Philum. Suivre à distance : si les auteurs stabilisent leur pattern d'event log worker, revisiter la piste §2.2 le jour où on voudra vraiment une reprise SSE robuste.

## 4. Références

- Repo : https://github.com/firetower-cloud/firetower
- README (analyse résumée dans ce doc) : `https://raw.githubusercontent.com/firetower-cloud/firetower/main/README.md`
