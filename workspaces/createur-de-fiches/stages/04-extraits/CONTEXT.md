---
contract: "Contrat de l'etape 04 : extraire les verbatim et les ancrer aux sources."
layer: L2
---
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
| Règles d'extraits | `../../shared/principes-editoriaux.md` | « Extraits » | Verbatim, `context`, fourchettes de nombre et de longueur |
| Garde-fous serveur | `../../shared/garde-fous.md` | « Sur les extraits » | Anti hors-contexte |
| Guide DOI/OpenAlex | `references/verification-doi.md` | Full file | Où chercher un texte plein |

## Process

1. **Récupérer le texte de chaque source clé** : lire la page directement, ou pour un texte long `mcp__philum__chunk_text(source_id, text, size)` qui découpe en chunks lisibles. Si HTML bloqué anti-bot, coller le texte à la main dans `provided_text`.
2. **Optionnel : suggestions LLM** : `mcp__philum__suggest_excerpts(source_id, provided_text?, include_annotation, include_existing, include_card_context)` propose des candidats déjà vérifiés contre le texte (anti-hallucination). L'agent choisit lesquels retenir ; le LLM peut aussi suggérer titre + `context` via `mcp__philum__annotate_excerpt(source_id, excerpt_text)`.
3. **Sélectionner les passages selon ce que la source apporte**, pas selon un quota : 1 à 3 extraits quand on vient y chercher un point précis, 3 à 4 et au-delà quand une grande part du contenu sert la fiche, jusqu'au découpage intégral quand tout le propos est pertinent, 0 quand la source est secondaire ou invérifiable. Les fourchettes complètes sont dans `../../shared/principes-editoriaux.md`, section « Combien d'extraits par source ». La longueur suit la même logique : 15 à 80 mots pour une affirmation, plus court avec `context` pour une formule ou un chiffre, jusqu'à 160 mots pour un raisonnement.
4. **Vérifier verbatim** : le passage doit exister mot pour mot dans la source. Toute reformulation invalide.
5. **Écrire la mise en situation (`context`)** : obligatoire dès qu'un extrait commence par un pronom référentiel, ou qu'il est trop court pour se comprendre seul. Optionnel quand le passage porte lui-même son contexte.
6. **Écrire le titre de l'extrait** : 2 à 6 mots, ce qu'on trouve dedans.
7. **Appeler `mcp__philum__add_excerpt(source_id, text, title?, context?)`**. Si refus serveur (garde-fou), élargir ou compléter `context` puis rappeler.
8. **Relecture serveur** : `mcp__philum__verify_excerpts(source_id, provided_text?)` fait passer `verified_status` de null à `found`/`moved`/`missing`/`unreadable`. Sans cette passe, la fiche affirme sans preuve. Pour les pages bloquées anti-bot, fournir `provided_text` (l'agent atteste le texte).

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
| Pas de remplissage | Aucun extrait qui redit un extrait déjà posé, ou qui ne dit rien du sujet de la fiche |
| Titres descriptifs | Chaque titre d'extrait fait 2 à 6 mots, sans slogan (« Une découverte majeure ») |
