# 16 — Le déclencheur d'adoption : premières utilisations, premières ventes

> Ce document répond à une seule question : **qu'est-ce qui fait que quelqu'un se dit « ah oui, j'ai vraiment besoin de ça » ?** Il distingue le déclencheur d'*usage* (créateurs, gratuit) du déclencheur d'*achat* (premium et cercle 2). Rédigé le 2026-07-14, après livraison des trois briques d'acquisition (waitlist, seed & claim, serveur MCP).

---

## Thèse centrale

Philum ne sera pas adopté parce que c'est « beau » ou « bien fait ». La carte interactive est un différenciateur, pas un déclencheur. Le déclencheur, c'est un **moment de vulnérabilité publique** : l'instant où un créateur est contesté sur la solidité de son travail et n'a **rien à brandir en une seule action**.

Aujourd'hui, quand Léa (persona principal) est attaquée en commentaire ou sur X — « source ? », « c'est du cherry-picking », « t'as inventé ce chiffre » — elle a deux options, toutes deux perdantes :

1. Répondre par un pavé de liens que personne ne lira (et qui peut être mort : link rot).
2. Ne pas répondre, et laisser le doute s'installer.

**Philum lui donne une troisième option : un seul lien, qui écrase le débat.** Une URL qui montre en un coup d'œil 14 sources, dont 6 peer-reviewed, toutes archivées et horodatées *avant* la polémique. L'horodatage est la clef : il prouve que le sourçage précède l'attaque, pas qu'il a été bricolé après coup.

> Le « aha moment » n'est donc pas à la création de la fiche. Il est à la **première fois qu'un créateur colle son lien Philum en réponse à une contestation** — et que la contestation s'arrête.

Corollaire produit : tout ce qui raccourcit le délai entre l'inscription et ce premier moment défensif est prioritaire. Tout le reste (export PDF, thèmes, badges…) est secondaire.

---

## Déclencheur n°1 — usage créateur : « l'assurance réputationnelle »

### Ce que le créateur achète vraiment (même en gratuit)

Du temps et de la sérénité. Léa passe une journée à sourcer chaque vidéo ; ce travail est invisible et ne la protège de rien. Philum convertit ce coût déjà payé en **actif défensif permanent**. C'est le même ressort psychologique qu'une assurance : on ne s'inscrit pas pour le jour où tout va bien.

### Les trois conditions du déclenchement

1. **La preuve doit être antérieure au litige.** D'où l'archivage Wayback + horodatage + attestation signée `(creator_id, content_url, attested_at)` (ADR-019). Sans antériorité prouvable, la fiche n'est qu'une jolie liste de liens.
2. **La preuve doit être lisible en 5 secondes par un tiers hostile.** Le bandeau de stats (n sources, n peer-reviewed, n archivées) fait le travail avant même le graphe. Le sceptique de passage ne lira jamais 14 sources ; il lira « 14 sources · 6 peer-reviewed · archivées ».
3. **Le geste doit tenir en une action.** Copier un lien. Pas « va voir ma description », pas un thread.

### Comment déclencher *la première* utilisation (amorçage)

Le problème du cold start : le moment défensif est imprévisible, on ne peut pas attendre que chaque créateur se fasse attaquer. Les trois briques livrées attaquent ce problème par trois angles :

| Brique | Ressort psychologique | Effet attendu |
|---|---|---|
| **Seed & claim** (PR #113) | Effet de dotation : « votre fiche existe déjà, elle est belle, réclamez-la » | Supprime le coût de création pour les 20-50 premiers créateurs ciblés. On ne leur demande pas de travailler, on leur montre un actif qui leur appartient déjà. |
| **Serveur MCP** (PR #114) | Peur de la mal-citation par les IA : « les assistants IA citent déjà vos sources — correctement ou pas » | Donne une raison d'exister *avant* toute audience humaine : la fiche est lisible par les agents IA le jour 1. Argument différenciant pour les vulgarisateurs tech/science, sensibles au sujet. |
| **Waitlist** (PR #112) | Preuve sociale + rareté | Capture l'intention des visiteurs de fiches seed avant que le produit soit ouvert à tous. |

Le pitch d'amorçage qui découle de la thèse (pour les DM/emails de seed) n'est **pas** « transformez votre bibliographie en belle fiche » mais :

> « La prochaine fois qu'on vous demande "source ?", répondez avec un seul lien. On a déjà préparé le vôtre : [lien fiche seed]. »

---

## Déclencheur n°2 — premières ventes

### Qui paie, et pourquoi (dans l'ordre réaliste)

**Vague 1 — créateurs premium (faible ARPU, valide le modèle).**
Le créateur gratuit se sert de Philum comme bouclier. Il passe premium le jour où il voit **la preuve chiffrée que le bouclier sert** : analytics de consultation de fiche (qui a ouvert la fiche, depuis quel réseau, combien de sources cliquées), alertes de citation (« votre fiche a été consultée 340 fois depuis le thread de X »), et alertes de link rot (« 2 de vos sources ont disparu du web ; l'archive Philum les couvre »). Le déclencheur d'achat est le **premier pic de trafic défensif** : le jour où sa fiche encaisse une polémique, le créateur veut voir les chiffres — c'est ce jour-là qu'on lui présente le paywall analytics. Vendre l'analytics *avant* ce pic ne marche pas (pas de douleur) ; le vendre *pendant* est trivial.

**Vague 2 — organisations (ARPU réel : médias, fact-checkers, institutions).**
Une rédaction ou une cellule de fact-checking n'achète pas de la visibilité, elle achète de la **conformité et de l'outillage** : attestations en volume via API, pages-identité vérifiées pour ses journalistes, export des chaînes de provenance. Le déclencheur est réglementaire et réputationnel (DSA, AI Act, chartes de déontologie) : « prouvez que vos contenus étaient sourcés au moment de la publication ». Ici, le serveur MCP et l'API publique sont l'argument d'entrée : une infrastructure de provenance que leurs propres outils IA peuvent interroger.

**Vague 3 — plateformes et moteurs IA (le pari long, cercle 2).**
Les moteurs de réponse IA hallucinent leurs citations ; c'est un risque produit et juridique pour eux. Philum leur vend un **registre de provenance interrogeable** (le MCP en est le prototype gratuit). Cette vague ne se déclenche que si les vagues 1-2 ont créé un corpus de fiches suffisant pour que le registre ait une valeur de couverture. C'est un objectif de série A, pas de MVP.

### Le fil qui relie les trois vagues

À chaque étage, ce qui est vendu est la même chose : **l'antériorité prouvable**. Le créateur prouve qu'il avait sourcé avant la polémique ; le média prouve qu'il avait vérifié avant la publication ; la plateforme prouve qu'elle citait une source vérifiée avant la réponse générée. La fonctionnalité technique sous-jacente (attestation signée + archive horodatée) est déjà dans le MVP — les ventes successives ne sont que des emballages différents du même actif.

---

## Ce que ça implique concrètement (priorités dérivées)

1. **Instrumenter le moment défensif.** Sans mesure, pas de paywall au bon moment. Métriques minimales : referrer des visites de fiche (détecter les pics venant de X/YouTube/Reddit), taux de clic sur les sources, consultations d'archive. C'est le prérequis de la vague 1.
2. **Le bandeau de stats de la fiche publique est l'écran le plus important du produit** — pas le graphe. Il doit convaincre un sceptique hostile en 5 secondes. Toute itération design doit être jugée sur ce critère.
3. **Le pitch de seed doit être défensif, pas esthétique.** Tester les deux messages en DM (« belle fiche » vs « répondez avec un seul lien ») sur les premières cibles et mesurer le taux de claim.
4. **Ne pas vendre trop tôt.** Le gratuit doit rester assez généreux pour que le bouclier fonctionne sans payer (principe fondateur n°5). On monétise la *mesure* de l'efficacité du bouclier, jamais le bouclier lui-même.
5. **Le MCP est un canal d'acquisition, pas (encore) un produit.** Sa métrique de succès en phase MVP : nombre de fiches servies à des agents IA, et mentions « source : Philum » observées dans des réponses d'assistants.

---

## Risques sur cette thèse

- **Le moment défensif est rare pour les petits créateurs.** Un créateur à 5k abonnés se fait peu attaquer. Mitigation : la cible MVP (vulgarisateurs science/climat/santé) est précisément la population la plus exposée aux contestations, quelle que soit sa taille.
- **La preuve d'antériorité peut être contestée** (« il a antidaté »). Mitigation : l'archive Wayback est un tiers indépendant ; l'horodatage qualifié eIDAS (phase ultérieure) fermera ce débat.
- **Le réflexe « un lien qui écrase le débat » doit s'apprendre.** Personne ne cherche « assurance réputationnelle pour créateur » sur Google. L'acquisition passera par l'exemple visible (fiches partagées pendant des polémiques réelles), pas par le SEO. D'où l'importance de recruter en seed 2-3 créateurs régulièrement au contact de controverses.
