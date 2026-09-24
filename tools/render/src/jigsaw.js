// Jigsaw assembly following the game's JigsawPlacement: weighted-shuffled pool candidates tried in
// shuffled rotations, connectors matched by name/target and opposite facing, no overlapping
// bounding boxes, the structure's depth (size) and max_distance_from_center limits.
// It produces one valid layout for a seed, not the layout of any particular world. There is no
// terrain: rigid pieces keep the height their connectors give them, terrain_matching pieces are laid
// into flat ground whose top block is at y=63.

const DIRS = ['north', 'east', 'south', 'west']
const VEC = { north: [0, 0, -1], south: [0, 0, 1], east: [1, 0, 0], west: [-1, 0, 0], up: [0, 1, 0], down: [0, -1, 0] }
const OPP = { north: 'south', south: 'north', east: 'west', west: 'east', up: 'down', down: 'up' }
const nsid = s => (s.includes(':') ? s : 'minecraft:' + s)

export const rotDir = (d, r) => (DIRS.includes(d) ? DIRS[(DIRS.indexOf(d) + r) % 4] : d)
// Clockwise quarter turns about the template origin, as StructureTemplate.transform does.
export const rotPos = ([x, y, z], r) => [[x, y, z], [-z, y, x], [-x, y, -z], [z, y, -x]][r]
// Block-state properties that depend on direction.
export function rotProps(props, r) {
  if (!r) return props
  const out = {}
  for (const [k, v] of Object.entries(props)) {
    if (DIRS.includes(k)) out[rotDir(k, r)] = v
    else if (k === 'facing') out[k] = rotDir(v, r)
    else if (k === 'orientation') { const [a, b] = v.split('_'); out[k] = `${rotDir(a, r)}_${rotDir(b, r)}` }
    else if (k === 'axis' && r % 2) out[k] = v === 'x' ? 'z' : v === 'z' ? 'x' : v
    else if (k === 'rotation') out[k] = String((+v + 4 * r) % 16)
    else out[k] = v
  }
  return out
}

function mulberry(seed) {
  let a = seed >>> 0
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }
}
function shuffle(arr, rand) {
  for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]] }
  return arr
}
const overlaps = (a, b) => [0, 1, 2].every(i => a.lo[i] <= b.hi[i] && b.lo[i] <= a.hi[i])
const within = (a, b) => [0, 1, 2].every(i => a.lo[i] >= b.lo[i] && a.hi[i] <= b.hi[i])
const contains = (b, p) => [0, 1, 2].every(i => p[i] >= b.lo[i] && p[i] <= b.hi[i])
function bbox(size, r, origin) {
  const c = [[0, 0, 0], [size[0] - 1, size[1] - 1, size[2] - 1]].map(p => rotPos(p, r))
  return {
    lo: [0, 1, 2].map(i => Math.min(c[0][i], c[1][i]) + origin[i]),
    hi: [0, 1, 2].map(i => Math.max(c[0][i], c[1][i]) + origin[i]),
  }
}

export async function assemble(structureId, seed, getJson, loadTemplate) {
  const rand = mulberry(seed)
  const structure = await getJson('/wg/structure/' + nsid(structureId))
  const pools = {}, templates = {}
  const getPool = async id => (id in pools ? pools[id] : (pools[id] = await getJson('/wg/template_pool/' + nsid(id)).catch(() => null)))
  async function getTemplate(loc) {
    if (loc in templates) return templates[loc]
    const s = await loadTemplate(loc).catch(() => null)
    if (!s) return (templates[loc] = null)
    const jigsaws = s.getBlocks().filter(b => b.state.getName().toString() === 'minecraft:jigsaw').map(b => {
      const [front, top] = b.state.getProperties().orientation.split('_')
      const g = k => b.nbt?.getString(k) ?? ''
      return {
        pos: b.pos, front, top,
        name: nsid(g('name') || 'empty'), target: nsid(g('target') || 'empty'), pool: nsid(g('pool') || 'empty'),
        joint: g('joint') || (DIRS.includes(front) ? 'rollable' : 'aligned'),
        selection: b.nbt?.getNumber?.('selection_priority') ?? 0,
      }
    })
    return (templates[loc] = { s, size: s.getSize(), jigsaws })
  }
  // A list element uses its first sub-element's connectors and the union of the sizes.
  const subs = el => (el.element_type === 'minecraft:list_pool_element' ? el.elements : [el])
  async function elementSize(el) {
    let m = [1, 1, 1]
    for (const s of subs(el)) { const t = await getTemplate(s.location); if (t) m = m.map((v, i) => Math.max(v, t.size[i])) }
    return m
  }
  async function elementJigsaws(el, r) {
    const t = await getTemplate(subs(el)[0].location)
    if (!t) return []
    const js = shuffle(t.jigsaws.map(j => ({ ...j, pos: rotPos(j.pos, r), front: rotDir(j.front, r), top: rotDir(j.top, r) })), rand)
    return js.sort((a, b) => b.selection - a.selection)
  }
  async function shuffledElements(poolId) {
    const pool = await getPool(poolId)
    if (!pool) return { list: [], fallback: null }  // a missing pool generates nothing, as in the game
    const list = []
    for (const e of pool.elements ?? []) for (let i = 0; i < (e.weight ?? 1); i++) list.push(e.element)
    return { list: shuffle(list, rand), fallback: pool.fallback }
  }

  const startEl = (await shuffledElements(structure.start_pool)).list.find(e => e.element_type !== 'minecraft:empty_pool_element')
  const startRot = Math.floor(rand() * 4)
  const startY = 64 + (structure.start_height?.absolute ?? 0)
  const start = { el: startEl, rot: startRot, origin: [0, startY, 0], depth: 0 }
  start.box = bbox(await elementSize(startEl), startRot, start.origin)
  const center = start.box.lo.map((v, i) => Math.floor((v + start.box.hi[i]) / 2))
  const R = structure.max_distance_from_center ?? 80
  const world = { lo: [center[0] - R, Math.max(center[1] - R, -57), center[2] - R], hi: [center[0] + R, Math.min(center[1] + R, 312), center[2] + R] }
  const maxDepth = structure.size ?? 7
  const pieces = [start], queue = [start]

  while (queue.length) {
    const piece = queue.shift()
    for (const j of await elementJigsaws(piece.el, piece.rot)) {
      const tgt = j.pos.map((v, i) => v + piece.origin[i] + VEC[j.front][i])
      const inside = contains(piece.box, tgt)
      const { list, fallback } = piece.depth < maxDepth ? await shuffledElements(j.pool) : { list: [], fallback: (await getPool(j.pool))?.fallback }
      const cands = [...list, ...(fallback ? (await shuffledElements(fallback)).list : [])]
      let placed = false
      for (const el of cands) {
        if (el.element_type === 'minecraft:empty_pool_element') break
        const size = await elementSize(el)
        for (const r of shuffle([0, 1, 2, 3], rand)) {
          for (const cj of await elementJigsaws(el, r)) {
            if (!(j.front === OPP[cj.front] && (j.joint === 'rollable' || j.top === cj.top) && j.target === cj.name)) continue
            const origin = tgt.map((v, i) => v - cj.pos[i])
            // terrain_matching: the game adds GravityProcessor(WORLD_SURFACE_WG, -1), so the piece's bottom
            // layer replaces the surface block (y=63 on flat ground)
            if ((subs(el)[0].projection ?? 'rigid') === 'terrain_matching') origin[1] = 63
            const box = bbox(size, r, origin)
            if (!within(box, inside ? piece.box : world)) continue
            if (pieces.some(p => p !== piece && overlaps(p.box, box))) continue
            if (!inside && overlaps(piece.box, box)) continue
            const child = { el, rot: r, origin, depth: piece.depth + 1, box }
            pieces.push(child)
            if (child.depth <= maxDepth) queue.push(child)
            placed = true
            break
          }
          if (placed) break
        }
        if (placed) break
      }
    }
  }
  return { pieces, template: loc => templates[loc] }
}
