# 07 — Questions ouvertes

> Décisions non tranchées à ce stade. Chacune doit être résolue à un moment, mais pas toutes en même temps. Tenir cette liste à jour permet de ne rien oublier.

---

## Q1 — Nom définitif du projet

**Statut** : non tranché.

**Options** : Filum (provisoire), Stemma, Colophon, Upstream, Tracé, Provenance.

**Décision à prendre avant** : lancement public (fin de phase 2).

**Démarche** : confronter le nom à 5-10 personnes du cercle cible, voir lequel résonne le mieux. Vérifier la disponibilité des domaines, des comptes sociaux, des marques.

---

## Q2 — Paliers exacts de la version gratuite

**Statut** : indicatif seulement.

**Indicatif actuel** : signature illimitée, sources illimitées par fiche, archivage par Wayback (gratuit), page publique gratuite.

**Question à arbitrer** : faut-il une limite sur le nombre de fiches par mois ? Sur la rétention des snapshots ? Sur la taille du graphe affiché ?

**À trancher en** : phase 2 après les premiers retours d'usage.

---

## Q3 — Modèle de partenariat avec Internet Archive

**Statut** : utilisation libre de l'API publique en MVP.

**À explorer** : partenariat formel pour augmenter les quotas, contribution financière, mention réciproque. Contact possible via leurs canaux officiels.

**À trancher en** : phase 3 si la volumétrie le justifie.

---

## Q4 — Gouvernance précise de la future fondation

**Statut** : forme juridique non décidée.

**Options** : Stichting néerlandaise (modèle Mozilla), Fondation reconnue d'utilité publique en France, association loi 1901 dans un premier temps.

**À trancher en** : phase 4, en amont de la création de la fondation. Consultation d'un avocat spécialisé recommandée.

---

## Q5 — Adhésion au consortium C2PA

**Statut** : pas adhéré.

**Question** : adhérer dès la phase 3 (~10k€/an) ou attendre une étape ultérieure ?

**Compromis** : utiliser le standard C2PA sans adhérer formellement permet déjà beaucoup. Adhérer apporte la reconnaissance des certificats par les outils mainstream et un siège dans les groupes de travail.

**À trancher en** : phase 3-4.

---

## Q6 — Stratégie de financement initial

**Statut** : autofinancement personnel + subventions publiques à viser.

**Options à activer** :
- NLnet (premier choix : rapide, non dilutif, ~50k€)
- NGI Trust/Sargasso (financement plus important, plus long)
- France 2030 Communs Numériques
- Love money / business angels (en complément)
- Pré-amorçage VC (à éviter pour préserver l'indépendance — sauf nécessité)

**À trancher en** : phase 2 (déposer un dossier NLnet dès qu'il y a un MVP démontrable).

---

## Q7 — Politique d'archivage et conformité juridique

**Statut** : niveau 2 (snapshots Wayback) en MVP, sans implication juridique pour Filum.

**Question** : quand on offrira l'option de stocker des fichiers source en propre (phase 3+), Filum devient hébergeur au sens LCEN/DSA. Procédures de retrait à formaliser, RGPD à appliquer.

**À trancher en** : avant le lancement du tier "archivage premium". Consultation juridique nécessaire.

---

## Q8 — Mode et endroit de stockage des clés privées

**Statut** : chiffrement Fernet avec clé maître en env var (MVP).

**Évolutions possibles** :
- Phase 2 : rotation périodique de la clé maître
- Phase 3 : HSM ou KMS (AWS KMS, Scaleway KMS)
- Phase 3 : option pour que le créateur stocke sa propre clé (modèle "self-custody")

**À trancher en** : phase 2.

---

## Q9 — Stratégie de modération des dérivés (cf. lineage descendant)

**Statut** : pas de lineage descendant en MVP.

**Question** : quand on activera le lineage descendant (un créateur déclare son contenu comme dérivé d'un autre), comment gérer les déclarations abusives ou malveillantes ?

**Pistes** :
- Par défaut, tout dérivé apparaît dans le graphe
- Dashboard pour le créateur source : voir, marquer "non reconnu", bloquer
- Procédure de signalement utilisateur

**À trancher en** : phase 3-4.

---

## Q10 — Intégration avec Anara

**Statut** : utilisation à clarifier.

**Question** : qu'apporte Anara précisément à Filum ? Référence à creuser dans la conception.

---

## Q11 — Vérification d'identité forte (Niveau 3)

**Statut** : non disponible en MVP.

**Question** : quel prestataire KYC pour les créateurs notoires en phase 2-3 ? Quels coûts ?

**Pistes** : Onfido, Persona, FranceConnect+ pour la France.

---

## Q12 — Mode sombre

**Statut** : pas en MVP.

**Question** : à quel moment l'introduire ? Demande utilisateur ?

**À trancher en** : phase 2 selon les retours.

---

## Q13 — Internationalisation

**Statut** : projet en français uniquement en MVP.

**Question** : quand passer en anglais ? Et autres langues européennes ?

**À trancher en** : phase 3-4 pour l'anglais. Plus tard pour les autres langues.

---

## Q14 — Stratégie de défense intellectuelle

**Statut** : non formalisée.

**Question** : protection de la marque "Filum" (INPI, EUIPO) ? Licences open-source précises pour chaque composant ? Stratégie en cas de fork ou de concurrent malveillant ?

**À trancher en** : phase 2-3 avec un conseil juridique.

---

## Q15 — Intégration MCP

**Statut** : prévu en phase 3.

**Question** : quel design exact pour le MCP server ? Quels endpoints exposer ?

**À explorer** : un MCP server qui expose les fiches Filum aux agents IA pour qu'ils puissent les interroger comme une source de vérité.

---

*Cette liste évolue avec le projet. Toute nouvelle question importante doit y être ajoutée.*
