# Étape 6 : Relecture qualité et verdict go/no-go

**Reads**
- Toutes les productions des étapes 1 à 5 dans `runs/<slug>/`.
- `_system/principes-editoriaux.md` (les cinq propriétés d'une fiche parfaite).
- `_system/garde-fous.md` (ce qui bloque la publication).
- `_system/voix-createur.md` (règles typographiques).

**Does**
Passer chaque item de la check-list, cocher, et rendre un verdict `go` ou `no-go`.

## Check-list

### Titre et description
- [ ] Titre ne doublonne pas le titre du contenu documenté.
- [ ] Titre de 40 à 90 caractères, phrase complète.
- [ ] Description de 2 à 4 phrases, ~250 à 500 caractères.
- [ ] Aucun tiret cadratin nulle part.

### Sources
- [ ] Chaque source a une annotation non paraphrastique.
- [ ] Chaque source a une `stance` déclarée OU un `null` assumé.
- [ ] Au moins une source pivot, au plus trois.
- [ ] Aucune source « en trop » qui gonfle la liste sans porter le propos.
- [ ] Métadonnées vérifiées : DOI, dates, auteurs, journal, pagination.

### Extraits
- [ ] Chaque source pivot a au moins 2 extraits verbatim.
- [ ] Aucun extrait n'est un contresens hors contexte (spot-check).
- [ ] Chaque extrait court avec pronom référentiel a un `context` explicite.
- [ ] Aucun extrait > 5 pour une source (usage éditorial).
- [ ] Titres d'extraits courts et descriptifs.

### Connexions
- [ ] Chaque suggestion automatique a un verdict tranché (confirmée ou retirée).
- [ ] Les fiches confirmées ont été ouvertes et sont bien celles voulues.

### Verdict
- [ ] Fiche prête à passer publique.
- [ ] URL cible de la publication : `https://filum-eight.vercel.app/@<creator>/<slug>`.

**Writes**
- `runs/<slug>/06_relecture/verdict.md` :

```markdown
---
go: yes | no
date: 2026-08-18
---

# Verdict

## Ce qui est OK
- ...

## Ce qui reste
- ... (si `go: no`)
```

**Human gate**
L'utilisateur ouvre `verdict.md`, lit la liste de ce qui est OK et ce qui reste, ajoute son propre verdict. Si `go: no`, retour à l'étape défaillante (2, 3, 4 ou 5). Si `go: yes`, l'étape 7 démarre.
