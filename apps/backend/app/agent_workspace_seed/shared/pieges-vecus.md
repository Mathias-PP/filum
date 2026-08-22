---
contract: "Erreurs passees a ne pas repeter, documentees a partir de conversations reelles."
layer: L3
---
# Pièges déjà payés

Chaque entrée : le symptôme visible, la cause profonde, la résolution. Objectif : qu'aucun agent ne les redécouvre.

À enrichir à chaque nouveau piège rencontré.

---

## 1. URL d'une source ne correspond pas au DOI

**Symptôme.** Une source pivot a `url = https://iopscience.iop.org/article/10.1088/1741-4326/ad64e5` alors que son `doi = 10.1088/1741-4326/ac2525`. Le lien mène à un article différent de la référence DOI. Le rendu de fiche affiche « ac2525 » dans la référence stylée mais renvoie vers ad64e5 quand on clique.

**Cause.** Le fetch d'origine (extraction automatique ou saisie manuelle) a associé le mauvais lien. Personne ne recoupe URL et DOI après coup.

**Résolution.**
- Avant `add_source`, vérifier que l'URL contient le DOI (ou, pour les pages non-DOI, faire un HEAD sur l'URL et lire la vraie destination).
- Si détecté après coup : `DELETE /sources/{id}` puis nouveau `add_source` avec la bonne URL. `PATCH url` est refusé par l'API (URL immuable).

---

## 2. 403 anti-bot sur ScienceDirect / IOP / PubMed

**Symptôme.** `POST /sources/{id}/excerpts/verify` retourne `text_source: fetched` avec `page_text_length: 0` et `access_blocked: true`. Tous les extraits ressortent `verified_status: unreadable`. La fiche publique affiche « source illisible à la relecture ».

**Cause.** Ces sites répondent 403 aux IPs de datacenter (Cloud, CI, VPS). Le backend Philum ne peut pas fetch la page.

**Résolution.** Récupérer le texte de la source ailleurs (NASA ADS, Semantic Scholar, Crossref abstract, PMC pour PubMed) et rappeler `verify` avec le payload `{text: "..."}`. L'agent atteste alors que le texte fourni est celui de la source. Le champ `text_source` bascule à `provided` dans la réponse et se lit sur la fiche publique comme « vérifié contre un texte fourni par le créateur ».

---

## 3. Extrait > 1 000 caractères refusé par `add_excerpt`

**Symptôme.** `add_excerpt` rend `ToolError: text ... max 1000`. Les abstracts scientifiques dépassent facilement.

**Cause.** Plafond volontaire côté serveur (`ExcerptCreate.text: max_length=1000`). Un extrait plus long n'est plus un extrait, c'est une source à part.

**Résolution.** Couper au niveau d'une phrase (jamais en milieu, voir garde-fou). Poser plusieurs extraits successifs si nécessaire. Ou, si l'abstract fait sens en entier, l'utiliser comme `annotation` de la source plutôt que comme extrait.

---

## 4. Tirets cadratins remplacés par virgules dans un verbatim

**Symptôme.** L'extrait posé dit `« 22 minutes, 1 337 secondes »` alors que la page source écrit `« 22 minutes—1,337 seconds »`. Le `verify` marque l'extrait `verified_status: missing` (introuvable verbatim).

**Cause.** La règle éditoriale « pas de cadratins » a été appliquée AU VERBATIM par erreur. Un extrait est du verbatim : sa typographie doit rester celle de la source.

**Résolution.** Cadratins interdits dans la prose éditoriale (titre, description, annotation, titre d'extrait, `context`) ; **préservés dans le `text` d'un extrait** quand la source les utilise. Voir `style-redactionnel.md`. Repost de l'extrait avec les cadratins exacts.

---

## 5. `add_source` appelé deux fois avec la même URL ne double pas la source

**Symptôme.** L'agent panique : « j'ai posé la source, puis rappelé `add_source` pour ajouter l'annotation, j'ai dû créer un doublon ». En fait non.

**Cause.** L'API dé-duplique par URL/DOI (identité normalisée via `_identite()`, sources.py). Le second appel met à jour la source existante au lieu d'en créer une deuxième.

**Résolution.** Comportement volontaire, utilisé par le pipeline (étape 03 pose l'annotation via ce chemin, sans avoir besoin d'un `update_source` MCP qui n'existe pas encore). Vérifiable : l'ID retourné est le même aux deux appels.

---

## 6. `DELETE` retourne 204 sans corps JSON

**Symptôme.** Un helper qui parse systématiquement la réponse comme JSON casse sur un DELETE réussi (`json.decoder.JSONDecodeError: Expecting value: line 1 column 1`).

**Cause.** RFC 7231 : un 204 No Content **ne doit pas** avoir de body. Le client HTTP doit tester le status code avant de tenter un `.json()`.

**Résolution.** Dans le helper Python :
```python
if response.status_code == 204:
    return None
return response.json()
```

---

## 7. Ordre d'affichage des sources non modifiable

**Symptôme.** Une source a été ajoutée après coup, elle apparaît en dernière position, alors qu'elle devrait être au milieu de la fiche. Un agent cherche `PATCH /sources/{id}` avec `position`, ou un endpoint `reorder`.

**Cause.** Pas de champ `position` mutable côté serveur. L'ordre affiché est l'ordre d'insertion (`created_at`).

**Résolution.** Deux options :
1. **Vivre avec** : les pivots portent une étoile visible dans la fiche publique, l'ordre est peu critique.
2. **Rebuild manuel** : `DELETE` toutes les sources dans l'ordre, puis les recréer dans l'ordre voulu. Coûteux (perte des UUID, perte des connexions entrantes). N'y aller que si vraiment nécessaire.

---

## 8. Titre de fiche reformulé au lieu du titre exact du contenu

**Symptôme.** La fiche porte « Stellarator contre tokamak : Stellaris, un concept de centrale à fusion en continu » alors que le contenu documenté s'intitule « Stellaris: A high-field quasi-isodynamic stellarator for a prototypical fusion power plant ». Le lecteur ne retrouve pas le contenu au titre de la fiche.

**Cause.** L'ancienne règle éditoriale « le titre de la fiche ≠ le titre du contenu » poussait à reformuler. Cette règle est **abrogée** (directive utilisateur 2026-08-19).

**Résolution.**
- Règle actuelle : **titre de la fiche = titre exact du contenu**, quel que soit le type (article, blog, vidéo…).
- Vérifier le titre du contenu sur une source d'autorité (Crossref pour les articles) avant de créer la fiche.
- Si détecté après coup : `PATCH /cards/{id}` avec `title` corrigé, puis relire l'export publié.

---

## 9. Sources affichées « s. d. » alors que la date de publication est connue

**Symptôme.** Toutes les sources d'une fiche affichent « s. d. » dans la fiche publique. Le graphe remonte `published_at: null` pour chaque source.

**Cause.** `add_source` a été appelé sans `published_at`. Les dates existaient pourtant (Crossref/éditeur), personne ne les a renseignées.

**Résolution.**
- Au moment d'ajouter une source, lancer l'extraction de métadonnées (`GET /sources/extract?url=...`) et poser `published_at` avec la date trouvée (Crossref `published` pour les articles).
- Si détecté après coup : `PATCH /sources/{id}` avec `{"published_at": "YYYY-MM-DDT00:00:00Z"}`.
- Règle actuelle : une date connue doit figurer ; une date introuvable se trace (« pas de date trouvée » dans l'audit).

---

## 10. La fiche affiche la date de publication Philum au lieu de la date du contenu

**Symptôme.** La fiche publique montre « Publiée le 19 août 2026 » (ou l'année 2026 sur le graphe) alors que le contenu documenté est sorti en 2025. Le `citation_publication_date` de la page reprend `card.published_at` (horodatage de publication Philum).

**Cause.** La carte n'a pas de métadonnées de date de contenu renseignées : le nœud carte du graphe a `published_at: null` et l'interface retombe sur la date de publication de la fiche.

**Résolution.**
- La date affichée pour le contenu doit être celle du contenu, pas l'horodatage de publication Philum (deux notions distinctes, directive utilisateur).
- Renseigner la date de publication du contenu sur la fiche au moment de sa création (via l'extraction du `content_url`), et vérifier à l'étape 07 que la page affiche l'année du contenu.
- Un correctif serveur propre (exposer/remplir une métadonnée de date de contenu distincte de `published_at`) reste à faire ; à ce stade, noter l'écart en alerte d'audit tant que le mécanisme n'est pas exposé par l'API.
