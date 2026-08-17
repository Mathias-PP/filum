# Rapport UX — walkthrough des parcours utilisateurs

Date : 2026-07-11 · Méthode : navigation réelle (Chrome) sur https://filum-eight.vercel.app + lecture du code pour les parcours authentifiés (backend prod indisponible pendant le test).

## P0 — Infra (action manuelle requise)

**Le backend Railway est down.** Toutes les requêtes vers `filum-production-07bb.up.railway.app` renvoient `{"status":"error","code":404,"message":"Application not found"}` (vérifié en direct et via le proxy Vercel). Conséquences observées :

- La fiche démo `/@example/memoire-et-cerveau` → 404. C'est la vitrine du produit ; un visiteur qui suit le CTA de la home tombe sur une page d'erreur.
- « Se connecter » → page brute Railway « Not Found » (train ASCII). Dead-end total, aucun retour possible vers le site.
- Tous les parcours dynamiques (profils, fiches, dashboard) sont morts.

→ **À faire (par toi, je ne déploie pas)** : vérifier le service Railway (crash-loop ? domaine détaché ? projet suspendu ?). Le frontend statique, lui, est up.

## Parcours visiteur (testé en navigateur)

| #   | Constat                                                                                                                                                               | Gravité | Statut                                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | « Se connecter » envoie sur `/api/v1/auth/google/login` : si le backend est down, l'utilisateur atterrit sur une page d'erreur brute hors du site, sans bouton retour | Haute   | ✅ Fix partiel : le proxy renvoie maintenant un 503 JSON propre (`backend_unreachable`) au lieu de crasher ; la page brute Railway reste possible sur les redirections navigateur — dépend du fix infra |
| 2   | Typo « vulgaristeur » sur /about — crédibilité d'un produit dont le cœur est la rigueur                                                                               | Basse   | ✅ Corrigé                                                                                                                                                                                              |
| 3   | Fiche démo 404 (backend down)                                                                                                                                         | Haute   | Infra                                                                                                                                                                                                   |

## Parcours créateur (audité via le code — non testable en prod)

| #   | Constat                                                                                                                                                                                                                 | Gravité | Statut                                                                                |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------- |
| 4   | Les deux pages du wizard (`/dashboard/new` et `/dashboard/new/[id]/sources`) utilisaient des couleurs codées en dur (`bg-white`, `slate-*`) : **illisibles en dark mode** alors que tout le reste de l'app a des tokens | Haute   | ✅ Migré vers les tokens `ink-*`/`surface-*`/`border`/`danger`/`info`                 |
| 5   | Après publication, `goto('/dashboard')` : l'utilisateur ne voit jamais sa fiche publiée, aucun lien à partager. Le moment de récompense est raté                                                                        | Haute   | ✅ Redirection vers la page publique de la fiche (`public_url` renvoyée par l'API)    |
| 6   | Message d'erreur de publication en dev-speak : « Ouvre la console (F12 → Network)… » — incompréhensible pour un créateur non-technicien                                                                                 | Moyenne | ✅ Reformulé (le brouillon est conservé, réessayer)                                   |
| 7   | Suppression d'une source **sans confirmation** — un clic à côté du bouton Modifier et la source part (avec son annotation)                                                                                              | Moyenne | ✅ `ConfirmDialog` (déjà utilisé pour la suppression de fiche — incohérence corrigée) |
| 8   | Préfixe slug « `/@vous/` » au lieu du vrai username : l'utilisateur ne sait pas quelle URL il crée                                                                                                                      | Basse   | ✅ Affiche `/@{username}/` réel                                                       |

## Recommandations non implémentées (à discuter)

- **Route `/login` dédiée** : aujourd'hui le seul point d'entrée auth est le lien direct vers l'API. Une page `/login` avec bouton Google + explication du pourquoi (signature des fiches) serait plus rassurante et survivrait à un backend down.
- **Onboarding dashboard vide** : le premier login mène à un dashboard vide ; un état vide guidé « Créez votre première fiche en 2 étapes » existe (`EmptyState`) mais pourrait montrer un aperçu de la fiche démo.
- **Sandbox `/sandbox/customize`** : 69 warnings a11y (`label` sans contrôle associé). Pages internes, non prioritaire.
- **Étape 2 du wizard** : le formulaire d'ajout de source est long (9 champs). Un mode « rapide » (URL seule, le reste plié dans un accordéon « Détails ») réduirait la friction du premier ajout.
