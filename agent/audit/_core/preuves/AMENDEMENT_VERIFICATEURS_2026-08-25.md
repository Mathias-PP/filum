# Amendements des vérificateurs — 2026-08-25, pendant la porte G1

Règle 5 du plan (anti-contournement) : un vérificateur amendé invalide ses verts antérieurs. Les deux correctifs ci-dessous ont été suivis d'un **rejeu complet de G0** (verte, voir `G0_vert_*_1547/1549` via rejeu dans gate_g1.sh) puis du double vert G1 final.

## 1. `spot_check.sh` — pollution des ancres par le seed

Le tirage concaténait le seed à chaque ancre (`awk '{print substr($0"     "s,0), ""}'`) : l'extraction `p=${a%:*}` / `l=${a##*:}` produisait une « ligne » contenant le seed → erreur arithmétique, extraits de code vides dans la fiche.

Correctif : suppression de l'awk ; le caractère déterministe du tirage reste assuré par `sort -R --random-source=<(yes "$SEED")`.

## 2. `check_lot.sh` (e) — deux faux négatifs/positifs

- **Faux positif** : `grep -c 'CONTRADICTION'` comptait la ligne d'instruction du gabarit spot-check (elle mentionne le mot) → toute fiche conforme était déclarée en contradiction. Correctif : exclure les lignes d'en-tête `^>` avant comptage.
- **Faux négatif** : `grep '^\s*- \[ \]'` ne matchait pas les items réels du gabarit (`## - [ ] chemin:ligne`, préfixés par `##`) → une case jamais cochée rendait PAS la porte rouge. Détecté par smoke-test. Correctif : motif `'^#{0,4}[[:space:]]*-[[:space:]]\[[[:space:]]\]'`.

## Validation post-amendement (gate_g1b.sh)

| Test | Attendu | Résultat |
|---|---|---|
| G0 rejoué | verte | ✅ VERTE |
| Smoke A : item `- [ ]` non coché | ECHEC G1(e) cases vides | ✅ détecté |
| Smoke B : aucune fiche spot | ECHEC G1(e) absence | ✅ détecté |
| Smoke C : ancre `llm.py:99999` | ECHEC G1(c) hors bornes | ✅ détecté |
| Double vert G1 sur doc réelle | 2× exit 0 | ✅ `G1_vert_*_final.txt` |

Enseignement consigné aussi dans PITFALLS §3.8 : un vérificateur validé uniquement sur son chemin nominal (G0) peut porter ces deux classes de bugs ; toujours smoke-tester avec le format réel produit, pas un format reconstruit de mémoire.
