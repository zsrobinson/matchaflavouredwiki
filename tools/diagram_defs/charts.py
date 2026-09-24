"""Charts of the pack's numbers: the food level, healing overlap and the release timeline."""
import datetime
import re

from diagrams import SMALL, Scale, Svg, data, diagram, mcfunction, need, text_width


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


def roman(n):
    out = ''
    for v, s in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out, n = out + s, n - v
    return out


# ---------------------------------------------------------------------------------------------
# Death: the floor that maximum health can't fall below, against milestones earned


# ---------------------------------------------------------------------------------------------
# Sleeping: how fast time runs against the share of players in bed


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


# ---------------------------------------------------------------------------------------------
# Fishing: what one cast can bring up, from the category to the single fish

FISHING = 'minecraft:gameplay/fishing'


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
    lane_h = 17
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
