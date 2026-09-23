#!/usr/bin/env bash
# Build every Tsumugi firmware variant listed in keyboard/firmware/build.yaml.
#   ZMK_APP       : path to zmk/app inside an initialised west workspace
#   EXTRA_MODULES : additional zephyr modules, ';'-separated (zmk-rgbled-widget)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FW="$ROOT/keyboard/firmware"
ZMK_APP="${ZMK_APP:-/opt/zmkws/zmk/app}"
EXTRA_MODULES="${EXTRA_MODULES:-/opt/zmkws/zmk-rgbled-widget}"
OUT="${OUT:-$FW/build}"
mkdir -p "$OUT"

python3 - "$FW/build.yaml" > "$OUT/matrix.tsv" <<'PY'
import sys, yaml
for e in yaml.safe_load(open(sys.argv[1]))["include"]:
    print("|".join([e["board"], e["shield"], e.get("snippet", ""), e.get("cmake-args", ""), e["artifact-name"]]))
PY

status=0
while IFS='|' read -r board shield snippet cargs name; do
  echo "=== $name ($board / $shield)"
  bdir="$OUT/$name"
  args=(-DZMK_CONFIG="$FW/config" "-DSHIELD=$shield" "-DZMK_EXTRA_MODULES=$ROOT;$EXTRA_MODULES")
  [ -n "$cargs" ] && args+=($cargs)
  snip=()
  [ -n "$snippet" ] && snip=(-S "$snippet")
  if (cd "$ZMK_APP" && west build -p -s "$ZMK_APP" -d "$bdir" -b "$board" "${snip[@]}" -- "${args[@]}") \
       > "$OUT/$name.log" 2>&1; then
    cp "$bdir/zephyr/zmk.uf2" "$OUT/$name.uf2"
    printf '    ok   %s\n' "$(grep -E 'FLASH:' "$OUT/$name.log" | tail -1 | sed 's/  */ /g')"
  else
    echo "    FAILED - see $OUT/$name.log"; tail -30 "$OUT/$name.log"; status=1
  fi
done < "$OUT/matrix.tsv"
exit $status
