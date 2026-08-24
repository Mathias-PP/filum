# 2026-08-22 — Modèles économiques des produits qui embarquent une IA payante

> **Objet** : cartographier comment les produits SaaS qui embarquent des agents ou chats IA
> accèdent aux modèles, quels modèles ils servent, quelle valeur ajoutée ils revendiquent
> sur les APIs directes, s'ils font de la marge sur l'inférence, et comment ils structurent
> leur pricing. Objectif : nourrir la décision produit Philum entre BYOK strict, forfait
> tout inclus, add-on à seat, crédits mesurés, mode découverte sponsorisé.
>
> **Verdict** : cinq patterns observés, un seul soutenable pour un CMS de la taille de
> Philum → **BYOK pass-through + mode découverte plafonné**. Les autres patterns (forfait
> plat inclusif, add-on à seat, effort-based opaque) ont soit un problème de marge
> documenté, soit une adoption défaillante, soit un backlash public.
>
> **Méthode** : synthèse d'une recherche web (2026-08-22) sur 18 produits représentatifs.
> Toutes les affirmations chiffrées sont sourcées. Les prix sont ceux publiés au
> 2026-08-22 et bougent chaque mois — vérifier avant décision d'implémentation.

---

## 1. Panorama des 18 produits étudiés

| Produit                     | Modèle d'accès                                               | Modèles servis                                                  | Prix principal                                         | Marge connue / signal                                             |
| --------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------------- |
| **Cursor Pro**              | Forfait + pool d'usage à prix API pass-through               | Composer/Grok maison + Claude, GPT, Gemini                      | 20 $/mois (20 $ d'API inclus)                          | Marge fine sur inclus                                             |
| **Cursor Teams**            | Seat + overage prix API + « Cursor Token Rate » 0.25 $/M tok | Idem                                                            | 40 $/seat (Premium 120 $)                              | Frais 0.25 $/M sur toute requête tierce, y compris BYOK           |
| **GitHub Copilot Business** | Seat + AI Credits (1 crédit = 0.01 $)                        | GPT-5, Claude, Gemini via multi-model                           | 19 $/user, 1 900 crédits inclus                        | Historique WSJ 2023 : perte ~20 $/user ; pivot 2026 vers crédits  |
| **GitHub Copilot Pro**      | Seat plat, quota                                             | Idem                                                            | 10 $/mois                                              | Perte documentée (WSJ)                                            |
| **Windsurf Pro**            | Quota rechargeable (Flow Actions)                            | GPT-5, Claude Sonnet 4.6, Gemini 3.1, SWE-1 maison              | 20 $/mois                                              | Non publié ; quota abaisse le risque                              |
| **Zed Pro**                 | BYOK gratuit + hosted en overage +10 %                       | Claude Sonnet 5 promo, autres via provider                      | 10 $/mois (5 $ de crédit hosted)                       | Marge nette 10 % sur hosted, zéro sur BYOK                        |
| **Replit Core**             | Effort-based, crédits mesurés                                | Anthropic majoritaire                                           | 20 $/mois (20 $ inclus)                                | Marge cachée dans le « effort » auto                              |
| **Notion AI (Business)**    | Bundlé au seat                                               | 12 modèles (Anthropic, OpenAI, Google, xAI, Moonshot, DeepSeek) | 20 $/seat                                              | Custom Agents facturés 10 $/1 000 crédits (l'inclus a une limite) |
| **Linear**                  | Seat + BYO AI credits séparés                                | Agents multi-provider                                           | 16 $/user Business                                     | Ne prend pas la marge IA, la refile                               |
| **Slack AI**                | Bundlé Business+ (add-on 20 $ retiré Q2 2025)                | Stack Salesforce/Anthropic                                      | 15 $/user Business+                                    | Retrait de l'add-on = signal d'échec                              |
| **M365 Copilot**            | Add-on plat sur licence M365                                 | GPT-5, Anthropic                                                | 30 $/user (SMB 21 $)                                   | Adoption 2-3 % de la base 450 M ; ROI contesté (Forbes)           |
| **ChatGPT Plus**            | Forfait plat + caps                                          | GPT-5.x propriétaire                                            | 20 $/mois, ~160 msg/3h                                 | Altman : Pro perd de l'argent (déclaration publique)              |
| **ChatGPT Business**        | Forfait plat, soft caps                                      | GPT-5.x                                                         | 20 $/seat annuel                                       | Baisse de -5 $ en avril 2026 = pression concurrentielle           |
| **Claude Pro/Max**          | Forfait + session cap + weekly cap                           | Sonnet/Opus/Haiku/Fable                                         | 17-200 $/mois                                          | Caps hebdo introduits 2025 = surcoût inférence                    |
| **Perplexity Pro**          | Forfait + 5 $ API credit Sonar (supprimé 2026)               | Sonar maison + frontier                                         | 20 $/mois, 20 Deep Research/j                          | Cap Deep Research = coût plafonné                                 |
| **Poe**                     | Points multi-modèles, 6 paliers                              | Tout catalogue via APIs                                         | 5 → 249.99 $/mois                                      | Pass-through mesuré, marge sur volume                             |
| **OpenRouter**              | BYOK pass-through, fee 5.5 % sur recharge crédits            | Tout catalogue                                                  | Gratuit ; 5.5 % achat carte, 5 % BYOK au-delà 25 k$/mo | Marge visible et cadrée : 5-5.5 %                                 |
| **Jasper**                  | Forfait plat, output « illimité »                            | GPT/Claude/Gemini                                               | 39-59 $/mois                                           | Guardrails fair-use ; marge sur volume rédactionnel               |

## 2. Cinq patterns économiques observés

### Pattern 1 — BYOK pass-through, marge sur la commodité (aggregators)

OpenRouter : **pas de markup au token**, 5.5 % sur achat crédits par carte et 5 % sur BYOK
au-delà de 25 k$/mois. Together, Fireworks, Vercel AI Gateway suivent le même modèle. La
valeur revendiquée est le routing multi-provider, la facturation unifiée, un failover
transparent. **Zed** est un cas hybride intéressant : BYOK **totalement gratuit** dans son
IDE, hosted à +10 % pour ceux qui ne veulent pas gérer leurs clés.

### Pattern 2 — Forfait plat avec caps mous (chat grand public)

ChatGPT Plus 20 $, Claude Pro 20 $, Perplexity Pro 20 $. **Le prix a convergé** à 20 $/mois.
La différenciation ne se fait plus sur le prix mais sur les caps :

- Claude est passé à cap **hebdomadaire** en plus du cap 5 h en 2025.
- ChatGPT annonce ~160 messages / 3 h.
- Perplexity plafonne à 20 Deep Research / jour.

Ces caps sont l'aveu implicite que **le forfait plat ne couvre pas un power user au coût API**.

### Pattern 3 — Add-on à seat plat (productivité entreprise)

Notion (bundle Business 20 $), Slack (bundle Business+ 15 $, ex add-on 20 $ retiré),
M365 Copilot 30 $ add-on. Le mouvement 2025-2026 est clair : **les add-ons IA standalone
à 20-30 $ ont échoué en adoption**, et les vendeurs les rebundlent dans le tier supérieur.
M365 Copilot reste en add-on mais avec **2-3 % d'adoption seulement** sur la base 450 M
utilisateurs (source Forbes/EPCGroup).

### Pattern 4 — Crédits mesurés / effort-based (agents intensifs)

GitHub Copilot est passé de « premium requests » à **AI Credits** (1 crédit = 0.01 $) au
1er juin 2026. Business : 1 900 crédits inclus dans les 19 $. Replit facture par « effort »
décidé après coup par l'agent. Cursor Teams facture un **« Cursor Token Rate » de
0.25 $/M tokens** sur toute requête tierce (y compris BYOK). Notion facture les Custom
Agents 10 $/1 000 crédits. Le pattern gagne partout où l'agent est **long-running** et
l'inférence lourde.

**Backlash Replit** : l'effort-based est perçu comme opaque (le coût n'est connu qu'après
l'exécution), toxique pour un utilisateur qui veut prédire sa facture.

### Pattern 5 — Freemium + usage overage (hybride)

Cursor Pro 20 $ inclut **20 $ d'API à prix pass-through**, puis overage au prix API.
Windsurf Pro 20 $ avec quotas qui se rechargent. Perplexity Pro incluait 5 $ Sonar
(supprimé 2026). Le forfait couvre l'usage médian, l'overage débloque les power users
sans les subventionner.

## 3. Signaux financiers publics à retenir

- **WSJ, octobre 2023** : Copilot perdait ~20 $/user/mois en moyenne, jusqu'à 80 $ pour
  certains. Chiffre non actualisé publiquement, mais le **pivot Copilot vers crédits mesurés
  en 2026** est cohérent avec un problème de marge non résolu.
- **Sam Altman a reconnu publiquement** que ChatGPT Pro à 200 $/mois perd de l'argent.
- **Slack retire son add-on IA 20 $ en Q2 2025** et le bundle dans Business+ à 15 $.
- **ChatGPT Business baisse de -5 $ en avril 2026** = pression concurrentielle Anthropic.
- **M365 Copilot : 2-3 % d'adoption** malgré 450 M d'utilisateurs éligibles = plafond
  clair pour un add-on IA à 30 $.

## 4. Cinq recommandations pour Philum

### R1 — Garder BYOK en socle par défaut, gratuit, sans markup

**Validé par** : Zed (BYOK gratuit), OpenRouter (5.5 % seulement sur achat crédits),
Cursor (BYOK autorisé).

Philum est un CMS scientifique, pas un aggregator ; le BYOK est un signal de bonne foi et
évite d'avoir à gérer trésorerie IA. Le public sérieux (chercheurs, éditeurs, créateurs de
contenu long) a déjà des clés OpenAI/Anthropic/Gemini. L'archi Philum est déjà là (`AgentProvider`,
`KeyManager`, `MODELES_RECOMMANDES`).

### R2 — Ne PAS construire de « forfait tout inclus IA » en 2026

**Contre-indiqué par** : GitHub Copilot (perte de 20 $/user documentée), ChatGPT Pro
(Altman confirme perte), Slack (add-on retiré), M365 Copilot (2-3 % d'adoption).

Un forfait plat inclusif est un **contrat asymétrique** : les gros utilisateurs le
rentabilisent, les petits le subventionnent, et l'adoption des petits ne compense pas les
gros. Philum n'a ni le pricing power d'OpenAI ni la base captive de Microsoft. Le forfait
inclusif est un piège de trésorerie.

### R3 — Si un plan payant Philum arrive, préférer crédits mesurés en overage

**Validé par** : Cursor (20 $ inclus au prix API, puis overage), Notion Custom Agents
(10 $/1 000 crédits séparés), Copilot (AI Credits 0.01 $ chacun), Zed (+10 % sur hosted).

L'usage IA passe en **ligne séparée** du plan Philum ; on ne « vend » pas l'IA, on la
refacture avec un léger frais de service (5-10 %, cf. Zed +10 % et OpenRouter 5.5 %). Cela
protège la marge et rend la facture lisible. **Éviter l'effort-based à la Replit** (backlash
documenté, opacité toxique — en science, l'utilisateur veut prédire son coût, pas le
découvrir).

### R4 — Mode découverte plafonné et sponsorisé, court et honnête

**Validé par** : OpenRouter (50 requêtes/jour gratuites sous 10 $ de crédit), Windsurf
Free (25 Cascade actions/mois), Perplexity Free (3 Pro/jour).

Un utilisateur qui n'a jamais essayé un agent BYOK ne saura pas configurer une clé.
Sponsoriser **10-20 tours d'agent gratuits par nouveau compte**, sur un modèle bon marché
(Haiku, Gemini Flash, DeepSeek), coûte 0.05-0.20 $ par onboarding, mesurable et budgétable.
Après le plafond, message clair : _« collez votre clé, on garantit zéro markup »_.

Décision déjà tracée dans [a-copier-adapter-ameliorer-harness](2026-08-21-a-copier-adapter-ameliorer-harness.md)
sous l'item A11 (P1-P2) ; cette étude la confirme.

### R5 — Publier la structure de coût IA, la nommer « pass-through »

**Validé par** : OpenRouter (transparence 5.5 % affichée), Zed (documente le +10 % sur
hosted), Linear (dit explicitement « no plan includes AI credits »).

C'est un **différenciateur défendable** : le marché est fatigué des add-ons opaques (WSJ
Copilot, backlash Replit effort-based, retrait add-on Slack). Le positionnement _« votre
clé, votre facture chez OpenAI/Anthropic, nous ne prenons rien dessus »_ est rare chez les
CMS et cohérent avec la mission Philum (confiance créateur-audience, [mémoire mission](../memory/INDEX.md)).

## 5. À éviter explicitement

- **Effort-based à la Replit** : opacité toxique en science où l'utilisateur veut prédire
  son coût.
- **Forfait plat inclusif** : perte assurée, cf. les 5 exemples publics documentés.
- **Add-on IA standalone à 20-30 $** : Slack et M365 montrent le plafond d'adoption.
- **Markup silencieux sur BYOK** : Cursor Teams 0.25 $/M sur toute requête tierce est
  perçu comme une taxe cachée par sa communauté.

## 6. Sources vérifiées 2026-08-22

- [Cursor Models & Pricing](https://cursor.com/docs/models-and-pricing)
- [Vantage — Cursor Pricing Explained](https://www.vantage.sh/blog/cursor-pricing-explained)
- [GitHub Docs — Billing for Copilot](https://docs.github.com/en/copilot/concepts/billing/organizations-and-enterprises)
- [CloudZero — GitHub Copilot cost 2026](https://www.cloudzero.com/blog/github-copilot-cost/)
- [Windsurf Pricing 2026 — Baeseokjae](https://baeseokjae.github.io/posts/windsurf-pricing-guide-2026/)
- [LowCode — Windsurf Pricing & Credits](https://www.lowcode.agency/blog/windsurf-pricing)
- [Notion AI Pricing 2026 — FelloAI](https://felloai.com/notion-ai-pricing/)
- [Notion AI — Fayedtion](https://fayedtion.com/notion-ai-guide/)
- [ChatGPT Enterprise Pricing — Inference.net](https://inference.net/content/chatgpt-enterprise-pricing/)
- [ChatGPT Limits 2026 — Northflank](https://northflank.com/blog/chatgpt-usage-limits-free-plus-enterprise)
- [Claude Pricing 2026 — CloudZero](https://www.cloudzero.com/blog/claude-pricing/)
- [Claude Plans & Pricing officiel](https://claude.com/pricing)
- [Perplexity Pricing 2026 — FelloAI](https://felloai.com/perplexity-pricing/)
- [M365 Copilot Pricing EPCGroup](https://www.epcgroup.net/microsoft-365-copilot-pricing-licensing-enterprise-guide-2026)
- [Forbes — Microsoft AI adoption Copilot](https://www.forbes.com/sites/petercohan/2026/03/28/microsofts-36-slide-reveals-a-deeper-ai-problem/)
- [OpenRouter Hidden 5.5 % Fee — ofox.ai](https://ofox.ai/blog/openrouter-pricing-hidden-markup-breakdown-2026/)
- [OpenRouter Pricing — Omid Saffari](https://omidsaffari.com/blog/openrouter-pricing)
- [Linear AI Agents Guide — BuildBetter](https://blog.buildbetter.ai/linear-ai-agents-2026-guide-5-alternatives-for-engineering-teams/)
- [Slack Pricing 2026 — UseCarly](https://www.usecarly.com/blog/slack-pricing/)
- [Zed Pricing 2026 — YixScout](https://yixscout.com/resources/columns/zed-pricing)
- [Zed Hosted Models docs](https://zed.dev/docs/account/zed-hosted-models)
- [Replit Effort-Based Pricing](https://blog.replit.com/effort-based-pricing)
- [Replit Agent Pricing — UseCarly](https://www.usecarly.com/blog/replit-agent-pricing-explained/)
- [Poe Purchases FAQ officiel](https://help.poe.com/hc/en-us/articles/19945140063636-Poe-Purchases-FAQs)
- [TechCrunch — Poe 5 $ plan](https://techcrunch.com/2025/03/25/quoras-poe-now-offers-an-affordable-subscription-plan-for-5-month)
- [Neowin — Microsoft losing money Copilot WSJ](https://www.neowin.net/news/microsoft-reportedly-is-losing-lots-of-money-per-user-on-github-copilot/)
- [Thurrott — Copilot -20 $/user report](https://www.thurrott.com/cloud/290661/report-github-copilot-loses-an-average-of-20-per-user-per-month)
- [Jasper Pricing DemandSage](https://www.demandsage.com/jasper-ai-pricing/)
