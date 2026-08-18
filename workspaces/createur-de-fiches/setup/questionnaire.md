# Questionnaire de démarrage

À remplir par l'utilisateur avant l'étape 1. Chaque question a un but précis pour le pipeline ; une réponse absente bloque un choix plus loin.

**Instructions** : copier ce fichier en `runs/<slug>/00-brief.md`, remplir, puis lancer `stages/01-brief/`.

---

1. **slug** (URL courte, kebab-case, unique chez toi) :
2. **title** (titre affiché, phrase complète, pas de nom d'auteur) :
3. **content_type** (`video` | `article` | `podcast` | `livre` | `autre`) :
4. **platform** (`youtube` | `spotify` | `substack` | `other` ...) :
5. **content_url** (URL du contenu documenté, si publique) :
6. **content_authors** (auteur·ice·s du contenu documenté, pas des sources) :
7. **thèse en une phrase** (ce que le contenu affirme et que la fiche va sourcer) :
8. **portée** (jusqu'où on va : thèse centrale seulement, ou ramifications ?) :
9. **sources déjà connues** (URLs, DOI, titres) :
10. **as-tu le droit de publier le texte intégral du contenu ?** (`oui` | `non` | `partiel`). Si `oui`, colle-le en fin de brief.
11. **contraintes** (choses à ne pas dire, sources à ne pas citer, angles à éviter) :

---

Une fois rempli, l'étape 1 lit ce fichier et écrit `runs/<slug>/stages/01-brief/output/brief.md`, contrat stable pour toutes les étapes suivantes.
