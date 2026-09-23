#!/usr/bin/env python3
"""Single source of truth for board geometry, derived from ergogen points.

Builds clean, closed outlines with shapely (the ergogen/makerjs offset output
contains tiny broken arcs that KiCad rejects) and writes one JSON per half that
both the PCB pipeline and the case CAD consume.

Coordinates are written in KiCad convention (mm, y pointing down).

usage: geometry.py <ergogen points.yaml> <out_dir>
"""
import json
import math
import sys

import yaml
from shapely import affinity
from shapely.geometry import Point, box
from shapely.ops import unary_union

KX, KY = 18.0, 17.0
BAY_R = 17.0
BALL_HOLE = 28.0
ROUTE_INSET = 0.15


def rot_rect(x, y, w, h, r):
    return affinity.rotate(box(x - w / 2, y - h / 2, x + w / 2, y + h / 2), r, origin=(x, y))


def build(points, mirrored):
    sel = {k: v for k, v in points.items() if k.startswith("mirror_") == mirrored}
    shapes, keys = [], []
    bay = mcu = None
    for name, p in sel.items():
        tags = p["meta"].get("tags") or []
        tags = list(tags.keys()) if isinstance(tags, dict) else tags
        if "key" in tags:
            shapes.append(rot_rect(p["x"], p["y"], KX + 1, KY + 1, p["r"]))
            keys.append({"name": name, "x": p["x"], "y": -p["y"], "r": p["r"],
                         "row": p["meta"]["row_net"], "col": p["meta"]["column_net"],
                         "thumb": "thumb" in tags})
        elif "bay" in tags:
            bay = p
            shapes.append(Point(p["x"], p["y"]).buffer(BAY_R + 1, 128))
        elif "mcu" in tags:
            mcu = p
            shapes.append(rot_rect(p["x"], p["y"], 26, 38, 0))
            shapes.append(rot_rect(p["x"], p["y"] - 24, 24, 20, 0))
    body = unary_union(shapes).buffer(9, 64).buffer(-7.5, 64)
    body = body.simplify(0.01)
    flip = lambda g: affinity.scale(g, 1, -1, origin=(0, 0))
    body = flip(body)
    # Freerouting only keeps its default 0.2 mm from the edge; routing inside an
    # outline shrunk by ROUTE_INSET guarantees the 0.3 mm copper-to-edge rule.
    route = body.buffer(-ROUTE_INSET, 64).simplify(0.01)
    return {
        "outline": [list(c) for c in body.exterior.coords],
        "outline_route": [list(c) for c in route.exterior.coords],
        "route_inset": ROUTE_INSET,
        "ball": {"x": bay["x"], "y": -bay["y"], "hole_d": BALL_HOLE, "bay_r": BAY_R},
        "mcu": {"x": mcu["x"], "y": -mcu["y"]},
        "keys": keys,
        "bounds": list(body.bounds),
    }


def main(points_yaml, out_dir):
    points = yaml.safe_load(open(points_yaml))
    for side, mirrored in (("left", False), ("right", True)):
        g = build(points, mirrored)
        json.dump(g, open(f"{out_dir}/geometry_{side}.json", "w"), indent=1)
        b = g["bounds"]
        print(f"{side}: {b[2] - b[0]:.1f} x {b[3] - b[1]:.1f} mm, {len(g['keys'])} keys, "
              f"{len(g['outline'])} outline vertices")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
