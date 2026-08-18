# 01-brief

## Scope

Transformer le brief rempli par l'utilisateur en un contrat de fiche stable, et créer la fiche brouillon côté Philum.

## Inputs

| Source | File | Section | Why |
|---|---|---|---|
| Brief utilisateur | `../../runs/<slug>/00-brief.md` | Full file | Thèse, sources connues, droits |
| Squelette du brief | `../../_core/templates/brief.md` | Full file | Structure attendue |
| Règles typographiques | `../../shared/voix-createur.md` | « Règles typographiques » et « Longueurs cibles » | Titre et description conformes |
| Signature des tools MCP | `../../shared/philum-mcp.md` | « Écriture » ligne `create_card`, ligne `set_content_text` | Appels stricts |

## Process

1. Appeler `mcp__philum__whoami` : vérifier que le compte identifié par le token est bien l'auteur du brief. Si ambigu, refuser.
2. Passer `mcp__philum__search_cards(query="<slug>")` : vérifier qu'aucune fiche à ce slug n'existe déjà. Si conflit, proposer un slug alternatif.
3. Écrire `brief.md` propre à partir de `00-brief.md`. Titre et description doivent respecter les règles typographiques.
4. Appeler `mcp__philum__create_card(slug, title, content_url?, description?, content_authors?, platform, content_type, visibility="public")`. Récupérer l'`id` retourné.
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
| Titre ne doublonne pas le contenu | Le titre de la fiche est différent du titre du contenu documenté |
| Aucun tiret cadratin | `grep "—"` sur `brief.md` retourne 0 |
| Longueurs conformes | Titre 40-90 car, description 250-500 car |
