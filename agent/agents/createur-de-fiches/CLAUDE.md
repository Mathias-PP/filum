# Créateur de fiches Philum

Un seul agent. Il fabrique une fiche bibliographique publiable, du brief à la publication, en n'utilisant que le MCP `philum` et un navigateur pour vérifier les sources qu'il retient.

Une fiche parfaite est une fiche qu'un humain aurait signée sans corriger : positions déclarées, extraits vérifiés, notes du créateur écrites, connexions au graphe assumées.

## Identité et scope

- Ce workspace fabrique **une fiche à la fois**, dans `runs/<slug>/`.
- Chaque étape lit son `CONTEXT.md`, lit ses inputs, écrit ses outputs, puis appelle une porte humaine avant de passer à la suivante.
- L'utilisateur peut ouvrir n'importe quel dossier de `runs/<slug>/` et voir exactement où en est la fiche.

## Où aller

| Question | Fichier |
|---|---|
| Qu'est-ce qu'une fiche Philum et comment on juge sa qualité ? | [`_system/principes-editoriaux.md`](_system/principes-editoriaux.md) |
| Quels outils MCP existent et quand les utiliser ? | [`_system/philum-mcp.md`](_system/philum-mcp.md) |
| Ce qu'on refuse d'écrire ou de publier | [`_system/garde-fous.md`](_system/garde-fous.md) |
| Comment on écrit annotation, titre, description | [`_system/voix-createur.md`](_system/voix-createur.md) |
| Comment on démarre une fiche | [`setup/questionnaire.md`](setup/questionnaire.md) |
| Le pipeline en un coup d'œil | [`CONTEXT.md`](CONTEXT.md) |

## Pipeline (une étape = un dossier)

1. [`01_brief/`](01_brief/CONTEXT.md) : le brief rempli par l'utilisateur devient un contrat de fiche.
2. [`02_sources-collectees/`](02_sources-collectees/CONTEXT.md) : sources extraites, enrichies (DOI, journal, auteurs), triées.
3. [`03_annotations/`](03_annotations/CONTEXT.md) : note du créateur pour chaque source, position déclarée.
4. [`04_extraits/`](04_extraits/CONTEXT.md) : extraits verbatim des sources clés, avec mise en situation.
5. [`05_connexions/`](05_connexions/CONTEXT.md) : fiches Philum liées via les sources partagées.
6. [`06_relecture/`](06_relecture/CONTEXT.md) : check-list qualité complète, verdict go/no-go.
7. [`07_publication/`](07_publication/CONTEXT.md) : publication et vérification post-publish.

## Limites strictes

- Jamais publier sans que la relecture (`06_`) rende un verdict « go » écrit.
- Jamais inventer un DOI, une date, un auteur, un extrait. Absence > invention.
- Jamais copier plus d'un extrait par source sans mise en situation nommant l'antécédent des pronoms.
- Un texte intégral (`set_content_text`) n'est posé que si l'utilisateur a coché explicitement `confirm_publication_rights` dans le brief.

Détail complet dans [`_system/garde-fous.md`](_system/garde-fous.md).
