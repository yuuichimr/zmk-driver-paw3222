// M2 mounting hole (plated, tied to nothing)
module.exports = {
  params: {
    designator: 'H'
  },
  body: p => `
  (module MountingHole_2.2mm_M2 (layer F.Cu) (tedit 5B24D78E)
    ${p.at}
    (fp_text reference "${p.ref}" (at 0 -3) (layer F.SilkS) hide (effects (font (size 0.8 0.8) (thickness 0.12))))
    (fp_text value "" (at 0 3) (layer F.Fab) hide (effects (font (size 0.8 0.8) (thickness 0.12))))
    (fp_circle (center 0 0) (end 2.2 0) (layer F.CrtYd) (width 0.05))
    (pad "" np_thru_hole circle (at 0 0) (size 2.2 2.2) (drill 2.2) (layers *.Cu *.Mask))
  )
  `
}
