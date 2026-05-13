# 11 — Regard critique et améliorations suggérées

> Document de prise de recul. Lu en complément de [`10-mvp-completion-plan.md`](./10-mvp-completion-plan.md) (qui dit *quoi faire* maintenant) — celui-ci dit *ce qu'on pourrait faire mieux* et *quels arbitrages assumer ensuite*.
>
> Sert au développeur humain pour réviser sa propre vision, et à un agent autonome pour comprendre où il a le droit de suggérer des évolutions et où il doit s'abstenir.

---

## 1. Forces du projet — ce qu'il faut préserver

| Force | Pourquoi c'est précieux |
|---|---|
| **Vision claire et différenciante** | Filum se positionne comme un *label qualité positif*, pas un détecteur anti-deepfake. C'est rare et défendable. À ne pas diluer. |
| **Discipline documentaire** | 10 documents `.docs/`, 17 ADRs, `STATE.md` vivant, `DECISIONS.md` historique. C'est ce qui rend possible un dev solo + IA assistante sans perdre le fil. |
| **Crypto réelle, pas simulée** | Ed25519 + AES-GCM + SHA-256 dès le MVP. Permet une démo crédible auprès d'institutions sans refonte ultérieure. |
| **Stack cohérente et moderne** | FastAPI async + SvelteKit + DuckDB/dbt forment un signal Data Engineer fort. Pas de tech debt en démarrage. |
| **CI verte enforced** | 8 jobs verts, aucun `\|\| true`, dependabot actif. Le projet ne se dégrade pas silencieusement. |
| **MVP backend + frontend déjà déployés** | La plupart des projets meurent avant le déploiement. Filum a passé ce cap. |
| **Effet wow visuel** | Le graphe D3 sur `/@example/memoire-et-cerveau` justifie à lui seul la démo de 5 min. C'est le hook narratif. |
| **Sécurité prise au sérieux** | Trivy + TruffleHog + secrets baseline + dependency review. Au-dessus de la moyenne pour un MVP solo. |

**À ne pas casser** : la discipline ADR, le SSR sélectif, les variables d'env lowercase, la validation des fiches signées (canonical_hash payload immuable). Toute évolution doit conserver ces invariants.

---

## 2. Faiblesses identifiées — par criticité

### Bloquants pour le MVP (cf. [10-mvp-completion-plan.md](./10-mvp-completion-plan.md))

- **OAuth Google pas branché end-to-end** → aucun utilisateur tiers ne peut s'inscrire.
- **Auth guard absent sur `/dashboard*`** → la moindre interaction non-loggée crashe ou expose.
- **Extracteur backend isolé** → 30 % de la valeur UX du formulaire n'est pas livrée.

### Sérieuses mais non-bloquantes

- **Pas de rate limiting actif** sur l'extracteur public → vecteur DoS / coût Wayback à dimensionner.
- **Pas d'observabilité runtime** au-delà des logs Railway → un bug en prod prend des jours à voir.
- **Test composant Svelte 5 absent** → la couverture frontend est très partielle.
- **Pas de stratégie de backup BDD documentée** → un drop accidentel ou un OOM Railway coûte tout l'historique.

### Dettes dormantes

- **`impact_factor` toujours `null`** mais le champ est sérialisé : soit le supprimer de l'API tant qu'il n'est pas alimenté, soit brancher OpenAlex (qui avait été enlevé en dead code — pourquoi ?). État ambigu = signal cassé pour l'utilisateur final.
- **`authority_level` legacy** : encore en base et dans l'API mais plus utilisé en UI. Décider : drop avec migration ou documenter « champ legacy non-affiché ».
- **`apps/analytics/` (dbt + DuckDB)** présent mais inerte en runtime — uniquement `dbt compile` en CI. Joli pour le portfolio, mais entretient une dette qu'il faudra purger ou activer un jour.
- **Pas de tests E2E** (Playwright prévu en phase 2) → impossible de valider le flow OAuth en CI.
- **`SECURITY.md` mentionne « Fernet symmetric encryption »** alors que **ADR-009** acte le passage à AES-GCM. Cohérence à rétablir.
- **`SECURITY.md` mentionne « 1.x.x supported / 0.x.x EOL »** alors que le projet est en `0.1.0`. À corriger sinon ça envoie un mauvais signal en cas de rapport de vulnérabilité.

### Symptômes d'over-engineering

- **dbt + DuckDB à ce stade** : valeur portfolio claire, valeur produit nulle. À conserver pour le portfolio, mais ne **pas** dépenser de temps dessus avant d'avoir un signal utilisateur.
- **Architecture analytics anticipée** alors qu'il n'y a pas encore de volumétrie.
- **Page `/dashboard/new` en 2 étapes** alors qu'une seule pourrait suffire en MVP (à valider auprès des premiers utilisateurs).

---

## 3. Suggestions d'amélioration — par horizon

### Court terme (post-MVP immédiat)

1. **Compteur de vues basique** : un `INSERT` sur une table `card_views` à chaque hit SSR de `/@slug/card-slug`. Pas de cookie, pas de tracking, juste un compteur global par fiche. Donne un signal mesurable pour valider l'hypothèse 2 de la vision (« le lecteur clique »).
2. **Page d'accueil orientée action** : remplacer la home actuelle par « Voir un exemple → [fiche démo] » + « Demander un accès créateur → [formulaire Tally/typeform gratuit] ». Pas de promesse vide.
3. **Documentation utilisateur** : 1 page Notion ou GitHub Pages « Comment Filum marche, comment créer ta première fiche, pourquoi c'est gratuit ». Texte humain, pas marketing.
4. **Health page publique** : `/status` ou un Statuspage.io gratuit. Crédibilité auprès d'institutions.

### Moyen terme (phase 2, après 3-5 utilisateurs actifs)

5. **OAuth YouTube ou ORCID** : avant l'extraction IA. Permet de revendiquer un compte créateur officiel et d'afficher une vérification visible.
6. **OpenGraph image dynamique** : génère une preview riche pour le partage X/Bluesky/LinkedIn. C'est probablement ce qui fait la différence virale.
7. **Mode privé / unlisted** (cf. `09-private-mode-and-integrations.md`) : utile pour les premiers tests utilisateurs qui veulent jouer sans publier.
8. **Embed widget** : un `<iframe>` ou un `<script>` qu'un créateur colle dans son blog Substack/Ghost.

### Long terme (phase 3+)

9. **MCP server** pour exposer les fiches aux agents IA (Claude, Perplexity) comme source de vérité citable.
10. **C2PA en lecture** : pouvoir vérifier qu'une fiche Filum porte un cachet C2PA valide, sans nécessairement adhérer au consortium.
11. **API publique de vérification** : `GET /api/v1/verify?card_url=...` → retourne signature + hash + horodatage.
12. **Lineage descendant** : permettre à un créateur B de déclarer son contenu dérivé d'un contenu A (avec opt-out de A).

---

## 4. Arbitrages techniques à reconsidérer (avec contexte)

### A. Garder DuckDB + dbt ou les retirer ?

**Pour garder** : signal Data Engineer fort sur le portfolio, cohérence avec ADR-001, pas de coût direct (DuckDB embarqué, dbt compile en CI gratuit).

**Pour retirer** : code mort = surface d'attaque, deps à maintenir (mise à jour dbt parfois cassante), confusion pour un futur contributeur (« on est censé l'utiliser ? »).

**Recommandation** : **garder** mais isoler. Déplacer `apps/analytics/` dans une branche dédiée `experimental/dbt` jusqu'à ce qu'on ait des données réelles à analyser. Documenter clairement dans `README.md` que c'est dormant.

### B. Choix Railway → tenir ou migrer vers Render/Fly.io ?

**Railway aujourd'hui** : auto-deploy GitHub, Postgres inclus, Wait-for-CI, healthcheck natif → très bien.

**Risques** : tier gratuit limité à $5/mois ; en cas de hit volumétrique le service s'arrête.

**Recommandation** : **rester sur Railway** tant qu'on est en bêta privée. Migrer (si nécessaire) seulement quand on aura un cas d'usage qui dépasse $5/mois. Scaleway reste l'objectif phase 3 pour le narratif souverain.

### C. SvelteKit + SSR sélectif → bien dimensionné ?

**Aujourd'hui** : `+layout.ts` SSR off par défaut, `+page.ts` SSR on pour les pages publiques. C'est le bon compromis (CSR pour le dashboard, SSR pour le SEO/GEO).

**Limite** : difficile à maintenir mentalement. Risque d'erreur (oublier le `ssr=true` sur une nouvelle route publique).

**Recommandation** : ajouter dans `agent/skills/frontend-svelte.md` un mémo explicite « toute nouvelle route publique = `+page.ts` avec `ssr=true` ». **Ne pas** réécrire en mode SSR global (perte de bénéfices pour le dashboard interactif).

### D. Pas de tests E2E → tolérable ?

**Aujourd'hui** : tests unitaires backend solides (41 pytest), tests frontend minimaux (vitest source-colors), zéro E2E.

**Risque** : un flow critique (OAuth) qui casse en prod sans qu'aucun test ne le détecte.

**Recommandation** : ajouter **un seul** test Playwright qui exécute le scénario démo (visite fiche publique, vérifie présence du graphe). C'est suffisant pour détecter 80 % des régressions. Playwright complet attend phase 2.

### E. Pas de monitoring tiers (Sentry, Plausible, Logflare) → tolérable ?

**Aujourd'hui** : logs Railway (pas grep-able facilement), erreurs frontend dans console navigateur uniquement.

**Risque** : impossible de savoir si un utilisateur tiers a planté avant qu'il ne nous le dise.

**Recommandation** : pour le MVP, accepter cette cécité. **Mais** : ajouter un endpoint backend `POST /api/v1/_log/client-error` (no-auth, rate-limited) qui reçoit un payload minimal `{message, url, user_agent}` et le log côté backend. Le frontend l'appelle dans un `window.onerror`. Coût zéro, visibilité ×10.

---

## 5. Suggestions sur la vision / stratégie

### V1 — La cible « vulgarisateurs scientifiques » est-elle la bonne en MVP ?

Forces : audience engagée, valeur de sourçage immédiate, mesurable.

Faiblesses : très peu nombreux (~quelques dizaines de cibles primaires en France), tous très sollicités. Conversion difficile.

**Alternative à considérer** : viser les **fact-checkers indépendants** ou les **profs/docs scientifiques en collège-lycée**. Audience moins glamour mais besoin de sourçage encore plus mécanique et plus volumique.

**Pas de décision à prendre ici** — c'est une réflexion à confronter aux premiers retours utilisateurs. Mais éviter de bétonner la vision avant d'avoir testé.

### V2 — Le narratif « couche de citation du web » est-il prématuré ?

L'ambition longue (HTTPS de la provenance, fondation, etc.) est belle et juste, mais elle expose à deux risques :
- **Effet vaporware** si le MVP ne suit pas (commune dans le monde Web3/crypto).
- **Désalignement avec un investisseur ou un partenaire institutionnel** qui voudra du concret court terme.

**Recommandation** : garder la vision longue dans `00-vision.md` (référence interne), mais sur la home publique, parler uniquement de **« la bibliographie de tes vidéos enfin visible et archivée »**. Le narratif large viendra plus tard.

### V3 — La gratuité illimitée est-elle tenable ?

Le manifeste promet « gratuit pour les créateurs jusqu'à un seuil généreux ». OK mais à définir avant le premier vrai utilisateur.

**Proposition** : 50 fiches/mois gratuites + 1 GB de snapshots Wayback gardés en cache local. Au-delà, on demande un don ou un upgrade. Permet d'éviter qu'un seul gros utilisateur coule l'infra free-tier.

---

## 6. Risques à anticiper (qui ne sont pas dans STATE.md)

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| **Railway free tier coupe au bout du crédit** | Moyenne | Backend down | Passer en plan Hobby ($5/mois) dès le 1er utilisateur réel |
| **Postgres Railway plein (~1 GB)** | Faible court terme | Écriture cassée | Documenter une procédure de vacuum + archivage |
| **Wayback Machine en panne / rate limit** | Moyenne | Snapshots non créés | Retry exponentiel + fallback : marquer source « archivage en attente » sans bloquer la publication |
| **Cookie OAuth bloqué par un navigateur strict (Safari ITP)** | Élevée | Login cassé sur certains users | Tester sur Safari iOS dès la PR M1 |
| **Google révoque le projet OAuth** (TOS, abus) | Très faible | Login universel cassé | Documenter procédure de re-création |
| **Vercel coupe le free tier** (sortie de l'éducation, etc.) | Très faible | Frontend down | Procédure de bascule vers Netlify documentée |
| **Mathias-PP repo devient orphelin** (transfert d'org, etc.) | Faible | Liens cassés | Réserver `filum.org` GitHub org dès que possible |
| **Une fiche signée publiée révèle un bug crypto** | Faible | Crédibilité catastrophique | Le canonical_hash payload est gelé. Ajouter un test de vérification automatique sur la fiche démo dans la CI |

---

## 7. Ce que ce document n'est PAS

- Ce n'est **pas** un substitut au roadmap (`06-roadmap.md`) ni au plan opérationnel (`10-mvp-completion-plan.md`).
- Ce n'est **pas** une autorisation pour l'agent autonome de partir dans des refontes. Toute évolution mentionnée ici nécessite une décision humaine explicite avant exécution.
- Ce n'est **pas** une liste exhaustive. D'autres regards critiques (utilisateurs, contributeurs, mentors) doivent enrichir cette analyse au fil du temps.

---

*Mettre à jour quand un point devient obsolète (résolu, abandonné, repensé). Ne pas créer un `12-…md` parallèle ; éditer celui-ci.*
