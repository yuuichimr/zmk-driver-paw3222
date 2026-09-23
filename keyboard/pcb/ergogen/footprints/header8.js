// 1x8 2.54 mm header: the MODULE BAY connector.
// 1 GND | 2 VCC (switched ext-power 3V3) | 3 SCK / ENC_A | 4 SDIO / ENC_B
// 5 NCS | 6 MOTION | 7 COL (bay key column) | 8 KEY (bay key, diode on main PCB)
module.exports = {
  params: {
    designator: 'J',
    P1: {type: 'net', value: 'GND'},
    P2: {type: 'net', value: 'VCC'},
    P3: {type: 'net', value: 'MOD_SCK'},
    P4: {type: 'net', value: 'MOD_SDIO'},
    P5: {type: 'net', value: 'MOD_NCS'},
    P6: {type: 'net', value: 'MOD_MOTION'},
    P7: {type: 'net', value: 'MOD_COL'},
    P8: {type: 'net', value: 'MOD_KEY'}
  },
  body: p => {
    const labels = ['GND', 'VCC', 'SCK', 'SDIO', 'NCS', 'MOT', 'COL', 'KEY']
    const nets = [p.P1, p.P2, p.P3, p.P4, p.P5, p.P6, p.P7, p.P8]
    let pads = ''
    for (let i = 0; i < 8; i++) {
      const x = (i - 3.5) * 2.54
      const shape = i == 0 ? 'rect' : 'oval'
      pads += `(pad ${i + 1} thru_hole ${shape} (at ${x.toFixed(3)} 0 ${p.r}) (size 1.7 1.7) (drill 1.0) (layers *.Cu *.Mask) ${nets[i]})\n`
      pads += `(fp_text user "${labels[i]}" (at ${x.toFixed(3)} 2.2 ${p.r + 90}) (layer F.SilkS) (effects (font (size 0.8 0.8) (thickness 0.12)) (justify right)))\n`
    }
    return `
  (module MODULE_BAY_1x08 (layer F.Cu) (tedit 5B24D78E)
    ${p.at}
    (fp_text reference "${p.ref}" (at 0 -2) (layer F.SilkS) ${p.ref_hide} (effects (font (size 0.8 0.8) (thickness 0.12))))
    (fp_text value "MODULE_BAY" (at 0 -2) (layer F.Fab) hide (effects (font (size 0.8 0.8) (thickness 0.12))))
    (fp_line (start -10.3 -1.4) (end 10.3 -1.4) (layer F.CrtYd) (width 0.05))
    (fp_line (start 10.3 -1.4) (end 10.3 1.4) (layer F.CrtYd) (width 0.05))
    (fp_line (start 10.3 1.4) (end -10.3 1.4) (layer F.CrtYd) (width 0.05))
    (fp_line (start -10.3 1.4) (end -10.3 -1.4) (layer F.CrtYd) (width 0.05))
    ${pads}
  )
  `
  }
}
