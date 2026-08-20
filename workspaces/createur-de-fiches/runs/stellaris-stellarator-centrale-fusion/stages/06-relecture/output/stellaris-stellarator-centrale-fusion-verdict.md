---
go: yes
date: 2026-08-19
slug: stellaris-stellarator-centrale-fusion
---

# Verdict de relecture : stellaris-stellarator-centrale-fusion

Passage de la check-list du 2026-08-19.

## Checks

| Check | Résultat |
|---|---|
| Titre = titre exact du contenu | PASS (titre fiche = « Stellaris: A high-field quasi-isodynamic stellarator for a prototypical fusion power plant », corrigé le 2026-08-19, règle utilisateur stricte) |
| Description | PASS (~440 car., inchangée) |
| Aucun tiret cadratin | PASS (grep « — » sur `runs/<slug>/stages/*/output/` retourne 0) |
| Annotations non paraphrastiques | PASS (aucune annotation ne reformule le titre de sa source) |
| Stance déclarée ou null assumé | PASS (5/5 sources ont un stance explicite : 3 appuie, 2 contexte) |
| Au moins un pivot | PASS (3 pivots : Beidler, Boozer, Goodman JPP) |
| Pivots avec extraits | PASS (3 extraits chacun, ≥ 2 requis) |
| Extraits vérifiables | PASS (9/9 `verified_status=found` via `verify_excerpts`, textes attestés fournis) |
| Aucune suggestion connexion pendante | PASS (aucun outgoing, aucun incoming) |
| Extraits ≤ 5 par source | PASS (3 extraits par source pivot, 0 sur les non-pivots) |
| Métadonnées vérifiées | PASS (6 DOI vérifiés dans Crossref à l'étape 01, dates depuis les pages éditeurs ; `published_at` posé sur les 5 sources le 2026-08-19) |

## Alertes (non bloquantes, tracées)

- **Date du contenu non renseignée sur la fiche** : le graphe affiche la date de publication Philum (2026-08-19) faute de métadonnée de date de contenu sur la carte. La date du contenu (2025-05-01, Crossref) est consignée au brief. Correctif serveur (exposer une date de contenu distincte de `published_at`) à faire — voir `shared/pieges-vecus.md` §10. Rien ne passe silencieusement : `audit_fiche.py` remonte cette alerte à chaque audit.

## Vérifications complémentaires

- Extraits verbatim copiés depuis les pages publiques éditeurs : Nature (Beidler, open access), IOP (Boozer, abstract public), Cambridge Core (Goodman JPP, open access). Chaque passage existe mot pour mot.
- Landreman et Goodman 2024 sans extrait : pages APS bloquées anti-bot (403), pas de texte intégral vérifiable. Assumé dans l'artefact extraits.
- Droits texte intégral : `droits_texte_integral: non` dans le brief, `set_content_text` non appelé.

## Verdict

`go: yes`. La fiche est publiable.