// Browser entry point: render window.JOB into the canvas and report through window.RESULT.
import { renderEntity } from './entity.js'
import { renderStructure } from './structure.js'

const canvas = document.getElementById('c')
const job = window.JOB
const run = job.kind === 'entity' ? renderEntity : renderStructure
run(job, canvas)
  .then(info => { window.RESULT = { ok: true, info, png: canvas.toDataURL('image/png') } })
  .catch(e => { window.RESULT = { ok: false, error: String(e.stack || e) } })
