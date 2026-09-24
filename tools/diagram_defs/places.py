"""Places and the rules tied to them: fishing climates, and the radius maps of the Warding Stone and
the abandoned village's mannequin."""
import json
import os

from diagrams import SMALL, VANILLA_DATA, PACK_DATA, SRC, Svg, data, diagram, mcfunction, need, pack_json, text_width

# ---------------------------------------------------------------------------------------------
# Tags and names, the way the game layers them: a pack tag adds to vanilla's unless it replaces it


def tag_values(kind, tag):
    """The block/item ids in #tag (resolved recursively), pack over vanilla."""
    ns, path = tag.lstrip('#').split(':')
    rel = os.path.join(ns, 'tags', kind, path + '.json')
    found, values = False, []
    for base in (PACK_DATA, VANILLA_DATA):  # the pack first: if it replaces, vanilla's list is dropped
        p = os.path.join(base, rel)
        if os.path.exists(p):
            found = True
            t = json.load(open(p, encoding='utf-8'))
            values += [v if isinstance(v, str) else v['id'] for v in t['values']]
            if t.get('replace'):
                break
    if not found:
        raise FileNotFoundError('tag #%s' % tag.lstrip('#'))
    out = set()
    for v in values:
        out |= tag_values(kind, v) if v.startswith('#') else {v}
    return out


_lang = None


def block_name(bid):
    """A block's name in the pack's language (its renames), else vanilla's."""
    global _lang
    if _lang is None:
        _lang = json.load(open(os.path.join(SRC, 'vanilla-assets', 'assets', 'minecraft', 'lang', 'en_us.json'), encoding='utf-8'))
        _lang.update(data()['lang_pack'])
    key = 'block.' + bid.replace(':', '.')
    if key not in _lang:
        raise KeyError('no name for %s' % bid)
    return _lang[key]


def wrap(s, width, size=SMALL):
    """Words into lines no wider than width."""
    lines = []
    for word in s.split():
        if lines and text_width(lines[-1] + ' ' + word, size) <= width:
            lines[-1] += ' ' + word
        else:
            lines.append(word)
    return lines


# ---------------------------------------------------------------------------------------------
# Mining levels: which pickaxe gets drops from which block, from each pickaxe's tool rules


# ---------------------------------------------------------------------------------------------
# The Abbey: which pools each room's jigsaw connectors lead to, read from the templates themselves

def read_nbt(path):
    """A structure template (gzipped NBT) as Python values."""
    import gzip
    import struct
    b = gzip.open(path).read()
    pos = 0

    def rd(fmt):
        nonlocal pos
        v = struct.unpack_from('>' + fmt, b, pos)[0]
        pos += struct.calcsize('>' + fmt)
        return v

    def raw(k):
        nonlocal pos
        pos += k
        return b[pos - k:pos]

    def payload(t):
        if t in (1, 2, 3, 4, 5, 6):
            return rd('bhiqfd'[t - 1])
        if t == 7:
            return raw(rd('i'))
        if t == 8:
            return raw(rd('H')).decode('utf-8', 'replace')
        if t == 9:
            et, k = rd('b'), rd('i')
            return [payload(et) for _ in range(k)]
        if t == 10:
            out = {}
            while True:
                tt = rd('b')
                if tt == 0:
                    return out
                key = payload(8)
                out[key] = payload(tt)
        if t in (11, 12):
            k = rd('i')
            return [rd('i' if t == 11 else 'q') for _ in range(k)]
        raise ValueError('NBT tag %d in %s' % (t, path))

    t = rd('b')
    payload(8)
    return payload(t)


def pack_file_any(rel):
    p = os.path.join(PACK_DATA, rel)
    if not os.path.exists(p):
        raise FileNotFoundError(rel)
    return p


# ---------------------------------------------------------------------------------------------
# Fishing: the climate tables, cold to hot, with their biomes and fish

FISHING = 'minecraft:gameplay/fishing'
CLIMATE_ROWS = [
    ('Freshwater', ['freshwater_cold', 'freshwater_cool', 'freshwater_temperate', 'freshwater_hot_dry', 'freshwater_hot_wet']),
    ('Saltwater', ['saltwater_cold', 'saltwater_cool', 'saltwater_temperate', 'saltwater_warm', 'saltwater_hot']),
    ('Brackish', ['swamps']),
]
CLIMATE_NAMES = {'freshwater_hot_dry': 'Arid', 'freshwater_hot_wet': 'Tropical', 'swamps': 'Brackish'}  # the Almanac's
SPECIAL_TABLES = {'junk', 'treasure', 'deep_dark', 'pale_garden', 'sulfur_caves'}  # not climates: the page's own tables


def biome_name(bid):
    block_name('minecraft:stone')  # loads the language
    return _lang['biome.' + bid.replace(':', '.')]


def fishing_climates():
    """{table: (biome ids, [fish names by weight])} from the fishing loot table and its climate tables."""
    loot = data()['loot']
    out = {}
    for e in loot[FISHING]['entries']:
        table = e.get('loot_table', '')
        biomes = None
        for c in e.get('conditions') or []:
            if c['condition'] == 'minecraft:location_check':
                b = c['predicate']['biomes']
                if isinstance(b, str) and b.startswith('#'):
                    listed = [v for v in tag_order('worldgen/biome', b[1:]) if not v.startswith('#')]
                    biomes = listed + sorted(tag_values('worldgen/biome', b) - set(listed))
                else:
                    biomes = [b] if isinstance(b, str) else b
        if biomes is None:
            continue
        key = table.split('/')[-1]
        prev = out.get(key, ([], None))[0]
        fish = []
        for f in sorted(loot[table]['entries'], key=lambda f: -f['weight']):
            if f.get('loot_table'):
                items = [i['item'] for i in loot[f['loot_table']]['entries']]
                assert len(items) == 1, f
                fish.append(items[0])
        out[key] = (prev + [b for b in biomes if b not in prev], fish)
    return out


def tag_order(kind, tag):
    """A tag's direct values in file order (for picking the biomes a cell names first)."""
    ns, path = tag.split(':')
    return [v for v in pack_json(os.path.join(ns, 'tags', kind, path + '.json'))['values'] if isinstance(v, str)]


@diagram('Fishing climates')
def fishing_climates_diagram():
    climates = fishing_climates()
    drawn = {t for _, ts in CLIMATE_ROWS for t in ts}
    for t in climates:
        if t not in drawn and t not in SPECIAL_TABLES:
            raise ValueError('fishing table %s is in no row of the Fishing climates diagram' % t)
    W, left = 760, 96
    cols = max(len(ts) for _, ts in CLIMATE_ROWS)
    cw = (W - left) / cols
    ch, gap = 104, 8
    svg = Svg(W, 0, "The fishing climates from cold to hot: each one's biomes and its fish, common to rare")
    # a cold-to-hot axis over the columns
    svg.line(left + 10, 12, W - 12, 12, stroke='@muted', sw=1.5, arrow=True)
    svg.text(left + 10, 26, 'Colder', size=SMALL, fill='@blue')
    svg.text(W - 12, 26, 'Hotter', size=SMALL, fill='@red', anchor='end')
    y = 38
    for row, tables in CLIMATE_ROWS:
        svg.text(left - 12, y + ch / 2, row, bold=True, anchor='end')
        for i, t in enumerate(tables):
            biomes, fish = climates[t]
            x = left + cw * i
            svg.rect(x + gap / 2, y, cw - gap, ch, fill='@panel', stroke='@panel_edge', rx=6)
            name = CLIMATE_NAMES.get(t, t.split('_')[-1].capitalize())
            svg.text(x + 12, y + 16, name, bold=True)
            # a few biome names, in the tag's order, as fits two lines
            names = [biome_name(b) for b in biomes]
            shown = []
            for k in range(len(names), 0, -1):
                more = len(names) - k
                s = ', '.join(names[:k]) + (' +%d' % more if more else '')
                if len(wrap(s, cw - 30)) <= 2:
                    shown = wrap(s, cw - 30)
                    break
            if not shown:
                shown = wrap(names[0] + ' +%d' % (len(names) - 1), cw - 30)[:2]
            for j, line in enumerate(shown):
                svg.text(x + 12, y + 36 + j * 15, line, size=SMALL, fill='@muted')
            fx = x + gap / 2 + 7 + 11
            step = min(26, (cw - gap - 14 - 22) / max(len(fish) - 1, 1))
            for k, f in enumerate(fish):
                svg.icon(f, fx + k * step, y + ch - 20, 22)
        y += ch + gap
    y += 6
    svg.text(12, y, 'Fish are shown from common to rare. Pale Garden, Deep Dark and Sulfur Caves have small tables of their own.',
             size=SMALL, fill='@muted')
    svg.h = y + 12
    return svg


# ---------------------------------------------------------------------------------------------
# Radius maps around a placed block, drawn with the helpers of the Warding and Doom diagrams

def ring_label(svg, cx, cy, r, text, colour):
    """A radius's label just inside the top of its ring."""
    svg.text(cx, cy - r + 13, text, size=SMALL, fill=colour, anchor='middle', bold=True)


@diagram('Warding Stone')
def warding_stone():
    from diagram_defs.areas import rings
    src = mcfunction('matcha/function/mechanics/warding_stone/effects.mcfunction')
    regen = need(r'@e\[distance=\.\.(\d+),type=#matcha:villager_friends[^\]]*\] run effect give @s minecraft:regeneration',
                 src, 'warding stone regeneration radius', cast=int)
    slow = need(r'@e\[distance=\.\.(\d+),type=#matcha:warding_stone_targets\] run function \S+apply_slowness', src,
                'warding stone slowing radius', cast=int)
    hit_r = need(r'@n\[distance=\.\.(\d+),type=#matcha:warding_stone_targets\] run function \S+apply_damage', src,
                 'warding stone damage radius', cast=int)
    hit = need(r'@n\[distance=\.\.\d+,type=#matcha:warding_stone_targets\] run function \S+ \{damage:(\d+)\}', src,
               'warding stone damage', cast=int)
    held = mcfunction('matcha/function/enchantment_effects/warding/power_4.mcfunction')
    held_r = need(r'@n\[distance=\.\.(\d+),type=#matcha:warding_targets\] run function \S+apply_damage', held,
                  'Warding 4 damage radius', cast=int)
    outer = max(regen, slow, hit_r)
    W, size = 360, 280
    scale = (size / 2 - 6) / outer
    svg = Svg(W, 0, "The warding stone's regeneration and damage radii, to scale")
    cx, cy = W / 2, size / 2 + 4
    layers = [(regen, '@green_soft', '@green', None)]
    if slow == hit_r:
        layers.append((slow, '@red_soft', '@red', None))
    else:
        raise ValueError('warding stone: slowing (%d) and damage (%d) radii differ; draw both' % (slow, hit_r))
    layers.append((held_r, 'none', '@muted', '5 4'))
    rings(svg, cx, cy, scale, layers)
    ring_label(svg, cx, cy, slow * scale, '%d blocks' % slow, '@red')
    ring_label(svg, cx, cy, regen * scale, '%d blocks' % regen, '@green')
    svg.text(cx, cy + held_r * scale - 16, '%d blocks' % held_r, size=SMALL, fill='@muted', anchor='middle')
    svg.icon('Warding Stone', cx, cy, 26)
    y = size + 22
    svg.rect(12, y - 6, 14, 12, fill='@green_soft', stroke='@green', rx=2)
    svg.text(34, y, 'Villager friends get Regeneration', size=SMALL, fill='@muted')
    y += 20
    svg.rect(12, y - 6, 14, 12, fill='@red_soft', stroke='@red', rx=2)
    svg.text(34, y, 'Undead and pillagers are slowed;', size=SMALL, fill='@muted')
    y += 16
    w = svg.hp(34, y, hit, size=SMALL, fill='@muted')
    svg.text(34 + w + 6, y, 'to the nearest, each pulse', size=SMALL, fill='@muted')
    y += 20
    svg.line(12, y, 26, y, stroke='@muted', sw=1.5, dash='5 4')
    svg.text(34, y, "A held Warding 4's damage reach, for scale", size=SMALL, fill='@muted')
    svg.h = y + 12
    return svg


HAUNTED_HOUSE = 'minecraft/structure/village_beta/buildings/extra_large_4.nbt'


@diagram('Mannequin')
def mannequin():
    from diagram_defs.areas import rings
    env = 'matcha/function/environmental/'
    eerie = mcfunction(env + 'village_eerie_sound.mcfunction')
    music = need(r'tag=!music_played\] run execute if score @p\[distance=\.\.(\d+),gamemode=survival\] eerie >= 1 eerie '
                 r'run function matcha:environmental/play_village_jukebox', eerie, 'mannequin music radius', cast=int)
    near_box = need(r'@n\[type=marker,tag=jukebox\] run execute if entity @p\[distance=\.\.(\d+),gamemode=survival\] '
                    r'run function matcha:environmental/kill_village_entity', eerie, 'jukebox vanish radius', cast=int)
    near = need(r'tag=haunted\] run execute if entity @p\[distance=\.\.(\d+),gamemode=survival\] run function '
                r'matcha:environmental/kill_village_entity', eerie, 'mannequin vanish radius', cast=int)
    door = need(r'@p\[distance=\.\.(\d+),gamemode=survival\] run tp @s ~ ~-1000 ~',
                mcfunction(env + 'check_if_entity_should_die.mcfunction'), 'oak door vanish radius', cast=int)
    # where things stand in the house: the mannequin, the jukebox marker, the jukebox and the door
    house = read_nbt(pack_file_any(HAUNTED_HOUSE))
    ents = {e['nbt']['id']: e['pos'] for e in house['entities'] if e['nbt'].get('Tags')}
    man, marker = ents['minecraft:mannequin'], ents['minecraft:marker']
    pal = house['palette']
    blocks = {pal[b['state']]['Name']: b['pos'] for b in house['blocks']}
    juke, oak = blocks['minecraft:jukebox'], blocks['minecraft:oak_door']
    sx, _, sz = house['size']

    W = 360
    scale = (W / 2 - 8) / music
    cx, cy = W / 2, W / 2 - 4
    svg = Svg(W, 0, "The haunted house's mannequin: the distances that start the music and make it vanish, to scale")

    def at(p):  # template x/z to the drawing, the mannequin at the centre
        return cx + (p[0] - man[0]) * scale, cy + (p[2] - man[2]) * scale

    rings(svg, cx, cy, scale, [(music, '@blue_soft', '@blue', None)])
    x0, y0 = at((0, 0, 0))
    svg.rect(x0, y0, sx * scale, sz * scale, fill='@panel', stroke='@panel_edge', rx=2)
    svg.text(x0 + sx * scale, y0 + sz * scale + 10, 'House', size=SMALL, fill='@muted', anchor='end')
    rings(svg, cx, cy, scale, [(door, 'none', '@amber', '5 4'), (near, '@red_soft', '@red', None)])
    mx, my = at(marker)
    svg.circle(mx, my, near_box * scale, fill='@red_soft', stroke='@red', sw=1.5)
    dx, dy = at((oak[0] + 0.5, 0, oak[2] + 0.5))
    d = max(scale, 7)
    svg.rect(dx - d / 2, dy - d / 2, d, d, fill='@amber', rx=1)
    svg.icon('Jukebox', *at((juke[0] + 0.5, 0, juke[2] + 0.5)), 16)
    svg.circle(cx, cy, 3.5, fill='@ink')
    ring_label(svg, cx, cy, music * scale, '%d blocks' % music, '@blue')
    svg.text(cx - door * scale + 6, cy, '%d' % door, size=SMALL, fill='@amber', bold=True)
    y = W - 4
    rows = [(('@blue_soft', '@blue', None), 'Within %d: the jukebox starts Dry Hands' % music),
            (('none', '@amber', '5 4'), 'Within %d, opening an oak door: it vanishes' % door),
            (('@red_soft', '@red', None), 'Within %d of it, or %d of the jukebox: it vanishes' % (near, near_box))]
    for (fill, edge, dash), label in rows:
        svg.rect(12, y - 6, 14, 12, fill=fill, stroke=edge, rx=2, dash=dash)
        svg.text(34, y, label, size=SMALL, fill='@muted')
        y += 20
    svg.circle(19, y, 3.5, fill='@ink')
    svg.text(34, y, 'The mannequin', size=SMALL, fill='@muted')
    svg.rect(130, y - 5, 10, 10, fill='@amber', rx=1)
    svg.text(146, y, 'Oak door', size=SMALL, fill='@muted')
    svg.icon('Jukebox', 228, y, 16)
    svg.text(242, y, 'Jukebox', size=SMALL, fill='@muted')
    svg.h = y + 12
    return svg
