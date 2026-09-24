// Mob and armor renders (three.js): the game's own entity models (entity_models.json), with texture
// layers drawn the way the game's renderers draw them.
import * as THREE from 'three'
import MODELS from './entity_models.json'
import { isoCamera } from './camera.js'
import { CAMERAS, EQUIPMENT_SLOTS, POSES, REST } from './models.js'

const nsid = s => (s.includes(':') ? s : 'minecraft:' + s)
// 'zombie' -> 'minecraft:zombie#main'; 'stray#outer' -> 'minecraft:stray#outer'
const layerId = s => nsid(s.includes('#') ? s : s + '#main')
const modelKey = id => id.split(':')[1].split('#')[0]

function loadTexture(id) {
  return new Promise((ok, err) => new THREE.TextureLoader().load('/tex/' + nsid(id), t => {
    t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.colorSpace = THREE.SRGBColorSpace; ok(t)
  }, undefined, () => err(new Error('missing texture ' + id))))
}
async function textureMeta(id) {
  const r = await fetch('/texmeta/' + nsid(id))
  return r.ok ? r.json() : {}
}

// One cube as the game builds it (ModelPart.Cube): six quads with box UVs, grown by its deformation,
// mirrored if asked. Vertices are in the part's space, in the game's model units.
const E = 0.02  // texels: keep a hair inside each face so edges don't pick up the neighbours
function cubeGeometry(c, texW, texH) {
  const [x0, y0, z0] = c.from, [w, h, d] = c.size, [gx, gy, gz] = c.grow ?? [0, 0, 0]
  const [tu, tv] = c.texScale ?? [1, 1], TW = texW * tu, TH = texH * tv
  let minX = x0 - gx, maxX = x0 + w + gx
  const minY = y0 - gy, maxY = y0 + h + gy, minZ = z0 - gz, maxZ = z0 + d + gz
  if (c.mirror) [minX, maxX] = [maxX, minX]
  const t0 = [minX, minY, minZ], t1 = [maxX, minY, minZ], t2 = [maxX, maxY, minZ], t3 = [minX, maxY, minZ]
  const l0 = [minX, minY, maxZ], l1 = [maxX, minY, maxZ], l2 = [maxX, maxY, maxZ], l3 = [minX, maxY, maxZ]
  const [u, v] = c.uv
  const u1 = u + d, u2 = u + d + w, u22 = u + d + w + w, u3 = u + d + w + d, u4 = u + d + w + d + w
  const v1 = v + d, v2 = v + d + h
  const faces = [
    ['down', [l1, l0, t0, t1], u1, v, u2, v1, [0, -1, 0]],
    ['up', [t2, t3, l3, l2], u2, v1, u22, v, [0, 1, 0]],
    ['west', [t0, l0, l3, t3], u, v1, u1, v2, [-1, 0, 0]],
    ['north', [t1, t0, t3, t2], u1, v1, u2, v2, [0, 0, -1]],
    ['east', [l1, t1, t2, l2], u2, v1, u3, v2, [1, 0, 0]],
    ['south', [l0, l1, l2, l3], u3, v1, u4, v2, [0, 0, 1]],
  ]
  const pos = [], nrm = [], uvs = [], idx = []
  for (const [name, verts, fu0, fv0, fu1, fv1, n] of faces) {
    if (c.faces && !c.faces.includes(name)) continue
    // ModelPart.Polygon: the corners get (u1,v0) (u0,v0) (u0,v1) (u1,v1); a mirrored cube then
    // reverses the corner order (keeping each corner's uv) and its x faces point the other way
    let corners = verts.map((p, i) => [p, [[fu1, fv0], [fu0, fv0], [fu0, fv1], [fu1, fv1]][i]])
    let normal = n
    if (c.mirror) { corners = corners.reverse(); if (n[0]) normal = [-n[0], 0, 0] }
    const cu = (fu0 + fu1) / 2, cv = (fv0 + fv1) / 2
    const base = pos.length / 3
    for (const [p, [pu, pv]] of corners) {
      const uu = pu + Math.sign(cu - pu) * E, vv = pv + Math.sign(cv - pv) * E
      pos.push(...p); nrm.push(...normal); uvs.push(uu / TW, 1 - vv / TH)
    }
    idx.push(base, base + 1, base + 2, base, base + 2, base + 3)
  }
  const g = new THREE.BufferGeometry()
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3))
  g.setAttribute('normal', new THREE.Float32BufferAttribute(nrm, 3))
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2))
  g.setIndex(idx)
  return g
}

// Builds a layer's part tree. Returns the root group and name -> group for every part.
function buildModel(def, material, order) {
  const byName = {}
  const build = (part, name) => {
    const g = new THREE.Group()
    g.name = name
    g.userData.def = part
    for (const c of part.cubes ?? []) {
      const mesh = new THREE.Mesh(cubeGeometry(c, def.tex[0], def.tex[1]), material)
      mesh.renderOrder = order
      g.add(mesh)
    }
    for (const [child, p] of Object.entries(part.children ?? {})) g.add(build(p, child))
    ;(byName[name] ??= []).push(g)
    return g
  }
  return { root: build(def.root, 'root'), byName }
}

// A villager's layers (VillagerRenderer + VillagerProfessionLayer): the base skin, the type (biome)
// outfit, the profession outfit and the level badge. The type's hat is left off under a profession
// hat that covers it, as the textures' .mcmeta files say.
async function villagerLayers({ type = 'plains', profession = 'none', level = 1, base = 'villager' }) {
  const hat = async id => (await textureMeta(id)).villager?.hat ?? 'none'
  const typeTex = `minecraft:entity/${base}/type/${type}`
  const profTex = `minecraft:entity/${base}/profession/${profession}`
  const typeHat = await hat(typeTex), profHat = profession === 'none' ? 'none' : await hat(profTex)
  const typeHatVisible = profHat === 'none' || (profHat === 'partial' && typeHat !== 'full')
  const layers = [
    { model: base, texture: `minecraft:entity/${base}/${base}` },
    { model: typeHatVisible ? base : base + '_no_hat', texture: typeTex },
  ]
  if (profession !== 'none') {
    layers.push({ model: base, texture: profTex })
    if (profession !== 'nitwit') {
      const badge = ['stone', 'iron', 'gold', 'emerald', 'diamond'][Math.min(Math.max(level, 1), 5) - 1]
      layers.push({ model: base, texture: `minecraft:entity/${base}/profession_level/${badge}` })
    }
  }
  return layers
}

export async function renderEntity(job, canvas) {
  const scene = new THREE.Scene()
  // The game draws models with y down and the feet at y=24 (after the renderer's flip): turning
  // the whole model half a turn about x gives y up with the front facing +z, towards the camera.
  const world = new THREE.Group()
  world.rotation.x = Math.PI
  world.position.y = 24
  scene.add(world)
  const trees = []
  const add = (id, material) => {
    const def = MODELS[id]
    if (!def) throw new Error('unknown model ' + id)
    const t = buildModel(def, material, trees.length)
    world.add(t.root)
    trees.push(t)
  }
  // texture layers: [{ model, texture, emissive }]; every entity layer is drawn without culling
  const layers = [...(job.villager ? await villagerLayers(job.villager) : []), ...(job.layers ?? [])]
  for (const layer of layers) {
    const map = await loadTexture(layer.texture)
    const material = layer.emissive
      ? new THREE.MeshBasicMaterial({ map, transparent: true, depthWrite: false, side: THREE.DoubleSide })  // eyes (RenderTypes.eyes)
      : new THREE.MeshLambertMaterial({ map, alphaTest: 0.1, side: THREE.DoubleSide })
    add(layerId(layer.model), material)
  }
  // equipment: an equipment asset (assets/<ns>/equipment/<id>.json) on the armor model layers
  if (job.equipment) {
    const asset = await (await fetch('/equip/' + nsid(job.equipment.asset))).json()
    const armor = nsid(job.equipment.model ?? 'player')
    for (const slot of job.equipment.slots ?? ['head', 'chest', 'legs', 'feet']) {
      const spec = EQUIPMENT_SLOTS[slot]
      for (const entry of asset.layers[spec.layer] ?? []) {
        const [ns, name] = nsid(entry.texture).split(':')
        const map = await loadTexture(`${ns}:entity/equipment/${spec.layer}/${name}`)
        const material = new THREE.MeshLambertMaterial({ map, alphaTest: 0.1, side: THREE.DoubleSide })
        if (entry.dyeable) material.color = new THREE.Color((entry.dyeable.color_when_undyed >>> 0) & 0xffffff)
        add(`${armor}#${spec.model}`, material)
      }
    }
  }

  // poses: every part of a name moves together across the layers, as the game poses each layer's
  // model the same way
  const state = {}
  const get = name => {
    if (!state[name]) {
      const g = trees.map(t => t.byName[name]?.[0]).find(Boolean)
      const d = g?.userData.def ?? {}  // a part this render doesn't draw (a helmet has no arms)
      state[name] = { pivot: [...(d.pivot ?? [0, 0, 0])], rot: [...(d.rot ?? [0, 0, 0])] }
    }
    return state[name]
  }
  const key = modelKey(layerId(layers[0]?.model ?? job.equipment?.model ?? 'player'))
  REST[key]?.(get)
  if (job.pose) {
    if (!POSES[job.pose]) throw new Error('unknown pose ' + job.pose)
    POSES[job.pose](get)
  }
  for (const t of trees) {
    for (const [name, groups] of Object.entries(t.byName)) {
      for (const g of groups) {
        const d = g.userData.def, s = state[name]
        const p = s?.pivot ?? d.pivot ?? [0, 0, 0], r = s?.rot ?? d.rot ?? [0, 0, 0]
        g.position.set(...p)
        g.rotation.set(r[0], r[1], r[2], 'ZYX')  // ModelPart.translateAndRotate: rotationZYX
        if (d.scale) g.scale.set(...d.scale)
      }
    }
  }

  scene.add(new THREE.AmbientLight(0xffffff, 1.6))
  const sun = new THREE.DirectionalLight(0xffffff, 1.4)
  sun.position.set(-0.6, 1, 0.8)
  scene.add(sun)

  // an isometric camera from the front-right (the mob faces left, as on minecraft.wiki), then fit an
  // orthographic frustum to what's in the scene
  const { yaw, pitch } = isoCamera({ ...CAMERAS[key], ...CAMERAS[job.pose], ...job.camera })
  scene.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(scene)
  const centre = box.getCenter(new THREE.Vector3())
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 4000)
  camera.position.set(centre.x + Math.sin(yaw) * Math.cos(pitch) * 1000, centre.y + Math.sin(pitch) * 1000, centre.z + Math.cos(yaw) * Math.cos(pitch) * 1000)
  camera.lookAt(centre)
  camera.updateMatrixWorld()
  let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity]
  const v = new THREE.Vector3()
  scene.traverse(o => {
    if (!o.isMesh) return
    const p = o.geometry.attributes.position
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i).applyMatrix4(o.matrixWorld).applyMatrix4(camera.matrixWorldInverse)
      x0 = Math.min(x0, v.x); x1 = Math.max(x1, v.x); y0 = Math.min(y0, v.y); y1 = Math.max(y1, v.y)
    }
  })
  Object.assign(camera, { left: x0 - 0.5, right: x1 + 0.5, top: y1 + 0.5, bottom: y0 - 0.5 })
  camera.updateProjectionMatrix()
  const W = job.width, H = Math.round(W * (y1 - y0 + 1) / (x1 - x0 + 1))
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, preserveDrawingBuffer: true })
  renderer.setSize(W, H, false)
  renderer.setClearColor(0x000000, 0)
  renderer.render(scene, camera)
  return { width: W, height: H }
}
