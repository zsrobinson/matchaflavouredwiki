// Structure renders with deepslate: one template, several stacked templates (a list pool element),
// or a whole jigsaw structure assembled by jigsaw.js. Placement does what the game does: jigsaw
// blocks become their final_state, structure voids vanish, and the template pool's processors run.
import { BlockColors, BlockDefinition, BlockModel, Identifier, NbtFile, Structure, StructureRenderer } from 'deepslate'
import { mat4, vec3 } from 'gl-matrix'
import { assemble, rotPos, rotProps } from './jigsaw.js'

const getJson = async u => { const r = await fetch(u); if (!r.ok) throw new Error('missing ' + u); return r.json() }
const nsid = s => (s.includes(':') ? s : 'minecraft:' + s)
// never placed: air, structure voids, and the structure blocks templates use as data markers
const AIR = /:(air|cave_air|void_air|structure_void|structure_block)$/
const FLAT_HEIGHT = 64  // renders have no terrain: the ground is flat, its top block at y=63

// Blocks drawn see-through or cut out (the models don't say; the game hard-codes it).
const TRANSLUCENT = /glass|ice$|^minecraft:water$|slime_block|honey_block/
const CUTOUT = /glass|leaves|ice|slime|honey|spawner|barrier|mangrove_roots|beacon|grate|copper_bulb|vault|trial_spawner/

async function loadImage(url) {
  const r = await fetch(url)
  if (!r.ok) return null
  return createImageBitmap(await r.blob())
}

// Texture atlas: every block texture plus the entity textures deepslate's special renderers use
// (chests, beds, signs...). Packed in sorted order so the output is the same on every run.
async function buildAtlas(ids) {
  const imgs = []
  for (const id of ids) {
    const bmp = await loadImage('/tex/' + id)
    if (!bmp) continue
    const entity = id.includes(':entity/')
    imgs.push({ id, bmp, w: bmp.width, h: entity ? bmp.height : Math.min(bmp.height, bmp.width) })  // first animation frame
  }
  imgs.sort((a, b) => b.h - a.h || b.w - a.w || (a.id < b.id ? -1 : 1))
  const W = 4096
  const canvas = new OffscreenCanvas(W, W)
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#f0f'; ctx.fillRect(0, 0, 16, 16)  // "missing texture" at 0,0
  let x = 16, y = 0, rowH = 16
  const uv = {}
  for (const im of imgs) {
    if (x + im.w > W) { x = 0; y += rowH; rowH = im.h }
    ctx.drawImage(im.bmp, 0, 0, im.w, im.h, x, y, im.w, im.h)
    uv[im.id] = [x / W, y / W, (x + im.w) / W, (y + im.h) / W]
    x += im.w; rowH = Math.max(rowH, im.h)
  }
  return { image: ctx.getImageData(0, 0, W, W), uv, size: W }
}

// Grass, foliage and water colours for a biome, from the pack's colour maps (as the game samples them).
async function biomeTint(biomeId) {
  const b = await getJson('/wg/biome/' + nsid(biomeId))
  const sample = async (map, t, d) => {
    const bmp = await loadImage(`/tex/minecraft:colormap/${map}`)
    const c = new OffscreenCanvas(bmp.width, bmp.height).getContext('2d')
    c.drawImage(bmp, 0, 0)
    const tt = Math.min(Math.max(t, 0), 1), dd = Math.min(Math.max(d, 0), 1) * tt
    const px = c.getImageData(Math.floor((1 - tt) * 255), Math.floor((1 - dd) * 255), 1, 1).data
    return [px[0] / 255, px[1] / 255, px[2] / 255]
  }
  const hex = v => {
    const n = typeof v === 'number' ? v : parseInt(String(v).replace('#', ''), 16)
    return [(n >> 16 & 255) / 255, (n >> 8 & 255) / 255, (n & 255) / 255]
  }
  const e = b.effects ?? {}
  return {
    grass: e.grass_color != null ? hex(e.grass_color) : await sample('grass', b.temperature, b.downfall),
    foliage: e.foliage_color != null ? hex(e.foliage_color) : await sample('foliage', b.temperature, b.downfall),
    water: e.water_color != null ? hex(e.water_color) : hex(0x3f76e4),
  }
}

function applyTint(tint) {
  const grass = ['grass_block', 'short_grass', 'tall_grass', 'fern', 'large_fern', 'potted_fern', 'sugar_cane', 'pink_petals']
  const foliage = ['oak_leaves', 'jungle_leaves', 'acacia_leaves', 'dark_oak_leaves', 'mangrove_leaves', 'vine']
  const water = ['water', 'bubble_column', 'water_cauldron']
  for (const k of grass) if (BlockColors[k]) BlockColors[k] = () => tint.grass
  for (const k of foliage) if (BlockColors[k]) BlockColors[k] = () => tint.foliage
  for (const k of water) if (BlockColors[k]) BlockColors[k] = () => tint.water
}

// Processors: the rule and block_rot processors the pack's structures use. The random source is
// seeded by the block position, like the game's, so a render is the same every time.
function rng(pos, salt) {
  let h = (pos[0] * 3129871) ^ (pos[1] * 116129781) ^ (pos[2] * 2654435761) ^ (salt * 668265263)
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); h ^= h >>> 16
    return (h >>> 0) / 4294967296
  }
}
function matches(pred, name, rand) {
  const t = pred.predicate_type
  if (t === 'minecraft:always_true') return true
  if (t === 'minecraft:block_match') return nsid(pred.block) === name
  if (t === 'minecraft:random_block_match') return nsid(pred.block) === name && rand() < pred.probability
  return false
}
function applyProcessors(procs, pos, name, props) {
  procs.forEach((p, i) => {
    if (!name) return
    const rand = rng(pos, i + 1)
    if (p.processor_type === 'minecraft:block_rot') {
      if (rand() > p.integrity) name = null
    } else if (p.processor_type === 'minecraft:rule') {
      for (const r of p.rules) {
        if (matches(r.input_predicate, name, rand) && matches(r.location_predicate ?? { predicate_type: 'minecraft:always_true' }, name, rand)) {
          name = nsid(r.output_state.Name); props = r.output_state.Properties ?? {}
          break
        }
      }
    }
  })
  return [name, props]
}
export async function resolveProcessors(p) {
  if (typeof p === 'string') p = await getJson('/wg/processor_list/' + nsid(p)).catch(() => [])
  p = p ?? []
  return Array.isArray(p) ? p : p.processors ?? []
}

async function loadTemplate(loc) {
  const [n, p] = nsid(loc).split(':')
  const r = await fetch(`/nbt/${n}/structure/${p}.nbt`)
  if (!r.ok) throw new Error('missing template ' + loc)
  return Structure.fromNbt(NbtFile.read(new Uint8Array(await r.arrayBuffer())).root)
}

// Block states, models and the texture atlas, as deepslate's renderers want them. Item icons pass
// the item textures too (the atlas is otherwise only block and entity textures).
export async function resources(extraTextures = []) {
  const [statesJson, modelsJson, texIds, blocks] = await Promise.all(
    ['/asset/blockstates', '/asset/models', '/asset/textures', '/asset/blocks'].map(getJson))
  const atlas = await buildAtlas([...texIds, ...extraTextures].sort())
  // The pack uses the newer multi-axis element rotation ({x, y, z, origin}); deepslate reads {axis, angle}.
  for (const j of Object.values(modelsJson)) for (const e of j.elements ?? []) {
    const r = e.rotation
    if (r && r.axis === undefined) {
      const axis = ['x', 'y', 'z'].find(a => r[a]) ?? 'y'
      e.rotation = { axis, angle: r[axis] ?? 0, origin: r.origin ?? [8, 8, 8], rescale: r.rescale }
    }
  }
  const defs = {}, models = {}, flags = {}
  for (const [id, j] of Object.entries(statesJson)) defs[id] = BlockDefinition.fromJson(j)
  for (const [id, j] of Object.entries(modelsJson)) models[id] = BlockModel.fromJson(j)
  const getBlockModel = id => models[id.toString()] ?? null
  Object.values(models).forEach(m => m.flatten({ getBlockModel }))
  const fullCube = id => {
    const els = modelsJson[id]?.elements ?? models[id]?.elements
    return Array.isArray(els) && els.length === 1 && els[0].from.every(v => v === 0) && els[0].to.every(v => v === 16)
  }
  for (const [id, j] of Object.entries(statesJson)) {
    const variants = j.variants ? Object.values(j.variants).flat() : null
    const full = variants && variants.every(v => fullCube(Identifier.parse(v.model).toString()))
    flags[id] = { opaque: !!full && !CUTOUT.test(id), semi_transparent: TRANSLUCENT.test(id), self_culling: CUTOUT.test(id) || TRANSLUCENT.test(id) }
  }
  const missingTex = new Set()
  return {
    defs, flags, missingTex,
    res: {
      getBlockDefinition: id => defs[id.toString()] ?? null,
      getBlockModel,
      getTextureAtlas: () => atlas.image,
      // '#missing' faces (the pack's invisible faces) resolve to an empty id and are never drawn
      getTextureUV: id => atlas.uv[id.toString()] ?? (id.path && missingTex.add(id.toString()), [0, 0, 16 / atlas.size, 16 / atlas.size]),
      getPixelSize: () => 1 / atlas.size,
      getBlockFlags: id => flags[id.toString()] ?? null,
      getBlockProperties: id => blocks[id.path]?.[0] ?? null,
      getDefaultBlockProperties: id => blocks[id.path]?.[1] ?? null,
    },
  }
}

// Collect every block to draw as { pos, name, props, nbt }, in world coordinates starting at 0.
async function collectBlocks(job) {
  const out = []
  let size
  const place = (tpl, procs, rot, origin, cut) => {
    const tsize = tpl.getSize()
    for (const b of tpl.getBlocks()) {
      if (cut && b.pos[1] >= tsize[1] - cut) continue
      let name = b.state.getName().toString(), props = rotProps(b.state.getProperties(), rot)
      if (name === 'minecraft:jigsaw') {
        const m = (b.nbt?.getString('final_state') || 'minecraft:air').match(/^([^[]+)(?:\[(.*)\])?$/)
        name = nsid(m[1]); props = Object.fromEntries((m[2] ?? '').split(',').filter(Boolean).map(kv => kv.split('=')))
      }
      const pos = rotPos(b.pos, rot).map((v, i) => v + origin[i])
      // gravity processor: height above the ground instead of the template's (the well sinks 8)
      const gravity = procs.find(p => p.processor_type === 'minecraft:gravity')
      if (gravity) pos[1] = FLAT_HEIGHT + (gravity.offset ?? 0) + b.pos[1]
      ;[name, props] = applyProcessors(procs, pos, name, props)
      if (!name || AIR.test(name)) continue
      out.push({ pos, name, props, nbt: b.nbt })
    }
  }
  if (job.jigsaw) {
    const { pieces, template } = await assemble(job.jigsaw, job.seed ?? 1, getJson, loadTemplate)
    const cutRe = job.cut?.pools ? new RegExp(job.cut.pools) : null
    for (const pc of pieces) {
      const els = pc.el.element_type === 'minecraft:list_pool_element' ? pc.el.elements : [pc.el]
      for (const el of els) {
        const t = template(el.location)
        if (!t) continue
        place(t.s, await resolveProcessors(el.processors), pc.rot, pc.origin, cutRe?.test(el.location) ? job.cut.layers : 0)
      }
    }
    window.renderInfo = { pieces: pieces.map(p => `${p.depth} ${p.el.location ?? p.el.elements?.[0]?.location} r${p.rot}`) }
  } else {
    // One template, or several stacked like a list pool element; processors come from the pools
    // that place each template unless the job names them.
    for (const [i, loc] of [job.template].flat().entries()) {
      const tpl = await loadTemplate(loc)
      const procs = job.processors !== undefined ? await resolveProcessors(job.processors) : await getJson('/asset/pool-processors/' + nsid(loc))
      if (i === 0) size = tpl.getSize()
      place(tpl, procs, 0, [0, 0, 0], job.cut ?? 0)
    }
  }
  // later blocks win (stacked templates), then shift to start at 0
  const byPos = new Map()
  for (const b of out) byPos.set(b.pos.join(), b)
  const blocks = [...byPos.values()]
  if (job.ground) {
    const lo = [0, 2].map(i => Math.min(...blocks.map(b => b.pos[i]))), hi = [0, 2].map(i => Math.max(...blocks.map(b => b.pos[i])))
    const m = job.ground.margin ?? 4
    for (let x = lo[0] - m; x <= hi[0] + m; x++) for (let z = lo[1] - m; z <= hi[1] + m; z++) {
      const k = [x, job.ground.y ?? 63, z].join()
      if (!byPos.has(k)) blocks.push({ pos: [x, job.ground.y ?? 63, z], name: nsid(job.ground.block), props: {}, nbt: undefined })
    }
  }
  const lo = [0, 1, 2].map(i => Math.min(...blocks.map(b => b.pos[i])))
  const hi = [0, 1, 2].map(i => Math.max(...blocks.map(b => b.pos[i])))
  for (const b of blocks) b.pos = b.pos.map((v, i) => v - lo[i])
  return { blocks, size: hi.map((v, i) => v - lo[i] + 1) }
}

export async function renderStructure(job, canvas) {
  const { defs, res, missingTex } = await resources()
  if (job.biome) applyTint(await biomeTint(job.biome))
  const { blocks, size } = await collectBlocks(job)
  const s = new Structure(size)
  const unknown = new Set()
  for (const b of blocks) {
    if (!defs[b.name]) unknown.add(b.name)
    s.addBlock(b.pos, b.name, b.props, b.nbt)
  }
  const cam = job.camera ?? {}
  const yaw = (cam.yaw ?? 45) * Math.PI / 180, pitch = (cam.pitch ?? 30) * Math.PI / 180
  const view = mat4.create()
  mat4.translate(view, view, [0, 0, -1000])
  mat4.rotateX(view, view, pitch)
  mat4.rotateY(view, view, yaw)
  mat4.translate(view, view, size.map(v => -v / 2))
  // an orthographic box around the projected bounding box
  let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity]
  for (const cx of [0, size[0]]) for (const cy of [0, size[1]]) for (const cz of [0, size[2]]) {
    const p = vec3.transformMat4(vec3.create(), [cx, cy, cz], view)
    x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1])
  }
  const ppb = job.width / (x1 - x0)  // pixels per block for the requested width
  canvas.width = Math.round((x1 - x0) * ppb); canvas.height = Math.round((y1 - y0) * ppb)
  const gl = canvas.getContext('webgl', { preserveDrawingBuffer: true, premultipliedAlpha: false, antialias: false })
  // no invisible-block mesh: it covers every empty cell, which is millions for a whole structure
  const r = new StructureRenderer(gl, s, res, { chunkSize: 16, useInvisibleBlockBuffer: false })
  gl.bindTexture(gl.TEXTURE_2D, r.atlasTexture)
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
  r.projMatrix = mat4.ortho(mat4.create(), x0, x1, y0, y1, 0.1, 5000)
  gl.viewport(0, 0, canvas.width, canvas.height)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT)
  r.drawStructure(view)
  return { size, blocks: blocks.length, unknownBlocks: [...unknown], missingTextures: [...missingTex], ...(window.renderInfo ?? {}) }
}
