// Browser entry point: render window.JOB into the canvas and report through window.RESULT.
import { renderEntity } from './entity.js'
import { renderIcons } from './items.js'
import { renderStructure } from './structure.js'

const canvas = document.getElementById('c')
const job = window.JOB
const run = { entity: renderEntity, icons: renderIcons, structure: renderStructure }[job.kind]
run(job, canvas)
  .then(info => { window.RESULT = info.pngs ? { ok: true, ...info } : { ok: true, info, png: canvas.toDataURL('image/png') } })
  .catch(e => { window.RESULT = { ok: false, error: String(e.stack || e) } })
