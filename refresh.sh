#!/bin/sh
# DECP Radar — weekly refresh (target: under 2h/week of effort, one command).
#
# Steps:
#   1. download the CURRENT-YEAR consolidated DECP file if a newer version
#      exists upstream (data.gouv.fr, Licence Ouverte 2.0). Older years are
#      frozen snapshots: only re-download manually with --full.
#   2. rebuild the expiry dataset from every local decp-YYYY.json
#      (newest consolidation of a (acheteur, id) wins).
#   3. regenerate data/expiries_upcoming.csv + the free public sample.
#
# Usage:
#   ./refresh.sh            # download current-year delta + rebuild + sample
#   ./refresh.sh --full     # also re-download every missing year (large)
#   ./refresh.sh --no-dl    # rebuild from local files only
#
# Inputs:  $DECP_CONSOL (default ~/src/decp-digest/data/consol) decp-YYYY.json
# Outputs: data/expiries.parquet, data/expiries_upcoming.csv,
#          data/build_stats.json, samples/sample-expirations.csv
set -eu

BASE="$(cd "$(dirname "$0")" && pwd)"
CONSOL="${DECP_CONSOL:-$BASE/../decp-digest/data/consol}"
PYTHON="${PYTHON:-python3}"
MODE="${1:-default}"
mkdir -p "$CONSOL" "$BASE/data" "$BASE/report"

# --- 1. download (current year by default; all years with --full) -----------
if [ "$MODE" != "--no-dl" ]; then
  YEARS=$(python3 - "$CONSOL" <<'EOF'
import sys
from pathlib import Path
from datetime import date
consol = Path(sys.argv[1])
have = {p.name for p in consol.glob("decp-*.json")}
y = date.today().year
want = [f"decp-{y}.json"]
if len(sys.argv) > 2 and sys.argv[2] == "--full":
    want += [f"decp-{yy}.json" for yy in (2019, 2022, 2024, 2025)]
print("\n".join(w for w in want if w not in have))
EOF
)
  # Resolve the latest dataset version URL for each year via the data.gouv API.
  for f in $YEARS; do
    y=$(echo "$f" | sed 's/decp-\(.*\)\.json/\1/')
    url=$(python3 - "$y" <<'EOF'
import json, sys, urllib.request
y = sys.argv[1]
u = ("https://www.data.gouv.fr/api/2/datasets/"
     "donnees-essentielles-de-la-commande-publique-fichiers-consolides/")
d = json.load(urllib.request.urlopen(u, timeout=60))
for r in d.get("resources", []):
    if r.get("format") == "json" and r.get("title", "").endswith(f"decp-{y}.json"):
        print(r["url"]); break
EOF
)
    if [ -n "${url:-}" ]; then
      echo "downloading $f ..."
      curl -fsSL --retry 3 -o "$CONSOL/$f.part" "$url" && mv "$CONSOL/$f.part" "$CONSOL/$f"
    else
      echo "WARNING: no upstream URL found for $f; skipping download" >&2
    fi
  done
fi

# --- 2. rebuild the expiry dataset ------------------------------------------
cd "$BASE"
DECP_CONSOL="$CONSOL" "$PYTHON" expiry_build.py

# --- 3. upcoming-window CSV + free public sample + IT report ----------------
"$PYTHON" expiry_report.py

echo "refresh done: $(date -Is)"