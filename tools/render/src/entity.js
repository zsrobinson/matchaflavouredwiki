// Mob and armor renders: texture layers and equipment on the models in models.js (three.js).
import * as THREE from 'three'
import { EQUIPMENT_SLOTS, MODELS, POSES } from './models.js'

const nsid = s => (s.includes(':') ? s : 'minecraft:' + s)

function loadTexture(id) {
  return new Promise((ok, err) => new THREE.TextureLoader().load('/tex/' + nsid(id), t => {
    t.magFilter = THREE.NearestFilter; t.minFilter = THREE.NearestFilter; t.colorSpace = THREE.SRGBColorSpace; ok(t)
  }, undefined, () => err(new Error('missing texture ' + id))))
}

// One cube with Minecraft's box UV layout. UVs are worked out per vertex from its position and
// normal, so the mapping doesn't depend on three.js's face order.
function cube(c, tex, { inflate = 0, tint = null, doubleSided = false }) {
  const [w, h, d] = c.size, [u, v] = c.uv, mirror = !!c.mirror
  const g = new THREE.BoxGeometry(w + 2 * inflate, h + 2 * inflate, d + 2 * inflate)
  const pos = g.attributes.position, nrm = g.attributes.normal, uv = g.attributes.uv
  const TW = tex.image.width, TH = tex.image.height
  const W = w + 2 * inflate, H = h + 2 * inflate, D = d + 2 * inflate
  const e = 0.02  // stay a hair inside each face's texels so edges don't pick up the neighbours
  for (let i = 0; i < pos.count; i++) {
    const ax = (pos.getX(i) + W / 2) / W, ay = (pos.getY(i) + H / 2) / H, az = (pos.getZ(i) + D / 2) / D
    const nx = Math.round(nrm.getX(i)), ny = Math.round(nrm.getY(i)), nz = Math.round(nrm.getZ(i))
    const mx = mirror ? 1 - ax : ax
    let r, s, t
    if (nz === 1) { r = [u + d, v + d, w, h]; s = mx; t = 1 - ay }                       // front
    else if (nz === -1) { r = [u + 2 * d + w, v + d, w, h]; s = 1 - mx; t = 1 - ay }      // back
    else if (nx !== 0) {
      const entityRight = (nx === -1) !== mirror                                         // -X is the entity's right
      if (entityRight) { r = [u, v + d, d, h]; s = az } else { r = [u + d + w, v + d, d, h]; s = 1 - az }
      if (mirror) s = 1 - s
      t = 1 - ay
    } else if (ny === 1) { r = [u + d, v, w, d]; s = mx; t = az }                       // top
    else { r = [u + d + w, v, w, d]; s = mx; t = az }                                   // bottom
    uv.setXY(i, (r[0] + e + s * (r[2] - 2 * e)) / TW, 1 - (r[1] + e + t * (r[3] - 2 * e)) / TH)
  }
  const mat = new THREE.MeshLambertMaterial({ map: tex, transparent: true, alphaTest: 0.1, side: doubleSided ? THREE.DoubleSide : THREE.FrontSide })
  if (tint != null) mat.color = new THREE.Color(tint)
  const mesh = new THREE.Mesh(g, mat)
  // Minecraft model space has y down and the feet at y=24; here y is up and the feet are at 0.
  mesh.position.set(c.from[0] + w / 2, -(c.from[1] + h / 2), -(c.from[2] + d / 2))
  return mesh
}

export async function renderEntity(job, canvas) {
  const scene = new THREE.Scene()
  const parts = {}
  const part = (name, def) => {
    if (!parts[name]) {
      const g = new THREE.Group()
      g.position.set(def.pivot[0], 24 - def.pivot[1], -def.pivot[2])
      scene.add(g)
      parts[name] = g
    }
    return parts[name]
  }
  // texture layers: [{ model, texture, inflate }]
  for (const layer of job.layers ?? []) {
    const model = MODELS[layer.model]
    if (!model) throw new Error('unknown model ' + layer.model)
    const tex = await loadTexture(layer.texture)
    for (const [name, def] of Object.entries(model)) {
      for (const c of def.cubes) part(name, def).add(cube(c, tex, { inflate: (c.inflate ?? 0) + (layer.inflate ?? 0) }))
    }
  }
  // equipment: an equipment asset (assets/<ns>/equipment/<id>.json) on the humanoid armor model.
  // The game draws armor with back faces, so it does here too (it shows inside a lone helmet).
  if (job.equipment) {
    const asset = await (await fetch('/equip/' + nsid(job.equipment.asset))).json()
    const model = MODELS.humanoid
    for (const slot of job.equipment.slots ?? ['head', 'chest', 'legs', 'feet']) {
      const spec = EQUIPMENT_SLOTS[slot]
      for (const entry of asset.layers[spec.layer] ?? []) {
        const [ns, name] = nsid(entry.texture).split(':')
        const tex = await loadTexture(`${ns}:entity/equipment/${spec.layer}/${name}`)
        const tint = entry.dyeable ? (entry.dyeable.color_when_undyed >>> 0) & 0xffffff : null
        for (const pname of spec.parts) {
          const def = model[pname]
          const c = def.cubes[0]  // the hat layer is not part of armor
          part(pname, def).add(cube(c, tex, { inflate: spec.inflate, tint, doubleSided: true }))
        }
      }
    }
  }
  const pose = POSES[job.pose ?? 'stand']
  if (!pose) throw new Error('unknown pose ' + job.pose)
  for (const [name, rot] of Object.entries(pose.parts)) if (parts[name]) parts[name].rotation.set(...rot)

  scene.add(new THREE.AmbientLight(0xffffff, 1.6))
  const sun = new THREE.DirectionalLight(0xffffff, 1.4)
  sun.position.set(-0.6, 1, 0.8)
  scene.add(sun)

  // camera from the front-right, then fit an orthographic frustum to what's in the scene
  const cam = { ...pose.camera, ...job.camera }
  const yaw = (cam.yaw ?? 35) * Math.PI / 180, pitch = (cam.pitch ?? 10) * Math.PI / 180
  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 1000)
  camera.position.set(Math.sin(yaw) * Math.cos(pitch) * 200, 16 + Math.sin(pitch) * 200, Math.cos(yaw) * Math.cos(pitch) * 200)
  camera.lookAt(0, 16, 0)
  camera.updateMatrixWorld()
  const box = new THREE.Box3().setFromObject(scene)
  let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity]
  for (const x of [box.min.x, box.max.x]) for (const y of [box.min.y, box.max.y]) for (const z of [box.min.z, box.max.z]) {
    const p = new THREE.Vector3(x, y, z).applyMatrix4(camera.matrixWorldInverse)
    x0 = Math.min(x0, p.x); x1 = Math.max(x1, p.x); y0 = Math.min(y0, p.y); y1 = Math.max(y1, p.y)
  }
  Object.assign(camera, { left: x0 - 0.5, right: x1 + 0.5, top: y1 + 0.5, bottom: y0 - 0.5 })
  camera.updateProjectionMatrix()
  const W = job.width, H = Math.round(W * (y1 - y0 + 1) / (x1 - x0 + 1))
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: false, preserveDrawingBuffer: true })
  renderer.setSize(W, H, false)
  renderer.setClearColor(0x000000, 0)
  renderer.render(scene, camera)
  return { width: W, height: H }
}
