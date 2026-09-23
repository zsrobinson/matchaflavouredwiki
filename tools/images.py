#!/usr/bin/env python3
"""Build wiki images from pack/vanilla textures into build/images/.

  <Item Name>.png   inventory icon for every item in build/data.json (the file name
                    convention used by Module:Inventory slot and minecraft.wiki's Invicons)
  Glyph EXXX.png    each custom-font glyph from custom_emojis.png (used by {{G}})
  Texture <path>.png  raw textures listed in tools/extra_textures.txt (optional)

and into site/assets/gui/: the pack's station screens, progress sprites, villager offer button,
HUD hearts and glyph sheet at 2x, for Module:Station, Module:Tooltip and {{Hp}}.

Icons are upscaled with nearest-neighbour to 128px so MediaWiki thumbnails stay crisp.
Each item is drawn the way the inventory draws it (the `gui` node of its item definition, which
tools/extract.py records): flat items stack their layers with the game's tints, plain cubes get
iso_cube, other block models (stairs, fences, beds, ...) and entity-rendered items (chests,
sacks, heads, banners, shields, decorated pots, copper golem statues, the conduit) are drawn in
3D by render() below.
"""
import json
import math
import os
import re

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'build', 'images')
RP = os.path.join(ROOT, 'source', 'matcha-flavoured', 'MF_resourcepack', 'assets')
SIZE = 128


def first_frame(im):
    w, h = im.size
    if h > w and h % w == 0:
        im = im.crop((0, 0, w, w))
    return im


def upscale(im):
    im = first_frame(im.convert('RGBA'))
    w, h = im.size
    scale = max(1, SIZE // max(w, h))
    return im.resize((w * scale, h * scale), Image.NEAREST)


def shade(im, f):
    px = im.load()
    out = im.copy()
    po = out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            po[x, y] = (int(r * f), int(g * f), int(b * f), a)
    return out


def iso_cube(top, left, right, height=1.0):
    """Isometric cube (like the in-game inventory block render). The top texture's top-left
    corner is drawn at the back corner, its u axis along the upper-right edge."""
    n = 16
    top = first_frame(top.convert('RGBA')).resize((n, n), Image.NEAREST)
    left = first_frame(left.convert('RGBA')).resize((n, n), Image.NEAREST)
    right = first_frame(right.convert('RGBA')).resize((n, n), Image.NEAREST)
    hpx = max(1, int(round(n * height)))
    if height < 1:
        left = left.crop((0, n - hpx, n, n))
        right = right.crop((0, n - hpx, n, n))
    s = 8  # output scale per texel
    W = 2 * n * s
    # the cube spans 2*n*k vertically (top face n*k + side faces n*k): leave room for all of it
    canvas = Image.new('RGBA', (W, W + 16), (0, 0, 0, 0))
    ox, oy = W // 2, 4
    # half-extents of a texel step in screen space
    ux, uy = s * 0.866 * 1.155 / 1.0, s * 0.5 * 1.155

    def blit(tex, origin, ax, ay, bx, by, f):
        tex = shade(tex, f)
        tp = tex.load()
        tw, th = tex.size
        cp = canvas.load()
        # draw each texel as a parallelogram by sampling
        steps = 6
        for ty in range(th):
            for tx in range(tw):
                c = tp[tx, ty]
                if c[3] == 0:
                    continue
                for sy in range(steps):
                    for sx in range(steps):
                        u = tx + (sx + 0.5) / steps
                        v = ty + (sy + 0.5) / steps
                        X = origin[0] + ax * u + bx * v
                        Y = origin[1] + ay * u + by * v
                        xi, yi = int(X), int(Y)
                        for dx in (0, 1):
                            for dy in (0, 1):
                                if 0 <= xi + dx < W and 0 <= yi + dy < W:
                                    cp[xi + dx, yi + dy] = c
    k = s * 0.95
    h = k * 0.866  # true isometric: horizontal step is cos(30°) of the edge length (Minecraft's GUI block render)
    # top face: u -> down-right, v -> down-left
    blit(top, (ox, oy), h, k * 0.5, -h, k * 0.5, 1.0)
    # left face
    blit(left, (ox - h * n, oy + k * n * 0.5), h, k * 0.5, 0, k, 0.8)
    # right face
    blit(right, (ox, oy + k * n), h, -k * 0.5, 0, k, 0.62)
    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    side = max(canvas.size)
    sq = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    sq.paste(canvas, ((side - canvas.size[0]) // 2, (side - canvas.size[1]) // 2))
    return sq.resize((SIZE, SIZE), Image.LANCZOS)


FOLIAGE = (72, 181, 24)   # plains grass/foliage colour, as the game tints grayscale textures
GRASS = (145, 189, 89)  # vanilla's; the grass tint comes from the pack's colormap when it has one


def tint_if_foliage(im, faces, which):
    path = ''
    for k in ((which,) + ('top', 'all', 'side')):
        if k in faces:
            path = faces[k]
            break
    base = os.path.basename(getattr(im, 'filename', '') or path)
    if not any(x in base for x in ('grass_block_top', 'leaves', 'vine', 'fern', 'short_grass', 'tall_grass', 'lily_pad')):
        return im
    if 'cherry' in base or 'azalea' in base or 'pale_oak' in base:
        return im
    col = (colormap('grass', 0.5, 1.0) or GRASS) if 'grass' in base or 'fern' in base else FOLIAGE
    im = first_frame(im.convert('RGBA'))
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            px[x, y] = (r * col[0] // 255, g * col[1] // 255, b * col[2] // 255, a)
    return im


def safe(name):
    return re.sub(r'[\\/:*?"<>|#\[\]{}]', '', name).strip()


# ---------------------------------------------------------------- models in 3D
# Blocks that aren't plain cubes (stairs, fences, beds, ...) and the items the game draws with an
# entity renderer (item definition type "minecraft:special": chests, sacks, heads, banners,
# shields, decorated pots, copper golem statues) are drawn by a small software rasteriser. Every
# face is a textured parallelogram, drawn with a depth buffer under the item's own GUI display
# transform. 45-degree views use iso_cube's true isometric pitch, and the scale matches it: a full
# block at the usual GUI scale (0.625) fills the icon exactly as an iso_cube does, so a chest, a
# head or a slab keeps its size relative to a block, as in the game.
VANILLA = os.path.join(ROOT, 'source', 'vanilla-assets', 'assets')
VANILLA_DATA = os.path.join(ROOT, 'source', 'vanilla-data', 'data')
PACK_DATA = os.path.join(ROOT, 'source', 'matcha-flavoured', 'MF_datapack', 'data')
ISO_PITCH = math.degrees(math.atan(1 / math.sqrt(2)))
PX = SIZE / (32 * math.sqrt(2 / 3) * 0.625)  # icon px per model pixel at display scale 1
SS = 2  # supersampling: drawn at 2x, then reduced like iso_cube

# DyeColor's texture colours (banner and shield patterns)
DYE = {'white': 0xF9FFFE, 'orange': 0xF9801D, 'magenta': 0xC74EBD, 'light_blue': 0x3AB3DA, 'yellow': 0xFED83D,
       'lime': 0x80C71F, 'pink': 0xF38BAA, 'gray': 0x474F52, 'light_gray': 0x9D9D97, 'cyan': 0x169C9C,
       'purple': 0x8932B8, 'blue': 0x3C44AA, 'brown': 0x835432, 'green': 0x5E7C16, 'red': 0xB02E26, 'black': 0x1D1D21}
# MobEffect colours, for potion tints (PotionContents mixes them weighted by amplifier + 1)
EFFECT = {'speed': 0x33EBFF, 'slowness': 0x8BAFE0, 'haste': 0xD9C043, 'mining_fatigue': 0x4A4217,
          'strength': 0xFFC700, 'instant_health': 0xF82423, 'instant_damage': 0xA9656A, 'jump_boost': 0xFDFF84,
          'nausea': 0x551D4A, 'regeneration': 0xCD5CAB, 'resistance': 0x9146F0, 'fire_resistance': 0xFF9900,
          'water_breathing': 0x98DAC0, 'invisibility': 0xF6F6F6, 'blindness': 0x1F1F23, 'night_vision': 0xC2FF66,
          'hunger': 0x587653, 'weakness': 0x484D48, 'poison': 0x87A363, 'wither': 0x736156,
          'health_boost': 0xF87D23, 'absorption': 0x2552A5, 'saturation': 0xF82423, 'glowing': 0x94A061,
          'levitation': 0xCEFFFF, 'luck': 0x59C106, 'unluck': 0xC0A44D, 'slow_falling': 0xF3CFB9,
          'conduit_power': 0x1DC2D1, 'dolphins_grace': 0x88A3BE, 'bad_omen': 0x0B6138,
          'hero_of_the_village': 0x44FF44, 'darkness': 0x292721, 'trial_omen': 0x16A6A6, 'raid_omen': 0xDE4058,
          'wind_charged': 0xBDC9FF, 'weaving': 0x78695A, 'oozing': 0x99FFA3, 'infested': 0x8C9B8C}
POTION = {'healing': ['instant_health'], 'harming': ['instant_damage'], 'leaping': ['jump_boost'],
          'swiftness': ['speed'], 'turtle_master': ['slowness', 'resistance']}


def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return {'x': ((1, 0, 0), (0, c, -s), (0, s, c)), 'y': ((c, 0, s), (0, 1, 0), (-s, 0, c)),
            'z': ((c, -s, 0), (s, c, 0), (0, 0, 1))}[axis]


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def _mv(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


# affine transforms are (3x3 matrix, translation); xf(a, b) applies b first
IDENT = (((1, 0, 0), (0, 1, 0), (0, 0, 1)), (0, 0, 0))


def xf(*parts):
    out = IDENT
    for b in parts:
        out = (_mm(out[0], b[0]), tuple(x + y for x, y in zip(_mv(out[0], b[1]), out[1])))
    return out


def move(x, y, z):
    return (IDENT[0], (x, y, z))


def scale(x, y, z):
    return (((x, 0, 0), (0, y, 0), (0, 0, z)), (0, 0, 0))


def rotate(axis, deg):
    return (_rot(axis, deg), (0, 0, 0))


def pose(x, y, z, rx=0, ry=0, rz=0):
    """ModelPart pose: offset, then rotationZYX (degrees)."""
    return xf(move(x, y, z), rotate('z', rz), rotate('y', ry), rotate('x', rx))


def quat(q):
    x, y, z, w = q
    return (((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
             (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
             (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y))), (0, 0, 0))


def transformation(t):
    """An item definition's `transformation` (in blocks) as an affine transform in model pixels."""
    if not t:
        return IDENT
    if isinstance(t, list):  # a 4x4 matrix, row-major
        m = tuple(tuple(t[r * 4 + c] for c in range(3)) for r in range(3))
        return (m, tuple(t[r * 4 + 3] * 16 for r in range(3)))
    tr = [v * 16 for v in t.get('translation', (0, 0, 0))]
    return xf(move(*tr), quat(t.get('left_rotation', (0, 0, 0, 1))), scale(*t.get('scale', (1, 1, 1))),
              quat(t.get('right_rotation', (0, 0, 0, 1))))


def asset(ref, kind, ext):
    """A resource pack file (pack first, then vanilla): asset('minecraft:block/stone', 'textures', '.png')."""
    ns, p = ref.split(':', 1) if ':' in ref else ('minecraft', ref)
    for base in (RP, VANILLA):
        f = os.path.join(base, ns, kind, p + ext)
        if os.path.exists(f):
            return f
    return None


_TEX = {}


def texture(path):
    if path not in _TEX:
        _TEX[path] = first_frame(Image.open(path).convert('RGBA'))
    return _TEX[path]


def entity_texture(name):
    f = asset(name, 'textures', '.png')
    return texture(f) if f else None


class Scene:
    """Faces to draw. A face is a texture rectangle uv = (u0, v0, u1, v1) in texture pixels (reversed
    for a mirrored face) laid on the parallelogram p0 -> p0 + eu (along u), p0 -> p0 + ev (along v)."""

    def __init__(self):
        self.faces = []

    def face(self, t, tex, p0, eu, ev, uv, tint=None, shade=True):
        m, _ = t
        self.faces.append((tex, xf(t, move(*p0))[1], _mv(m, eu), _mv(m, ev), uv, tint, shade))

    def cuboid(self, t, tex, tsize, uv, pos, size, grow=0.0, mirror=False, tint=None):
        """A ModelPart cube: texture offset uv, box pos/size in model pixels, with the game's box UV
        layout (tsize is the size the model declares for its texture)."""
        u, v = uv
        dx, dy, dz = size
        x0, y0, z0 = pos[0] - grow, pos[1] - grow, pos[2] - grow
        x1, y1, z1 = pos[0] + dx + grow, pos[1] + dy + grow, pos[2] + dz + grow
        if mirror:
            x0, x1 = x1, x0
        sx, sy = tex.width / tsize[0], tex.height / tsize[1]
        for rect, p0, eu, ev in (
                ((u + dz, v, u + dz + dx, v + dz), (x0, y0, z1), (x1 - x0, 0, 0), (0, 0, z0 - z1)),  # -y
                ((u + dz + dx, v, u + dz + 2 * dx, v + dz), (x0, y1, z1), (x1 - x0, 0, 0), (0, 0, z0 - z1)),  # +y
                ((u, v + dz, u + dz, v + dz + dy), (x0, y0, z1), (0, 0, z0 - z1), (0, y1 - y0, 0)),  # -x
                ((u + dz, v + dz, u + dz + dx, v + dz + dy), (x0, y0, z0), (x1 - x0, 0, 0), (0, y1 - y0, 0)),  # -z
                ((u + dz + dx, v + dz, u + 2 * dz + dx, v + dz + dy), (x1, y0, z0), (0, 0, z1 - z0), (0, y1 - y0, 0)),  # +x
                ((u + 2 * dz + dx, v + dz, u + 2 * dz + 2 * dx, v + dz + dy), (x1, y0, z1), (x0 - x1, 0, 0), (0, y1 - y0, 0))):  # +z
            if rect[0] == rect[2] or rect[1] == rect[3]:
                continue
            self.face(t, tex, p0, eu, ev, (rect[0] * sx, rect[1] * sy, rect[2] * sx, rect[3] * sy), tint)


def _shade(n, yaw, light):
    """Brightness of a face with world normal n (unit, facing the viewer): 'side' light matches
    iso_cube (top 1.0, left 0.8, right 0.62); 'front' light (gui_light: front) lights what faces you."""
    ny = n[1]
    hx = _mv(_rot('y', yaw), n)[0]
    horiz = math.sqrt(max(0.0, 1 - ny * ny))
    if light == 'front':
        facing = horiz - abs(hx)  # 1 for a face turned to the viewer, 0 for one seen edge-on
        return min(1.0, 0.72 + 0.28 * max(0.0, ny) + 0.28 * facing)
    sh = 0.71 - 0.127 * (hx / horiz if horiz > 1e-9 else 0)
    return (ny if ny > 0 else -0.5 * ny) + horiz * sh


def render(scene, rotation=(30, 225, 0), scl=0.625, translation=(0, 0, 0), light='side', center=None):
    """Draw a scene the way the inventory shows an item with this GUI display transform. center=None
    centres the model's bounding box (for models the game places by other means); otherwise the
    point `center` (model pixels) goes to the middle of the slot, moved by `translation`."""
    rx, ry, rz = rotation
    if rx == 30 and rz == 0 and ry % 90 == 45:
        rx = ISO_PITCH
    view = _mm(_rot('x', rx), _mm(_rot('y', ry), _rot('z', rz)))
    N = SIZE * SS
    k = PX * SS * scl
    faces = []
    for tex, p0, eu, ev, uv, tint, shade in scene.faces:
        a, u, w = _mv(view, p0), _mv(view, eu), _mv(view, ev)
        n = (ev[1] * eu[2] - ev[2] * eu[1], ev[2] * eu[0] - ev[0] * eu[2], ev[0] * eu[1] - ev[1] * eu[0])
        ln = math.sqrt(sum(c * c for c in n))
        if ln < 1e-9:
            continue
        n = tuple(c / ln for c in n)
        if _mv(view, n)[2] < 0:
            n = tuple(-c for c in n)
        f = _shade(n, ry, light) if shade else 1.0
        col = (f, f, f) if tint is None else tuple(f * c / 255 for c in tint)
        faces.append([a[0] * k, -a[1] * k, u[0] * k, -u[1] * k, w[0] * k, -w[1] * k, a[2], u[2], w[2], tex, uv, col])
    if not faces:
        return None
    xs = [f[0] + dx for f in faces for dx in (0, f[2], f[4], f[2] + f[4])]
    ys = [f[1] + dy for f in faces for dy in (0, f[3], f[5], f[3] + f[5])]
    if center is None:
        ox, oy = N / 2 - (min(xs) + max(xs)) / 2, N / 2 - (min(ys) + max(ys)) / 2
    else:
        c = _mv(view, center)
        ox = N / 2 - c[0] * k + translation[0] * PX * SS
        oy = N / 2 + c[1] * k - translation[1] * PX * SS
    # too big for the slot (the dragon head): shrink it to fit, centred
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    fit = 1.0
    if min(xs) + ox < 0 or max(xs) + ox > N or min(ys) + oy < 0 or max(ys) + oy > N:
        fit = min(1.0, N / span)
        ox, oy = N / 2 - (min(xs) + max(xs)) / 2 * fit, N / 2 - (min(ys) + max(ys)) / 2 * fit
    for f in faces:
        for i in range(6):
            f[i] *= fit
        f[0] += ox
        f[1] += oy
    buf = bytearray(N * N * 4)
    zb = [-1e30] * (N * N)
    solid, clear = [], []
    for i, f in enumerate(faces):
        tex, uv = f[9], f[10]
        lo_u, hi_u = sorted((uv[0], uv[2]))
        lo_v, hi_v = sorted((uv[1], uv[3]))
        region = tex.crop((int(lo_u), int(lo_v), max(int(lo_u) + 1, int(math.ceil(hi_u))),
                           max(int(lo_v) + 1, int(math.ceil(hi_v)))))
        alpha = region.getchannel('A').getextrema()
        if alpha[1] == 0:
            continue
        f[6] += i * 1e-4  # coplanar faces: the one drawn later wins, like the game's depth test
        (clear if 0 < alpha[0] < 255 or (alpha[0] == 0 and 0 < alpha[1] < 255) else solid).append(f)
    clear.sort(key=lambda f: f[6] + (f[7] + f[8]) / 2)
    for f in solid:
        _raster(buf, zb, N, f, False)
    for f in clear:
        _raster(buf, zb, N, f, True)
    im = Image.frombytes('RGBA', (N, N), bytes(buf))
    return im.resize((SIZE, SIZE), Image.LANCZOS)


def _raster(buf, zb, N, f, blend):
    ax, ay, ux, uy, wx, wy, d0, du, dv, tex, uv, col = f
    det = ux * wy - uy * wx
    if abs(det) < 1e-6:
        return
    px = tex.load()
    u0, v0, u1, v1 = uv
    umin, umax = int(math.floor(min(u0, u1))), int(math.ceil(max(u0, u1))) - 1
    vmin, vmax = int(math.floor(min(v0, v1))), int(math.ceil(max(v0, v1))) - 1
    umax, vmax = min(umax, tex.width - 1), min(vmax, tex.height - 1)
    umin, vmin = max(0, min(umin, umax)), max(0, min(vmin, vmax))
    cr, cg, cb = col
    xs = (ax, ax + ux, ax + wx, ax + ux + wx)
    ys = (ay, ay + uy, ay + wy, ay + uy + wy)
    xa0, xb0 = max(0, int(math.floor(min(xs)))), min(N - 1, int(math.ceil(max(xs))))
    ya0, yb0 = max(0, int(math.floor(min(ys)))), min(N - 1, int(math.ceil(max(ys))))
    inv = 1.0 / det
    bs, bt = wy * inv, -uy * inv
    for y in range(ya0, yb0 + 1):
        yc = y + 0.5 - ay
        as_ = (-ax * wy - yc * wx) * inv
        at = (ux * yc + uy * ax) * inv
        lo, hi = xa0 + 0.5, xb0 + 0.5
        for a, b in ((as_, bs), (at, bt)):
            if abs(b) < 1e-12:
                if not 0 <= a < 1:
                    lo, hi = 1, 0
            else:
                e0, e1 = -a / b, (1 - a) / b
                if e0 > e1:
                    e0, e1 = e1, e0
                lo, hi = max(lo, e0), min(hi, e1)
        if lo > hi:
            continue
        row = y * N
        for x in range(max(xa0, int(math.ceil(lo - 0.5))), min(xb0, int(math.floor(hi - 0.5))) + 1):
            xc = x + 0.5
            s = min(max(as_ + bs * xc, 0.0), 0.999999)
            t = min(max(at + bt * xc, 0.0), 0.999999)
            d = d0 + s * du + t * dv
            i = row + x
            if d < zb[i]:
                continue
            tu = min(max(int(math.floor(u0 + s * (u1 - u0))), umin), umax)
            tv = min(max(int(math.floor(v0 + t * (v1 - v0))), vmin), vmax)
            r, g, b, a = px[tu, tv]
            if a == 0:
                continue
            r, g, b = min(255, int(r * cr)), min(255, int(g * cg)), min(255, int(b * cb))
            j = i * 4
            if blend and a < 255:
                fa = a / 255
                da = buf[j + 3] / 255
                oa = fa + da * (1 - fa)
                for c, v in ((0, r), (1, g), (2, b)):
                    buf[j + c] = int((v * fa + buf[j + c] * da * (1 - fa)) / oa)
                buf[j + 3] = int(oa * 255)
            else:
                buf[j:j + 4] = bytes((r, g, b, 255 if not blend else a))
                zb[i] = d


# ---- block models (elements), for blocks that aren't plain cubes
_MODELS = {}


def block_model(ref):
    """A model with its parents merged: textures, elements, display, gui_light, parent chain."""
    ref = ref if ':' in ref else 'minecraft:' + ref
    if ref in _MODELS:
        return _MODELS[ref]
    f = asset(ref, 'models', '.json')
    m = None
    if f:
        d = json.load(open(f, encoding='utf-8'))
        par = block_model(d['parent']) if d.get('parent') else None
        m = {'textures': dict(par['textures']) if par else {}, 'elements': par['elements'] if par else None,
             'display': dict(par['display']) if par else {}, 'gui_light': par['gui_light'] if par else 'side',
             'chain': [ref] + (par['chain'] if par else [d['parent']] if d.get('parent') else [])}
        m['textures'].update({k: (v.get('sprite') if isinstance(v, dict) else v)
                              for k, v in d.get('textures', {}).items()})
        if 'elements' in d:
            m['elements'] = d['elements']
        m['display'].update(d.get('display', {}))
        m['gui_light'] = d.get('gui_light', m['gui_light'])
    _MODELS[ref] = m
    return m


def model_texture(m, key):
    v = key
    for _ in range(10):
        v = m['textures'].get(v.lstrip('#'))
        if not isinstance(v, str) or not v.startswith('#'):
            break
    return asset(v, 'textures', '.png') if isinstance(v, str) else None


def flat_model(m):
    return any(c.endswith('builtin/generated') for c in m['chain'])


def plain_cube(m):
    return all(e.get('from') == [0, 0, 0] and e.get('to') == [16, 16, 16] and not e.get('rotation')
               for e in m['elements'])


def cube_faces(node):
    """Texture files of the up, north and east faces of a plain cube model, or None."""
    if node.get('type', '').split(':')[-1] != 'model' or not node.get('model'):
        return None
    m = block_model(node['model'])
    if not m or flat_model(m) or not m['elements'] or not plain_cube(m):
        return None
    faces = {}
    for el in m['elements']:
        for name, face in el.get('faces', {}).items():
            path = model_texture(m, face.get('texture', ''))
            if path:
                faces.setdefault(name, (path, face.get('uv'), face.get('rotation', 0)))
    out = tuple(faces.get(n) for n in ('up', 'north', 'east'))
    return out if all(out) else None


def face_image(im, uv, rotation):
    """A cube face's texture as the model lays it: its uv rectangle (reversed = mirrored), turned
    clockwise by the face's rotation."""
    im = first_frame(im.convert('RGBA'))
    if uv and list(uv) != [0, 0, 16, 16]:
        s = im.width / 16
        u0, v0, u1, v1 = uv
        im = im.crop((int(min(u0, u1) * s), int(min(v0, v1) * s), int(max(u0, u1) * s), int(max(v0, v1) * s)))
        if u0 > u1:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        if v0 > v1:
            im = im.transpose(Image.FLIP_TOP_BOTTOM)
    turn = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}.get(rotation % 360)
    return im.transpose(turn) if turn else im


# face corners (top-left, top-right, bottom-left) as seen from outside, texture upright
FACE = {'north': lambda a, b: ((b[0], b[1], a[2]), (a[0], b[1], a[2]), (b[0], a[1], a[2])),
        'south': lambda a, b: ((a[0], b[1], b[2]), (b[0], b[1], b[2]), (a[0], a[1], b[2])),
        'west': lambda a, b: ((a[0], b[1], a[2]), (a[0], b[1], b[2]), (a[0], a[1], a[2])),
        'east': lambda a, b: ((b[0], b[1], b[2]), (b[0], b[1], a[2]), (b[0], a[1], b[2])),
        'up': lambda a, b: ((a[0], b[1], a[2]), (b[0], b[1], a[2]), (a[0], b[1], b[2])),
        'down': lambda a, b: ((a[0], a[1], b[2]), (b[0], a[1], b[2]), (a[0], a[1], a[2]))}
DEFAULT_UV = {'north': lambda a, b: (16 - b[0], 16 - b[1], 16 - a[0], 16 - a[1]),
              'south': lambda a, b: (a[0], 16 - b[1], b[0], 16 - a[1]),
              'west': lambda a, b: (a[2], 16 - b[1], b[2], 16 - a[1]),
              'east': lambda a, b: (16 - b[2], 16 - b[1], 16 - a[2], 16 - a[1]),
              'up': lambda a, b: (a[0], a[2], b[0], b[2]),
              'down': lambda a, b: (a[0], 16 - b[2], b[0], 16 - a[2])}


def element_rotation(r):
    if not r:
        return IDENT
    o = r.get('origin', (8, 8, 8))
    if 'axis' in r:
        rot = rotate(r['axis'], r.get('angle', 0))
        if r.get('rescale') and r.get('angle'):
            f = 1 / math.cos(math.radians(22.5 if abs(r['angle']) == 22.5 else 45))
            rot = xf(scale(*(1 if a == r['axis'] else f for a in 'xyz')), rot)
    else:
        rot = xf(rotate('x', r.get('x', 0)), rotate('y', r.get('y', 0)), rotate('z', r.get('z', 0)))
    return xf(move(*o), rot, move(-o[0], -o[1], -o[2]))


def add_model(scene, m, t=IDENT, tints=()):
    for el in m['elements'] or ():
        a, b = el['from'], el['to']
        et = xf(t, element_rotation(el.get('rotation')))
        for name, face in el.get('faces', {}).items():
            path = model_texture(m, face.get('texture', ''))
            if not path or name not in FACE:
                continue
            tex = texture(path)
            tl, tr, bl = FACE[name](a, b)
            br = tuple(tr[i] + bl[i] - tl[i] for i in range(3))
            corner, right, down = {0: (tl, tr, bl), 90: (tr, br, tl), 180: (br, bl, tr),
                                   270: (bl, tl, br)}[face.get('rotation', 0) % 360]
            eu = tuple(right[i] - corner[i] for i in range(3))
            ev = tuple(down[i] - corner[i] for i in range(3))
            uv = face.get('uv') or DEFAULT_UV[name](a, b)
            s = tex.width / 16
            ti = face.get('tintindex', -1)
            tint = tints[ti] if 0 <= ti < len(tints) else None
            scene.face(et, tex, corner, eu, ev, tuple(c * s for c in uv), tint, el.get('shade', True))


def display(m, default=((30, 225, 0), (0, 0, 0), 0.625)):
    g = (m or {}).get('display', {}).get('gui')
    if not g:
        return default
    return tuple(g.get('rotation', (0, 0, 0))), tuple(g.get('translation', (0, 0, 0))), g.get('scale', (1, 1, 1))[0]


def rgb(v):
    if isinstance(v, dict):
        v = v.get('rgb')
    if isinstance(v, list):
        v = (int(v[0] * 255) << 16) | (int(v[1] * 255) << 8) | int(v[2] * 255)
    if not isinstance(v, int):
        return None
    return ((v >> 16) & 255, (v >> 8) & 255, v & 255)


def potion_colour(pc, default):
    if isinstance(pc, str):
        pc = {'potion': pc}
    if not isinstance(pc, dict):
        return default
    if 'custom_color' in pc:
        return pc['custom_color']
    effects = list(pc.get('custom_effects', []))
    base = pc.get('potion', '').split(':')[-1]
    base = re.sub(r'^(long|strong)_', '', base)
    effects += [{'id': e} for e in POTION.get(base, [base] if base in EFFECT else [])]
    r = g = b = n = 0
    for e in effects:
        c = EFFECT.get(e.get('id', '').split(':')[-1])
        if c is None or e.get('show_particles') is False:
            continue
        w = e.get('amplifier', 0) + 1
        r, g, b, n = r + w * (c >> 16), g + w * ((c >> 8) & 255), b + w * (c & 255), n + w
    return default if not n else (r // n << 16) | (g // n << 8) | b // n


def colormap(name, temperature, downfall):
    im = entity_texture('colormap/' + name)
    if im is None:
        return None
    t = min(max(temperature, 0.0), 1.0)
    d = min(max(downfall, 0.0), 1.0) * t
    return im.getpixel((int((1 - t) * 255), int((1 - d) * 255)))[:3]


def tint(src, comps):
    """The colour of an item definition tint source for this item (its default when it doesn't vary)."""
    kind = src.get('type', '').split(':')[-1]
    if kind == 'constant':
        return rgb(src.get('value'))
    if kind == 'dye':
        return rgb(comps.get('dyed_color', src.get('default')))
    if kind == 'potion':
        return rgb(potion_colour(comps.get('potion_contents'), src.get('default')))
    if kind == 'map_color':
        return rgb(comps.get('map_color', src.get('default')))
    if kind == 'grass':
        return colormap('grass', src.get('temperature', 0.5), src.get('downfall', 1.0))
    if kind == 'firework':
        cols = (comps.get('firework_explosion') or {}).get('colors') or []
        if cols:
            cs = [rgb(c) for c in cols]
            return tuple(sum(c[i] for c in cs) // len(cs) for i in range(3))
    return rgb(src.get('default'))


def flat_icon(m, tints):
    """An item/generated model: its layers stacked, each tinted like the game tints it."""
    layers = []
    i = 0
    while 'layer%d' % i in m['textures']:
        path = model_texture(m, 'layer%d' % i)
        if path:
            layers.append((texture(path), tints[i] if i < len(tints) else None))
        i += 1
    if not layers:
        return None
    w = max(t.width for t, _ in layers)
    out = Image.new('RGBA', (w, w), (0, 0, 0, 0))
    for tex, col in layers:
        tex = tex.resize((w, w), Image.NEAREST) if tex.width != w else tex.copy()
        if col:
            px = tex.load()
            for y in range(w):
                for x in range(w):
                    r, g, b, a = px[x, y]
                    px[x, y] = (r * col[0] // 255, g * col[1] // 255, b * col[2] // 255, a)
        out.alpha_composite(tex)
    return upscale(out)


def model_icon(item, node):
    """Icon for a `model` or `composite` item model node, or None to use the plain cube/texture icon."""
    comps = item.get('components', {})
    parts = node.get('models', []) if node.get('type', '').endswith('composite') else [node]
    parts = [(p, block_model(p['model'])) for p in parts if p.get('type', '').endswith(':model') and p.get('model')]
    parts = [(p, m) for p, m in parts if m]
    if not parts:
        return None
    node0, m0 = parts[0]
    tints = [tint(s, comps) for s in node0.get('tints', [])]
    if flat_model(m0):
        layered = 'layer1' in m0['textures'] or any(tints)
        return flat_icon(m0, tints) if layered and len(parts) == 1 else None
    if not m0['elements'] or (len(parts) == 1 and plain_cube(m0)):
        return None
    scene = Scene()
    for p, m in parts:
        if m['elements'] and not flat_model(m):
            add_model(scene, m, transformation(p.get('transformation')), [tint(s, comps) for s in p.get('tints', [])])
    rot, tr, scl = display(m0)
    return render(scene, rot, scl, tr, m0['gui_light'], center=(8, 8, 8))


# ---- entity-rendered items (item definition type "minecraft:special")
def patterned(base, pattern_dir, base_colour, layers):
    """A banner or shield texture: the base, the base colour, then each pattern, tinted by dye."""
    out = base.copy()
    for pattern, colour in [('minecraft:base', base_colour)] + layers:
        asset_id = pattern
        ns, p = pattern.split(':', 1) if ':' in pattern else ('minecraft', pattern)
        for data in (PACK_DATA, VANILLA_DATA):
            f = os.path.join(data, ns, 'banner_pattern', p + '.json')
            if os.path.exists(f):
                asset_id = json.load(open(f, encoding='utf-8')).get('asset_id', pattern)
                break
        ans, ap = asset_id.split(':', 1) if ':' in asset_id else ('minecraft', asset_id)
        tex = entity_texture('%s:entity/%s/%s' % (ans, pattern_dir, ap))
        if tex is None:
            continue
        tex = tex.resize(out.size, Image.NEAREST) if tex.size != out.size else tex.copy()
        col = rgb(DYE.get(colour, 0xFFFFFF))
        px = tex.load()
        for y in range(tex.height):
            for x in range(tex.width):
                r, g, b, a = px[x, y]
                px[x, y] = (r * col[0] // 255, g * col[1] // 255, b * col[2] // 255, a)
        out.alpha_composite(tex)
    return out


def pattern_layers(comps):
    return [(l.get('pattern', ''), l.get('color', 'white')) for l in comps.get('banner_patterns') or []
            if isinstance(l, dict) and isinstance(l.get('pattern'), str)]


MOB_Y_DOWN = xf(move(8, 0, 8), scale(1, -1, -1))  # entity model space -> item space (head, statue)


def special_chest(scene, spec, comps):
    name = spec.get('texture', 'minecraft:normal')
    ns, p = name.split(':', 1) if ':' in name else ('minecraft', name)
    tex = entity_texture('%s:entity/chest/%s' % (ns, p))
    if tex is None:
        return False
    s = (64, 64)
    scene.cuboid(IDENT, tex, s, (0, 19), (1, 0, 1), (14, 10, 14))
    scene.cuboid(pose(0, 9, 1), tex, s, (0, 0), (1, 0, 0), (14, 5, 14))
    scene.cuboid(pose(0, 9, 1), tex, s, (0, 0), (7, -2, 14), (2, 4, 1))
    return True


def special_shulker_box(scene, spec, comps):
    name = spec.get('texture', 'minecraft:shulker')
    ns, p = name.split(':', 1) if ':' in name else ('minecraft', name)
    tex = entity_texture('%s:entity/shulker/%s' % (ns, p))
    if tex is None:
        return False
    t = xf(move(8, 24, 8), scale(1, -1, -1), pose(0, 24, 0))
    scene.cuboid(t, tex, (64, 64), (0, 28), (-8, -8, -8), (16, 8, 16))
    scene.cuboid(t, tex, (64, 64), (0, 0), (-8, -16, -8), (16, 12, 16))
    return True


HEADS = {'skeleton': ('entity/skeleton/skeleton', (64, 32), False),
         'wither_skeleton': ('entity/skeleton/wither_skeleton', (64, 32), False),
         'creeper': ('entity/creeper/creeper', (64, 32), False),
         'zombie': ('entity/zombie/zombie', (64, 64), True),
         'player': ('entity/player/wide/steve', (64, 64), True),
         'piglin': ('entity/piglin/piglin', (64, 64), False),
         'dragon': ('entity/enderdragon/dragon', (256, 256), False)}


def special_head(scene, spec, comps):
    kind = spec.get('kind', 'player') if not spec.get('type', '').endswith('player_head') else 'player'
    path, size, hat = HEADS.get(kind, (None, None, None))
    if spec.get('texture'):
        path = spec['texture']
    tex = entity_texture(path) if path else None
    if tex is None:
        return False
    t = MOB_Y_DOWN
    if kind == 'dragon':  # DragonHeadModel, scaled to 3/4
        t = xf(t, scale(0.75, 0.75, 0.75), pose(0, -7.99, 0))
        c = lambda uv, p, s, mirror=False: scene.cuboid(t, tex, size, uv, p, s, mirror=mirror)
        c((176, 44), (-6, -1, -24), (12, 5, 16))
        c((112, 30), (-8, -8, -10), (16, 16, 16))
        c((0, 0), (-5, -12, -4), (2, 4, 6), True)
        c((112, 0), (-5, -3, -22), (2, 2, 4), True)
        c((0, 0), (3, -12, -4), (2, 4, 6))
        c((112, 0), (3, -3, -22), (2, 2, 4))
        scene.cuboid(xf(t, pose(0, 4, -8, rx=math.degrees(0.2))), tex, size, (176, 65), (-6, 0, -16), (12, 4, 16))
        return True
    if kind == 'piglin':
        scene.cuboid(t, tex, size, (0, 0), (-5, -8, -4), (10, 8, 8))
        scene.cuboid(t, tex, size, (31, 1), (-2, -4, -5), (4, 4, 1))
        scene.cuboid(t, tex, size, (2, 4), (2, -2, -5), (1, 2, 1))
        scene.cuboid(t, tex, size, (2, 0), (-3, -2, -5), (1, 2, 1))
        scene.cuboid(xf(t, pose(4.5, -6, 0, rz=-30)), tex, size, (51, 6), (0, 0, -2), (1, 5, 4))
        scene.cuboid(xf(t, pose(-4.5, -6, 0, rz=30)), tex, size, (39, 6), (-1, 0, -2), (1, 5, 4))
        return True
    scene.cuboid(t, tex, size, (0, 0), (-4, -8, -4), (8, 8, 8))
    if hat:
        scene.cuboid(t, tex, size, (32, 0), (-4, -8, -4), (8, 8, 8), grow=0.25)
    return True


def special_banner(scene, spec, comps):
    base = entity_texture('entity/banner/banner_base')
    if base is None:
        return False
    tex = patterned(base, 'banner', spec.get('color', 'white'), pattern_layers(comps))
    t = xf(move(8, 0, 8), scale(2 / 3, -2 / 3, -2 / 3))
    scene.cuboid(t, tex, (64, 64), (44, 0), (-1, -42, -1), (2, 42, 2))
    scene.cuboid(t, tex, (64, 64), (0, 42), (-10, -44, -1), (20, 2, 2))
    scene.cuboid(xf(t, pose(0, -44, 0)), tex, (64, 64), (0, 0), (-10, 0, -2), (20, 40, 1))
    return True


def special_shield(scene, spec, comps):
    layers = pattern_layers(comps)
    if layers or comps.get('base_color'):
        tex = patterned(entity_texture('entity/shield/shield_base'), 'shield', comps.get('base_color', 'white'), layers)
    else:
        tex = entity_texture('entity/shield/shield_base_nopattern')
    if tex is None:
        return False
    t = scale(1, -1, -1)
    scene.cuboid(t, tex, (64, 64), (0, 0), (-6, -11, -2), (12, 22, 1))
    scene.cuboid(t, tex, (64, 64), (26, 0), (-1, -3, -1), (2, 6, 6))
    return 'centre'  # placed by its bounding box: the game's offsets for it assume a different origin


def special_decorated_pot(scene, spec, comps):
    base = entity_texture('entity/decorated_pot/decorated_pot_base')
    plain = entity_texture('entity/decorated_pot/decorated_pot_side')
    if base is None or plain is None:
        return False
    sides = []
    for d in (comps.get('pot_decorations') or [])[:4]:
        name = str(d).split(':')[-1]
        pat = entity_texture('entity/decorated_pot/' + name.replace('_pottery_sherd', '_pottery_pattern')) \
            if name.endswith('_pottery_sherd') else None
        sides.append(pat or plain)
    sides += [plain] * (4 - len(sides))
    neck = pose(0, 37, 16, rx=180)
    scene.cuboid(neck, base, (32, 32), (0, 0), (4, 17, 4), (8, 3, 8), grow=-0.1)
    scene.cuboid(neck, base, (32, 32), (0, 5), (5, 20, 5), (6, 1, 6), grow=0.2)
    scene.cuboid(pose(1, 16, 1), base, (32, 32), (-14, 13), (0, 0, 0), (14, 0, 14))
    scene.cuboid(pose(1, 0, 1), base, (32, 32), (-14, 13), (0, 0, 0), (14, 0, 14))
    # sides, in PotDecorations order: back, left, right, front (a plane with only its north face)
    for tex, t in zip(sides, (pose(15, 16, 1, rz=180), pose(1, 16, 1, ry=-90, rz=180),
                              pose(15, 16, 15, ry=90, rz=180), pose(1, 16, 15, rx=180))):
        s = tex.width / 16
        scene.face(t, tex, (0, 0, 0), (14, 0, 0), (0, 16, 0), (1 * s, 0, 15 * s, 16 * s))
    return True


def special_copper_golem_statue(scene, spec, comps):
    path = spec.get('texture', 'minecraft:textures/entity/copper_golem/copper_golem.png')
    ns, p = path.split(':', 1) if ':' in path else ('minecraft', path)
    f = next((os.path.join(b, ns, p) for b in (RP, VANILLA) if os.path.exists(os.path.join(b, ns, p))), None)
    if not f:
        return False
    tex, s = texture(f), (64, 64)
    # CopperGolemModel, standing (entity space, y down), stood up in item space
    t = xf(move(8, 24, 8), scale(1, -1, -1))
    body = xf(t, pose(0, 19, 0))
    head = xf(body, pose(0, -6, 0))
    scene.cuboid(body, tex, s, (0, 15), (-4, -6, -3), (8, 6, 6))
    scene.cuboid(head, tex, s, (0, 0), (-4, -5, -5), (8, 5, 10), grow=0.015)
    scene.cuboid(head, tex, s, (56, 0), (-1, -2, -6), (2, 3, 2))
    scene.cuboid(head, tex, s, (37, 8), (-1, -9, -1), (2, 4, 2), grow=-0.015)
    scene.cuboid(head, tex, s, (39, 0), (-2, -13, -2), (4, 4, 4), grow=-0.015)
    scene.cuboid(xf(body, pose(-4, -5, 0)), tex, s, (36, 16), (-3, -1, -2), (3, 10, 4))
    scene.cuboid(xf(body, pose(4, -5, 0)), tex, s, (50, 16), (0, -1, -2), (3, 10, 4))
    scene.cuboid(xf(t, pose(0, 19, 0)), tex, s, (0, 27), (-4, 0, -2), (4, 5, 4))
    scene.cuboid(xf(t, pose(0, 19, 0)), tex, s, (16, 27), (0, 0, -2), (4, 5, 4))
    return 'centre'


def special_conduit(scene, spec, comps):
    tex = entity_texture('entity/conduit/base')
    if tex is None:
        return False
    scene.cuboid(xf(move(8, 8, 8), scale(1, -1, -1)), tex, (32, 16), (0, 0), (-3, -3, -3), (6, 6, 6))
    return True


SPECIAL = {'chest': special_chest, 'conduit': special_conduit, 'shulker_box': special_shulker_box, 'head': special_head,
           'player_head': special_head, 'banner': special_banner, 'shield': special_shield,
           'decorated_pot': special_decorated_pot, 'copper_golem_statue': special_copper_golem_statue}
UNSUPPORTED = set()


def special_icon(item, node):
    """Icon for an item the game draws with an entity renderer, or None to fall back to its base
    model (for special types not drawn here)."""
    spec = node.get('model', {})
    kind = spec.get('type', '').split(':')[-1]
    fn = SPECIAL.get(kind)
    if fn is None:
        UNSUPPORTED.add(kind)
        return None
    scene = Scene()
    placed = fn(scene, spec, item.get('components', {}))
    if not placed:
        return None
    base = block_model(node['base']) if node.get('base') else None
    rot, tr, scl = display(base, ((30, 45, 0), (0, 0, 0), 0.625))
    if kind == 'copper_golem_statue':
        rot = (rot[0], rot[1], 0)  # its z=180 turns the upside-down entity model upright; ours already is
    light = base['gui_light'] if base else 'side'
    return render(scene, rot, scl, tr, light, center=None if placed == 'centre' else (8, 8, 8))


def item_icon(item):
    icon = item.get('icon')
    if not icon:
        return None
    node = icon.get('gui') or {}
    kind = node.get('type', '').split(':')[-1]
    im = None
    if kind == 'special':
        im = special_icon(item, node)
    elif kind in ('model', 'composite'):
        im = model_icon(item, node)
    if im is not None:
        return im
    faces = {k: os.path.join(ROOT, v) for k, v in icon['faces'].items()}
    if icon['kind'] == 'item':
        return upscale(Image.open(faces['layer0']))
    name = item['name'].lower()
    flat_keys = ('cross', 'plant', 'texture')
    for k in flat_keys:
        if k in faces and not any(x in faces for x in ('all', 'side', 'top', 'end')):
            return upscale(tint_if_foliage(Image.open(faces[k]), faces, k))
    def pick(*keys):
        for k in keys:
            if k in faces:
                return Image.open(faces[k])
        return Image.open(next(iter(faces.values())))
    cube = cube_faces(node)
    if cube:  # the model's own up / north / east faces (a crafting table's top is not its front)
        top, front, side = (Image.open(p) for p, _, _ in cube)  # up, north, east
    else:
        top = pick('top', 'end', 'all', 'side', 'wall', 'wool', 'pattern', 'texture', 'particle')
        side = pick('side', 'front', 'all', 'wall', 'wool', 'pattern', 'texture', 'particle', 'top')
        front = pick('front', 'side', 'all', 'wall', 'wool', 'pattern', 'texture', 'particle')
    top, side, front = (tint_if_foliage(top, faces, 'top'), tint_if_foliage(side, faces, 'side'),
                        tint_if_foliage(front, faces, 'front'))
    if cube:
        top, front, side = (face_image(im, uv, rot) for im, (_, uv, rot) in zip((top, front, side), cube))
    height = 0.5 if name.endswith(' slab') else 1.0
    if any(name.endswith(s) for s in (' carpet', ' pressure plate')):
        height = 1 / 16
    # the game's view of a block (display rotation y=225): the east face on the left, the north
    # (front) face on the right, and the top turned so its north edge runs along the right-hand side
    return iso_cube(first_frame(top.convert('RGBA')).transpose(Image.ROTATE_270), side, front, height)


def glyphs():
    sheet = Image.open(os.path.join(RP, 'minecraft', 'textures', 'font', 'custom_emojis.png')).convert('RGBA')
    n = 0
    for r in range(sheet.size[1] // 8):
        for c in range(16):
            g = sheet.crop((c * 8, r * 8, c * 8 + 8, r * 8 + 8))
            if not g.getbbox():
                continue
            code = 'E%03X' % (r * 16 + c)
            # glyphs are white in the font; tint for a light page, keep alpha
            px = g.load()
            for y in range(8):
                for x in range(8):
                    a = px[x, y][3]
                    px[x, y] = (52, 52, 52, a) if a else (0, 0, 0, 0)
            g.resize((64, 64), Image.NEAREST).save(os.path.join(OUT, 'Glyph %s.png' % code))
            n += 1
    return n


# ---------------------------------------------------------------- GUI art
# The pack reskins every container screen. Its station screens (Module:Station) are drawn from
# these textures, so they are cut out here, at 2x (one texture pixel = 2 CSS pixels, the scale
# of minecraft.wiki's 32px slot icons). Output: site/assets/gui/, served as /assets/gui/.
GUI_OUT = os.path.join(ROOT, 'site', 'assets', 'gui')
GUI = os.path.join(RP, 'minecraft', 'textures', 'gui')
VANILLA_TEX = os.path.join(ROOT, 'source', 'vanilla-assets', 'assets', 'minecraft', 'textures')
BAND = 77  # the themed top part of a station screen; the brown player inventory starts below it
PANEL = {'outline': (13, 9, 3), 'light': (127, 102, 77), 'base': (96, 77, 58), 'shadow': (41, 31, 24),
         'slot': (67, 54, 42), 'slot_shadow': (27, 21, 17)}


def tex(*parts):
    """A texture from the pack, falling back to vanilla."""
    for base in (os.path.join(RP, 'minecraft', 'textures'), VANILLA_TEX):
        p = os.path.join(base, *parts)
        if os.path.exists(p):
            return Image.open(p).convert('RGBA')
    raise FileNotFoundError(os.path.join(*parts))


def x2(im):
    return im.resize((im.width * 2, im.height * 2), Image.NEAREST)


def band(name):
    """The station's own top panel (176x77), with its bottom corners rounded like the top ones."""
    im = tex('gui', 'container', name + '.png').crop((0, 0, 176, BAND))
    px = im.load()
    outline = px[2, 0]
    for y in range(3):
        for dx in range(3):
            for x_top, x in ((dx, dx), (175 - dx, 175 - dx)):
                top = px[x_top, y]
                if top[3] == 0:
                    px[x, BAND - 1 - y] = (0, 0, 0, 0)
                elif top == outline:
                    px[x, BAND - 1 - y] = outline
    for x in range(3, 173):
        px[x, BAND - 1] = outline
    return im


def panel(w, h):
    """A plain panel in the pack's inventory palette (vanilla's bevel, recoloured brown)."""
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = {k: v + (255,) for k, v in PANEL.items()}
    d.rectangle((1, 1, w - 2, h - 2), fill=c['base'])
    d.line((2, 0, w - 4, 0), fill=c['outline']); d.line((2, h - 1, w - 3, h - 1), fill=c['outline'])
    d.line((0, 2, 0, h - 4), fill=c['outline']); d.line((w - 1, 3, w - 1, h - 3), fill=c['outline'])
    for p in ((1, 1), (w - 3, 1), (w - 2, 2), (1, h - 3), (2, h - 2), (w - 2, h - 2)):
        im.putpixel(p, c['outline'])
    d.rectangle((2, 1, w - 4, 2), fill=c['light']); d.rectangle((1, 2, 2, h - 4), fill=c['light'])
    d.rectangle((3, h - 3, w - 3, h - 2), fill=c['shadow']); d.rectangle((w - 3, 3, w - 2, h - 3), fill=c['shadow'])
    im.putpixel((3, 3), c['light'])
    im.putpixel((w - 4, h - 4), c['shadow'])
    return im


def slot_frame(im, x, y, size=18):
    """Draw an inventory slot frame whose item area starts at (x, y)."""
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = x - 1, y - 1, x - 2 + size, y - 2 + size
    d.rectangle((x0, y0, x1, y1), fill=PANEL['slot'] + (255,))
    d.line((x0, y0, x1 - 1, y0), fill=PANEL['slot_shadow'] + (255,))
    d.line((x0, y0, x0, y1 - 1), fill=PANEL['slot_shadow'] + (255,))
    d.line((x0 + 1, y1, x1, y1), fill=PANEL['light'] + (255,))
    d.line((x1, y0 + 1, x1, y1), fill=PANEL['light'] + (255,))


def campfire_frames(soul=False):
    """A lit campfire as a 2D icon: the pack's log icon in front of the animated fire, one frame
    per fire frame, stacked vertically (animated with CSS steps())."""
    logs = tex('item', 'soul_campfire.png' if soul else 'campfire.png')
    fire = tex('block', ('soul_' if soul else '') + 'campfire_fire.png')
    n = fire.height // fire.width
    strip = Image.new('RGBA', (16, 16 * n), (0, 0, 0, 0))
    for i in range(n):
        f = fire.crop((0, i * 16, 16, i * 16 + 16)).resize((12, 12), Image.NEAREST)
        strip.alpha_composite(f, (2, i * 16 + 1))
        strip.alpha_composite(logs, (0, i * 16 + 3))
    return strip, n


def gui_assets():
    os.makedirs(GUI_OUT, exist_ok=True)
    out = {}

    def save(im, name):
        x2(im).save(os.path.join(GUI_OUT, name + '.png'))
        out[name] = im.size

    for station, texture in (('crafting', 'crafting_table'), ('oven', 'furnace'), ('kiln', 'smoker'),
                             ('blast', 'blast_furnace'), ('smithing', 'smithing'), ('stonecutter', 'stonecutter')):
        save(band(texture), station)
    for station, sprites in (('oven', 'furnace'), ('kiln', 'smoker'), ('blast', 'blast_furnace')):
        save(tex('gui', 'sprites', 'container', sprites, 'burn_progress.png'), station + '-progress')
        save(tex('gui', 'sprites', 'container', sprites, 'lit_progress.png'), station + '-lit')
    save(tex('gui', 'sprites', 'container', 'stonecutter', 'recipe_selected.png'), 'stonecutter-selected')
    save(tex('gui', 'sprites', 'container', 'stonecutter', 'scroller.png'), 'stonecutter-scroller')

    # Kindling has no screen in the game, so it gets one in the pack's own palette: the item rests
    # on the lit campfire, with the villager screen's arrow (the pack's brown one) to the result.
    k = panel(176, BAND)
    slot_frame(k, 56, 17)
    d = ImageDraw.Draw(k)
    x0, y0 = 111, 30  # large output frame, as the furnace screens draw it
    d.rectangle((x0, y0, x0 + 25, y0 + 25), fill=PANEL['slot'] + (255,))
    d.line((x0, y0, x0 + 24, y0), fill=PANEL['slot_shadow'] + (255,))
    d.line((x0, y0, x0, y0 + 24), fill=PANEL['slot_shadow'] + (255,))
    d.line((x0 + 1, y0 + 25, x0 + 25, y0 + 25), fill=PANEL['light'] + (255,))
    d.line((x0 + 25, y0 + 1, x0 + 25, y0 + 25), fill=PANEL['light'] + (255,))
    arrow = tex('gui', 'container', 'villager.png').crop((186, 38, 208, 53))
    k.alpha_composite(arrow, (80, 35))
    save(k, 'kindling')
    for soul in (False, True):
        strip, n = campfire_frames(soul)
        save(strip, 'soul-campfire' if soul else 'campfire')
        out['campfire_frames'] = n

    # a villager offer, as the trading screen lists it: the pack's button (a nine-slice sprite,
    # border 3) cut to the offer width of 88, and the trade arrow
    button = tex('gui', 'sprites', 'widget', 'button.png')
    offer = Image.new('RGBA', (88, 20), (0, 0, 0, 0))
    offer.alpha_composite(button.crop((0, 0, 85, 20)), (0, 0))
    offer.alpha_composite(button.crop((button.width - 3, 0, button.width, 20)), (85, 0))
    save(offer, 'trade-offer')
    save(tex('gui', 'sprites', 'container', 'villager', 'trade_arrow.png'), 'trade-arrow')

    # hearts from the pack's HUD (pink in this pack), for {{Hp}}
    for h in ('full', 'half', 'container'):
        save(tex('gui', 'sprites', 'hud', 'heart', h + '.png'), 'heart-' + h)

    # the custom font's glyph sheet, white, for tooltips (tinted by CSS mask like the game tints text)
    sheet = tex('font', 'custom_emojis.png')
    x2(sheet).save(os.path.join(GUI_OUT, 'glyphs.png'))
    return out


def glyph_widths():
    """Advance data for each glyph of the custom font: Minecraft uses the rightmost opaque
    column + 1 as a bitmap glyph's width."""
    sheet = tex('font', 'custom_emojis.png')
    widths = {}
    for r in range(sheet.size[1] // 8):
        for c in range(16):
            g = sheet.crop((c * 8, r * 8, c * 8 + 8, r * 8 + 8))
            bb = g.getbbox()
            if bb:
                widths[0xE000 + r * 16 + c] = bb[2]
    return widths


def main():
    os.makedirs(OUT, exist_ok=True)
    print('gui art', len(gui_assets()))
    data = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
    done = skipped = 0
    for key, item in sorted(data['items'].items()):
        fn = os.path.join(OUT, safe(key) + '.png')
        try:
            im = item_icon(item)
        except Exception as e:  # a broken texture should not stop the build
            print('icon failed', key, e)
            im = None
        if im is None:
            skipped += 1
            continue
        im.save(fn)
        done += 1
    extra = os.path.join(ROOT, 'tools', 'extra_textures.txt')
    if os.path.exists(extra):
        for line in open(extra):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            path, _, name = line.partition('=')
            path, name = path.strip(), name.strip()
            faces = [os.path.join(ROOT, x.strip()) for x in path.split('+')]
            if not all(os.path.exists(f) for f in faces):
                continue
            if len(faces) == 3:  # top + left + right: an isometric block icon
                iso_cube(*(first_frame(Image.open(f).convert('RGBA')) for f in faces)).save(os.path.join(OUT, name))
            else:
                upscale(Image.open(faces[0])).save(os.path.join(OUT, name))
    if UNSUPPORTED:
        print('special item renderers not drawn (base model used):', ', '.join(sorted(UNSUPPORTED)))
    print('icons', done, 'no icon', skipped, 'glyphs', glyphs())


if __name__ == '__main__':
    main()
