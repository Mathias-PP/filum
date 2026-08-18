# Questionnaire de démarrage

À remplir par l'utilisateur avant l'étape 1. Chaque question a un but précis pour le pipeline. Une réponse absente bloque un choix plus loin ; mieux vaut le savoir maintenant.

Copier ce fichier en `runs/<slug>/00_brief.md`, le remplir, puis lancer l'étape 1.

---

## Identité de la fiche

- **slug** (URL courte, kebab-case, unique chez toi) :
- **title** (le titre affiché, phrase complète, pas de nom d'auteur) :
- **content_type** (`video` | `article` | `podcast` | `livre` | `autre`) :
- **platform** (`youtube` | `spotify` | `substack` | `other` | ...) :
- **content_url** (l'URL du contenu documenté, si publique) :
- **content_authors** (auteur·ice·s du contenu documenté, pas des sources) :

## Thèse

- **thèse en une phrase** (ce que le contenu affirme et que la fiche va sourcer) :
- **portée** (jusqu'où on va : la thèse centrale seulement, ou aussi ses ramifications ?) :

## Sources déjà connues

- URLs, DOI, ou titres si tu en as déjà à la main :
- Où en trouver d'autres (bibliographie du contenu, notes de bas de page, description) :

## Texte intégral

- **as-tu le droit de publier le texte intégral du contenu ?** (`oui` | `non` | `partiel`) :
- Si `oui`, colle-le en fin de brief ou pointe le fichier :

## Ton et positionnement

- **la fiche appuie, nuance ou contextualise la thèse ?** (une phrase pour chaque source clé, si tu sais déjà) :
- **contraintes** (choses à ne pas dire, sources à ne pas citer, angles à éviter) :

---

Une fois rempli, l'étape 1 lit ce fichier et produit `runs/<slug>/01_brief/brief.md`, le contrat de fiche stable pour toutes les étapes suivantes.
