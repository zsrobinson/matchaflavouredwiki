"""The world: where ores generate, the moon's cycle, water in Hell and where hostile mobs may spawn."""
import json
import os
import re

from diagrams import (PACK_DATA, SMALL, TEXT, VANILLA_DATA, Scale, Svg, data, diagram, legend, mcfunction, need,
                      pack_file, pack_json, text_width)


# ---------------------------------------------------------------------------------------------
# Ores: every overworld ore feature's placements, as ore attempts per chunk per Y level

def _load(base, rel):
    p = os.path.join(base, rel)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def _layered(rel, pack=True):
    """data/<rel> from the pack over vanilla (pack=True), or vanilla alone."""
    return (pack and _load(PACK_DATA, rel)) or _load(VANILLA_DATA, rel)


def _id(ref):
    ns, _, path = ref.partition(':')
    return (ns, path) if path else ('minecraft', ns)


def _anchor(a, bottom, top):
    if 'absolute' in a:
        return a['absolute']
    if 'above_bottom' in a:
        return bottom + a['above_bottom']
    return top - a['below_top']


def height_weights(h, bottom, top):
    """{y: probability} of a height provider (uniform or trapezoid, as HeightProvider samples them)."""
    lo, hi = _anchor(h['min_inclusive'], bottom, top), _anchor(h['max_inclusive'], bottom, top)
    kind = h.get('type', 'minecraft:uniform').split(':')[1]
    if kind == 'uniform' or (kind == 'trapezoid' and h.get('plateau', 0) >= hi - lo):
        return {y: 1 / (hi - lo + 1) for y in range(lo, hi + 1)}
    if kind != 'trapezoid':
        raise ValueError('height provider %s' % kind)
    # TrapezoidHeight: min + U[0, k - l] + U[0, l], with k = max - min and l = (k - plateau) / 2
    k = hi - lo
    small = (k - h.get('plateau', 0)) // 2
    big = k - small
    out = {}
    for a in range(big + 1):
        for b in range(small + 1):
            out[lo + a + b] = out.get(lo + a + b, 0) + 1 / ((big + 1) * (small + 1))
    return out


def _count(c):
    if isinstance(c, dict):
        return (c['min_inclusive'] + c['max_inclusive']) / 2  # uniform int provider: its mean
    return c


def placed_profile(placed, bottom, top):
    """Ore attempts per chunk at each Y level for one placed feature (clipped to the world)."""
    count, heights = 1.0, None
    for p in placed['placement']:
        kind = p['type'].split(':')[1]
        if kind == 'count':
            count *= _count(p['count'])
        elif kind == 'rarity_filter':
            count /= p['chance']
        elif kind == 'height_range':
            heights = height_weights(p['height'], bottom, top)
    return {y: w * count for y, w in heights.items() if bottom <= y <= top}


def _biome_features(pack=True):
    """{placed feature id: [overworld biomes that place it]}."""
    tag = _layered('minecraft/tags/worldgen/biome/is_overworld.json', pack)
    out = {}
    for ref in tag['values']:
        ns, path = _id(ref)
        biome = _layered('%s/worldgen/biome/%s.json' % (ns, path), pack)
        for step in biome['features']:
            for f in (step if isinstance(step, list) else [step]):
                out.setdefault(f if ':' in f else 'minecraft:' + f, []).append(path)
    return out, len(tag['values'])


# biomes grouped the way the pages name them, for labelling features that only some biomes place
BIOME_GROUPS = {'badlands': 'Badlands', 'eroded_badlands': 'Badlands', 'wooded_badlands': 'Badlands',
                'desert': 'Deserts', 'deep_dark': 'deep dark', 'dripstone_caves': 'Dripstone caves',
                'stony_peaks': 'Mountains', 'jagged_peaks': 'Mountains', 'frozen_peaks': 'Mountains',
                'snowy_slopes': 'Mountains', 'grove': 'Mountains', 'meadow': 'Mountains', 'cherry_grove': 'Mountains',
                'windswept_hills': 'Mountains', 'windswept_gravelly_hills': 'Mountains', 'windswept_forest': 'Mountains'}


def biome_label(biomes):
    groups = []
    for b in biomes:
        g = BIOME_GROUPS.get(b, b.replace('_', ' ').capitalize())
        if g not in groups:
            groups.append(g)
    groups.sort(key=lambda g: g[0].islower())  # 'Mountains and deep dark'
    return ' and '.join(groups)


# the page's order (Ores.wiki's table); ores not listed follow
ORE_ORDER = ['coal_ore', 'copper_ore', 'iron_ore', 'gold_ore', 'emerald_ore', 'lapis_ore', 'redstone_ore', 'diamond_ore']


def ore_lanes(pack=True):
    """{stone ore block: {'deep': deepslate ore block, 'features': [(id, profile, biomes, from_pack)]}}."""
    dim = _layered('minecraft/dimension_type/overworld.json', pack)
    bottom, top = dim['min_y'], dim['min_y'] + dim['height'] - 1
    feats, n_biomes = _biome_features(pack)
    lanes = {}
    for fid, biomes in feats.items():
        ns, path = _id(fid)
        rel = '%s/worldgen/placed_feature/%s.json' % (ns, path)
        placed = _layered(rel, pack)
        if not placed or not isinstance(placed['feature'], str):
            continue
        cns, cpath = _id(placed['feature'])
        crel = '%s/worldgen/configured_feature/%s.json' % (cns, cpath)
        conf = _layered(crel, pack)
        if not conf or conf['type'] not in ('minecraft:ore', 'minecraft:scattered_ore'):
            continue
        states = [t['state']['Name'].split(':')[1] for t in conf['config']['targets']]
        stone = next((s for s in states if s.endswith('_ore') and not s.startswith('deepslate_')), None)
        if not stone:
            continue  # dirt, gravel, tuff, infested stone...
        deep = next((s for s in states if s == 'deepslate_' + stone), None)
        from_pack = pack and (os.path.exists(os.path.join(PACK_DATA, rel)) or os.path.exists(os.path.join(PACK_DATA, crel)))
        lane = lanes.setdefault(stone, {'deep': deep, 'features': []})
        lane['features'].append((path, placed_profile(placed, bottom, top), biomes, from_pack))
    return lanes, n_biomes, bottom, top


def _sum(profiles):
    out = {}
    for p in profiles:
        for y, v in p.items():
            out[y] = out.get(y, 0) + v
    return out


def ore_name(block_id):
    for item in data()['items'].values():
        if item.get('base_id') == 'minecraft:' + block_id:
            return item['name']
    return block_id.replace('_', ' ').title()


@diagram('Ore heights')
def ore_heights():
    lanes, n_biomes, bottom, top = ore_lanes()
    vanilla, _, _, _ = ore_lanes(pack=False)
    noise = pack_json('minecraft/worldgen/noise_settings/overworld.json')
    sea = noise['sea_level']

    g = _gradient(noise['surface_rule'], 'minecraft:deepslate')  # the deepslate layer's vertical gradient
    slate_full = _anchor(g['true_at_and_below'], bottom, top)
    slate_none = _anchor(g['false_at_and_above'], bottom, top)

    order = [o for o in ORE_ORDER if o in lanes] + sorted(o for o in lanes if o not in ORE_ORDER)
    W, left, right = 760, 238, 744
    x = Scale(bottom, top + 1, left, right)
    row_h, lane_h, head = 50, 34, 30
    svg = Svg(W, 0, 'Where each overworld ore generates by Y level, with the changes the pack makes')
    widespread = n_biomes / 2  # placed in at least half the overworld biomes: drawn solid

    for i, stone in enumerate(order):
        lane = lanes[stone]
        base = head + (i + 1) * row_h - 8
        solid = [f for f in lane['features'] if len(f[2]) >= widespread]
        some = [f for f in lane['features'] if len(f[2]) < widespread]
        total = _sum(f[1] for f in solid)
        van = _sum(f[1] for f in vanilla.get(stone, {'features': []})['features'] if len(f[2]) >= widespread)
        ghost = van if van and any(abs(van.get(y, 0) - total.get(y, 0)) > 1e-9 for y in set(van) | set(total)) else None
        # features only some biomes place, grouped by where; one that only replaces a widespread
        # feature there (same heights and count, like dripstone caves' large copper) adds nothing
        groups = {}
        for fid, prof, biomes, fp in some:
            if any(prof == s[1] for s in solid):
                continue
            label = biome_label(biomes)
            groups.setdefault(label, [[], False])
            groups[label][0].append(prof)
            groups[label][1] |= fp
        extra = [(label, _sum(profs), fp) for label, (profs, fp) in groups.items()]
        peak = max([max(total.values(), default=0)] + [max(p.values()) for _, p, _ in extra])
        yv = Scale(0, peak, base, base - lane_h)

        def area(prof, **kw):
            pts = [(x(bottom), base)]
            for y in range(bottom, top + 1):
                v = prof.get(y, 0)
                pts += [(x(y), yv(v)), (x(y + 1), yv(v))]
            pts.append((x(top + 1), base))
            # drop points on flat runs so the path stays small
            keep = [pts[0]] + [p for a, p, b in zip(pts, pts[1:], pts[2:])
                               if not (a[1] == p[1] == b[1] or a[0] == p[0] == b[0])] + [pts[-1]]
            svg.poly(keep, **kw)

        # widespread: the pack's own features stacked on vanilla's, pack in teal
        if any(f[3] for f in solid):
            area(total, fill='@teal_soft', stroke='@teal', sw=1.2)
        van_part = _sum(f[1] for f in solid if not f[3])
        if van_part:
            area(van_part, fill='@grey_soft', stroke='@grey', sw=1.2)
        for label, prof, fp in extra:
            colour = '@teal' if fp else '@grey'
            area(prof, stroke=colour, sw=1.6, dash='5 3')
            # the label sits inside the dashed shape, under the middle of its highest run
            top_v = max(prof.values())
            run = [y for y in sorted(prof) if prof[y] >= top_v * 0.999]
            lx = x((run[0] + run[-1] + 1) / 2)
            svg.text(lx, (base + yv(top_v)) / 2, label, size=SMALL, fill=colour, anchor='middle')
        if ghost:
            area(ghost, stroke='@ink', sw=1.2, dash='1.5 2.5')
        svg.line(left, base, right, base, stroke='@rule')

        # the row label: icon, name, and the deepslate variant's name when it isn't just "Deepslate X"
        name = ore_name(stone)
        deep = ore_name(lane['deep']) if lane['deep'] else None
        svg.icon(name, 20, base - lane_h / 2, 26)
        if deep and deep.replace('Deepslate ', '') != name:
            svg.text(40, base - lane_h / 2 - 8, name, bold=True)
            svg.text(40, base - lane_h / 2 + 9, '%s in deepslate' % deep, size=SMALL, fill='@muted')
        else:
            svg.text(40, base - lane_h / 2, name, bold=True)

    bottom_y = head + len(order) * row_h - 8

    def backdrop():
        svg.rect(x(bottom), head, x(slate_full) - x(bottom), bottom_y - head, fill='@grey_soft', opacity=0.6)
        svg.rect(x(slate_full), head, x(slate_none) - x(slate_full), bottom_y - head, fill='@grey_soft', opacity=0.3)
        for t in range(bottom, top + 2, 64):
            svg.line(x(t), head, x(t), bottom_y + 4, stroke='@grid')
        svg.line(x(sea), head - 4, x(sea), bottom_y, stroke='@blue', dash='4 3')
    svg.behind(backdrop)
    svg.text((x(bottom) + x(slate_full)) / 2, head - 12, 'Deepslate', size=SMALL, fill='@muted', anchor='middle')
    svg.text(x(sea) + 5, head - 12, 'Sea level (%d)' % sea, size=SMALL, fill='@blue')
    for t in range(bottom, top + 2, 64):
        svg.text(x(t), bottom_y + 16, '%d' % t, size=SMALL, fill='@muted', anchor='middle')
    svg.text((left + right) / 2, bottom_y + 34, 'Y level (the world ends at %d)' % top, size=SMALL, fill='@muted',
             anchor='middle')
    ly = bottom_y + 60
    legend(svg, 12, ly, [('@grey_soft', 'As in vanilla', 'box'), ('@teal_soft', 'Added or changed by the pack', 'box'),
                         ('@grey', 'Only in the biomes named', 'dash'), ('@ink', 'Vanilla, where the pack changed it', 'dots')])
    svg.text(12, ly + 22, 'Each row is scaled to its own peak; the height is ore veins attempted per chunk at that level.',
             size=SMALL, fill='@muted')
    svg.h = ly + 36
    return svg


# ---------------------------------------------------------------------------------------------
# The moon: its phases and the surface slime chance over the pack's 8-day cycle

RESOURCE_PACKS = [os.path.join(os.path.dirname(PACK_DATA), '..', 'MF_resourcepack', 'assets'),
                  os.path.join(os.path.dirname(VANILLA_DATA), '..', 'vanilla-assets', 'assets')]


def texture_uri(rel, size, crop=0):
    """A texture from the resource pack (else vanilla's), `crop` pixels trimmed off each edge and
    scaled up without smoothing, as a data URI."""
    import base64
    import io
    from PIL import Image
    for base in RESOURCE_PACKS:
        p = os.path.normpath(os.path.join(base, 'minecraft', 'textures', rel))
        if os.path.exists(p):
            im = Image.open(p).convert('RGBA')
            im = im.crop((crop, crop, im.width - crop, im.height - crop)).resize((size, size), Image.NEAREST)
            buf = io.BytesIO()
            im.save(buf, 'PNG', optimize=True)
            return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    raise FileNotFoundError(rel)


def phase_name(v):
    return v.split(':')[-1].replace('_', ' ').capitalize()


@diagram('Moon phases')
def moon_phases():
    tl = pack_json('minecraft/timeline/moon.json')
    day_tl = pack_json('minecraft/timeline/day.json')
    period, day = tl['period_ticks'], day_tl['period_ticks']
    days = period // day
    tracks = tl['tracks']
    phases = sorted((k['ticks'], k['value']) for k in tracks['minecraft:visual/moon_phase']['keyframes'])
    slime = sorted((k['ticks'], k['value']) for k in tracks['minecraft:gameplay/surface_slime_spawn_chance']['keyframes'])
    marks = {k.split(':')[1]: (v if isinstance(v, int) else v['ticks']) for k, v in day_tl['time_markers'].items()}
    night, dawn = marks['night'], marks['day'] + day

    W, left, right = 760, 172, 718
    x = Scale(0, period, left, right)
    svg = Svg(W, 0, "The moon's phases and the chance of slimes on the surface over the pack's 8-day lunar cycle")
    top = 22
    moon_y, sprite = top + 28, 48  # the moon textures' middle 24 pixels, drawn 2x
    name_y = moon_y + sprite / 2 + 14
    bar_top, bar_h = name_y + 44, 64
    bar_base = bar_top + bar_h
    bottom = bar_base

    # phases: each keyframe holds until the next, and the last one runs on into the next cycle's
    # start; a phase is drawn at the middle of its span, and one that spans the cycle's end at both ends
    spans = [[t, phases[i + 1][0] if i + 1 < len(phases) else period + phases[0][0], v]
             for i, (t, v) in enumerate(phases)]
    if spans[0][0] == 0 and spans[-1][2] == spans[0][2]:  # the same phase either side of tick 0: join them
        spans[-1][1] = period + spans[0][1]
        spans.pop(0)
    centres = []
    for a, b, v in spans:
        c = (a + b) / 2
        centres += [(c, v)] + ([(c - period, v)] if b > period else [])
    for c, v in sorted(centres):
        cx = x(c)
        svg.sprite(texture_uri('environment/celestial/moon/%s.png' % v.split(':')[-1], sprite, crop=4), cx, moon_y, sprite)
        for j, w in enumerate(phase_name(v).split(' ')):
            svg.text(cx, name_y + j * 15, w, size=SMALL, fill='@ink', anchor='middle')
    boundaries = sorted(a for a, b, v in spans if 0 < a < period)

    # slime chance: a bar per keyframe span, as tall as the chance
    peak = max(v for _, v in slime)
    yv = Scale(0, peak, bar_base, bar_top)
    for i, (t, v) in enumerate(slime):
        end = slime[i + 1][0] if i + 1 < len(slime) else period
        x0, x1 = x(t) + 6, x(end) - 6
        if v > 0:
            svg.rect(x0, yv(v), x1 - x0, bar_base - yv(v), fill='@teal', rx=2)
        svg.text((x0 + x1) / 2, yv(v) - 9, '%s%%' % ('%g' % (v * 100)), size=SMALL, fill='@ink', anchor='middle')
    svg.line(left, bar_base, right, bar_base, stroke='@rule')

    svg.text(left - sprite / 2 - 14, moon_y, 'Moon', anchor='end')
    svg.text(left - sprite / 2 - 14, bar_base - bar_h / 2 - 8, 'Slime chance', anchor='end')
    svg.text(left - sprite / 2 - 14, bar_base - bar_h / 2 + 9, 'on the surface', size=SMALL, fill='@muted', anchor='end')

    def backdrop():
        for d in range(days):  # nights, from the day timeline's markers
            a, b = d * day + night, min(d * day + dawn, period)
            svg.rect(x(a), top - 4, x(b) - x(a), bottom - top + 4, fill='@blue_soft')
            if d == 0 and dawn > day:  # the end of the last night, carried over the cycle's start
                svg.rect(x(0), top - 4, x(dawn - day) - x(0), bottom - top + 4, fill='@blue_soft')
        for d in range(days + 1):
            svg.line(x(d * day), top - 4, x(d * day), bottom + 4, stroke='@grid')
        for t in boundaries:  # where the phase changes
            svg.line(x(t), top - 4, x(t), name_y + 22, stroke='@rule', dash='2 3')
    svg.behind(backdrop)
    for d in range(days + 1):
        svg.text(x(d * day), bottom + 16, '%d' % d, size=SMALL, fill='@muted', anchor='middle')
    svg.text((left + right) / 2, bottom + 34, 'Days into the cycle (1 day = %s ticks)' % format(day, ','), size=SMALL,
             fill='@muted', anchor='middle')
    ly = bottom + 60
    legend(svg, left, ly, [('@blue_soft', 'Night', 'box'), ('@rule', 'Phase changes', 'dash')])
    svg.h = ly + 14
    return svg


# ---------------------------------------------------------------------------------------------
# Hell: where water is cleared, as a cross-section to scale

def _gradient(rule, name):
    """The surface rule's vertical gradient with this random name (bedrock floor and roof, deepslate)."""
    if isinstance(rule, dict):
        if rule.get('random_name') == name:
            return rule
        rule = list(rule.values())
    for v in rule if isinstance(rule, list) else []:
        g = _gradient(v, name)
        if g:
            return g


@diagram('Hell water')
def hell_water():
    pred = pack_json('matcha/predicate/invalid_nether_water.json')
    pos = pred['terms'][0]['predicate']['minecraft:location']['position']['y']
    lo, hi = pos['min'], pos['max']
    src = mcfunction('matcha/function/environmental/nether_water.mcfunction')
    # three fills (2, 10 and 20 blocks) run one after another; the largest covers the others
    fill = r'fill ~-(\d+) ~-\1 ~-\1 ~\1 ~\1 ~\1 air replace water'
    need(fill, src, 'the water fill', cast=int)
    reach = max(int(r) for r in re.findall(fill, src))
    noise = pack_json('minecraft/worldgen/noise_settings/nether.json')
    bottom = noise['noise']['min_y']
    top = bottom + noise['noise']['height'] - 1
    floor = _gradient(noise['surface_rule'], 'minecraft:bedrock_floor')
    roof = _gradient(noise['surface_rule'], 'minecraft:bedrock_roof')

    W = 360
    y_top = hi + 1 + 36  # a little of the space above the roof
    y = Scale(bottom, y_top, 330, 20)
    k = (y(0) - y(1))  # pixels per block, the same across
    left, right = 56, 56 + 104 * k
    svg = Svg(W, 0, 'A cross-section of Hell: where emptying a water bucket clears the water around the player')

    # the two zones
    svg.rect(left, y(hi + 1), right - left, y(lo) - y(hi + 1), fill='@red_soft')
    svg.rect(left, y(y_top), right - left, y(hi + 1) - y(y_top), fill='@blue_soft')
    # bedrock: solid at the floor and roof, thinning out over the gradient
    for g, solid in ((floor, bottom), (roof, top)):
        a = _anchor(g['true_at_and_below'], bottom, top)
        b = _anchor(g['false_at_and_above'], bottom, top)
        lo_b, hi_b = min(a, b), max(a, b)
        svg.rect(left, y(hi_b + 1), right - left, y(lo_b) - y(hi_b + 1), fill='@grey', opacity=0.35)
        svg.rect(left, y(solid + 1), right - left, y(solid) - y(solid + 1), fill='@grey')
    svg.rect(left, y(y_top), right - left, y(bottom) - y(y_top), fill='none', stroke='@panel_edge')

    # a player low down in Hell, and the cube the fill clears around them, to scale
    py = lo + 44
    px = (left + right) / 2
    svg.rect(px - reach * k, y(py + reach + 1), (2 * reach + 1) * k, (2 * reach + 1) * k, fill='none', stroke='@red',
             sw=1.5, dash='5 3')
    svg.icon('Water Bucket', px, y(py + 0.5), 22)
    svg.text(px, y(py - reach) + 14, '%d × %d × %d blocks cleared' % ((2 * reach + 1,) * 3), size=SMALL, fill='@red',
             anchor='middle')
    # on the roof, water stays
    svg.icon('Water Bucket', px, y(hi + 1) - 12, 22)

    # labels to the right
    tx = right + 12
    svg.text(tx, (y(hi + 1) + y(y_top)) / 2 - 8, 'Water stays', bold=True, fill='@blue')
    svg.text(tx, (y(hi + 1) + y(y_top)) / 2 + 9, 'Y=%d and up' % (hi + 1), size=SMALL, fill='@muted')
    mid = (y(lo) + y(hi + 1)) / 2
    svg.text(tx, mid - 8, 'Water cleared', bold=True, fill='@red')
    svg.text(tx, mid + 9, 'Y=%d to %d' % (lo, hi), size=SMALL, fill='@muted')
    svg.text(tx, y(top) + k * 3, 'Bedrock roof', size=SMALL, fill='@muted')
    svg.text(tx, y(bottom) - k * 3, 'Bedrock floor', size=SMALL, fill='@muted')
    for t in (0, 32, 64, 96, hi + 1):
        svg.text(left - 8, y(t), '%d' % t, size=SMALL, fill='@muted', anchor='end')
        svg.line(left - 4, y(t), left, y(t), stroke='@rule')
    svg.text(14, (y(bottom) + y(y_top)) / 2, 'Y', size=SMALL, fill='@muted', anchor='middle')
    svg.h = y(bottom) + 14
    return svg


# ---------------------------------------------------------------------------------------------
# Surface spawning: which mundane hostile mobs may appear where, before and after the dragon dies.
# The rules are read from the pack's spawn-check functions and predicates and evaluated for each
# place in a schematic cross-section, so the picture says what the files say.

SPAWN = 'matcha/function/mechanics/spawn_mechanic/'


def _entity_types(ref):
    """The entity types a type or #tag names."""
    if not ref.startswith('#'):
        return {ref if ':' in ref else 'minecraft:' + ref}
    ns, path = _id(ref[1:])
    out = set()
    for v in pack_json('%s/tags/entity_type/%s.json' % (ns, path))['values']:
        out |= _entity_types(v if isinstance(v, str) else v['id'])
    return out


def _test(cond, place, mob):
    """A predicate condition for a mob of type `mob` at `place` ({'sky', 'y', 'structures'})."""
    kind = cond['condition'].split(':')[-1]
    if kind == 'all_of':
        return all(_test(t, place, mob) for t in cond['terms'])
    if kind == 'any_of':
        return any(_test(t, place, mob) for t in cond['terms'])
    if kind == 'inverted':
        return not _test(cond['term'], place, mob)
    if kind == 'reference':
        return _predicate(cond['name'], place, mob)
    if kind == 'entity_properties':
        ok = True
        for key, v in cond['predicate'].items():
            key = key.split(':')[-1]
            if key == 'entity_type':
                ok &= mob in _entity_types(v)
            elif key == 'location':
                for lk, lv in v.items():
                    if lk == 'can_see_sky':
                        ok &= place['sky'] == lv
                    elif lk == 'position':
                        r = lv['y']
                        ok &= r.get('min', -1e9) <= place['y'] <= r.get('max', 1e9)
                    elif lk == 'structures':
                        ok &= bool(place['structures'] & set(lv))
                    elif lk == 'dimension':
                        ok &= lv == 'minecraft:overworld'
                    else:
                        raise ValueError('location test %s' % lk)
            else:
                raise ValueError('entity test %s' % key)
        return ok
    raise ValueError('condition %s' % kind)


def _predicate(ref, place, mob):
    ns, path = _id(ref)
    return _test(pack_json('%s/predicate/%s.json' % (ns, path)), place, mob)


def removed(function, place, mob):
    """Whether a spawn-check function tags a new mob SpawnForbidden: each line that does, with its
    `if`/`unless` tests (predicates, entity types, the Overworld), read from the file."""
    for line in mcfunction(SPAWN + function + '.mcfunction').splitlines():
        if not line.rstrip().endswith('tag @s add SpawnForbidden'):
            continue
        hit = True
        for mode, what, arg in re.findall(r'\b(if|unless) (predicate|entity|dimension) (\S+)', line):
            if what == 'predicate':
                ok = _predicate(arg, place, mob)
            elif what == 'dimension':
                ok = arg == 'minecraft:overworld'
            else:
                ok = mob in _entity_types(need(r'type=([^\],]+)', arg, 'entity type test', cast=str))
            hit &= ok if mode == 'if' else not ok
        if hit:
            return True
    return False


def surface_rules():
    """The places in the cross-section, the mob groups, and who may spawn where in each state."""
    ticking = mcfunction(SPAWN + 'ticking.mcfunction')
    after = need(r'if score gamerule gamerule_safe_surface matches 1 run .* run function matcha:mechanics/spawn_mechanic/(\w+)',
                 ticking, 'the check after the dragon', cast=str)
    before = need(r'unless score gamerule gamerule_safe_surface matches 1 run .* run function matcha:mechanics/spawn_mechanic/(\w+)',
                  ticking, 'the check before the dragon', cast=str)
    mobs = sorted(_entity_types('#matcha:mundane_hostiles'))
    line = int(need(r'"min": (\d+)', open(pack_file('matcha/predicate/surface_spawn.json')).read(), 'surface height'))
    places = {  # a Y above or below the surface predicate's line; the abbey is the in_dungeon structure
        'sky': {'sky': True, 'y': line + 20, 'structures': set()},
        'ravine': {'sky': True, 'y': line - 20, 'structures': set()},
        'cover': {'sky': False, 'y': line + 20, 'structures': set()},
        'abbey': {'sky': False, 'y': line + 20, 'structures': {'minecraft:abbey_overgrown'}},
        'cave': {'sky': False, 'y': line - 20, 'structures': set()},
    }
    states = {}
    for state, fn in (('before', before), ('after', after)):
        states[state] = {p: {m for m in mobs if not removed(fn, place, m)} for p, place in places.items()}
    # mobs that every rule treats alike form one group
    groups = {}
    for m in mobs:
        sig = tuple((s, p, m in states[s][p]) for s in states for p in places)
        groups.setdefault(sig, []).append(m)
    return line, states, list(groups.values())


def _group_name(members):
    undead = _entity_types('#minecraft:undead')
    if len(members) == 1:
        n = members[0].split(':')[1].replace('_', ' ')
        return n if n.endswith('ed') else n + 's'  # drowned, creepers
    return 'undead' if all(m in undead for m in members) else 'others'


def verdict(allowed, groups):
    """A short label for who may spawn in a place, and its colour role."""
    have = [g for g in groups if set(g) <= allowed]
    if len(have) == len(groups):
        return 'All', '@red_soft'
    if not have:
        return 'None', '@green_soft'
    missing = [g for g in groups if g not in have]
    mobs = {m for g in groups for m in g}
    if allowed == mobs & _entity_types('#minecraft:undead'):
        return 'Undead only', '@amber_soft'
    if len(missing) == 1:
        return 'All but %s' % _group_name(missing[0]), '@amber_soft'
    return ' and '.join(_group_name(g).capitalize() for g in have) + ' only', '@amber_soft'


@diagram('Surface spawning')
def surface_spawning():
    """A side view of the same patch of ground before and after the dragon: the places are drawn as
    they are (sky, stone, an overhang, an abbey, a cave), and a chip on each says who may spawn there."""
    line, states, groups = surface_rules()
    PW, PH, gap = 364, 246, 32
    svg = Svg(2 * PW + gap, 0, 'Where mundane hostile mobs can appear in the Overworld before and after the Ender Dragon is killed')
    top, sea, cell = 30, 160, 12
    strong = {'@red_soft': '@red', '@amber_soft': '@amber', '@green_soft': '@green'}
    for i, (state, title) in enumerate((('before', 'Before the dragon is killed'), ('after', 'After the dragon is killed'))):
        ox = i * (PW + gap)
        rules = states[state]

        def P(pts):
            return [(ox + px, top + py) for px, py in pts]
        svg.text(ox + PW / 2, 12, title, anchor='middle', bold=True)
        # stone, drawn as blocks
        svg.rect(ox, top + 60, PW, PH - 60, fill='@grey_soft')
        for gx in range(0, PW + 1, cell):
            svg.line(ox + gx, top + 60, ox + gx, top + PH, stroke='@grid', sw=0.6)
        for gy in range(60, PH + 1, cell):
            svg.line(ox, top + gy, ox + PW, top + gy, stroke='@grid', sw=0.6)
        # the open spaces: sky (and the ravine open to it), and air under cover, in the abbey and in the cave
        sky = [(0, 0), (PW, 0), (PW, 118), (338, 118), (338, sea), (306, sea), (306, 118), (288, 118), (288, 62),
               (172, 62), (172, 118), (150, 118), (150, 60), (0, 60)]
        svg.poly(P(sky) + P(sky[:1]), fill='@blue_soft')
        svg.poly(P([(306, sea), (338, sea), (338, 198), (306, 198)]) + P([(306, sea)]), fill='@blue_soft')
        svg.rect(ox + 30, top + 76, 120, 42, fill='@panel')                      # under the overhang
        svg.rect(ox + 30, top + 180, 220, 48, fill='@panel', rx=18)              # a cave
        svg.rect(ox + 172, top + 62, 116, 56, fill='@grey')                      # the abbey's walls and roof
        svg.rect(ox + 179, top + 70, 102, 48, fill='@panel')
        # grass on the ground open to the sky
        for x0, x1, y in ((0, 150, 60), (150, 172, 118), (288, 306, 118), (338, PW, 118)):
            svg.rect(ox + x0, top + y, x1 - x0, 4, fill='@green')
        svg.rect(ox, top, PW, PH, fill='none', stroke='@panel_edge')
        svg.line(ox, top + sea, ox + PW, top + sea, stroke='@blue', dash='4 3')
        svg.text(ox + PW - 6, top + sea - 8, 'Sea level, Y=%d' % line, size=SMALL, fill='@blue', anchor='end')

        def chip(key, x, y, name, room):
            label, fill = verdict(rules[key], groups)
            w = min(room, max(text_width(name, SMALL), text_width(label, TEXT)) + 16)
            svg.rect(ox + x - w / 2, top + y - 17, w, 34, fill=fill, stroke=strong[fill], rx=3)
            svg.text(ox + x, top + y - 7, name, size=SMALL, fill='@muted', anchor='middle', fit=w - 8)
            svg.text(ox + x, top + y + 8, label, anchor='middle', bold=True, fit=w - 8)
        chip('sky', PW / 2, 30, 'Under the open sky, at any height', PW - 40)
        chip('cover', 90, 97, 'Under cover', 112)
        chip('abbey', 230, 94, 'In an abbey', 96)
        chip('cave', 140, 204, 'Cave below Y=%d' % line, 200)
    y = top + PH + 24
    w = legend(svg, 0, y, [('@red_soft', 'Every mundane hostile mob', 'box'), ('@amber_soft', 'Only some', 'box'),
                           ('@green_soft', 'None', 'box')])
    svg.text(w + 6, y, 'Trial chambers count as abbeys.', size=SMALL, fill='@muted')
    svg.h = y + 14
    return svg
