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
