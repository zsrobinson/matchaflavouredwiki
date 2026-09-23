#!/usr/bin/env python3
"""Build wiki images from pack/vanilla textures into build/images/.

  <Item Name>.png   inventory icon for every item in build/data.json (the file name
                    convention used by Module:Inventory slot and minecraft.wiki's Invicons)
  Glyph EXXX.png    each custom-font glyph from custom_emojis.png (used by {{G}})
  Texture <path>.png  raw textures listed in tools/extra_textures.txt (optional)

Icons are upscaled with nearest-neighbour to 128px so MediaWiki thumbnails stay crisp.
Block items get a simple isometric cube render (slabs are half height).
"""
import json
import os
import re

from PIL import Image

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
    """Isometric cube (like the in-game inventory block render)."""
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
    # top face: u -> down-right, v -> down-left
    blit(top, (ox, oy), k, k * 0.5, -k, k * 0.5, 1.0)
    # left face
    blit(left, (ox - k * n, oy + k * n * 0.5), k, k * 0.5, 0, k, 0.8)
    # right face
    blit(right, (ox, oy + k * n), k, -k * 0.5, 0, k, 0.62)
    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    side = max(canvas.size)
    sq = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    sq.paste(canvas, ((side - canvas.size[0]) // 2, (side - canvas.size[1]) // 2))
    return sq.resize((SIZE, SIZE), Image.LANCZOS)


FOLIAGE = (72, 181, 24)   # plains grass/foliage colour, as the game tints grayscale textures
GRASS = (145, 189, 89)


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
    col = GRASS if 'grass' in base or 'fern' in base else FOLIAGE
    im = first_frame(im.convert('RGBA'))
    px = im.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            r, g, b, a = px[x, y]
            px[x, y] = (r * col[0] // 255, g * col[1] // 255, b * col[2] // 255, a)
    return im


def safe(name):
    return re.sub(r'[\\/:*?"<>|#\[\]{}]', '', name).strip()


def item_icon(item):
    icon = item.get('icon')
    if not icon:
        return None
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
    top = pick('top', 'end', 'all', 'side', 'wall', 'wool', 'pattern', 'texture', 'particle')
    side = pick('side', 'front', 'all', 'wall', 'wool', 'pattern', 'texture', 'particle', 'top')
    front = pick('front', 'side', 'all', 'wall', 'wool', 'pattern', 'texture', 'particle')
    top, side, front = (tint_if_foliage(top, faces, 'top'), tint_if_foliage(side, faces, 'side'),
                        tint_if_foliage(front, faces, 'front'))
    height = 0.5 if name.endswith(' slab') else 1.0
    if any(name.endswith(s) for s in (' carpet', ' pressure plate')):
        height = 1 / 16
    return iso_cube(top, front, side, height)


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


def main():
    os.makedirs(OUT, exist_ok=True)
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
            full = os.path.join(ROOT, path)
            if os.path.exists(full):
                upscale(Image.open(full)).save(os.path.join(OUT, name))
    print('icons', done, 'no icon', skipped, 'glyphs', glyphs())


if __name__ == '__main__':
    main()
