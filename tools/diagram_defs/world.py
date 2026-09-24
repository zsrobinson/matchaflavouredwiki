"""The world: where ores generate, the moon's cycle, water in Hell and where hostile mobs may spawn."""
import json
import os

from diagrams import (PACK_DATA, SMALL, TEXT, VANILLA_DATA, Scale, Svg, data, diagram, legend, mcfunction, need,
                      pack_json, text_width)


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

    def gradient(o):  # the deepslate layer: the surface rule's vertical gradient
        if isinstance(o, dict):
            if o.get('random_name') == 'minecraft:deepslate':
                return o
            o = list(o.values())
        for v in o if isinstance(o, list) else []:
            g = gradient(v)
            if g:
                return g
    g = gradient(noise['surface_rule'])
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
    lx = 12 + legend(svg, 12, ly, [('@grey_soft', 'As in vanilla', 'box'),
                                   ('@teal_soft', 'Added or changed by the pack', 'box'),
                                   ('@grey', 'Only in the biomes named', 'dash')])
    svg.line(lx, ly, lx + 18, ly, stroke='@ink', sw=1.4, dash='1.5 2.5')
    svg.text(lx + 24, ly, 'Vanilla, where the pack changed it', size=SMALL, fill='@muted')
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
        svg.text(x(d * day), bottom + 16, '%d' % (d % days), size=SMALL, fill='@muted', anchor='middle')
    svg.text((left + right) / 2, bottom + 34, 'Days into the cycle (1 day = %s ticks)' % format(day, ','), size=SMALL,
             fill='@muted', anchor='middle')
    ly = bottom + 60
    legend(svg, left, ly, [('@blue_soft', 'Night', 'box'), ('@rule', 'Phase changes', 'dash')])
    svg.h = ly + 14
    return svg
