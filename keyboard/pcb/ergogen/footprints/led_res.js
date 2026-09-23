// 0603 status LED + 0603 series resistor (front side, shines through a light pipe)
// net chain: GPIO -> R -> LED anode ; LED cathode -> GND
module.exports = {
  params: {
    designator: 'LED',
    gpio: undefined,
    mid: undefined,
    GND: {type: 'net', value: 'GND'}
  },
  body: p => `
  (module LED_R_0603_pair (layer F.Cu) (tedit 5B24D78E)
    ${p.at}
    (fp_text reference "${p.ref}" (at 0 -1.6) (layer F.SilkS) ${p.ref_hide} (effects (font (size 0.7 0.7) (thickness 0.1))))
    (fp_text value "" (at 0 1.6) (layer F.Fab) hide (effects (font (size 0.7 0.7) (thickness 0.1))))
    (fp_line (start -3.4 -0.9) (end 3.4 -0.9) (layer F.CrtYd) (width 0.05))
    (fp_line (start 3.4 -0.9) (end 3.4 0.9) (layer F.CrtYd) (width 0.05))
    (fp_line (start 3.4 0.9) (end -3.4 0.9) (layer F.CrtYd) (width 0.05))
    (fp_line (start -3.4 0.9) (end -3.4 -0.9) (layer F.CrtYd) (width 0.05))
    (fp_line (start 3.3 -0.8) (end 3.3 0.8) (layer F.SilkS) (width 0.12))
    ${''/* resistor */}
    (pad 1 smd roundrect (at -2.575 0 ${p.r}) (size 0.8 0.95) (layers F.Cu F.Paste F.Mask) (roundrect_rratio 0.25) ${p.gpio})
    (pad 2 smd roundrect (at -1.025 0 ${p.r}) (size 0.8 0.95) (layers F.Cu F.Paste F.Mask) (roundrect_rratio 0.25) ${p.mid})
    ${''/* LED: 3 anode, 4 cathode */}
    (pad 3 smd roundrect (at 1.025 0 ${p.r}) (size 0.8 0.95) (layers F.Cu F.Paste F.Mask) (roundrect_rratio 0.25) ${p.mid})
    (pad 4 smd roundrect (at 2.575 0 ${p.r}) (size 0.8 0.95) (layers F.Cu F.Paste F.Mask) (roundrect_rratio 0.25) ${p.GND})
  )
  `
}
