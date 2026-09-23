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
| Ball | Ø25, centre z = -2.5, top z = +10; cup R13.2; 3 × Ø3 bearings, 35° below the equator |
| Sensor | 10×10 window, 21×21 module pocket open to the underside, lens gap 2.4, 2 × M2 insert |
| Battery | largest LiPo that fits: **803040** (8×30×40, ~1000 mAh), pocket 31×41×8.5 |
| Magnets | 2 × Ø6×3 per half, on the desk-vertical inner face, z = 13.15 mm |
| Size per half | 144.8 × 101.9 × 32.0 mm (ball top at 34.4 mm) |

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
| 1 | LiPo 803040 (any smaller one also fits) |

## Notes / 注意

* The sensor looks straight up relative to the desk, which is 9.5° off the PCB normal. This lets its pocket print without supports. The lens gap stays 2.4 mm, and the tilt scales one axis by about 1.4 %.
* The USB-C slot (12×7) and the switch slot (8×4) overlap, so they form one opening.
* The reset pin-hole (Ø2) runs along the PCB normal, through the wedge to the underside.
* A 4 × 3.7 mm wire channel leads from the sensor pocket up beside the ball to J1.
* The underside of the cover is 5.6 mm above the PCB. A tall 2.54 mm pin header on J1 would hit it: solder the wires directly or use a low-profile header.
