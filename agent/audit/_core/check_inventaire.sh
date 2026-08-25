#!/usr/bin/env bash
# check_inventaire.sh — Porte G0 (bloquante). Sortie 0 = porte verte, sinon échec.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")"/../../.. && pwd)"
cd "$ROOT"
AUDIT="agent/audit/_core"
CSV="$AUDIT/inventaire.csv"
FAIL=0
note() { printf '%s\n' "$*"; FAIL=$((FAIL+1)); }

[ -f "$CSV" ] || { echo "ECHEC G0: $CSV absent"; exit 1; }
[ -f "$AUDIT/invariants.txt" ] || { echo "ECHEC G0: invariants.txt absent"; exit 1; }

# (a)+(b) point fixe : tout ce que collect() voit doit être au CSV, et réciproquement pour le périmètre
"$AUDIT/gen_inventaire.sh" --paths | sort > /tmp/g0_expected.txt
tail -n +2 "$CSV" | awk -F, '{print $1" "$2" "$3}' | sort > /tmp/g0_actual.txt
MISSING=$(comm -23 /tmp/g0_expected.txt /tmp/g0_actual.txt | wc -l)
EXTRA=$(comm -13 /tmp/g0_expected.txt /tmp/g0_actual.txt | wc -l)
if [ "$EXTRA" -ne 0 ]; then note "ECHEC G0(a): $EXTRA ligne(s) du CSV ne correspondent plus à rien"; fi
if [ "$MISSING" -ne 0 ]; then note "ECHEC G0(b): $MISSING fichier(s) manquant(s) au CSV :"; comm -23 /tmp/g0_expected.txt /tmp/g0_actual.txt; fi

# (c) LOC périmètre cohérent avec la baseline gelée (±5 %) et avec la référence du plan
LOC_DISK=$(awk -F, '$1=="perimetre"{s+=$4} END{print s+0}' "$CSV")
BASE=$(grep -E '^INV_LOC_PERIMETRE=' "$AUDIT/invariants.txt" | cut -d= -f2)
REF_LO=22843; REF_HI=25248   # baseline machine du 2026-08-25 : 24046 ±5 % (estimation initiale 21400 corrigée en G0)
if [ -z "$BASE" ]; then note "ECHEC G0(c): baseline LOC absente des invariants";
else
  LO=$(( BASE * 95 / 100 )); HI=$(( BASE * 105 / 100 ))
  if [ "$LOC_DISK" -lt "$LO" ] || [ "$LOC_DISK" -gt "$HI" ]; then note "ECHEC G0(c): LOC disque=$LOC_DISK hors ±5% de la baseline=$BASE"; fi
fi
if [ "$LOC_DISK" -lt "$REF_LO" ] || [ "$LOC_DISK" -gt "$REF_HI" ]; then note "ECHEC G0(c): LOC=$LOC_DISK hors de la référence plan [$REF_LO..$REF_HI]"; fi

# (d) intégrité des lignes du CSV (loc=0 légitime : fichier vide = trivialement lu en entier)
BAD=$(tail -n +2 "$CSV" | awk -F, '
  $4 !~ /^[0-9]+$/ || $4+0 < 0             { print "loc invalide: " $3; next }
  $5 !~ /^[0-9a-f]{64}$/                   { print "sha256 invalide: " $3; next }
  ($6 !~ /^-?[0-9]+$/)                     { print "symboles invalide: " $3; next }
  $7 == "" || !($7 ~ /^(todo|lu|documente|verifie)$/) { print "statut invalide: " $3 }
')
if [ -n "$BAD" ]; then note "ECHEC G0(d): lignes invalides:"; echo "$BAD"; fi

# (e) les 4 invariants posés et entiers
for v in INV_OUTILS_MCP INV_ENDPOINTS_AGENT INV_EVENEMENTS_SSE INV_VARS_ENV; do
  val=$(grep -E "^$v=[0-9]+$" "$AUDIT/invariants.txt" | cut -d= -f2)
  [ -z "$val" ] && note "ECHEC G0(e): invariant $v absent ou non entier"
done

if [ "$FAIL" -eq 0 ]; then echo "G0 VERTE : inventaire complet et coherent ($(wc -l < "$CSV") lignes, $LOC_DISK LOC perimetre)"; exit 0; fi
echo "G0 ROUGE : $FAIL categorie(s) d'echec"; exit 1
