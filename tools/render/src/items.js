// Inventory icons for block items, drawn from their item models the way the game draws an item in a
// slot: the model's gui display transform, seen head-on in a 16x16 frame. Used by tools/images.py.
// job: { kind: 'icons', size, items: [{ file, id, model }] } -> one png per item
import { Identifier, ItemModel, ItemRenderer, ItemStack, ItemTint, jsonToNbt, NbtString } from 'deepslate'
import { resources } from './structure.js'

const getJson = async u => { const r = await fetch(u); if (!r.ok) throw new Error('missing ' + u); return r.json() }

// Slot lighting: the top of a block at full brightness, its left face at 80% and its right face at
// 62%, as the game's GUI lights a block item; worked out from the face normal as the view sees it.
const VS = `
  attribute vec4 vertPos;
  attribute vec2 texCoord;
  attribute vec4 texLimit;
  attribute vec3 vertColor;
  attribute vec3 normal;
  uniform mat4 mView;
  uniform mat4 mProj;
  varying highp vec2 vTexCoord;
  varying highp vec4 vTexLimit;
  varying highp vec3 vTintColor;
  varying highp float vLighting;
  void main(void) {
    gl_Position = mProj * mView * vertPos;
    vTexCoord = texCoord;
    vTexLimit = texLimit;
    vTintColor = vertColor;
    vLighting = clamp(0.794 - 0.127 * normal.x + 0.238 * normal.y, 0.45, 1.0);
  }
`
const FS = `
  precision highp float;
  varying highp vec2 vTexCoord;
  varying highp vec4 vTexLimit;
  varying highp vec3 vTintColor;
  varying highp float vLighting;
  uniform sampler2D sampler;
  uniform highp float pixelSize;
  void main(void) {
    vec4 texColor = texture2D(sampler, clamp(vTexCoord, vTexLimit.xy + vec2(0.5) * pixelSize, vTexLimit.zw - vec2(0.5) * pixelSize));
    if (texColor.a < 0.1) discard;
    gl_FragColor = vec4(texColor.xyz * vTintColor * vLighting, 1.0);
  }
`

function compile(gl) {
  const shader = (type, src) => {
    const s = gl.createShader(type)
    gl.shaderSource(s, src); gl.compileShader(s)
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s))
    return s
  }
  const p = gl.createProgram()
  gl.attachShader(p, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(p, shader(gl.FRAGMENT_SHADER, FS))
  gl.linkProgram(p)
  return p
}

// The grass tint of an item (grass block, fern...) from the pack's grass colour map, as the game
// samples it; deepslate has one fixed colour.
async function grassColormap() {
  const r = await fetch('/tex/minecraft:colormap/grass')
  const bmp = await createImageBitmap(await r.blob())
  const c = new OffscreenCanvas(bmp.width, bmp.height).getContext('2d')
  c.drawImage(bmp, 0, 0)
  return (temperature, downfall) => {
    const t = Math.min(Math.max(temperature, 0), 1), d = Math.min(Math.max(downfall, 0), 1) * t
    const px = c.getImageData(Math.floor((1 - t) * 255), Math.floor((1 - d) * 255), 1, 1).data
    return [px[0] / 255, px[1] / 255, px[2] / 255]
  }
}

export async function renderIcons(job, canvas) {
  const [itemDefs, itemTextures, components] = await Promise.all(
    ['/asset/items', '/asset/item-textures', '/asset/item-components'].map(getJson))
  const { res, missingTex } = await resources(itemTextures)
  const grass = await grassColormap()
  ItemTint.Grass.prototype.getTint = function () { return grass(this.temperature, this.downfall) }
  const itemModels = {}
  const nbt = {}
  const r = {
    ...res,
    getItemModel: id => (itemModels[id.toString()] ??= itemDefs[id.toString()] ? ItemModel.fromJson(itemDefs[id.toString()].model) : null),
    getItemComponents: id => (nbt[id.toString()] ??= new Map(Object.entries(components[id.path] ?? {}).map(([k, v]) => [k, jsonToNbt(v)]))),
  }
  const size = job.size ?? 256
  canvas.width = canvas.height = size
  const gl = canvas.getContext('webgl', { preserveDrawingBuffer: true, antialias: false, alpha: true, premultipliedAlpha: false })
  const program = compile(gl)
  const pngs = {}, failed = []
  let renderer
  for (const it of job.items) {
    const stack = new ItemStack(Identifier.parse(it.id), 1, new Map(it.model ? [['minecraft:item_model', new NbtString(it.model)]] : []))
    try {
      if (!renderer) {
        renderer = new ItemRenderer(gl, stack, r)
        renderer.shaderProgram = program
      } else {
        renderer.setItem(stack)
      }
      gl.viewport(0, 0, size, size)
      gl.clearColor(0, 0, 0, 0)
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT)
      renderer.drawItem()
      pngs[it.file] = canvas.toDataURL('image/png')
    } catch (e) {
      failed.push(`${it.file}: ${e.message ?? e}`)
    }
  }
  return { pngs, info: { icons: Object.keys(pngs).length, failed, missing: [...missingTex] } }
}
