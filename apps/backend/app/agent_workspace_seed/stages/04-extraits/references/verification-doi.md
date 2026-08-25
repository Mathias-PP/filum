---
contract: "Reference de verification des DOI et metadonnees d'articles scientifiques."
layer: L3
---
# Vérification DOI et texte plein

Sources d'autorité pour vérifier un DOI et retrouver le texte plein d'un article.

## Crossref

- API : `https://api.crossref.org/works/{doi}`
- Rend : titre exact, auteurs, journal, volume, pages, année. Métadonnées bibliographiques fiables.
- Ne rend PAS le texte plein.

## OpenAlex

- API : `https://api.openalex.org/works/https://doi.org/{doi}` (identifiant complet)
- Rend : les mêmes métadonnées que Crossref, plus `open_access.oa_url` quand une version gratuite existe.
- Utile pour trouver un texte plein légal (green OA, gold OA).

## PubMed / PMC

- Articles biomédicaux. `https://pubmed.ncbi.nlm.nih.gov/{pmid}/` pour la fiche, `https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/` pour le texte quand disponible.
- L'API interne `E-utilities` rend le texte plein des articles PMC en accès libre. Le code backend Philum le fait déjà pour la relecture d'extraits.

## unpaywall

- API : `https://api.unpaywall.org/v2/{doi}?email=<mail>`
- Rend l'URL du meilleur PDF gratuit disponible pour un DOI donné.

## Retraction Watch

- Base des articles rétractés : `http://retractiondatabase.org/`
- À consulter avant de retenir un article scientifique en source. Une source rétractée doit être signalée dans son annotation ou retirée.

## Ordre de vérification recommandé

1. Crossref pour figer les métadonnées (titre, auteurs, journal, année).
2. Retraction Watch pour signaler une rétractation éventuelle.
3. OpenAlex ou unpaywall pour trouver un texte plein légal.
4. Lire la source elle-même pour choisir les extraits verbatim.
