// Renders jobs in headless Chromium (WebGL through SwiftShader, so every machine draws the same
// pixels). Called by tools/render.py, which decides what needs rendering and post-processes.
//   node tools/render/render.mjs <jobs.json> <out dir>
// jobs.json: [{ "name": "...", "kind": "structure" | "entity", ... }]; writes <out dir>/<name>.png
// and prints one JSON line per job. Assets are served from source/ with the resource pack over
// vanilla, the way the game layers them.
import fs from 'node:fs'
import path from 'node:path'
import * as esbuild from 'esbuild'
import { chromium } from 'playwright-core'

const HERE = path.dirname(new URL(import.meta.url).pathname)
const ROOT = path.resolve(HERE, '../..')
const SRC = `${ROOT}/source`
const PACK = `${SRC}/matcha-flavoured/MF_resourcepack/assets`
const VANILLA = `${SRC}/vanilla-assets/assets`
const DATA = [`${SRC}/matcha-flavoured/MF_datapack/data`, `${SRC}/vanilla-data/data`]
// entity textures deepslate's special block renderers draw with (chests, beds, signs, skulls...)
const ENTITY_DIRS = ['chest', 'bed', 'bell', 'signs', 'banner', 'decorated_pot', 'shulker', 'conduit', 'skeleton', 'zombie', 'creeper', 'piglin', 'enderdragon', 'player']

const [jobsFile, outDir] = process.argv.slice(2)
const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8'))
fs.mkdirSync(outDir, { recursive: true })

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out
  for (const e of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => (a.name < b.name ? -1 : 1))) {
    const p = path.join(dir, e.name)
    e.isDirectory() ? walk(p, out) : out.push(p)
  }
  return out
}
// id -> file for everything under assets/<ns>/<sub>, the pack winning over vanilla
function collect(sub, ext, keep = () => true) {
  const map = {}
  for (const root of [VANILLA, PACK]) {
    for (const ns of fs.existsSync(root) ? fs.readdirSync(root).sort() : []) {
      const base = path.join(root, ns, sub)
      for (const f of walk(base)) {
        if (!f.endsWith(ext)) continue
        const rel = path.relative(base, f).slice(0, -ext.length)
        if (keep(rel)) map[`${ns}:${rel}`] = f
      }
    }
  }
  return map
}
const firstExisting = files => files.find(f => fs.existsSync(f))
const idPath = id => (id.includes(':') ? id.split(':') : ['minecraft', id])
const readJson = f => JSON.parse(fs.readFileSync(f, 'utf8'))

const blockstates = collect('blockstates', '.json')
const models = collect('models', '.json', r => r.startsWith('block/'))
const atlasTextures = collect('textures', '.png', r => r.startsWith('block/') || ENTITY_DIRS.some(d => r.startsWith(`entity/${d}/`)))
// Minecraft 26 moved sign textures to block/<wood>_sign and block/<wood>_hanging_sign; deepslate still
// asks for entity/signs/<wood> and entity/signs/hanging/<wood>
for (const [id, f] of Object.entries(atlasTextures)) {
  const m = id.match(/^(\w+):block\/(\w+?)_(hanging_)?sign$/)
  if (m) atlasTextures[`${m[1]}:entity/signs/${m[3] ? 'hanging/' : ''}${m[2]}`] ??= f
}

// template location -> the processors of the first pool element that places it
const poolProcessors = {}
for (const dir of DATA) for (const f of walk(dir).filter(f => f.includes('/worldgen/template_pool/') && f.endsWith('.json'))) {
  for (const e of readJson(f).elements ?? []) {
    for (const x of e.element.elements ?? [e.element]) if (x.location) poolProcessors[x.location.includes(':') ? x.location : 'minecraft:' + x.location] ??= x.processors ?? []
  }
}
const resolveProcessors = p => {
  if (typeof p === 'string') {
    const [ns, name] = idPath(p)
    const f = firstExisting(DATA.map(d => `${d}/${ns}/worldgen/processor_list/${name}.json`))
    p = f ? readJson(f) : []
  }
  return Array.isArray(p) ? p : p?.processors ?? []
}

const cache = {}
const once = (k, fn) => (cache[k] ??= JSON.stringify(fn()))
const assets = {
  '/asset/blockstates': () => once('bs', () => Object.fromEntries(Object.entries(blockstates).map(([k, f]) => [k, readJson(f)]))),
  '/asset/models': () => once('m', () => Object.fromEntries(Object.entries(models).map(([k, f]) => { try { return [k, readJson(f)] } catch { return [k, null] } }).filter(([, v]) => v))),
  '/asset/textures': () => once('t', () => Object.keys(atlasTextures).sort()),
  '/asset/blocks': () => once('b', () => readJson(`${SRC}/vanilla-summary/blocks/data.min.json`)),
}
function serve(p) {
  if (assets[p]) return { body: assets[p](), type: 'application/json' }
  if (p.startsWith('/asset/pool-processors/')) return { body: JSON.stringify(resolveProcessors(poolProcessors[p.slice(23)])), type: 'application/json' }
  let f, type = 'application/json'
  if (p.startsWith('/tex/')) {  // any texture by id, pack first
    const [ns, name] = idPath(p.slice(5)); type = 'image/png'
    f = atlasTextures[`${ns}:${name}`] ?? firstExisting([PACK, VANILLA].map(r => `${r}/${ns}/textures/${name}.png`))
  } else if (p.startsWith('/texmeta/')) {  // a texture's .mcmeta (villager hats), pack first
    const [ns, name] = idPath(p.slice(9))
    f = firstExisting([PACK, VANILLA].map(r => `${r}/${ns}/textures/${name}.png.mcmeta`))
  } else if (p.startsWith('/equip/')) {
    const [ns, name] = idPath(p.slice(7))
    f = firstExisting([PACK, VANILLA].map(r => `${r}/${ns}/equipment/${name}.json`))
  } else if (p.startsWith('/wg/')) {  // /wg/<kind>/<ns:path>: worldgen json, pack first
    const rest = p.slice(4), kind = rest.slice(0, rest.indexOf('/')), [ns, name] = idPath(rest.slice(kind.length + 1))
    f = firstExisting(DATA.map(d => `${d}/${ns}/worldgen/${kind}/${name}.json`))
  } else if (p.startsWith('/nbt/')) {  // /nbt/<ns>/structure/<path>.nbt
    type = 'application/octet-stream'
    f = firstExisting(DATA.map(d => path.join(d, p.slice(5))))
  }
  return f ? { body: fs.readFileSync(f), type } : null
}

const bundle = (await esbuild.build({ entryPoints: [`${HERE}/src/page.js`], bundle: true, format: 'iife', write: false, logLevel: 'warning' })).outputFiles[0].text

function chromiumPath() {
  if (process.env.MFW_CHROMIUM) return process.env.MFW_CHROMIUM
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, `${process.env.HOME}/.cache/ms-playwright`, `${process.env.HOME}/Library/Caches/ms-playwright`].filter(Boolean)
  for (const r of roots) {
    if (!fs.existsSync(r)) continue
    for (const d of fs.readdirSync(r).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()) {
      const exe = firstExisting([`${r}/${d}/chrome-linux/chrome`, `${r}/${d}/chrome-linux64/chrome`,
        `${r}/${d}/chrome-mac/Chromium.app/Contents/MacOS/Chromium`, `${r}/${d}/chrome-mac-arm64/Chromium.app/Contents/MacOS/Chromium`])
      if (exe) return exe
    }
  }
  // an installed Chrome or Chromium (CI runners set CHROME_BIN)
  return firstExisting([process.env.CHROME_BIN, '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium'].filter(Boolean))
}

const browser = await chromium.launch({
  executablePath: chromiumPath(),
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--js-flags=--max-old-space-size=6144'],
})
const page = await browser.newPage()
let current
await page.route('http://render.local/**', route => {
  const p = decodeURIComponent(new URL(route.request().url()).pathname)
  if (p === '/') {
    const html = `<!doctype html><body style="margin:0"><canvas id="c"></canvas><script>window.JOB=${JSON.stringify(current)}</script><script>${bundle}</script>`
    return route.fulfill({ body: html, contentType: 'text/html' })
  }
  const r = serve(p)
  return r ? route.fulfill({ body: r.body, contentType: r.type }) : route.fulfill({ status: 404, body: '' })
})
let failed = 0
for (const job of jobs) {
  current = job
  await page.goto('http://render.local/')
  await page.waitForFunction(() => window.RESULT, null, { timeout: 600000 })
  const res = await page.evaluate(() => window.RESULT)
  if (!res.ok) { failed++; console.log(JSON.stringify({ name: job.name, error: res.error })); continue }
  fs.writeFileSync(path.join(outDir, job.name + '.png'), Buffer.from(res.png.split(',')[1], 'base64'))
  console.log(JSON.stringify({ name: job.name, ...res.info }))
}
await browser.close()
process.exit(failed ? 1 : 0)
