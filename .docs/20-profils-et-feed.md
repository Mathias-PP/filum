# Spec : profils publics cherchables et feed chronologique

> Spécification demandée le 2026-08-06. Aucun code dans ce document.

---

## Contexte et existant

Deux surfaces publiques existent déjà :

- `/@[username]` : profil public d'un créateur, affiche ses fiches publiées.
- `/discover` : liste de fiches récentes, cherchables par texte libre.

Ce qui manque :
- La recherche de **créateurs** (pas seulement de fiches).
- Un **feed chronologique public** des publications.

---

## 1. Recherche de profils

### Ce qui est indexé

- Nom affiché (`display_name`).
- Nom d'utilisateur (`username`).
- Biographie (`User.bio`, colonne à ajouter ou à exposer si elle existe).

### Ce qui n'est pas indexé — règle stricte

- Les fiches privées et les brouillons.
- L'adresse e-mail.
- Les comptes liés non vérifiés.

### Interface

Ajouter un onglet « Créateurs » dans `/discover` (ou une route `/discover/creators`)
retournant des profils paginés. Chaque résultat montre le nom, l'avatar, le
nombre de fiches publiées et les badges de comptes vérifiés.

L'endpoint backend `GET /api/v1/discover/creators?q=&limit=&offset=` n'existe pas :
à créer lors de l'implémentation.

---

## 2. Le feed : une trace, pas un réseau social

### Sa raison d'être

L'utilisateur l'a formulé lui-même : « l'objectif est de tracer les dates de
publication des fiches sur un feed visible publiquement ».

Cette phrase doit guider toutes les décisions de conception : le feed est un
registre chronologique, pas un outil d'engagement.

### Règles de conception, non négociables

1. **Ordre chronologique strict**, jamais algorithmique. Un tri par engagement
   cesserait d'être une trace : il deviendrait un concours.
2. **Pas de compteurs de popularité, pas de « likes », pas de recommandations.**
   Ils transformeraient l'horodatage en signal de performance.
3. **Les entrées sont immuables.** Une entrée enregistre qu'une fiche a été
   publiée à une date. Si la fiche est ensuite dépubliée, l'entrée reste —
   éventuellement marquée « dépubliée ». C'est la même logique que l'attestation
   de contenu (ADR-019) : on ne peut pas effacer le passé.

### Ce que le feed rend possible

L'étude interne (2026-08-06, front 6) a établi, citant Viblio et CHI 2024, que
publier une bibliographie pour une audience est un vide documenté dans
l'écosystème. Les spectateurs traitent une description YouTube comme un signal
d'effort, pas comme une source vérifiable. Le feed est la surface publique qui
manque pour que l'effort de documentation soit visible et daté.

### Modèle de données esquissé (à ne pas implémenter ici)

```sql
feed_events (
  id          UUID PRIMARY KEY,
  kind        TEXT NOT NULL,         -- 'card_published' en v1
  actor_id    UUID REFERENCES users,
  card_id     UUID REFERENCES biblio_cards,
  occurred_at TIMESTAMP NOT NULL
)
```

Types prévus pour les versions suivantes, sans les ouvrir :
- `card_updated` : modification d'une fiche publiée.
- `claim_verified` : rattachement d'un canal vérifié à un compte.

### Vie privée

Une fiche privée n'entre jamais dans le feed. La question de la rétroactivité
(une fiche publiée puis passée en privé doit-elle disparaître du feed ?) est
posée dans `.docs/07-open-questions.md`.

---

## 3. Ce qui reste hors périmètre de cette spec

- L'implémentation du feed ou de la recherche de créateurs.
- Les notifications push ou e-mail basées sur le feed.
- Les abonnements entre créateurs.
- La modération du feed.
