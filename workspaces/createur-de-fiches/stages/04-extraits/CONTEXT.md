# 04-extraits

## Scope

Extraire et poser les verbatim des sources clés (pivots obligatoires, autres sources souhaitables), avec mise en situation quand nécessaire.

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Catalogue des sources | `../02-sources-collectees/output/<slug>-sources.md` | Full file | Repérer les pivots |
| Mapping UUID | `../02-sources-collectees/output/<slug>-ids.json` | Full file | `source_id` pour `add_excerpt` |
| Annotations | `../03-annotations/output/<slug>-annotations.md` | Full file | Savoir ce que chaque source apporte |
| Squelette d'un extrait | `../../_core/templates/extrait.md` | Full file | Structure |
| Règles d'extraits | `../../shared/principes-editoriaux.md` | « Extraits » | 3-5 par pivot, verbatim, `context` |
| Garde-fous serveur | `../../shared/garde-fous.md` | « Sur les extraits » | Anti hors-contexte |
| Guide DOI/OpenAlex | `references/verification-doi.md` | Full file | Où chercher un texte plein |

## Process

1. **Récupérer le texte de chaque source clé** : lire la page ou coller le texte manuellement si HTML bloqué.
2. **Sélectionner 3 à 5 extraits par pivot, 1 à 2 par autre source clé** : passages qui portent une affirmation clé. La longueur idéale est de 15 mots et plus, mais un extrait plus court reste valable s'il est adossé à un `context` qui le rend intelligible seul.
3. **Vérifier verbatim** : le passage doit exister mot pour mot dans la source. Toute reformulation invalide.
4. **Écrire la mise en situation (`context`)** : obligatoire dès qu'un extrait commence par un pronom référentiel, ou qu'il est trop court pour se comprendre seul. Optionnel quand le passage porte lui-même son contexte.
5. **Écrire le titre de l'extrait** : 2 à 6 mots, ce qu'on trouve dedans.
6. **Appeler `mcp__philum__add_excerpt(source_id, text, title?, context?)`**. Si refus serveur (garde-fou), élargir ou compléter `context` puis rappeler.

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Extraits posés | `output/<slug>-extraits.md` | Markdown groupé par source (verbatim + `context` + `excerpt_id`) |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 2 | Sélection des passages candidats par pivot | Confirmer, retirer, ajouter |
| 4 | Titres et mises en situation rédigés | Valider ou réécrire |
| 6 | Extraits posés côté prod, liens vers la fiche | Spot-check verbatim sur 2-3 extraits |

## Audit

| Check | Pass Condition |
|---|---|
| Pivots couverts | Chaque source `is_pivot=True` a ≥ 2 extraits posés |
| Vérifiabilité | Chaque `text` d'extrait apparaît mot pour mot dans la source (grep) |
| Pas de hors-contexte court | Aucun extrait court (moins d'une phrase autonome) sans `context` non vide |
| Plafond éditorial | Aucune source > 5 extraits |
| Titres descriptifs | Chaque titre d'extrait fait 2 à 6 mots, sans slogan (« Une découverte majeure ») |
