---
contract: "Contrat de l'etape 06 : relecture qualite et emission du verdict de publication."
layer: L2
---

# 06-relecture

## Scope

Passer une check-list qualité complète sur la fiche, rendre un verdict `go` ou `no-go` écrit qui autorise (ou non) la publication.

## Inputs

| Source                           | File                                   | Section                                           | Why                          |
| -------------------------------- | -------------------------------------- | ------------------------------------------------- | ---------------------------- |
| Productions de toutes les étapes | `../0[1-5]-*/output/`                  | Full files                                        | Tout ce qui va être publié   |
| Cinq propriétés                  | `../../shared/principes-editoriaux.md` | « Les cinq propriétés d'une fiche parfaite »      | Grille de lecture            |
| Garde-fous complets              | `../../shared/garde-fous.md`           | Full file                                         | Ce qui bloque la publication |
| Règles typographiques            | `../../shared/style-redactionnel.md`   | « Règles typographiques » et « Longueurs cibles » | Vérifications finales        |

## Process

1. Ouvrir chaque `output/` des étapes 01 à 05.
2. Passer chaque check de la section Audit ci-dessous.
3. Écrire `<slug>-verdict.md` avec frontmatter `go: yes` ou `go: no`, la liste de ce qui est OK et de ce qui reste.

## Outputs

| Artifact      | Location                   | Format                                                |
| ------------- | -------------------------- | ----------------------------------------------------- |
| Verdict signé | `output/<slug>-verdict.md` | Markdown avec frontmatter YAML (`go: yes/no`, `date`) |

## Checkpoints

| After Step | Agent Presents                       | Human Decides                                        |
| ---------- | ------------------------------------ | ---------------------------------------------------- |
| 2          | Résultat de chaque check (pass/fail) | Contester un fail, corriger et repasser, ou accepter |
| 3          | Le verdict rédigé                    | Signer, ou retour à l'étape défaillante              |

## Audit

Les checks ci-dessous émettent des **alertes** listées dans le verdict. Aucune n'est un verrou : la décision de publier appartient à l'humain, mais rien ne passe silencieusement. Un fichier `audit_fiche.py` (voir `_core/audit/`) automatise les vérifications de titre et de dates.

| Check                                | Pass Condition                                                                                                |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Titre = titre exact du contenu       | `titre_contenu` du brief == `title` de la carte (vérifié sur le contenu lui-même, Crossref pour les articles) |
| Date du contenu tracée               | `date_contenu` du brief renseignée (ou notée « pas de date trouvée ») et cohérente avec le contenu            |
| Dates des sources                    | Chaque source porte `published_at` si la date existe (aucune « s. d. » quand la date est connue)              |
| Longueurs titre/description          | Titre = titre exact du contenu ; description 250-500 car                                                      |
| Aucun tiret cadratin                 | `grep -R "—" runs/<slug>/stages/*/output/` retourne 0                                                         |
| Annotations non paraphrastiques      | Aucune annotation ne reformule le titre de sa source                                                          |
| Stance déclarée ou null assumé       | Chaque source a un `stance` explicite (peut être `null`)                                                      |
| Au moins un pivot                    | Au moins une source marquée `is_pivot=True`                                                                   |
| Pivots avec extraits                 | Chaque pivot a ≥ 2 extraits                                                                                   |
| Extraits vérifiables                 | Aucun `verified_status=missing` sans autorisation explicite                                                   |
| Aucune suggestion connexion pendante | Chaque `outgoing` a un verdict tranché                                                                        |
| Extraits ≤ 5 par source              | Aucune source > 5 extraits                                                                                    |
| Métadonnées vérifiées                | DOI présents cochés via Crossref, dates depuis le contenu                                                     |
