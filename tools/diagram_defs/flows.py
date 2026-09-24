"""Flow charts of the pack's chains and checks: progression, the Hell-Bound Book, the spawn check,
the warding level, the sacred texts and heart loss. Node contents come from the recipes, loot tables,
trades and functions, and a missing recipe or changed function raises, so CI notices."""
import re

from diagrams import SMALL, TEXT, Flow, Svg, asset_uri, data, diagram, legend, mcfunction, need, pack_json, text_width


# ---------------------------------------------------------------------------------------------
# Data helpers

def recipes(output, station=None, src=None):
    """Every recipe (the pack's and the vanilla ones it keeps) that makes an item."""
    d = data()
    out = [r for r in d['recipes'] + d['vanilla_recipes_kept'] if r['output']['name'] == output
           and (station is None or r.get('station') == station) and (src is None or src in r['src'])]
    if not out:
        raise ValueError('diagram data not found: recipe for %s%s%s' % (
            output, ' at ' + station if station else '', ' in ' + src if src else ''))
    return out


def recipe(output, station=None, src=None):
    return recipes(output, station, src)[0]


def ingredients(r):
    """{name: count} for a recipe; a slot that takes several items counts under its first."""
    slots = []
    if r.get('pattern'):
        slots = [r['key'][c] for row in r['pattern'] for c in row if c != ' ']
    elif r.get('ingredients'):
        slots = r['ingredients']
    elif r.get('input'):
        slots = [r['input']]
    out = {}
    for s in slots:
        name = s['names'][0]
        out[name] = out.get(name, 0) + 1
    return out


def plural(name, count):
    low = name.lower()
    if count > 1 and not low.endswith(('s', 'mud', 'stone', 'deepslate', 'ash', 'hellspore')):
        low += 's'
    return low


def stations_for(output):
    return {r.get('station') for r in recipes(output)}


def advancements_with_reward(function):
    return {k.split('/')[-1]: a for k, a in data()['advancements'].items()
            if (a.get('rewards') or {}).get('function') == function}


def loot_tables_giving(item=None, table=None):
    """Loot tables with an entry for an item (or that roll another table): {table id: [entries]}."""
    out = {}
    for tid, t in data()['loot'].items():
        hits = [e for e in t['entries'] if (item and e.get('item') == item) or (table and e.get('loot_table') == table)]
        if hits:
            out[tid] = hits
    return out


def trades(wants=None, gives=None):
    """[(profession name, level, trade)] for villager trades matching the item names."""
    d = data()
    out = []
    for prof, levels in d['trades'].items():
        for level, ts in levels.items():
            for t in ts:
                w = {t['wants']['name']} | ({t['additional_wants']['name']} if t.get('additional_wants') else set())
                if (wants is None or wants in w) and (gives is None or t['gives']['name'] == gives):
                    out.append((d['professions'].get(prof, prof), int(level.split('_')[1]), t))
    return out


def one(items, what):
    if not items:
        raise ValueError('diagram data not found: ' + what)
    return items


# ---------------------------------------------------------------------------------------------
# Drawing helpers (on top of Flow)

def icons_node(f, key, x, y, items, w, h=40, label=None, fill='@panel', edge='@panel_edge'):
    """A node showing a recipe's ingredients as icons with counts ([(name, count)]), plus an optional label."""
    svg = f.svg
    svg.rect(x - w / 2, y - h / 2, w, h, fill=fill, stroke=edge, rx=6, sw=1.2)
    step = 44
    total = step * len(items) + (text_width(label, SMALL) + 6 if label else 0)
    cx = x - total / 2 + step / 2
    for name, count in items:
        svg.icon(name, cx - 4, y, 26)
        if count > 1:
            svg.text(cx + 12, y + 8, '×%d' % count, size=SMALL, fill='@muted', anchor='middle')
        cx += step
    if label:
        svg.text(cx - step / 2 + 4, y, label, size=SMALL, fill='@muted')
    f.nodes[key] = (x, y, w, h)


def badge(svg, x, y, count):
    """A red pill with the pack's heart and '-n', for milestones that lower the minimum hearts."""
    text = '−%d' % count
    w = 30 + text_width(text, SMALL)
    svg.rect(x - w / 2, y - 10, w, 20, fill='@red_soft', stroke='@red', rx=10, sw=1.2)
    svg.sprite(asset_uri('heart-full.png'), x - w / 2 + 13, y, 12)
    svg.text(x - w / 2 + 23, y + 0.5, text, size=SMALL, fill='@red', bold=True)
    return w


def label_at(svg, x, y, s, anchor='middle', fill='@muted'):
    svg.text(x, y, s, size=SMALL, fill=fill, anchor=anchor)


# ---------------------------------------------------------------------------------------------
# Progression

@diagram('Progression')
def progression():
    d = data()
    lower = 'matcha:mechanics/heart_container/decrease_minimum_hearts'
    per = need(r'scoreboard players remove @s minimum_hearts (\d+)',
               mcfunction('matcha/function/mechanics/heart_container/decrease_minimum_hearts.mcfunction'),
               'minimum hearts lost per milestone', cast=int)

    def made(output, station):
        if station not in stations_for(output):
            raise ValueError('diagram data not found: %s made in %s' % (output, station))
        return station

    def needs(output, drop=('Kindling',)):
        ing = ingredients(recipe(output, 'Crafting Table'))
        return ', '.join(plural(n, c) for n, c in ing.items() if n not in drop)

    # the chain: (key, label, icon, how, advancements that lower the minimum hearts)
    for tool in ('pickaxe', 'axe', 'shovel', 'sword', 'hoe'):
        if 'recipe/stone_%s.json' % tool not in d['blocked_vanilla']:
            raise ValueError('diagram data not found: stone %s recipe blocked' % tool)
    recipe('Tinder', 'Crafting Table'), recipe('Fire Starter', 'Crafting Table')
    grass = recipe('Short Dry Grass', 'Kindling')
    metals = ['Iron Ingot', 'Gold Ingot', 'Silver Bullion', 'Diamond']
    for m in metals:
        made(m, 'Blast Furnace')
    steel = recipe('Steel Alloy', 'Blast Furnace')
    if 'Carbon-Rich Iron' not in ingredients(steel):
        raise ValueError('diagram data not found: steel from carbon-rich iron')
    smith = sorted({r['station'] for r in d['recipes'] if r['output']['name'].startswith('Electrum ') and r.get('base')})
    eye = ingredients(recipe('Eye of Ender', 'Crafting Table'))
    stages = [
        ('wood', 'Wood', 'Oak Log', 'wooden tools, no stone tools', []),
        ('fire', 'Kindling', 'Kindling', 'lit with tinder or fire starter', []),
        ('grass', 'Dry grass', 'Short Dry Grass', 'grass cooked %d s on kindling' % (grass['cookingtime'] / 20), []),
        ('kiln', 'Mud kiln', 'Mud Kiln', needs('Mud Kiln'), []),
        ('copper', 'Copper', 'Copper Ingot', 'raw copper in the ' + made('Copper Ingot', 'Mud Kiln').lower(), ['obtain_copper']),
        ('blast', 'Blast furnace', 'Blast Furnace', needs('Blast Furnace'), []),
        ('metals', 'Metals', 'Iron Ingot', ', '.join(m.split()[0].lower() for m in metals),
         ['obtain_iron_ingot', 'obtain_diamond']),
        ('oven', 'Oven', 'Oven', needs('Oven'), []),
        ('steel', 'Steel', 'Steel Alloy', 'carbon-rich iron, blasted', []),
        ('alloys', 'Alloys', 'Electrum Alloy', 'applied at the ' + smith[0].lower(), ['obtain_electrum', 'obtain_adamant']),
        ('magic', 'Magic', 'Stabilized Estus', 'estus, benzene from Hell', ['enter_nether']),
        ('end', 'The End', 'Eye of Ender', 'eyes of ender, a stronghold', ['find_stronghold']),
    ]
    if 'Stabilized Estus' not in eye:
        raise ValueError('diagram data not found: eyes of ender from stabilized estus')
    milestones = advancements_with_reward(lower)
    drawn = {a for s in stages for a in s[4]}
    if drawn != set(milestones):
        raise ValueError('minimum-hearts milestones changed: drawn %s, pack %s' % (sorted(drawn), sorted(milestones)))

    cols, w, h = [115, 380, 645], 230, 50
    top, pitch = 34, 84
    svg = Svg(760, 0, 'Progression in Matcha Flavoured: wood, kindling, the mud kiln, copper, the blast furnace, '
                      'metals, the oven, steel, alloys, magic and the End, with the milestones that lower the minimum hearts')
    f = Flow(svg)
    for i, (key, label, icon, how, advs) in enumerate(stages):
        row, col = divmod(i, 3)
        x = cols[col if row % 2 == 0 else 2 - col]
        y = top + row * pitch
        f.node(key, x, y, label, w=w, h=h, icon=icon, sub=how, bold=True, edge='@red' if advs else '@panel_edge')
        if advs:
            badge(svg, x + w / 2 - 26, y - h / 2, len(advs) * per // 2)
    for (a, *_), (b, *_) in zip(stages, stages[1:]):
        f.arrow(a, b)
    y = top + 3 * pitch + h / 2 + 26
    x = cols[0] - w / 2
    x += badge(svg, x + 20, y + 8, 1) + 8
    names = [milestones[a]['title'] for s in stages for a in s[4]]
    svg.text(x, y, 'Milestones that lower the minimum hearts by %s each:' % ('one heart' if per == 2 else '%d HP' % per),
             size=SMALL, fill='@muted')
    svg.text(x, y + 17, ', '.join(names) + '.', size=SMALL, fill='@muted')
    svg.h = y + 30
    return svg


# ---------------------------------------------------------------------------------------------
# Routing helpers for charts with tall "bus" nodes, where Flow.arrow's centre-to-centre clipping
# would give slanted ends

def side(f, key, s, at=None, gap=3):
    """A point just outside one side of a node: s is 'l', 'r', 't' or 'b'; at is the y (or x) along it."""
    x, y, w, h = f.nodes[key]
    if s in 'lr':
        return (x - w / 2 - gap if s == 'l' else x + w / 2 + gap, y if at is None else at)
    return (x if at is None else at, y - h / 2 - gap if s == 't' else y + h / 2 + gap)


def route(f, pts, colour='@rule', label=None, at=None, anchor='middle', dash=None):
    """An arrow along the given points, with an optional label at `at` (x, y)."""
    f.svg.poly(pts, stroke=colour, sw=1.5, dash=dash, arrow=True)
    if label:
        x, y = at or ((pts[0][0] + pts[-1][0]) / 2, (pts[0][1] + pts[-1][1]) / 2 - 9)
        label_at(f.svg, x, y, label, anchor=anchor)


def hop(f, a, b, y=None, colour='@rule', label=None):
    """A level arrow from node a's facing side to node b's, at height y."""
    ax, bx = f.nodes[a][0], f.nodes[b][0]
    y = f.nodes[a][1] if y is None else y
    p1 = side(f, a, 'r' if bx > ax else 'l', y)
    p2 = side(f, b, 'l' if bx > ax else 'r', y, gap=4)
    route(f, [p1, p2], colour, label, at=((p1[0] + p2[0]) / 2, y - 9) if label else None)


def block(f, key, x, y, w, h, title, lines=(), fill='@panel', edge='@panel_edge', ink='@ink', icon=None, sub_ink='@muted'):
    """A node with a bold title and several lines under it, centred as a group."""
    svg = f.svg
    svg.rect(x - w / 2, y - h / 2, w, h, fill=fill, stroke=edge, rx=6, sw=1.2)
    tx = x
    if icon:
        svg.icon(icon, x - w / 2 + 19, y, 26)
        tx = x + 14
    y0 = y - 8 * len(lines)
    svg.text(tx, y0, title, anchor='middle', bold=True, fill=ink)
    for i, line in enumerate(lines):
        svg.text(tx, y0 + 17 * (i + 1), line, size=SMALL, anchor='middle', fill=sub_ink)
    f.nodes[key] = (x, y, w, h)


def split_label(names, width, size=TEXT):
    """Join names into a label that fits `width`, and the rest into an 'and ...' line."""
    for k in range(len(names), 0, -1):
        head = ', '.join(names[:k])
        if text_width(head, size) <= width:
            rest = names[k:]
            return head[0].upper() + head[1:], ('and ' + ', '.join(rest)) if rest else None
    return names[0], None


def mob_name(table):
    """'minecraft:entities/zombie_villager' -> 'zombie villagers'."""
    n = table.split('/')[-1].replace('_', ' ')
    return n if n.endswith(('drowned', 's')) else n + 's'


def undead():
    out = set()
    for v in pack_json('minecraft/tags/entity_type/undead.json')['values']:
        if v.startswith('#'):
            out |= set(pack_json('minecraft/tags/entity_type/%s.json' % v[1:].split(':')[1])['values'])
        else:
            out.add(v)
    return {v.split(':')[1] for v in out}


# ---------------------------------------------------------------------------------------------
# Hell-Bound Book (Enchanting)

@diagram('Hell-Bound Book')
def hell_bound_book():
    und = undead()

    def mobs(item):
        tables = [t for t in loot_tables_giving(item=item) if t.startswith('minecraft:entities/')]
        return sorted(mob_name(t) for t in tables if t.split('/')[-1] in und)

    conv = mcfunction('matcha/function/mechanics/estus/estus_effects.mcfunction')
    d = data()['items']
    raw_id, ash_id = d['Raw Estus']['base_id'].split(':')[1], d['Estus Ash']['base_id'].split(':')[1]
    need(r'give @s (?:minecraft:)?%s (\d+)' % ash_id, conv, 'Raw Estus turns into Estus Ash')
    need(r'clear @s (?:minecraft:)?%s (\d+)' % raw_id, conv, 'Raw Estus cleared on pickup')
    raw_mobs, ash_mobs = one(mobs('Raw Estus'), 'undead dropping Raw Estus'), one(mobs('Estus Ash'), 'undead dropping Estus Ash')
    void_mobs = one(sorted(mob_name(t) for t in loot_tables_giving(item='Stable Void') if t.startswith('minecraft:entities/')),
                    'mobs dropping Stable Void')
    benzene = ingredients(recipe('Benzene', 'Crafting Table'))
    stab = ingredients(recipe('Stabilized Estus', 'Crafting Table'))
    book = ingredients(recipe('Hell-Bound Book', 'Crafting Table'))
    for want in ('Estus Ash', 'Benzene', 'Stable Void'):
        if want not in stab:
            raise ValueError('diagram data not found: %s in Stabilized Estus' % want)
    for want in ('Benzene', 'Stabilized Estus', 'Book'):
        if want not in book:
            raise ValueError('diagram data not found: %s in the Hell-Bound Book' % want)
    blessings = sorted(r['output']['name'] for r in data()['recipes']
                       if r.get('folder') == 'blessing' and 'Hell-Bound Book' in ingredients(r))
    one(blessings, 'blessing recipes')

    svg = Svg(760, 0, 'How to make a Hell-Bound Book: Estus Ash from undead, Benzene, and a Stable Void make '
                      'Stabilized Estus, which with a book and a second Benzene makes the book')
    f = Flow(svg)
    A, B, C, D = 100, 285, 462, 660
    ys = [30, 94, 158, 222]
    for key, y, names in (('raw_mobs', ys[0], raw_mobs), ('ash_mobs', ys[1], ash_mobs)):
        head, tail = split_label(names, 150)
        f.node(key, A, y, head, w=180, h=46, sub=tail)
    f.node('void_mob', A, ys[2], split_label(void_mobs, 150)[0], w=180, h=46)
    icons_node(f, 'bz_in', A, ys[3], list(benzene.items()), w=180, h=46)
    f.node('raw', B, ys[0], 'Raw Estus', w=140, h=46, icon='Raw Estus')
    f.node('ash', B, ys[1], 'Estus Ash', w=140, h=46, icon='Estus Ash')
    f.node('void', B, ys[2], 'Stable Void', w=140, h=46, icon='Stable Void')
    f.node('benzene', B, ys[3], 'Benzene', w=140, h=46, icon='Benzene', edge='@purple')
    mid = (ys[1] + ys[2]) / 2
    f.node('stab', C, mid, 'Stabilized Estus', w=172, h=46, icon='Stabilized Estus', bold=True)
    f.node('book', D, ys[0], 'Book', w=160, h=46, icon='Book')
    f.node('hbb', D, mid, 'Hell-Bound Book', w=172, h=46, icon='Hell-Bound Book', bold=True)
    f.node('blessing', D, ys[3], 'Blessing', w=160, h=46, icon=blessings[0], sub='%d recipes' % len(blessings))
    f.node('anvil', D, ys[3] + 72, 'Anvil', w=160, h=46, icon='Anvil', sub='onto armor or tools')

    f.arrow('raw_mobs', 'raw')
    f.arrow('raw', 'ash', 'on pickup')
    f.arrow('ash_mobs', 'ash')
    f.arrow('void_mob', 'void')
    f.arrow('bz_in', 'benzene')
    f.arrow('ash', 'stab', '×%d' % stab['Estus Ash'])
    f.arrow('void', 'stab', '×%d' % stab['Stable Void'], label_side='below')
    f.arrow('benzene', 'stab', '×%d' % stab['Benzene'], colour='@purple')
    f.arrow('stab', 'hbb')
    f.arrow('book', 'hbb')
    f.arrow('benzene', 'hbb', '×%d again' % book['Benzene'], colour='@purple', label_side='below')
    f.arrow('hbb', 'blessing')
    f.arrow('blessing', 'anvil')
    svg.h = ys[3] + 72 + 30
    return svg


# ---------------------------------------------------------------------------------------------
# Spawn check (Spawning)

STRUCTURE_NAMES = {'minecraft:trial_chambers': 'trial chambers', 'minecraft:abbey_overgrown': 'abbeys'}


@diagram('Spawn check')
def spawn_check():
    mobs = pack_json('matcha/tags/entity_type/mundane_hostiles.json')['values']
    tick = mcfunction('matcha/function/mechanics/spawn_mechanic/ticking.mcfunction')
    need(r'if score gamerule gamerule_safe_surface matches (1) run .*safe_surface', tick, 'safe surface branch')
    need(r'unless score gamerule gamerule_safe_surface matches (1) run .*check_mob_spawn', tick, 'normal branch')
    need(r'scoreboard players set gamerule gamerule_safe_surface (1)',
         mcfunction('matcha/function/mechanics/first_dragon_killed_reward.mcfunction'), 'dragon kill sets safe surface')
    src = mcfunction('matcha/function/mechanics/spawn_mechanic/check_mob_spawn.mcfunction')
    lines = [l for l in src.splitlines() if l.startswith('execute')]

    def find(*bits):
        for i, l in enumerate(lines):
            if all(b in l for b in bits):
                return i, l
        raise ValueError('diagram data not found: spawn check line with %s' % (bits,))
    creeper = find('is_creeper', 'surface_spawn', 'SpawnForbidden')
    camel = find('is_husk', 'riding_camel_husk', 'remove_camel_husk_jockey')
    sky = find('unless entity @s[type=#minecraft:undead]', 'sky_spawn', 'SpawnForbidden')
    if not creeper[0] < camel[0] < sky[0]:
        raise ValueError('spawn check order changed')
    if 'dimension' in creeper[1] or 'if dimension minecraft:overworld' not in camel[1] + sky[1] or \
            sky[1].count('if dimension minecraft:overworld') != 1:
        raise ValueError('spawn check dimensions changed')
    drop = need(r'tp @s ~ ~-(\d+) ~', src, 'removal teleport', cast=int)
    need(r'tag=!SpawnForbidden\] run function matcha:mechanics/spawn_mechanic/(modify_mob)', src, 'modify kept mobs', cast=str)
    if pack_json('matcha/predicate/sky_spawn.json')['terms'][0]['predicate']['minecraft:location'] != {'can_see_sky': True}:
        raise ValueError('sky_spawn predicate changed')
    surf = pack_json('matcha/predicate/surface_spawn.json')['terms']
    if surf[0]['predicate']['minecraft:location'] != {'can_see_sky': True}:
        raise ValueError('surface_spawn predicate changed')
    ymin = surf[1]['terms'][0]['predicate']['minecraft:location']['position']['y']['min']
    if surf[1]['terms'][1]['term']['name'] != 'matcha:in_dungeon':
        raise ValueError('surface_spawn exemption changed')
    places = [STRUCTURE_NAMES[s] for s in
              pack_json('matcha/predicate/in_dungeon.json')['terms'][0]['predicate']['location']['structures']]
    husk = pack_file_text('matcha/function/mechanics/spawn_mechanic/remove_camel_husk_jockey.mcfunction')
    need(r'summon (?:minecraft:)?(husk)', husk, 'camel jockey replaced by a husk', cast=str)

    svg = Svg(760, 0, 'The spawn check run on every new mundane hostile mob: which are removed and which are kept')
    f = Flow(svg)
    K, Q, R = 85, 390, 672
    qw, h, pitch, top = 300, 44, 62, 26
    ys = [top + pitch * i for i in range(7)]
    f.node('start', Q, ys[0], 'A mundane hostile mob appears', w=qw, h=h, sub='%d types, each checked once' % len(mobs),
           fill='@blue_soft', edge='@blue', bold=True)
    qs = [('dragon', 'Has the Ender Dragon been killed?', None),
          ('creeper', 'A creeper that can see the sky, or at', 'Y %d or above outside %s?' % (ymin, ' and '.join(places))),
          ('overworld', 'In the Overworld?', None),
          ('camel', 'A husk riding a camel husk?', None),
          ('undead', 'Undead?', None),
          ('sky', 'Can it see the sky?', None)]
    for (key, label, sub), y in zip(qs, ys[1:]):
        if sub:
            f.node(key, Q, y, label, w=qw, h=h + 6, sub=sub)
        else:
            f.node(key, Q, y, label, w=qw, h=h)
    f.node('surface', R, ys[1], 'Stricter check', w=150, h=h, sub='see Surface', fill='@blue_soft', edge='@blue')
    rtop, rbot = ys[2] - h / 2, ys[6] + h / 2
    block(f, 'removed', R, (rtop + rbot) / 2, 150, rbot - rtop, 'Removed',
          ['teleported %s' % format(drop, ','), 'blocks down,', 'then killed'], fill='@red_soft', edge='@red', ink='@red')
    ktop = ys[3] - h / 2
    block(f, 'kept', K, (ktop + rbot) / 2, 140, rbot - ktop, 'Kept', ['modified for', 'the difficulty'],
          fill='@green_soft', edge='@green', ink='@green')
    f.arrow('start', 'dragon')
    hop(f, 'dragon', 'surface', label='yes', colour='@blue')
    f.arrow('dragon', 'creeper', 'no')
    hop(f, 'creeper', 'removed', label='yes', colour='@red')
    f.arrow('creeper', 'overworld', 'no')
    hop(f, 'overworld', 'kept', label='no', colour='@green')
    f.arrow('overworld', 'camel', 'yes')
    hop(f, 'camel', 'removed', label='yes', colour='@red')
    f.arrow('camel', 'undead', 'no')
    hop(f, 'undead', 'kept', label='yes', colour='@green')
    f.arrow('undead', 'sky', 'no')
    hop(f, 'sky', 'removed', label='yes', colour='@red')
    hop(f, 'sky', 'kept', label='no', colour='@green')
    label_at(svg, R, ys[4] + 30, 'a husk on foot', fill='@red')
    label_at(svg, R, ys[4] + 45, 'takes its place', fill='@red')
    svg.h = rbot + 6
    return svg


def pack_file_text(rel):
    return mcfunction(rel)


# ---------------------------------------------------------------------------------------------
# Warding level (Warding)

@diagram('Warding level')
def warding_level():
    calc = mcfunction('matcha/function/enchantment_effects/warding/value/calculate.mcfunction')
    need(r'WardingPower = @s (warding_equipment)', calc, 'held warding first', cast=str)
    need(r'WardingPower < \$Max (warding_equipment)', calc, 'held warding capped', cast=str)
    need(r'WardingPower > @s (electrum_armour)', calc, 'higher of held and armor', cast=str)
    cap = need(r'scoreboard players set \$Max warding_equipment (\d+)',
               mcfunction('matcha/function/setup/scoreboard/create_scoreboards.mcfunction'), 'held warding cap', cast=int)
    per = need(r'scoreboard players add @s electrum_armour (\d+)',
               mcfunction('matcha/function/enchantment_effects/warding/value/electrum_armour.mcfunction'), 'per piece', cast=int)
    held = {}
    for lv in range(1, 5):
        ench = pack_json('matcha/enchantment/warding_%d.json' % lv)
        if sorted(ench['slots']) != ['mainhand', 'offhand']:
            raise ValueError('warding %d slots changed' % lv)
        held[lv] = need(r'scoreboard players add @s warding_equipment (\d+)',
                        mcfunction('matcha/function/enchantment_effects/warding/value/equipment_%d.mcfunction' % lv),
                        'warding %d adds' % lv, cast=int)
    if pack_json('matcha/enchantment/electrum_armour.json')['slots'] != ['armor']:
        raise ValueError('electrum armor slots changed')
    pieces = 4 * per

    def level(item):
        c = data()['items'][item]['components']
        for k in list((c.get('enchantments') or {})) + list((c.get('stored_enchantments') or {})):
            m = re.match(r'matcha:warding_(\d)$', k)
            if m:
                return held[int(m.group(1))]
        raise ValueError('diagram data not found: warding on %s' % item)
    sword, nazar = level('Warding Sword'), level('Nazar')

    svg = Svg(760, 0, 'How the warding level is worked out: held warding summed and capped, then the higher of that '
                      'and the electrum armor count')
    f = Flow(svg)
    A, B, C = 100, 340, 600
    f.node('main', A, 30, 'Main hand', w=170, h=44, icon='Warding Sword', sub='its Warding level')
    f.node('off', A, 90, 'Off hand', w=170, h=44, icon='Nazar', sub='its Warding level')
    f.node('armor', A, 170, 'Electrum armor', w=170, h=44, icon='Electrum Chestplate', sub='+%d per piece worn' % per)
    f.node('held', B, 60, 'Held warding', w=190, h=44, sub='the sum, capped at %d' % cap, fill='@purple_soft', edge='@purple')
    f.node('count', B, 170, 'Armor count', w=190, h=44, sub='0 to %d' % pieces, fill='@purple_soft', edge='@purple')
    f.node('level', C, 115, 'Warding level', w=190, h=44, sub='the higher of the two', bold=True,
           fill='@purple_soft', edge='@purple', ink='@purple')
    f.arrow('main', 'held')
    f.arrow('off', 'held')
    f.arrow('armor', 'count')
    f.arrow('held', 'level')
    f.arrow('count', 'level')
    y = 222
    svg.text(15, y, 'Examples', size=SMALL, bold=True, fill='@muted')
    ex = ['Warding Sword (%d) + Nazar (%d) in the hands: %d' % (sword, nazar, min(cap, sword + nazar)),
          'One electrum piece and a Warding %d item: %d' % (sword, max(min(cap, sword), per)),
          'Full electrum set: %d, the only way to reach it' % pieces]
    for i, e in enumerate(ex):
        svg.text(15, y + 18 * (i + 1), e, size=SMALL, fill='@muted')
    svg.h = y + 18 * len(ex) + 10
    return svg
