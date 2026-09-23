// SOD-123 diode on the back side (hand-solderable, 1N4148W)
// from = anode, to = cathode (square pad)
module.exports = {
  params: {
    designator: 'D',
    from: undefined,
    to: undefined
  },
  body: p => `
  (module D_SOD-123_Back (layer B.Cu) (tedit 5B24D78E)
    ${p.at}
    (fp_text reference "${p.ref}" (at 0 1.8) (layer B.SilkS) ${p.ref_hide} (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (fp_text value "1N4148W" (at 0 -1.8) (layer B.Fab) hide (effects (font (size 0.8 0.8) (thickness 0.12)) (justify mirror)))
    (fp_line (start 2.4 -0.9) (end 2.4 0.9) (layer B.SilkS) (width 0.12))
    (fp_line (start 2.4 0.9) (end -1.6 0.9) (layer B.SilkS) (width 0.12))
    (fp_line (start 2.4 -0.9) (end -1.6 -0.9) (layer B.SilkS) (width 0.12))
    (fp_line (start -2.6 -1.15) (end 2.6 -1.15) (layer B.CrtYd) (width 0.05))
    (fp_line (start 2.6 -1.15) (end 2.6 1.15) (layer B.CrtYd) (width 0.05))
    (fp_line (start 2.6 1.15) (end -2.6 1.15) (layer B.CrtYd) (width 0.05))
    (fp_line (start -2.6 1.15) (end -2.6 -1.15) (layer B.CrtYd) (width 0.05))
    (pad 1 smd rect (at 1.65 0 ${p.r}) (size 1.2 1.2) (layers B.Cu B.Paste B.Mask) ${p.to})
    (pad 2 smd rect (at -1.65 0 ${p.r}) (size 1.2 1.2) (layers B.Cu B.Paste B.Mask) ${p.from})
  )
  `
}
