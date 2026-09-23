# Tsumugi case / ケース

Parametric build123d model of Tsumugi's 3D-printable tented case. Each half is built from its own PCB geometry, so the right half is a separate build, not a mirror of the left.
build123d によるパラメトリックなテント付きケースです。左右それぞれを自分の PCB データから生成します（右は左のミラーではありません）。

```
/opt/tv/bin/pip install build123d trimesh rtree networkx
/opt/tv/bin/python case.py     # -> output/*.step, *.stl, case_report.json
/opt/tv/bin/python render.py   # -> output/render_*.png
```

Inputs: `../pcb/output/geometry_{left,right}.json` and `../pcb/output/tsumugi_{left,right}.kicad_pcb`. The build reads the positions of the mounting holes H1-H5, the power switch, the reset button and LED1-3 from the PCB files.

## Parameters / 主なパラメータ（`case.py` の先頭）

| | value |
|---|---|
| Tent angle / テント角 | **9.5°** (requested 8°; the build raises it automatically until the sensor module clears the desk / センサーが机に当たらない角度まで自動で上げます) |
| Floor top / wall / wall top | z = -3.8 / 2.2 mm (+0.5 clearance) / z = +2.5 (PCB frame) |
| Min. floor & wall | 1.6 mm |
| Ball | `BALL_SIZES = (25, 19)`. Ø25: centre z = -2.5, cup R13.2. Ø19: centre z = +0.5, cup R10.2. The ball top is always 2 mm above the keycap tops (+10). 3 × Ø3 bearings, 35° below the equator |
| Sensor | 10×10 window, 21×21 module pocket open to the underside, lens gap 2.4, 2 × M2 insert at (±8.5, 0) |
| Battery | largest LiPo that fits: **803040** (8×30×40, ~1000 mAh), pocket 31×41×8.5 |
| Magnets | 2 × Ø6×3 per half, on the desk-vertical inner face, z = 13.15 mm |
| Size per half | 144.8 × 101.9 × 32.0 mm (ball top at 34.4 mm) |

### Tent detents / テント角のバリエーション (Kobito-key 風の「角度を印刷で選ぶ」方式)

The tent angle is set by the printed wedge. Pick the file for the angle you want: `case_{left,right}_b{25|19}_t{angle}.stl`. The minimum angle is computed so that the sensor module's screw heads clear the desk by at least 1 mm, then rounded up to 0.5°.
テント角はケース自体で決まります。好きな角度の STL を選んで印刷してください。

| ball | tent | case height | ball top | volume (solid mass) |
|---|---|---|---|---|
| 25 | **9.5° (min)** = `case_{left,right}.stl` | 32.0 | 34.4 | 100 cm³ (124 g) |
| 25 | 14° | 43.3 | 43.3 | 137 cm³ (170 g) |
| 25 | 18° | 53.2 | 51.0 | 167 cm³ (207 g) |
| 19 | **6.5° (min)** | 24.4 | 28.4 | 75 cm³ (93 g) |
| 19 | 14° | 43.3 | 43.2 | 137 cm³ (170 g) |
| 19 | 18° | 53.2 | 50.8 | 168 cm³ (208 g) |

With the 19 mm ball, the 28 mm PCB hole leaves a 4.5 mm ring gap. That is fine: the ball rests on the bearings, not on the PCB. The 25 mm ball leaves 1.75 mm.
19 mm ボールでも PCB 穴は 28 mm のままです（隙間 4.5 mm、ボールはベアリングで支持）。

Only the defaults (b25 at 9.5°) are also written as STEP files.

### Bay lids / ベイ用フタ (`lid_{trackpad,encoder,blank}_b{25|19}.stl`)

One set of lids fits both halves; use the `b25` or `b19` set to match the pod. Each lid drops through the 28 mm PCB hole (lid Ø27.4). It rests on 2 keyed legs that sit in 2 landing bores in the pod, at 120° and 240°. A 5×2 mm magnet in each leg and in each landing holds the lid. The legs also stop it from turning. Below the legs, a 45° cone clears the cup. Lids print upright with no supports; the encoder panel is a short bridge.
フタは左右共通。脚2本（キー兼用）と 5×2 mm 磁石で固定。サポート不要。

* **Trackpad:** the pad surface is flush with the keycap tops (+8.0). **A 35 mm TM035035 collides with the thumb keycaps:** the nearest keycap edge is 15.25 mm from the bay centre, so the pad edge would overlap by 2.25 mm (3.55 mm with the bezel and clearance). The largest pad that fits is Ø27.9, so the lid uses a **Cirque TM023023 (23 mm)**. The FPC leaves through a 12×3 slot. The lid clears the keycaps by 1.55 mm.
  35 mm パッドは親指キーと干渉するため 23 mm (TM023023) を採用。
* **Encoder:** EC11 with a 15 mm shaft, 7 mm panel hole and an anti-rotation slot (check the slot position against your datasheet). The body hangs into the cup. With the b25 set the knob top is at +10.2, 2.2 mm above the keycaps. With the b19 set the shallow cup forces the knob top up to +17.8: use a shorter shaft or a low knob. Remove the sensor module when using this lid, because the EC11 pins reach into the sensor window.
* **Blank:** flat cap, flush with the PCB top.

Frames: the PCB frame has z = 0 at the PCB top. The **desk frame** is the frame of every exported case, with z = 0 at the desk (the print bed).
座標系：出力されるケースはすべて机面（造形面）が z = 0 です。

## Printing / 印刷

* PLA or PETG, 0.2 mm layers, 4 perimeters (1.6 mm), 15-20 % gyroid infill.
* **Case:** print as exported, bottom on the bed, **no supports**. The overhangs are the 9.5° tilted walls, the Ø6 magnet holes and one flat 21.6 mm bridge over the sensor pocket (turn on bridge settings).
  ケースはそのままの向きで、サポートなしで印刷できます。
* **MCU cover:** exported plate-down, with the posts and skirt facing up; no supports.
* Solid mass is about 125 g per case. With the settings above a print weighs roughly 70-80 g.

## BOM (per half, ×2 for the set) / 部品表（片側）

| qty | part |
|---|---|
| 7 | M2 heat-set insert, OD 3.2 × L 4 (5 for the PCB, 2 for the sensor) |
| 4 | M2 × 5 button head (PCB → insert) |
| 1 | M2 × 12 (MCU cover → post → PCB → insert at H2) |
| 2 | M2 × 4 button head (sensor module → insert, from below) |
| 3 | Ø3 mm Si3N4 or ZrO2 ball (press-fit) |
| 1 | 25 mm trackball |
| 2 | Ø6 × 3 mm N52 disc magnet. Glue in with CA. The **left half faces N outward, the right half faces S outward** / 左右で極性を逆に |
| 4 | Ø10 mm silicone bumper (0.8 mm recess) |
| 2 (+2 per lid) | Ø5 × 2 mm disc magnet for the bay lid (pod landing + lid leg) |
| opt. | Cirque TM023023 trackpad / EC11 (15 mm shaft) + knob Ø ≤ 18 |
| 1 | LiPo 803040 (any smaller one also fits) |

## Notes / 注意

* The sensor looks straight up relative to the desk, which is 9.5° off the PCB normal. This lets its pocket print without supports. The lens gap stays 2.4 mm, and the tilt scales one axis by about 1.4 %.
* The USB-C slot (12×7) and the switch slot (8×4) overlap, so they form one opening.
* The reset pin-hole (Ø2) runs along the PCB normal, through the wedge to the underside.
* A 4 × 3.7 mm wire channel leads from the sensor pocket up beside the ball to J1.
* The underside of the cover is 5.6 mm above the PCB. A tall 2.54 mm pin header on J1 would hit it: solder the wires directly or use a low-profile header.
