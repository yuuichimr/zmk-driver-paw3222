#!/usr/bin/env bash
# Full PCB pipeline: ergogen -> clean outline -> KiCad prep -> Freerouting -> SES import
#                    -> GND pour -> DRC -> gerbers/drill/renders
# requires: node (ergogen 4.2.1 in $ERGOGEN_PREFIX), KiCad 7 (pcbnew python + kicad-cli),
#           java 21 + freerouting jar ($FREEROUTING_JAR), python venv with shapely/pyyaml ($PYVENV)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERGOGEN_PREFIX="${ERGOGEN_PREFIX:-/opt/ergo}"
FREEROUTING_JAR="${FREEROUTING_JAR:-/opt/fr/fr2.jar}"  # freerouting v2.1.0
PY="${PYVENV:-/opt/tv}/bin/python"
KPY=/usr/bin/python3
WORK="${WORK:-$(mktemp -d)}"
OUT="$ROOT/pcb/output"
mkdir -p "$OUT" "$WORK"
drc_failed=0

npx --prefix "$ERGOGEN_PREFIX" ergogen "$ROOT/pcb/ergogen" -o "$WORK/ergogen" --debug >/dev/null
"$PY" "$ROOT/tools/geometry.py" "$WORK/ergogen/points/points.yaml" "$OUT"
"$PY" "$ROOT/tools/render_layout.py" "$WORK/ergogen" "$OUT/layout_preview.png"

for side in left right; do
  "$KPY" "$ROOT/tools/pcb_prepare.py" "$WORK/ergogen/pcbs/tsumugi_$side.kicad_pcb" \
      "$OUT/geometry_$side.json" "$WORK/$side.kicad_pcb" "$WORK/$side.dsn" 2>&1 | grep -v swig/python
  (cd "$WORK" && java -jar "$FREEROUTING_JAR" --gui.enabled=false --router.max_passes=250 --router.optimizer.enabled=false --router.job_timeout=00:15:00 \
      -de "$side.dsn" -do "$side.ses" >"$side.freerouting.log" 2>&1 || true)
  "$KPY" "$ROOT/tools/pcb_finish.py" "$WORK/$side.kicad_pcb" "$WORK/$side.ses" \
      "$OUT/tsumugi_$side.kicad_pcb" "$OUT/drc_$side.txt" 2>&1 | grep -v swig/python || drc_failed=1
  mkdir -p "$OUT/gerbers_$side"
  kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
      --subtract-soldermask -o "$OUT/gerbers_$side/" "$OUT/tsumugi_$side.kicad_pcb" >/dev/null
  kicad-cli pcb export drill --format excellon --excellon-separate-th -o "$OUT/gerbers_$side/" \
      "$OUT/tsumugi_$side.kicad_pcb" >/dev/null
  (cd "$OUT/gerbers_$side" && rm -f "../tsumugi_${side}_gerbers.zip" && zip -q "../tsumugi_${side}_gerbers.zip" *)
  kicad-cli pcb export svg --layers F.Cu,B.Cu,F.SilkS,B.SilkS,Edge.Cuts --page-size-mode 2 \
      --exclude-drawing-sheet -o "$WORK/$side.svg" "$OUT/tsumugi_$side.kicad_pcb" >/dev/null
  "$PY" -c "import cairosvg; cairosvg.svg2png(url='$WORK/$side.svg', write_to='$OUT/pcb_$side.png', output_width=1600, background_color='white')"
done
echo "outputs in $OUT"
exit $drc_failed
