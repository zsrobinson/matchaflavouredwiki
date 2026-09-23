#!/usr/bin/env python3
"""Build wiki images from pack/vanilla textures into build/images/.

  <Item Name>.png   inventory icon for every item in build/data.json (the file name
                    convention used by Module:Inventory slot and minecraft.wiki's Invicons)
  Glyph EXXX.png    each custom-font glyph from custom_emojis.png (used by {{G}})
  Texture <path>.png  raw textures listed in tools/extra_textures.txt (optional)

and into site/assets/gui/: the pack's station screens, progress sprites, villager offer button,
HUD hearts and glyph sheet at 2x, for Module:Station, Module:Tooltip and {{Hp}}.

Icons are upscaled with nearest-neighbour to 128px so MediaWiki thumbnails stay crisp.
Block items get a simple isometric cube render (slabs are half height).
"""
import json
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
            full = os.path.join(ROOT, path)
            if os.path.exists(full):
                upscale(Image.open(full)).save(os.path.join(OUT, name))
    print('icons', done, 'no icon', skipped, 'glyphs', glyphs())


if __name__ == '__main__':
    main()
