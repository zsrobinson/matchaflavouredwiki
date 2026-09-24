"""Pictures that stand for the site outside it (used by tools/export_static.py).

- Share cards: one 1200x630 image per indexable page, which link previews (Discord, Reddit,
  iMessage, X, Slack) show as og:image. The page's item icon sits in an inventory slot on a panel
  in the pack's brown inventory palette, next to its title in the game's font.
- Site icons: the wiki logo's pixel art at exact multiples of its pixels. Google only shows a
  favicon whose size is a multiple of 48px, and the logo's own file is 135x135.

Output depends only on its inputs (title, image bytes, fonts), so an unchanged page gets an
identical card and a deploy uploads only the cards that changed.
"""
import hashlib
import io
import json
import os
import unicodedata

from PIL import Image, ImageDraw

import images  # the pack's palette, panels and textures (tools/images.py)

ROOT = images.ROOT
LOGO = os.path.join(ROOT, 'site', 'assets', 'Wiki.png')
FONT_JSON = os.path.join(ROOT, 'source', 'vanilla-assets', 'assets', 'minecraft', 'font', 'include', 'default.json')
W, H = 1200, 630
PX = 6  # one pixel of the panel and slot art, in card pixels
TEXT = (255, 255, 255)
MUTED = (221, 205, 180)
CARD_DIR = 'og'


# --- the wiki logo -----------------------------------------------------------------
def logo_art():
    """The logo's own 18x17 pixel art. Wiki.png draws it at 6x from (14, 17)."""
    im = Image.open(LOGO).convert('RGBA')
    art = Image.new('RGBA', (18, 17))
    for j in range(17):
        for i in range(18):
            art.putpixel((i, j), im.getpixel((14 + 6 * i + 3, 17 + 6 * j + 3)))
    return art


def site_icons(out):
    """favicon.ico, PNG icons at 48px multiples and the Apple touch icon (linked by ICON_TAGS)."""
    art = logo_art()
    square = Image.new('RGBA', (24, 24), (0, 0, 0, 0))
    square.alpha_composite(art, (3, 4))
    os.makedirs(os.path.join(out, 'assets'), exist_ok=True)
    for size in (48, 96, 192):
        square.resize((size, size), Image.NEAREST).save(os.path.join(out, 'assets', 'icon-%d.png' % size), optimize=True)
    # browsers ask for /favicon.ico whatever the page says
    square.resize((48, 48), Image.NEAREST).save(os.path.join(out, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)])
    # iOS draws a transparent touch icon on black: give it the pack's panel colour
    touch = Image.new('RGBA', (180, 180), images.PANEL['base'] + (255,))
    touch.alpha_composite(art.resize((144, 136), Image.NEAREST), (18, 22))
    touch.convert('RGB').save(os.path.join(out, 'apple-touch-icon.png'), optimize=True)


# what every page's <head> links to, in place of MediaWiki's single 135px favicon
ICON_TAGS = ('<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">\n'
             '<link rel="icon" type="image/png" sizes="96x96" href="/assets/icon-96.png">\n'
             '<link rel="icon" type="image/png" sizes="192x192" href="/assets/icon-192.png">\n'
             '<link rel="apple-touch-icon" href="/apple-touch-icon.png">')


# --- the game's font -----------------------------------------------------------------
_font = None


def font():
    """char -> (glyph image, y offset, advance), from the game's default bitmap fonts."""
    global _font
    if _font is None:
        glyphs = {}
        for p in json.load(open(FONT_JSON))['providers']:
            if p.get('type') != 'bitmap':
                continue
            sheet = images.tex(*('font/' + p['file'].split('font/', 1)[1]).split('/'))
            rows = p['chars']
            cw, ch = sheet.width // len(rows[0]), sheet.height // len(rows)
            scale = p.get('height', 8) / ch
            for r, row in enumerate(rows):
                for c, char in enumerate(row):
                    if char == '\0' or char in glyphs:
                        continue
                    g = sheet.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
                    if scale != 1:
                        g = g.resize((max(1, round(cw * scale)), max(1, round(ch * scale))), Image.NEAREST)
                    bb = g.getbbox()
                    glyphs[char] = (g, 7 - p['ascent'], (bb[2] if bb else 0) + 1)
        glyphs[' '] = (None, 0, 4)
        _font = glyphs
    return _font


def text_width(s):
    f = font()
    return sum(f.get(c, f['?'])[2] for c in s) - 1


def draw_text(card, s, x, y, scale, rgb):
    """Text as the game draws it: each glyph with a shadow one pixel down and right, in a quarter
    of the colour. (x, y) is the top of the line in card pixels."""
    f = font()
    layer = Image.new('RGBA', (text_width(s) + 2, 14), (0, 0, 0, 0))
    for colour, off in ((tuple(v // 4 for v in rgb), 1), (rgb, 0)):
        cx = 0
        for c in s:
            g, dy, adv = f.get(c, f['?'])
            if g is not None:
                layer.paste(Image.new('RGBA', g.size, colour + (255,)), (cx + off, 3 + dy + off), g.split()[3])
            cx += adv
    big = layer.resize((layer.width * scale, layer.height * scale), Image.NEAREST)
    card.alpha_composite(big, (x, y - 3 * scale))


def wrap(s, width, scale):
    """Break s into lines no wider than width card pixels (a word longer than that stays whole)."""
    lines, line = [], ''
    for word in s.split(' '):
        test = (line + ' ' + word).strip()
        if line and text_width(test) * scale > width:
            lines.append(line)
            line = word
        else:
            line = test
    return lines + [line]


# --- cards ----------------------------------------------------------------------------
def pixel_icon(im):
    """An inventory icon (a 16px texture drawn at an integer scale), or None for a render."""
    return im.width == im.height and im.width <= 256 and im.width % 16 == 0


def card(title, image=None, label=None, subtitle=None):
    """A share card: image bytes (the infobox picture) or the wiki logo, the title, a small label
    above it (the page's category) and the site's name at the bottom."""
    c = images.panel(W // PX, H // PX).resize((W, H), Image.NEAREST)
    pic = Image.open(io.BytesIO(image)).convert('RGBA') if image else None
    if pic is None or pixel_icon(pic):
        # an inventory slot, 50 panel pixels square, with the icon at 16 card pixels per texel
        slot = Image.new('RGBA', (52, 52), (0, 0, 0, 0))
        images.slot_frame(slot, 1, 1, size=50)
        c.alpha_composite(slot.resize((52 * PX, 52 * PX), Image.NEAREST), (9 * PX, 26 * PX))
        art = logo_art() if pic is None else pic.resize((16, 16), Image.NEAREST)
        glyph = pic is not None and len({c for _, c in art.getcolors(256) if c[3]}) == 1
        if glyph:
            # a tooltip glyph (an intrinsic's symbol): a one-colour mask the game tints with the
            # text colour, drawn dark for the wiki's light pages; on the card, the title's white,
            # and smaller, since a glyph fills its whole square
            art = Image.composite(Image.new('RGBA', art.size, TEXT + (255,)), art, art.getchannel('A'))
        f = (160 if glyph else 256) // max(art.size)
        art = art.resize((art.width * f, art.height * f), Image.NEAREST)
        cx, cy = 10 * PX + (48 * PX - art.width) // 2, 27 * PX + (48 * PX - art.height) // 2
        c.alpha_composite(art, (cx, cy))
        left = 66 * PX
    else:
        # a render (structure, mob, armor): without its transparent margin, as large as fits on the
        # left, drawn at its own scale
        pic = pic.crop(pic.getchannel('A').getbbox() or (0, 0, pic.width, pic.height))
        box = (480, 510)
        f = min(box[0] / pic.width, box[1] / pic.height)
        f = int(f) if f >= 1 else f
        pic = pic.resize((max(1, round(pic.width * f)), max(1, round(pic.height * f))),
                         Image.NEAREST if f >= 1 else Image.LANCZOS)
        c.alpha_composite(pic, (48 + (box[0] - pic.width) // 2, 60 + (box[1] - pic.height) // 2))
        left = 560
    width = W - left - 8 * PX
    for scale in (7, 6, 5, 4):
        lines = wrap(title, width, scale)
        if len(lines) <= 3 and all(text_width(l) * scale <= width for l in lines):
            break
    line_h = 10 * scale
    sub = wrap(subtitle, width, 4)[:3] if subtitle else []
    block = (8 * 4 + 2 * 4 if label else 0) + len(lines) * line_h + (len(sub) * 40 + 16 if sub else 0)
    y = max(8 * PX, (H - 20 * PX - block) // 2 + 2 * PX)
    if label:
        draw_text(c, label, left, y, 4, MUTED)
        y += 8 * 4 + 2 * 4
    for line in lines:
        draw_text(c, line, left, y, scale, TEXT)
        y += line_h
    if sub:
        y += 16
        for line in sub:
            draw_text(c, line, left, y, 4, MUTED)
            y += 40
    # the site, bottom right: the logo and the wiki's name
    name = 'Matcha Flavoured Wiki'
    nx = W - 8 * PX - text_width(name) * 3
    c.alpha_composite(logo_art().resize((36, 34), Image.NEAREST), (nx - 48, H - 8 * PX - 30))
    draw_text(c, name, nx, H - 8 * PX - 24, 3, MUTED)
    buf = io.BytesIO()
    c.convert('RGB').save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def card_path(title):
    """Published path of a page's card: stable per title, safe on every file system."""
    return '/%s/%s.png' % (CARD_DIR, hashlib.sha1(title.encode('utf-8')).hexdigest()[:16])


def normalize(s):
    """Titles in characters the game's fonts have (typographic quotes and dashes to plain ones)."""
    s = s.replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    s = s.replace('–', '-').replace('—', '-')
    f = font()
    return ''.join(ch if ch in f else unicodedata.normalize('NFKD', ch)[0] for ch in s)
