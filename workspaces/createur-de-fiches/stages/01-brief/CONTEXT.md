---
contract: "Contrat de l'etape 01 : transformer le brief en fiche brouillon cote Philum."
layer: L2
---
# 01-brief

## Scope

Transformer le brief rempli par l'utilisateur en un contrat de fiche stable, et créer la fiche brouillon côté Philum.

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Brief utilisateur | `../../runs/<slug>/00-brief.md` | Full file | Thèse, sources connues, droits |
| Squelette du brief | `../../_core/templates/brief.md` | Full file | Structure attendue |
| Règles typographiques | `../../shared/style-redactionnel.md` | « Règles typographiques » et « Longueurs cibles » | Titre et description conformes |
| Signature des tools MCP | `../../shared/philum-mcp.md` | « Écriture » ligne `create_card`, ligne `set_content_text` | Appels stricts |

## Process

1. Appeler `mcp__philum__whoami` : vérifier que le compte identifié par le token est bien l'auteur du brief. Si ambigu, refuser.
2. Passer `mcp__philum__search_cards(query="<slug>")` : vérifier qu'aucune fiche à ce slug n'existe déjà. Si conflit, proposer un slug alternatif.
3. Écrire `brief.md` propre à partir de `00-brief.md`. Le titre de la fiche doit être **le titre exact du contenu** (vérifié sur le contenu lui-même, Crossref pour les articles). Renseigner `titre_contenu` et `date_contenu` (si elle existe) dans le frontmatter.
4. Appeler `mcp__philum__create_card(slug, title, content_url?, description?, content_authors?, platform, content_type, visibility="public")`. Le `title` passé est le titre exact du contenu. Récupérer l'`id` retourné.
5. Si `droits_texte_integral: oui` dans le brief, appeler `mcp__philum__set_content_text(card_slug=slug, text=..., confirm_publication_rights=True)`. Sinon, ne PAS appeler.

## Outputs

| Artifact | Location | Format |
|---|---|---|
| Brief propre | `output/<slug>-brief.md` | Markdown avec frontmatter YAML |
| Preuve d'existence côté prod | `output/<slug>-card.json` | JSON (réponse de `create_card`) |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|---|---|---|
| 3 | `brief.md` propre : slug, titre, description | Signer le titre, corriger la description si besoin |
| 5 | `card.json` + lien `https://filum-eight.vercel.app/dashboard` | Vérifier que la fiche brouillon est bien là |

## Audit

| Check | Pass Condition |
|---|---|
| Slug unique | `search_cards("<slug>")` ne retourne aucune fiche du même slug chez le même auteur |
| Titre = titre exact du contenu | `titre_contenu` du brief == titre du contenu vérifié (Crossref pour les articles) ; `title` de la fiche == `titre_contenu` |
| Date du contenu tracée | `date_contenu` renseignée dans le brief si la date existe (sinon noté « pas de date trouvée ») |
| Aucun tiret cadratin | `grep "—"` sur `brief.md` retourne 0 |
| Description conforme | Description 2 à 4 phrases (~250-500 car) |
