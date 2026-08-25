#!/usr/bin/env bash
# check_lot.sh <lot> — Porte bloquante G1..G7. Sortie 0 = porte verte, sinon échec.
# Conditions : (a) 100% fichiers du lot statut=verifie · (b) 100% symboles retrouvés dans la doc
# (c) ancres chemin:ligne résolues · (d) sha256 courant cité dans la doc + chemin mentionné
# (e) fiche spot-check complète (aucune case vide)
set -uo pipefail
LOT="${1:?usage: check_lot.sh <1-7> [seed]}"
SEED="${2:-$(date +%s)}"
ROOT="$(cd "$(dirname "$0")"/../../.. && pwd)"
cd "$ROOT"
AUDIT="agent/audit/_core"
CSV="$AUDIT/inventaire.csv"
declare -A DIRS=( [1]=01-fondations [2]=02-noyau [3]=03-outils-mcp [4]=04-api [5]=05-services-metier [6]=06-interface-chat [7]=07-tests-et-prod )
DOC="agent/audit/${DIRS[$LOT]:-}"
FAIL=0
note() { printf '%s\n' "$*"; FAIL=$((FAIL+1)); }

[ -n "${DIRS[$LOT]:-}" ] || { echo "ECHEC: lot '$LOT' inconnu (attendu 1-7)"; exit 1; }
[ -d "$DOC" ] || { echo "ECHEC G$LOT: dossier doc absent ($DOC) — rien n'a été documenté"; exit 1; }

# (a) statut verifie pour 100 % des fichiers du lot
TODO=$(awk -F, -v l="$LOT" '$2==l && $7!="verifie" {print $3" ("$7")"}' "$CSV")
if [ -n "$TODO" ]; then note "ECHEC G$LOT(a): fichiers non 'verifie':"; echo "$TODO"; fi

# (b) chaque symbole greppé doit apparaître dans la doc du domaine
MISS_SYM=0
while IFS=, read -r typ lot f loc sha sym st; do
  [ "$lot" = "$LOT" ] || continue
  case "$f" in
    *.py)     NAMES=$(grep -oE '^(async def|def|class) [A-Za-z_]+' "$f" | awk '{print $NF}') ;;
    *.ts)     NAMES=$(grep -oE '^export (async )?(function|const|interface|type|class) [A-Za-z_]+' "$f" | awk '{print $NF}') ;;
    *)        NAMES="" ;;
  esac
  for n in $NAMES; do
    grep -rqw --include='*.md' "$n" "$DOC" || { note "ECHEC G$LOT(b): symbole '$n' ($f) absent de la doc"; MISS_SYM=$((MISS_SYM+1)); }
  done
done < <(tail -n +2 "$CSV")

# (c) toutes les ancres chemin:ligne citées dans la doc résolvent
BAD_ANCHOR=0
grep -rhoE '[A-Za-z0-9_/.-]+\.(py|ts|svelte|yaml|json|md):[0-9]+' "$DOC" --include='*.md' | sort -u | while read -r a; do
  p="${a%:*}"; l="${a##*:}"
  if [ ! -f "$p" ]; then echo "ECHEC G$LOT(c): ancre vers fichier inexistant: $a"; touch /tmp/glot_fail_$$
  elif ! [ "$l" -le "$(wc -l < "$p")" ] 2>/dev/null; then echo "ECHEC G$LOT(c): ancre hors bornes: $a"; touch /tmp/glot_fail_$$
  fi
done
[ -f /tmp/glot_fail_$$ ] && { note "(voir lignes ECHEC (c) ci-dessus)"; rm -f /tmp/glot_fail_$$; }

# (d) chaque fichier code du lot est mentionné + son sha256 COURANT figure dans la doc
while IFS=, read -r typ lot f loc sha sym st; do
  [ "$lot" = "$LOT" ] && [ "$loc" -gt 0 ] || continue
  grep -rqF "$f" "$DOC" --include='*.md' || note "ECHEC G$LOT(d): fichier jamais cité: $f"
  grep -rqE "sha256:?\s*${sha:0:12}" "$DOC" --include='*.md' || note "ECHEC G$LOT(d): sha256 courant non cité (fichier modifié depuis lecture ?): $f"
done < <(tail -n +2 "$CSV")

# (e) fiche(s) spot-check présentes et entièrement cochées
SPOT=$(ls "$AUDIT"/preuves/spot_lot"${LOT}"_*.md 2>/dev/null | tail -1)
if [ -z "$SPOT" ]; then note "ECHEC G$LOT(e): aucune fiche spot-check (lancer spot_check.sh $LOT)";
else
  OPEN=$(grep -c '^\s*- \[ \]' "$SPOT" || true)
  BADV=$(grep -c 'CONTRADICTION' "$SPOT" || true)
  [ "$OPEN" -gt 0 ] && note "ECHEC G$LOT(e): $OPEN item(s) spot-check non vérifié(s) dans $SPOT"
  [ "$BADV" -gt 0 ] && note "ECHEC G$LOT(e): CONTRADICTION consignée dans $SPOT — le(s) fichier(s) repassent à 'lu', doc à réécrire, puis reboucler"
fi

if [ "$FAIL" -eq 0 ]; then echo "G$LOT VERTE : lot couvert, documenté, spot-checké (seed=$SEED)"; exit 0; fi
echo "G$LOT ROUGE : $FAIL catégorie(s) d'échec"; exit 1
