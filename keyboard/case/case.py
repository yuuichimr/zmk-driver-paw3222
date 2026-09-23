#!/usr/bin/env python3
"""
Tsumugi - parametric 3D-printable tented case (build123d)
=========================================================

Builds, for each half (left / right, each from its own PCB geometry):

  * a tented tray case with integrated wedge (prints flat on its bottom),
  * a trackball pod (25 mm ball, 3 x 3 mm static bearings, PAW3222 sensor
    module pocket with 2 M2 heat-set inserts),
  * USB-C / power-switch openings, reset pin-hole, battery pocket,
    M2 heat-set insert bosses, magnet pockets on the inner face (the two
    halves snap together into a "Λ" unibody) and bumper recesses,
  * a separate MCU cover plate (with LED holes),
  * visual-only solids (PCB, keycaps, ball, nice!nano, sensor module) used
    for the renders.

Coordinate frames
-----------------
PCB frame  : millimetres, x right, y UP (= -KiCad y), z = 0 is the PCB top
             surface, the PCB occupies -1.6 <= z <= 0.
DESK frame : the PCB frame translated so that the outer bottom edge of the
             case is at the origin and rotated about the y axis by the tent
             angle so that the INNER edge is raised.  z = 0 is the desk.
             All case STL/STEP files are exported in this frame (print bed).

  left  half : inner edge = +x ;  x_d = u*cos(t) - (z+Z_BOTTOM)*sin(t)
  right half : inner edge = -x ;  (mirror)       z_d = u*sin(t) + (z+Z_BOTTOM)*cos(t)
  with u = distance from the outer edge measured inwards and Z_BOTTOM = 5.4.

Run:  /opt/tv/bin/python case.py            (writes ./output/*)
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
from shapely import affinity
from shapely.geometry import MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

from build123d import (Align, Box, Cone, Cylinder, Face, Location, Part, Pos, Rot,
                       Sphere, Vector, Wire, export_step, export_stl, extrude)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PCB_OUT = HERE.parent / "pcb" / "output"
PCB_FALLBACK = Path("/tmp/claude-0/pcb")
OUT = HERE / "output"
SCRATCH = Path(os.environ.get("CASE_SCRATCH", "/tmp/claude-0/case_scratch"))

# ---------------------------------------------------------------------------
# Parameters (all mm / degrees)
# ---------------------------------------------------------------------------
PCB_T = 1.6                 # PCB thickness
HOTSWAP_GAP = 2.2           # space below the PCB for Choc hot-swap sockets
FLOOR_TOP = -PCB_T - HOTSWAP_GAP        # = -3.8, tray floor top under the keys
FLOOR_T = 1.6               # minimum floor / wall thickness
Z_BOTTOM = FLOOR_TOP - FLOOR_T          # = -5.4, case underside at the outer edge
WALL_T = 2.2                # tray wall thickness
WALL_CLEAR = 0.5            # gap PCB edge -> wall
WALL_TOP = 2.5              # wall top (below keycaps, which start at +5.6)

TENT_DEG_MIN = 8.0          # requested tent (lower bound of the search)
TENT_STEP = 0.5             # minimum tent is rounded UP to this step
TENT_RES = 0.1              # resolution of the exact minimum-tent search
POD_MIN_CLEAR = 1.0         # sensor module + screw heads must clear the desk by this
# "Detents": the tent is fixed by the printed wedge, so users print the angle
# they want (our answer to Kobito-key's adjustable tenting).  The minimum per
# ball size is computed, the others are fixed.
TENT_DETENTS = (14.0, 18.0)

# Trackball / pod
BALL_SIZES = (25.0, 19.0)  # supported trackballs (Kobito-key style 19 mm or 25 mm)
BALL_DEFAULT = 25.0
BALL_TOP_ABOVE_KEYS = 2.0   # ball top this much above the keycap tops (+8.0)
CUP_AIR = 0.7               # cup inner radius = ball radius + CUP_AIR
# active ball variant - set by set_ball(); defaults = 25 mm ball
BALL_D = 25.0
BALL_Z = -2.5               # ball centre (PCB frame): top at +10.0
CUP_R = 13.2                # cup inner radius
BEARING_D = 3.0             # static support balls (Si3N4 / ZrO2)
BEARING_SEAT_D = 3.05       # spherical press-fit seat
BEARING_ELEV = -35.0        # contact angle below the ball equator (PCB frame)
BEARING_AZ = (180.0, 300.0, 60.0)   # azimuths (deg, 0 = +x); 180 lies in the section plane
SENSOR_WINDOW = 10.0        # square through-opening under the ball
LENS_GAP = 2.4              # lens top -> ball surface
LENS_H = 3.0                # lens height above the module board
MODULE_W = 21.0             # sensor module board (square)
MODULE_T = 1.6
MODULE_CLEAR = 0.3          # per side in the pocket
MODULE_SCREWS = ((-8.5, 0.0), (8.5, 0.0))    # M2 holes on the module (local, desk x); keeps clear of the lid bores
SCREW_HEAD_H = 1.3          # M2 pan/button head height (below the module)
WIRE_CH_W = 4.0             # wire channel pod -> tray; radial span CUP_R-2.7 .. CUP_R+1.0
WIRE_CH_R0, WIRE_CH_R1 = 10.5, 14.2

# Bay lids (trackpad / encoder / blank) - drop into the 28 mm PCB hole
BAY_HOLE_R = 14.0           # PCB cut-out radius
LID_R = 13.7                # lid body radius (0.3 radial clearance in the PCB hole)
LID_CONE_CLEAR = 0.4        # 45 deg cone underside vs the cup rim / cup sphere
LID_LEG_R = 3.2             # 2 legs, keyed into 2 landing bores in the pod
LID_BORE_R = 3.5
LID_LEG_AZ = (120.0, 240.0) # azimuths (PCB frame, same on both halves), clear of the bearings
LID_MAG_D, LID_MAG_T = 5.1, 2.1   # pockets for 5 x 2 mm disc magnets (lid leg + pod landing)
LID_MAG_FLOOR = 0.8         # material kept under the pod magnet pocket
PAD_D_WANTED = 35.0         # Cirque TM035035
PAD_D_FALLBACK = 23.0       # Cirque TM023023
PAD_T = 3.0                 # 1.8 mm overlay + board
PAD_BEZEL = 0.8             # printed ring around the pad
PAD_KEY_CLEAR = 0.5         # plan-view clearance pad bezel -> keycap
FPC_SLOT = (12.0, 3.0)
BLANK_TOP_Z = 0.0           # blank lid flush with the PCB top
ENC_BODY = 12.0             # EC11 body (square) ...
ENC_BODY_H = 6.5            # ... height below the mounting surface
ENC_SHAFT_L = 15.0          # shaft length from the mounting surface (EC11E 15 mm)
ENC_KNOB_TOP_EXTRA = 1.0    # knob top above the shaft end
ENC_PANEL_T = 2.0
ENC_HOLE_D = 7.0            # M7 bushing
ENC_TAB = (1.4, 2.6, 7.0)   # anti-rotation slot (w, l, offset from the shaft) - check datasheet
ENC_KNOB_D = 18.0

# Heat-set inserts (M2)
INSERT_BOSS_D = 5.5
INSERT_HOLE_D = 3.2
INSERT_DEPTH = 4.0

# Openings
USB_W, USB_H = 12.0, 7.0    # USB-C plug overmold slot
# nice!nano mounting differs per half (lead's note on the final PCBs):
#   left : component side UP, flush            -> board 0..1.6, USB-C on top
#   right: component side DOWN on ~2 mm spacer -> board 3.5..5.1, USB-C below
MCU_Z = {"left": (0.0, 3.0), "right": (2.0, 5.1)}      # visual block z range
USB_ZC = {"left": 3.2, "right": 1.9}                     # USB-C receptacle centre
SW_W, SW_H, SW_ZC = 8.0, 4.0, 0.9             # slide-switch actuator slot
RESET_HOLE_D = 2.0
LED_LOCAL_X = 1.8                             # LED offset inside LED_R_0603_pair

# Battery pocket
BAT_CLEAR = 0.5             # per side
BAT_Z_CLEAR = 0.5           # extra depth (LiPo swelling)
BAT_MAX_DIST_MCU = 25.0     # pocket centre must stay within this of the MCU
# (name, thickness, width, length, typical capacity mAh) - common LiPo sizes
LIPOS = [
    ("402030", 4.0, 20.0, 30.0, 180),
    ("403035", 4.0, 30.0, 35.0, 400),
    ("502535", 5.0, 25.0, 35.0, 400),
    ("503035", 5.0, 30.0, 35.0, 500),
    ("603035", 6.0, 30.0, 35.0, 600),
    ("603040", 6.0, 30.0, 40.0, 750),
    ("803040", 8.0, 30.0, 40.0, 1000),
    ("603450", 6.0, 34.0, 50.0, 1100),
    ("803450", 8.0, 34.0, 50.0, 1500),
]

# Magnets / bumpers
MAG_D, MAG_T = 6.1, 3.1     # pocket for 6 x 3 mm N52 discs
MAG_Z_PCB = -16.0           # magnet centre depth (PCB frame, at the inner face)
INNER_STRIP = 5.0           # solid strip along the inner face (no hollowing)
BUMPER_D, BUMPER_DEPTH = 10.4, 0.8
BUMPER_INSET = 8.0

# Light-weighting: open-top wells under the floor (vertical walls => no supports)
WELL_PITCH = 14.0
RIB_T = 1.6

# MCU cover
COVER_T = 1.6
COVER_Z0 = 5.6              # plate underside: common for both halves, 0.5 mm over the
                            # right nano (top ~5.1 on spacers) and the left USB-C receptacle
COVER_HALF_W = 15.0         # cover extent from the MCU centre towards the keys
COVER_TOP_EXTRA = 22.0      # from MCU centre towards the top edge
COVER_LED_MARGIN = 4.5      # below the LED row
COVER_KEY_CLEAR = 0.7       # plan-view clearance to the keycaps
COVER_BALL_CLEAR = 15.5     # plan-view radius kept free around the ball
COVER_POST_D, COVER_PIN_D = 5.0, 3.0
COVER_SCREW_D = 2.4
LED_HOLE_D = 2.0

# Visual parts
KEYCAP_W, KEYCAP_H = 17.5, 16.5
KEYCAP_Z0, KEYCAP_Z1 = 5.6, 8.0
MCU_W, MCU_L, MCU_T = 18.0, 33.0, 3.0

PLA_DENSITY = 1.24          # g/cm^3
STL_TOL, STL_ANG = 0.03, 0.15


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------
def parse_kicad(path: Path) -> dict:
    """Return {ref: (x, y, rot, lib)} for all footprints (KiCad coords)."""
    txt = path.read_text()
    out = {}
    for m in re.finditer(r'\(footprint "([^"]+)"', txt):
        lib = m.group(1)
        chunk = txt[m.end(): m.end() + 3000]
        at = re.search(r'\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', chunk)
        ref = re.search(r'\(fp_text reference "([^"]+)"', chunk)
        if not ref:
            ref = re.search(r'\(property "Reference" "([^"]+)"', chunk)
        if at and ref:
            out[ref.group(1)] = (float(at.group(1)), float(at.group(2)),
                                 float(at.group(3) or 0.0), lib)
    return out


def load_half(side: str) -> dict:
    g = json.loads((PCB_OUT / f"geometry_{side}.json").read_text())
    pcb = PCB_OUT / f"tsumugi_{side}.kicad_pcb"
    if not pcb.exists():
        pcb = PCB_FALLBACK / f"{side}.kicad_pcb"
    fps = parse_kicad(pcb)
    Y = lambda y: -y                               # KiCad -> y-up
    h = {"side": side, "s": 1 if side == "left" else -1, "pcb_file": str(pcb)}
    h["outline"] = Polygon([(x, Y(y)) for x, y in g["outline"]]).buffer(0)
    h["ball"] = (g["ball"]["x"], Y(g["ball"]["y"]))
    h["ball_hole_r"] = g["ball"]["hole_d"] / 2
    h["mcu"] = (g["mcu"]["x"], Y(g["mcu"]["y"]))
    h["keys"] = [(k["x"], Y(k["y"]), k["r"]) for k in g["keys"]]
    h["holes"] = [(fps[r][0], Y(fps[r][1])) for r in sorted(fps)
                  if re.fullmatch(r"H\d+", r) and "MountingHole" in fps[r][3]]
    by_lib = lambda name: [v for v in fps.values() if name in v[3]]
    sw = by_lib("SPDT_C128955")[0]
    rst = by_lib("SW_TACT_ALPS_SKQGABE010")[0]
    h["switch"] = (sw[0], Y(sw[1]))
    h["reset"] = (rst[0], Y(rst[1]))
    leds = []
    for ref in sorted(r for r in fps if r.startswith("LED")):
        x, y, rot, _ = fps[ref]
        a = math.radians(rot)
        # KiCad: local +x rotated by rot (counter-clockwise on screen)
        lx, ly = x + LED_LOCAL_X * math.cos(a), y - LED_LOCAL_X * math.sin(a)
        leds.append((lx, Y(ly)))
    h["leds"] = leds
    j1 = [v for v in fps.values() if "MODULE_BAY" in v[3]]
    h["j1"] = (j1[0][0], Y(j1[0][1])) if j1 else h["mcu"]
    xs = [p[0] for p in h["outline"].exterior.coords]
    h["x_outer"] = min(xs) if h["s"] > 0 else max(xs)
    h["x_inner"] = max(xs) if h["s"] > 0 else min(xs)
    # straight inner segment (y range)
    seg = [p for p in h["outline"].exterior.coords if abs(p[0] - h["x_inner"]) < 0.05]
    h["seg_y"] = (min(p[1] for p in seg), max(p[1] for p in seg))
    return h


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------
class Frame:
    """PCB frame <-> desk frame for one half."""

    def __init__(self, h: dict, tent: float):
        self.s, self.xoc, self.t = h["s"], h["x_outer"] + (-h["s"]) * (WALL_CLEAR + WALL_T), math.radians(tent)
        self.tent = tent

    def to_desk(self, x, y, z):
        u = self.s * (x - self.xoc)
        c, sn = math.cos(self.t), math.sin(self.t)
        zz = z - Z_BOTTOM
        return (self.s * (u * c - zz * sn), y, u * sn + zz * c)

    def desk_z_axis_in_pcb(self):
        """Unit vector of the desk vertical expressed in the PCB frame."""
        return np.array([self.s * math.sin(self.t), 0.0, math.cos(self.t)])

    def loc(self) -> Location:
        return Rot(0, -self.s * self.tent, 0) * Pos(-self.xoc, 0, -Z_BOTTOM)

    def T(self, shape):
        return self.loc() * shape

    def desk_to_pcb_xy_on_desk(self, xd, yd):
        """PCB xy of the point that lies on the desk plane at desk (xd, yd)."""
        u_d = self.s * xd
        u = u_d * math.cos(self.t)
        return (self.xoc + self.s * u, yd)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _wire(coords, z):
    pts = [Vector(float(x), float(y), z) for x, y in list(coords)[:-1]]
    return Wire.make_polygon(pts, close=True)


def prism(geom, z0: float, z1: float) -> Part | None:
    """Extrude a shapely (Multi)Polygon between z0 and z1."""
    if geom.is_empty:
        return None
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    solids = None
    for p in polys:
        if p.area < 0.05:
            continue
        p = p.simplify(0.01, preserve_topology=True)
        f = Face(_wire(p.exterior.coords, z0),
                 [_wire(i.coords, z0) for i in p.interiors if Polygon(i).area > 0.05])
        s = extrude(f, amount=z1 - z0, dir=(0, 0, 1))
        solids = s if solids is None else solids + s
    return solids


def box_at(cx, cy, cz, lx, ly, lz) -> Part:
    return Pos(cx, cy, cz) * Box(lx, ly, lz)


def rect(cx, cy, w, l, rot=0.0):
    r = box(cx - w / 2, cy - l / 2, cx + w / 2, cy + l / 2)
    return affinity.rotate(r, rot, origin=(cx, cy)) if rot else r


def union_all(parts):
    out = None
    for p in parts:
        if p is None:
            continue
        out = p if out is None else out + p
    return out


# ---------------------------------------------------------------------------
# Tent angle: raise it until the sensor module (+ screw heads) clears the desk
# ---------------------------------------------------------------------------
def set_ball(d: float):
    """Select the active trackball variant (updates the ball-dependent globals)."""
    global BALL_D, BALL_Z, CUP_R, WIRE_CH_R0, WIRE_CH_R1
    BALL_D = d
    BALL_Z = KEYCAP_Z1 + BALL_TOP_ABOVE_KEYS - d / 2      # 25 -> -2.5, 19 -> +0.5
    CUP_R = d / 2 + CUP_AIR
    WIRE_CH_R0, WIRE_CH_R1 = CUP_R - 2.7, CUP_R + 1.0


def cup_z(r):
    """Lower cup surface height (PCB frame) at radius r from the ball axis."""
    return BALL_Z - math.sqrt(max(CUP_R ** 2 - r ** 2, 0.0))


def cup_rim_r():
    return math.sqrt(CUP_R ** 2 - (FLOOR_TOP - BALL_Z) ** 2)


def lid_landing():
    """Leg radius and landing height of the lid legs in the pod."""
    # legs as far out as the PCB hole allows (same for every ball size); the
    # landing floor sits where the cup surface passes the inner edge of the
    # magnet ring, so the magnet pocket and a LID_MAG_FLOOR ring are in solid
    r_leg = LID_R - LID_LEG_R
    z_land = cup_z(r_leg - LID_MAG_D / 2 - LID_MAG_FLOOR)
    return r_leg, z_land


def module_depths():
    """Distances below the ball centre (along the sensor axis)."""
    top = BALL_D / 2 + LENS_GAP + LENS_H          # module board top surface
    return top, top + MODULE_T, top + MODULE_T + SCREW_HEAD_H


def pod_clearance(h, tent):
    fr = Frame(h, tent)
    bz = fr.to_desk(h["ball"][0], h["ball"][1], BALL_Z)[2]
    _, board_bot, screw_bot = module_depths()
    return bz - board_bot, bz - screw_bot


def choose_tent(halves):
    """Exact minimum tent (TENT_RES) and the value rounded up to TENT_STEP."""
    t = 0.0
    while t < 30:
        if all(pod_clearance(h, t)[1] >= POD_MIN_CLEAR for h in halves):
            exact = t
            return exact, math.ceil(exact / TENT_STEP - 1e-9) * TENT_STEP
        t = round(t + TENT_RES, 3)
    raise RuntimeError("no tent angle found")


# ---------------------------------------------------------------------------
# Battery placement (2D search)
# ---------------------------------------------------------------------------
def place_battery(h, fr, allowed):
    mx, my = h["mcu"]
    best = None
    for name, t, w, l, mah in sorted(LIPOS, key=lambda b: -b[4]):
        depth = t + BAT_Z_CLEAR
        zb = FLOOR_TOP - depth
        for (pw, pl) in ((w + 2 * BAT_CLEAR, l + 2 * BAT_CLEAR), (l + 2 * BAT_CLEAR, w + 2 * BAT_CLEAR)):
            cands = []
            for dx in np.arange(-BAT_MAX_DIST_MCU, BAT_MAX_DIST_MCU + 0.1, 0.5):
                for dy in np.arange(-BAT_MAX_DIST_MCU, BAT_MAX_DIST_MCU + 0.1, 0.5):
                    if math.hypot(dx, dy) > BAT_MAX_DIST_MCU:
                        continue
                    cx, cy = mx + dx, my + dy
                    r = rect(cx, cy, pw, pl)
                    if not allowed.contains(r):
                        continue
                    # every pocket-bottom corner must keep FLOOR_T above the desk
                    zmin = min(fr.to_desk(x, y, zb)[2] for x, y in list(r.exterior.coords))
                    if zmin < FLOOR_T:
                        continue
                    cands.append((math.hypot(dx, dy), cx, cy, zmin))
            if cands:
                d, cx, cy, zmin = min(cands)
                cand = dict(name=name, t=t, w=w, l=l, mah=mah, cx=cx, cy=cy,
                            pw=pw, pl=pl, depth=depth, z_bottom=zb,
                            floor_below=zmin, dist_mcu=d)
                if best is None or d < best["dist_mcu"]:
                    best = cand
        if best:
            return best
    return None


# ---------------------------------------------------------------------------
# Build one half
# ---------------------------------------------------------------------------
def build_half(h: dict, tent: float) -> dict:
    s = h["s"]
    fr = Frame(h, tent)
    th = math.radians(tent)
    outline = h["outline"]
    outer = outline.buffer(WALL_CLEAR + WALL_T, join_style=1, quad_segs=6)
    cavity = outline.buffer(WALL_CLEAR, join_style=1, quad_segs=6)
    zone = outline.buffer(WALL_CLEAR - FLOOR_T, join_style=1, quad_segs=6)
    xin = h["x_inner"]
    y0, y1 = h["seg_y"]

    # --- inner face: vertical in the desk frame -----------------------------
    # X_in so that the wall is >= WALL_T at the floor level (it is thicker above)
    X_in = fr.to_desk(xin + s * WALL_CLEAR, 0, FLOOR_TOP)[0] + s * WALL_T
    # extension so the PCB-frame prism reaches the desk-vertical face everywhere
    near = [p for p in outline.exterior.coords if s * (p[0] - xin) > -2.0]
    ext_top = max(p[1] for p in near) + WALL_CLEAR + WALL_T
    ext = box(min(xin, xin + s * 40), y0, max(xin, xin + s * 40), ext_top)
    body_poly = unary_union([outer, ext])

    # --- pod geometry (desk frame) ------------------------------------------
    bx, by = h["ball"]
    C = np.array(fr.to_desk(bx, by, BALL_Z))
    m_top, m_bot, m_screw = module_depths()
    z_mtop = C[2] - m_top

    # desk-vertical column around the pod in PCB xy (for the keep-outs)
    dz = fr.desk_z_axis_in_pcb()
    shift = -dz[0] / dz[2] * (m_top + 2)          # xy drift of the axis at module depth
    pod_keep = unary_union([
        Point(bx, by).buffer(max(CUP_R + FLOOR_T + 0.5, lid_landing()[0] + LID_BORE_R + FLOOR_T)),
        rect(bx, by, MODULE_W + 2 * MODULE_CLEAR + 2 * FLOOR_T, MODULE_W + 2 * MODULE_CLEAR + 2 * FLOOR_T),
        rect(bx + shift, by, MODULE_W + 2 * MODULE_CLEAR + 2 * FLOOR_T, MODULE_W + 2 * MODULE_CLEAR + 2 * FLOOR_T),
    ]).convex_hull

    # --- keep-outs for wells and battery ------------------------------------
    boss_keep = unary_union([Point(p).buffer(INSERT_BOSS_D / 2 + FLOOR_T) for p in h["holes"]])
    reset_keep = Point(h["reset"]).buffer(RESET_HOLE_D / 2 + FLOOR_T)
    strip = box(min(xin, xin - s * INNER_STRIP), -1e4, max(xin, xin - s * INNER_STRIP) + 0 * s, 1e4)
    strip = box(min(xin - s * INNER_STRIP, xin + s * 50), -1e4, max(xin - s * INNER_STRIP, xin + s * 50), 1e4)

    allowed_bat = zone.difference(unary_union([
        Point(p).buffer(INSERT_BOSS_D / 2 + 1.0) for p in h["holes"]]
        + [reset_keep, pod_keep]))
    bat = place_battery(h, fr, allowed_bat)
    if bat is None:
        raise RuntimeError(f"{h['side']}: no battery fits")
    bat_poly = rect(bat["cx"], bat["cy"], bat["pw"], bat["pl"])

    # --- bumpers (desk frame, on the underside) -----------------------------
    # desk-level footprint: PCB-frame prism walls meet the desk at x_d = s*u/cos
    def foot_map(g):
        return affinity.scale(affinity.translate(g, -fr.xoc, 0), xfact=1 / math.cos(th), yfact=1, origin=(0, 0))
    foot = foot_map(outer)
    foot = foot.difference(box(-1e4, -1e4, 1e4, 1e4).difference(
        box(min(0, X_in), -1e4, max(0, X_in), 1e4)))
    foot = unary_union([foot, foot_map(ext).intersection(box(min(0, X_in), -1e4, max(0, X_in), 1e4))])
    rx, ry = h["reset"]
    u_r = s * (rx - fr.xoc)
    reset_foot = (s * u_r / math.cos(th), ry)
    bump_region = foot.buffer(-BUMPER_INSET).difference(unary_union([
        Point(C[0], C[1]).buffer(18.0), Point(reset_foot).buffer(7.0)]))
    minx, miny, maxx, maxy = bump_region.bounds
    bumpers = []
    for cx, cy in ((minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)):
        from shapely.ops import nearest_points
        p = nearest_points(bump_region, Point(cx, cy))[0]
        bumpers.append((p.x, p.y))
    bump_keep = unary_union([Point(fr.desk_to_pcb_xy_on_desk(*b)).buffer(BUMPER_D / 2 + FLOOR_T + 1.0)
                             for b in bumpers])

    # --- wells (light-weighting) --------------------------------------------
    keep = unary_union([boss_keep, reset_keep, pod_keep, strip,
                        bat_poly.buffer(FLOOR_T, join_style=2), bump_keep])
    gx0, gy0, gx1, gy1 = zone.bounds
    cells = []
    for gx in np.arange(gx0 - WELL_PITCH, gx1 + WELL_PITCH, WELL_PITCH):
        for gy in np.arange(gy0 - WELL_PITCH, gy1 + WELL_PITCH, WELL_PITCH):
            cells.append(box(gx + RIB_T / 2, gy + RIB_T / 2, gx + WELL_PITCH - RIB_T / 2, gy + WELL_PITCH - RIB_T / 2))
    wells2d = unary_union(cells).intersection(zone).difference(keep)
    # drop slivers
    wells2d = unary_union([g for g in getattr(wells2d, "geoms", [wells2d])
                           if g.area > 12 and g.minimum_rotated_rectangle.buffer(0).area > 0
                           and g.buffer(-2.0).area > 0])

    # ======================= solid modelling ================================
    BIG = 2000.0
    body = fr.T(prism(body_poly, -120.0, WALL_TOP))
    keep_box = Pos(0, 0, BIG / 2) * Box(BIG, BIG, BIG)                         # z_d >= 0
    keep_box = keep_box - Pos(X_in + s * BIG / 2, 0, 0) * Box(BIG, BIG, 3 * BIG)  # inner face
    case = body & keep_box

    case = case - fr.T(prism(cavity, FLOOR_TOP, 30.0))
    wells = fr.T(prism(wells2d, -120.0, FLOOR_TOP + 0.3))
    wells = wells & (Pos(0, 0, FLOOR_T + BIG / 2) * Box(BIG, BIG, BIG))
    case = case - wells

    # insert bosses (top at the PCB bottom)
    bosses = union_all(fr.T(Pos(x, y, (FLOOR_TOP - 0.4 - PCB_T) / 2) *
                            Cylinder(INSERT_BOSS_D / 2, -PCB_T - (FLOOR_TOP - 0.4)))
                       for x, y in h["holes"])
    case = case + bosses

    cut = []
    for x, y in h["holes"]:
        cut.append(Pos(x, y, -PCB_T - INSERT_DEPTH / 2 + 0.05) * Cylinder(INSERT_HOLE_D / 2, INSERT_DEPTH + 0.1))
    # reset pin-hole, straight down (PCB normal) through the whole wedge
    cut.append(Pos(rx, ry, -60) * Cylinder(RESET_HOLE_D / 2, 2 * 60 + 2 * FLOOR_TOP + 0.2))
    # battery pocket
    cut.append(prism(bat_poly, bat["z_bottom"], FLOOR_TOP + 0.3))
    # USB-C and slide-switch slots through the top wall
    mx, my = h["mcu"]
    top_edge = max(p[1] for p in outline.exterior.coords if abs(p[0] - mx) < 7)
    usb_slot = box_at(mx, top_edge + 2.0, USB_ZC[h["side"]], USB_W, 8.0, USB_H)
    swx, swy = h["switch"]
    sw_edge = max(p[1] for p in outline.exterior.coords if abs(p[0] - swx) < 5)
    sw_slot = box_at(swx, sw_edge + 1.0, SW_ZC, SW_W, 8.0, SW_H)
    cut += [usb_slot, sw_slot]
    # ball cup + bearing seats (PCB frame)
    cut.append(Pos(bx, by, BALL_Z) * Sphere(CUP_R))
    bearings = []
    rb = BALL_D / 2 + BEARING_D / 2
    for az in BEARING_AZ:
        a, e = math.radians(az), math.radians(BEARING_ELEV)
        p = (bx + rb * math.cos(e) * math.cos(a), by + rb * math.cos(e) * math.sin(a),
             BALL_Z + rb * math.sin(e))
        bearings.append(p)
        cut.append(Pos(*p) * Sphere(BEARING_SEAT_D / 2))
    # bay-lid landings: 2 keyed bores with a magnet pocket at the bottom
    r_leg, z_land = lid_landing()
    for a in LID_LEG_AZ:
        lx, ly = bx + r_leg * math.cos(math.radians(a)), by + r_leg * math.sin(math.radians(a))
        cut.append(Pos(lx, ly, (z_land + FLOOR_TOP + 1) / 2) * Cylinder(LID_BORE_R, FLOOR_TOP + 1 - z_land))
        cut.append(Pos(lx, ly, z_land - LID_MAG_T / 2 + 0.05) * Cylinder(LID_MAG_D / 2, LID_MAG_T + 0.1))
    case = case - fr.T(union_all(cut))

    # ---- desk-frame cuts: sensor window, module pocket, inserts, channel ---
    Cx, Cy, Cz = C
    dcut = []
    win_top = Cz - 6.0
    dcut.append(box_at(Cx, Cy, (win_top + z_mtop) / 2 + 0.05, SENSOR_WINDOW, SENSOR_WINDOW, win_top - z_mtop + 0.1))
    pw = MODULE_W + 2 * MODULE_CLEAR
    dcut.append(box_at(Cx, Cy, (z_mtop - 5) / 2, pw, pw, z_mtop + 5))
    for lx, ly in MODULE_SCREWS:
        dcut.append(Pos(Cx + lx, Cy + ly, z_mtop + INSERT_DEPTH / 2 - 0.05) * Cylinder(INSERT_HOLE_D / 2, INSERT_DEPTH + 0.1))
    jx, jy = h["j1"]
    j_d = fr.to_desk(jx, jy, 0)
    az = math.atan2(j_d[1] - Cy, j_d[0] - Cx)
    # rotate the channel away from the bearings if needed
    bearing_az_d = [math.atan2(fr.to_desk(*b)[1] - Cy, fr.to_desk(*b)[0] - Cx) for b in bearings]
    # keep >= 25 deg from the bearings and >= 34 deg from the lid landing bores
    avoid = [(b, 25.0) for b in bearing_az_d] + [(math.radians(a), 34.0) for a in LID_LEG_AZ]
    angd = lambda x, y: abs((x - y + math.pi) % (2 * math.pi) - math.pi)
    while any(angd(az, b) < math.radians(m) for b, m in avoid):
        az += math.radians(1)
    rc = (WIRE_CH_R0 + WIRE_CH_R1) / 2
    ch_z0, ch_z1 = z_mtop - 0.5, Cz + 4.0
    chan = Pos(Cx + rc * math.cos(az), Cy + rc * math.sin(az), (ch_z0 + ch_z1) / 2) * \
        Rot(0, 0, math.degrees(az)) * Box(WIRE_CH_R1 - WIRE_CH_R0, WIRE_CH_W, ch_z1 - ch_z0)
    dcut.append(chan)
    # magnets on the inner face (axis = desk x)
    mags = []
    ym = (y0 + y1) / 2
    for yy in (ym - (y1 - y0) / 4, ym + (y1 - y0) / 4):
        zd = fr.to_desk(xin, yy, MAG_Z_PCB)[2]
        mags.append((yy, zd))
        dcut.append(Pos(X_in - s * (MAG_T / 2 - 0.05), yy, zd) * Rot(0, 90, 0) * Cylinder(MAG_D / 2, MAG_T + 0.1))
    # bumper recesses
    for bxx, byy in bumpers:
        dcut.append(Pos(bxx, byy, BUMPER_DEPTH / 2 - 0.5) * Cylinder(BUMPER_D / 2, BUMPER_DEPTH + 1.0))
    case = case - union_all(dcut)
    case = Part(case.wrapped) if not isinstance(case, Part) else case

    # ============================ MCU cover ==================================
    led_y = min(p[1] for p in h["leds"])
    # towards the inner edge the box is left open; the case footprint clips it
    cx0, cx1 = sorted((mx - s * COVER_HALF_W, mx + s * 40.0))
    cov = box(cx0, led_y - COVER_LED_MARGIN, cx1, my + COVER_TOP_EXTRA)
    # inner edge flush with the desk-vertical face at the wall top
    zz = WALL_TOP - Z_BOTTOM
    u_face = (s * X_in + zz * math.sin(th)) / math.cos(th)
    x_face = fr.xoc + s * u_face
    footprint_top = unary_union([outer, ext.intersection(
        box(min(xin, x_face), -1e4, max(xin, x_face), 1e4))])
    cov = cov.intersection(footprint_top)
    keycaps2d = unary_union([rect(kx, ky, KEYCAP_W, KEYCAP_H, kr) for kx, ky, kr in h["keys"]])
    cov = cov.difference(keycaps2d.buffer(COVER_KEY_CLEAR)).difference(
        Point(bx, by).buffer(COVER_BALL_CLEAR))
    if isinstance(cov, MultiPolygon):
        cov = max(cov.geoms, key=lambda g: g.area)
    skirt2d = cov.difference(cavity)
    h2 = min(h["holes"], key=lambda p: math.hypot(p[0] - mx, p[1] - my - (-23)))
    screw_post = h2 if cov.buffer(-COVER_POST_D / 2).contains(Point(h2)) else None
    # locating pin: over the PCB, away from the MCU, LEDs, switch and the screw post
    pin_ok = cov.buffer(-2.5).intersection(outline.buffer(-1.5)).difference(unary_union(
        [rect(mx, my, MCU_W + 1, MCU_L + 6)] + [Point(p).buffer(3.0) for p in h["leds"]]
        + [rect(swx, swy, 10, 6)] + ([Point(screw_post).buffer(8)] if screw_post else [])
        ).buffer(COVER_PIN_D / 2 + 0.3))
    pin = None
    if not pin_ok.is_empty:
        ref = screw_post or (mx, my)
        best = None
        for gx in np.arange(cov.bounds[0], cov.bounds[2], 0.5):
            for gy in np.arange(cov.bounds[1], cov.bounds[3], 0.5):
                if pin_ok.contains(Point(gx, gy)):
                    d = math.hypot(gx - ref[0], gy - ref[1])
                    if best is None or d > best[0]:
                        best = (d, gx, gy)
        pin = best[1:] if best else None
    cover = prism(cov, COVER_Z0, COVER_Z0 + COVER_T)
    if not skirt2d.is_empty:
        cover = cover + prism(skirt2d, WALL_TOP, COVER_Z0 + 0.01)
    if screw_post:
        cover = cover + Pos(screw_post[0], screw_post[1], COVER_Z0 / 2 + 0.005) * Cylinder(COVER_POST_D / 2, COVER_Z0 + 0.01)
    if pin:
        cover = cover + Pos(pin[0], pin[1], COVER_Z0 / 2 + 0.005) * Cylinder(COVER_PIN_D / 2, COVER_Z0 + 0.01)
    ccut = [usb_slot, sw_slot] + [Pos(x, y, COVER_Z0 + COVER_T / 2) * Cylinder(LED_HOLE_D / 2, COVER_T + 2) for x, y in h["leds"]]
    if screw_post:
        ccut.append(Pos(screw_post[0], screw_post[1], COVER_Z0 / 2) * Cylinder(COVER_SCREW_D / 2, COVER_Z0 + 2 * COVER_T + 2))
    cover = cover - union_all(ccut)
    cover_desk = fr.T(cover)
    # print orientation: plate top on the bed
    cover_print = Rot(180, 0, 0) * cover
    bb = cover_print.bounding_box()
    cover_print = Pos(-bb.min.X, -bb.min.Y, -bb.min.Z) * cover_print

    # ============================ visuals ====================================
    pcb2d = outline.difference(Point(bx, by).buffer(h["ball_hole_r"]))
    vis = {}
    vis["pcb"] = fr.T(prism(pcb2d, -PCB_T, 0.0))
    vis["keycaps"] = fr.T(union_all(prism(rect(kx, ky, KEYCAP_W, KEYCAP_H, kr), KEYCAP_Z0, KEYCAP_Z1)
                                    for kx, ky, kr in h["keys"]))
    vis["ball"] = Pos(*C) * Sphere(BALL_D / 2)
    mz0, mz1 = MCU_Z[h["side"]]
    vis["mcu"] = fr.T(box_at(mx, my, (mz0 + mz1) / 2, MCU_W, MCU_L, mz1 - mz0))
    vis["bearings"] = fr.T(union_all(Pos(*b) * Sphere(BEARING_D / 2) for b in bearings))
    vis["module"] = union_all([
        box_at(Cx, Cy, z_mtop - MODULE_T / 2, MODULE_W, MODULE_W, MODULE_T),
        box_at(Cx, Cy, z_mtop + LENS_H / 2, 9.0, 9.0, LENS_H),
    ] + [Pos(Cx + lx, Cy + ly, z_mtop - MODULE_T - SCREW_HEAD_H / 2) * Cylinder(1.9, SCREW_HEAD_H)
         for lx, ly in MODULE_SCREWS])
    vis["battery"] = fr.T(box_at(bat["cx"], bat["cy"], FLOOR_TOP - bat["t"] / 2 - 0.1,
                                 bat["pw"] - 2 * BAT_CLEAR if bat["pw"] < bat["pl"] else bat["pw"] - 2 * BAT_CLEAR,
                                 bat["pl"] - 2 * BAT_CLEAR, bat["t"]))
    vis["cover"] = cover_desk

    board_clear, screw_clear = pod_clearance(h, tent)
    info = dict(
        X_in=X_in, ball_desk=C.tolist(), module_top_z=z_mtop,
        pod_clear_board=board_clear, pod_clear_screws=screw_clear,
        battery=bat, magnets=mags, bumpers=bumpers, pin=pin, screw_post=screw_post,
        bearings_pcb=bearings, chan_az_deg=math.degrees(az),
        cup_bottom_to_module=(Cz - CUP_R) - z_mtop,
        insert_floor_min=min(fr.to_desk(x, y, -PCB_T - INSERT_DEPTH)[2] for x, y in h["holes"]),
        reset_foot=reset_foot,
    )
    return dict(case=case, cover_desk=cover_desk, cover_print=cover_print, vis=vis, info=info, frame=fr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def write_stl(shape, path: Path, tol=STL_TOL, ang=STL_ANG):
    """Tessellate with OCC, then drop the odd zero-area sliver triangle OCC
    leaves where a small sphere seat meets a plane, and re-save (binary STL)."""
    import trimesh
    tmp = SCRATCH / ("_raw_" + path.name)
    export_stl(shape, str(tmp), tolerance=tol, angular_tolerance=ang)
    m = trimesh.load(tmp, process=True)
    m.merge_vertices(digits_vertex=4)
    m.update_faces(m.nondegenerate_faces(height=1e-6))
    m.remove_unreferenced_vertices()
    if not m.is_watertight:
        # remove isolated leftovers (single triangles not connected to the body)
        parts = m.split(only_watertight=False) if False else None
        import numpy as np
        from trimesh.grouping import group_rows
        edges = m.edges_sorted
        open_e = group_rows(edges, require_count=1)
        bad_v = set(np.unique(edges[open_e]).tolist())
        keep = [i for i, f in enumerate(m.faces) if not (set(f.tolist()) <= bad_v)]
        m.update_faces(np.array(keep))
        m.remove_unreferenced_vertices()
    m.fix_normals()
    m.export(path)
    return m


# ---------------------------------------------------------------------------
# Bay lids (trackpad / encoder / blank)
# ---------------------------------------------------------------------------
def pad_fit(halves):
    """Largest Cirque pad that clears the neighbouring keycaps in plan view."""
    d_key = min(rect(x, y, KEYCAP_W, KEYCAP_H, r).distance(Point(*h["ball"]))
                for h in halves for x, y, r in h["keys"])
    max_r = d_key - PAD_KEY_CLEAR - PAD_BEZEL
    want_r = PAD_D_WANTED / 2
    pad_d = PAD_D_WANTED if want_r <= max_r else PAD_D_FALLBACK
    return dict(nearest_keycap_mm=d_key, max_pad_d=2 * max_r,
                pad_wanted_overlap_mm=max(0.0, want_r + PAD_BEZEL + PAD_KEY_CLEAR - d_key),
                pad_wanted_edge_overlap_mm=max(0.0, want_r - d_key),
                pad_d=pad_d, lid_to_keycap_mm=d_key - LID_R)


def lid_body(z_top):
    """Common lid body (PCB frame, axis = PCB normal through the bay centre):
    45 deg cone that clears the cup + cylinder in the PCB hole + 2 keyed legs
    with magnet pockets.  Prints upright on the leg / cone bottoms."""
    r_leg, z_land = lid_landing()
    r0 = cup_rim_r() - LID_CONE_CLEAR            # cone radius at the floor level
    z_full = FLOOR_TOP + (LID_R - r0)            # cone reaches LID_R here
    z = FLOOR_TOP
    while z - 0.05 >= z_land:                   # go down while the cone clears the sphere
        zn = z - 0.05
        rc = r0 + (zn - FLOOR_TOP)
        rs = math.sqrt(max(CUP_R ** 2 - (zn - BALL_Z) ** 2, 0.0))
        if rc < 2.0 or rc > rs - LID_CONE_CLEAR:
            break
        z = zn
    if z - z_land < 0.5:                        # snap to the leg plane: one flat bed face
        z = z_land
    z_cb, r_cb = z, r0 + (z - FLOOR_TOP)
    top = max(z_top, z_full) + 1.0
    # 45 deg cone continued upwards, clipped by the lid cylinder (clean edge at z_full)
    body = Pos(0, 0, z_cb) * Cone(r_cb, r_cb + (top - z_cb), top - z_cb, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body & (Pos(0, 0, z_cb - 1) * Cylinder(LID_R, top - z_cb + 2, align=(Align.CENTER, Align.CENTER, Align.MIN)))
    leg_top = min(-PCB_T - 0.4, z_top)
    for a in LID_LEG_AZ:
        lx, ly = r_leg * math.cos(math.radians(a)), r_leg * math.sin(math.radians(a))
        body = body + Pos(lx, ly, z_land) * Cylinder(LID_LEG_R, leg_top - z_land, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body & (Pos(0, 0, z_top - 500) * Box(200, 200, 1000))
    for a in LID_LEG_AZ:
        lx, ly = r_leg * math.cos(math.radians(a)), r_leg * math.sin(math.radians(a))
        body = body - Pos(lx, ly, z_land - 0.1) * Cylinder(LID_MAG_D / 2, LID_MAG_T + 0.1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    return body, dict(z_land=z_land, r_leg=r_leg, cone_bottom_z=z_cb, cone_bottom_r=r_cb, z_top=z_top)


def build_lids(pad_d):
    lids, vis, info = {}, {}, {}
    # (a) trackpad: pad glass flush with the keycap tops
    z_top = KEYCAP_Z1
    pr = pad_d / 2
    body, inf = lid_body(z_top)
    if pr + PAD_BEZEL > LID_R:                  # mushroom head (only for a big pad)
        hr = pr + PAD_BEZEL
        zh = z_top - PAD_T - 1.6
        body = body + Pos(0, 0, zh - (hr - LID_R)) * Cone(LID_R, hr, hr - LID_R, align=(Align.CENTER, Align.CENTER, Align.MIN))
        body = body + Pos(0, 0, zh) * Cylinder(hr, z_top - zh, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body - Pos(0, 0, z_top - PAD_T) * Cylinder(pr + 0.25, PAD_T + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body - Pos(0, 0, inf["z_land"] - 1) * Box(FPC_SLOT[0], FPC_SLOT[1], z_top - inf["z_land"] + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    lids["trackpad"] = body
    vis["trackpad"] = [Pos(0, 0, z_top - PAD_T) * Cylinder(pr, PAD_T, align=(Align.CENTER, Align.CENTER, Align.MIN))]
    info["trackpad"] = dict(inf, pad_d=pad_d, pad_top_z=z_top)

    # (b) EC11 encoder: body hangs into the cup, knob top ~ keycap height
    r_diag = ENC_BODY / 2 * math.sqrt(2) + 0.3
    z_bb = BALL_Z - math.sqrt(max(CUP_R ** 2 - r_diag ** 2, 0.0))
    pb = max(z_bb + ENC_BODY_H, KEYCAP_Z1 - ENC_SHAFT_L - ENC_KNOB_TOP_EXTRA)
    pt = pb + ENC_PANEL_T
    z_top = max(pt, 0.0)
    body, inf = lid_body(z_top)
    if z_top > pt:                              # dish above the panel for the knob
        body = body - Pos(0, 0, pt) * Cylinder(LID_R - 1.6, z_top - pt + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cav = ENC_BODY + 0.4
    body = body - Pos(0, 0, inf["z_land"] - 1) * Rot(0, 0, 45) * Box(cav, cav, pb - inf["z_land"] + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    body = body - Pos(0, 0, pb - 1) * Cylinder(ENC_HOLE_D / 2, ENC_PANEL_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    tw, tl, toff = ENC_TAB
    body = body - Pos(toff * math.cos(math.radians(45)), toff * math.sin(math.radians(45)), pb - 1) * Rot(0, 0, 45) * \
        Box(tl, tw, ENC_PANEL_T + 2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    lids["encoder"] = body
    knob_top = pb + ENC_SHAFT_L + ENC_KNOB_TOP_EXTRA
    vis["encoder"] = [
        Pos(0, 0, pb - ENC_BODY_H) * Rot(0, 0, 45) * Box(ENC_BODY, ENC_BODY, ENC_BODY_H, align=(Align.CENTER, Align.CENTER, Align.MIN)),
        Pos(0, 0, pt) * Cylinder(3.4, 5.0, align=(Align.CENTER, Align.CENTER, Align.MIN)),
        Pos(0, 0, max(pt + 1.0, knob_top - 12.0)) * Cylinder(ENC_KNOB_D / 2, knob_top - max(pt + 1.0, knob_top - 12.0), align=(Align.CENTER, Align.CENTER, Align.MIN)),
    ]
    info["encoder"] = dict(inf, panel_top_z=pt, body_bottom_z=pb - ENC_BODY_H, knob_top_z=knob_top,
                           knob_above_keycaps=knob_top - KEYCAP_Z1)

    # (c) blank
    body, inf = lid_body(BLANK_TOP_Z)
    lids["blank"] = body
    vis["blank"] = []
    info["blank"] = inf
    return lids, vis, info


def lid_print(shape):
    """Upright print orientation: lowest point on the bed."""
    bb = shape.bounding_box()
    return Pos(-(bb.min.X + bb.max.X) / 2, -(bb.min.Y + bb.max.Y) / 2, -bb.min.Z) * shape


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def fmt_t(t):
    return f"{t:g}"


def main():
    import trimesh
    OUT.mkdir(parents=True, exist_ok=True)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    halves = [load_half("left"), load_half("right")]
    variants, defaults = {}, {}
    fit = pad_fit(halves)
    lid_report = {"pad": {k: round(v, 2) for k, v in fit.items()}, "sets": {}}
    for bd in BALL_SIZES:
        set_ball(bd)
        exact, tmin = choose_tent(halves)
        angles = [tmin] + [t for t in TENT_DETENTS if t > tmin]
        vrep = {"min_tent_exact_deg": exact, "min_tent_deg": tmin, "ball_centre_z_pcb": BALL_Z,
                "cup_r": CUP_R, "ring_gap_pcb_top_mm": round(BAY_HOLE_R - math.sqrt(max((BALL_D / 2) ** 2 - BALL_Z ** 2, 0)), 2),
                "ring_gap_equator_mm": round(BAY_HOLE_R - BALL_D / 2, 2), "detents": {}}
        print(f"ball {bd:g}: min tent {exact:.1f} -> {tmin} deg; detents {angles}", flush=True)
        for t in angles:
            dv = {}
            for h in halves:
                side = h["side"]
                r = build_half(h, t)
                name = f"case_{side}_b{bd:g}_t{fmt_t(t)}.stl"
                m = write_stl(r["case"], OUT / name)
                info = r["info"]
                dv[side] = {"file": name, "watertight": bool(m.is_watertight),
                            "min_z": round(float(m.bounds[0][2]), 3),
                            "max_height_mm": round(float(m.bounds[1][2]), 1),
                            "ball_top_mm": round(info["ball_desk"][2] + BALL_D / 2, 1),
                            "volume_cm3": round(m.volume / 1000, 2),
                            "pla_mass_g_solid": round(m.volume / 1000 * PLA_DENSITY, 1),
                            "pod_clear_board_mm": round(info["pod_clear_board"], 2),
                            "pod_clear_screws_mm": round(info["pod_clear_screws"], 2),
                            "battery": info["battery"]["name"]}
                print(f"  t={t}: {side} wt={m.is_watertight} vol={m.volume / 1000:.1f}", flush=True)
                if bd == BALL_DEFAULT and t == tmin:
                    defaults[side] = (h, r, t)
            vrep["detents"][fmt_t(t)] = dv
        variants[f"b{bd:g}"] = vrep

        # lids for this ball size (one set fits both halves)
        lids, lvis, linfo = build_lids(fit["pad_d"])
        lset = {}
        for k, shp in lids.items():
            name = f"lid_{k}_b{bd:g}.stl"
            m = write_stl(lid_print(shp), OUT / name)
            lset[k] = {"file": name, "watertight": bool(m.is_watertight),
                       "volume_cm3": round(m.volume / 1000, 2),
                       **{kk: (round(v, 2) if isinstance(v, float) else v) for kk, v in linfo[k].items()}}
            if bd == BALL_DEFAULT:
                # scratch meshes for renders: lids in their own frame, and on the left half
                export_stl(shp, str(SCRATCH / f"r_lid_{k}.stl"), tolerance=0.03, angular_tolerance=0.15)
                if lvis[k]:
                    export_stl(union_all(lvis[k]), str(SCRATCH / f"r_lidvis_{k}.stl"), tolerance=0.03, angular_tolerance=0.15)
        lid_report["sets"][f"b{bd:g}"] = lset
        if bd == BALL_DEFAULT:
            defaults["lids"] = (lids, lvis)

    # ---- defaults: b25 at its minimum tent (STEP + cover + render meshes) --
    set_ball(BALL_DEFAULT)
    results = {}
    for side in ("left", "right"):
        h, r, t = defaults[side]
        results[side] = r
        export_step(r["case"], str(OUT / f"case_{side}.step"))
        write_stl(r["case"], OUT / f"case_{side}.stl")
        write_stl(r["cover_print"], OUT / f"mcu_cover_{side}.stl")
        export_step(r["cover_print"], str(OUT / f"mcu_cover_{side}.step"))
        write_stl(r["case"], SCRATCH / f"r_case_{side}.stl", 0.08, 0.3)
        for k, v in r["vis"].items():
            fine = k in ("ball", "bearings")
            export_stl(v, str(SCRATCH / f"r_{k}_{side}.stl"), tolerance=0.01 if fine else 0.08,
                       angular_tolerance=0.08 if fine else 0.3)
        # trackpad lid installed (desk frame)
        lids, lvis = defaults["lids"]
        bx, by = h["ball"]
        fr = r["frame"]
        export_stl(fr.T(Pos(bx, by, 0) * lids["trackpad"]), str(SCRATCH / f"r_lidtp_{side}.stl"), tolerance=0.05, angular_tolerance=0.2)
        export_stl(fr.T(Pos(bx, by, 0) * union_all(lvis["trackpad"])), str(SCRATCH / f"r_pad_{side}.stl"), tolerance=0.05, angular_tolerance=0.2)
    tent = defaults["left"][2]
    report = build_report(halves, results, tent)
    report["variants"] = variants
    report["lids"] = lid_report
    (OUT / "case_report.json").write_text(json.dumps(report, indent=2, default=float))
    (SCRATCH / "layout.json").write_text(json.dumps(
        {s: results[s]["info"] for s in results}, indent=2, default=float))
    print(json.dumps({"variants": variants, "lids": lid_report}, indent=1, default=float)[:4000])


def build_report(halves, results, tent):
    import trimesh
    rep = {"tent_deg": tent, "tent_deg_requested": TENT_DEG_MIN, "ball_d": BALL_DEFAULT,
           "default_files": "case_{left,right}.stl/.step = b25 at its minimum tent",
           "frame": "desk frame, z=0 is the desk / print bed",
           "density_g_cm3": PLA_DENSITY,
           "mass_note": "solid-model mass (100 % infill); a 4-wall / 20 % infill print is roughly 55-65 % of it",
           "notes": [
               f"default tent raised from {TENT_DEG_MIN} to {tent} deg so the sensor module and its screw heads clear the desk by >= {POD_MIN_CLEAR} mm",
               "sensor axis is desk-vertical (tent angle off the PCB normal) so the module pocket ceiling prints as a flat bridge; lens gap unchanged",
               "sensor module pocket is open to the underside (module is screwed up into 2 M2 heat-set inserts)",
               "light-weighting = open-top wells under the tray floor (rib grid), printable without supports",
               "MCU cover plate underside at z=+5.6 (PCB frame) for both halves: clears the right nice!nano on 2 mm spacers",
               "the pod has 2 keyed landing bores (+ 5x2 magnet pockets) at 120/240 deg for the bay lids",
           ],
           "halves": {}}
    for h in halves:
        side = h["side"]
        r = results[side]
        info = r["info"]
        m = trimesh.load(OUT / f"case_{side}.stl")
        c = trimesh.load(OUT / f"mcu_cover_{side}.stl")
        ball_top = info["ball_desk"][2] + BALL_D / 2
        keycap_top = r["vis"]["keycaps"].bounding_box().max.Z
        ext = m.bounds[1] - m.bounds[0]
        bat = info["battery"]
        rep["halves"][side] = {
            "pcb_file": h["pcb_file"],
            "case_dims_mm": {"x": round(ext[0], 1), "y": round(ext[1], 1), "z": round(ext[2], 1)},
            "case_max_height_mm": round(float(m.bounds[1][2]), 1),
            "assembly_max_height_mm (ball top)": round(ball_top, 1),
            "keycap_top_max_mm": round(keycap_top, 1),
            "case_min_z_mm": round(float(m.bounds[0][2]), 3),
            "ball_centre_desk_mm": [round(v, 2) for v in info["ball_desk"]],
            "pod_min_clearance_to_desk_mm": {
                "sensor_board_bottom": round(info["pod_clear_board"], 2),
                "module_screw_heads": round(info["pod_clear_screws"], 2)},
            "cup_bottom_to_module_top_mm": round(info["cup_bottom_to_module"], 2),
            "insert_hole_bottom_min_z_mm": round(info["insert_floor_min"], 2),
            "battery": {"model": bat["name"], "size_mm": [bat["t"], bat["w"], bat["l"]],
                        "typical_mAh": bat["mah"],
                        "pocket_mm": [round(bat["pw"], 1), round(bat["pl"], 1), round(bat["depth"], 1)],
                        "pocket_centre_pcb_kicad": [round(bat["cx"], 2), round(-bat["cy"], 2)],
                        "floor_below_pocket_min_mm": round(bat["floor_below"], 2)},
            "magnets_y_zdesk_mm": [[round(-a, 2), round(b, 2)] for a, b in info["magnets"]],
            "inner_face_x_desk_mm": round(info["X_in"], 3),
            "volumes_cm3": {"case": round(m.volume / 1000, 2), "mcu_cover": round(c.volume / 1000, 2)},
            "pla_mass_g_solid": {"case": round(m.volume / 1000 * PLA_DENSITY, 1),
                                 "mcu_cover": round(c.volume / 1000 * PLA_DENSITY, 1)},
            "watertight": {"case": bool(m.is_watertight), "mcu_cover": bool(c.is_watertight)},
        }
    return rep


if __name__ == "__main__":
    sys.exit(main())
