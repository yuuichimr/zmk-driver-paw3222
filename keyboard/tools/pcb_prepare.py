#!/usr/bin/env python3
"""Stage 1 of the PCB pipeline (run with KiCad's python: /usr/bin/python3).

 - replaces ergogen's Edge.Cuts with the clean outline from geometry.py
 - applies JLCPCB-friendly design rules (all currents here are < 50 mA)
 - places M2 mounting holes automatically in free board area
 - exports a Specctra DSN for Freerouting

usage: pcb_prepare.py <ergogen.kicad_pcb> <geometry.json> <out.kicad_pcb> <out.dsn>
"""
import json
import math
import re
import sys

import pcbnew

MM = pcbnew.FromMM


def replace_outline(src, geo, route=False):
    """Swap ergogen's Edge.Cuts for the clean outline (text level, before loading).

    route=True writes the slightly shrunk outline used only for autorouting."""
    text = open(src).read()
    text = re.sub(r"^[ \t]*\(gr_(line|arc|circle) [^\n]*Edge\.Cuts[^\n]*\n", "", text, flags=re.M)
    outline = geo["outline_route"] if route else geo["outline"]
    grow = geo["route_inset"] if route else 0.0
    pts = " ".join(f"(xy {x:.4f} {y:.4f})" for x, y in outline[:-1])
    ball = geo["ball"]
    edge = (f"(gr_poly (pts {pts}) (layer Edge.Cuts) (width 0.15))\n"
            f"(gr_circle (center {ball['x']:.4f} {ball['y']:.4f}) "
            f"(end {ball['x'] + ball['hole_d'] / 2 + grow:.4f} {ball['y']:.4f}) (layer Edge.Cuts) (width 0.15))\n")
    idx = text.rstrip().rfind(")")
    text = text[:idx] + edge + text[idx:]
    out = src.replace(".kicad_pcb", ".route.kicad_pcb" if route else ".edge.kicad_pcb")
    open(out, "w").write(text)
    return out


def setup_rules(board):
    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = MM(0.2)
    ds.m_MinClearance = MM(0.2)
    ds.m_ViasMinSize = MM(0.6)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.3)  # JLCPCB minimum for routed edges
    ns = ds.m_NetSettings
    default = ns.m_DefaultNetClass
    default.SetTrackWidth(MM(0.25))
    default.SetClearance(MM(0.2))
    default.SetViaDiameter(MM(0.6))
    default.SetViaDrill(MM(0.3))


def keepouts(board):
    """Return list of (kind, data) keep-out primitives in mm."""
    rects, circles = [], []
    for fp in board.GetFootprints():
        pos = fp.GetPosition()
        x, y = pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)
        ang = fp.GetOrientationDegrees()
        name = fp.GetFPIDAsString()
        if "PG1350" in name:
            rects.append((x, y, 17.0, 17.0, ang))  # switch body 15 mm + 1 mm margin each side
        else:
            # everything else (MCU, switch, LEDs, header, diodes...): bounding box + margin
            bb = fp.GetBoundingBox(False, False)
            rects.append((pcbnew.ToMM(bb.GetCenter().x), pcbnew.ToMM(bb.GetCenter().y),
                          pcbnew.ToMM(bb.GetWidth()) + 1.0, pcbnew.ToMM(bb.GetHeight()) + 1.0, 0))
        for pad in fp.Pads():
            p = pad.GetPosition()
            r = max(pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)) / 2
            circles.append((pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), r + 1.2))
    return rects, circles


def inside_rect(px, py, r):
    x, y, w, h, ang = r
    a = math.radians(ang)
    dx, dy = px - x, py - y
    lx = dx * math.cos(a) - dy * math.sin(a)
    ly = dx * math.sin(a) + dy * math.cos(a)
    return abs(lx) < w / 2 + 2.0 and abs(ly) < h / 2 + 2.0


def place_mount_holes(board, count=5):
    outline = board.GetBoardEdgesBoundingBox()
    poly = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(poly)
    rects, circles = keepouts(board)
    x0, y0 = pcbnew.ToMM(outline.GetX()), pcbnew.ToMM(outline.GetY())
    x1, y1 = x0 + pcbnew.ToMM(outline.GetWidth()), y0 + pcbnew.ToMM(outline.GetHeight())
    cands = []
    step = 0.5
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            v = pcbnew.VECTOR2I(MM(x), MM(y))
            if poly.Contains(v) and not any(inside_rect(x, y, r) for r in rects) \
                    and not any(math.hypot(x - cx, y - cy) < cr + 1.1 for cx, cy, cr in circles):
                # edge distance >= 3 mm (screw boss wall)
                if all(poly.Contains(pcbnew.VECTOR2I(MM(x + 3 * math.cos(t)), MM(y + 3 * math.sin(t))))
                       for t in [i * math.pi / 6 for i in range(12)]):
                    cands.append((x, y))
            x += step
        y += step
    if not cands:
        return []
    # greedy farthest-point sampling from the candidate closest to the board centroid
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    chosen = [min(cands, key=lambda c: math.hypot(c[0] - cx, c[1] - cy))]
    while len(chosen) < count:
        best = max(cands, key=lambda c: min(math.hypot(c[0] - q[0], c[1] - q[1]) for q in chosen))
        if min(math.hypot(best[0] - q[0], best[1] - q[1]) for q in chosen) < 15:
            break
        chosen.append(best)
    lib = pcbnew.FootprintLoad("/usr/share/kicad/footprints/MountingHole.pretty", "MountingHole_2.2mm_M2")
    for i, (x, y) in enumerate(chosen):
        fp = pcbnew.FOOTPRINT(lib)
        fp.SetReference(f"H{i + 1}")
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        board.Add(fp)
    return chosen


def main(src, geo_path, dst, dsn):
    geo = json.load(open(geo_path))
    board = pcbnew.LoadBoard(replace_outline(src, geo))
    setup_rules(board)
    holes = place_mount_holes(board)
    print(f"mounting holes: {[(round(x, 1), round(y, 1)) for x, y in holes]}")
    board.Save(dst)
    # the DSN is exported from a twin board whose edge is inset (see geometry.py)
    route = pcbnew.LoadBoard(replace_outline(src, geo, route=True))
    setup_rules(route)
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("H"):
            route.Add(fp.Duplicate())
    print("dsn export:", pcbnew.ExportSpecctraDSN(route, dsn))


if __name__ == "__main__":
    main(*sys.argv[1:5])
