#!/usr/bin/env bash
# gen_inventaire.sh — Phase 0 du plan de revue agent (agent/plans/2026-08-25-revue-code-agent.md)
# Génère l'inventaire machine du périmètre + les invariants chiffrés.
# Usage :
#   ./gen_inventaire.sh            → écrit inventaire.csv + invariants.txt
#   ./gen_inventaire.sh --paths    → imprime "type lot chemin" (utilisé par check_inventaire.sh)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")"/../../.. && pwd)"
cd "$ROOT"
AUDIT="agent/audit/_core"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

symboles() {
  local f="$1"
  case "$f" in
    *.py)     { grep -cE '^(async def|def|class) ' "$f" || true; } 2>/dev/null ;;
    *.ts)     { grep -cE '^export (async )?(function|const|interface|type|class)|^export \{' "$f" || true; } 2>/dev/null ;;
    *.svelte) { grep -cE '(^|[[:space:]])((async )?function [A-Za-z_$]+|const [A-Za-z_$]+ = (\(|async))' "$f" || true; } 2>/dev/null ;;
    *)        echo "-1" ;;
  esac
}

# Charge les listes brutes dans $T (migrations, tests, workspace, seed, scripts)
charger_listes() {
  git ls-files "apps/backend/alembic/versions/*.py" > "$T/migs.txt" || true
  git ls-files "apps/backend/tests/unit/test_agent*.py" "apps/backend/tests/unit/test_mcp*.py" "apps/backend/tests/unit/test_workspace_seed_sync.py" > "$T/tests.txt" || true
  git ls-files "apps/backend/tests/integration/*" > "$T/integ.txt" || true
  grep -iE 'agent|mcp|chat' "$T/integ.txt" >> "$T/tests.txt" || true
  find workspaces/createur-de-fiches -type f >> "$T/tests.txt" 2>/dev/null || true
  find apps/backend/app/agent_workspace_seed -type f >> "$T/tests.txt" 2>/dev/null || true
  git ls-files "apps/backend/app/scripts/build_workspace_seed.py" "apps/backend/app/scripts/export_openapi.py" >> "$T/tests.txt" || true
  sort -u -o "$T/tests.txt" "$T/tests.txt"
}

# Écrit "type lot chemin" dans $1 : périmètre par patterns, puis interfaces par fermeture d'imports
collect_to_file() {
  local dest="$1" p f
  : > "$dest"
  for p in \
    "apps/backend/app/services/agent*.py" \
    "apps/backend/app/mcp_server/*.py" \
    "apps/backend/app/api/v1/endpoints/agent_*.py" \
    "apps/backend/app/schemas/agent_*.py" \
    "apps/backend/app/models/agent_*.py" ; do
    for f in $(git ls-files "$p"); do
      case "$f" in
        */services/agent.py|*/services/agent_approvals.py|*/services/agent_sessions.py) echo "perimetre 2 $f" >> "$dest" ;;
        */mcp_server/*)                                                                 echo "perimetre 3 $f" >> "$dest" ;;
        */endpoints/*)                                                                  echo "perimetre 4 $f" >> "$dest" ;;
        */schemas/*|*/models/*)                                                         : ;;  # classés lot 1 ci-dessous
        *)                                                                              echo "perimetre 5 $f" >> "$dest" ;;
      esac
    done
  done
  # lot 1 : fondations (config, contrats de données, migrations, transport LLM)
  echo "perimetre 1 apps/backend/app/core/config.py" >> "$dest"
  for f in $(git ls-files "apps/backend/app/models/agent_*.py" "apps/backend/app/schemas/agent_*.py"); do echo "perimetre 1 $f" >> "$dest"; done
  grep -E '/(040|042|045|046|047|049|051|052)_' "$T/migs.txt" | while read -r f; do echo "perimetre 1 $f" >> "$dest"; done
  for f in apps/backend/app/services/llm.py apps/backend/app/services/llm_adapters.py; do
    [ -f "$f" ] && echo "perimetre 1 $f" >> "$dest";
  done
  # lot 6 : frontend
  git ls-files "apps/frontend/src/lib/agent/*.ts" "apps/frontend/src/lib/api/agent.ts" "apps/frontend/src/lib/components/chat/*.svelte" | while read -r f; do echo "perimetre 6 $f" >> "$dest"; done
  find apps/frontend/src/routes/dashboard/chat apps/frontend/src/routes/dashboard/agents -name '*.svelte' -type f 2>/dev/null | while read -r f; do echo "perimetre 6 $f" >> "$dest"; done
  # lot 7 : tests + workspace ICM + seed embarqué + scripts outillant
  while read -r f; do [ -n "$f" ] && echo "perimetre 7 $f" >> "$dest"; done < "$T/tests.txt"
  # --- interfaces : imports app-local des .py du périmètre, hors périmètre ---
  awk '$1=="perimetre"{print $3}' "$dest" > "$T/perim.txt"
  : > "$T/mods.txt"
  while read -r f; do
    [ "${f##*.}" = "py" ] || continue
    grep -hoE '(from|import) app\.[a-zA-Z_.]+' "$f" >> "$T/mods.txt" 2>/dev/null || true
  done < "$T/perim.txt"
  sed -E 's/^(from|import) //' "$T/mods.txt" | sort -u | while read -r mod; do
    [ -n "$mod" ] || continue
    cand="$(echo "$mod" | tr '.' '/')"
    for ext in ".py" "/__init__.py"; do
      [ -f "apps/backend/${cand}${ext}" ] && echo "interface 0 apps/backend/${cand}${ext}" >> "$dest"
    done
  done
  return 0
}

if [ "${1:-}" = "--paths" ]; then
  charger_listes
  collect_to_file "$T/all.txt"
  sort -u -k3,3 "$T/all.txt"
  exit 0
fi

mkdir -p "$AUDIT"
COMMIT="$(git rev-parse HEAD)"
DATE="$(date +%F)"

charger_listes
collect_to_file "$T/all.txt"
sort -u -k3,3 "$T/all.txt" > "$T/all_sorted.txt"

# --- CSV ---
{
  echo "type,lot,chemin,loc,sha256,symboles,statut"
  while read -r typ lot f; do
    printf '%s,%s,%s,%s,%s,%s,todo\n' "$typ" "$lot" "$f" "$(wc -l < "$f")" "$(sha256sum "$f" | cut -d' ' -f1)" "$(symboles "$f")"
  done < "$T/all_sorted.txt"
} > "$AUDIT/inventaire.csv"

# --- invariants ---
OUTILS=$(grep -c '^@outil' apps/backend/app/mcp_server/server.py || echo 0)
ENDPOINTS=$(grep -hE '@router\.(get|post|put|delete|patch)' apps/backend/app/api/v1/endpoints/agent_*.py | wc -l)
# Les événements SSE sont émis depuis la boucle ET l'endpoint chat (session/discovery/gratuit) :
cat apps/backend/app/services/agent.py \
    apps/backend/app/services/agent_gratuit.py \
    apps/backend/app/services/agent_discovery.py \
    apps/backend/app/api/v1/endpoints/agent_chat.py 2>/dev/null > "$T/sse_src.txt" || true
SSE=$(grep -hoE '"type": "[a-z_]+"' "$T/sse_src.txt" | sort -u | grep -v '"function"' | wc -l)
VARS=$(grep -cE '^[[:space:]]+(agent_|llm_|gratuit_|lane_|discovery_)[a-z_]*[[:space:]]*:' apps/backend/app/core/config.py || echo 0)
LOC_PERIM=$(awk -F, '$1=="perimetre"{s+=$4} END{print s+0}' "$AUDIT/inventaire.csv")
NB_FIC=$(($(wc -l < "$AUDIT/inventaire.csv") - 1))

cat > "$AUDIT/invariants.txt" <<EOF
# Invariants de la revue agent — gelés le $DATE au commit $COMMIT
INV_DATE=$DATE
INV_COMMIT=$COMMIT
INV_OUTILS_MCP=$OUTILS
INV_ENDPOINTS_AGENT=$ENDPOINTS
INV_EVENEMENTS_SSE=$SSE
INV_VARS_ENV=$VARS
INV_LOC_PERIMETRE=$LOC_PERIM
INV_NB_FICHIERS=$NB_FIC
# Référence du plan (mesurée le 2026-08-25 sur dae9cc0) : ~21400 LOC / ~80 fichiers
EOF

echo "[gen] $NB_FIC fichiers ($LOC_PERIM LOC perimetre) -> $AUDIT/inventaire.csv"
echo "[gen] invariants : outils=$OUTILS endpoints=$ENDPOINTS sse=$SSE vars_env=$VARS"
