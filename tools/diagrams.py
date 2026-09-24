#!/usr/bin/env python3
"""Draw the wiki's diagrams from the pack's data into wiki/diagrams/ (committed, like wiki/generated).

Every diagram is a function in tools/diagram_defs/ (one module per topic), registered with
@diagram('<Name>'); it reads its numbers from the pack's files (source/, build/data.json) with the
helpers here, so a pack update redraws it, and it draws with the shared style here so every diagram
looks like the others. Each is written twice,
for the light and the dark theme:

    wiki/diagrams/<Name> diagram.svg          File:<Name> diagram.svg
    wiki/diagrams/<Name> diagram (dark).svg   File:<Name> diagram (dark).svg

and shown with {{Diagram|<Name>|caption=...}}, which swaps them with the theme. When and how a page
gets one is in wiki/STYLE.md ("Diagrams").

    python3 tools/diagrams.py            redraw every diagram
    python3 tools/diagrams.py Ores ...   only diagrams whose name contains one of the words
    python3 tools/diagrams.py --check    exit 1 if a committed diagram differs from what the data gives

Needs build/data.json (tools/extract.py) and the sources (tools/fetch_sources.sh).
"""
import base64
import importlib
import io
import json
import math
import os
import re
import sys

if __name__ == '__main__':  # the diagram modules import this one as `diagrams`
    sys.modules.setdefault('diagrams', sys.modules['__main__'])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
OUT = os.path.join(ROOT, 'wiki', 'diagrams')
SRC = os.path.join(ROOT, 'source')
PACK_DATA = os.path.join(SRC, 'matcha-flavoured', 'MF_datapack', 'data')
VANILLA_DATA = os.path.join(SRC, 'vanilla-data', 'data')

# ---------------------------------------------------------------------------------------------
# Style. One palette per theme; diagrams name colours by role (@ink, @green...), never by value.
# The roles follow the skin: body text, secondary text, rules, and a few accents that keep their
# meaning across diagrams (green = safe/good/day, red = danger/damage, blue = water/cold/night...).

FONT = '"Liberation Sans", Arial, Helvetica, FreeSans, sans-serif'  # the skin's body font
THEMES = {
    # drawn on the article background: #e6eff4 (light) and #2b2f39 (dark)
    'light': {
        'ink': '#202122', 'muted': '#4f555b', 'rule': '#8f989f', 'grid': '#c9d2d9', 'panel': '#f7f9fb',
        'panel_edge': '#aab3bb', 'paper': '#ffffff',
        'green': '#3a7322', 'green_soft': '#cbe4bb', 'red': '#b0392f', 'red_soft': '#f1c7c2',
        'blue': '#2c5aad', 'blue_soft': '#c3d4f1', 'amber': '#9c6210', 'amber_soft': '#f3dcad',
        'purple': '#66489e', 'purple_soft': '#dccfef', 'teal': '#137068', 'teal_soft': '#c1e4df',
        'grey': '#6a7178', 'grey_soft': '#d2d8de', 'night': '#27345a', 'day': '#f3d06e',
    },
    'dark': {
        'ink': '#eaecf0', 'muted': '#aeb4bb', 'rule': '#7d848d', 'grid': '#3f4552', 'panel': '#353a46',
        'panel_edge': '#5b6270', 'paper': '#1b1e24',
        'green': '#7fc45d', 'green_soft': '#314b28', 'red': '#ef7e74', 'red_soft': '#5a302b',
        'blue': '#8eaaec', 'blue_soft': '#2e3f63', 'amber': '#e6ad4f', 'amber_soft': '#58431f',
        'purple': '#b89fe8', 'purple_soft': '#46385f', 'teal': '#62c7ba', 'teal_soft': '#224b46',
        'grey': '#a9afb7', 'grey_soft': '#474d59', 'night': '#1d2744', 'day': '#cfae4f',
    },
}

# Styles: the same drawing code in different dress. STYLE is picked with $MFW_DIAGRAM_STYLE (default
# 'clean'); each style may replace the palettes and change the font, corners, frame and details.
_TABLE = {
    'light': dict(THEMES['light'], panel='#f8f9fa', panel_edge='#a2a9b1', grid='#dde2e7', frame='#f8f9fa',
                  frame_edge='#a2a9b1', head='#eaecf0'),
    'dark': dict(THEMES['dark'], panel='#27292d', panel_edge='#54595d', grid='#3a3d42', frame='#202122',
                 frame_edge='#54595d', head='#27292d'),
}
_GUI = dict(  # the pack's brown inventory (MediaWiki:Gadget-mfw-ui.css), the same in both themes
    ink='#f4ecdf', muted='#cdbb9f', rule='#9b8266', grid='#57473a', panel='#43362A', panel_edge='#1B1511',
    paper='#2a2019', shadow='#241a12', hi='#7F664D', lo='#1B1511', frame='#604D3A', frame_edge='#0D0903',
    green='#8fd16a', green_soft='#3f5a2c', red='#f08a7e', red_soft='#6e3328', blue='#9db8f2', blue_soft='#3a4a6a',
    amber='#f0b95a', amber_soft='#7a5a27', purple='#c5aef0', purple_soft='#533f6a', teal='#72d3c6',
    teal_soft='#2a5550', grey='#c0b4a4', grey_soft='#5a4a3a', night='#20283f', day='#e8c65a')
STYLES = {
    'clean': {'themes': THEMES},
    'wikitable': {'themes': _TABLE, 'rx': 0, 'frame': 'table', 'grid': True},
    'blocky': {'themes': THEMES, 'rx': 0, 'font': 'minecraft', 'grid': True, 'node_sw': 2},
    'inventory': {'themes': {'light': _GUI, 'dark': _GUI}, 'rx': 0, 'font': 'minecraft', 'grid': True,
                  'frame': 'gui', 'shadow': True, 'bevel': True},
}
STYLE = STYLES[os.environ.get('MFW_DIAGRAM_STYLE', 'clean')]
MINECRAFT = STYLE.get('font') == 'minecraft'

# accents in the order series take them, for charts with several lines or bars
SERIES = ['green', 'blue', 'amber', 'red', 'purple', 'teal', 'grey']
TEXT = 12 if MINECRAFT else 13       # label size
SMALL = 10 if MINECRAFT else 11.5    # axis ticks and notes


# Arial/Liberation Sans advance widths (em) for laying out labels; anything unlisted is an average letter
_W = {' ': .278, '(': .333, ')': .333, '.': .278, ',': .278, ':': .278, ';': .278, "'": .191, '-': .333,
      'i': .222, 'l': .222, 'j': .222, 'f': .278, 't': .278, 'r': .333, 'm': .833, 'w': .722, 'W': .944,
      'M': .833, 'I': .278, '×': .584, '\u00a0': .278, '/': .278, '%': .889, '–': .556, '→': 1.0}


# the Minecraft font: most glyphs advance 6 of 8 pixels
_MC = {' ': .5, 'i': .25, '!': .25, '.': .25, ',': .25, ':': .25, ';': .25, "'": .25, 'l': .375, 'I': .5,
       't': .5, '(': .5, ')': .5, 'f': .625, 'k': .625, '\u00a0': .5}


def text_width(s, size=TEXT, bold=False):
    if MINECRAFT:
        return sum(_MC.get(c, .75) for c in str(s)) * size * (1.12 if bold else 1)
    w = sum(_W.get(c, .556 if c.isdigit() else .667 if c.isupper() else .5) for c in str(s))
    return w * size * (1.06 if bold else 1)


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def n(v):
    """Numbers as short, stable strings."""
    v = round(float(v), 2)
    return str(int(v)) if v == int(v) else ('%.2f' % v).rstrip('0')


class Svg:
    """An SVG drawing in user units (1 unit = 1 CSS pixel at full width). Colours are @roles."""

    def __init__(self, width, height, title):
        self.w, self.h, self.title = width, height, title
        self.items = []
        self.defs = []

    def add(self, s):
        self.items.append(s)
        return s

    def behind(self, draw, *args, **kw):
        """Run a drawing function and put what it drew under everything drawn so far (gridlines)."""
        start = len(self.items)
        out = draw(*args, **kw)
        new = self.items[start:]
        del self.items[start:]
        self.items[:0] = new
        return out

    def rect(self, x, y, w, h, fill='@panel', stroke=None, rx=0, sw=1, opacity=None, dash=None):
        if rx and STYLE.get('rx') is not None:
            rx = STYLE['rx']
        a = ' stroke="%s" stroke-width="%s"' % (stroke, n(sw)) if stroke else ''
        a += ' rx="%s"' % n(rx) if rx else ''
        a += ' fill-opacity="%s"' % n(opacity) if opacity is not None else ''
        a += ' stroke-dasharray="%s"' % dash if dash else ''
        return self.add('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"%s/>' % (n(x), n(y), n(w), n(h), fill, a))

    def line(self, x1, y1, x2, y2, stroke='@rule', sw=1, dash=None, cap=None, arrow=False):
        a = ' stroke-dasharray="%s"' % dash if dash else ''
        a += ' stroke-linecap="%s"' % cap if cap else ''
        a += ' marker-end="url(#arrow%s)"' % stroke.strip('@') if arrow else ''
        if arrow:
            self.marker(stroke)
        return self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s/>'
                        % (n(x1), n(y1), n(x2), n(y2), stroke, n(sw), a))

    def path(self, d, stroke=None, fill='none', sw=1.5, dash=None, arrow=False, opacity=None, join='round'):
        a = ' stroke="%s" stroke-width="%s" stroke-linejoin="%s"' % (stroke, n(sw), join) if stroke else ''
        a += ' stroke-dasharray="%s"' % dash if dash else ''
        a += ' fill-opacity="%s"' % n(opacity) if opacity is not None else ''
        if arrow:
            self.marker(stroke)
            a += ' marker-end="url(#arrow%s)"' % stroke.strip('@')
        return self.add('<path d="%s" fill="%s"%s/>' % (d, fill, a))

    def poly(self, pts, **kw):
        return self.path('M' + ' L'.join('%s %s' % (n(x), n(y)) for x, y in pts), **kw)

    def circle(self, cx, cy, r, fill='@panel', stroke=None, sw=1, dash=None, opacity=None):
        a = ' stroke="%s" stroke-width="%s"' % (stroke, n(sw)) if stroke else ''
        a += ' stroke-dasharray="%s"' % dash if dash else ''
        a += ' fill-opacity="%s"' % n(opacity) if opacity is not None else ''
        return self.add('<circle cx="%s" cy="%s" r="%s" fill="%s"%s/>' % (n(cx), n(cy), n(r), fill, a))

    def text(self, x, y, s, size=TEXT, fill='@ink', anchor='start', bold=False, italic=False, baseline='middle'):
        if STYLE.get('shadow'):  # the game's text shadow
            self._text(x + size / 8, y + size / 8, s, size, '@shadow', anchor, bold, italic, baseline)
        return self._text(x, y, s, size, fill, anchor, bold, italic, baseline)

    def _text(self, x, y, s, size, fill, anchor, bold, italic, baseline):
        a = ' font-weight="bold"' if bold and not MINECRAFT else ''
        a += ' font-style="italic"' if italic else ''
        a += ' text-anchor="%s"' % anchor if anchor != 'start' else ''
        a += ' dominant-baseline="%s"' % baseline if baseline else ''
        return self.add('<text x="%s" y="%s" font-size="%s" fill="%s"%s>%s</text>' % (n(x), n(y), n(size), fill, a, esc(s)))

    def icon(self, name, x, y, size=24):
        """An item's inventory icon (the wiki's own, drawn by tools/images.py), centred on x, y."""
        uri = icon_uri(name)
        if uri:
            self.add('<image x="%s" y="%s" width="%s" height="%s" href="%s" style="image-rendering:pixelated"/>'
                     % (n(x - size / 2), n(y - size / 2), n(size), n(size), uri))

    def sprite(self, uri, x, y, size):
        """A pixel-art image (a data URI) centred on x, y."""
        self.add('<image x="%s" y="%s" width="%s" height="%s" href="%s" style="image-rendering:pixelated"/>'
                 % (n(x - size / 2), n(y - size / 2), n(size), n(size), uri))

    def hp(self, x, y, hp, size=TEXT, anchor='start', fill='@ink'):
        """Health as the wiki's {{Hp}} writes it: '16 (heart x 8)', with the pack's HUD heart."""
        hearts = hp / 2
        tail = '\u00a0%s)' % ('× ' + n(hearts) if hp >= 2 else '× 0.5')  # SVG drops a plain leading space
        head = '%s (' % n(hp)
        w = text_width(head, size) + size + text_width(tail, size)
        x0 = {'start': x, 'middle': x - w / 2, 'end': x - w}[anchor]
        self.text(x0, y, head, size=size, fill=fill)
        self.sprite(asset_uri('heart-full.png' if hp >= 2 else 'heart-half.png'), x0 + text_width(head, size) + size / 2, y, size)
        self.text(x0 + text_width(head, size) + size, y, tail, size=size, fill=fill)
        return w

    def marker(self, colour):
        mid = 'arrow' + colour.strip('@')
        if not any('id="%s"' % mid in d for d in self.defs):
            self.defs.append('<marker id="%s" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                             'orient="auto-start-reverse"><path d="M0 1 L9 5 L0 9 z" fill="%s"/></marker>' % (mid, colour))

    def render(self, theme):
        pal = STYLE['themes'][theme]
        body = '\n'.join(self.items)
        defs = ''.join(self.defs)
        font = FONT
        if MINECRAFT:  # an SVG shown as an image can't load the skin's font file: embed it
            raw = open(os.path.join(ROOT, 'site', 'assets', 'mcw', 'Minecraft.woff2'), 'rb').read()
            defs += '<style>FONTFACE</style>'  # filled in after the colour roles (it contains an @)
            font = 'MinecraftDiagram, ' + FONT
        w, h = self.w, self.h
        frame = STYLE.get('frame')
        if frame:  # a frame round the drawing: a wikitable's border, or the pack's inventory panel
            pad = 14
            w, h = self.w + 2 * pad, self.h + 2 * pad
            if frame == 'table':
                back = '<rect x="0.5" y="0.5" width="%s" height="%s" fill="@frame" stroke="@frame_edge"/>' % (n(w - 1), n(h - 1))
            else:
                back = ('<rect x="0" y="0" width="%s" height="%s" fill="@frame_edge"/>'
                        '<rect x="2" y="2" width="%s" height="%s" fill="@hi"/>'
                        '<rect x="6" y="6" width="%s" height="%s" fill="@lo"/>'
                        '<rect x="6" y="6" width="%s" height="%s" fill="@frame"/>'
                        % (n(w), n(h), n(w - 8), n(h - 8), n(w - 8), n(h - 8), n(w - 12), n(h - 12)))
            body = '%s\n<g transform="translate(%s %s)">\n%s\n</g>' % (back, pad, pad, body)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%s" height="%s" '
               'font-family=\'%s\' role="img">\n<title>%s</title>\n%s%s\n</svg>\n'
               % (n(w), n(h), n(w), n(h), font, esc(self.title),
                  '<defs>%s</defs>\n' % defs if defs else '', body))
        svg = re.sub(r'@([a-z_]+)', lambda m: pal[m.group(1)], svg)
        if MINECRAFT:
            svg = svg.replace('FONTFACE', '@font-face{font-family:MinecraftDiagram;src:url(data:font/woff2;base64,%s) '
                              'format("woff2")}' % base64.b64encode(raw).decode())
        return svg


# ---------------------------------------------------------------------------------------------
# Shared pieces

class Scale:
    """Linear map from data to drawing units."""

    def __init__(self, d0, d1, r0, r1):
        self.d0, self.d1, self.r0, self.r1 = d0, d1, r0, r1

    def __call__(self, v):
        return self.r0 + (v - self.d0) * (self.r1 - self.r0) / (self.d1 - self.d0)


def block_grid(svg, cx, cy, scale, half):
    """A top-down patch of ground centred on a source, one cell per block with a heavier line every
    16 blocks (a chunk), `half` blocks out each way: for styles that draw areas on the block grid."""
    x0, y0, size = cx - half * scale, cy - half * scale, 2 * half * scale
    svg.rect(x0, y0, size, size, fill='@panel', stroke='@panel_edge')
    for i in range(-half + 1, half):
        heavy = i % 16 == 0
        colour, sw = ('@rule', 1) if heavy else ('@grid', 0.8)
        svg.line(cx + i * scale, y0, cx + i * scale, y0 + size, stroke=colour, sw=sw)
        svg.line(x0, cy + i * scale, x0 + size, cy + i * scale, stroke=colour, sw=sw)


def legend(svg, x, y, entries, gap=18):
    """Swatch + label entries in a row; returns the width used."""
    x0 = x
    for colour, label, kind in entries:
        if kind == 'line':
            svg.line(x, y, x + 18, y, stroke=colour, sw=3, cap='round')
        elif kind == 'dash':
            svg.line(x, y, x + 18, y, stroke=colour, sw=2.5, dash='5 3')
        else:
            svg.rect(x, y - 6, 14, 12, fill=colour, rx=2)
        svg.text(x + 24, y, label, size=SMALL, fill='@muted')
        x += 24 + text_width(label, SMALL) + gap
    return x - x0


def box(svg, x, y, w, h, label, fill='@panel', edge='@panel_edge', ink='@ink', sub=None, icon=None, bold=False, rx=6):
    """A labelled node for flow charts, centred on x, y; an optional item icon on its left."""
    svg.rect(x - w / 2, y - h / 2, w, h, fill=fill, stroke=edge, rx=rx)
    tx = x
    if icon:
        svg.icon(icon, x - w / 2 + 16, y, 22)
        tx = x + 10
    if sub:
        svg.text(tx, y - 7, label, anchor='middle', fill=ink, bold=bold)
        svg.text(tx, y + 9, sub, size=SMALL, anchor='middle', fill='@muted')
    else:
        svg.text(tx, y + 0.5, label, anchor='middle', fill=ink, bold=bold)


class Flow:
    """Flow charts: boxes (with an optional item icon) and arrows clipped to the boxes' edges."""

    def __init__(self, svg):
        self.svg = svg
        self.nodes = {}

    def node(self, key, x, y, label, w=None, h=40, icon=None, sub=None, fill='@panel', edge='@panel_edge',
             dash=None, bold=False, ink='@ink'):
        if w is None:
            w = max(text_width(label, TEXT, bold), text_width(sub or '', SMALL)) + (58 if icon else 28)
        svg = self.svg
        if STYLE.get('bevel'):  # a recessed inventory slot: dark top and left edges, light bottom and right
            svg.rect(x - w / 2, y - h / 2, w, h, fill=fill if fill != '@panel' else '@panel')
            svg.poly([(x - w / 2, y + h / 2), (x - w / 2, y - h / 2), (x + w / 2, y - h / 2)], stroke='@lo', sw=2, join='miter')
            svg.poly([(x + w / 2, y - h / 2), (x + w / 2, y + h / 2), (x - w / 2, y + h / 2)], stroke='@hi', sw=2, join='miter')
            if edge not in ('@panel_edge',) or dash:
                svg.rect(x - w / 2 + 3, y - h / 2 + 3, w - 6, h - 6, fill='none', stroke=edge, sw=1, dash=dash)
        else:
            svg.rect(x - w / 2, y - h / 2, w, h, fill=fill, stroke=edge, rx=6, sw=STYLE.get('node_sw', 1.2), dash=dash)
        tx = x
        if icon:
            svg.icon(icon, x - w / 2 + 19, y, 26)
            tx = x + 14
        if sub:
            svg.text(tx, y - 7, label, anchor='middle', bold=bold, fill=ink)
            svg.text(tx, y + 9, sub, size=SMALL, anchor='middle', fill='@muted')
        else:
            svg.text(tx, y + 0.5, label, anchor='middle', bold=bold, fill=ink)
        self.nodes[key] = (x, y, w, h)
        return self.nodes[key]

    def _clip(self, key, tx, ty, gap=3):
        """Where the line from a node's centre towards (tx, ty) leaves its box."""
        x, y, w, h = self.nodes[key]
        dx, dy = tx - x, ty - y
        if dx == 0 and dy == 0:
            return x, y
        k = min((w / 2 + gap) / abs(dx) if dx else 1e9, (h / 2 + gap) / abs(dy) if dy else 1e9)
        return x + dx * k, y + dy * k

    def arrow(self, a, b, label=None, colour='@rule', dash=None, sw=1.5, label_side='above', via=None):
        """An arrow from node a to node b, straight or through the points in via."""
        ax, ay = self.nodes[a][:2]
        bx, by = self.nodes[b][:2]
        pts = via or []
        start = self._clip(a, *(pts[0] if pts else (bx, by)))
        end = self._clip(b, *(pts[-1] if pts else (ax, ay)), gap=4)
        path = [start] + list(pts) + [end]
        self.svg.poly(path, stroke=colour, sw=sw, dash=dash, arrow=True)
        if label:
            (x1, y1), (x2, y2) = path[len(path) // 2 - 1], path[len(path) // 2]
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if abs(y2 - y1) < abs(x2 - x1):
                self.svg.text(mx, my - 9 if label_side == 'above' else my + 11, label, size=SMALL, fill='@muted', anchor='middle')
            else:
                self.svg.text(mx + 7, my, label, size=SMALL, fill='@muted')


# ---------------------------------------------------------------------------------------------
# Data access: the pack's files over vanilla's, the way the game layers them

_data = None


def data():
    global _data
    if _data is None:
        _data = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
    return _data


def pack_file(rel):
    """Path of data/<rel> in the pack, else vanilla."""
    for base in (PACK_DATA, VANILLA_DATA):
        p = os.path.join(base, rel)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(rel)


def pack_json(rel):
    return json.load(open(pack_file(rel), encoding='utf-8'))


def mcfunction(rel):
    return open(os.path.join(PACK_DATA, rel), encoding='utf-8').read()


def need(pattern, text, what, group=1, cast=float):
    """A number the diagram depends on, read with a regex; a pack change that breaks it fails loudly."""
    m = re.search(pattern, text)
    if not m:
        raise ValueError('diagram data not found: %s (/%s/)' % (what, pattern))
    return cast(m.group(group))


def asset_uri(name):
    """A sprite from site/assets/gui (the pack's GUI art, cut by tools/images.py), as a data URI."""
    raw = open(os.path.join(ROOT, 'site', 'assets', 'gui', name), 'rb').read()
    return 'data:image/png;base64,' + base64.b64encode(raw).decode()


_icons = {}


def icon_uri(name):
    """The wiki's icon for an item name, as a data URI (64 px; the slot art is 16 px, drawn 4x)."""
    if name in _icons:
        return _icons[name]
    uri = None
    item = data()['items'].get(name)
    if item:
        import images
        from PIL import Image
        im = images.item_icon(item)
        if im is not None:
            im = im.convert('RGBA').resize((64, 64), Image.NEAREST if (item.get('icon') or {}).get('kind') == 'item' else Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, 'PNG', optimize=True)
            uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    _icons[name] = uri
    return uri


# ---------------------------------------------------------------------------------------------
# Registry

DIAGRAMS = {}


def diagram(name):
    def reg(fn):
        DIAGRAMS[name] = fn
        return fn
    return reg


def canonical(svg):
    """An SVG with each embedded PNG replaced by a hash of its pixels, so --check doesn't trip over
    two Pillow versions encoding the same icon differently."""
    from PIL import Image
    import hashlib

    def pixels(m):
        im = Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert('RGBA')
        return 'pixels:%s' % hashlib.sha1(repr(im.size).encode() + im.tobytes()).hexdigest()
    return re.sub(r'data:image/png;base64,([A-Za-z0-9+/=]+)', pixels, svg)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    check = '--check' in sys.argv
    for f in sorted(os.listdir(os.path.join(ROOT, 'tools', 'diagram_defs'))):
        if f.endswith('.py') and not f.startswith('_'):
            try:
                importlib.import_module('diagram_defs.' + f[:-3])  # each registers its diagrams
            except Exception as e:
                if not args:  # drawing everything: every module must load
                    raise
                print('skipped tools/diagram_defs/%s: %s' % (f, e))
    names = [k for k in DIAGRAMS if not args or any(a.lower() in k.lower() for a in args)]
    os.makedirs(OUT, exist_ok=True)
    stale = []
    for name in names:
        svg = DIAGRAMS[name]()
        for theme, suffix in (('light', ''), ('dark', ' (dark)')):
            path = os.path.join(OUT, '%s diagram%s.svg' % (name, suffix))
            out = svg.render(theme)
            old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
            if old != out and (old is None or canonical(old) != canonical(out)):
                stale.append(os.path.relpath(path, ROOT))
                if not check:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(out)
    if not args:
        known = {'%s diagram%s.svg' % (k, s) for k in DIAGRAMS for s in ('', ' (dark)')}
        for f in sorted(os.listdir(OUT)):
            if f.endswith('.svg') and f not in known:
                stale.append('wiki/diagrams/%s (no diagram draws it)' % f)
                if not check:
                    os.remove(os.path.join(OUT, f))
    if check:
        for s in stale:
            print('out of date:', s)
        sys.exit(1 if stale else 0)
    print('%d diagrams, %d files written' % (len(names), len(stale)))


if __name__ == '__main__':
    main()
