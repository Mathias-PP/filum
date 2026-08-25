#!/usr/bin/env bash
# spot_check.sh <lot> [nb_items] [seed] — sous-boucle anti-fraude des portes G1..G7.
# Tire au hasard (seed déterministe) des ancres dans la doc du lot, imprime le code réel
# à côté de chaque ancre, et génère une fiche à cocher dans _core/preuves/.
# La porte check_lot.sh refuse le vert tant que cette fiche contient des cases vides
# ou une CONTRADICTION non résolue.
set -uo pipefail
LOT="${1:?usage: spot_check.sh <1-7> [nb=6] [seed]}"
NB="${2:-6}"
SEED="${3:-$(date +%s)}"
ROOT="$(cd "$(dirname "$0")"/../../.. && pwd)"
cd "$ROOT"
AUDIT="agent/audit/_core"
declare -A DIRS=( [1]=01-fondations [2]=02-noyau [3]=03-outils-mcp [4]=04-api [5]=05-services-metier [6]=06-interface-chat [7]=07-tests-et-prod )
DOC="agent/audit/${DIRS[$LOT]:-}"
mkdir -p "$AUDIT/preuves"
OUT="$AUDIT/preuves/spot_lot${LOT}_$(date +%F)_s$SEED.md"

[ -d "$DOC" ] || { echo "ECHEC: dossier doc absent ($DOC)"; exit 1; }

grep -rhoE '[A-Za-z0-9_/.-]+\.(py|ts|svelte|yaml|json):[0-9]+' "$DOC" --include='*.md' | sort -u > /tmp/spots_all.txt
TOTAL=$(wc -l < /tmp/spots_all.txt)
[ "$TOTAL" -eq 0 ] && { echo "ECHEC: aucune ancre dans $DOC"; exit 1; }
[ "$NB" -gt "$TOTAL" ] && NB=$TOTAL

{
  echo "# Spot-check lot $LOT — seed=$SEED, $(date +%F)"
  echo "> Pour chaque item : comparer l'affirmation de la doc au code réel ci-dessous."
  echo "> Cocher \`[x]\` OK, ou écrire \`CONTRADICTION\` + fichier concerné (il retombera à statut=lu)."
  echo ""
  # tirage déterministe : tri par hash(seed, ligne)
  awk -v s="$SEED" '{ print substr($0"     "s,0), "" }' /tmp/spots_all.txt | sort -R --random-source=<(yes "$SEED") | head -n "$NB" | while read -r a; do
    p="${a%:*}"; l="${a##*:}"
    echo "## - [ ] $a"
    echo '```'
    sed -n "$((l>2 ? l-2 : 1)),$((l+4))p" "$p" 2>/dev/null || echo "(fichier illisible : $p)"
    echo '```'
    echo ""
  done
} > "$OUT"

echo "[spot] $NB items tirés sur $TOTAL ancres -> $OUT"
echo "[spot] Tant que cette fiche contient des cases vides ou une CONTRADICTION, G$LOT reste rouge."
