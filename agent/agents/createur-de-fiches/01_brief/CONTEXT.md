# Étape 1 : Brief → contrat de fiche

**Reads**
- `runs/<slug>/00_brief.md` (rempli par l'utilisateur depuis `setup/questionnaire.md`).
- `_templates/brief.md` (structure attendue).
- `_system/voix-createur.md` (règles pour titre et description).

**Does**
1. Appeler `mcp__philum__whoami` : vérifier que le compte identifié par le token est bien l'auteur du brief.
2. Vérifier le slug : passer `mcp__philum__search_cards(query="<slug>")` pour repérer un doublon. Si conflit, proposer un slug alternatif.
3. Écrire `brief.md` propre à partir de `00_brief.md`. Titre et description doivent respecter les règles de `_system/voix-createur.md` (pas de tirets cadratins, longueur, pas de doublon avec le titre du contenu).
4. Appeler `mcp__philum__create_card(slug, title, content_url?, description?, content_authors?, platform, content_type, visibility="public")`.
5. Si `droits_texte_integral: oui` dans le brief, appeler `set_content_text(card_slug=slug, text=..., confirm_publication_rights=True)`. Sinon, ne PAS appeler.

**Writes**
- `runs/<slug>/01_brief/brief.md` : le brief propre, servira de référence à toutes les étapes suivantes.
- `runs/<slug>/01_brief/card.json` : la réponse de `create_card` (id, slug, timestamps). Sert de preuve d'existence de la fiche brouillon.

**Human gate**
L'utilisateur ouvre `brief.md` et `card.json`, vérifie :
- Slug conforme à ce qu'il attend, sans doublon.
- Titre et description qu'il aurait signés lui-même.
- Fiche brouillon bien créée côté prod (`https://filum-eight.vercel.app/dashboard`).

Une fois ces trois cases cochées explicitement, l'étape 2 démarre.
