# 06-relecture

## Scope

Passer une check-list qualité complète sur la fiche, rendre un verdict `go` ou `no-go` écrit qui autorise (ou non) la publication.

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Productions de toutes les étapes | `../0[1-5]-*/output/` | Full files | Tout ce qui va être publié |
| Cinq propriétés | `../../shared/principes-editoriaux.md` | « Les cinq propriétés d'une fiche parfaite » | Grille de lecture |
| Garde-fous complets | `../../shared/garde-fous.md` | Full file | Ce qui bloque la publication |
| Règles typographiques | `../../shared/voix-createur.md` | « Règles typographiques » et « Longueurs cibles » | Vérifications finales |

## Process

1. Ouvrir chaque `output/` des étapes 01 à 05.
2. Passer chaque check de la section Audit ci-dessous.
3. Écrire `<slug>-verdict.md` avec frontmatter `go: yes` ou `go: no`, la liste de ce qui est OK et de ce qui reste.

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Verdict signé | `output/<slug>-verdict.md` | Markdown avec frontmatter YAML (`go: yes/no`, `date`) |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Résultat de chaque check (pass/fail) | Contester un fail, corriger et repasser, ou accepter |
| 3 | Le verdict rédigé | Signer, ou retour à l'étape défaillante |

## Audit

| Check | Pass Condition |
|---|---|
| Titre ne doublonne pas le contenu | `<slug>-brief.md` title différent du titre du contenu documenté |
| Longueurs titre/description | Titre 40-90 car, description 250-500 car |
| Aucun tiret cadratin | `grep -R "—" runs/<slug>/stages/*/output/` retourne 0 |
| Annotations non paraphrastiques | Aucune annotation ne reformule le titre de sa source |
| Stance déclarée ou null assumé | Chaque source a un `stance` explicite (peut être `null`) |
| Au moins un pivot | Au moins une source marquée `is_pivot=True` |
| Pivots avec extraits | Chaque pivot a ≥ 2 extraits |
| Extraits vérifiables | Aucun `verified_status=missing` sans autorisation explicite |
| Aucune suggestion connexion pendante | Chaque `outgoing` a un verdict tranché |
| Extraits ≤ 5 par source | Aucune source > 5 extraits |
| Métadonnées vérifiées | DOI présents cochés via Crossref, dates depuis la source |
