#!/usr/bin/env python3
"""Stage 2 of the PCB pipeline (KiCad python).

 - imports the Freerouting session (.ses)
 - adds GND copper pours on both layers and fills them
 - runs KiCad DRC and writes a report + a one-line summary

usage: pcb_finish.py <prepared.kicad_pcb> <routed.ses|-> <out.kicad_pcb> <drc_report.txt>
"""
import re
import sys

import pcbnew

MM = pcbnew.FromMM


def tokenize(text):
    return re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text)


def parse_sexpr(tokens):
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def import_ses(board, path):
    """Minimal Specctra session importer (KiCad 7's ImportSpecctraSES needs the GUI frame)."""
    ses = parse_sexpr(tokenize(open(path).read()))
    routes = find(ses, "routes")[0]
    res = float(find(routes, "resolution")[0][2])        # e.g. um 10 -> 1 unit = 0.1 um
    to_nm = lambda v: int(round(float(v) * 1000.0 / res))  # um/res -> nm
    layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    tracks = vias = 0
    for net_node in find(find(routes, "network_out")[0], "net"):
        net = board.FindNet(net_node[1])
        for wire in find(net_node, "wire"):
            path = find(wire, "path")[0]
            layer, width, coords = path[1], to_nm(path[2]), path[3:]
            pts = [(to_nm(coords[i]), -to_nm(coords[i + 1])) for i in range(0, len(coords) - 1, 2)]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(x0, y0))
                t.SetEnd(pcbnew.VECTOR2I(x1, y1))
                t.SetWidth(width)
                t.SetLayer(layers[layer])
                t.SetNet(net)
                board.Add(t)
                tracks += 1
        for via_node in find(net_node, "via"):
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(to_nm(via_node[2]), -to_nm(via_node[3])))
            m = re.search(r"_(\d+):(\d+)_um", via_node[1])
            v.SetWidth(int(m.group(1)) * 1000 if m else MM(0.6))
            v.SetDrill(int(m.group(2)) * 1000 if m else MM(0.3))
            v.SetNet(net)
            board.Add(v)
            vias += 1
    return tracks, vias


def add_gnd_pours(board):
    gnd = board.FindNet("GND")
    poly = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(poly)
    outline = poly.Outline(0)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(layer)
        zone.SetNet(gnd)
        zone.SetLocalClearance(MM(0.3))
        zone.SetMinThickness(MM(0.25))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        zone.SetIsFilled(False)
        zone.AddPolygon(outline)
        zone.SetAssignedPriority(0)
        board.Add(zone)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def main(src, ses, dst, report):
    board = pcbnew.LoadBoard(src)
    if ses != "-":
        tracks, vias = import_ses(board, ses)
        print(f"imported {tracks} track segments, {vias} vias")
    add_gnd_pours(board)
    board.Save(dst)
    board = pcbnew.LoadBoard(dst)
    pcbnew.WriteDRCReport(board, report, pcbnew.EDA_UNITS_MILLIMETRES, True)
    text = open(report).read()
    counts = re.findall(r"\*\* Found (\d+) ([^*]+?) \*\*", text)
    # library-link warnings are expected: ergogen embeds footprints without a library
    errors = [b for b in text.split("\n[")[1:] if "Severity: error" in b]
    unconnected = int(dict((w.strip(), n) for n, w in counts).get("unconnected pads", 0))
    print(f"{dst}: " + ", ".join(f"{n} {what.strip()}" for n, what in counts)
          + f" -> {len(errors)} errors, {unconnected} unconnected")
    if errors or unconnected:
        for e in errors[:10]:
            print("  [" + e.strip().splitlines()[0])
        raise SystemExit(1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
