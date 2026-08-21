# État du projet — Philum

> Snapshot vivant, 1 page max. **Pour l'historique détaillé** : voir [`CHANGELOG.md`](./CHANGELOG.md). **Pour les items long terme** : voir [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).

**Dernière mise à jour : 2026-08-21**

---

## Session 2026-08-21 (autonome) : moteur d'agent BYOK, 39 outils MCP, interface de chat

**PR #499** : providers BYOK CRUD. Le createur enregistre sa cle API (OpenAI, Anthropic, Gemini, DeepSeek) chiffree en AES-GCM, test de cle depuis l'interface, masquage a l'affichage. Isolation par createur, un seul defaut par provider.

**PR #500** : workspace ICM heberge en base. La progression d'une session d'agent (etapes completees, sorties texte, avertissements) est persistee dans une table `agent_sessions`.

**PR #508** : moteur d'agent BYOK, boucle, outils, chat SSE. Le createur ouvre un chat dans son tableau de bord ; l'agent enchaîne les appels d'outils en streaming SSE, chaque evenement est visible en temps reel. La boucle est plafonnee (protection contre les cycles infinis).

**Plan d'implementation 2026-08-21, 8 taches :**

- **Tache 1** : orchestrateur de fiche autonome. `POST /agent/fiche` demarre un run ICM en 7 etapes (brief, sources, extraits, relecture, connexions, attestation, publication), chaque etape streamee en SSE avec `stage_start` / `stage_done` / `stage_failed`.

- **Tache 2** : le test de cle rend le message exact du fournisseur. `_detail_provider()` extrait le texte brut de trois formes de corps d'erreur (OpenAI, Gemini liste, HTML brut). `_classify()` prefixe d'un cadrage lisible et expose `provider_message`. Avant : « Quota epuise ou limite de debit. Reessayer plus tard. » ; apres : le message verbatim du provider apparait.

- **Tache 3** : selecteur de modele via `GET /agent/providers/{id}/models`. Le backend interroge `GET /models` avec la cle du createur et replie sur `MODELES_SUGGERES` si le provider refuse. Le front affiche un `<select>` avec les modeles du compte, avec bascule vers la saisie libre.

- **Tache 4** : modifier une cle sans la supprimer. Bouton « Modifier » sur chaque provider ; en mode edition le champ cle est optionnel (vide = conserver l'actuelle), le fournisseur est en lecture seule.

- **Tache 5** : quatre fournisseurs a cle gratuite sans carte (Groq, OpenRouter, Mistral, Cerebras), avec liens directs vers les consoles. Encart d'onboarding quand aucun provider n'est enregistre.

- **Tache 6** : navigation et contexte. Lien retour depuis Providers, banniere du provider actif dans le chat, bloc d'onboarding si aucun provider n'est marque par defaut. Bouton « Nouvelle conversation ».

- **Tache 7** : schemas MCP compatibles Gemini. `aplatir_nullable()` remplace recursivement `anyOf: [T, null]` par `T` dans les `parameters` des 39 outils. Le validateur de function declarations de Gemini rejetait `anyOf` et silenciait la liste entiere. Verifie : `test_aucun_outil_mcp_ne_publie_any_of` passe, 0 `anyOf` dans les schemas d'entree.

- **Tache 8** : page `/developers` utilisable. L'URL nue du serveur MCP apparait en premier avec un bouton copier. Une recette par client (Claude Code, Claude application, Gemini CLI avec `httpUrl`, Cursor/opencode/Codex). Les 39 outils sont listes et groupes par categorie.

---

## Session 2026-08-16 (autonome, suite) : une seconde fiche qui cite la première, et le défaut qu'elle a révélé

Deuxième fiche construite selon la même méthode, sur une revue qui **cite** la première : « Early detection of multiple cancers: methylation-based liquid biopsy » (`10.3389/fonc.2025.1657418`), publiée sur [`/@mathias-pinault/early-detection-of-multiple-cancers-methylation-liquid-biopsy`](https://filum-eight.vercel.app/@mathias-pinault/early-detection-of-multiple-cancers-methylation-liquid-biopsy). Le lien entre les deux fiches est matérialisé dans la base par `linked_card_id`, pas seulement dans le texte.

**PR #405 validée en production.** 77 sources importées, `extraction_confidence: high`, `refs_from_oracle: 77`, et surtout **77/77 portent leur DOI et leur revue**, contre 0/50 sur la première fiche avant correctif. Résultat visible sur la page publique : 62 badges d'accès libre, 3 mentions de rétractation ou de correctif, et **zéro « Non vérifiable »** là où la première fiche en affichait 50. Les badges de comptage d'extraits de la PR #404 sont visibles sur les lignes repliées.

**Ce que la lecture des sources a produit.** 8 extraits verbatim, tous vérifiés `found`, sur 6 sources clés. Deux d'entre eux contredisent la revue qui les cite, et sont enregistrés en posture `nuance-contredit` : la revue annonce « 9024 asymptomatic individuals » là où l'étude K-DETEK elle-même écrit 9057 ; et la sensibilité de 82,8 % mise en avant pour GUIDE vaut à 95,8 % de spécificité, le même article rapportant 64 à 66 % dès que la spécificité dépasse 99 %. C'est le genre d'écart qu'une bibliographie listée ne montre jamais.

**PR #407 : un champ inconnu dans un PATCH cessait de répondre 200.** Six requêtes envoyant `is_key_source` au lieu de `is_pivot` ont toutes réussi, sans rien écrire ni rien dire ; c'est en relisant la fiche publiée qu'on voyait zéro source clé. Pydantic ignore les champs surnuméraires par défaut, et sur un schéma de mise à jour où tout est facultatif, un corps entièrement faux vaut un corps vide. `extra="forbid"` sur `SourceUpdate` et `CardUpdate`. L'enjeu dépasse la coquille de frappe : Philum expose un serveur MCP, et un agent qui devine un nom de champ doit s'entendre dire qu'il se trompe.

**PR #409 : une même source ajoutée deux fois cessait de passer.** La fiche comptait 80 sources pour 77 références distinctes, sans que rien ne le signale ; les trois doublons se faisaient archiver, enrichir et afficher deux fois. Une source est désormais identifiée dans sa fiche par son DOI ou son URL normalisée, jamais par son titre, et une source mise à la corbeille ne bloque pas sa recréation. Le POST individuel répond 409 en désignant la source déjà présente, le lot les écarte dans un champ `duplicates`. Au passage, le gestionnaire d'erreurs ne conservait que `code` et `message` : les clés qui désignent la ressource en cause passent maintenant, ce qui rend un refus actionnable plutôt qu'à deviner.

**PR #411 : le texte plein NCBI vient de l'API, plus du mur reCAPTCHA.** Huit extraits de la première fiche restaient marqués « illisible » alors que les articles cités sont en accès libre : PubMed et PMC opposent un interstitiel aux IP de datacenter, et ce verdict accuse l'auteur·ice à la place du site. Or NCBI publie le même contenu en JSON structuré, sans clé ni captcha, pour son sous-ensemble Open Access. Mesure faite **depuis la VM de production**, sur PubMed 33313194 : le scraping rend 0 caractère et se déclare bloqué, l'API rend 37 074 caractères. Une URL hors NCBI n'est pas touchée. Deux pièges traités : un article hors accès libre reçoit un corps d'erreur en texte brut avec un code 200, qu'il ne faut pas prendre pour du texte plein ; et la bibliographie est écartée, sinon un extrait qui n'est que le titre d'un ouvrage cité passerait pour retrouvé dans le corps. Les trois chemins qui récupéraient le texte d'une source (découpage, relecture, suggestion) passent désormais par un helper commun.

**PR #413 : un résumé ne suffit pas pour déclarer un extrait absent.** Cinq des huit extraits illisibles portaient sur des articles hors du sous-ensemble Open Access, où l'API BioC répond une erreur. NCBI en publie le résumé par `efetch`, sans captcha, et c'est là que ces extraits avaient été lus. Ajouter ce texte sans rien dire aurait converti « illisible » en « absent » pour toute citation tirée du corps, c'est-à-dire en accusation de citation inventée sur la foi d'un dixième de l'article. Le module rend donc `TexteNCBI(texte, complet)`, et la relecture retombe sur « illisible » quand le texte est partiel. Après déploiement, les treize extraits jusque-là illisibles s'ancrent tous. Les verdicts étant stockés et sans péremption, une passe de re-vérification a été appliquée en base : les trois extraits restants d'une revue Elsevier sont honnêtement illisibles (Unpaywall confirme l'absence de version ouverte), leur ancien « absent » datait d'avant la détection du mur.

**PR #414 : la fiche vitrine cite ses sources mot à mot.** Les huit extraits de `/@example/memoire-et-cerveau` étaient des paraphrases françaises de sources anglaises. « Relire la source » ne pouvait donc que conclure à l'absence ou à l'illisibilité : la vitrine démontrait l'inverse de la promesse du produit. Les cinq sources qu'un serveur ne peut pas lire n'ont plus d'extrait, les quatre lisibles portent du verbatim dans la langue de l'article. Sept extraits, sept `found` en production. Une traduction, même fidèle, ne se retrouve jamais dans le texte source : c'est une contrainte de conception, pas un détail éditorial.

**PR #416 : un déploiement n'efface plus la relecture de la vitrine.** Le seed supprime et recrée les sources de la fiche de démonstration à chaque démarrage du conteneur, et les extraits renaissaient sans verdict : les sept `found` de la PR #414 auraient disparu au déploiement suivant. Les verdicts sont désormais relevés avant la suppression et reportés, indexés par le couple (URL de la source, texte de l'extrait). Un extrait réécrit repart sans verdict, car lui reporter l'ancien afficherait « retrouvé dans la source » pour une phrase jamais cherchée. Vérifié en production après redéploiement : le seed rejoue, les sept `found` sont toujours là.

**PR #418 : « non vérifiable » ne se dit plus d'un podcast.** Sur la fiche vitrine, douze sources sur dix-huit portaient ce badge, c'est-à-dire toutes celles sans DOI : un dossier Inserm, un article de TIME, un podcast, un livre, des pages de laboratoire. L'infobulle précisait qu'il s'agissait de l'avis de rétractation, mais le badge se lit de loin, à côté de « Accès libre », et le message qui restait était « rien n'est vérifiable ici », sur la page qui vend exactement le contraire. Une revue rétracte un article, pas un podcast : le non-avis n'est affiché que sur un article ou un préprint, et le tableau comparatif y dit « sans objet ». Un avis réellement publié reste affiché partout. Mesuré sur la page déployée : zéro « Non vérifiable », cinq « Aucun avis » sur les cinq articles à DOI.

**PR #420 : la colonne d'identité du tableau reste visible au défilement.** Le tableau comparatif compte huit colonnes et dépasse la largeur de l'écran. En défilant vers la droite pour lire l'accès ou la rétractation, le titre de la source sortait du cadre : il ne restait que des valeurs sans sujet, « Accès payant », « Aucun avis », sans savoir de quelle source. Un tableau comparatif dont la colonne d'identité s'en va ne compare plus rien. Le numéro et le titre sont figés à gauche, avec fond opaque et survol de ligne repris. Vérifié dans le bundle déployé : les classes et leurs règles CSS sont bien émises.

**PR #421 : une source citée mot à mot porte le badge « source clé ».** Quatre sources de la vitrine portaient un extrait verbatim retrouvé dans la source sans être marquées clés, et les deux qui l'étaient ne citaient aucun passage, leurs extraits ayant été retirés en #414 faute de texte lisible. Le lecteur voyait donc la marque de l'appui à côté de ce qui ne l'appuie pas. Citer un passage, c'est déclarer qu'on s'y appuie : un test verrouille désormais la règle sur le seed, toute entrée porteuse d'extraits doit être clé. Mesuré en production après redéploiement : six sources clés dont les quatre porteuses d'extraits, et les sept `found` ont survécu au rejeu du seed.

**PR #423 : la date de relecture survit au redéploiement.** Régression de la PR #416 elle-même : le report de verdicts ne transportait que `verified_status`, laissant `verified_at` et `verified_text_source` repartir à `null` à chaque redémarrage du conteneur. La vitrine affichait donc « Relu dans la source » tout court, une affirmation qu'on ne peut situer ni dans le temps ni par rapport à ce qui a été relu. Le verdict, sa date et sa provenance voyagent désormais dans un triplet nommé, parce qu'ils ne veulent rien dire séparément. La date était déjà perdue en base : une passe de relecture a été rejouée en production contre les pages réelles, sept `found` datés du 2026-08-16, tous adossés à la page publique. Vérifié ensuite par un redémarrage du conteneur : les trois champs sont toujours là.

**PR #424 : une provenance inconnue cesse d'être présentée comme publique.** `lireVerdict` dérivait la provenance d'un seul test : tout ce qui n'était pas « texte fourni » devenait « Relecture faite contre la page publique : quiconque peut la refaire ». Une provenance absente tombait donc du bon côté par défaut, et l'interface promettait une reproductibilité que rien n'établit. C'était précisément le cas des sept extraits de la vitrine avant #423. Trois cas distincts désormais, dont « ce contre quoi la relecture a été faite n'est pas enregistré ».

**PR #426 : la fiche vitrine cesse de rajeunir à chaque déploiement.** L'API de production portait `created_at: 2026-07-18` et `published_at` égal à l'heure exacte du dernier redémarrage du conteneur : le seed reposait la date à chaque passage. La fiche affichait donc « Publiée le » à l'instant même, et le JSON-LD servait ce `datePublished` mouvant aux moteurs et aux agents. Une date de publication qui change sans que rien ne soit publié est une date fausse, sur la page qui sert de vitrine à un produit dont la datation est l'argument. La date n'est plus posée que la première fois. Mesuré en production : identique avant et après un redémarrage.

**PR #428 : « et al. » cesse d'être exporté comme un nom d'auteur.** L'export BibTeX de la vitrine portait la clé `al2010n2` et le RIS la ligne `AU  - al., Brian J. Wiltgen et` : la règle « dernier jeton = nom de famille » prenait l'abréviation pour un nom, et l'auteur réel disparaissait dans le prénom. Le défaut traversait tout ce qui dérive du pivot CSL, jusqu'au tri dans Zotero. L'abréviation est retirée avant le découpage, dans ses variantes anglaises et françaises, avec un ancrage en fin de chaîne qui laisse « Mohammed Al Fayed » intact. Mesuré en production : `@article{wiltgen2010n2}` et `AU  - Wiltgen, Brian J.`.

**PR #429 : le bilan d'export cesse de douter d'un podcast.** Le markdown annonçait « Sur 18 source(s) : Rétractation : 5 vérifiée(s) sans rétractation, 13 non vérifiable(s) ». L'interface avait cessé de le dire en #418, l'export non : c'est pourtant le format que lisent les agents conversationnels, donc eux qui héritaient du doute. Le bilan ne compte plus que la littérature scientifique et les sources portant un avis réellement publié, et il annonce son dénominateur, sans quoi les treize autres se liraient comme en attente d'un verdict qui ne viendra jamais.

**PR #430 : les verdicts Crossref et OpenAlex survivent au seed.** Mesuré juste après le déploiement de #429 : le même document disait désormais « 18 accès jamais vérifié » et « 5 jamais vérifiée(s) », alors que les verdicts avaient bien été obtenus. Même piège que #423 : le seed efface et recrée les sources à chaque démarrage du conteneur, et l'enrichissement paresseux ne les recalcule qu'à la première visite. Les sept champs de verdict sont maintenant reportés, indexés par `(url, DOI)`, un DOI corrigé invalidant la réponse qu'on avait obtenue pour l'ancien. Un test compare les champs reportés à ceux du modèle, pour qu'un champ ajouté plus tard ne disparaisse pas en silence.

**PR #432 : une liste d'auteurs abrégée le reste jusqu'à l'export.** Suite directe de #428, qui retirait « et al. » sans rien mettre à la place : « Brian J. Wiltgen et al. » se citait « Wiltgen, B. J. », et la référence attribuait à une personne un article écrit à plusieurs. Une référence bien formée et fausse coûte plus qu'une référence laide. L'abréviation devient une entrée CSL `literal`, rendue par chaque format dans sa forme, `and others` en BibTeX, une ligne `AU` en RIS, « , et al. » dans les six styles. Le même passage corrige le point doublé de Chicago, servi en production sous la forme « Loftus, Elizabeth F.. 2005. ». Mesuré en production : `author = {Wiltgen, Brian J. and others}`, `AU  - et al.`, zéro double point.

**PR #434 : une archive porte la date de sa capture, pas celle du jour.** Chaque source de la vitrine pointait un instantané Wayback du 1er juin 2024 et annonçait un horodatage d'archive fixé à l'instant du dernier démarrage du conteneur : le même enregistrement portait deux dates de capture, dont l'une changeait à chaque déploiement. Le seed n'était que le révélateur, le chemin utilisateur avait le même défaut : coller une URL d'archive à la main faisait affirmer qu'une capture de 2019 datait d'aujourd'hui. `horodatage_wayback` lit les quatorze chiffres que Wayback place dans ses URLs. Rien n'est complété : un horodatage partiel donnerait un 1er janvier que personne n'a mesuré, et une archive hébergée ailleurs ne porte pas sa date, donc la réponse est l'absence. Mesuré en production : seize sources archivées, toutes datées du 1er juin 2024, aucune archive sans date ni date sans archive.

**PR #436 : chercher dans le corpus atteint enfin les bibliographies.** Le serveur MCP interrogé comme le ferait un agent : « reconsolidation » ramenait une fiche, « engram » aucune, alors que le corpus cite « Optogenetic Stimulation of a Hippocampal Engram Activates Fear Memory Recall » et en porte deux extraits vérifiés. Même silence sur `/discover` : les deux surfaces confrontaient le terme aux cinq colonnes de la fiche et jamais à ce qu'elle cite. Le produit répondait « rien » à la question qu'il existe pour traiter. Le prédicat vit désormais dans un seul module, `exists` corrélé plutôt qu'une jointure pour qu'une fiche citant deux fois le terme reste une fiche et que le décompte des facettes suive les résultats. Titre et auteurs des sources seulement : étendre à la revue ferait remonter toutes les fiches citant Nature dès qu'on cherche « nature ». La description de l'outil MCP, seul mode d'emploi qu'un agent lise avant de choisir, disait encore « par titre ou nom de créateur » : elle dit maintenant ce que la recherche atteint. Mesuré en production : « engram » et « Tonegawa » ramènent trois fiches, « Loftus » et « Optogenetic » une.

**PR #438 : une citation se reconnaît quelle que soit l'écriture de l'URL.** Suite immédiate de #436 : la recherche atteignait enfin les bibliographies, mais les arêtes du graphe de citations dépendaient encore de l'orthographe exacte. Mesuré en production sur un article que le corpus cite bien : `https://www.nature.com/articles/nature11028` ramenait une fiche, et les quatre écritures ordinaires du même lien (en `http`, sans `www.`, avec la barre finale, avec un paramètre de campagne) n'en ramenaient aucune. Un agent recopie ce qu'il a lu, pas la forme que le créateur avait saisie, et le produit lui répondait quatre fois sur cinq que personne ne citait la référence. `find_cards_citing` applique désormais le critère d'identité que le reste du produit tient déjà, `content_identity`, utilisé par `card_link` depuis longtemps : les écritures littérales par un `IN` sur une colonne indexée, plus une branche DOI dans les deux sens, un agent tenant souvent le DOI quand la fiche tient l'URL de l'éditeur. Une URL illisible ne produit aucune clause, donc aucune fiche : elle ne vaut pas « toutes les fiches ». Mesuré en production : les cinq écritures ramènent la fiche, et `https://doi.org/10.1038/nature11028` aussi, forme que le corpus ne stocke nulle part.

**PR #440 : le MCP rend visible l'arête d'une fiche vers une fiche.** Le serveur MCP se présente à l'agent par « naviguer comme un graphe », mais rendait des bibliographies plates. Mesuré en production sur `synaptic-tagging-during-memory-allocation` : deux des 103 sources sont elles-mêmes des fiches Philum, avec leurs propres extraits vérifiés ; un humain le voit sur le web, un agent lisait cent references sans le savoir. `get_card` et `get_source` portent maintenant `linked_card` (`{creator, slug}` ou `null` explicite), revérifié à la lecture avec le même filtre de publicité que partout ailleurs pour ne jamais publier le slug d'une fiche redevenue privée. Mesuré en production : les deux fiches citantes exposent bien l'arête sortante.

**PR #441 : une citation se reconnaît par le lien résolu, pas seulement par l'écriture.** Suite immédiate de #440. La même fiche `nrn3667` est citée par deux fiches sous deux adresses sans aucune sous-chaîne commune : l'une par `https://www.nature.com/articles/nrn3667`, l'autre par le DOI `https://doi.org/10.1038/nrn3667`. Aucune règle syntaxique ne rapprochera ces deux écritures, mais le produit avait déjà résolu chacune vers la même `linked_card` en amont. `find_cards_citing` s'appuie désormais sur ce lien déjà posé, via `resolve_card_by_content` qui refuse déjà une fiche pivot non publique. Mesuré en production : la forme Nature ramène les deux fiches (contre une seule avant), la forme DOI seule n'en ramène toujours qu'une parce que `resolve_card_by_content` ne réconcilie pas l'identifiant Nature `nrn3667` avec le DOI `10.1038/nrn3667` ; défaut de résolution en amont, à traiter séparément.

**PR #443 : une URL laissée en clair dans le titre devient l'URL de la source.** Mesuré sur la vitrine, source de l'American Lung Association : `title` portait « State of Lung Cancer 2024 Report. https://www.lung.org/... (2024). », `url` vide, et le bouton « Version live » cachait un lien mort alors que l'URL était visible en toutes lettres dans le texte affiché. Un parseur libre recopie la citation telle qu'écrite ; le champ dédié reste vide, le rendu ne peut plus rendre le lien cliquable. Passe universelle `promouvoir_lien_du_titre` appliquée dans `_dedupe`, seul point de convergence de tous les parseurs (bibtex, csl-json, ris, markdown, freetext, pdf, docx, html) : elle promeut vers `ref.url` ou `ref.doi` tout lien laissé en clair, puis nettoie la ponctuation orpheline. Ne promeut que ce qui manque ; laisse un titre qui n'était qu'une URL tel quel (mieux qu'un titre vide). Effet sur les futurs imports ; les sources déjà en base restent à corriger via un backfill dédié.

**PRs #444 + #445 : une IA connectée au MCP fabrique une fiche complète de bout en bout.** Le serveur MCP se présentait par « naviguer comme un graphe » mais ne portait que la lecture : produire une fiche exigeait de piloter un navigateur ou de passer par le REST par un chemin parallèle. #444 branche l'identité (même JWT que la session, obtenu via `POST /api/v1/auth/mcp-token` depuis un navigateur connecté, passé en `Authorization: Bearer`) ; #445 ajoute quatre outils d'écriture (`create_card`, `add_source`, `add_excerpt`, `publish_card`) qui délèguent aux mêmes services que le REST, avec les mêmes invariants (unicité du slug, propriété de la ressource, dédup de source par identité du contenu, extrait marqué `suggested_by_ai` et `annotated_by_ai`). Mesuré en production le 2026-08-17 : depuis un token émis pour `mathias-pinault`, `whoami` renvoie `{creator: mathias-pinault}`, `create_card` puis deux `add_source` puis `add_excerpt` puis `publish_card` s'enchaînent sans erreur ; la fiche `mcp-e2e-probe` (créée en `visibility=private` pour ne pas polluer le web) porte deux sources et un extrait avant d'être supprimée. La chaîne complète du geste « je viens de lire un corpus, je te laisse en tirer une fiche » se fait désormais depuis le protocole standard.

**PR #447 : « les sources que vous avez choisies », pas « ces sources et rien d'autre ».** La formulation du hero et de la meta description sonnait comme une restriction imposée. La reformulation dit ce que la personne fait : elle choisit son corpus et l'interroge.

**PR #448 : le créateur ne devient pas l'auteur d'un article qu'il n'a pas écrit.** Mesuré sur la vitrine, fiche seed « Early detection of multiple cancers » (dont `content_authors` est vide) : le meta `citation_author` valait « Mathias », qui est le curateur Philum et non l'auteur de l'article. Zotero et Google Scholar attribuaient donc l'article à Mathias. Le compromis codifié (« sans `content_authors`, Scholar ignore la page ; mieux vaut le créateur que rien ») n'en était pas un : une page invisible de Scholar est un silence, une page fausse est un mensonge qui se recopie. `cardHighwireTags` ne retombe désormais sur le créateur que quand `is_seed === false` — cas où le créateur documente son propre contenu et où le nommer ne ment pas. Le OG `article:author` et le JSON-LD `Article.author` conservent le créateur : leur sémantique est « auteur du document », ce que le créateur reste bien.

**PR #449 : un titre d'extrait qui devient une phrase est refusé.** Le prompt disait « 2 à 6 mots » mais le rempart en code (`_MAX_TITLE_CHARS = 200`) laissait passer une phrase entière. Vu en production : « Chiffre de départ de l'article : la dépense ne bougeant pas avec l'activité mentale, le sommeil ne peut pas être une simple mise en veille énergétique. » Un intitulé sert à *retrouver* dans une liste ; au-delà de huit mots, on ne repère plus, on lit. Nouveau seuil `_MAX_TITLE_MOTS = 8` (marge sur 2-6 pour un article ou une préposition de plus). Un titre plus long est rendu `None` plutôt que tronqué : couper au milieu d'une phrase produirait un intitulé faux au lieu d'une absence claire, même règle que #317, #323 et #327. Appliqué aux deux chemins de génération (`suggest_chunk_titles` et `suggest_annotation`).

**Fiche `liquid-biopsy-multi-cancer-early-detection-and-artificial-in` publiée.** Restée en brouillon dans le corpus mathias-pinault avec 217 sources et 5 extraits, `content_authors` et description renseignés — extraction complète, publication oubliée. Passée en `published` le 2026-08-17 et visible sur le web.

**Constat non corrigé, décision à prendre : le contenu de la fiche vitrine n'existe pas.** `content_url` vaut `https://www.youtube.com/watch?v=memoire-et-cerveau`, un identifiant inventé. YouTube répond 200 mais sert « cette vidéo n'est pas disponible » : le bouton « Voir le contenu » du panneau de fiche est donc le seul lien mort de la page de démonstration, et il porte le contenu lui-même. Trois issues, aucune neutre : retirer `content_url`, ce qui prive la vitrine de la démonstration de l'attestation créateur ↔ contenu ; pointer vers une vraie vidéo tierce, ce qui reviendrait à attester un lien entre une créatrice fictive et le contenu d'autrui ; ou afficher explicitement que ce contenu est un exemple. Les deux premières modifient le triplet `(creator_id, content_url, attested_at)` qui est signé, donc relèvent d'un ADR avec plan de ré-attestation (cf. CLAUDE.md, pivot ADR-019). Non tranché seul pour cette raison.

---

## Session 2026-08-16 (autonome, suite) : une fiche scientifique de bout en bout, et cinq défauts qu'elle a révélés

Fiche construite en se comportant en utilisateur sur un article grand public de 2026 : Nature Communications, « Real-world data and clinical experience from over 100,000 multi-cancer early detection tests » (`10.1038/s41467-025-64094-7`), publiée sur [`/@mathias-pinault/real-world-data-and-clinical-experience-from-over-100-000-mu`](https://filum-eight.vercel.app/@mathias-pinault/real-world-data-and-clinical-experience-from-over-100-000-mu). 50 sources extraites par l'oracle Crossref, 10 qualifiées « source clé », 19 extraits verbatim relevés dans les sources elles-mêmes puis vérifiés par « Relire la source ».

La méthode change tout : au lieu de lister une bibliographie, on va lire les sources citées et on en rapporte les passages qui portent réellement l'affirmation. C'est ce parcours qui a produit les cinq défauts ci-dessous, tous corrigés, déployés et revérifiés en production.

**PR #401 : annoncer une langue rend Springer et Nature lisibles.** Le scraper n'envoyait pas d'en-tête `Accept-Language`. Plusieurs éditeurs répondent alors une page de sélection régionale au lieu de l'article, et Philum concluait que la source était inaccessible.

**PR #402 : un 429 passager ne condamne plus une source.** NCBI répond `429 Too Many Requests` quand on enchaîne les lectures, ce qui est transitoire par définition. Une seule tentative suffisait à marquer l'extrait invérifiable. Un réessai espacé rattrape la plupart des cas.

**PR #403 : un mur de lecture se distingue d'une page vide.** Après plusieurs lectures, NCBI passe du 429 à une page d'interstitiel : `203` avec « Cookies must be enabled » sur PubMed, puis un reCAPTCHA en `200` sur PMC. La page a un corps court mais non vide, donc elle passait pour un contenu légitime où l'extrait était absent. Un extrait bien réel se voyait alors imputer une citation inventée. Trois paliers de détection (signal fort seul, signal faible sous 2000 caractères, signal générique sous 200) rendent désormais le verdict `unreadable`, qui dit « je n'ai pas pu lire » et non « ce n'est pas là ».

**PR #404 : une source citée se voit sans être ouverte.** Sur cette fiche, 14 des 50 sources portent des extraits verbatim, et rien ne les distinguait des 36 seulement listées tant qu'on ne dépliait pas les lignes une par une. Les extraits ne s'affichaient qu'une fois la source ouverte. Un badge de comptage figure maintenant sur la ligne repliée.

**PR #405 : le DOI déposé par l'éditeur n'arrivait pas en base.** Les 50 sources venaient de l'oracle Crossref, où chaque référence porte son DOI et sa revue ; en base, les 50 avaient `doi = null` et `journal = null`. Or les deux vérifications les plus concrètes de Philum sont indexées sur le DOI : la rétractation (Crossref) et l'accès libre (Unpaywall). **Toute fiche scientifique affichait donc « Non vérifiable » sur chacune de ses références.** Point de perte unique : `_s2_ref_to_imported_ref` recopiait titre, auteurs, année et texte brut, et laissait tomber `doi` et `journal`.

Effet mesuré après reprise des 50 sources publiées : 45 DOI posés (les 5 restants n'en ont pas, page produit, rapport, registre), accès libre renseigné sur les 45, et **2 références portent un correctif publié** que la fiche annonçait jusque-là comme non vérifiable. C'est exactement le signal que le produit existe pour rendre.

**Piège de déploiement à retenir.** Le fichier compose de la VM est sous `infra/oracle/docker-compose.micro.yml`, pas à la racine du dépôt. Enchaîner `git pull && docker compose up --build` avec `&&` dans un seul `ssh` rend **exit 0** même quand le rebuild échoue sur `no such file or directory` : le pull a réussi, la VM affiche le bon SHA, et le conteneur tourne toujours l'ancien code. Deux correctifs ont été crus déployés pendant des heures. Toujours vérifier le code réellement embarqué dans le conteneur, jamais le SHA du dépôt.

---

## Session 2026-08-16 (autonome, suite) — une fiche construite en se comportant en utilisateur

Une fiche a été créée de bout en bout depuis l'interface, sans raccourci d'API, sur le rapport GRAM 2022 du Lancet (`10.1016/S0140-6736(21)02724-0`, lu via le miroir ouvert PMC) : [`/@mathias-pinault/global-burden-of-bacterial-antimicrobial-resistance-in-2019-`](https://filum-eight.vercel.app/@mathias-pinault/global-burden-of-bacterial-antimicrobial-resistance-in-2019-). 62 sources, dont 60 extraites par l'oracle Crossref en confiance élevée et 2 ajoutées à la main par DOI, 43 mises en file d'archivage Wayback, 2 sources qualifiées (posture, annotation, source clé), 1 extrait verbatim suggéré par le modèle puis vérifié mot à mot par « Relire la source ».

Le parcours a produit deux défauts que la lecture de code n'avait pas donnés, corrigés dans la **PR #399**, déployés et revérifiés en production.

**Une fiche non revendiquée se disait revendiquée.** Le pied de page affirmait « Contenu revendiqué par son créateur·ice » et « attestée par signature Ed25519 » sur toute fiche publiée. Sur une fiche seed, la même page portait donc deux phrases contraires : le bandeau du haut annonçait qu'elle n'était pas validée par l'auteur·rice du contenu. C'est la promesse centrale du produit qui se contredisait à l'écran. La mention est désormais conditionnée à `!card.is_seed`. Vérifié en prod : absente sur la fiche GRAM (seed), toujours présente sur `/@example/memoire-et-cerveau` (revendiquée).

**Le référencement saisi à la création disparaissait.** Le formulaire demande format, catégorie et type d'auteur ; le type TypeScript les déclarait, mais le payload ne les envoyait pas, `CardCreate` ne les acceptait pas et `CardService.create_card` ne les écrivait pas. Trois champs remplis, aucun message, et une fiche qui affiche « Non déclaré » jusqu'à une édition ultérieure. Les trois étages les portent maintenant, et les gardent facultatifs.

Comportement honnête relevé au passage, sans correctif à faire : le suggéreur d'extraits a répondu « Aucun passage n'a été retenu dans cette page » sur une source hébergée chez Elsevier plutôt que d'inventer une citation.

---

## Session 2026-08-16 (autonome, suite) — audit fonctionnel de la production

Toutes les surfaces ont été exercées contre la production réelle, API puis navigateur, et non par lecture de code. Quatre défauts trouvés, quatre corrigés, déployés, revérifiés en prod.

**PR #392 — un quota épuisé n'éteint plus la couche LLM.** Le quota gratuit de Gemini se compte **par modèle et par jour** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, 20 appels), pas par clé. Au vingtième appel, annotation d'extraits, suggestion d'intitulés, extraction de métadonnées et parsing de bibliographie s'arrêtaient tous ensemble jusqu'au lendemain, alors que la même clé répondait encore sur d'autres modèles. Nouveau réglage `llm_direct_model_fallbacks` : une liste ordonnée de modèles essayés à chaque 429 ou 404. Un 429 ne condamne plus que le modèle visé ; les autres statuts restent terminaux, il n'y a rien à espérer d'un second modèle pour une clé refusée. Capacité quotidienne en production : **20 → 100 appels**. Modèles vérifiés vivants sur cette clé : `gemini-3.6-flash` (primaire), `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-flash-lite-latest`. `gemini-2.5-flash` et `gemini-2.5-flash-lite` rendent 404.

**PR #393 — une référence Wikipedia ne s'intitule plus `ISBN` ni `doi`.** Les modèles `{{cite book}}` et `{{cite journal}}` posent le lien tantôt sur le **nom** de l'identifiant (`ISBN`, `PMID`), tantôt sur sa **valeur** (`978-0-521-58325-1`, `10.1038/nrn1201`, `14523382`). L'oracle prenait le premier lien venu pour un titre. Un libellé doit désormais porter au moins un mot de trois lettres, et les préfixes DOI sont écartés explicitement (leur suffixe contient des lettres et passait le filtre). Vérifié sur l'API MediaWiki en direct : `Working_memory` 186 références, 0 douteuse, 0 sans titre ; `Mémoire_de_travail` 11 références, 0 douteuse.

**PR #394 — chercher sans accent trouve les fiches qui en portent.** Le corpus est francophone, les motifs tapés ne le sont pas : « memoire » ne trouvait pas « Mémoire et cerveau », et une recherche qui répond « rien » se lit comme un corpus vide plutôt que comme une comparaison trop littérale. Migration `037_unaccent` (extension Postgres) et module `db/text_search.py` : `contient()` compare en `OR` le motif littéral et le motif replié, de sorte qu'aucune recherche qui aboutissait ne cesse d'aboutir. `sans_accent()` se compile en `unaccent()` sur Postgres et en identité ailleurs, donc les tests sur SQLite ne mentent pas. Branché sur `/discover`, `/discover/creators`, la liste de fiches du tableau de bord et l'outil MCP `search_cards`. Effet de bord corrigé au passage : `%` et `_` n'étaient pas échappés, chercher « % » ramenait toute la table.

**PR #395 — une recherche d'extraits se recharge et se partage.** `/dashboard/recherche` gardait sa question en mémoire seulement : un rafraîchissement l'effaçait, le bouton Retour ne ramenait rien, un résultat n'était pas partageable. Or la question y est une phrase entière, pas un mot-clé. L'URL la porte désormais, comme sur `/discover`.

**Inventaire vérifié en production** : 14 fiches publiques publiées, 2 créateurs. La fiche Frontiers 651547 affiche **exactement 152 sources**, la cible chiffrée du plan d'extraction agnostique. Aucune erreur console sur l'accueil, la fiche publique, `/discover`, `/discover/creators`, `/feed`, `/features`, `/roadmap`, `/security`, `/about`, `/developers`, `/privacy`, le tableau de bord, l'écran sources et l'écran connexions.

**PR #397 — un agent cherche aussi large qu'un humain.** L'outil MCP `search_cards` ne comparait la requête qu'au titre et au pseudo du créateur, là où `/discover` compare aussi la description, les auteurs du contenu et le nom affiché. Or un agent formule une intention, pas un titre exact : l'écart tombait précisément là où il compte, et zéro résultat se lit comme un corpus vide. Mêmes colonnes des deux côtés désormais. Vérifié en production : « sommeil » et « Bruce Benamran » rendaient chacun zéro fiche avant, une fiche juste après.

---

## Session 2026-08-16 (autonome) — la recherche par le sens existe, et elle marche

Les extraits sont désormais cherchables par le sens depuis `/dashboard/recherche`. Le chantier a démarré sur un constat : Philum calculait un vecteur pour chaque extrait et n'en lisait jamais aucun. Deux issues cohérentes, brancher la recherche ou retirer l'indexation ; c'est la première qui est faite.

**PR #388 — la recherche.** `services/excerpt_search.py` (requête pgvector qualifiée par le schéma lu dans `pg_catalog`, jamais par le `search_path`), route `GET /api/v1/excerpts/search`, composant `ExcerptSearchResults`, écran `/dashboard/recherche`, bac à sable `/sandbox/recherche` pour voir les cinq états sans session. Le service rend `None` quand il ne peut pas répondre, et l'écran le dit : « la recherche n'a pas pu avoir lieu » ne se confond pas avec « aucun extrait ne s'approche ». Script `app.scripts.reindex_excerpts` pour rattraper les extraits saisis avant l'indexation.

**PR #389 — l'indexation était morte en silence.** Le rattrapage lancé en production a rendu `0 vecteurs écrits sur 51 extraits`. Cause : Gemini sérialise en protobuf et élide toute valeur égale au défaut du type, donc le premier élément de chaque lot `/embeddings` n'a pas de champ `index`. Le tri levait une `KeyError`, capturée par le contrat « ne lève jamais » du service. Aucun extrait n'avait jamais eu de vecteur. La position dans le tableau tient désormais lieu d'index absent. 51 vecteurs écrits ensuite.

**PR #390 — le seuil se cale sur des mesures.** Le plancher de 0.30 ne coupait rien : une recherche de tarte tatin rendait cinq extraits sur les phases du sommeil. Mesure sur le corpus réel, six questions étrangères entre 0.473 et 0.560, cinq questions du domaine entre 0.651 et 0.828. `SIMILARITE_MINIMALE` passe à 0.60, et les paliers de proximité découpent la plage utile au lieu de l'intervalle 0..1.

Vérifié en production après déploiement : « recette de la tarte tatin » et « la reproduction des méduses » rendent zéro résultat, « sommeil et mémoire » en rend trois entre 0.71 et 0.73. pgvector est dans `public` sur cette base.

Leçon : une CI verte ne prouve rien d'une fonctionnalité adossée à un service externe. Les tests tournent sur SQLite, qui n'a pas de type `vector`, et le seul journal de la panne était un `Embeddings failed: 'index'` anodin. C'est l'exercice du code path réel sur la VM qui a tout révélé.

---

## Session 2026-08-14/15 (autonome) — l'accueil explicatif revient en prod, réécrit

La page d'accueil de production est désormais la version explicative (hero pulsar dont les sept planètes portent chacune une fonctionnalité), avec **tout son texte réécrit**. Le doublon d'atelier `/sandbox/accueil` est supprimé : la page vit en prod, il n'y a plus de raison de la maintenir en double.

Ce qui change dans le discours, après une dizaine de passes de relecture :

- l'accroche ne promet plus « des bibliographies vérifiables » mais **un espace de travail pour vos sources**, et la lede annonce les trois usages réels : publier pour son audience, retrouver une référence par son contenu, donner un corpus choisi à lire à une IA ;
- une section **« Et pour votre propre travail »** est ajoutée : recherche par le sens dans ses propres extraits, liens entre ses lectures, bibliographie gardée privée jusqu'à la sortie du contenu ;
- chaque phrase nomme les choses (« un article », « la phrase citée », « un paragraphe ») au lieu de « la source » ou « le contenu », et aucun chiffre non adossé au code ne subsiste.

⚠️ La recherche par le sens est annoncée alors que l'endpoint n'est pas encore branché (fondations posées PRs #373-#375). Décision assumée : personne ne visite encore le site.

**Passe de mise en forme (2026-08-15, PR suivante)**, à texte constant, sur retour utilisateur :

- **mobile** : la page débordait de 60 px sur la droite (une valeur en `nowrap` élargissait sa colonne de grille, corrigé par `min-width: 0`), la scène du hero réservait un carré plein écran de vide (rognée par marges négatives sous 1024 px), et un glissement vertical sur le canvas traînait une planète au lieu de faire défiler (`touch-action: pan-y` au pointeur grossier) ;
- **rythme** : les trois sections « D'où vient l'information », « Et pour votre propre travail » et « Interroger une IA » étaient trois grilles de cartes identiques. Elles deviennent respectivement un fil de questions sur rail tracé, un panneau unique à filets et glyphes, et une chaîne de maillons raccordés. La page alterne désormais nuit / jour / nuit ;
- **environnement** : grain SVG sur les fonds sombres (contre les bandes de quantification), halos animés, apparitions décalées au défilement.

**Reprises de forme sur retour utilisateur (2026-08-15, PR #378 puis #379)** :

- une planète traînée hors du cadre rogné passait sous le texte voisin et n'était plus rattrapable : `HeroPulsar` lit désormais les marges négatives de son hôte au `resize()` et borne le déplacement à la zone réellement cliquable ;
- le hero et le fil de questions posaient chacun leur fond : la couture restait visible même à couleurs proches. Ils partagent maintenant un bloc `.nuit-haut` unique qui porte le dégradé, le voile et le grain ;
- le rail du fil de questions démarrait au-dessus du premier point et se terminait en fondu. Chaque question porte à présent le segment qui la relie à la suivante, du centre d'un point au centre du suivant ; la dernière n'en porte aucun. Le tracé est branché sur l'action `reveal` : sans JavaScript le rail s'affiche entier plutôt qu'invisible ;
- les traits de raccord fondus entre les maillons de la section IA sont retirés.

**Reprises de texte (2026-08-15, PR #380 puis #381)**, relecture ligne à ligne avec l'utilisateur. Le texte n'était donc pas gelé : deux passes de plus ont été nécessaires.

- **deux affirmations fausses retirées**, l'une et l'autre vérifiées dans le code avant décision :
  - « Philum retourne régulièrement lire ces citations sur les sites d'origine » : `needs_recheck()` (`services/source_enrichment.py`) ne couvre que `retraction_checked_at` et `oa_checked_at`. **Aucune revérification périodique des extraits n'existe.** Le passage décrit maintenant ce que la fiche publiée affiche pour chaque citation, ce qui est vrai (`lireVerdict` sur la fiche publique) ;
  - l'accès libre était présenté comme une version gratuite coexistant avec un article payant, ce qui sonne illégal. Formulation refaite sur ce que fait réellement `extractors/open_access.py` : interrogation d'OpenAlex, dépôt en archive ouverte (HAL, arXiv, PubMed Central) ou revue en accès libre ;
- **aucun nom d'entreprise** dans le discours : ChatGPT, Claude, Gemini et Word sortent. Crossref, OpenAlex et Zotero restent, en tant que mécanisme interrogé ou format d'export visé, pas en tant que marque ;
- **registre** : « quand ça sort », « à votre main », « trois gestes », « en bas de votre article », « dossier de PDF » sont remplacés ; les titres de section deviennent des questions (« D'où vient l'information ? », « Comment se construit une fiche bibliographique ? ») ;
- les formulations creuses sont remplacées par ce qu'elles voulaient dire : « chaque référence est cliquable » disparaît, l'extrait de démonstration est allongé pour être parlant, et les suggestions automatiques d'intitulé et de contexte sont mentionnées ;
- la lede a fini par « publiez-les pour votre audience, retrouvez une citation sans vous rappeler ses mots exacts, ou interrogez une IA sur ces sources et rien d'autre » (PR #383 ; « chercher par le sens » ne voulait rien dire pour un lecteur).

**Troisième passe de texte (2026-08-15, PR #383)** : neuf corrections de plus, dont une correction de fond. La section IA affirmait que les assistants ne citent pas leurs sources, ce qui est faux : la plupart les citent. Le problème réel est ailleurs, et c'est celui que Philum traite : rien ne garantit que ces sources font autorité ni qu'elles disent ce qu'on leur fait dire.

**Cohérence visuelle sur tout le front (2026-08-15, PR #384)**. Six recettes de verre divergentes coexistaient, chacune inventée sur place (`/85 blur-md`, `/90 blur-xs`, `slate-900/80` codé en dur et donc cassé en thème clair). Une seule recette les remplace.

- `app.css` porte `.glass` (fond translucide, flou, saturation, reflet spéculaire haut) et `.glass-panel` (arête, élévation), pilotées par des jetons `--glass-*` déclinés en clair et en sombre. **Règle d'usage écrite dans le fichier : le verre ne va que sur les surfaces qui flottent au-dessus du contenu** (en-tête collant, menus, fenêtres modales, notifications, surimpressions de graphe) ; toute surface qui porte de la prose reste opaque ;
- deux replis d'accessibilité : `@supports not (backdrop-filter)` et `prefers-reduced-transparency: reduce`. Ce second repli est actif sur la machine de l'utilisateur (réglage Windows « Effets de transparence » désactivé) : **le verre y rend opaque, c'est voulu.** Le reflet, l'arête, l'élévation, l'aura et les micro-interactions survivent toutes au repli, donc la cohérence tient sans le flou ;
- `+layout.svelte` est le vecteur de cohérence, présent sur chaque page : en-tête en verre dont l'arête et l'ombre n'apparaissent qu'au défilement, souligné de navigation détaché du flux qui se déploie depuis le centre, `.page-aura` posée sur toute route sauf `/` (qui a son aurore), et transition de page de 180 ms à la navigation ;
- dix classes désignaient des jetons de thème inexistants (`border-border-subtle`, `bg-surface-elevated`). Elles retombaient silencieusement sur le gris de Tailwind, donc fausses en sombre ;
- relief au survol étendu aux grilles restantes (`discover`, `discover/creators`) et aux rangées du tableau de bord, avec un décalage volontairement plus court sur ces dernières : trois pixels y feraient onduler la liste entière.

Deux pièges de couche de cascade, notés parce qu'ils reviendront : le CSS non calqué en fin d'`app.css` bat les utilitaires Tailwind (d'où la barre d'accent des notifications repositionnée en absolu, le raccourci `border` de `.glass-panel` tuant un `border-l-4`), et une règle scopée par Svelte gagne en spécificité sur `.glass`, ce qui est exactement ce qui permet à `.site-header.is-scrolled` de fonctionner.

**Repli 2D du hero rendu invisible (2026-08-15, PR #385)**, signalé par l'utilisateur : l'illustration SVG de repli était peinte à chaque chargement, puis cédait la place au rendu WebGL en fondu. Deux illustrations différentes se succédaient à l'écran.

Le repli n'est pas supprimé : il reste le rendu final sans JavaScript, en `prefers-reduced-motion`, et si l'import du module OGL échoue ; il porte aussi la description accessible du hero, le canvas étant `aria-hidden`. Il est désormais masqué par `html.hero-webgl`, classe posée par un script en tête de document, donc **avant la première peinture**. Le décider à l'hydratation ne suffisait pas : le clignotement se produit avant l'exécution du bundle. Même mécanisme que la résolution du thème juste au-dessus, dans `app.html`. Le canvas entre en fondu à sa première image, et `fallbackForced` redonne la main au repli si l'import échoue.

---

## ✅ État production vérifié (2026-07-21)

**Prod migrée Railway → GCP + Supabase** (cf. ADR-028). **VM redéployée le 2026-07-21** (commit 464ba95, PRs #179-#181 incluses). Vérifié par curl depuis la VM :
- `https://philum-api.duckdns.org/health` → `{"status":"ok","version":"0.1.0"}` (HTTPS Let's Encrypt via Caddy)
- `POST /api/v1/import/from-content-url` et `POST /api/v1/import/parse` → 401 (auth requise = endpoints déployés)
- `grobid_base_url` dans le conteneur → `https://zfhxi-grobid.hf.space` (défaut code, rien dans le `.env`)
- Fiche démo `https://filum-eight.vercel.app/@example/memoire-et-cerveau` → 200, sources + graphe OK
- Login Google → dashboard OK (redirect URI DuckDNS ajoutée au client OAuth ; l'URI Railway existe encore, à retirer)

Infra : VM GCP e2-micro us-central1 always-free (Ubuntu 24.04, swap 2 GB, Docker Compose `infra/oracle/docker-compose.micro.yml` : backend + Caddy) · Postgres Supabase free (Session pooler **5432**, jamais 6543) · DuckDNS + IP statique GCP. 10 migrations Alembic + seed démo appliqués sur base neuve (secrets régénérés — l'ancienne `master_encryption_key` Railway était un placeholder).

**Railway est décommissionnable** (laissé en secours quelques jours). Boucle retry Oracle (WSL) toujours active en arrière-plan si A1 Paris se libère.

---

## Phase courante

**Phase 3 — Features d'adoption (juillet 2026) : imports/exports, IA, extension, API.**

Livré (mergé) : exports multi-formats (JSON/CSV/BibTeX/Markdown/xlsx/**docx**), imports (BibTeX/CSL-JSON/Markdown/PDF + biblio collée via LLM + multi-liens + **URL de contenu → draft de fiche + sources citées, PR #154**), citations IA vérifiées verbatim, extraction métadonnées durcie (DOI éditeurs + **PII ScienceDirect via Crossref**), fix session 7 jours, durcissement sécurité MCP + **rate-limit 60/min par IP sur `/mcp/` (PR #147)**, extension navigateur MV3 (`apps/extension/`), page `/developers` (docs API + MCP).

✅ **VM GCP redéployée le 2026-07-21** sur `main` (464ba95) : endpoints d'import (#154, #179-#181), rate-limit `/mcp/` (#147) et extraction DOCX/HTML/PDF-GROBID effectifs en prod. Piège connu : toujours vérifier `git branch` avant un pull sur la VM. Note : les 502 juste après `docker compose up` sont normaux (alembic + seed avant uvicorn, e2-micro lente) ; et `docker compose exec backend` doit passer par `uv run python`.

Avant : Phase 2 (identité visuelle Pulsar-graph + audit) et Phase 1 (MVP complet, flow login → création → signature → attestation → publication).

---

## Session 2026-08-10/11 (autonome) — le hero explique au lieu de décorer

**PRs #358, #359, #365 mergées.** La page d'accueil est refaite autour du pulsar : les sept nœuds en orbite portent chacun une fonctionnalité de Philum et un clic ouvre un panneau qui la décrit. `HeroPulsar` gagne trois props optionnelles (`selected`, `onframe`, `timeScale`) et une horloge virtuelle, si bien que la page peut ralentir les orbites sans faire sauter le graphe. La route d'atelier `/sandbox/accueil` a été supprimée au moment du portage : elle ne répondait qu'en dev et un doublon de mille lignes n'aurait servi qu'à diverger.

Le rendu des repères a demandé trois passes, chacune sur un défaut distinct constaté à l'écran :

- **#358** — un clic ne visait jamais juste, la cible dérivant sous le pointeur. Les orbites se figent maintenant au survol de la scène.
- **#359** — les étiquettes sautaient d'un rang à l'autre quand deux planètes se croisaient, parce que l'ordre de résolution suivait la profondeur. Il suit désormais l'identité du nœud, et les positions sont lissées.
- **#365** — le vrai reproche était l'amplitude du mouvement, pas sa brusquerie. La poussée verticale anti-chevauchement a été retirée : les étiquettes tiennent à leur planète, le recouvrement est assumé, et un fondu progressif efface celle qui passe derrière une autre étiquette, une planète plus proche ou le disque du pulsar (`onframe` expose pour ça la géométrie du cœur). Orbites ralenties à 0.45 du rythme nominal.

**VM redéployée le 2026-08-11** sur `main` (`d917981`), `/health` → 200. Le changement est purement frontend (Vercel), le redéploiement backend n'a fait que réaligner le dépôt de la VM.

⛔ **Retiré le même jour (PR #367)**, faute d'un texte à la hauteur : l'accueil est revenu à sa forme précédente et la version explicative a attendu dans l'atelier. ✅ **Remise en prod le 2026-08-15** une fois le texte entièrement réécrit (cf. session du 14/15 août en haut de ce fichier).

---

## Session 2026-08-08/09 (autonome) — aucun format ne perd ce qu'il pourrait porter

**PR #350 mergée** (sha `09bbacd`) — barre optionnelle d'intitulé et de mise en situation par morceau, repliée par défaut, avec suggestion LLM (`POST /excerpts/annotate`). Migration `035_excerpt_context` appliquée en prod.

✅ **La couche LLM est vivante en production depuis le 2026-08-10** (`/health/llm-diagnose` → `status: ok`, suggestions réelles). Gemini est visé directement, sans proxy LiteLLM : `litellm_base_url=https://generativelanguage.googleapis.com/v1beta/openai`, `llm_direct_model=gemini-3.6-flash` (ADR-035). Deux obstacles ont été levés :

- **PR #353** — le backend ajoutait `/v1` à toute racine configurée. Gemini expose sa surface OpenAI sous `/v1beta/openai` : le `/v1` en trop donnait un 404 que la couche avale en silence. **Aucune valeur d'environnement ne pouvait marcher sans ce correctif** — un test entérinait même l'URL fautive. La présence d'un chemin dans la racine tranche désormais entre proxy (hôte nu, on préfixe) et provider direct (chemin déjà là, on n'ajoute rien).
- **Facturation** — la première clé pointait un projet Google en prépayé à crédits épuisés (`HTTP 429`). Un projet en prépayé ne bénéficie plus du free tier. Résolu par une clé sur un projet neuf sans facturation liée.

**PR #354 mergée** (sha `472068f`) — leçon de ce déblocage : `/health/llm-diagnose` disait « l'appel n'a rien rendu, voir les logs » alors qu'il avait le message du provider en main. Un `429 quota épuisé`, un `401 clé refusée` et un `404 modèle inconnu` appellent trois corrections sans rapport, et la couche rend `None` dans les trois cas. La sonde porte désormais un champ `panne` avec la réponse du provider, **clé expurgée** — elle est accessible sans auth.

⚠️ **Piège de vérification** : `curl` vers `philum-api.duckdns.org` **depuis la VM elle-même** rend une réponse vide (le trafic sort et rentre par l'IP publique). Toujours vérifier depuis une autre machine.

**PR #351 mergée** (sha `02bd69e`) — les exports Excel et Word étaient les surfaces les plus pauvres du projet, et le MCP plus pauvre encore : un agent obtenait par `get_source` moins que quiconque téléchargeant le CSV.

- **Tableur** : un tableur n'imbrique pas, donc ce qui ne tient pas en colonne tient en feuille — « Extraits » (jointe par `source_position`) et « Fiches voisines » (par sens et par degré). Le périmètre `include=` était jusqu'ici **entièrement ignoré** en XLSX, tout comme `cited=`/`citing=` : c'est le « les degrés ne sont pas exportables » signalé.
- **Word** : les mêmes faits en sections. C'est le format qu'on lit hors ligne, donc le pire endroit où omettre une rétractation — personne n'ira recouper.
- **MCP `get_source`** : rend désormais le verbatim de chaque extrait, sa mise en situation, le verdict de relecture, la rétractation, l'accès ouvert, le DOI et la position déclarée.
- **`llms.txt`** annonçait 6 formats sur 12 et taisait `include`/`cited`/`citing`.

Deux règles tenues, à ne pas défaire : un champ exclu du périmètre **garde sa colonne, vide** (une colonne absente se lit « ce format ne sait pas porter ça », une colonne vide « il n'y a rien à en dire ») ; et `verified_at: null` reste **silencieux**, parce que « jamais relu » n'est pas « relu et introuvable ».

Vérifié en prod après redéploiement VM : XLSX à 3 feuilles, DOCX portant DOI + position déclarée + extraits, MCP rendant 2 extraits avec `context`/`verified_*`. La fiche de démo n'ayant aucune voisine, la feuille « Fiches voisines » n'a que son en-tête — c'est correct, le cas peuplé est couvert par les tests unitaires.

**PR #352 mergée** (sha `195283c`) — la moitié visible du même défaut. Le backend savait porter le voisinage en XLSX et DOCX, mais le panneau d'export ne le proposait pas : `NEIGHBOUR_FORMATS` excluait les deux et `SCOPED_FORMATS` excluait aussi le CSV, si bien que choisir « Excel » affichait *« Ce format ne sait pas porter de fiches voisines »* devant un format qui le savait. Ajoutée au passage : une feuille **« Sources des voisines »**, sans quoi demander un degré n'aurait rapporté au tableur que des titres — on ne va pas chercher une fiche voisine pour son titre, mais pour ce qu'elle cite. Vérifié en prod : le classeur a bien ses 4 feuilles.

Au passage : `app/api/v1/endpoints/excerpts.py` était resté non formaté après #350 et rendait **`main` rouge** sur `Lint Backend`. Corrigé dans #351. **Leçon** : `Lint Backend` fait tourner `ruff format --check app/`, que ni `ruff check` ni les tests ne remplacent — le lancer avant de pousser.

---

## Session 2026-08-07 (fin) — accessibilite mesuree et cloture des lots B a F

**Parcours visiteur (#78, clos).** Mesure sur le deploiement de prod, pas sur la
PR — sonde iframe 375px dans Chrome, viewport reel 362px, sur
`/@mathias-pinault/ca-sert-a-quoi-de-dormir`. Chrome refuse de descendre sous
~547px de large, d'ou l'iframe.

| mesure | avant | apres |
|---|---|---|
| scroll horizontal | 423px pour 362 de large | aucun (362/362) |
| cibles tactiles sous 24x24 | 8 | 1 |
| `--success` sur son fond de badge | 2,98:1 | 4,54:1 |
| `--warning` sur son fond de badge | 3,24:1 | 4,53:1 |

Le debordement venait du bouton « Partager » : les enfants de la barre d'action
portent `shrink-0`, donc sous ~380px il sortait du conteneur (PR #301,
`flex-wrap`). La cible restante, « En savoir plus », est un lien au fil d'une
phrase : le critere WCAG 2.5.8 l'exempte explicitement (clause « Inline »), et
l'agrandir casserait l'interligne du paragraphe. PRs #301 et #302.

**Signale, pas corrige — arbitrage design en attente.** `--text-placeholder` a
2,17:1 : le monter a 4,5:1 le rendrait indiscernable de `--text-tertiary`
(4,61:1), ce qui contredit son intention documentee. Les bordures de champ
(`--border-strong`) a 1,59:1 contre les 3:1 du critere 1.4.11, en zone
authentifiee seulement. 22 textes sous 12px, essentiellement des etiquettes de
graphe zoomables.

**Interoperabilite (lot E, clos).** Bug reel trouve : `coins.ts` decoupait
`content_authors` sur la virgule seule alors que `citation-meta.ts`, qui
alimente les balises Highwire de la **meme page**, a un `splitAuthors` correct.
Sur `Diamond, A.; Ling, D.S.`, Highwire annoncait 2 auteurs et COinS 4, dont
`A.` et `D.S.` seuls — et Zotero resout COinS avant Embedded Metadata, donc
c'est la version fausse qui gagnait. Corrige et teste (PR #302).

**ADR perime corrige.** `DECISIONS.md` disait « ne pas produire de `llms.txt` »
alors que la route existe et sert un fichier en prod. La route est posterieure a
l'entree : c'est la decision qui visait a cote, elle confondait « mecanisme
d'acces » (ecarte, argument toujours valable) et « panneau indicateur » (retenu,
purement additif). Critere pose pour les cas suivants : est-ce qu'on en
dependrait pour etre lu ? (PR #303)

**Lots B, C, D, F : verifies complets, aucun code manquant.** B1-B5 (marqueurs
de fleche, selecteur de sens a trois positions, imbrication au depliage,
epinglage, acces a la fiche depuis une source absorbee), C1-C3 (migration 026,
API, formulaire et coloration des noeuds fiche par mode de lecture), D1-D4
(migration 027, provenance des liens, `card_connections.py`, ecran
`/dashboard/new/[card_id]/connexions`), F1-F3 (`.docs/ADR-019-bis-preuve-autorat.md`,
`.docs/20-profils-et-feed.md`, perimetre de la garantie dans `DECISIONS.md`).
Le selecteur de sens et les marqueurs de fleche sont confirmes en prod.

**Reste a faire, et pourquoi ca bloque.** Les audits de persona (#74 a #77 :
article de presse d'investigation, video de vulgarisation, essai de blog long
format, rapport institutionnel) demandent de **creer du vrai contenu** sous un
compte reel. Ils ne sont pas faisables sans l'utilisateur. Rappel : le corpus
actuel est un echantillon de un, il ne prouve rien sur le comportement des
createurs.

**Hors de portee d'un agent, a faire par l'utilisateur.** Soumettre le sitemap a
la Search Console — le rendu serveur rend les pages indexables, il ne les indexe
pas ; sans soumission, l'indexation prend des semaines plutot que des jours. Et
le DNS de `philum.app` chez le registrar.

572 tests backend et 132 tests frontend au vert.

---

## Session 2026-08-07 (apres-midi) — securite Supabase et rendu serveur

- **ADR-034 / migration `030_rls_lockdown`** (PR #296, appliquee en prod).
  Supabase exposait le schema `public` en PostgREST : les 11 tables etaient
  sans RLS et les roles `anon` / `authenticated` portaient
  `SELECT, INSERT, UPDATE, DELETE, TRUNCATE` sur toutes, y compris `users` et
  les cles privees chiffrees de `linked_accounts` — avec une cle `anon`
  publique par conception. Verifie apres coup :
  `tables=11 sans_RLS=0 grants_anon_auth=0`, application intacte.
  **Tout nouvel environnement Supabase doit rejouer ce verrou.**

- **Rendu serveur retabli** (PR #297). `src/routes/+layout.ts` portait
  `export const ssr = false` : accueil, pages vitrine et profils renvoyaient
  1477 octets et **zero caractere de texte indexable**. C'est la cause du
  `site:filum-eight.vercel.app` -> zero resultat, donc de l'echec de ChatGPT a
  atteindre les fiches (une couche de navigation IA qui ne trouve rien dans
  l'index ne tente jamais le GET). Le SSR redevient le defaut ; `dashboard`,
  `auth` et `sandbox` s'en exemptent explicitement. Le profil `/@[username]`
  passe d'un chargement en `$effect` (jamais execute en SSR) a un `load`
  SvelteKit, ce qui corrige aussi le soft-404. Mesure en prod apres deploiement :
  `/` 1500 car, `/about` 3406, `/features` 3693, `/discover` 4066,
  `/@mathias-pinault` 1587, `/@inexistant-xyz` -> **404**.

- **Diagnostic invalide a ne pas rejouer** : le `@` dans l'URL n'etait pas la
  cause de l'echec de ChatGPT. Teste avec les deux formes, echec identique.
  Les variantes `/c/<createur>/<fiche>` (PR #295) restent utiles pour les
  agents qui suivent l'en-tete `Link`, mais elles ne reglaient pas le probleme.

- **Serveur MCP** verifie de bout en bout sans authentification sur
  `https://philum-api.duckdns.org/mcp/` (protocole 2025-06-18) :
  `search_cards` et `get_card` repondent. C'est le canal d'acces qui marche
  aujourd'hui pour un agent conversationnel.

## Session 2026-08-07 (autonome) — audits persona #74-#77 : quatre fiches mesurees

Harnais `apps/backend/scripts/audit_personas.py` (PR #306) : il appelle
`parse_content_url` directement — le code exact derriere le bouton « importer
depuis une URL » du dashboard — sans aucune ecriture en base ni en prod.
Quatre URLs publiques reelles, une par persona. Six defauts trouves, chacun
mesure d'abord, chacun corrige par un test ecrit rouge avant le code.

| persona | URL | avant | apres | confiance | sans titre |
|---|---|---|---|---|---|
| journaliste | ProPublica *How the IRS was gutted* | 0 | **12** | medium | 0 |
| vulgarisateur | YouTube 3Blue1Brown *neural network* | 16 (bruitees) | **6** (propres) | high | 0 |
| essayiste | gwern.net *scaling hypothesis* | 0 | **78** | medium | 0 |
| institution | fiche depression de l'OMS | 1 | **6** | medium | 0 |

Les correctifs, par PR :

- **#306** `_resolve_confidence` — l'ecran annoncait « confiance haute » sur
  **zero reference**, c'est-a-dire affirmait que le contenu ne cite rien. La
  promotion medium → high exige desormais que l'oracle ait effectivement
  fourni quelque chose : un resultat vide satisfait « zero ref enrichie » sans
  etre le cas vise.
- **#306** `_fallback_title_from_anchor` — 6 sources sur 11 arrivaient sans
  titre, plusieurs sites (treasury.gov) refusant la visite du backfill. Une
  source sans titre s'affiche comme une URL nue, que le lecteur ne peut pas
  situer. Le texte du lien est le dernier filet, borne a 120 caracteres —
  `raw_text` porte aussi des blocs de reference entiers (Frontiers, PMC).
- **#307** `app/extractors/body_links.py` — un article de presse et un essai
  n'ont pas de section References : leur bibliographie est faite de liens
  poses dans le texte. Sans ce repli, journaliste et essayiste voyaient un
  **ecran vide** la ou la page cite des dizaines de pieces. ⚠️ **Le module ne
  tranche pas ce qui est une source** — il ecarte ce qui ne peut pas en etre
  une (navigation, chrome, boutons de partage, ancres vides) et laisse
  l'auteur·ice arbitrer a l'ecran. D'ou le branchement aux seules pages sans
  section *et* sans refs Crossref, et la confiance maintenue a « medium ».
- **#307** ⚠️ **Le texte du lien n'est pas un titre.** Premiere version :
  `title = label`. Mesure : la fiche affichait « at least $3 billion », et
  renseigner `title` **bloquait silencieusement** `_backfill_url_metadata`,
  qui ne visite que les refs sans titre. Le label part en `raw_text`
  (contexte de citation) ; les vrais titres remontent alors.
- **2026-08-07, revision du repli sur l'ancre** — le repli de #306 valait mieux
  que rien, mais l'audit persona du meme jour mesure ce que « mieux que rien »
  donne : sur **102 titres produits pour les quatre contenus, 15 commencent par
  une minuscule**, et ce sont des morceaux de phrase soulignes — « at least
  $3 billion », « ran for president », « criticized the IRS for loose spending
  on its conferences. » Aucun ne nomme un document ; affiches comme titres de
  source, ils se lisent comme si l'auteur avait cite un texte portant ce nom.
  C'est la regle deja tenue en #317 (`impact_factor`) et #323 (`title='OSF'`) :
  **un titre faux est pire qu'un titre absent**, parce qu'il se recopie dans la
  fiche sans que rien ne signale qu'il ne designe pas ce qu'il pretend. L'URL,
  elle, reste juste. Discriminant retenu : minuscule initiale ⇒ refus, sauf
  majuscule interne au premier mot (`iGPT`, seul vrai titre des 15 ; `arXiv`,
  `eLife`, `iPhone` sont du meme genre).
- **2026-08-08, #341 #342 #343 — l'export a la carte, et deux defauts que 774
  tests verts n'ont pas vus.** Trois briques. #341 : six styles de citation
  (APA 7, Harvard, MLA 9, Chicago auteur-date, Vancouver, IEEE). #342 : un
  perimetre (`?include=annotations,excerpts,archives,reliability`) et les
  fiches voisines par degre **et par sens** (`?cited=`, `?citing=`). #343 :
  le panneau qui permet de les demander.
  Trois points de doctrine s'y jouent.
  **(1) Les deux sens du lien ne sont pas deux valeurs d'un meme attribut.**
  `build_card_graph` les confond, et il a raison : il sert a *dessiner*, et un
  lecteur qui regarde une constellation se moque de savoir par quel bout il est
  entre. Un export ne peut pas se le permettre — « les fiches qui citent
  celle-ci » est la posterite d'un propos, « les fiches qu'elle cite » ses
  fondations ; melangees dans un fichier, on ne sait plus lire la liste. D'ou
  un parcours oriente separe (`export_neighbourhood.py`), et deux zones dans
  l'UI, jamais fondues en un reglage.
  **(2) Un format ferme n'obeit pas au perimetre, et doit le dire.** BibTeX,
  RIS, CSL et les styles suivent des conventions closes : y glisser un extrait
  produirait un fichier que Zotero refuserait. Le panneau grise les cases et
  ecrit la raison — cocher « extraits » et recevoir un `.bib` sans extraits
  ressemblerait a un bug plutot qu'a une convention.
  **(3) Les extraits n'etaient dans AUCUN format.** C'est pourtant le verbatim
  qui relie une affirmation a sa source, la piece la plus specifique a Philum.
  Ils partent desormais avec leur ancrage : sans lui, un extrait exporte n'est
  plus qu'une citation invérifiable.
  Les deux defauts trouves l'ont ete **en imprimant la sortie a l'ecran**, pas
  en lisant des assertions. (a) En Markdown, l'annotation du createur et
  l'extrait de la source se rendaient tous deux `- > texte` — attribuer a un
  auteur une phrase ecrite par le createur de la fiche est la faute exacte que
  Philum existe pour rendre impossible ; les deux voix portent chacune son nom
  desormais. (b) Le voisinage nommait les fiches voisines **sans lier vers
  elles** : un export qui dit qu'une fiche existe sans donner le moyen d'y
  aller ne sert a rien. Ni les 774 tests, ni ruff, ni mypy ne pouvaient voir
  l'un ou l'autre. **Un defaut de rendu est invisible a l'outillage** — c'est
  la troisieme fois cette semaine (#331, #335, ici).
- **2026-08-08 — le texte de la source, depose ou colle : ce qui debloque la
  moitie du web.** La question posee etait « pourquoi la suggestion IA ne
  marche pas ». La reponse tient en une ligne : `litellm_base_url` est vide en
  prod, chaque fonction de `services/llm.py` rend `None` des sa premiere ligne,
  et l'ecran l'annonce honnetement. Ce n'est pas un bug. **Mais ce n'etait pas
  non plus le vrai blocage.**
  Le decoupage est *algorithmique* — il ne lui manque jamais un modele, il lui
  manque du **texte**. Mesure du 2026-08-08 sur dix URLs : cinq n'en rendent
  aucun (NYT, ScienceDirect, treasury.gov et Cell a zero caractere, YouTube
  313). Sur ces cinq-la, « Relire la source » rendait `unreadable` pour chaque
  extrait — ni oui ni non, a vie. Un extrait qui ne peut jamais etre relu n'est
  pas verifiable, et Philum ne repose sur rien d'autre.
  Trois chemins ouverts, tous vers la meme matiere :
  `app/services/document_text.py` (nouveau) lit `.pdf`, `.docx`, `.odt`,
  `.txt`, `.md` ; `POST /excerpts/chunk-file` decoupe un document depose ;
  `/verify` et `/suggest` acceptent desormais un texte fourni et disent
  (`text_source`) contre quoi ils ont conclu.
  Quatre refus assumes, tous du meme genre — **rendre le vide se lit comme une
  reponse** : (1) aucune OCR, un PDF scanne le *dit* plutot que de rendre `""`,
  qui ferait proposer zero extrait sur un document qui en contient cent, et
  deviner le texte d'une image ferait citer a un auteur des mots produits par
  une reconnaissance de caracteres — exactement ce qu'un extrait empeche ;
  (2) aucune troncature silencieuse, un document coupe en son milieu donnerait
  un decoupage qui se lit comme complet ; (3) le `.doc` binaire d'avant 2007
  oriente vers `.docx` plutot que de tirer une dependance lourde ; (4) une
  relecture contre un texte fourni ne se presente pas comme une relecture
  contre la page publique.
  Une seule dependance ajoutee (`pypdf`, pur Python — la VM est une e2-micro
  d'un gigaoctet, un binding compile n'y tient pas). Les `.docx` et `.odt` n'en
  demandent aucune : ce sont des archives ZIP contenant du XML, et l'export
  Word du projet les *ecrit* deja a la main. `defusedxml` et non `xml.etree` :
  le fichier vient de l'utilisateur, la stdlib reste vulnerable a l'expansion
  d'entites.
  Deux bugs trouves par les tests avant tout navigateur, tous deux du meme
  genre : `ElementTree.iter()` est **pre-ordre**, si bien qu'un saut de ligne
  pose en *voyant* un paragraphe atterrit avant son contenu — d'ou une descente
  recursive qui pose le saut a la remontee. Et les `tail` XML sont du
  **contenu** : dans un ODT, la phrase qui suit un passage en gras est le
  `tail` du `<text:span>`, la perdre trouerait le texte au milieu d'une phrase.
  Merge en #344, VM redeployee (image backend reconstruite : `pypdf` est une
  dependance nouvelle) et **chaine verifiee en prod** le meme jour : un `.docx`
  depose rend son texte accents et sauts de paragraphe compris, `text_source`
  vaut `uploaded`, le decoupage suit ; un PDF illisible rend sa consigne
  (`unreadable_document`) et non une erreur generique.
- **2026-08-08, #331 — ce que sept tests verts ne voyaient pas.** L'ecran de
  decoupage (#328, #329) etait couvert par sept tests de composant tenant
  l'invariant « le texte affiche est celui de la source », et n'avait jamais
  ete exerce dans un navigateur : il vit derriere l'authentification Google,
  dans un formulaire a plusieurs etapes. `/sandbox/decoupage` leve cet
  obstacle — atelier dev-only, meme convention que `/sandbox/logo`, reponse
  serveur simulee — et a montre du premier coup un defaut qu'aucun test ne
  cherchait : apres « Ajouter », le morceau etait **fusionne avec son voisin**,
  son texte restait donc affiche et un second clic produisait un extrait
  **chevauchant le premier**. Deux extraits qui se recouvrent se lisent sur la
  fiche comme deux passages distincts de la source. Les bornes partitionnent le
  texte : on ne peut pas en oter un segment sans recoller ses voisins. Le
  morceau reste donc en place, marque `✓ ajoute` ; deplacer une borne fait
  tomber la marque, le passage n'etant alors plus le meme. **Un test de
  composant tient une logique, pas un usage.**
- **2026-08-08, #330 — le prix de cette rigueur, et ce qui n'en faisait pas
  partie.** Le re-audit d'apres #327 compte **8 sources sans titre sur l'essai
  gwern**, la ou le tableau ci-dessus dit `sans titre=0` : ce chiffre est
  desormais perime, et le refus des ancres non-titres en explique une part
  attendue. Restait a savoir laquelle. Sonde
  `scripts/probe_titres_manquants.py`, qui redemande son titre a chacune de ces
  pages sans plafond : **5 des 8 repondaient tres bien** — Wikipedia
  *Activation function*, *Sigmoid function*, *Stochastic gradient descent*…
  Le pipeline ne le leur avait jamais demande. `_backfill_url_metadata`
  plafonnait a 60 visites (`url_backfill capped: 77 candidates -> 60`), un
  plafond qui coupe la liste **a un rang arbitraire**. Sa justification —
  « une biblio de cette taille vient forcement d'une source structuree deja
  traitee » — est fausse pour un essai web de 78 liens nus sans un seul DOI.
  Ce qu'il fallait borner etait la latence, pas le nombre de pages : plafond
  remplace par un budget de temps global (`_URL_BACKFILL_BUDGET_S = 45 s`),
  l'enrichissement se faisant en place, un budget epuise laisse acquis tout ce
  qui est deja revenu. **8 sans titre → 3**, et les trois derniers (openai.com,
  lesswrong, metaculus) n'ont reellement pas de titre a donner : l'URL nue y
  est la reponse honnete. Sonde repassee sur les quatre personas apres
  correctif — journaliste 6 sans titre, vulgarisateur 0, essayiste 3,
  institution 0 ; **les 9 restants sont tous non recuperables**, leur page
  refusant la visite ou ne publiant aucun titre. Le tableau plus haut
  (`sans titre=0` partout) date d'avant #327 et n'est plus a jour : ce n'est
  pas une regression mais le prix assume du refus des faux titres.
- **2026-08-08, #328 — decouper soi-meme le texte d'une source en extraits**
  La suggestion automatique lisait la page, et la page ne se laisse pas
  toujours lire. Mesure du jour sur dix URLs dont les quatre personas
  (`scripts/probe_excerpt_text.py`) : **cinq ne rendent aucun texte
  exploitable** — NYT, ScienceDirect, treasury.gov et Cell rendent zero
  caractere, YouTube 313. Une capture Wayback ne rattraperait ni ScienceDirect
  ni Cell, dont le texte est derriere un paywall : l'archive n'en detient pas
  plus que la page vivante. Le seul chemin qui marche a tous les coups est le
  texte que la personne a sous les yeux et colle elle-meme. D'ou le `422
  no_text` de `/suggest` remplace par une reponse vide qui **declare sa
  provenance** (`text_source`) — une page illisible n'est pas une erreur, c'est
  un etat, et c'est lui qui fait basculer l'ecran sur le collage. Nouveau
  `POST /sources/{id}/excerpts/chunk` adosse a `app/services/chunker.py` (ni
  reseau ni cle, ce qui en fait le plancher sur lequel tout le reste repose),
  taille cible suggeree ou choisie en caracteres / mots / tokens, bornes
  deplacables **de phrase en phrase, jamais de caractere en caractere** : une
  coupe au milieu d'une phrase produit un fragment, et un fragment cite se lit
  comme une affirmation tronquee. Intitules d'extraits facultatifs (migration
  `032_excerpt_title`), saisis ou suggeres — facultatifs parce qu'imposer un
  intitule ferait inventer une etiquette la ou il n'y a rien a dire.
- **#308** `is_creator_self_link` — la fin d'une description YouTube est un
  **bloc de signature** (Patreon, site perso, comptes sociaux, boutique)
  reconduit a l'identique d'une video a l'autre. 11 des 16 sources extraites
  en venaient. Filtre sur le nom de chaine (`videoDetails.author`) dans l'URL
  *et* dans le titre — l'album de la bande-son a une URL Spotify opaque que
  seul son titre trahit. Plancher a 6 caracteres : « Vox » apparait dans
  voxeurop.eu.
- **#309** citations internes — l'OMS cite **cinq de ses propres
  publications**, toutes ecartees comme « liens internes ». On distingue
  desormais par la **position** : un lien pose au milieu d'une phrase de texte
  courant (≥ 80 caracteres autour) est une citation, un lien isole dans un
  bloc court est de la navigation. Plafond a 20 : mesure des « liens internes
  dans une phrase » — ProPublica **0**, OMS **5**, Gwern **238**. Les trois
  regimes se separent nettement ; au-dela du plafond on n'en garde aucun,
  plutot que d'en trier arbitrairement (sinon la fiche Gwern passait de 78 a
  316 sources).

⚠️ **Non verifiable localement, consigne pour arbitrage ulterieur** :
`classification` est `None` sur toutes les sources en execution locale.
L'etage 7 (classification LLM source/promo/social/other) ne tourne pas sans
cle API, donc l'etiquetage promo/social n'a pas pu etre mesure sur ces quatre
personas. A refaire depuis le dashboard en prod.

🔴 **Repondu le 2026-08-08, et la reponse est pire que prevu : la prod non plus
n'a pas de modele.** `docker exec philum-backend env | grep -i llm` ne rend
**rien**, et `infra/oracle/.env` ne definit ni `litellm_base_url` ni
`litellm_master_key`. « A refaire en prod » etait donc sans objet : l'etage 7
n'y tourne pas davantage qu'en local. Trois fonctionnalites sont silencieuses
en prod depuis leur livraison — classification `source`/`promo`/`social`/
`other`, suggestion d'extraits (`/suggest` repond `llm_enabled: false`), et
suggestion d'intitules (#328). **Ce n'est pas un bug de code** : c'est une
variable d'environnement absente, et provisionner un modele est un arbitrage
de cout et de fournisseur qui revient au proprietaire du projet — consigne, pas
tranche ici. Ce qui a ete corrige en attendant (#329) : la case « Suggerer les
intitules » cochait dans le vide sans que rien ne le dise. `ChunkResponse`
porte desormais `llm_enabled` et l'ecran grise la commande — une commande qui
promet un service absent se lit comme une offre, meme faute qu'un titre faux.

✅ **Clos le 2026-08-10** : la variable manquante a ete fournie et Gemini est
vise directement, sans LiteLLM (ADR-035, PRs #353 et #354). Les trois
fonctionnalites listees ci-dessus ne sont plus silencieuses — verifie a l'ecran
sur une source reelle, pas seulement par la sonde. Detail en tete de fichier.

594 tests backend verts. PRs #306 → #309 toutes mergees sur `main`.

### Suite : le manque d'annee (PR #315)

Le re-audit apres #309→#314 ne montre **aucune regression** (12 / 6 / 78 / 6
sources, `sans titre=0` partout) mais un manque massif : `sans annee` = 10/12,
5/6, 35/78, 6/6. Une source sans annee tombe dans la colonne « sans date » de
la frise chronologique.

Sonde 1 : **100 %** de ces sources portent un titre. Le backfill d'URL les
saute donc toutes, par construction (`imports.py:331` et `:386` ne visitent
que les refs *sans titre*).

Sonde 2 — la question decisive, posee aux pages elles-memes : **9 des 10
pages sondees ne publient aucune date exploitable** (treasury.gov,
washingtonpost/archive, colah.github.io, distill.pub, github, openai.com,
incompleteideas.net, who.int, vizhub). Elargir le backfill aux refs « titrees
mais sans annee » couterait des dizaines de visites reseau par import pour
recuperer environ une date sur dix. **Ecarte, faute de justification.**

La 10e page revele en revanche un vrai defaut, corrige par #315 : bioRxiv et
medRxiv collent le numero de version et la variante d'affichage au DOI dans
le chemin. `10.1101/2020.06.26.174482.full` ne retourne **rien** de Crossref ;
le meme DOI sans suffixe retourne titre et date (2020-06-27). Le nettoyage
existait mais n'attendait qu'un separateur `/`, la ou ces serveurs utilisent
un point et les cumulent (`v2.full.pdf`).

Sonde 3 : la date presente dans le *chemin* de certaines URLs de presse
(`/1996/02/03/`) semblait un gisement gratuit — aucune requete reseau. Mesure
sur les quatre personas : **1 source sur 55** sans annee en porte une
(journaliste 1/10, vulgarisateur 0/5, essayiste 0/34, institution 0/6).
Ecrire un extracteur de date d'URL pour une source rendrait le code plus
lourd sans rendre une fiche plus lisible. **Ecarte.**

Apres #315, l'essayiste passe de 35 a **34** sources sans annee : le preprint
bioRxiv a recupere sa date. Reste que la majorite des sources sans annee sont
des pages qui, reellement, n'en publient pas — ce n'est pas un defaut du
pipeline mais un fait du web, et la colonne « sans date » de la frise existe
precisement pour ca.

609 tests backend verts.

## Session 2026-08-07 (autonome) — la surveillance du corpus vaut-elle la peine ?

Question posee **avant** d'ecrire la moindre ligne de produit de veille : sur
les sources reellement publiees, combien de retractations, de liens morts et
de bascules en acces ouvert une surveillance periodique trouverait-elle ? Si
le chiffre etait proche de zero, mieux valait le savoir tout de suite.
Script `apps/backend/scripts/mesure_surveillance.py`, resultat brut dans
`apps/backend/mesure_surveillance.json`.

**643 sources publiees, 575 portant un DOI.** Ce qu'une veille trouverait :

- **6 corrections/retractations** non refletees a l'ecran. ⚠️ **Deux d'entre
  elles sont enregistrees en base comme `unverifiable`** : ce n'est pas une
  absence d'information, c'est une information **perimee et fausse**. La
  fiche affirme « je n'ai pas pu verifier » la ou le papier est corrige.
- **117 bascules en acces ouvert.** Une source enregistree comme fermee est
  devenue librement lisible sans que la fiche le dise. C'est le gisement le
  plus gros, et de loin celui qui sert le plus le lecteur.
- **5 liens morts**, dont **4 DOI `doi.org` qui ne resolvent plus** sur des
  articles anciens (`10.1111/j.1572-0241.*`). Un DOI mort est une promesse de
  permanence rompue : c'est precisement ce que Philum pretend garantir.
- Repartition acces ouvert mesuree : 341 `unverifiable`, 114 `closed`, 36
  `green`, 36 `bronze`, 31 `gold`, 15 `hybrid`, 2 `diamond`.

⚠️ **Biais de mesure a ne pas oublier** : sur les 610 liens testes, **455 ont
repondu « bloque »** (anti-bot). Les 5 morts sont donc un **plancher**, pas
un compte. Le vrai chiffre est necessairement plus eleve, et une veille
devra distinguer « le serveur me refuse » de « la ressource n'existe plus » —
la faute deja payee neuf fois en session 2026-08-04.

**Conclusion : la surveillance a un interet mesure**, porte surtout par les
117 bascules d'acces ouvert et par les 2 etats perimes qui font mentir la
fiche. Le corpus reste toutefois celui d'un seul createur (cf. la limite
consignee ailleurs : il ne prouve rien sur le comportement des createurs en
general).

✅ **Ces deux gisements sont desormais captes par #311**, sans ordonnanceur ni
produit de veille nouveau : le declenchement paresseux existant reprend les
verdicts qui ont vieilli. Trois regimes plutot qu'un delai unique — jamais
sans DOI (aucun service ne sait repondre, le « non verifiable » y est
definitif), 6 h quand le verdict est `unverifiable` **avec** un DOI (c'est une
panne de service, pas un fait), 30 j pour un verdict etabli.

⚠️ **Ce qui reste non justifie par la mesure** : la surveillance des liens
morts. 5 sur 610 seulement, et **455 des liens testes repondent « bloque »** —
le chiffre est un plancher, pas un compte. Construire un produit de veille de
liens sur cette base serait batir sur une mesure qu'on sait aveugle. A
remesurer si l'anti-bot se contourne.

## Session 2026-08-07 (nuit) — chantier 2 : DOI depuis URL editeur

Branche `feat/extraction-pipeline-v2`. Le pipeline d'extraction v2 (ADR-030,
389a291, 2026-07-23) etait deja en prod avec ses 7 etages, ses tests unitaires
et son integration frontend (`extraction_confidence`, `refs_from_oracle`,
`refs_dropped_validation`). Le plan `agent/plans/_archive/2026-08-07-chantiers-conception.md`
listait « chantier 2 pending » a tort.

Ce qui reste vraiment ajoute cette session :
- **DOI derive de l'URL editeur** pour Nature (`10.1038/<slug>`), bioRxiv
  et medRxiv (`10.1101/<date>.<id>` avec strip du suffixe de version `vN`).
  Sans cette resolution, la fiche Nature `nrn3667` faisait echouer tout le
  pipeline : anti-bot bloque le HTML, aucun DOI dans l'URL -> Crossref
  jamais interroge -> zero ref extraite. Maintenant Crossref donne les 152
  refs autoritatives et le blocage anti-bot est sans consequence.

## Session 2026-08-07 (soir) — chantiers de conception

Branche `feat/chantiers-p0-p3-ia-feed-search`, 5 chantiers du plan `agent/plans/_archive/2026-08-07-chantiers-conception.md` :

- **3a** — message anti-scraping oriente maintenant vers l'import fichier (`.ris`/`.bib`) quand Nature/Elsevier/IEEE bloquent. Meme logique pour « aucune section References ».
- **1B** — content negotiation : `hooks.server.ts` reecrit l'URL canonique vers `.md` ou `.philum.json` selon `Accept`. Une seule URL, plusieurs representations.
- **1C** — nouveau format `application/vnd.philum+json` (JSON-LD schema.org + champs Philum : `philum:stance`, `philum:retractionStatus`, `philum:archiveUrl`). Route `.philum.json` et export backend `format=philum`.
- **5** — recherche createurs : endpoint `GET /discover/creators`, page `/discover/creators` avec onglet depuis `/discover`.
- **4** — feed chronologique : migration `028_feed_events`, endpoint `GET /feed` (curseur `before`), page `/feed` groupee par jour, insertion automatique dans `publish_card`. Registre, jamais fil algorithmique.

Migrations a appliquer sur la VM apres merge : **028_feed_events**.

Chantiers restant du plan :
- **2** — pipeline extraction v2 (7 etages, plan `.claude/plans/effervescent-foraging-lollipop.md`), 3-4 j
- **6** — audits persona (#74-#77) : besoin de creer du vrai contenu
- **7** — audit visiteur (#78) : besoin de test mobile

## PRs ouvertes

**`feat/graphe-corrections-visuelles` (en cours, sessions 2026-08-06 / 2026-08-07)** — **graphe, connexions et identité** — PR à ouvrir après la vérification finale :
- **Lot A** (A1-A3) : épaisseur des liens caractérisés réduite, légende repliable, purge des em-dashes.
- **Lot B** (B1-B5) : flèches de sens sur les arêtes fiche→fiche, sélecteur à trois positions (sortant/entrant/deux), imbrication des fiches affichée, épinglage, lien « ★ Ouvrir la fiche Philum » dans l'encadré de source.
- **Lot C** (C1-C3) : migration `026_card_ref` (columns `format`/`category`/`author_kind` sur `biblio_cards`), PATCH API + schéma, sélecteur UI dans le formulaire de fiche, coloration des nœuds fiche selon le mode de couleur actif.
- **Lot D** (D1-D4) : migration `027_link_prov` (`link_origin`/`link_confirmed_at` sur `sources`), `LinkResolution` + `resolve_link()` dans `card_link.py`, endpoints REST de gestion des connexions (`GET/POST/DELETE /api/v1/cards/{id}/connections`), page `/dashboard/new/[card_id]/connexions` avec encart ambre pour les suggestions, liste des citations entrantes en lecture seule, bande d'annulation 8 s.
- **Lot E** (E1-E3) : `coinsTitle()` dans `$lib/utils/coins.ts` + `<span class="Z3988">` sur la fiche publique, balises Highwire déjà en place (#239) ; alertes de citation déjà sur le dashboard (#248) ; décision `llms.txt` → MCP consignée dans `DECISIONS.md`.
- **Lot F** (F1-F3) : `.docs/ADR-019-bis-preuve-autorat.md` (périmètre honnête de la garantie, anti-usurpation, formulations interdites, ORCID, faux) ; `.docs/20-profils-et-feed.md` (feed chronologique, recherche créateurs) ; question feed rétroactivité dans `.docs/07-open-questions.md`.
- **731 tests backend, 131 tests frontend, 0 erreur lint.**
- **Non encore déployé** : les migrations 026 et 027 doivent être appliquées sur la VM après le merge.

**#281 → #287** — Session 2026-08-05 (autonome) — **rendre les fiches trouvables, cesser de servir ce qui était privé, cesser de perdre des références, cesser de confondre une citation avec un titre.** Toutes mergées, VM redéployée et prod vérifiée.
- **#281** `fix/mcp-fiches-privees` — ⚠️ **vraie fuite de données**. Le serveur MCP (ses quatre outils) et l'endpoint d'export public (ses huit formats) ne filtraient que sur `status == "published"`. Or **« publiée » dit que le travail est achevé, « publique » qu'il est offert au monde** : une fiche pouvait être l'un sans être l'autre, et n'importe quel appelant anonyme obtenait la bibliographie complète de fiches que leur autrice avait gardées privées. Prouvé rouge avant correction (4 échecs MCP, 6 échecs d'export — un par format). Le contrôle était recopié à chaque route publique et l'export l'avait simplement oublié : il passe désormais par un `_load_public_card()` unique, qui répond **404 et non 403** pour ne pas confirmer qu'une fiche existe à cette adresse. Le graphe, lui, était déjà protégé.
- **#282** `feat/annuaire-public` — tout était déjà accessible sans compte (HTML rendu côté serveur, JSON-LD portant la bibliographie dans `citation[]`, REST public, MCP anonyme) mais **rien ne permettait de *trouver* une fiche** sans en connaître l'adresse : `robots.txt`, `sitemap.xml` et toute surface de navigation répondaient 404 en prod. Ajoute `GET /api/v1/discover` (recherche plein texte titre / description / auteur du contenu / créateur, filtres plateforme / type / dates, tri, pagination, sans authentification) et `/discover/facets`. ⚠️ **Un seul chemin de filtrage partagé** entre la requête de résultats et celle des comptes, pour que les facettes ne puissent pas diverger des résultats — l'interface n'invente pas ses filtres depuis les enums du modèle, une case à cocher qui ne ramène jamais rien est une promesse non tenue. Page `/discover` avec tout l'état dans l'URL (partageable, et rendue côté serveur pour les crawlers) ; « aucun résultat » et « je n'ai pas pu chercher » restent deux phrases distinctes. `autoescape=True` sur la recherche, sans quoi un `%` saisi ramène tout le corpus. **Vérifié en prod** : 10 fiches publiques rendues en SSR, sitemap à 18 URL, `llms.txt` pointant vers `philum-api.duckdns.org/mcp` (l'annoncer à l'origine du front enverrait un agent sur une 404).
- **#283** `feat/fiches-markdown` — un agent conversationnel à qui on donne `/@créateur/fiche` reçoit du HTML, doit en extraire la bibliographie, **et c'est là qu'il invente**. Suffixer `.md` lui rend le même contenu déjà structuré, servi par l'export markdown du backend — **une seule sérialisation**, donc aucune divergence possible entre ce qu'on télécharge et ce qu'on lit (l'écart entre deux copies d'une même vérité est la faute payée en #263/#264). L'export s'enrichit de ce qui rend une source *vérifiable* et pas seulement citable : rétractation + DOI de l'avis, DOI quand l'URL ne le porte pas déjà, texte intégral gratuit, revue, position déclarée. Bouton « Pour une IA » sur la fiche, `<link rel="alternate" type="text/markdown">` et une entrée dans `llms.txt` pour que l'agent apprenne la convention sans la deviner. ⚠️ **Une mesure a changé le design** : rendu sur la fiche réelle de 185 sources, répéter l'état de vérification sous chaque source ajoutait **370 lignes n'affirmant rien** et noyait les quelques faits qui comptent — le détail par source ne porte donc que des **faits établis**, et le recensement complet passe en tête sous `## Fiabilité des sources`. Rien n'est tu, c'est la place de l'information qui change (796 → 510 lignes) ; « jamais vérifiée », « vérifiée sans rétractation » et « non vérifiable » restent trois phrases distinctes. **Limite mesurée et assumée** : `parse_markdown` récolte toute URL **et tout DOI nu**, donc l'URL d'accès ouvert et le DOI d'un avis de rétractation coûtent chacun une source fantôme au réimport — deux tests le mesurent plutôt que de le taire. **Vérifié en prod** : `text/markdown` sans `content-disposition`, 75 lignes d'accès ouvert, 404 sur fiche inexistante.
- **#285** `fix/scoring-ne-supprime-plus-de-refs-reelles` — une fiche recréée par extraction seule affichait **184 références là où l'éditeur en dépose 187**. Ni Crossref, ni la dédup, ni l'URL obligatoire : l'**étage 6 (scoring syntaxique)** en supprimait trois, silencieusement, alors que chacune portait un DOI valide (mesure locale sur `10.1186/s12916-019-1380-z` : Crossref 187 → dédup 187 → **scoring 184**). Il les jugeait sur le champ `unstructured` de Crossref — **la citation brute entière recopiée dans `title`** — et y voyait des mots dupliqués là où il y avait deux auteurs homonymes (`Nasr I, Nasr I`) et un titre publié reprenant une expression (`... risk of celiac disease: risk of celiac disease ...`). Deux corrections agnostiques : une répétition ne compte comme artefact de concaténation que si elle **recouvre ≥ 50 % des mots** du titre ; et **un DOI résolvable prime sur toute heuristique typographique** — ce module note la cohérence d'un titre, il n'a pas autorité pour supprimer une œuvre enregistrée dont le titre reste rattrapable par résolution. ⚠️ **La cause amont reste ouverte** : `_crossref_reference_item_to_ref` (`url_extractor.py:549`) recopie `unstructured` dans `title` au lieu de le laisser en `raw_text`, ce qui produit aussi les titres dégradés sur les dépôts Springer/BMC (99 % des refs de cet article, contre 0 % chez Frontiers qui dépose structuré).
- **#286** `fix/aucune-reference-ecartee-faute-de-lien` — le `.ris` que Springer expose (`citation-needed.springer.com/v2/references/<DOI>?format=refman&flavour=references` — bien `flavour=references`, pas `citation` qui ne rend que l'article lui-même) compte **187 entrées ; Philum en importait 170**. Les 17 écartées portaient auteurs, année, revue et titre complets : leur seul tort, aucune adresse. **Un livre, un chapitre, un article antérieur au DOI n'en ont pas** — les écarter ampute une bibliographie de ses références les plus anciennes, celles qu'aucune autre voie ne rattrapera. Les trois parseurs (RIS, BibTeX, CSL-JSON) le faisaient au nom d'une contrainte énoncée dans le docstring du module — « le modèle Source exige une URL » — **qui n'existe plus** : `SourceCreate.url` a pour défaut la chaîne vide et un chemin voisin (`_s2_ref_to_imported_ref`) conservait déjà ces refs ; le commentaire avait survécu à la règle. Une entrée n'est désormais écartée que si **rien ne l'identifie**, ni adresse ni titre — sans URL *ni* titre elle reste comptée dans `skipped`, le silence serait malhonnête. ⚠️ `_dedupe` distingue les refs sans lien par titre + auteurs + année : la clé URL vide les aurait **toutes fondues en une seule entrée**. Un test d'intégration tient la chaîne entière, de l'envoi en batch à la relecture — l'extraction ne sert à rien si l'enregistrement refuse ce qu'elle produit. Mesure : `170 / 17 écartées` → **`187 / 0 écartée`**.
- **#287** `fix/crossref-unstructured-titles` — la cause amont laissée ouverte par #285. Springer, BMC et Wiley ne déposent souvent chez Crossref **aucun champ structuré** : seulement la citation entière (`unstructured`), parfois seulement le nom de la revue (`journal-title`). Les deux étaient recopiés dans `title`, ce qui donnait 187 références intitulées `Okada H, Kuhn C. The hygiene hypothesis. Clin Exp Immunol. 2010;160(1):1-9.` — ou pire, `N Engl J Med`. Illisible pour un humain, et **c'est exactement ce sur quoi une IA hallucine** quand elle lit la fiche. ⚠️ **Le titre manquant se résout par le DOI, jamais en découpant la citation** : découper une chaîne de citation est une heuristique qui casse dès qu'un éditeur change de style, alors qu'interroger Crossref sur le DOI rend le titre exact que l'éditeur du papier *cité* a lui-même déposé — exact plutôt qu'heuristique, et valable pour n'importe quel éditeur. Requêtes groupées par 50 DOI (4 allers-retours pour 187 refs). La citation brute est conservée en `raw_text` et ne sert que de **dernier recours**, quand aucun DOI n'existe ; `journal` est stocké à part et n'est plus jamais pris pour un titre. Un échec réseau laisse la référence intacte. Mesure : `10.1186/s12916-019-1380-z` **187 refs, 175 désormais titrées correctement** (les 12 restantes n'ont aucun DOI, la citation brute est le repli honnête) ; aucune régression sur `10.3389/fpsyg.2022.651547` (152 refs, 0 citation brute).
- **Correctif d'accessibilité au passage** : `--text-tertiary` échouait au seuil WCAG AA dans **les deux thèmes** (3,54:1 en clair, 3,59:1 en sombre). Ce token porte dates, compteurs et libellés de filtre, souvent en 12px, sur ~118 usages du dépôt — corrigé **au niveau du token** (#757575 → 4,61:1 ; #8B92A1 → 5,52:1) plutôt qu'en rustine sur la seule page nouvelle, hiérarchie préservée (secondaire à 7,13:1). **Reste ouvert** : `--text-placeholder` clair est à 2,17:1, et il n'y a pas de place entre un placeholder conforme et le nouveau tertiaire — arbitrage produit, pas un patch glissé dans cette PR.

**#257 → #272** — Session 2026-08-04 (autonome) — **audit UX de bout en bout, puis une même faute retrouvée à neuf profondeurs différentes.** Toutes mergées, VM redéployée. Le fil conducteur : *un état ne doit jamais en absorber un autre.* Un délai n'est pas un échec ; rien à archiver n'est pas un échec d'archivage ; un service qui refuse de répondre n'est pas une absence d'instantané ; un canal qui refuse n'est pas l'archive qui n'a rien ; un dépassement de délai n'est pas une réponse ; un panneau indicateur n'est pas la ressource ; une capture de « Redirecting » n'est pas une archive ; une source jamais atteinte n'est pas « en attente », elle est ignorée ; et **« le service a essayé et échoué » n'est pas « le service refuse de me répondre »**.
- **#257** `fix/archivage-cadence` — l'archivage inscrivait `failed` faute d'avoir trouvé à temps. Un délai n'est pas un échec : la source reste `pending` et la reprise paresseuse la repropose.
- **#258** `fix/fiche-demo` — métadonnées de la fiche démo. **Vérifié en prod** : 18 sources, 9 datées, 5 DOI, les 4 positions, 16 archivées, **0 en échec**.
- **#259** `fix/coherence-pages-vitrine` — trois affirmations fausses sur les pages publiques, chacune vérifiée dans le code avant correction : l'inscription Google est ouverte, donc la liste d'attente ne pouvait pas promettre « une notification à l'ouverture ». Six fonctionnalités livrées mais jamais annoncées ont été ajoutées à `/features` et `/roadmap` — **chacune grepée dans le code avant d'être vendue**.
- **#260** `fix/csrf-and-sandbox` — ⚠️ **vraie faille**. `csrf.checkOrigin: false` traînait depuis #22 sans justification écrite ; or le cookie de session est `SameSite=None` en prod et `/api/[...path]` relaie les POST avec ce cookie — une page tierce pouvait soumettre un formulaire authentifié. Rien ne requiert de POST cross-origin (les deux étapes OAuth sont des GET, aucune `action` SvelteKit). Bloc supprimé, **test vérifié rouge quand on le réintroduit**. Au passage `/sandbox` répond 404 hors développement.
- **#261** `fix/archive-not-applicable` — 4 sources sur 152 n'avaient **aucune URL** (manuel DSM-IV-TR, chapitre de livre) et étaient marquées `failed`. Nouvel état `not_applicable`, et surtout **dénominateur honnête** : `archivable_count` exclut ce qui n'a rien à archiver, sinon « 148/152 » était indépassable sur une fiche pourtant complète.
- **#262** `fix/wayback-adaptive-pacing` — mesuré sur la VM : Save Page Now répondait `429` **et** `523` malgré l'intervalle fixe de 6 s ; zéro source archivée sur 152. Deux défauts. ⚠️ **Un intervalle fixe ne peut pas être juste** — les limites d'archive.org ne sont pas publiées et varient avec sa charge. La cadence part d'un plancher, double à chaque refus (`Retry-After` honoré), redescend quand ça repasse, sous un budget de temps par lot. Et `_lookup_snapshot` avalait le 429 pour répondre « aucun instantané » — conclure sur une URL qu'on n'a **jamais réussi à interroger**. Le refus est désormais un signal distinct.
- **#263** `fix/archive-status-schema-enum` — ⚠️ **régression de #261, active en prod, trouvée par la vérification post-déploiement**. `not_applicable` était écrit en base par la migration 024, mais `app/schemas/source.py` redéclarait **sa propre copie** de l'enum, restée à trois valeurs : toute fiche contenant une source sans URL répondait **500**. La fiche de démo n'en contient aucune — elle passait, ce qui a rendu la CI *et* le premier contrôle post-déploiement muets. La copie est supprimée, le schéma réexporte l'enum du modèle, deux tests interdisent la divergence de revenir.
- **#264** `test/enums-parity` — la parade générique à #263, écrite parce que corriger une copie ne dit rien des six autres. Le test **découvre les enums par introspection** de `app.models` et `app.schemas` et exige que toute paire homonyme porte les mêmes valeurs — il couvre donc aussi les enums qui n'existent pas encore. **Vérifié rouge** en injectant une valeur canari dans une seule des deux déclarations.
- **#265** `fix/wayback-cdx-fallback` — toujours zéro archivée après #262. Mesuré depuis la VM, **à la même seconde et depuis la même IP** : `archive.org/wayback/available` répondait `429` pendant que `web.archive.org/cdx/search/cdx` répondait `200` avec l'instantané. ⚠️ **La limitation porte sur le point d'entrée, pas sur l'archive.** Les deux canaux interrogent le même index ; `ThrottledError` n'est levée que si *aucun* n'a pu se prononcer, et une absence n'est affirmée que sur une réponse saine.
- **#266** `fix/wayback-lookup-first` — toujours zéro. Le sondage exécuté **à la main dans le conteneur** trouvait l'instantané de la première URL immédiatement : le lot ne parvenait donc jamais à la phase de sondage. Deux défauts. ⚠️ **On demandait une capture avant de regarder s'il en existait une** — or une bibliographie académique cite surtout des travaux archivés depuis des années, et Save Page Now est la partie la plus lente et la plus limitée du service. Les deux boucles sont inversées. Et ⚠️ **le budget comptait les pauses, pas le temps écoulé** : avec des requêtes de 30 s, un lot tenait des heures sans jamais « dépasser » 900 s. Le test de #257 qui figeait l'ancien ordre a été **réécrit, pas supprimé**, sa justification conservée.
- **#267** `fix/wayback-lookup-timeout` — toujours zéro, et le journal disait `Wayback lookup unusable ... :` suivi de rien. ⚠️ **`httpx.ReadTimeout` a un `str()` vide** — le log taisait sa propre cause. J'ai d'abord soupçonné un corps CDX vide ; `curl` a prouvé que CDX renvoie un `[]\n` parfaitement valide. La mesure a tranché : **18,41 s / 18,68 s / 19,67 s** pour trois appels ne renvoyant rien, contre un délai partagé de 30 s. CDX cherche dans un index de centaines de milliards de captures — il a droit à son propre délai (60 s), et le journal consigne désormais le **type** de l'exception, pas seulement son message.
- **#268** `fix/wayback-resolve-redirects` — toujours zéro, et la mesure a enfin nommé la cause : **les 148 sources en attente sont toutes des `doi.org`**. `doi.org` est un résolveur ; toutes ses captures sont des `302`, le sondage filtre sur `200` et ne pouvait donc rien trouver. ⚠️ **On sondait et on archivait le panneau indicateur au lieu de la ressource.** Le filtre `200` a raison — c'est l'URL visée qui était mauvaise. Résolution par **comportement**, jamais par liste de domaines. Deux pièges réels, chacun testé : les éditeurs répondent `403` aux robots mais la redirection a déjà eu lieu (juger sur le code jetterait une URL exacte), et **doi.org limite lui aussi les rafales** — une résolution impossible laisse l'URL intacte. **Vérifié en prod : 0 → 16 archivées.** Au passage, les recorders des tests existants n'écrasaient pas `_resolve` et faisaient de **vrais appels réseau** (suite wayback : 50 s → 1 s).
- **#269** `fix/wayback-meta-refresh` — trouvée **en lisant le résultat plutôt que le compteur**. Plusieurs des 16 pointaient sur `linkinghub.elsevier.com` ; j'ai ouvert l'instantané : **9,5 ko de HTML pour un seul mot de texte, « Redirecting »**. ⚠️ `linkinghub` répond **200** — aucun client HTTP n'y voit une redirection — avec un `<meta http-equiv="refresh">`. Seize sources affirmaient donc être archivées sur une capture qui ne préserve **rien** : la même faute, un cran plus bas encore. Les deux formes de redirection sont désormais suivies. Garde-fou testé : les deux conditions sont exigées sur la **même balise**, sans quoi un `<meta name="citation_title" content="0; url=…">` déplacerait la cible. Les 23 sources concernées ont été remises en attente par un correctif ponctuel formulé en règle générale (une capture ne vaut que si elle a saisi la ressource).
- **#270** `fix/wayback-refresh-entities` — trouvée **en lisant la sortie de cette réparation**, pas en relisant le code : la résolution rendait `…%3Fvia%253Dihub&`, avec un `&` final seul. ⚠️ Mon motif bornait l'URL sur `;` — or le point-virgule n'apparaît dans une URL de `meta refresh` qu'à l'intérieur d'une **entité HTML**. La cible était coupée au milieu de `&amp;`. Corrigé, la chaîne atteint bien `sciencedirect.com/science/article/pii/…`. **Vérifié en prod après redéploiement** : les 16 `archive_url` pointent toutes vers un éditeur réel (Wiley, ScienceDirect, Cambridge, Frontiers, Hindawi, Taylor & Francis) — plus aucun `doi.org` ni `linkinghub`. Deux instantanés relus : **12 146 et 641 mots**, titres conformes à la référence citée, contre **1 mot** avant. **Limite mesurée et volontairement non corrigée** : CDX cherche l'URL exacte et `linkinghub` ajoute `?via=ihub` ; retirer la requête à l'aveugle transformerait `article.aspx?doi=…` en `article.aspx`, une page générique — on archiverait la mauvaise ressource. Consignée dans les bugs latents.
- **#271** `fix/wayback-tour-de-role` — les 16 archivées de #270 pointaient enfin sur la bonne ressource, mais **132 restaient en attente après six passes de reprise**, avec un journal montrant des réponses CDX saines. La cause n'était ni la résolution ni la cadence : `cards.py` construisait la liste des `pending` **toujours dans le même ordre**, et le lot s'arrête sur son budget de temps. ⚠️ **Les sources situées après la frontière n'étaient jamais atteintes — pas « plus tard », jamais.** Mesuré en résolvant un échantillon à la main : `10.3389/fnsys.2014.00206` et `10.3389/fnhum.2017.00020` avaient une capture `200` disponible à l'instant même et restaient `pending`. Même faute que le reste de la série, une couche plus haut : `pending` disait « en cours de traitement » pour des sources que personne ne traitait. Le remède rend l'état vrai — `archive_attempted_at` consigne **quand on a essayé**, distinctement de `archive_timestamp` qui date **la capture** (les confondre réintroduirait exactement l'erreur corrigée ici), et la file sert d'abord les sources tentées le moins récemment. Garde-fou testé : **marquer une tentative ne conclut rien** — ni `archived` ni `failed`. **Question de backlog tranchée au passage** : retirer les paramètres de tracking avant la requête CDX n'est pas seulement risqué, c'est **mesurément faux** — sur 15 URL, les 4 cas où seule l'URL nue avait une capture renvoyaient **tous la même page générique** `linkinghub.elsevier.com/retrieve/articleSelectSinglePerm`. Quatre articles distincts auraient été marqués archivés sur une seule page de rebond.
- **#272** `fix/wayback-save-outcome` — trouvée **en surveillant l'effet de #271**, pas en relisant le code : le tour de rôle a bien débloqué le sondage (130 → 125 en attente, 18 → 23 archivées après six passes stériles), puis tout s'est figé à 10:09. La phase de **capture** du lot répondait `520` sur toutes ses requêtes, et le service réessayait la même URL en doublant l'attente — 19 s, 30 s, 56 s, 102 s, 127 s — soit **les 900 s du budget brûlées sur sept requêtes et deux URL**, zéro capture demandée pour les 128 autres sources. ⚠️ En lisant le **corps** de ces `520` depuis la VM, ce ne sont pas des refus de service, et ils ne disent même pas tous la même chose : `example.com` → « already captured 5 times today […] please try again tomorrow » ; `sciencedirect.com/…?via%3Dihub` → « Job failed », archive.org a essayé et n'a pas pu — cohérent avec nos propres journaux où l'éditeur répond `403` aux robots. Dans les deux cas le service **s'est prononcé sur cette URL** : redemander la même deux minutes plus tard ne peut rien y changer, et sur le cas du quota **ce sont nos propres réessais qui le consomment**. Le remède : seuls `429`, `503` et `523` disent « reviens plus tard » et ralentissent la cadence ; tout autre code fait passer à l'URL suivante et **laisse la source `pending`** — « archive.org n'a pas pu capturer aujourd'hui » n'est pas « cette page est perdue ». Le critère est le **code de réponse, jamais le corps** : lire de la prose HTML pour piloter un flot de contrôle réintroduirait la fragilité de #269 ; aucune liste de domaines non plus. **Deux garde-fous testés** : `_refusal` reste inchangée, donc sur le chemin du **sondage** un `5xx` demeure une absence de réponse et jamais une absence d'instantané (régression de #262) ; et un `429` reste bien réessayé, pour que le correctif ne devienne pas « on n'insiste plus jamais ».
- **Leçon de méthode** : quatre expériences successives ont été nécessaires pour distinguer « archive.org est en panne » de « nous sommes limités » — et **deux hypothèses intermédiaires ont dû être corrigées** (un `200` isolé s'est révélé être un cache CDN). Instrumenter avant de spéculer, y compris contre soi-même.
- **Décision assumée** : pas de refonte UI. L'interface est cohérente ; c'était la donnée affichée qui était vide ou fausse.

**#251 → #256** — Session 2026-08-03 (autonome) — **passe de sécurité et de dépendances**, une fois les 9 chantiers livrés :
- **#251** `fix/postcss-path-traversal` — la seule alerte Dependabot ouverte (sévérité haute, scope runtime) : postcss ≤ 8.5.17 laissait un `sourceMappingURL` forgé faire lire un `.map` arbitraire au build. Le lockfile était sur 8.5.14. ⚠️ **Le plancher déclaré `^8.5.0` autorisait la plage vulnérable** — il ne suffit pas de bouger le lockfile, le plancher est relevé à `^8.5.25` pour qu'il ne puisse plus redescendre. Même logique appliquée aux autres paquets : `^9.0.0` ou `^5.0.0` permettaient un lockfile très en deçà de ce qui est réellement testé. **Mergée. Zéro alerte Dependabot ouverte depuis.**
- **#252** `chore/deps-patch-minor` — svelte 5.56.8, prettier 3.9.6, @eslint/js 9.39.5, @testing-library/svelte 5.4.2, @tailwindcss/typography 0.5.20. **Mergée.**
- **#253** `chore/deps-actions` — setup-python v7, setup-node v7, codeql-action v4.37.3, trufflehog 6f3c981. ⚠️ De l'infra CI ne se vérifie pas en local : **la CI de la PR elle-même est la seule validation qui vaille**. **Mergée.**
- **#254** `chore/deps-test-majors` — jsdom 30, jest-dom 7. Majeures, mais confinées à l'outillage de test. **Mergée.**
- **#255** `chore/deps-prettier-svelte4` — prettier-plugin-svelte 4.1.1. La crainte usuelle (un reformatage massif noyant les revues suivantes) a été **mesurée plutôt que supposée** : `prettier --write .` ne modifie aucun fichier. **Mergée.**
- **#256** `chore/deps-eslint10` — eslint 10.8.0. ⚠️ **La montée a trouvé un vrai défaut** : la nouvelle règle `no-useless-assignment` a relevé `let host = ''` dans `guessPlatform` (`dashboard/new/+page.svelte`), dont la valeur initiale n'était jamais lue puisque le `catch` sort en retour anticipé. Corrigé en `let host: string`.
- **Méthode** : 15 PRs Dependabot regroupées en 6 PRs par nature de risque (patch/minor, infra CI, outillage de test, formateur, linter), pour ne pas déclencher 15 CI complètes et pour qu'un job rouge désigne sans ambiguïté sa cause.

**#250** — `feat/colonnes-comparaison`. Session 2026-08-03 (autonome) — **chantier 9, la matrice de comparaison sans un seul appel à un modèle**. **Mergée et déployée le 2026-08-03** (sélecteur « Liste / Tableau » rendu côté serveur en prod) :
- Bouton « Liste / Tableau » au-dessus des sources citées. Six colonnes triables — année, type, revue ou éditeur, accès, rétraction, position déclarée — toutes lues dans des champs déjà en base. Rien n'est généré, donc rien ne peut être halluciné : c'est le contrat qui sépare ce tableau des matrices LLM.
- ⚠️ **Aucune case n'est vide.** Le `N/A` indifférencié de SciSpace (étude §2.4) confond « l'information manque » et « le document est inaccessible ». Ici quatre formulations qui ne se recouvrent jamais : *non renseignée* (rien n'a été saisi), *sans objet* (un podcast n'a pas de revue), *non vérifié* (le contrôle n'a jamais tourné), *non vérifiable* (le contrôle ne peut pas conclure). Même règle à trois états que `retraction_status` / `oa_status` ; un `stance` non déclaré n'est jamais rabattu sur « mentionne ».
- Le tri suit la même logique : **une absence n'a pas de rang** et se range en queue dans les deux sens. Troisième clic sur un en-tête → retour à l'ordre voulu par l'auteur. La liste reste montée sous le tableau (`hidden print:block`) car c'est elle qui porte les balises COinS que Zotero détecte.
- 🔧 Bug attrapé au navigateur : le clic sur une ligne ne défilait pas jusqu'à la source. `requestAnimationFrame` s'exécutait avant que Svelte n'ait retiré la classe `hidden` — sans boîte de rendu, `scrollIntoView` est un no-op. Remplacé par `await tick()`.
- Vérifié sur données de prod (Frontiers 651547, 152 références) : **152 lignes, 0 cellule vide**, trois formulations d'absence présentes en réel (152 « non déclarée », 24 « non vérifiable », 13 « non renseignée »). 12 tests unitaires ; 105 tests frontend au vert.

**#249** — `fix/graphe-cadrage-dates`. Session 2026-08-03 (autonome) — **quatre défauts d'affichage du graphe, signalés à l'usage**. **Mergée le 2026-08-03** (frontend seul → Vercel déploie automatiquement) :
- ⚠️ **La mise à l'échelle qui saute.** Le recadrage était appelé à *chaque tick* dès `alpha < 0.06` : le graphe s'affichait, le lecteur commençait à le parcourir, et deux à trois secondes plus tard tout changeait d'échelle. La disposition est désormais déroulée d'un coup (`simulation.tick(n)`) **avant** le premier rendu, puis la vue posée une seule fois. Mesuré sur la fiche Frontiers : **une seule transformation sur 24 s** d'observation. Coût du calcul synchrone ~200 ms, invisible puisqu'il précède l'affichage. (Cet item remplace le « Cadrage initial du graphe Sources » du court terme — le correctif envisagé, « recadrer à chaque tick », était précisément la cause.)
- **Années rognées en frise.** Le bandeau était accroché au sommet du nuage, dont la hauteur dépend de la simulation. Il vit maintenant hors du groupe zoomable, à hauteur fixe, et ne suit le cadrage qu'horizontalement ; le recadrage lui réserve sa place.
- **Date sous chaque nœud**, au même seuil de zoom que le nom d'auteur, avec la même source de vérité que la frise pour que les deux modes ne se contredisent pas. Date inconnue → « s. d. », jamais une place vide qui se confondrait avec un défaut d'affichage.
- **Nœuds fiche** 28→22 px (racine) et 22→19 px (voisines), et ils suivent désormais la densité comme les références. Au passage, redimensionnement et plein écran ne relancent plus la simulation : ils ne changent pas les liens, et réchauffer la disposition faisait dériver un graphe qu'on venait de lire.

**#248** — `feat/citations-entrantes`. Session 2026-08-03 (autonome) — **qui s'appuie sur mes fiches** :
- `Source.linked_card_id` lu à l'envers donne les citations entrantes. Trois règles de prudence : seules les fiches **publiées ET publiques** d'un **tiers** comptent (un brouillon fuiterait, une auto-citation gonflerait le compteur), et la date de la citation est celle où elle est devenue **publique**, pas celle de la ligne en base.
- ⚠️ **`citations_seen_at` est nullable et `NULL` veut dire « jamais consulté », pas « rien de nouveau »** : à la première visite tout est signalé neuf, et l'interface le dit explicitement au lieu de faire semblant. `POST /cards/citations/seen` renvoie l'état **d'avant** le marquage — sinon la visite éteindrait sous les yeux de l'utilisateur ce qu'il vient d'ouvrir.
- 🔧 **Effet de bord notable : les 31 tests adossés à la base ne pouvaient pas tourner sous Windows.** Cause réelle trouvée (et non « Windows ne peut pas ») : Windows stocke les variables d'environnement en majuscules, donc `os.environ["database_url"]` du conftest devenait `DATABASE_URL`, que `case_sensitive=True` (ADR-010) rend invisible à pydantic-settings — repli silencieux sur un Postgres local absent. `case_sensitive` relâché **dans le conftest uniquement** (le garder en prod évite qu'un `DEBUG=1` d'un outil tiers active le mode debug). Résultat : **413 passed en 16 s** contre 369 passed / 31 errors en 147 s.
- Migration `022_citations_seen`. **Mergée et déployée le 2026-08-03**, migration appliquée sur la VM (`alembic current` → `022_citations_seen (head)`), `/api/v1/cards/citations` → 401 en prod (route servie).

**#247** — `feat/ris-import`. Session 2026-08-03 (autonome) — **le sens inverse du pivot CSL** : import RIS + décodage LaTeX. **Mergée et déployée le 2026-08-03.** Validée par un aller-retour réel sur la fiche Frontiers : **148/148 références ayant une URL relues avec titres et auteurs intacts**, 0 titre vide, 0 auteur manquant. Les 4 « perdues » sur 152 n'ont **ni URL ni DOI** en base — exactement le cas que le compteur `skipped` est fait pour exposer plutôt que masquer.

**#246** — `feat/csl-pivot-ris`. Session 2026-08-03 (autonome) — **CSL-JSON devient le pivot, RIS s'ajoute** :
- BibTeX et RIS sont des formats de *sortie*, pas des pivots. Les faire descendre d'un même `app/services/csl.py` garantit qu'ils ne divergent pas : un champ corrigé l'est partout. Neuvième format d'export (`?format=ris`, EndNote/Mendeley/Zotero).
- ⚠️ **Le point dur est le nom d'auteur.** Philum stocke une chaîne libre, CSL attend `{family, given}`. L'ancien code passait tout en `[{literal}]` (tri dégradé dans Zotero) **et** cassait `"Dupont, Marie"` en deux co-auteurs. La virgule joue deux rôles : `"Dupont, J."` est *un* auteur, `"Dupont J., Martin A."` en fait deux. Le découpage s'appuie d'abord sur les initiales (seule marque typographique fiable), puis sur la parité des morceaux mono-mot. **Pari assumé et documenté** : il peut se tromper sur `"Bell, Aron"` (deux auteurs sans prénom), chaîne que rien ne distingue d'un auteur unique — **le point-virgule lève l'ambiguïté et reste la forme à préférer**.
- Deux bugs trouvés par les tests pendant l'écriture : un auteur fantôme `{family: ""}` sur une chaîne de séparateurs seuls, et une clé de citation qui donnait `cerveau` pour « Mémoire et cerveau » (un titre n'a pas de nom de famille).
- RIS : vocabulaire fermé dérivé du type CSL (défaut `ELEC`), un auteur par ligne `AU`, `ER  - ` obligatoire — sans lui les lecteurs fusionnent silencieusement toutes les références en une seule ; note multi-ligne repréfixée `N1` ligne par ligne.
- **Mergée et déployée le 2026-08-03.** Vérifié en prod sur la fiche Frontiers : **152 enregistrements RIS, 152 `ER`, 0 ligne malformée** ; CSL et BibTeX rendent `{family, given}` sans `literal` résiduel (`author = {Adleman, N. and Menon, V. and …}`). 49 tests unitaires, dont un qui vérifie que RIS et BibTeX découpent les noms à l'identique — la garantie de non-divergence du pivot.

**#245** — `feat/open-access`. Session 2026-08-03 (autonome) — **où lire gratuitement une référence payante** :
- Une bibliographie qui renvoie à un paywall arrête le lecteur net. OpenAlex agrège les routes d'accès libre (dépôt HAL, revue en libre accès, version acceptée chez l'éditeur) et expose au passage le référencement DOAJ de la revue — l'item DOAJ du chantier 3 est donc réglé sans seconde intégration.
- ⚠️ **Même règle à trois états que les rétractations.** `NULL` = jamais vérifié · `closed` = OpenAlex connaît la référence et ne trouve rien de gratuit, **information positive et datée** · `unverifiable` = pas de DOI, DOI inconnu, service muet. Afficher « payant » dans le troisième cas détournerait le lecteur d'une version libre qui existe. `in_doaj` est **nullable** pour la même raison : `False` affirmerait que la revue n'est pas référencée.
- Migration `021_source_oa` (`oa_status`, `oa_url`, `oa_license`, `in_doaj`, `oa_checked_at`). `retraction_check.py` devient `source_enrichment.py` : une seule passe, mais chaque service enveloppé **séparément** — une panne OpenAlex n'efface pas un verdict de rétractation obtenu, et deux pannes n'écrivent **rien** plutôt que de dater une vérification qui n'a pas eu lieu.
- `freeReadUrl` refuse de rendre un bouton mort (statut libre **et** URL en `http`). Le badge compact ne signale que l'accès libre : un « payant » gris sur 152 références serait du bruit ; le verdict complet et daté vit dans le panneau déplié.
- **Mergée et déployée le 2026-08-03**, migration `021` appliquée. Vérifié en prod sur la fiche Frontiers (152 sources) : **0 NULL** — 76 `closed`, 24 `gold`, 20 `green`, 13 `bronze`, 7 `hybrid`, 12 `unverifiable` (exactement les 12 sans DOI). **64 références lisibles gratuitement avec un lien réel** là où la fiche n'en signalait aucune. DOAJ : 88 `None` / 36 `False` / 28 `True`. Vérification visuelle navigateur non faite.

**#243 + #244** — `feat/graph-cap`, `feat/graph-chrono`. Session 2026-08-03 (autonome) — **le graphe reste lisible, et il sait dire le temps** :
- #243 borne le rendu aux 60 premières références (`GRAPH_SOURCE_CAP`). La troncature n'est **jamais silencieuse** : bouton `+N autres` / `Réduire à 60` dans la barre d'outils et mention permanente « N sur M références affichées » dans la légende — un graphe de 60 nœuds sur 152 ne doit pas passer pour un graphe complet.
- #244 ajoute un second axe de lecture (bascule Réseau / Chronologie). Le maillage dit qui dépend de qui, jamais l'ancienneté : « cette affirmation s'appuie sur un article de 1998 » est une information qu'il ne peut pas porter.
- ⚠️ **Une source sans date connue ne reçoit jamais une position inventée sur la frise.** Elle est garée dans une colonne hachurée à part, étiquetée « sans date (N) ». Les cas dégénérés sont tous testés : rien de daté (tout au centre, aucune graduation), une seule année (centrée et non écrasée à gauche), et les bornes réelles toujours graduées — une frise 1998-2024 par pas de 5 commencerait à 2000 et ferait croire que la source la plus ancienne date de 2000.
- Les nœuds de jonction restent libres (pas de date propre, ils tireraient leurs branches vers une année qu'ils n'ont pas) et `forceCenter` est désactivé en frise (il ramènerait une source de 1998 vers le milieu). **Mergées, frontend seul → Vercel.**

**#241 + #242** — `feat/retraction-badge`, `feat/retraction-lazy-check`. Session 2026-08-03 (autonome) — **une source dit si l'article qu'elle cite a été rétracté** :
- Une bibliographie qui cite un article rétracté le cite pour toujours : une fois le contenu publié, ni le lecteur ni l'auteur de la fiche n'ont de moyen de l'apprendre. Crossref agrège Retraction Watch et expose les avis sur `works/{doi}` (champ `updated-by`), vérifié empiriquement avant d'écrire une ligne.
- ⚠️ **Trois états, pas deux.** `NULL` = jamais vérifié · `none` = Crossref connaît le DOI et ne signale rien, **information positive et datée** · `unverifiable` = pas de DOI, DOI inconnu, service muet. Afficher « aucune rétractation » dans le troisième cas serait un mensonge par omission. Le plus grave l'emporte (corrigé en 2004 puis rétracté en 2010 → « Rétracté ») et un type Crossref inconnu retombe sur `concern` : inviter à vérifier plutôt que rassurer à tort.
- Migration `020_source_retraction` (`retraction_status`, `retraction_notice_doi`, `retraction_checked_at`). Champs **read-only** sur `SourceResponse` seulement : dérivés machine, jamais saisis.
- #242 comble le trou de #241 : la vérification ne partait qu'à la création, donc toute fiche antérieure serait restée muette indéfiniment. L'affichage d'une fiche publique planifie désormais le contrôle des sources jamais vérifiées, via `app/services/retraction_check.py` (garde anti-doublon + séquentiel sur le lot — le projet n'a pas d'ordonnanceur).
- **Mergées et déployées le 2026-08-03**, migration `020` appliquée. Vérifié en prod sur la fiche Frontiers (152 sources) : **139 `none`, 12 `unverifiable` (exactement les 12 sans DOI), 1 `corrected`** avec le DOI de l'erratum (`10.1016/j.jecp.2017.04.001`). Vérification visuelle navigateur non faite.

**#240** — `feat/source-stance`. Session 2026-08-03 (autonome) — **le rapport déclaré entre une source et le propos** :
- Une bibliographie dit sur quoi on s'appuie, jamais comment. Quatre valeurs déclaratives (`appuie`, `nuance-contredit`, `mentionne`, `contexte`), migration `019_source_stance`, arêtes colorées dans le graphe et légende conditionnelle.
- ⚠️ `NULL` (non déclaré) n'est **jamais** ramené à `mentionne` : l'un est un silence, l'autre une réponse. Invariant tenu dans le modèle, le schéma, le sélecteur (« Non déclaré » en premier), la légende et trois tests.
- Point dur : une source qui désigne une fiche Philum est absorbée en arête fiche→fiche et disparaît comme nœud — sa position déclarée se serait perdue précisément sur les liens qui structurent le graphe. Résolu par `card_edges` en dict avec règle de fusion (premier non-nul gagne). **Mergée et déployée.**

**#239** — `feat/citation-meta`. Session 2026-08-03 (autonome) — **meta tags Highwire + COinS sur les fiches publiques** :
- Google Scholar exige titre + premier auteur + année ; Zotero résout dans l'ordre translator > unAPI > COinS > DOI. Les fiches n'exposaient rien : ni indexables, ni capturables en un clic.
- COinS avec trois contextes OpenURL (`journal`, `book`, **`dc`**) — c'est le contexte Dublin Core qui rend l'export agnostique : sans lui une source YouTube devrait mentir sur son genre pour être exportable.
- **Mergée et déployée.** Vérifié dans le HTML servi par Vercel : 5 tags Highwire, 18 spans COinS pour 18 sources.

**#238** — `feat/card-content-authors`. Session 2026-08-03 (autonome) — **la fiche porte enfin les auteurs de son contenu** :
- Suite directe de #237, qui n'avait changé que la règle de préséance sans régler le manque de donnée : le nœud racine continuait d'afficher « Mathias ». ⚠️ **Une fiche n'avait aucun champ d'auteurs.** La seule source était `Source.authors` d'une source *d'une autre fiche* pointant vers elle (`_load_card_authors`) — donc rien du tout quand personne ne cite. Le repli sur le créateur était correct au regard du code et faux au regard du sens.
- Colonne `biblio_cards.content_authors` (migration `018_card_authors`, backfill depuis les sources citantes en gardant le candidat le plus long). Trois voies d'alimentation, pour couvrir toutes les situations : backfill des lignes existantes, PATCH opportuniste après import (l'extraction connaît déjà les auteurs via Crossref/JSON-LD/OG), et champ « Auteurs du contenu » dans l'éditeur de fiche (seul recours pour une fiche saisie à la main et jamais citée). `/import/url-metadata` expose désormais `authors` pour pré-remplir ce champ.
- Préséance à trois étages dans `card_graph.py` : `content_authors` déclarés → reconstitution depuis les fiches citantes → créateur. La fiche fait foi sur son propre contenu.
- Correction de rendu associée : d3 pose les étiquettes **impérativement** dans `mountGraph()`. `rootAuthors` arrivant après coup, le garde de remontage `if (neighborCards.size > 0)` laissait le nœud avec le nom de son créateur — devenu `|| rootAuthors`.
- Nouveau `CardDetailPanel.svelte` : cliquer un nœud fiche (racine, ou voisine sans source à déplier) ouvre un encadré — auteurs, date, nombre de sources, description, lien vers le contenu, créateur. Pendant du `SourceDetailPanel`, mêmes règles de placement ; les deux panneaux s'excluent.
- **Mergée et déployée le 2026-08-03.** Migration `018_card_authors` appliquée sur la VM (`Running upgrade 017_link_by_content -> 018_card_authors`), backend sain. Vérifié en prod : la fiche Frontiers renvoie `content_authors = "Kang W., Hernández S., Rahman M., Voigt K., Malvaso A."` et son nœud racine les porte dans `/graph`.
- Reste attendu : la fiche `f99a1b64` garde `authors: null` — personne ne la cite avec des auteurs et elle n'a jamais été importée. C'est le cas résiduel que la saisie manuelle est là pour couvrir, pas un défaut.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : l'encadré du nœud fiche n'a pas été observé en conditions réelles.

**#237** — `feat/root-node-identity`. Session 2026-08-03 (autonome) — **une fiche se nomme par les auteurs du contenu, pas par son créateur Philum** :
- Le nœud d'une fiche revendiquée affichait le créateur (« Mathias »), laissant croire qu'il était l'auteur de l'article ou de la vidéo décrits. ⚠️ Revendiquer une fiche, c'est répondre de sa bibliographie, **pas** signer le contenu cité : la distinction `is_seed` n'avait pas lieu d'être dans l'étiquetage. Les auteurs réels priment désormais toujours, le créateur n'étant qu'un repli ; `isSeed` disparaît de `CardLabelInput` et de ses trois sites d'appel.
- Le nom du créateur ne pouvant plus servir de « vous êtes ici », le nœud racine se distingue par un fond indigo profond `#312e81` (les voisines restent ardoise `#1e293b`) **et** un anneau plein. Redondance couleur + forme volontaire : la distinction doit tenir en vision des couleurs réduite. La vue constellation distinguait déjà sa racine en ambre, inchangée.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : les couleurs et le halo n'ont pas été observés en conditions réelles.

**#236** — `fix/expand-badge-size`. Session 2026-08-03 (autonome) — **la pastille de dépliage montre son nombre en entier** :
- Le disque de 8 px de rayon tronquait son propre libellé dès deux chiffres : sur une fiche de 306 références, la pastille censée annoncer ce que le clic révèle ne le montrait pas. Elle n'était pas non plus une cible cliquable acceptable, alors que #235 venait d'en faire la seule prise du dépliage.
- Gélule de hauteur fixe (18 px) dont la largeur suit le libellé. ⚠️ Elle part du point où se tenait le disque et s'allonge **vers l'extérieur** : la centrer ferait mordre un nombre à trois chiffres sur le nœud. La pastille « − » adopte la même hauteur, pour que les deux actions se lisent comme un seul contrôle à deux états.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : la largeur est approximée sur l'avance des chiffres, à contrôler sur un nombre à trois chiffres.

**#235** — `feat/card-node-source-panel`. Session 2026-08-02 (autonome) — **l'encadré d'une référence reste ouvrable quand elle est rendue comme fiche** :
- Depuis #233, une référence qui fait l'objet d'une fiche **est** le nœud fiche. Mais ce nœud ne gardait aucune trace de la référence absorbée et son clic servait à déplier : revue, DOI, date et annotation devenaient inatteignables. Le nœud reprend désormais la référence (`absorbedSource`).
- **Cliquer un nœud ouvre son encadré, source ou fiche.** La règle cesse de dépendre de la représentation choisie par le graphe — ce qu'un lecteur ne peut pas deviner. Déplier/replier passent aux pastilles, qui les annonçaient déjà : « +N » déplie, « − » referme, les deux avec `stopPropagation`.
- **Mergée le 2026-08-03** (frontend seul, déploiement Vercel automatique). Vérification visuelle navigateur **non faite** (extension Chrome déconnectée).

**#234** — `fix/seed-demo-real-urls`. Session 2026-08-02 (autonome) — **la fiche d'exemple ne cite que des pages réelles** :
- Sept des dix-huit références de `/@example/memoire-et-cerveau` pointaient vers des pages inexistantes ou tout autres : l'URL Nature rendait un article de Virginia Gewin sur le racisme dans la science, l'URL Simon & Schuster un roman d'Emma Fedor, et Lex Fridman / Wellcome / YouTube étaient en 404. Une vitrine dont les liens mentent contredit exactement la promesse du produit.
- Remplacées par TIME (Purtill), Quanta (Svoboda), CNRS Le Journal (Gros), Radiolab (« Memory and Forgetting », transcript confirmant Karim Nader), Penguin Random House (le vrai éditeur de Genova), Wikimedia Commons (planche de Cajal, 1911) et « Building Blocks of Memory in the Brain » (Kirsanov). **Chaque URL a été ouverte** et son titre, auteur et date vérifiés sur la page servie.
- ⚠️ `nytimes.com` et `lemonde.fr` bloquent toute vérification automatique : proposer une autre URL sur ces domaines aurait reproduit le problème. La Wayback Machine n'a **aucun** instantané des deux URL d'origine — alors qu'un vrai article NYT Well ou Le Monde Sciences est systématiquement archivé : elles étaient fabriquées.
- **Mergée et déployée le 2026-08-02** (aucune migration ; `_get_or_create_demo_card` supprime et recrée ses sources à chaque exécution, le redéploiement suffit). Vérifié par curl : les 18 URL en prod sont les nouvelles.

**#233** — `feat/source-card-identity`. Session 2026-08-02 (autonome) — **une source rejoint la fiche qui documente le même contenu** :
- Une référence vers un article et la fiche Philum qui documente cet article sont le même objet. Le lien ne dépendait que d'un clic manuel dans le picker ou d'une URL `/@user/slug` : sur la fiche `examining-…`, la source vers `doi.org/10.3389/fpsyg.2022.651547` flottait isolée alors que la fiche `inhibitory-control-…` existait pour ce DOI exact.
- `content_identity.py` (module pur, 20 tests) : deux références désignent le même contenu si elles partagent un DOI ou une URL normalisée. Critère **agnostique** — vaut pour un article, une vidéo, un blog ou un rapport, sans connaître le domaine. ⚠️ Le `/full` de Frontiers et le `/pdf` de Wiley sont retirés du DOI : sans ça la clé extraite d'une URL d'éditeur ne correspondait jamais au DOI nu saisi sur la source qui la cite, et le rattrapage ne faisait silencieusement rien.
- **Matérialisé à l'écriture, pas résolu à la lecture** : trois points d'application (création/batch/édition de source, publication de fiche, migration `017` de rattrapage). Résoudre dans `card_graph` aurait été auto-réparateur mais laissait `find_cards_citing`, la constellation et le sens entrant aveugles.
- La publication d'une fiche rattrape les références déjà saisies vers son contenu : une fiche existe souvent **parce que** quelqu'un a cité le contenu.
- `_load_card_authors` retient désormais la liste d'auteurs la plus complète (« Kang » d'un côté, « Kang W., Hernández S., Rahman M., Voigt K., Malvaso A. » de l'autre), la plus ancienne départageant à longueur égale.
- **Mergée et déployée le 2026-08-02** (migration `017_link_by_content` passée). Vérifié par curl sur `examining-…?depth=3` : le nœud source isolé a disparu, la 3ᵉ arête `is_card` racine → `inhibitory-control-…` est apparue, et le nœud fiche porte la liste d'auteurs complète.

**#232** — `fix/graph-fade-and-seed-banner`. Session 2026-08-02 (autonome) — **apparition du graphe et place du bandeau seed** :
- Le graphe s'allumait nœud par nœud pendant que les liens gris étaient dessinés d'emblée : des traits flottaient entre des extrémités invisibles, et l'animation durait quinze secondes sur une fiche de 300 références. Le groupe racine est désormais fondu d'un bloc en 350 ms. Fondre le parent plutôt que chaque nœud évite en plus le conflit avec le `$effect` de survol/recherche, qui écrit lui aussi l'opacité des `.node`.
- Le bandeau « fiche non revendiquée / Réclamer cette fiche » passe **sous** le graphe : c'est une réserve sur la provenance, pas la première chose qu'un visiteur doit lire.
- **Mergée le 2026-08-02** (frontend seul, déploiement Vercel automatique).

**#227** — `feat/graph-search`. Session 2026-07-31 (autonome) — **recherche dans le graphe** :
- Barre de recherche sur `SourceGraph`. Elle porte sur tout ce qui identifie une référence — titre, auteurs, revue, éditeur, DOI, URL, année, **et les libellés lisibles** du type d'auteur / format / catégorie (taper « article scientifique » fonctionne, pas seulement le code `article-scientifique`). Insensible à la casse et aux accents ; termes combinés en **ET à travers les champs**, si bien que `madigan 2023` trouve la référence alors que le nom et l'année ne sont jamais adjacents dans le texte indexé.
- **Le backend devait suivre** : le méta-graphe ne renvoyait ni `journal`, ni `publisher`, ni `doi`. Sans eux, une source de fiche voisine aurait été introuvable sur des critères qui trouvent une source de la racine — le filtre aurait donné des résultats différents selon la provenance du nœud.
- Rendu : les non-correspondants s'effacent (opacité 0.08) au lieu de disparaître, une arête reste visible dès qu'**une** extrémité correspond (elle dit à quelle fiche le résultat est rattaché), et un résultat affiche son titre quel que soit le zoom. Compteur + « Recadrer » (aussi sur Entrée).
- ⚠️ L'index de recherche est calculé **une fois par montage**, pas à chaque frappe : 300 nœuds re-normalisés à chaque caractère seraient sensibles. La logique de correspondance vit dans `$lib/utils/graph-search.ts` (fonctions pures, 11 tests).
- **Mergée et déployée le 2026-07-31** (VM sur `f19eb32`, aucune migration). Vérifié par curl sur `inhibitory-control-…?depth=3` : sur 306 nœuds source, 263 portent `doi` et `publisher`, 262 `journal`, 302 `published_at`, 303 `authors`.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) : la correspondance est couverte par les tests unitaires, mais le rendu de la barre elle-même n'a pas été vu.

**#226** — `feat/graph-panel-and-bidirectional-links`. Session 2026-07-31 (autonome) — **le graphe se lit dans les deux sens** :
- **Une source de fiche voisine ouvre l'encadré, pas un onglet.** Cliquer sur un nœud issu d'une fiche dépliée déclenchait un `window.open`. Le méta-graphe ne renvoyant pas `published_at` sur ses nœuds source, le champ est ajouté au nœud backend plutôt que fabriqué côté client, sinon l'encadré serait apparu amputé de « Publié le … ». Les champs réellement absents (extraits, archive, annotation) sont déjà facultatifs dans `SourceDetailPanel`.
- **Les arêtes fiche → fiche viennent du backend.** Le frontend les déduisait des seules sources affichées : construction structurellement incapable de montrer le sens entrant, ou une chaîne A → B → C tant que B n'est pas dépliée. Toutes les fiches du voisinage sont désormais rendues en permanence, seules leurs *sources* restant masquées jusqu'au dépliage. Côté backend, le parcours des citations entrantes — jusqu'ici réservé à la constellation — est activé pour les deux vues. Le repli en cascade de `collapseCard` devient obsolète : replier une fiche ne rend plus aucune autre inatteignable.
- ⚠️ `test_source_graph_stays_outgoing_only` verrouillait l'ancien comportement ; remplacé par `test_source_graph_surfaces_incoming_citations_too`, qui revérifie au passage qu'une fiche **privée** citant la racine ne transparaît toujours pas.
- **Mergée et déployée le 2026-07-31** (VM sur `03dcd56`, aucune migration). Vérifié par curl : depuis `clarifying-…`, `examining-…` **et** `inhibitory-control-…` — les trois maillons de la chaîne — la réponse est identique (3 nœuds fiche, 2 arêtes `is_card`, 0 arête partant d'un nœud source), donc le voisinage complet est restitué quel que soit le bout par lequel on entre. 302 des 306 nœuds source portent `published_at` (les 4 restants n'en ont pas en base).
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) ; forme du graphe validée par CI Linux + curl prod.

**#225** — `feat/graph-real-authors-direct-card-links`. Session 2026-07-31 (autonome) — **lisibilité du méta-graphe** :
- **Auteurs réels sur les nœuds fiche.** Une fiche ne porte aucun champ auteur : la seule source agnostique est `Source.authors` sur la source qui la désigne (`linked_card_id`) dans la bibliographie de qui la cite. Le backend la remonte sur les nœuds `card` et expose `is_seed`. Règle d'étiquetage partagée par les deux vues (`$lib/utils/card-label.ts`) : auteurs réels quand la fiche n'est pas revendiquée, créateur sinon. Étiqueter « Mathias » une fiche seed laissait croire qu'il était l'auteur du contenu.
- **Plus de nœud source intercalé entre deux fiches.** Une source qui désigne une fiche **est** cette fiche ; la rendre en plus comme nœud affichait deux fois le même contenu en chaîne. Arête `card → card` directe, affordance de dépliage déplacée sur la fiche cible. ⚠️ **Le fix devait porter des deux côtés** : `SourceGraph.svelte` construit les sources de la fiche racine depuis `card.sources` (payload CardDetail), pas depuis l'endpoint graphe — un correctif backend seul aurait laissé la redondance visible sur la fiche racine.
- **Mergée et déployée le 2026-07-31** (VM sur `64cc2d9`, aucune migration). Vérifié par curl sur `/@mathias-pinault/clarifying-…/graph?depth=3` : le nœud fiche liée porte `authors="Kang W., Hernández S., …"` et `is_seed=true`, 1 arête `is_card` directe, **0 arête partant d'un nœud source**.
- Limite connue : la fiche racine n'a pas d'auteurs réels tant que personne ne la cite (rien ne les porte). Repli sur le créateur, comme prévu.
- Vérification visuelle navigateur **non faite** (extension Chrome déconnectée) ; forme du graphe validée sur fixture SQLite ad hoc + CI Linux + curl prod.

**#224** — `fix/constellation-stale-simulation`. Session 2026-07-30 (autonome) — **méta-graphe rendu réellement utilisable** :
- **PRs #222/#223 mergées, #224 en cours.** Le picker « fiche liée » écrivait une colonne que rien ne lisait : aucune méta-fiche n'était possible malgré des liens bien saisis (cf. §Méta-fiches ci-dessous). Fusion dans `linked_card_id` (migration `016`), libellés du picker clarifiés, et deux vues sur le méta-graphe — nœud dépliable dans le graphe Sources, et **constellation** (fiches seules).
- **Chaîne vérifiée en prod** : picker → `linked_card_id` → `/cards/{id}/graph` renvoie bien l'arête `is_card` et le nœud cerclé se déplie.
- **Leçon de cadrage d3** (PR #224) : un recadrage déclenché par un `setTimeout` ou par un seuil d'alpha se calcule sur des positions que la simulation déplace encore — la boîte englobante vaut alors les positions phyllotaxiques initiales de d3, d'où un `scale(2.5)` que les nœuds quittent aussitôt (canevas noir). **Recadrer à chaque tick** tant que l'utilisateur n'a pas pris la main, et lui donner un bouton « Recentrer » pour revenir. Les ticks d3 sont pilotés par `requestAnimationFrame` : ils ne tournent pas dans un onglet non rendu, donc tout cadrage adossé à une horloge `setTimeout` dérive.

Session 2026-07-30 (autonome) — **refonte du pipeline d'extraction v2, agnostique** :
- **PRs #191-#199 et #210 mergées.** Le pipeline est passé d'un empilement d'heuristiques à 7 étages explicites (cf. ADR-030) : oracle spécialisé par domaine (Wikipedia via API MediaWiki, **YouTube via `ytInitialPlayerResponse.videoDetails.shortDescription`**) → autoritatif Crossref si DOI → enrichissement (S2 + BS4 + LLM) → validation par section-detection (`app/extractors/section_detector.py`) → dédup multi-clé (`ref_dedup.py`) → scoring syntaxique (`ref_scorer.py`) → classification.
- **Vérité terrain établie sur Frontiers `10.3389/fpsyg.2022.651547`** : le site affiche 152 refs, Crossref en dépose 152, S2 en renvoie 160 (8 hallucinations ML). Philum rendait 156, puis 154, puis 153 ; **rend maintenant exactement 152**. Fixtures figées dans `tests/fixtures/frontiers_651547*` (HTML 1,6 Mo + JSON Crossref + JSON S2), test d'intégration en assertion stricte `== 152`.
- **Dédup asymétrique par couche** (PR #210, la clé du 153→152) : `same_ref` reste strict pour la dédup générale (deux éditions d'un même travail sont des références distinctes) ; mais `matches_authoritative_work`, utilisé **uniquement** en pré-filtre S2-vs-Crossref, accepte un titre long identique (≥40 car. normalisés) sans comparer les auteurs. Raison : ce n'est pas une dédup de set mais un test d'appartenance à un ensemble déjà complet, et les sources dégradent les chaînes d'auteurs de façons incompatibles (`J. Ridley` chez S2 contre `Stroop` chez Crossref, pour le même Stroop 1935). ⚠️ **Ne pas « harmoniser » ces deux fonctions** : l'asymétrie est le correctif.
- **Backfill par visite d'URL** (`_backfill_url_metadata`) : dernier filet pour les corpus non-académiques (description YouTube, blog, rapport) où ni Crossref ni le LLM bibliographique ne peuvent produire un titre. Branché sur `/import/paste` **et** `/import/from-content-url`. Le chemin paste reçoit désormais la même chaîne complète que le chemin URL (blocs + LLM par bloc + Crossref + visite d'URL).
- **Canal transcript YouTube** (PR #212) : `yt-dlp` récupère la piste de sous-titres (json3, sous-titres rédigés prioritaires sur l'ASR), le texte est découpé en morceaux de 30 k caractères puis passé au LLM. Les travaux nommés à l'oral arrivent comme **suggestions à cocher**, jamais fusionnées dans la liste de références : l'ASR massacre les noms propres. Endpoint dédié `POST /import/youtube-transcript`.
- **Méta-fiches** (PR #214, puis #222) : `parent_card_id` a été **fusionné dans `linked_card_id`** (migration `016`). La distinction n'avait aucun consommateur — le picker écrivait `parent_card_id`, que rien ne lisait, tandis que le méta-graphe et la constellation lisaient `linked_card_id`, que seule une URL Philum collée pouvait remplir : d'où 0 méta-fiche possible en prod. Un seul concept désormais, « cette source désigne cette fiche », alimenté soit par le picker soit par l'URL. `GET /cards/search` sert le picker (fiches de l'user, brouillons compris, + toutes les fiches publiées et publiques) et `assert_linked_card_allowed` revalide ce périmètre à l'écriture, sinon un id deviné permettrait de confirmer l'existence d'une fiche privée d'autrui. ⚠️ `SourceUpdate` **doit** déclarer `linked_card_id` : sans lui toute édition d'un autre champ effaçait le lien (cf. `test_link_survives_an_unrelated_edit`).
- Avant : garde-fou de cohérence de titre contre les DOIs erronés déposés par l'éditeur (cas Aron 2003 → DOI d'un papier sur les abeilles chez Oikos) ; auteurs canoniques forcés depuis Crossref ; refs sans URL autorisées (`url=""` pour livres/chapitres) ; alertes Dependabot traitées (#191).

Session 2026-07-22 :
- **PRs #185-#190 mergées** : quick-wins UI ; stepper cliquable + édition des infos d'une fiche existante (`/dashboard/new?card_id=`) ; indicateurs majoritaires sur fiche publiée (% auteur/catégorie réels, plus de compteurs fixes) ; **sources exhaustives** (résolution PII ScienceDirect → DOI + fallback Crossref `works/{doi}.reference` quand S2 élide — ScienceDirect 0→136 refs, Frontiers 160) ; **fiche parente v1** (migration `013 sources.linked_card_id`, détection serveur des URLs `/@user/slug` du frontend, badge « Fiche Philum · N sources » + bouton « Explorer la fiche », affordance lien parent par ligne dans le wizard) ; **métadonnées bibliographiques étendues** (migration `014` : journal/volume/pages/publisher/doi, autofill Crossref, date de publication dans le wizard, zone repliable pour les extras, exports **CSL-JSON Zotero** + **APA** + BibTeX enrichi).
- **VM GCP redéployée** après #186, #188, #189 et #190 (migrations 013 et 014 appliquées), health vérifié par curl.

Session 2026-07-21 :
- **PRs #179-#181 mergées** : retry Crossref 2ᵉ passe + backoff S2 429 (100 % métadonnées récupérées, 100 % gratuit) ; parcours « Nouvelle fiche » unifié (suppression `/dashboard/from-url`, extraction depuis la page sources, drop de fichier via store) ; **extraction fichiers DOCX/HTML + refs structurées PDF via GROBID** (Space HF `zfhxi/grobid`, fallback regex gracieux, ADR-023, support arXiv/CoRR).

Sessions précédentes (2026-07-19/20) :
- PRs #135-#144 mergées (imports, citations IA, session 7j, export docx, métadonnées PII, deps sécurité, durcissement MCP, extension MV3, page /developers, docs) — 2026-07-19
- **PRs #147-#154 mergées** (rate-limit MCP 60/min, fix hero moon-line-depth v1/v2/v3, fix dédup DOI/URL, endpoint `POST /import/from-content-url`, UI `/dashboard/from-url` avec preview + progression + fetch_status) — 2026-07-20
- **9 PRs Dependabot #153-#163 mergées** (vitest 4, svelte-check 4.7, svelte 5.56, sveltekit 2.70, eslint-plugin-svelte 3, svelte-eslint-parser 1.8, prettier 3.9, @types/node 26, autoprefixer 10.5) — 2026-07-20
- **PR #156 fermée** (tailwind v4 breaking, migration dédiée nécessaire)

Backend 197/197 tests, frontend check/build/lint OK.

> Mergées avant : #121-#134 (exports, imports, citations IA, graph colors, etc.), #116-#120 (infra GCP + LLM extract), #112-#115 (waitlist, seed & claim, MCP, adoption).

> _Quand cette section est vide, plus rien n'est en attente côté review humaine._

---

## URLs production

- **Frontend** : https://filum-eight.vercel.app
- **Backend** : https://philum-api.duckdns.org (GCP e2-micro + Caddy, cf. ADR-028)
- **API docs** : https://philum-api.duckdns.org/api/v1/docs
- **Fiche démo** : https://filum-eight.vercel.app/@example/memoire-et-cerveau
- **Ancien backend Railway** : https://filum-production-07bb.up.railway.app — décommissionnable

---

## Stack effective

**Backend** : Python 3.12 · FastAPI async · SQLAlchemy 2.x async · Alembic · PostgreSQL (Supabase, Session pooler 5432) · Crypto Ed25519 + AES-GCM + HS256 (PyJWT) · Pillow (OG images) · slowapi (rate limit) · pytest (~70 tests) · Hébergé sur GCP e2-micro (Docker Compose + Caddy TLS).

**Frontend** : SvelteKit 2 · Svelte 5 (runes) · TypeScript · Tailwind · D3 v7 (graphe) · OGL (WebGL hero, lazy) · Vercel · pnpm 10 pinné · Logo Philum v1 (Pulsar-graph CB12 + Z13 palette).

**Analytics** : dbt-core sur DuckDB (job `dbt compile` en CI).

**Architecture OAuth** : Frontend → proxy SvelteKit `/api/[...path]` → Backend (cookies first-party). Backend lit `X-Filum-Public-Origin` (set par proxy) pour construire `redirect_uri` (cf. ADR-025).

---

## CI (workflows GitHub Actions)

3 workflows : `ci.yml`, `analytics.yml`, `security.yml`. Jobs (~16 total) : Lint/Test/Type-Check Backend + Frontend, Build Frontend, Analytics (dbt compile), Security Scan (Trivy), Static Analysis (Bandit), Vulnerability Check (Safety), Secrets Detection (TruffleHog), Dependency Review, CI Summary, Vercel preview.

Toutes les actions bumpées en juin 2026 (`pnpm v6`, `setup-python v6`, `checkout v6`).

---

## Variables d'environnement (production GCP)

Fichier `~/filum/infra/oracle/.env` sur la VM (modèle : `infra/oracle/.env.example`) :

```
database_url           = postgresql://postgres.<ref>:<pwd>@aws-0-us-east-1.pooler.supabase.com:5432/postgres
session_secret         = <openssl rand -hex 32>
master_encryption_key  = <openssl rand -hex 32>
frontend_base_url      = https://filum-eight.vercel.app
backend_base_url       = https://philum-api.duckdns.org
google_redirect_uri    = https://philum-api.duckdns.org/api/v1/auth/google/callback
cors_origins           = ["https://filum-eight.vercel.app"]
google_client_id       = <Google OAuth Client ID>
google_client_secret   = <Google OAuth Client secret>
API_DOMAIN             = philum-api.duckdns.org   # utilisée par Caddy (TLS)
```

⚠️ **Toutes en lowercase** (ADR-010 — pydantic-settings `case_sensitive=True`), sauf `API_DOMAIN` (consommée par Caddy, pas par pydantic). ⚠️ Supabase : **Session pooler port 5432**, jamais le Transaction pooler 6543 (casse asyncpg).

Vercel : `BACKEND_URL=https://philum-api.duckdns.org` (env var serverless, jamais exposée navigateur).

---

## Bugs latents (non bloquants)

| Bug | Sévérité | Localisation |
|---|---|---|
| ~~`impact_factor` toujours `null`~~ | ✅ **#317** | Le défaut n'était pas celui-là. Mesure du 2026-08-07 : `impact_factor`, `subscribers_count` et `views_count` n'étaient écrits par **aucun** code de production — seul `seed_demo.py`, en dur. La fiche vitrine affichait donc `Impact factor 49.8` comme une donnée mesurée, sur une fiche qui promet la traçabilité. Retirés de l'affichage et du seed ; `citations_count` reste, Crossref le donne réellement. Colonnes laissées en base : les supprimer demande une migration destructive et casserait `generated.ts`. |
| ~~Test composant Svelte 5 incompat~~ | ✅ **#321** | Vérifié le 2026-08-07 : **il n'y avait plus aucun test de composant à réécrire** — `src/tests/` ne contenait que des fonctions pures et `@testing-library/svelte` était installé sans jamais être appelé ; l'absence se lisait comme une incompatibilité. La vraie cause, trouvée en écrivant le premier test, n'est pas dans testing-library : Vite résolvait la condition d'export `server` de Svelte 5, donc `mount()` levait `lifecycle_function_unavailable` et **aucun** composant n'était montable. Corrigé par `resolve.conditions: ['browser']` — une ligne. 3 tests sur `SourceDetailPanel`, dont un garde-fou sur #317. |
| ~~Le scan de secrets ne scannait rien~~ | ✅ **#324** | Trouvé le 2026-08-07 en enquêtant sur un échec de CI. Le job `Secrets Detection (TruffleHog)` de `security.yml` lançait `trufflehog … scan`, **qui n'est pas une sous-commande** : l'outil sortait sur `expected command but got "scan"`, et `\|\| true` joint à `continue-on-error` masquait l'erreur. Le job affichait **« pass » sans rien analyser**. Un scan de secrets qui ne scanne pas est pire qu'aucun scan : il donne l'assurance sans le contrôle. Corrigé en `filesystem`. Le job bloquant de `ci.yml`, lui, scannait bien — c'est lui qui a levé l'alerte. |
| ~~`Static Analysis (Bandit)` n'analysait aucun fichier~~ | ✅ **#325** | Troisième job de sécurité fantôme, même journée. Le chemin était `apps/backend/app/` **avec** `working-directory: apps/backend`, soit `apps/backend/apps/backend/app/` — inexistant. Bandit sortait en 0 après avoir analysé **0 fichier**, et le job affichait « pass ». Chemin corrigé : 77 fichiers, **6 alertes** restées invisibles. Traitées une par une : `ET.fromstring` sur le XML de GROBID passe à **`defusedxml`** (ce XML dérive d'un PDF fourni par l'utilisateur, et la stdlib expanse les entités internes — quelques kilo-octets suffisent à épuiser la mémoire du conteneur) ; un `assert` dans `card_connections.py` devient un vrai contrôle (sous `python -O` il disparaît, et la ligne suivante rendait un 500 muet là où la fiche désignée a simplement été supprimée) ; les 4 autres sont des faux positifs marqués `# nosec` **avec leur raison** (une URL publique prise pour un mot de passe, `saxutils.escape` qui échappe sans parser, un `continue` qui *est* la conduite voulue). Bandit est désormais à **0 sur 77 fichiers**, donc réellement bloquant. ⚠️ **Nouvelle dépendance** : `defusedxml>=0.7.1`, sans dépendance transitive. |
| ~~`Vulnerability Check (Safety)` n'analysait rien~~ | ✅ **#324** | Même défaut de classe, trouvé dans le log du job voisin le 2026-08-07 : `--output` attend un **format** (`screen`/`text`/`json`/`html`), pas un chemin. Les deux appels sortaient sur `Invalid value for '--output'`, le `\|\| true` final absorbait l'échec, et le job affichait « pass ». Le chemin de sortie, c'est `--save-json` — vérifié en local : 73 Ko de JSON valide, 0 vulnérabilité. **Leçon commune aux trois lignes ci-dessus** : un `\|\| true` en fin de chaîne masque aussi bien une commande invalide qu'un résultat négatif. Vérifier qu'un job de sécurité **produit** quelque chose, pas seulement qu'il est vert. |
| ~~Le détecteur Lob bloquait la CI sur des noms de tests~~ | ✅ **#324** | Une clé de test Lob s'écrit `test_` + 35 caractères — soit **n'importe quel nom de fonction de test un peu long**, et TruffleHog la déclare « vérifiée » puisque l'API Lob accepte toute clé de test. Un nom de test a bloqué la CI de #323. Mesuré sur le dépôt entier : des dizaines de correspondances, **toutes** des noms de tests (jusque dans `greenlet`, `joblib`, `jsonschema`). `--exclude-detectors=Lob` sur les deux jobs : Philum n'utilise pas Lob, rien de réel n'est perdu, et le scan cesse de punir des noms de tests explicites. |
| ~~Wayback queue durability~~ | ❌ **prémisse fausse, 2026-08-07** | La ligne attribuait les sources en attente à une file `asyncio` perdue au restart et réclamait un worker Postgres. **Mesuré : la file est déjà durable.** L'état vit dans Postgres (`archive_status='pending'`) et chaque affichage de fiche relance les non-archivées (`cards.py:441`) — un restart ne perd rien de définitif. Sur les 931 sources publiées, **493 en attente**, mais un échantillon de 60 d'entre elles n'avait **aucune** capture dans l'index : rien n'a été perdu ni manqué. La cause est ailleurs, et c'est la ligne suivante. Un worker durable n'aurait rien changé. |
| Pas de domaine custom | Feature | Brancher `philum.app` quand 1er ambassadeur prêt. |
| ~~Liste d'attente email retirée de l'UI, back-end encore là~~ | ✅ **#322** | La note posait une condition avant toute suppression : vérifier qu'aucune adresse n'avait été collectée, sous peine de perdre des contacts réels. **Vérifié sur la base de production le 2026-08-07 : 0 ligne.** Rien à exporter. `WaitlistForm.svelte` et son export, le client, l'endpoint, le modèle, le schéma et le test d'intégration sont supprimés ; migration `031_drop_waitlist` (réversible : le `downgrade` recrée la table). |
| ~~La clé archive.org n'était envoyée nulle part où la limite mord~~ | ✅ **#326** | La ligne ci-dessous concluait « pas un correctif de code ». **Faux, vérifié le 2026-08-07** : `wayback_api_key` n'était transmise qu'au **sondage**, en paramètre d'URL — ce qui n'est pas un mécanisme d'authentification d'archive.org. Le déclenchement, le seul appel réellement limité, restait anonyme : ouvrir un compte n'aurait rien changé. Deuxième défaut, indépendant de la clé : le plancher de cadence était de 6 s, soit **10 captures/minute**, alors que Save Page Now en annonce **3 en anonyme et 6 avec un compte**. Demander plus vite que la limite ne rend rien plus rapide — cela transforme chaque demande en `429`, mesuré le jour même sur toute URL, `example.com` comprise. Corrigé : en-tête `Authorization: LOW access:secret` sur le déclenchement **et** le sondage (jamais en paramètre d'URL — un secret ne doit pas finir dans les journaux du destinataire), planchers portés à 20 s / 10 s. ⚠️ **Non vérifiable ici** : sans compte archive.org, les tests établissent que la requête est *formée* comme la documentation le demande, pas que le quota se lève. |
| Ouvrir un compte archive.org et renseigner `wayback_api_key` | **Action humaine** | Clés S3 sur `archive.org/account/s3.php`, format `access:secret`. Depuis #326 le code sait s'en servir — c'est la seule pièce manquante pour passer de 3 à 6 captures/minute. Sans elle la convergence reste lente mais correcte : les 493 sources en attente se résorbent au rythme anonyme, 20 s par capture. |
| Quota anonyme de Save Page Now | Faible | Mesuré le 2026-08-04 : archive.org répond `520` « already captured 5 times today » sur une URL déjà demandée. `wayback_api_key` existe dans la config mais est **vide en prod** (vérifié sur la VM) et n'est de toute façon jamais transmis à la demande de capture. Une clé S3 authentifiée relèverait le quota — elle exige un compte archive.org, donc une action humaine, pas un correctif de code. Sans elle, la convergence est simplement plus lente : depuis #272 le budget n'est plus brûlé sur une URL. **Vérifié en prod le 2026-08-04 après #274** : la fiche `inhibitory-control-…` est passée de 23 à 44 sources archivées sur 152, et les 44 portent toutes une vraie URL `web.archive.org` — aucune source « archivée » sans capture, aucune capture sans le statut. |
| ~~Taxonomie « Plateforme » sans case pour une revue~~ | ✅ **#320** | Le backlog annonçait « demande une migration côté backend, donc une décision » — **vérifié le 2026-08-07, c'était faux** : `platform` est stocké en `String(50)` (`models/biblio_card.py:89`), pas en enum Postgres. Aucun DDL. Valeur `revue-scientifique` ajoutée, et `guessPlatform` sorti du composant vers `lib/utils/platform-guess.ts` où il devient testable (il ne l'était pas) : liste explicite de 22 hôtes d'éditeurs, pas un motif — « revue » n'a pas de marqueur dans un nom de domaine. |
| 131 brouillons dépliés d'un coup | Faible | Constaté le 2026-08-04 : une extraction de 131 réfs rend 131 formulaires, métadonnées étendues ouvertes dès que Crossref a répondu. `#276` a remonté « Tout ajouter » en tête de liste, mais la page reste très lourde. Replier par défaut cacherait ce qui a été extrait — arbitrage à trancher, pas à improviser. |
| ~~Paramètre de suivi ajouté par un redirecteur~~ | ✅ **#318** | Le critère demandé est une **liste explicite** (`via`, `fbclid`, `gclid`, `msclkid`, `igshid`, `mc_*`, `ref_src`, `_hs*`, préfixe `utm_`), pas une heuristique : `strip_tracking_params` ne retire que des noms connus pour ne jamais désigner la ressource, et un test verrouille le contre-exemple `article.aspx?doi=…`. L'ordre et l'encodage bruts des paramètres restants sont préservés — réordonner ou ré-encoder changerait la clé CDX. Branché sur l'archivage **et** sur le lookup, sinon on archiverait une adresse que la recherche ne retrouve pas. Vérifié le 2026-08-07 : la capture de `…/pii/S0896627301005839` date de 2019-10-16. |

---

## Prochaines étapes (par ordre d'impact/coût)

> **Roadmap consolidée et priorisée** : [`.docs/21-roadmap-2026-07.md`](./.docs/21-roadmap-2026-07.md). Plan d'audit détaillé : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md). Comptes plateformes liés : [`.docs/18-linked-accounts.md`](./.docs/18-linked-accounts.md).

**Immédiat**
- ~~**Moteur d'agent BYOK + orchestrateur de fiche**~~ ✅ **fait le 2026-08-21** (PRs #499, #500, #508 + plan 8 taches). Le createur branche sa propre cle, l'agent construit une fiche en 7 etapes streamees. Quatre corrections d'interface : message exact du fournisseur, selecteur de modele vivant, edition de cle sans suppression, page `/developers` avec URL MCP en clair. Schemas MCP compatibles Gemini (0 `anyOf` dans les 39 outils d'entree). Cinq fournisseurs a cle gratuite sans carte (Mistral, Groq, OpenRouter, Cerebras, Google AI Studio).
- ✅ **Dates manquantes et voie « sans date » en chronologie** (signalé le 2026-08-04) — **les deux défauts sont traités**, vérifié le 2026-08-07.
  1. ~~**L'identification de la date échoue là où la donnée existe.**~~ ✅ **#312**. Cause trouvée et mesurée comme générale : `_parse_crossref_work` ne lisait que `published-print` et `published-online`, et un enregistrement `posted-content` ne porte **ni l'un ni l'autre** — sa date vit dans `issued`. Vérifié sur OSF, bioRxiv et medRxiv comme la note le demandait. `issued` ajouté en **dernier** repli : présent sur tous les types (donc pas de branche par hébergeur ni de test sur `type`), et placé en dernier pour que la parution papier continue de faire foi — `nrn3667` reste à `2014-03-01`, aucun enregistrement déjà daté ne bouge. Cas témoin `10.31234/osf.io/x4yj3` : `null` → `2021-09-09`.
     - ~~⚠️ Mesuré au passage, hors périmètre : `_extract_doi` *et* `resolve_doi_from_url` rendent `None` sur `osf.io/preprints/…` **et** `arxiv.org/abs/…`.~~ ✅ **#323** — et **la note tirait la mauvaise conclusion des deux côtés**, vérifié le 2026-08-07 :
       - **arXiv n'a aucun défaut.** L'absence de DOI ne coûte rien : `extract()` rend déjà titre, date et auteurs complets par les balises Highwire (`1706.03762` → « Attention Is All You Need », `2017-06-12`, 8 auteurs). Et le DOI qu'on serait allé chercher ne servirait à rien : arXiv dépose chez DataCite (`10.48550/arXiv.…`), que **Crossref n'indexe pas** — `crossref_lookup` y répond `None`. Un oracle arXiv n'ajouterait donc rien à ce chemin.
       - **OSF avait un défaut bien pire que « DOI absent ».** La page est une application JavaScript : le scraping rendait `title='OSF'`, le titre de l'application, avec date et auteurs vides. **Un titre faux est pire qu'un titre absent** — il se recopie dans la fiche sans que rien ne signale qu'il ne désigne pas le document. Corrigé par l'API publique OSF, qui rend le dossier complet en une requête (`?embed=contributors`) : un seul hôte, donc **pas** la table de préfixes DOI par fournisseur (psyarxiv `10.31234`, socarxiv `10.31235`…) que le projet refuse. Quand le preprint est paru en revue, OSF donne le DOI de **la version parue** — c'est la version de référence, et Crossref prend alors le relais, mais seulement s'il nomme le document, sinon il remplacerait un dossier complet par une coquille vide. Cas témoin `x4yj3` : `'OSF'` / `null` → titre réel / `2024-10-01` / 5 auteurs.
  2. ~~**La voie « sans date » se lit comme une date.**~~ ✅ **déjà livré, la note était périmée**. `graph-chrono.ts` porte `breakX` — un **filet de rupture** explicite, convention usuelle pour « l'échelle s'interrompt ici » — et la colonne est passée **à droite** de la frise : à gauche elle occupait la place que l'œil lit comme « le plus ancien ». Rendu vérifié dans `SourceGraph.svelte:1140`, 16 tests dans `graph-chrono.test.ts`. Le principe est tenu : un simple décalage n'aurait pas suffi, une position sur un axe temporel *signifie* une date quel que soit l'écart.
- ~~Redéployer la VM GCP~~ ✅ fait le 2026-07-21 (464ba95, vérifié par curl).
- ~~3 alertes Dependabot high sur main~~ ✅ fermées le 2026-07-22 (PR #191 : overrides pnpm brace-expansion 1.x/5.x + js-yaml 4.x).
- ~~Alerte Dependabot high postcss (traversée de chemin)~~ ✅ fermée le 2026-08-03 (PR #251). **Zéro alerte ouverte**, et les 15 PRs Dependabot en attente ont été traitées ou closes (#251→#256).
- ~~**Brancher un LLM en prod**~~ ✅ **fait le 2026-08-10** (PRs #353 et #354). La cle Gemini a ete fournie par le proprietaire du projet, et deux defauts de code se cachaient derriere le blocage apparent : le `/v1` ajoute d'office a la racine configuree (#353), et une sonde qui disait « echec » sans jamais dire le motif (#354). Verifie a l'ecran en prod sur une source reelle : « Suggerer des citations » rend des passages retrouves mot pour mot dans la page. Constat conserve pour memoire, la voie tracee le 2026-08-08 : Mesure sur l'API reelle : `llm_enabled: false`, **aucun** appel LLM ne fonctionne, les sept points d'appel passent tous par `litellm_base_url` qui est vide. Trois fonctionnalites sont inertes depuis leur livraison. **Cloud Run ne reglerait pas le blocage** : LiteLLM est un proxy, il ne contient aucun modele, et il lui faut toujours une cle provider en amont. La solution retenue est de **ne pas monter LiteLLM du tout** — le backend parle deja OpenAI (`/v1/chat/completions` + `Bearer`), et Gemini expose cette forme nativement a `https://generativelanguage.googleapis.com/v1beta/openai`. Deux variables d'environnement, zero conteneur, zero RAM. Reste a faire cote code : une table alias de tache → nom de modele reel dans `llm.py` (les appels nomment `biblio-parse`, `excerpt-suggest`, `metadata-extract`). *Bloque sur une cle Gemini — elle se cree sur AI Studio avec le compte Google existant, aucun compte nouveau, mais saisir des identifiants est hors de portee d'un agent.*
- ~~**Un extrait s'affichait toujours seul**~~ ✅ #355 puis #356. Signale le 2026-08-10 : l'intitule et la mise en situation etaient saisis, stockes, exportes et servis par le MCP — et **jamais relus a l'ecran**. Une annotation qu'on ne relit pas est une annotation qu'on ne corrige pas. Le defaut portait sur **trois surfaces de rendu, pas une** : l'espace d'edition et le panneau lateral (#355), puis la liste de la fiche publique (#356) — celle qu'on lit *sans cliquer*, donc la seule que l'utilisateur avait sous les yeux. Corriger les deux premieres n'avait rien change a l'ecran, et c'est la verification au navigateur qui l'a montre. Point de doctrine tenu par les tests des deux cotes : **la mise en situation se rend hors des guillemets et sans italique**, dans un element distinct du verbatim — l'y fondre attribuerait a l'auteur·ice citee des mots qu'iel n'a pas ecrits. Le ✨ signale quand l'annotation vient d'un modele.
- **Les pages en JavaScript restent illisibles pour la relecture d'extraits.** Mesure le 2026-08-10 en prod sur une source `nature.com` : « Suggerer des citations » repond que la page ne laisse pas lire son texte, et cinq citations restent a « Source illisible ». **Ce n'est pas un bug** — c'est `unreadable` qui refuse de se faire passer pour `missing`, exactement le comportement voulu. Mais cela veut dire qu'une part notable des sources scientifiques ne sera pas relisible tant que le rendu JavaScript n'est pas fait ; le contournement existant est « Decouper un texte long ». Rejoint le chantier Playwright differe (Axe B).
- **Alerte budget 1 € sur GCP** (Billing → Budgets & alerts) si pas déjà en place — filet de sécurité, pas de plafond natif. *Action Cloud Console, hors de portée d'un agent.*
- **Décommissionner Railway** : supprimer le service + retirer l'ancienne redirect URI Railway du client OAuth Google. *Destructif et touche le client OAuth Google — demande une autorisation explicite, à ne pas faire en autonomie.*
- ~~**Migrer Tailwind v3 → v4**~~ ✅ #332. Le codemod officiel a fait le mécanique (14 fichiers, renommages seuls) ; le défaut est venu d'ailleurs. **Depuis la v4, `--color-*` n'est plus un nom libre : c'est l'espace de noms du thème.** Six alias hérités de la v3 (`--color-border: var(--border)`, etc.) déclarés dans `:root` écrasaient donc les variables générées par `@theme`, en rendant un triplet RGB nu — invalide comme couleur, si bien que `border-border` retombait sur `currentColor` et que les contours de carte prenaient le noir du texte. Ni le build, ni 147 tests verts, ni le diff des sélecteurs produits par les deux builds ne l'ont vu : **la classe existait toujours, seule sa valeur avait changé.** Il a fallu lire `getComputedStyle` dans un navigateur. Leçon générale : contre une migration de thème, comparer des captures ou des sélecteurs ne suffit pas, il faut mesurer des valeurs calculées. Garde-fou posé : `src/tests/app-css-theme.test.ts` (vérifié rouge sur le défaut avant d'être vert).
- ~~**Le mode sombre s'arrêtait au bord du graphe**~~ ✅ #335. Mesuré au navigateur le 2026-08-08, thème sombre actif sur la fiche de démo. Deux défauts, une même cause : **une couleur figée en face d'un jeton de thème n'est pas un choix, c'est un oubli** — le jeton s'inverse, la constante non. (1) `.skip-link` déclarait `background: rgb(var(--text-primary)); color: white`, soit blanc sur `#F5F5F5` — **1,09:1**, et invisible par construction puisque le lien ne paraît qu'au focus clavier, alors que c'est la seule façon de sauter le menu. (2) Le graphe restait une dalle claire au milieu d'une page sombre : 92 classes `slate-*`/`bg-white` dans son châssis et onze `#ffffff` peints par D3. **Le premier correctif a rendu l'écran pire** — fond passé en sombre, libellés restés `#0f172a`, donc disparus ; c'est la capture de la preview qui l'a montré, pas les tests. Les nuances figées du SVG passent par `jeton()`, qui lit la valeur calculée : `var(--…)` n'est pas résolu dans un attribut de présentation SVG. Un `$effect` sur `$theme` redessine, sinon basculer le thème laisserait les anciens halos jusqu'au prochain remontage, c'est-à-dire jamais. Après : skip-link **15,91:1**, libellés du graphe de 6,72 à 19,26:1, mode clair inchangé. Garde-fou `src/tests/skip-link-contraste.test.ts` (vérifié rouge, `Received: "white"`). Ajouté au passage : `API_PROXY_TARGET` sur le proxy Vite, pour regarder l'interface locale sur les données de prod sans monter Postgres.
- ~~**Les panneaux de détail ignoraient le mode sombre**~~ ✅ #336. Le graphe corrigé, restait ce qui s'ouvre par-dessus : cliquer un nœud faisait surgir une carte blanche à texte `slate-*` au milieu d'une page sombre. 47 classes converties en jetons dans `SourceDetailPanel`, `CardDetailPanel`, `CategoryBadge`, `FormatBadge`. Deux choses volontairement **non** touchées, parce que la règle n'est pas « aucune couleur figée » mais « une couleur figée doit porter un rôle qui ne s'inverse pas » : les voiles `bg-slate-900/30` des modales (un voile assombrit dans les deux thèmes ; le passer à un jeton l'éclaircirait en sombre, soit l'inverse de ce qu'on lui demande — commentaire posé sur place), et `CardConstellation`, un ciel `bg-slate-950` sombre par intention et cohérent avec ses propres contrôles. Vérifié à l'écran dans les deux thèmes sur la preview, comme en #335 où seule la capture avait vu le premier correctif empirer l'écran.
- ~~**Le mode sombre s'arrêtait aux écrans d'édition**~~ ✅ #337, fin du chantier. Un balayage exhaustif des classes `slate-*`/`bg-white` et des hex gris ne laissait plus que deux écrans en défaut : `dashboard/new/[card_id]/connexions` (titres, listes, séparateurs, toast d'annulation) et `/@username` (les deux cartes en `bg-white` face à un `border-border` déjà tiré d'un jeton — le contour suivait le thème, pas la surface). Plus un nœud du graphe : sans type déclaré il était peint `#1e293b`, donc une tache sombre sur un fond sombre ; il emprunte désormais la couleur du texte. **Le tri compte autant que la conversion** — restent figés, à raison : l'encart d'alerte `amber-50` de la page connexions (clair dans les deux thèmes, y mettre des jetons y rendrait le texte clair sur clair), le hero et la section CTA de l'accueil, `CardConstellation`, le logo. Après ce lot, plus aucune couleur figée non intentionnelle dans le frontend.
- ~~**Les verdicts eux-mêmes étaient illisibles**~~ ✅ #338. Le balayage #337 n'avait grepé que les `.svelte`, et manquait donc `lib/utils/retraction.ts` et `open-access.ts` — c'est-à-dire précisément **les quatre classes qui portent ce que Philum affirme sur une source qu'il n'a pas écrite**. Deux régimes à distinguer : les **avis** (rétracté, mise en garde, corrigé ; libre, gratuit) portent un fond coloré clair et un texte foncé, paire close sur elle-même qui ne s'inverse pas — figée à raison. Les **non-avis** (aucun avis, non vérifiable, accès payant, non vérifié) sont du texte nu posé sur une surface qui bascule : ils devaient venir de jetons. Mais **le jeton n'était que la moitié du problème** : mesuré au navigateur, `ink-placeholder` donnait **2,17:1 en clair**, sous le plancher WCAG AA — et le défaut préexistait, `text-neutral-400` mesurait exactement pareil. Ma première conversion l'avait déplacé (2,17 → 2,43) sans le réparer. Un état qu'on ne peut pas lire n'est pas discret, il est absent : le lecteur conclut du vide. Les deux non-avis partagent désormais `ink-tertiary` (**4,61:1** clair, **5,56:1** sombre), et ce qui les distingue est le mot et l'italique, pas une nuance de gris. Garde-fou `src/tests/verdicts-jetons.test.ts`, étendu après coup pour rejeter `ink-placeholder` — car tel qu'écrit d'abord, il passait au vert sur le défaut à 2,43:1 : **venir d'un jeton garantit que la couleur suit le thème, pas qu'on la lise**.

**Chantiers outils-chercheurs** (étude `agent/research/2026-08-03-outils-chercheurs.md`, dans l'ordre)
- ~~1. Meta tags Highwire + COinS~~ ✅ #239 · ~~2. Champ `stance` déclaratif~~ ✅ #240 · ~~3. Badge rétractation~~ ✅ #241+#242 · ~~4. Bornage + chronologie~~ ✅ #243+#244 · ~~5. Enrichissement OpenAlex~~ ✅ #245 · ~~6. Pivot CSL-JSON + RIS~~ ✅ #246 · ~~7. Import de fichier~~ ✅ #247 · ~~8. Alertes « on vous cite »~~ ✅ #248 · ~~9. Colonnes de comparaison sans IA~~ ✅ #250.
- **Les 9 chantiers de l'étude sont livrés.** Restent en réserve, plus lourds : extension navigateur (§3.6), colonnes custom LLM sur abstracts (§2.2), chemin entre deux nœuds (§3.4), Zotero Web API OAuth 1.0a (§4.7).
- ~~**Ancrage d'extrait fuzzy (§3.5)**~~ ✅ #333. Un extrait ne portait que son texte : la source corrigeait une coquille et le passage devenait introuvable — donc lisible comme une citation inventée. Désormais on persiste le voisinage (48 caractères de part et d'autre) et la position, et `POST /sources/{id}/excerpts/verify` ré-ancre dans la page telle qu'elle est aujourd'hui. Deux points de doctrine, tenus par les tests : **un ancrage complaisant est pire que pas d'ancrage** (en dessous du seuil de ressemblance on ne rend rien, plutôt que de désigner un passage plausible mais faux), et **`unreadable` n'est pas `missing`** — une page qui ne rend aucun texte ne dit rien sur l'extrait ; les confondre ferait passer une source inaccessible pour une citation fabriquée. L'écran suit en #334 : « Relire la source » affiche un verdict par citation, et l'espace d'édition sort de la page de 2300 lignes en `ExcerptWorkspace.svelte` (deux entrées explicites — coller un passage, découper un texte long). Deux défauts n'ont été vus **qu'au navigateur** : les actions en variante `ghost` se lisaient comme du texte de navigation, et le bouton « Proposer un découpage » était au-dessus du champ de collage, si bien que l'écran demandait de régler la taille cible avant d'avoir de quoi découper. Ni les 158 tests ni `pnpm check` ne pouvaient les voir. Garde-fou : `/sandbox/citations` monte le composant seul, sans fiche ni session.
- ~~**DOAJ**~~ ✅ — réglé par #245 sans seconde intégration : `best_oa_location.source.is_in_doaj` d'OpenAlex donne le drapeau au passage.

**Court terme** (semaines)
- ~~**F1** — `openapi-typescript`~~ ✅ — dépendance et script `generate:api` en place dans `apps/frontend/package.json`.
- ~~**F4** — `POST /cards/{id}/restore`~~ ✅ — `cards.py:333`, vérifié en prod le 2026-08-03 (401 = route servie, auth requise).
- ~~**F2** — Tests d'intégration sur `POST /cards/{id}/publish`~~ ✅ — `tests/integration/test_publish.py` couvre le path qui a coûté 4 PRs en mai.
- ⚠️ Ces trois lignes traînaient comme « à faire » alors qu'elles étaient livrées. Vérifier l'état réel (grep + curl) **avant** de rouvrir un item de ce backlog.

**Moyen terme** (déclencheurs naturels)
- ~~**F5** — Queue Wayback durable (Postgres-backed + worker)~~ ❌ **prémisse fausse, mesurée le 2026-08-07** — la file *est* déjà durable : l'état vit en base et chaque affichage de fiche relance les non-archivées. Les 493 sources en attente ne venaient pas d'un travail perdu (0 capture existante sur 60 échantillonnées) mais du quota Save Page Now, traité en #326. Un worker n'aurait rien changé ; il ne redeviendra utile que si la reprise paresseuse elle-même sature, ce qu'aucune mesure ne montre.
- ~~**Phases 2-4 du rename Philum** — convertir en issues GitHub~~ ✅ le 2026-08-08 : issues **#345** (docs), **#346** (identifiants frontend + dbt), **#347** (cookies, headers, domaine, dépôt). Chacune porte son déclencheur naturel plutôt qu'une date, et les deux gestes hors autonomie d'agent y sont nommés : renommer le cookie déconnecte toutes les sessions ouvertes, renommer le dépôt touche les URI de redirection du client OAuth Google.
- **F3** — Tests Postgres au lieu de SQLite quand on ajoute un index partial / colonne JSONB.

**Long terme** (conditionnel à validation produit)
- **Axe A** — Stockage cloud R2 pour contenu original (décision dépend des interviews créateurs).
- **Axe B** — Archivage multi-cible (Wayback → Archive.today → Playwright + table `archive_attempts`).
- **F8** — Multi-tenancy si pivot B2B confirmé.
- Domaine custom `philum.app` + import Zotero/BibTeX/Obsidian + plugin navigateur (après 3-5 créateurs actifs).

---

## Décisions techniques majeures

Voir [`DECISIONS.md`](./DECISIONS.md) pour le détail. Les plus structurantes :

- **ADR-013** : pnpm 10 pinné
- **ADR-014** : `python-jose` → `PyJWT` (CVE)
- **ADR-019** : signature sur le triplet `(creator_id, content_url, attested_at)`, fiches mutables
- **ADR-020** : taxonomie sources 3 axes (`format` / `category` / `author_kind`)
- **ADR-024** : sandbox tunable → port prod
- **ADR-025** : proxy SvelteKit pour OAuth cross-origin
- **ADR-026** : topologie graphe (lune + Y-fork virtuel + perspective 3D)
- **ADR-028** : hébergement GCP e2-micro always-free + Supabase (post-Railway)

---

## Commandes utiles

```bash
# Backend local
cd apps/backend
uv sync --all-extras
uv run uvicorn app.main:app --reload
uv run pytest tests/ -v
uv run alembic upgrade head
uv run ruff check app/ && uv run ruff format app/ && uv run mypy app/ --ignore-missing-imports

# Frontend local
cd apps/frontend
pnpm install --frozen-lockfile
pnpm run dev
pnpm run check
pnpm run lint
pnpm run build

# CI
wsl gh run list --branch main --limit 5
wsl gh pr list
```

---

## Comment relancer une session

1. **Lire ce fichier** (snapshot court).
2. Pour le détail historique : [`CHANGELOG.md`](./CHANGELOG.md).
3. Pour les items en attente : [`.docs/13-audit-2026-05-26-followups.md`](./.docs/13-audit-2026-05-26-followups.md).
4. Pour les décisions techniques : [`DECISIONS.md`](./DECISIONS.md).
5. Pour l'agent IA autonome multi-sessions : [`agent/README.md`](./agent/README.md).
6. Vérifier l'état avec : `git log --oneline -10`, `wsl gh pr list`, `curl https://philum-api.duckdns.org/health`.
7. Choisir une tâche dans « Prochaines étapes » ci-dessus.
8. Branche `feat/<sujet>` (jamais sur main), PR vers `main`, squash-merge **après validation humaine** explicite.

---

## Mettre à jour ce fichier

Quand la session apporte un changement significatif (PR mergée, phase qui change, URL prod modifiée, nouvelle ADR), **éditer la section pertinente** et bumper la date en haut. Pour les détails de la session (commits, root causes, bugs résolus), **écrire dans `CHANGELOG.md`** — pas ici.
