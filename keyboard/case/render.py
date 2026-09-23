#!/usr/bin/env python3
"""Renders for the Tsumugi case (run after case.py).

Uses the tessellated meshes that case.py drops into the scratch directory and
draws them with matplotlib (Poly3DCollection, Lambert shading from the face
normals).  Output: ./output/render_*.png
"""
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from matplotlib.patches import Polygon as MplPolygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from shapely.geometry import Polygon

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
SCRATCH = Path(os.environ.get("CASE_SCRATCH", "/tmp/claude-0/case_scratch"))
REPORT = json.loads((OUT / "case_report.json").read_text())

COL = {
    "case": "#c3c7cd", "cover": "#9aa1ab", "pcb": "#2e5e4e", "keycaps": "#f1efe8",
    "ball": "#a23b35", "mcu": "#2b2f36", "bearings": "#e0e0e0", "module": "#3d6fa3",
    "battery": "#c9a64a", "lid": "#d9d4c7", "lidtp": "#d9d4c7", "pad": "#30343b", "lidvis": "#4a4f57",
}
PARTS_3D = ["case", "pcb", "keycaps", "ball", "mcu", "cover"]


def load(name, side, shift=(0, 0, 0)):
    m = trimesh.load(SCRATCH / f"r_{name}_{side}.stl")
    m.apply_translation(shift)
    return m


def shade(mesh, color, light):
    n = mesh.face_normals
    lam = np.abs(n @ light)
    rgb = np.array(matplotlib.colors.to_rgb(color))
    k = 0.38 + 0.62 * lam
    return np.clip(rgb[None, :] * k[:, None], 0, 1)


def draw_scene(ax, meshes, elev, azim, zoom=1.0):
    e, a = np.radians(elev), np.radians(azim)
    eye = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    # key light: above, from the camera's upper left
    la, le = a - np.radians(40), np.radians(min(elev + 35, 80)) if elev > 0 else np.radians(elev - 20)
    light = np.array([np.cos(le) * np.cos(la), np.cos(le) * np.sin(la), np.sin(le)])
    light /= np.linalg.norm(light)
    tris, cols = [], []
    for m, c in meshes:
        m = m.copy()
        # split long triangles so the painter's sort (per-face mean depth) is reliable
        v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=3.0)
        m = trimesh.Trimesh(v, f, process=False)
        n = m.face_normals
        vis = n @ eye > -1e-3                       # back-face culling (closed meshes)
        rgb = np.array(matplotlib.colors.to_rgb(c))
        lam = np.clip(n[vis] @ light, 0, 1)
        rim = np.clip(n[vis] @ eye, 0, 1)
        k = 0.30 + 0.55 * lam + 0.20 * rim
        tris.append(m.vertices[m.faces[vis]])
        cols.append(np.clip(rgb[None, :] * k[:, None], 0, 1))
    tris = np.concatenate(tris)
    cols = np.concatenate(cols)
    pc = Poly3DCollection(tris, facecolors=cols, edgecolors=cols, linewidths=0.15)
    pc.set_zsort("average")
    ax.add_collection3d(pc)
    allv = tris.reshape(-1, 3)
    lo, hi = allv.min(0), allv.max(0)
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo), zoom=zoom)
    ax.set_proj_type("ortho")
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def scene(sides_shift, parts=PARTS_3D):
    ms = []
    for side, sh in sides_shift:
        for p in parts:
            f = SCRATCH / f"r_{p}_{side}.stl"
            if f.exists():
                ms.append((load(p, side, sh), COL[p]))
    return ms


def fig3d(ms, path, elev, azim, title, zoom=1.0, size=(16, 11)):
    fig = plt.figure(figsize=size, dpi=130)
    ax = fig.add_axes([0, 0, 1, 0.95], projection="3d")
    draw_scene(ax, ms, elev, azim, zoom)
    fig.suptitle(title, fontsize=15, y=0.97)
    fig.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    autocrop(path)


def autocrop(path, pad=24):
    """3D axes leave a lot of blank canvas: crop the drawing and the title
    separately and stack them."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    a = np.asarray(im)
    ink = (a < 245).any(axis=2)
    band = int(a.shape[0] * 0.07)                     # the suptitle lives up here

    def bbox(mask, yoff):
        ys, xs = np.where(mask)
        return xs.min(), ys.min() + yoff, xs.max(), ys.max() + yoff

    tx0, ty0, tx1, ty1 = bbox(ink[:band], 0)
    cx0, cy0, cx1, cy1 = bbox(ink[band:], band)
    title = im.crop((tx0, ty0, tx1 + 1, ty1 + 1))
    body = im.crop((max(cx0 - pad, 0), max(cy0 - pad, 0), min(cx1 + pad, a.shape[1]), min(cy1 + pad, a.shape[0])))
    W = max(title.width, body.width) + 2 * pad
    H = title.height + body.height + 2 * pad
    out = Image.new("RGB", (W, H), "white")
    out.paste(title, ((W - title.width) // 2, pad))
    out.paste(body, ((W - body.width) // 2, pad + title.height))
    out.save(path)


def section_polys(mesh, y):
    sec = mesh.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if sec is None:
        return None
    polys = []
    for d in sec.discrete:
        if len(d) >= 4:
            p = Polygon(d[:, [0, 2]]).buffer(0)
            if p.area > 1e-3:
                polys.append(p)
    # even-odd fill
    out = None
    for p in polys:
        out = p if out is None else out.symmetric_difference(p)
    return out


def add_poly(ax, g, color, ec="#333333", lw=0.6, z=1, alpha=1.0):
    if g is None or g.is_empty:
        return
    geoms = getattr(g, "geoms", [g])
    for p in geoms:
        if p.geom_type != "Polygon":
            continue
        verts = [np.array(p.exterior.coords)]
        codes = []
        from matplotlib.path import Path as MPath
        allv, allc = [], []
        for ring in [p.exterior] + list(p.interiors):
            v = np.array(ring.coords)
            allv.append(v)
            c = [MPath.LINETO] * len(v)
            c[0] = MPath.MOVETO
            c[-1] = MPath.CLOSEPOLY
            allc += c
        from matplotlib.patches import PathPatch
        path = MPath(np.concatenate(allv), allc)
        ax.add_patch(PathPatch(path, facecolor=color, edgecolor=ec, lw=lw, zorder=z, alpha=alpha))


def section_figure(side, path):
    rep = REPORT["halves"][side]
    by = rep["ball_centre_desk_mm"][1]
    bx, bz = rep["ball_centre_desk_mm"][0], rep["ball_centre_desk_mm"][2]
    parts = [("case", COL["case"], 2), ("battery", COL["battery"], 1), ("pcb", COL["pcb"], 3),
             ("keycaps", COL["keycaps"], 3), ("mcu", COL["mcu"], 3), ("cover", COL["cover"], 3),
             ("module", COL["module"], 4), ("bearings", COL["bearings"], 5), ("ball", COL["ball"], 4)]
    secs = {p: section_polys(load(p, side), by) for p, _, _ in parts}
    fig, axs = plt.subplots(2, 1, figsize=(14, 12), dpi=130,
                            gridspec_kw={"height_ratios": [1, 1.5]})
    for k, ax in enumerate(axs):
        for p, c, z in parts:
            if p == "ball":
                add_poly(ax, secs[p], c, z=z, alpha=0.85)
            else:
                add_poly(ax, secs[p], c, z=z)
        ax.axhline(0, color="#555555", lw=1.2, zorder=0)
        ax.set_aspect("equal")
        ax.set_facecolor("white")
        ax.grid(True, color="#eeeeee", lw=0.6, zorder=-1)
        ax.set_xlabel("x (desk frame, mm)")
        ax.set_ylabel("z above desk (mm)")
    cb = secs["case"].bounds
    x0, x1 = cb[0] - 6, cb[2] + 6
    from matplotlib.patches import Patch
    axs[0].legend(handles=[Patch(fc=c, ec="#333333", label=l) for l, c in [
        ("case (PLA/PETG)", COL["case"]), ("PCB", COL["pcb"]), ("keycaps", COL["keycaps"]),
        ("trackball", COL["ball"]), ("Ø3 bearing", COL["bearings"]), ("sensor module", COL["module"])]],
        loc="upper left", fontsize=9, ncol=2, frameon=True)
    axs[0].set_xlim(x0, x1)
    axs[0].set_ylim(-4, 38)
    axs[0].fill_between([x0, x1], -4, 0, color="#e8e2d6", zorder=-2, hatch="///", edgecolor="#b8ae9a", lw=0)
    axs[0].set_title(f"{side} half - section y = {-by:.1f} (KiCad), tent {REPORT['tent_deg']} deg", fontsize=13)
    axs[0].text(x0 + 2, -2.8, "desk", fontsize=10, color="#6b5f4a")
    # zoom on the pod
    ax = axs[1]
    ax.set_xlim(bx - 26, bx + 26)
    ax.set_ylim(-3, bz + 16)
    ax.fill_between([bx - 26, bx + 26], -3, 0, color="#e8e2d6", zorder=-2, hatch="///", edgecolor="#b8ae9a", lw=0)
    ax.set_title("ball pod (zoom)", fontsize=13)
    clr = rep["pod_min_clearance_to_desk_mm"]
    notes = [
        (bx, bz, "25 mm ball"),
    ]
    ann = dict(fontsize=10, arrowprops=dict(arrowstyle="-", color="#333333", lw=0.7),
               bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#999999", lw=0.5))
    mtop = bz - 17.9
    s = 1 if side == "left" else -1
    ax.annotate("ball  Ø25", (bx, bz + 6), xytext=(bx - s * 20, bz + 13), **ann)
    ax.annotate("Ø3 bearing seat\n35° below equator", (bx - s * 11.2, bz - 8.4), xytext=(bx - s * 24, bz - 3), **ann)
    ax.annotate("sensor window 10×10", (bx + s * 4.0, bz - 14.2), xytext=(bx + s * 14.5, bz - 9.0), **ann)
    ax.annotate("sensor module 21×21\n(lens gap 2.4 mm)", (bx + s * 6, mtop - 0.8), xytext=(bx + s * 14.5, mtop + 1.0), **ann)
    ax.annotate(f"desk clearance {clr['sensor_board_bottom']:.1f} mm\n(screw heads {clr['module_screw_heads']:.1f} mm)",
                (bx - s * 3, mtop - 2.2), xytext=(bx - s * 25, mtop - 1.0), **ann)
    ax.annotate("PCB", (bx + s * 20, -0.8 + (0)), xytext=(bx + s * 20, bz + 12), fontsize=10) if False else None
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main():
    L, R = REPORT["halves"]["left"], REPORT["halves"]["right"]
    join = L["inner_face_x_desk_mm"] - R["inner_face_x_desk_mm"]
    gap = 45.0
    # (a) both halves side by side
    ms = scene([("left", (0, 0, 0)), ("right", (join + gap, 0, 0))])
    fig3d(ms, OUT / "render_iso_halves.png", 32, -62, zoom=0.95, title=
          f"Tsumugi - both halves (tent {REPORT['tent_deg']}°), keycaps + 25 mm trackballs")
    # (b) joined unibody
    ms = scene([("left", (0, 0, 0)), ("right", (join, 0, 0))])
    fig3d(ms, OUT / "render_unibody.png", 12, -90 + 1e-3, zoom=0.95, title=
          "Magnetically joined 'Λ' unibody (front view)")
    ms = scene([("left", (0, 0, 0)), ("right", (join, 0, 0))])
    fig3d(ms, OUT / "render_unibody_iso.png", 30, -55, zoom=0.95, title="Joined unibody - isometric")
    # (e) the three bay lids (b25 set) with their parts, and (f) a half with the trackpad lid
    ms = []
    for i, k in enumerate(["trackpad", "encoder", "blank"]):
        m = trimesh.load(SCRATCH / f"r_lid_{k}.stl")
        m.apply_translation((0, -i * 40.0, 0))
        ms.append((m, COL["lid"]))
        f = SCRATCH / f"r_lidvis_{k}.stl"
        if f.exists():
            v = trimesh.load(f)
            v.apply_translation((0, -i * 40.0, 0))
            ms.append((v, COL["pad"] if k == "trackpad" else COL["lidvis"]))
    fig3d(ms, OUT / "render_lids.png", 18, 200, zoom=0.95,
          title="Bay lids: Cirque 23 mm trackpad | EC11 encoder | blank  (2 keyed legs with 5x2 magnets)")
    ms = scene([("left", (0, 0, 0))], parts=["case", "pcb", "keycaps", "mcu", "cover", "lidtp", "pad"])
    fig3d(ms, OUT / "render_trackpad_half.png", 38, -70, zoom=0.95,
          title="Left half with the trackpad lid (pad flush with the keycap tops)")
    # (c) section through the ball centre
    section_figure("left", OUT / "render_section_ball.png")
    # (d) bare case, top and bottom
    ms = scene([("left", (0, 0, 0)), ("right", (join + gap, 0, 0))], parts=["case"])
    fig3d(ms, OUT / "render_case_top.png", 55, -70, zoom=0.95, title="Bare cases - pockets, wells, bosses, pod")
    ms = []
    for side, sh in [("left", (0, 0, 0)), ("right", (join + gap, 0, 0))]:
        m = load("case", side, sh)
        ms.append((m, COL["case"]))
    fig3d(ms, OUT / "render_case_bottom.png", -50, -70, zoom=0.95, title="Bare cases - underside (sensor hatch, bumpers, reset hole)")


if __name__ == "__main__":
    main()
