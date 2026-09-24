"""Charts of the pack's numbers: minimum hearts, sleep speed, the food level, effect durations,
fishing odds and the release timeline."""
import datetime
import math
import re

from diagrams import SMALL, TEXT, Scale, Svg, data, diagram, legend, mcfunction, need, pack_json, text_width

HEART = 'matcha/function/mechanics/heart_container/'
SLEEP = 'matcha/function/mechanics/sleeping/'


# ---------------------------------------------------------------------------------------------
# Shared axis pieces, in the style of time.py: light gridlines behind, muted tick labels.

def y_grid(svg, y, ticks, left, right, fmt=str):
    def draw():
        for v in ticks:
            svg.line(left, y(v), right, y(v), stroke='@grid')
            svg.text(left - 8, y(v), fmt(v), size=SMALL, fill='@muted', anchor='end')
    svg.behind(draw)


def x_grid(svg, x, ticks, top, bottom, fmt=str, lines=True):
    def draw():
        for v in ticks:
            if lines:
                svg.line(x(v), top, x(v), bottom, stroke='@grid')
            svg.text(x(v), bottom + 14, fmt(v), size=SMALL, fill='@muted', anchor='middle')
    svg.behind(draw)


def mmss(ticks):
    s = round(ticks / 20)
    return '%d:%02d' % (s // 60, s % 60)


def roman(n):
    out = ''
    for v, s in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out, n = out + s, n - v
    return out


# ---------------------------------------------------------------------------------------------
# Death: the floor that maximum health can't fall below, against milestones earned

@diagram('Minimum hearts')
def minimum_hearts():
    dec = mcfunction(HEART + 'decrease_minimum_hearts.mcfunction')
    boards = mcfunction('matcha/function/setup/scoreboard/create_scoreboards.mcfunction')
    setup = mcfunction('matcha/function/setup/scoreboard/player_setup.mcfunction')
    setmax = mcfunction(HEART + 'set_max_hp.mcfunction')
    down = mcfunction(HEART + 'hpdown.mcfunction')
    step = need(r'scoreboard players remove @s minimum_hearts (\d+)', dec, 'minimum hearts step', cast=int)
    start = need(r'run scoreboard players set @s minimum_hearts (\d+)', setup, 'starting minimum', cast=int)
    cap = need(r'players set \$Max Hearts (\d+)', boards, 'health cap', cast=int)
    easy = need(r'players set \$Easy minimum_hearts (\d+)', boards, 'Easy floor', cast=int)
    normal = need(r'players set \$Normal minimum_hearts (\d+)', boards, 'Normal limit', cast=int)
    lowest = need(r'players set \$Hard minimum_hearts (\d+)', boards, 'lowest minimum', cast=int)
    need(r'matches 2 run execute if score @s minimum_hearts < \$Normal minimum_hearts run function \S+increase_difficulty',
         dec, 'Normal to Hard switch', group=0, cast=str)
    need(r'matches 1 run execute if score @s Hearts < \$Easy minimum_hearts', setmax, 'Easy floor in set_max_hp', group=0, cast=str)
    loss = need(r'matches \.\.2 run scoreboard players remove @s Hearts (\d+)', down, 'loss per death', cast=int)
    loss_hard = need(r'matches 3 run scoreboard players remove @s Hearts (\d+)', down, 'loss per death on Hard', cast=int)
    reward = 'matcha:mechanics/heart_container/decrease_minimum_hearts'
    milestones = sum(1 for a in data()['advancements'].values() if (a.get('rewards') or {}).get('function') == reward)
    if not milestones:
        raise ValueError('no advancement lowers the minimum hearts')
    floor = [max(start - k * step, lowest) / 2 for k in range(milestones + 1)]   # in hearts
    switch = next(k for k in range(milestones + 1) if start - k * step < normal)  # first milestone count on Hard
    cap_h, easy_h = cap / 2, easy / 2

    W, left, right, top, bottom = 760, 52, 560, 34, 254
    svg = Svg(W, 0, 'Minimum hearts: the lowest maximum health against the tutorial milestones earned, by difficulty')
    x = Scale(-0.5, milestones + 0.5, left, right)
    y = Scale(0, cap_h, bottom, top)
    col = lambda k: (x(k - 0.5), x(k + 0.5))

    # the hearts deaths can take: between the floor and the cap
    edge = []
    for k, f in enumerate(floor):
        a, b = col(k)
        edge += [(a, y(f)), (b, y(f))]
    svg.poly([(x(-0.5), y(cap_h))] + edge + [(x(milestones + 0.5), y(cap_h))], fill='@red_soft')
    bx = x((switch - 1) / 2)
    svg.text(bx, y((cap_h + floor[0]) / 2) - 9, 'Hearts a death can take', anchor='middle', fill='@red', bold=True)
    svg.text(bx, y((cap_h + floor[0]) / 2) + 9,
             '%s per death, %s on Hard' % (hearts_word(loss / 2), hearts_word(loss_hard / 2)),
             size=SMALL, anchor='middle', fill='@red')
    svg.text(x(0), y(floor[-1] / 2), 'Never lost', size=SMALL, anchor='middle', fill='@muted')

    # the switch to Hard
    sx = x(switch - 0.5)
    svg.line(sx, top - 12, sx, bottom, stroke='@amber', sw=1.5, dash='5 4')
    svg.text(sx, top - 22, 'Normal becomes Hard', size=SMALL, anchor='middle', fill='@amber', bold=True)

    # the cap, Easy's floor and the Normal/Hard floor
    svg.line(left, y(cap_h), right, y(cap_h), stroke='@rule', sw=2)
    svg.line(left, y(easy_h), right, y(easy_h), stroke='@green', sw=2.5, dash='7 4')
    pts = []
    for k, f in enumerate(floor):
        a, b = col(k)
        pts += [(a, y(f)), (b, y(f))]
    svg.poly(pts, stroke='@blue', sw=3, join='miter')
    for k, f in enumerate(floor):
        if k and f != easy_h:
            svg.text(x(k), y(f) + 11, n_(f), size=SMALL, anchor='middle', fill='@blue', bold=True)

    lx = right + 12
    svg.text(lx, y(cap_h) - 8, 'Cap for crystal hearts', size=SMALL, fill='@muted')
    svg.hp(lx, y(cap_h) + 9, cap, size=SMALL, fill='@ink')
    svg.text(lx, y(easy_h) - 8, 'Easy: the floor stays', size=SMALL, fill='@green', bold=True)
    svg.hp(lx, y(easy_h) + 9, easy, size=SMALL, fill='@ink')
    svg.text(lx, y(floor[-1]) - 8, 'Minimum hearts (Normal, Hard)', size=SMALL, fill='@blue', bold=True)
    svg.hp(lx, y(floor[-1]) + 9, floor[-1] * 2, size=SMALL, fill='@ink')

    y_grid(svg, y, range(0, int(cap_h) + 1, 5), left, right)
    x_grid(svg, x, range(milestones + 1), top, bottom, lines=False)
    svg.text(left - 8, top - 22, 'Hearts', size=SMALL, fill='@muted', anchor='end')
    svg.text((left + right) / 2, bottom + 32, 'Milestones earned (tutorial advancements)', size=SMALL, fill='@muted', anchor='middle')
    svg.h = bottom + 44
    return svg


def n_(v):
    return str(int(v)) if v == int(v) else str(v)


def hearts_word(h):
    return '%s heart%s' % (n_(h), '' if h == 1 else 's')


# ---------------------------------------------------------------------------------------------
# Sleeping: how fast time runs against the share of players in bed

@diagram('Sleep speed')
def sleep_speed():
    rate_src = mcfunction(SLEEP + 'calculate_sleep_rate.mcfunction')
    dur_src = mcfunction(SLEEP + 'calculate_sleep_duration.mcfunction')
    base = need(r'players set sleep_rate sleepTimerScore (\d+)', rate_src, 'sleep rate', cast=int)
    ops = re.findall(r'operation sleep_rate sleepTimerScore ([*/])= (\w+) sleepTimerScore', rate_src)
    if ops != [('*', 'players_sleeping')] * 2 + [('/', 'players_in_overworld')] * 2:
        raise ValueError('sleep rate formula changed: %s' % ops)
    day_sleep = need(r'players set @s sleepDuration (\d+)', dur_src, 'daytime sleep', cast=int)

    def rate(s, p):  # the scoreboard's integer arithmetic, one operation at a time
        r = base
        for op, var in ops:
            v = s if var == 'players_sleeping' else p
            r = r * v if op == '*' else r // v
        return r

    W, left, right, top, bottom = 760, 52, 736, 44, 264
    svg = Svg(W, 0, 'Ticks skipped per tick against the share of Overworld players asleep')
    x = Scale(0, 1, left, right)
    y = Scale(0, base, bottom, top)
    svg.poly([(x(i / 100), y(base * (i / 100) ** 2)) for i in range(101)], stroke='@blue', sw=2.5)
    # the page's examples, with the integer result and the time to sleep off half a day
    for s, p in ((1, 4), (1, 3), (1, 2), (3, 4), (1, 1)):
        r = rate(s, p)
        secs = math.ceil(day_sleep / r) / 20
        px, py = x(s / p), y(r)
        svg.circle(px, py, 4.5, fill='@blue', stroke='@paper', sw=1.5)
        name = 'Everyone' if s == p else '%d of %d' % (s, p)
        note = '%d per tick, %s s' % (r, n_(round(secs)))
        if s / p < 0.3 or s == p:   # upper left, clear of the curve
            tx, ty, anchor = px - 10, py - 12, 'end'
        else:                       # to the right, under the curve
            tx, ty, anchor = px + 12, py + 8, 'start'
        svg.text(tx, ty - 8, name, anchor=anchor, bold=True)
        svg.text(tx, ty + 8, note, size=SMALL, anchor=anchor, fill='@muted')
    y_grid(svg, y, range(0, base + 1, 50), left, right)
    x_grid(svg, x, [i / 4 for i in range(5)], top, bottom, fmt=lambda v: '%d%%' % round(v * 100))
    svg.text(left - 8, top - 30, 'Ticks skipped per tick', size=SMALL, fill='@muted')
    svg.text((left + right) / 2, bottom + 32, 'Share of Overworld players asleep', size=SMALL, fill='@muted', anchor='middle')
    svg.text((left + right) / 2, bottom + 48, 'Seconds: real time to sleep %s ticks (half a day)' % format(day_sleep, ','),
             size=SMALL, fill='@muted', anchor='middle')
    svg.h = bottom + 60
    return svg


# ---------------------------------------------------------------------------------------------
# Hunger: the hidden food bar and the two effects that hold it

SPRINT_LEVEL = 6   # vanilla FoodConstants.SPRINT_LEVEL: sprinting needs more than this (game code, not data)
HEAL_LEVEL = 18    # vanilla FoodConstants.HEAL_LEVEL: natural regeneration from this level
MAX_FOOD = 20


@diagram('Food level')
def food_level():
    src = mcfunction('matcha/function/mechanics/manage_hunger.mcfunction')
    hi = need(r'Hunger matches (\d+)\.\. run effect give @p minecraft:hunger', src, 'Hunger threshold', cast=int)
    hunger_amp = need(r'minecraft:hunger \d+ (\d+)', src, 'Hunger level', cast=int)
    lo = need(r'Hunger matches \.\.(\d+) run effect give @p minecraft:saturation', src, 'Saturation threshold', cast=int)
    sat_amp = need(r'minecraft:saturation \d+ (\d+)', src, 'Saturation level', cast=int)
    refill = sat_amp + 1          # Saturation restores amplifier + 1 food points each time it applies
    held = (lo + 1, lo + refill)  # a refill from the threshold lands here, below the drain

    W = 360
    left, right = 14, 346
    cell = (right - left) / MAX_FOOD
    svg = Svg(W, 0, 'The food level from 0 to 20: where the pack gives Saturation and Hunger, and the vanilla thresholds')
    by = 56
    for i in range(1, MAX_FOOD + 1):  # one cell per food point, paired into the bar's ten icons
        x0 = left + (i - 1) * cell + (1.5 if i % 2 else 0.5)
        fill = '@green_soft' if i <= lo else '@red_soft' if i >= hi else '@panel'
        edge = '@green' if i <= lo else '@red' if i >= hi else '@panel_edge'
        if held[0] <= i <= held[1]:
            fill, edge = '@amber_soft', '@amber'
        svg.rect(x0, by, cell - 2, 22, fill=fill, stroke=edge, rx=2)
    cx = lambda v: left + v * cell  # the boundary after v points
    # what the pack does in each zone
    svg.text(cx(lo / 2), 18, 'Saturation %s' % roman(sat_amp + 1), anchor='middle', fill='@green', bold=True)
    svg.text(cx(lo / 2), 35, '+%d a tick' % refill, size=SMALL, anchor='middle', fill='@green')
    mid = (hi - 1 + MAX_FOOD) / 2
    svg.text(cx(mid), 18, 'Hunger %s' % roman(hunger_amp + 1), anchor='middle', fill='@red', bold=True)
    svg.text(cx(mid), 35, 'drains it', size=SMALL, anchor='middle', fill='@red')
    hx = cx((held[0] - 1 + held[1]) / 2)
    svg.text(hx, 18, 'held', anchor='middle', fill='@amber', bold=True)
    svg.line(hx, 28, hx, by - 5, stroke='@amber', sw=1.5, arrow=True)
    # the levels and vanilla's thresholds underneath: cell i is food level i
    for v in sorted({1, lo, hi, HEAL_LEVEL, MAX_FOOD}):
        svg.text(cx(v - 0.5), by + 36, str(v), size=SMALL, anchor='middle', fill='@muted')
    for row, (v, label, anchor) in enumerate(((SPRINT_LEVEL, 'Sprinting above %d' % SPRINT_LEVEL, 'start'),
                                              (HEAL_LEVEL - 1, 'Natural regeneration at %d+ (off)' % HEAL_LEVEL, 'end'))):
        ly = by + 56 + 17 * row
        svg.line(cx(v), by - 4, cx(v), by + 26, stroke='@muted', sw=1.5, dash='3 3')
        svg.line(cx(v), by + 46, cx(v), ly + 6, stroke='@muted', sw=1.5, dash='3 3')
        svg.text(cx(v) + (5 if anchor == 'start' else -5), ly, label, size=SMALL, anchor=anchor, fill='@muted')
    svg.text((left + right) / 2, by + 102, 'Food level (vanilla thresholds dashed)', size=SMALL, anchor='middle', fill='@muted')
    svg.h = by + 114
    return svg


# ---------------------------------------------------------------------------------------------
# Intrinsic: how long each ingredient's effect lasts, from the simple preparation to the meal

# (ingredient item, label, [simple preparation], [preservation], [meal]), in the page's order
INTRINSICS = [
    ('Pumpkin', 'Pumpkin', ['Baked Pumpkin'], ['Pumpkin Jam'], ['Pumpkin Empanada']),
    ('Apple', 'Apple', ['Baked Apple'], ['Canned Apples'], ['Apple Empanada']),
    ('Carrot', 'Carrot', ['Steamed Carrots'], ['Pickled Carrots'], ['Carrot Cupcake']),
    ('Tomatoes', 'Tomatoes', ['Grilled Tomatoes'], ['Sun-dried Tomatoes'], ['Bruschetta']),
    ('Melon Slice', 'Melon', ['Grilled Melon'], ['Rind Jam'], ['Melon Sorbet']),
    ('Sweet Berries', 'Sweet Berries', ['Sweet Berry Mash'], ['Sweet Berry Jam'], ['Sweet Berry Danish']),
    ('Glow Berries', 'Glow Berries', ['Glow Berry Mash'], ['Glow Berry Jam'], ['Glow Berry Crumble']),
    ('Honey Bottle', 'Honey', ['Honey Ginger Tea'], ['Mead'], ['Honied French Toast']),
    ('Cocoa Beans', 'Cocoa Beans', ['Chocolate'], [], ['Chocolate Chip Cookie', 'Brownie']),
    ('Dried Kelp', 'Kelp', ['Dried Kelp'], [], ['Gimmari']),
    ('Chorus Fruit', 'Chorus Fruit', ['Popped Chorus Fruit'], [], ['Chorus Mochi']),
    ('Red Mushroom', 'Red Mushroom', ['Braised Toadstool'], ['Pickled Toadstools'], ['Toadstool Stroganoff']),
]


def made_from(item, ingredient, depth=4):
    """Whether a recipe for item uses the ingredient, directly or through a cooked or crafted step."""
    if item == ingredient:
        return True
    if depth == 0:
        return False
    for r in data()['recipes']:
        if r['output']['name'] != item:
            continue
        slots = [r.get('input'), r.get('base'), r.get('addition')] + list(r.get('ingredients') or [])
        if isinstance(r.get('key'), dict):
            slots += list(r['key'].values())
        names = {nm for s in slots if isinstance(s, dict) for nm in s.get('names', [])}
        if any(made_from(nm, ingredient, depth - 1) for nm in names if nm != item):
            return True
    return False


def aura_seconds(item):
    """Glow berry dishes: an advancement on eating runs a function that schedules the glowing."""
    model = item['components'].get('item_model') or item['base_id']
    for a in data()['advancements'].values():
        crit = [c for c in (a.get('criteria_raw') or {}).values() if c.get('trigger') == 'minecraft:consume_item']
        if any(((c.get('conditions') or {}).get('item') or {}).get('components', {}).get('minecraft:item_model') == model
               for c in crit):
            fn = (a.get('rewards') or {}).get('function', '')
            src = mcfunction(fn.replace(':', '/function/', 1) + '.mcfunction')
            nxt = need(r'schedule function (\S+)', src, 'aura schedule for %s' % item['name'], cast=str)
            glow = mcfunction(nxt.replace(':', '/function/', 1) + '.mcfunction')
            return need(r'minecraft:glowing (\d+)', glow, 'aura duration for %s' % item['name'], cast=int)
    return None


def intrinsic_effect(name):
    """(duration in ticks, level) of a dish's visible effect: the one shown with an icon, not the
    hidden Regeneration III that heals."""
    item = data()['items'][name]
    comp = item['components']
    effects = [e for ce in (comp.get('consumable') or {}).get('on_consume_effects') or []
               if ce.get('type') == 'minecraft:apply_effects' for e in ce.get('effects', [])]
    effects += (comp.get('potion_contents') or {}).get('custom_effects', []) if isinstance(comp.get('potion_contents'), dict) else []
    shown = [e for e in effects if e.get('show_icon', True)]
    if len(shown) == 1:
        return shown[0]['duration'], shown[0].get('amplifier', 0) + 1
    secs = aura_seconds(item)
    if secs is not None and not shown:
        return secs * 20, 1
    raise ValueError('no single intrinsic effect on %s: %s' % (name, shown))


@diagram('Effect durations')
def effect_durations():
    stages = [('Simple preparation', '@amber'), ('Preservation', '@teal'), ('Meal', '@blue')]
    rows = []
    for ingredient, label, *dishes in INTRINSICS:
        pts = []
        for stage, names in enumerate(dishes):
            for nm in names:
                if not made_from(nm, ingredient):
                    raise ValueError('%s is not made from %s' % (nm, ingredient))
                t, level = intrinsic_effect(nm)
                pts.append((stage, t, level))
        rows.append((ingredient, label, pts))

    W, left, right, top, row_h = 760, 170, 736, 50, 27
    longest = max(t for _, _, pts in rows for _, t, _ in pts)
    ticks = [t * 20 for t in (1, 3, 10, 30, 60, 180, 600, 1800) if t * 20 <= longest * 1.8]
    x0, x1 = 16, max(ticks[-1], longest)
    x = lambda t: left + (right - left) * math.log(t / x0) / math.log(x1 / x0)
    svg = Svg(W, 0, 'Effect duration of each ingredient\'s simple preparation, preservation and meal, on a log time scale')
    lx = left
    for s, c in stages:  # the key, with the chart's own dots
        svg.circle(lx + 6, 16, 6, fill=c, stroke='@paper', sw=1.5)
        svg.text(lx + 18, 16, s, size=SMALL, fill='@muted')
        lx += 18 + text_width(s, SMALL) + 22
    y = top
    shorter = []
    for ingredient, label, pts in rows:
        svg.icon(ingredient, 16, y, 20)
        svg.text(32, y, label)
        ts = [t for _, t, _ in pts]
        svg.line(x(min(ts)), y, x(max(ts)), y, stroke='@rule', sw=2)
        before = [(t, level) for stage, t, level in pts if stage < 2]
        for stage, t, level in pts:
            colour = stages[stage][1]
            svg.circle(x(t), y, 6, fill=colour, stroke='@paper', sw=1.5)
            if level > 1:
                svg.text(x(t), y - 13, roman(level), size=10.5, anchor='middle', fill=colour, bold=True)
            longer = [lv for bt, lv in before if bt > t]
            if stage == 2 and longer:
                if not all(level > lv for lv in longer):
                    raise ValueError('%s: a meal shorter than an earlier dish without a higher level' % label)
                shorter.append(label)
                svg.circle(x(t), y, 10, fill='none', stroke='@red', sw=1.5)
        y += row_h
    bottom = y - row_h / 2
    def grid():
        for t in ticks:
            svg.line(x(t), top - row_h / 2, x(t), bottom, stroke='@grid')
            s = t // 20
            svg.text(x(t), bottom + 14, '%d s' % s if s < 60 else '%d min' % (s // 60), size=SMALL, fill='@muted', anchor='middle')
    svg.behind(grid)
    svg.text((left + right) / 2, bottom + 32, 'Effect duration (log scale); roman numerals mark levels above I', size=SMALL,
             fill='@muted', anchor='middle')
    if shorter:
        svg.circle(left + 5, bottom + 52, 7, fill='none', stroke='@red', sw=1.5)
        svg.text(left + 18, bottom + 52, 'Meals that last less than an earlier dish, at a higher level: %s' % ', '.join(shorter),
                 size=SMALL, fill='@muted')
    svg.h = bottom + 64
    return svg


# ---------------------------------------------------------------------------------------------
# Fishing: what one cast can bring up, from the category to the single fish

FISHING = 'minecraft:gameplay/fishing'
RARITY = {1: '@grey', 2: '@green', 3: '@teal', 4: '@purple'}  # the tooltip's gray, green, aqua and pink stars


def star(svg, cx, cy, r, fill, stroke=None):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    svg.poly(pts + [pts[0]], fill=fill, stroke=stroke, sw=1, join='miter')


def fish_table(table):
    """[(fish name, weight, stars)] of a climate table."""
    loot = data()['loot']
    out = []
    for e in loot[table]['entries']:
        items = [x for x in loot[e['loot_table']]['entries'] if x.get('item')]
        if len(items) != 1:
            raise ValueError('%s: expected one fish' % e['loot_table'])
        name = items[0]['item']
        stars = data()['items'][name]['components']['lore'][0].count('⭐')
        out.append((name, e['weight'], stars))
    return out


@diagram('Fishing odds')
def fishing_odds():
    loot = data()['loot']
    entries = loot[FISHING]['entries']
    junk = next(e for e in entries if e.get('loot_table', '').endswith('/junk') and not e['conditions'])
    treasure = next(e for e in entries if e.get('loot_table', '').endswith('/treasure'))
    if 'in_open_water' not in str(treasure['conditions']):
        raise ValueError('treasure is no longer limited to open water')
    climates = [e for e in entries if re.search(r'/(fresh|salt)water_', e.get('loot_table', ''))]
    fish_w = {e['weight'] for e in climates}
    if len(fish_w) != 1:
        raise ValueError('climate tables have different weights: %s' % fish_w)
    fish_w = fish_w.pop()
    layouts = {tuple(sorted(w for _, w, _ in fish_table(e['loot_table']))) for e in climates}
    if len(layouts) != 1:
        raise ValueError('climate tables differ in their weights: %s' % layouts)
    example = 'minecraft:gameplay/fishing/freshwater_temperate'
    fish = fish_table(example)
    table_w = sum(w for _, w, _ in fish)

    W, left, right = 760, 112, 744
    unit = (right - left) / (junk['weight'] + treasure['weight'] + fish_w)
    svg = Svg(W, 0, 'The chance of junk, treasure or fish on one cast, and of each fish in a climate table')
    open_total = junk['weight'] + treasure['weight'] + fish_w
    other_total = junk['weight'] + fish_w
    pct = lambda v: ('%.2f' % (100 * v)).rstrip('0').rstrip('.') + '%'
    cats = [('Junk', junk['weight'], '@grey_soft', '@grey'), ('Treasure', treasure['weight'], '@amber_soft', '@amber'),
            ('Fish', fish_w, '@blue_soft', '@blue')]
    h = 26
    y_open, y_other = 30, 70
    x = left
    for name, w, fill, edge in cats:
        wd = w * unit
        svg.text(x + wd / 2, y_open - 12, name, size=SMALL, anchor='middle', fill=edge, bold=True)
        svg.rect(x, y_open, wd, h, fill=fill, stroke=edge, rx=3)
        svg.text(x + wd / 2, y_open + h / 2, pct(w / open_total), size=SMALL, anchor='middle')
        if name == 'Treasure':
            svg.rect(x, y_other, wd, h, fill='none', stroke='@rule', rx=3, dash='3 3')
        else:
            svg.rect(x, y_other, wd, h, fill=fill, stroke=edge, rx=3)
            svg.text(x + wd / 2, y_other + h / 2, pct(w / other_total), size=SMALL, anchor='middle')
        if name == 'Fish':
            fx0, fx1 = x, x + wd
        x += wd
    svg.text(left - 10, y_open + h / 2, 'Open water', anchor='end')
    svg.text(left - 10, y_other + h / 2, 'Other water', anchor='end')

    # the fish segment opened up into one climate table
    y_fish = y_other + h + 48
    svg.poly([(fx0, y_other + h), (fx1, y_other + h), (right, y_fish), (left, y_fish)], fill='@blue_soft', opacity=0.45)
    svg.text(left - 10, y_fish + h / 2, 'Fish', anchor='end')
    svg.text((left + right) / 2, y_other + h + 24, 'Every climate table weighs its fish %s of %d (%s shown)'
             % (', '.join(str(w) for _, w, _ in fish), table_w, re.sub(r'.*/(\w+)_(\w+)$', r'\2 \1', example)),
             size=SMALL, anchor='middle', fill='@muted')
    unit_f = (right - left) / table_w
    spans, x = [], left
    for name, w, stars in fish:
        spans.append((x, w * unit_f))
        x += w * unit_f
    # a column under each fish, at its segment where there is room, pushed apart where there isn't
    cols = [a + wd / 2 for a, wd in spans]
    gap = 76
    for i in range(len(cols) - 1, -1, -1):
        limit = right - 24 if i == len(cols) - 1 else cols[i + 1] - gap
        cols[i] = min(cols[i], limit)
    cy = y_fish + h + 46
    for (name, w, stars), (a, wd), cx in zip(fish, spans, cols):
        svg.rect(a, y_fish, wd, h, fill='@blue_soft', stroke='@blue', rx=3)
        if wd > 14:
            svg.text(a + wd / 2, y_fish + h / 2, str(w), size=SMALL, anchor='middle')
        svg.line(a + wd / 2, y_fish + h + 2, a + wd / 2, y_fish + h + 8, stroke='@rule')
        svg.line(a + wd / 2, y_fish + h + 8, cx, cy - 20, stroke='@rule')
        svg.icon(name, cx, cy, 28)
        svg.text(cx, cy + 26, name, anchor='middle', bold=True)
        for k in range(4):
            star(svg, cx + (k - 1.5) * 14, cy + 44, 6, RARITY[stars] if k < stars else 'none', None if k < stars else '@rule')
        svg.text(cx, cy + 66, pct(w / table_w * fish_w / open_total), anchor='middle', bold=True)
        svg.text(cx, cy + 86, pct(w / table_w * fish_w / other_total), anchor='middle', fill='@muted')
    svg.text(left - 10, cy + 66, 'Per cast', anchor='end')
    svg.text(left - 10, cy + 86, 'In other water', anchor='end', fill='@muted')
    svg.h = cy + 98
    return svg


# ---------------------------------------------------------------------------------------------
# Version history: the releases on Modrinth by date

TYPES = {'alpha': '@amber', 'beta': '@blue', 'release': '@green'}


def modrinth_versions():
    import json
    import os
    from diagrams import SRC
    raw = json.load(open(os.path.join(SRC, 'modrinth_versions.json'), encoding='utf-8'))
    out = {}
    for v in raw:  # 1.12.2-beta was uploaded twice, as the datapack and the resource pack
        num = v['version_number'].lstrip('v')
        when = datetime.datetime.fromisoformat(v['date_published'].replace('Z', '+00:00'))
        if num not in out or when < out[num]['when']:
            out[num] = {'num': num, 'when': when, 'type': v['version_type'], 'mc': v['game_versions'][-1]}
    return sorted(out.values(), key=lambda v: v['when'])


@diagram('Releases')
def releases():
    import os
    from diagrams import SRC
    versions = modrinth_versions()
    # a version deleted from Modrinth, known only from a later changelog: "<n> was deleted"
    deleted = []
    for f in sorted(os.listdir(os.path.join(SRC, 'changelogs'))):
        text = open(os.path.join(SRC, 'changelogs', f), encoding='utf-8').read()
        deleted += [m for m in re.findall(r'^(\d+(?:\.\d+)+) was deleted', text, re.M)]
    first, last = versions[0]['when'], versions[-1]['when']
    start = first.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (last.replace(day=28) + datetime.timedelta(days=5)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    W, left, right = 760, 92, 744
    x = Scale(start.timestamp(), end.timestamp(), left, right)
    X = lambda d: x(d.timestamp())
    svg = Svg(W, 0, 'Matcha Flavoured releases on Modrinth by date, by type, with the Minecraft version each is for')

    def key(num):
        return [int(p) for p in re.findall(r'\d+', num)]

    # labels: each in the lowest lane where it doesn't touch a label to its left
    lane_h, base = 17, 0
    items = []
    for v in versions:
        items.append((X(v['when']), '%s' % re.sub(r'-(alpha|beta)$', '', v['num']), TYPES[v['type']], v))
    for num in deleted:
        before = max((v for v in versions if key(v['num']) < key(num)), key=lambda v: key(v['num']))
        after = min((v for v in versions if key(v['num']) > key(num)), key=lambda v: key(v['num']))
        items.append(((X(before['when']) + X(after['when'])) / 2, '%s deleted' % num, '@muted', (before, after)))
    items.sort(key=lambda it: it[0])
    # flags: a leader up from the dot and the label to its right. Placed right to left, each takes the
    # lowest lane where its label touches no other label and no leader rising past it.
    placed = []
    for px, label, colour, v in sorted(items, key=lambda it: -it[0]):
        span = (px - 1, px + 5 + text_width(label, SMALL, bold=True) + 4)
        lane = 0
        while any((q[4] == lane and q[5][0] < span[1] and span[0] < q[5][1]) or
                  (q[4] > lane and span[0] <= q[0] <= span[1]) for q in placed):
            lane += 1
        placed.append((px, label, colour, v, lane, span))
    lanes = max(q[4] for q in placed) + 1
    axis = 20 + lanes * lane_h + 12
    for px, label, colour, v, lane, span in placed:
        ly = axis - 22 - lane * lane_h
        if isinstance(v, tuple):  # the deleted version: somewhere between its neighbours
            a, b = X(v[0]['when']), X(v[1]['when'])
            svg.line(a, axis - 8, b, axis - 8, stroke='@rule', dash='3 3')
            svg.line(px, axis - 8, px, ly - 6, stroke='@rule', dash='2 2')
            svg.text(px + 5, ly, label, size=SMALL, fill='@muted', italic=True)
            continue
        svg.line(px, axis, px, ly - 6, stroke=colour)
        svg.text(px + 5, ly, label, size=SMALL, fill=colour, bold=True)
    svg.line(left, axis, right, axis, stroke='@rule', sw=1.5)
    for px, label, colour, v, lane, span in placed:
        if not isinstance(v, tuple):
            svg.circle(px, axis, 5, fill=colour, stroke='@paper', sw=1.5)
    svg.text(left - 10, axis, 'Releases', anchor='end')

    # the Minecraft version each release is for
    by = axis + 16
    runs = []
    for v in versions:
        if runs and runs[-1][0] == v['mc']:
            runs[-1][2] = v['when']
        else:
            runs.append([v['mc'], v['when'], v['when']])
    for i, (mc, a, b) in enumerate(runs):
        x0 = X(a)
        x1 = X(runs[i + 1][1]) if i + 1 < len(runs) else right
        svg.rect(x0, by, x1 - x0 - 2, 20, fill='@grey_soft', stroke='@panel_edge', rx=3)
        svg.text((x0 + x1) / 2, by + 10, mc, size=SMALL, anchor='middle')
    svg.text(left - 10, by + 10, 'Minecraft', anchor='end')

    bottom = by + 20
    months = []
    d = start
    while d < end:
        months.append(d)
        d = (d.replace(day=28) + datetime.timedelta(days=5)).replace(day=1)
    def grid():
        for i, m in enumerate(months):
            svg.line(X(m), 10, X(m), bottom + 6, stroke='@grid')
            nxt = months[i + 1] if i + 1 < len(months) else end
            svg.text((X(m) + X(nxt)) / 2, bottom + 16, m.strftime('%B %Y'), size=SMALL, fill='@muted', anchor='middle')
        svg.line(X(end), 10, X(end), bottom + 6, stroke='@grid')
    svg.behind(grid)
    ky = bottom + 42
    lx = left
    for t, c in TYPES.items():
        svg.circle(lx + 5, ky, 5, fill=c, stroke='@paper', sw=1.5)
        svg.text(lx + 16, ky, t.capitalize(), size=SMALL, fill='@muted')
        lx += 16 + text_width(t.capitalize(), SMALL) + 22
    svg.h = ky + 12
    return svg


# ---------------------------------------------------------------------------------------------
# Food: two foods' healing overlapping, from the hidden Regeneration III on each

REGEN_BASE = 50  # vanilla RegenerationMobEffect: heals 1 point every (50 >> amplifier) ticks (game code, not data)


def healing(name):
    """(duration, amplifier) of a food's hidden healing: the Regeneration without an icon."""
    comp = data()['items'][name]['components']
    for ce in (comp.get('consumable') or {}).get('on_consume_effects') or []:
        for e in ce.get('effects', []) if ce.get('type') == 'minecraft:apply_effects' else []:
            if e['id'] == 'minecraft:regeneration' and e.get('show_icon') is False:
                return e['duration'], e.get('amplifier', 0)
    raise ValueError('%s has no hidden healing' % name)


def heal_ticks(events):
    """Ticks at which 1 health is restored, for foods eaten at the given ticks: [(tick, duration, amplifier)].
    Same-level effects follow the vanilla rule: a new one replaces the old only if it lasts longer."""
    out, cur = [], None  # cur: (end tick, amplifier)
    events = sorted(events)
    last = max(t + d for t, d, _ in events)
    for tick in range(last + 1):
        for t, d, amp in events:
            if t == tick and (cur is None or cur[0] - tick < d):
                cur = (tick + d, amp)
        if cur and cur[0] > tick:
            left = cur[0] - tick
            if left % (REGEN_BASE >> cur[1]) == 0:
                out.append(tick)
    return out


@diagram('Healing overlap')
def healing_overlap():
    meal, snack = 'Pumpkin Empanada', 'Baked Pumpkin'
    d, amp = healing(meal)
    ds, amps = healing(snack)
    if amps != amp or ds >= d // 2:
        raise ValueError('the example needs a same-level snack shorter than half the meal')
    second = d // 2
    one = heal_ticks([(0, d, amp)])
    two = heal_ticks([(0, d, amp), (second, d, amp)])
    with_snack = heal_ticks([(0, d, amp), (second, ds, amps)])
    if with_snack != one:
        raise ValueError('the snack changed the healing')
    full = 2 * len(one)

    W, left, right, top, bottom = 760, 60, 560, 48, 218
    end = (max(two) // 20 + 1) * 20
    x = Scale(0, end, left, right)
    y = Scale(0, full, bottom, top)
    svg = Svg(W, 0, 'Health restored over time by one %s, and by a second one eaten halfway through' % meal.lower())

    def steps(ticks, colour, sw, dash=None):
        pts, hp = [(x(0), y(0))], 0
        for t in ticks:
            pts += [(x(t), y(hp))]
            hp += 1
            pts += [(x(t), y(hp))]
        pts.append((x(end), y(hp)))
        svg.poly(pts, stroke=colour, sw=sw, dash=dash, join='miter')
        return hp
    svg.line(left, y(full), right, y(full), stroke='@rule', sw=1.5, dash='5 4')
    a = steps(one, '@grey', 2.5)
    b = steps(two, '@blue', 3)
    # the healing lost to the overlap
    lx = x(end) + 10
    svg.line(x(end) - 4, y(full), x(end) - 4, y(b), stroke='@red', sw=2)
    svg.text(x(end) - 12, y((full + b) / 2), '%d lost' % (full - b), size=SMALL, fill='@red', bold=True, anchor='end')
    svg.text(lx, y(full) - 10, 'If both healed in full', size=SMALL, fill='@muted')
    svg.hp(lx, y(full) + 6, full, size=SMALL, fill='@muted')
    svg.text(lx, y(b) + 12, 'Second one eaten halfway', size=SMALL, fill='@blue', bold=True)
    svg.hp(lx, y(b) + 28, b, size=SMALL)
    svg.text(lx, y(a) + 12, 'One %s' % meal.lower(), size=SMALL, fill='@grey', bold=True)
    svg.hp(lx, y(a) + 28, a, size=SMALL)
    # when each is eaten
    for t in (0, second):
        svg.icon(meal, x(t), top - 26, 24)
        svg.line(x(t), top - 12, x(t), bottom, stroke='@muted', dash='2 3')
    y_grid(svg, y, range(0, full + 1, 4), left, right)
    x_grid(svg, x, range(0, end + 1, 20), top, bottom, fmt=lambda t: '%d' % (t // 20), lines=False)
    svg.text(left - 20, top - 26, 'Health', size=SMALL, fill='@muted', anchor='end')
    svg.text((left + right) / 2, bottom + 32, 'Seconds after the first bite', size=SMALL, fill='@muted', anchor='middle')
    svg.text(left, bottom + 54, 'A %s eaten halfway (%s of healing, less than the %s left) changes nothing.'
             % (snack.lower(), '%.1f s' % (ds / 20), '%.1f s' % ((d - second) / 20)), size=SMALL, fill='@muted')
    svg.h = bottom + 66
    return svg
