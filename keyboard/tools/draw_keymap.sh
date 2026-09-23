#!/usr/bin/env bash
# Regenerate docs/keymap.svg from the ZMK keymap and the generated physical layout.
# needs: pip install keymap-drawer
set -euo pipefail
K="$(cd "$(dirname "$0")/.." && pwd)"
KEYMAP="${KEYMAP:-keymap}"
"$KEYMAP" -c "$K/docs/keymap_drawer.config.yaml" parse -c 12 -z "$K/firmware/config/tsumugi.keymap" > "$K/docs/keymap.yaml"
"$KEYMAP" -c "$K/docs/keymap_drawer.config.yaml" draw \
    -d "$K/firmware/boards/shields/tsumugi/tsumugi-layout.dtsi" "$K/docs/keymap.yaml" > "$K/docs/keymap.svg"
