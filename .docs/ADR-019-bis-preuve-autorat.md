# ADR-019-bis : preuve d'autorat, anti-usurpation et garantie d'authenticité

> Ce document est le pendant documentaire d'ADR-019 (signature du triplet
> `(creator_id, content_url, attested_at)`). Il répond aux questions que le code
> seul ne peut pas trancher : ce que Philum peut prouver, ce qu'il ne peut pas,
> et les formulations que l'interface a le droit d'utiliser.

---

## 1. Ce que Philum peut prouver — et ce qu'il ne peut pas

### Ce que la signature établit, et rien de plus

À la date T, le compte C, qui avait démontré son contrôle du canal K,
a déclaré être l'auteur du contenu situé à l'URL U.

Les trois éléments sont vérifiables indépendamment :

- la **date** par l'horodatage inclus dans le payload signé ;
- le **contrôle du canal** par la méthode de vérification enregistrée dans
  `LinkedAccount.verification_method` (`backlink`, `bio-code`, `oauth`) —
  voir `.docs/18-linked-accounts.md` pour le détail des méthodes ;
- la **déclaration** par la signature de l'attestation (clé publique `User.public_key`).

### Ce que Philum ne peut pas établir

- Que le contenu est authentique, non modifié, ou non généré par une IA.
- Que le déclarant est l'auteur intellectuel du contenu : Philum atteste qu'il
  contrôle le canal de diffusion, pas qu'il a créé le contenu.
- Qu'un contenu **non** attesté est faux : l'absence de revendication prouve
  seulement qu'aucune revendication n'a été faite sur Philum.

### Formulations autorisées et interdites dans l'interface

| Situation                             | Texte autorisé                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------------ |
| Attestation signée + canal vérifié    | « Déclaré par le titulaire du canal officiel le {date}. »                      |
| Attestation signée, canal non vérifié | « Déclaré par {compte} le {date}. Le canal de diffusion n'a pas été vérifié. » |
| Aucune attestation                    | « Aucune déclaration d'autorat sur Philum pour ce contenu. »                   |

**Formulations interdites, toujours :** « contenu certifié authentique »,
« garanti par Philum », « vérifié », « authentifié », « contenu suspect »
(pour l'absence d'attestation).

---

## 2. Le risque de revendication première

Un usurpateur qui revendique un contenu avant son auteur légitime obtiendrait
l'antériorité dans le registre. Trois protections, par ordre de force :

### 2a. La revendication n'est jamais suffisante seule

Elle ne prend valeur qu'adossée à une preuve de contrôle du canal de diffusion
(un `LinkedAccount` vérifié dont le domaine ou la chaîne correspond à l'URL du
contenu). Une revendication sans compte lié reste affichée comme
« déclarée, non adossée à un canal vérifié ».

Un générateur de faux ne contrôle pas le domaine du média ni sa chaîne
YouTube : il ne peut donc pas produire de `LinkedAccount` vérifié, et sa
revendication reste dans l'état non adossé.

### 2b. Le registre des revendications est public

Une usurpation visible est une usurpation contestable. La gratuité et la
publicité du registre sont une propriété de sécurité, pas une décision
commerciale. Ne jamais restreindre l'accès en lecture au registre, même
partiellement.

### 2c. Procédure de contestation (à implémenter)

États à prévoir dans le modèle de données futur, sans implémentation immédiate :

- `revendiquée` : état initial d'une attestation.
- `contestée` : un tiers dépose une contestation avec des preuves.
- `arbitrée` : un moderateur tranche (Philum, puis un jour un tiers de confiance).

Qui peut contester : tout compte Philum vérifié qui démontre contrôler le même
canal que la revendication contestée. Sur quelles preuves : une autre
`LinkedAccount` vérifiée pour le même domaine/canal. Délai d'arbitrage : à
définir, ≤ 30 jours comme point de départ.

---

## 3. Types de compte : individus et organisations

Question ouverte posée par le projet. Points à trancher lors de l'implémentation :

- Une colonne `account_kind` sur `users` (`individu` | `organisation`), nullable ;
  `NULL` = non déclaré.
- Une organisation peut avoir plusieurs personnes habilitées : cela suppose une
  table de liaison `organization_members(org_id, user_id, role)`, hors périmètre
  immédiat, mais à nommer pour que le schéma l'accueille sans rupture.
- La vérification d'une organisation passe par le contrôle du domaine
  (`rel=me` sur le site officiel), pas par une pièce d'identité. Philum ne doit
  **jamais** stocker de document d'identité : charge réglementaire
  disproportionnée, risque de fuite sans contrepartie.

---

## 4. Création de compte hors Google

Options, sans tranchement :

| Option                  | Avantage                              | Coût réel                                                                                               |
| ----------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| E-mail + mot de passe   | Universel                             | Hachage, rate limiting, réinitialisation, vérification d'adresse                                        |
| Lien magique par e-mail | Moins de surface, pas de mot de passe | Dépendance à la délivrabilité                                                                           |
| GitHub OAuth            | Familier développeurs                 | Dépendance à GitHub, moins pertinent hors tech                                                          |
| ORCID OAuth             | Identité vérifiée de chercheur        | Seul OAuth qui apporte une information d'identité exploitable pour la vérification d'autorat académique |

ORCID est le seul qui apporte une information d'identité vérifiée directement
utilisable pour authentifier un chercheur : l'identifiant ORCID est citable
dans une publication. Si Philum vise les chercheurs, ORCID devrait être
priorisé sur GitHub.

---

## 5. Philum face aux faux et à l'ingérence

### Ce qui ne fonctionne pas

Philum ne détecte pas les faux. Aucune analyse de contenu, aucune détection de
génération IA. Toute promesse en ce sens serait fausse et, si elle était
démentie une fois, endommagerait irrémédiablement la crédibilité du service.

### Ce qui fonctionne réellement : l'argument par l'absence

L'argument « ce contenu n'est pas sur Philum, donc il n'est pas attesté » ne
fonctionne que sous une condition stricte : si l'auteur du média atteste
**systématiquement** toutes ses publications, alors l'absence d'attestation
devient un signal fort.

Sans systématicité, l'absence ne prouve rien.

**Cette condition est le vrai produit.** Elle demande que l'attestation soit
assez peu coûteuse pour être faite à chaque publication, ce qui renvoie à
l'automatisation de l'attestation (webhook à la publication, extension
navigateur, API ouverte), pas à une fonctionnalité de détection.

### Invariant ADR-019 à ne jamais violer

Le payload signé d'une attestation de contenu est immuable. Aucun champ ne peut
être ajouté ou retiré sans un ADR explicite et un plan de ré-attestation des
attestations existantes. Toute idée de cette section qui supposerait d'enrichir
le payload doit passer par ce verrou avant toute implémentation.
