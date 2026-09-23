#!/usr/bin/env python3
"""Render the ergogen layout (points + board outline) to a PNG preview.

usage: render_layout.py <ergogen_output_dir> <out.png>
"""
import math
import sys

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.patches import Circle, Polygon


def rect(x, y, w, h, r):
    pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    c, s = math.cos(math.radians(r)), math.sin(math.radians(r))
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]


def draw_dxf(ax, path, **kw):
    doc = ezdxf.readfile(path)
    for e in doc.modelspace():
        if e.dxftype() == "LINE":
            ax.plot([e.dxf.start.x, e.dxf.end.x], [e.dxf.start.y, e.dxf.end.y], **kw)
        elif e.dxftype() == "ARC":
            a0, a1 = e.dxf.start_angle, e.dxf.end_angle
            if a1 < a0:
                a1 += 360
            n = max(8, int((a1 - a0) / 5))
            xs = [e.dxf.center.x + e.dxf.radius * math.cos(math.radians(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
            ys = [e.dxf.center.y + e.dxf.radius * math.sin(math.radians(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
            ax.plot(xs, ys, **kw)
        elif e.dxftype() == "CIRCLE":
            ax.add_patch(Circle((e.dxf.center.x, e.dxf.center.y), e.dxf.radius, fill=False, **kw))


def main(out_dir, png):
    pts = yaml.safe_load(open(f"{out_dir}/points/points.yaml"))
    fig, ax = plt.subplots(figsize=(16, 7))
    draw_dxf(ax, f"{out_dir}/outlines/board.dxf", color="#333", lw=1.2)
    draw_dxf(ax, f"{out_dir}/outlines/ball_cutout.dxf", color="#c0392b", lw=1)
    for name, p in pts.items():
        zone = p["meta"]["zone"]["name"]
        if zone in ("matrix", "thumb"):
            ax.add_patch(Polygon(rect(p["x"], p["y"], 17.5, 16.5, p["r"]), closed=True,
                                 fc="#dfe6ee" if zone == "matrix" else "#f5dcc4", ec="#556", lw=0.8))
            ax.text(p["x"], p["y"], f'{p["meta"]["row_net"]}{p["meta"]["column_net"]}', ha="center",
                    va="center", fontsize=6, color="#445")
        elif zone == "bay":
            ax.add_patch(Circle((p["x"], p["y"]), 12.5, fc="#e74c3c55", ec="#c0392b"))
            ax.text(p["x"], p["y"], "bay\n25mm ball", ha="center", va="center", fontsize=7)
        elif zone == "mcu":
            ax.add_patch(Polygon(rect(p["x"], p["y"], 18, 33, p["r"]), closed=True, fc="#9fd3a9", ec="#2e7d32"))
            ax.text(p["x"], p["y"], "nice!nano", ha="center", va="center", fontsize=7, rotation=90)
    ax.set_aspect("equal")
    ax.autoscale()
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(png, dpi=110)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
