// LiPo battery solder pads (B+ / B-), back side
module.exports = {
  params: {
    designator: 'BT',
    pos: {type: 'net', value: 'BAT_P'},
    neg: {type: 'net', value: 'GND'}
  },
  body: p => `
  (module BATTERY_PADS (layer B.Cu) (tedit 5B24D78E)
    ${p.at}
    (fp_text reference "${p.ref}" (at 0 2.6) (layer B.SilkS) ${p.ref_hide} (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (fp_text value "" (at 0 0) (layer B.Fab) hide (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (fp_text user "B+" (at -2 -2.4 ${p.r}) (layer B.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (fp_text user "B-" (at 2 -2.4 ${p.r}) (layer B.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (pad 1 smd rect (at -2 0 ${p.r}) (size 2.5 3) (layers B.Cu B.Mask) ${p.pos})
    (pad 2 smd rect (at 2 0 ${p.r}) (size 2.5 3) (layers B.Cu B.Mask) ${p.neg})
  )
  `
}
