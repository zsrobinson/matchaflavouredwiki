"""Places and the rules tied to them: mining levels, the Abbey's rooms, fishing climates, and the
radius maps of the Warding Stone and the abandoned village's mannequin."""
import json
import os

from diagrams import (SMALL, TEXT, VANILLA_DATA, PACK_DATA, SRC, Flow, Svg, data, diagram, legend, need, pack_json,
                      text_width)

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


def blocks_of(selector):
    return tag_values('block', selector) if selector.startswith('#') else {selector}


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


def check_mark(svg, x, y, colour='@green'):
    svg.path('M%s %s L%s %s L%s %s' % (x - 5, y, x - 1.5, y + 4, x + 5.5, y - 4.5), stroke=colour, sw=2.2)


def cross_mark(svg, x, y, colour='@red'):
    for dx in (-4, 4):
        svg.line(x - dx, y - 4, x + dx, y + 4, stroke=colour, sw=2.2, cap='round')


# ---------------------------------------------------------------------------------------------
# Mining levels: which pickaxe gets drops from which block, from each pickaxe's tool rules

PICKAXES = [('Wood', 'Wooden Pickaxe'), ('Copper', 'Copper Pickaxe'), ('Iron', 'Iron Pickaxe'),
            ('Gold', 'Golden Pickaxe'), ('Shakudo', 'Shakudo Pickaxe'), ('Hepatizon', 'Hepatizon Pickaxe'),
            ('Steel', 'Steel Pickaxe'), ('Diamond', 'Diamond Pickaxe'), ('Electrum', 'Electrum Pickaxe'),
            ('Adamant', 'Adamant Pickaxe')]
# the columns: the blocks the pickaxes' own rules name, grouped the way the page names them.
# (the blocks that name the column and give its icons, the blocks in it)
BLOCK_GROUPS = [
    (['minecraft:deepslate'], ['minecraft:deepslate', 'minecraft:cobbled_deepslate', 'minecraft:polished_deepslate']),
    (['minecraft:iron_ore'], ['#minecraft:iron_ores']),
    (['minecraft:gold_ore'], ['#minecraft:gold_ores']),
    (['minecraft:emerald_ore'], ['#minecraft:emerald_ores']),
    (['minecraft:deepslate_redstone_ore'], ['#minecraft:redstone_ores']),
    (['minecraft:deepslate_lapis_ore'], ['minecraft:deepslate_lapis_ore']),
    (['minecraft:diamond_ore'], ['#minecraft:diamond_ores']),
    (['minecraft:obsidian'], ['minecraft:obsidian']),
    (['minecraft:crying_obsidian', 'minecraft:ender_chest'], ['minecraft:crying_obsidian', 'minecraft:ender_chest']),
]
UNBREAKABLE = {'minecraft:reinforced_deepslate'}  # named in a rule, but no tool breaks it


def tool_result(rules, block):
    """(mining speed, drops?) of a tool component on a block: like the game, the first rule that
    matches the block and sets a value decides it; no rule means speed 1 and no drops."""
    speed = next((r['speed'] for r in rules if 'speed' in r and block in blocks_of(r['blocks'])), 1)
    drops = next((r['correct_for_drops'] for r in rules if 'correct_for_drops' in r and block in blocks_of(r['blocks'])), False)
    return speed, drops


@diagram('Mining levels')
def mining_levels():
    items = data()['items']
    groups = [(head, set().union(*(blocks_of(s) for s in sel))) for head, sel in BLOCK_GROUPS]
    covered = set().union(*(g for _, g in groups)) | UNBREAKABLE
    rows = []
    for tier, name in PICKAXES:
        rules = items[name]['components']['tool']['rules']
        general = next(r for r in rules if r['blocks'] == '#minecraft:mineable/pickaxe')
        assert general.get('correct_for_drops'), name
        for r in rules:  # every block a rule singles out must be in a column
            if r is not general:
                missing = blocks_of(r['blocks']) - covered
                if missing:
                    raise ValueError('%s: %s has no column in the Mining levels diagram' % (name, sorted(missing)))
        cells = []
        for head, blocks in groups:
            results = {tool_result(rules, b) for b in blocks}
            if len(results) != 1:
                raise ValueError('%s treats the %s group unevenly: %s' % (name, head, results))
            cells.append(results.pop())
        rows.append((tier, name, general['speed'], cells))

    W, left, speed_w = 760, 118, 52
    col = (W - left - speed_w) / len(groups)
    head_h, row_h = 92, 30
    svg = Svg(W, 0, 'Which pickaxe gets drops from which blocks, and where its mining speed changes')
    x0 = left + speed_w
    # column heads: the block's icon and its name
    for i, (heads, blocks) in enumerate(groups):
        cx = x0 + col * i + col / 2
        for k, h in enumerate(heads):
            svg.icon(block_name(h), cx + (k - (len(heads) - 1) / 2) * 30, 20, 28)
        for j, line in enumerate(wrap(', '.join(block_name(h) for h in heads), col - 4)):
            svg.text(cx, 48 + j * 14, line, size=SMALL, anchor='middle')
    svg.text(left + speed_w / 2, head_h - 12, 'Speed', size=SMALL, fill='@muted', anchor='middle')
    y = head_h
    for tier, name, general, cells in rows:
        cy = y + row_h / 2
        svg.icon(name, 16, cy, 24)
        svg.text(34, cy, tier, bold=True)
        svg.text(left + speed_w / 2, cy, '%g' % general, size=SMALL, fill='@muted', anchor='middle')
        for i, (speed, drops) in enumerate(cells):
            cx = x0 + col * i + col / 2
            svg.rect(cx - col / 2 + 2, y + 2, col - 4, row_h - 4, fill='@green_soft' if drops else '@red_soft', rx=3)
            other = speed != general
            mx = cx - 9 if other else cx
            (check_mark if drops else cross_mark)(svg, mx, cy)
            if other:
                fast = speed > general
                svg.text(cx + 3, cy + 0.5, '%g' % speed, size=SMALL if not fast else TEXT, bold=fast,
                         fill='@green' if drops else '@red')
        y += row_h
    svg.behind(lambda: [svg.line(12, yy, W, yy, stroke='@grid') for yy in (head_h + row_h * k for k in range(len(rows) + 1))])
    y += 22
    legend(svg, 12, y, [('@green_soft', 'Breaks and drops', 'box'), ('@red_soft', 'Breaks with no drops', 'box')])
    svg.text(W - 4, y, 'A number in a cell: the mining speed on that block, if it differs.', size=SMALL, fill='@muted',
             anchor='end')
    svg.h = y + 14
    return svg


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


def jigsaws(template):
    """[(name, pool, target)] of a template's jigsaw blocks, template like 'minecraft:abbey/default/rooms/bath'."""
    ns, path = template.split(':')
    nbt = read_nbt(pack_file_any(os.path.join(ns, 'structure', path + '.nbt')))
    pal = nbt['palette']
    out = []
    for block in nbt['blocks']:
        if pal[block['state']]['Name'] == 'minecraft:jigsaw':
            j = block['nbt']
            out.append((j['name'], j['pool'], j['target']))
    return out


def pack_file_any(rel):
    p = os.path.join(PACK_DATA, rel)
    if not os.path.exists(p):
        raise FileNotFoundError(rel)
    return p


def pool_exists(pool):
    ns, path = pool.split(':')
    return os.path.exists(os.path.join(PACK_DATA, ns, 'worldgen', 'template_pool', path + '.json'))


def pool_pieces(pool):
    """[(template, weight)] of a template pool."""
    ns, path = pool.split(':')
    p = pack_json(os.path.join(ns, 'worldgen', 'template_pool', path + '.json'))
    out = []
    for e in p['elements']:
        el = e['element']
        if el['element_type'] != 'minecraft:single_pool_element':
            raise ValueError('%s: %s pieces are not drawn' % (pool, el['element_type']))
        out.append((el['location'], e['weight']))
    return out


def jigsaw_graph(start_pool):
    """Walk a jigsaw structure from its start pool the way the game joins pieces: a connector picks a
    piece from its pool and joins one of that piece's connectors whose name is its target; the piece's
    other connectors lead on. Returns ({template: [onward pools]}, {template: pools it is in}, missing pools)."""
    onward, member, missing = {}, {}, set()
    queue = [(start_pool, None)]
    seen = set()
    while queue:
        pool, target = queue.pop(0)
        if (pool, target) in seen:
            continue
        seen.add((pool, target))
        if not pool_exists(pool):
            missing.add(pool)
            continue
        for template, _ in pool_pieces(pool):
            member.setdefault(template, set()).add(pool)
            conns = jigsaws(template)
            if target is not None:  # the connector it joins by is used up
                entry = next((c for c in conns if c[0] == target), None)
                if entry is None:
                    continue  # no connector to join by: the game never picks it here
                conns = [c for c in conns if c is not entry]
            if template in onward and onward[template] != [c[1] for c in conns]:
                raise ValueError('%s leads on differently depending on how it is joined' % template)
            onward[template] = [c[1] for c in conns]
            queue += [(c[1], c[2]) for c in conns]
    return onward, member, missing


ABBEY_POOLS = {  # the page's names for the pools
    'minecraft:abbey/overgrown/tower': ('Tower', 'on the surface'),
    'minecraft:abbey/default/entrances': ('Entrance', 'shaft down'),
    'minecraft:abbey/default/entrance_rooms': ('Tutorial', 'the hub'),
    'minecraft:abbey/default/dungeon_rooms': ('Combat rooms', None),
    'minecraft:abbey/default/puzzle_rooms': ('Puzzle rooms', None),
    'minecraft:abbey/default/boon_rooms': ('Reward rooms', 'dead ends'),
}
KIND = {'minecraft:abbey/default/dungeon_rooms': '@red', 'minecraft:abbey/default/puzzle_rooms': '@purple',
        'minecraft:abbey/default/boon_rooms': '@green'}


def room_name(template):
    name = template.split('/')[-1].replace('boon_', '').replace('_', ' ')
    return name[0].upper() + name[1:]


@diagram('Abbey rooms')
def abbey_rooms():
    st = pack_json('minecraft/worldgen/structure/abbey_overgrown.json')
    start = st['start_pool']
    onward, member, missing = jigsaw_graph(start)
    pools = {}
    for template, ps in member.items():
        for p in ps:
            pools.setdefault(p, []).append(template)
    for p in ABBEY_POOLS:
        if p not in pools:
            raise ValueError('the Abbey no longer reaches %s' % p)
    extra = set(pools) - set(ABBEY_POOLS)
    if extra:
        raise ValueError('new Abbey pools to draw: %s' % sorted(extra))
    pool_dir = os.path.join(PACK_DATA, 'minecraft', 'worldgen', 'template_pool', 'abbey')
    unused = sorted('minecraft:abbey/' + os.path.relpath(os.path.join(d, f), pool_dir)[:-5]
                    for d, _, fs in os.walk(pool_dir) for f in fs if f.endswith('.json'))
    unused = [p for p in unused if p not in pools]

    W = 760
    svg = Svg(W, 0, "How the Abbey's rooms connect: tower, entrance, tutorial hub, then combat, puzzle and reward rooms")
    f = Flow(svg)
    chain = [p for p in ABBEY_POOLS if p not in KIND]
    # which pool leads to which (the chain pools hold one piece each)
    for p in chain:
        assert len(pools[p]) == 1, p

    # the chain across the top
    top = 30
    xs = [82, 262, 470]
    for p, x in zip(chain, xs):
        label, sub = ABBEY_POOLS[p]
        f.node(p, x, top, label, w=150, h=42, sub=sub, bold=True)
    for a, b in zip(chain, chain[1:]):
        assert b in onward[pools[a][0]], (a, b)
        f.arrow(a, b)

    # the three room pools as panels of rows: name, weight, and a chip per onward connector
    row_h, head_h = 25, 30
    panels = {'minecraft:abbey/default/boon_rooms': (12, 170),
              'minecraft:abbey/default/dungeon_rooms': (224, 262),
              'minecraft:abbey/default/puzzle_rooms': (528, 220)}
    py = 118
    boxes = {}
    for p, (x, w) in panels.items():
        rooms = pool_pieces(p)
        h = head_h + row_h * len(rooms) + 8
        colour = KIND[p]
        svg.rect(x, py, w, h, fill='@panel', stroke=colour, rx=6, sw=1.2)
        label, sub = ABBEY_POOLS[p]
        svg.text(x + 12, py + 17, label, bold=True, fill=colour)
        if sub:
            svg.text(x + 12 + text_width(label, TEXT, True) + 8, py + 17, sub, size=SMALL, fill='@muted')
        weights = len({wt for _, wt in rooms}) > 1
        if weights:
            svg.text(x + w - 12, py + 17, 'weight', size=SMALL, fill='@muted', anchor='end')
        for i, (template, wt) in enumerate(rooms):
            ry = py + head_h + row_h * i + row_h / 2
            svg.text(x + 12, ry, room_name(template))
            cx = x + w - (46 if weights else 14)
            for q in sorted(onward[template], key=lambda q: list(KIND).index(q) if q in KIND else 9, reverse=True):
                if q in KIND:
                    svg.rect(cx - 9, ry - 6, 11, 11, fill=KIND[q], rx=2)
                else:
                    svg.rect(cx - 9, ry - 6, 11, 11, fill='none', stroke='@grey', rx=2, sw=1.2, dash='2 2')
                cx -= 15
            if weights:
                svg.text(x + w - 12, ry, str(wt), size=SMALL, fill='@muted', anchor='end')
        boxes[p] = (x, py, w, h)

    def kinds_from(pool):
        return {q for t in pools[pool] for q in onward[t]}

    hub = chain[-1]
    hx, hy, hw, hh = f.nodes[hub]
    # the hub down into each room pool
    for p, (x, y, w, h) in boxes.items():
        assert p in kinds_from(hub), p
    cb, pb, bb = (boxes[k] for k in ('minecraft:abbey/default/dungeon_rooms', 'minecraft:abbey/default/puzzle_rooms',
                                     'minecraft:abbey/default/boon_rooms'))
    lane = (hy + hh / 2 + py) / 2
    out = hy + hh / 2 + 3
    svg.line(hx, out, hx, cb[1] - 4, stroke='@red', sw=1.5, arrow=True)
    svg.poly([(hx + 45, out), (hx + 45, lane), (pb[0] + pb[2] / 2, lane), (pb[0] + pb[2] / 2, pb[1] - 4)],
             stroke='@purple', arrow=True)
    svg.poly([(hx - 45, out), (hx - 45, lane), (bb[0] + bb[2] / 2, lane), (bb[0] + bb[2] / 2, bb[1] - 4)],
             stroke='@green', arrow=True)
    # between the panels
    mid_c = cb[1] + cb[3] / 2
    gap_l, gap_r = cb[0] + cb[2], pb[0]
    assert 'minecraft:abbey/default/puzzle_rooms' in kinds_from('minecraft:abbey/default/dungeon_rooms')
    assert 'minecraft:abbey/default/dungeon_rooms' in kinds_from('minecraft:abbey/default/puzzle_rooms')
    svg.line(gap_l + 3, mid_c - 12, gap_r - 4, mid_c - 12, stroke='@purple', sw=1.5, arrow=True)
    svg.line(gap_r - 3, mid_c + 12, gap_l + 4, mid_c + 12, stroke='@red', sw=1.5, arrow=True)
    svg.line(cb[0] - 3, mid_c, bb[0] + bb[2] + 4, mid_c, stroke='@green', sw=1.5, arrow=True)
    if 'minecraft:abbey/default/dungeon_rooms' in kinds_from('minecraft:abbey/default/dungeon_rooms'):
        # combat rooms that lead on to another combat room: a loop under the panel
        lx, ly = cb[0] + cb[2] - 70, cb[1] + cb[3]
        svg.path('M%s %s C%s %s %s %s %s %s' % (lx - 16, ly + 3, lx - 16, ly + 26, lx + 16, ly + 26, lx + 16, ly + 4),
                 stroke='@red', arrow=True)
    bottom = max(b[1] + b[3] for b in boxes.values())
    if 'minecraft:abbey/default/boon_rooms' in kinds_from('minecraft:abbey/default/puzzle_rooms'):
        by = bottom + 30
        svg.poly([(pb[0] + pb[2] / 2, pb[1] + pb[3] + 3), (pb[0] + pb[2] / 2, by), (bb[0] + bb[2] / 2, by),
                  (bb[0] + bb[2] / 2, bb[1] + bb[3] + 4)], stroke='@green', arrow=True)
        bottom = by

    y = bottom + 28
    legend(svg, 12, y, [('@red', 'Combat room', 'box'), ('@purple', 'Puzzle room', 'box'), ('@green', 'Reward room', 'box')])
    svg.rect(360, y - 6, 12, 12, fill='none', stroke='@grey', rx=2, sw=1.2, dash='2 2')
    svg.text(378, y, 'Nothing: its pool does not exist (%s)' % ', '.join(p.split('/')[-1] for p in sorted(missing)),
             size=SMALL, fill='@muted')
    y += 22
    svg.text(12, y, "A room's squares are its other doorways and where they lead.", size=SMALL, fill='@muted')
    y += 18
    svg.text(12, y, 'Rooms keep branching until the structure is %d pieces deep or %d blocks from the tower.'
             % (st['size'], st['max_distance_from_center']), size=SMALL, fill='@muted')
    if unused:
        y += 18
        svg.text(12, y, 'Pools never used: %s' % ', '.join(p.split(':')[1] for p in unused), size=SMALL, fill='@muted')
    svg.h = y + 12
    return svg
