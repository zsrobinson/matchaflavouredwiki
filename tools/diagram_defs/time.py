"""Time of day: the day cycle, villager schedules and the moon, all on the day timeline's axis."""
from diagrams import SMALL, Scale, Svg, diagram, pack_json

DAY = 'minecraft/timeline/day.json'


def keyframes(track):
    return [(k['ticks'], k['value']) for k in track['keyframes']]


def spans(frames, period, want):
    """Tick ranges where a stepped track equals `want`, wrapping round the period."""
    frames = sorted(frames)
    out = []
    for i, (t, v) in enumerate(frames):
        end = frames[i + 1][0] if i + 1 < len(frames) else period + frames[0][0]
        if v == want:
            out.append((t, end))
    res = []
    for a, b in out:  # split a span that wraps past the end of the day
        if b > period:
            res += [(a, period), (0, b - period)]
        else:
            res.append((a, b))
    return res


def day_axis(svg, x, left, right, top, bottom, period):
    """Real-time axis under a day chart: minutes, gridlines, and the day's named markers above."""
    minutes = period / 1200
    for m in range(0, int(minutes) + 1, 5):
        px = x(m * 1200)
        svg.line(px, top, px, bottom, stroke='@grid')
        svg.text(px, bottom + 14, '%d' % m, size=SMALL, fill='@muted', anchor='middle')
    svg.text((left + right) / 2, bottom + 32, 'Real minutes into the day (1 minute = 1,200 ticks)', size=SMALL,
             fill='@muted', anchor='middle')


def row_label(svg, x, y, label):
    svg.text(x, y, label, anchor='end')


@diagram('Day and night')
def day_and_night():
    tl = pack_json(DAY)
    period = tl['period_ticks']
    tracks = tl['tracks']
    W, left, right = 760, 190, 740
    x = Scale(0, period, left, right)
    svg = Svg(W, 262, 'The day timeline: sky light, burning undead and night events over one day')
    top = 34

    # the named markers along the top
    for name, v in sorted(tl['time_markers'].items(), key=lambda kv: kv[1] if isinstance(kv[1], int) else kv[1]['ticks']):
        t = v if isinstance(v, int) else v['ticks']
        if isinstance(v, dict) and v.get('show_in_commands'):
            px = x(t)
            svg.line(px, top - 6, px, 200, stroke='@rule', dash='2 3')
            svg.text(px, top - 16, name.split(':')[1], size=SMALL, fill='@muted', anchor='middle')

    # sky light: the multiplier of the sky's light level, drawn as an area from 0 to 15
    sky = keyframes(tracks['minecraft:gameplay/sky_light_level'])
    y = Scale(0, 15, top + 62, top + 4)
    pts = [(t, v * 15) for t, v in sky]
    first, last = pts[0], pts[-1]
    # the curve wraps: interpolate the level at tick 0 and at the end of the day
    wrap = period - last[0] + first[0]
    edge = last[1] + (first[1] - last[1]) * (period - last[0]) / wrap
    line = [(0, edge)] + pts + [(period, edge)]
    area = [(x(t), y(v)) for t, v in line]
    svg.poly(area + [(x(period), y(0)), (x(0), y(0))], fill='@day', opacity=0.55)
    svg.poly(area, stroke='@amber', sw=2)
    for lv in (0, 4, 15):
        svg.text(left - 8, y(lv), str(lv), size=SMALL, fill='@muted', anchor='end')
    row_label(svg, left - 30, y(9), 'Sky light')

    # stepped tracks as bars
    rows = [
        ('Undead burn in sunlight', spans(keyframes(tracks['minecraft:gameplay/monsters_burn']), period, True), '@red'),
        ('Night blooms, creakings', spans(keyframes(tracks['minecraft:gameplay/eyeblossom_open']), period, True), '@purple'),
    ]
    ry = top + 92
    for label, sp, colour in rows:
        for a, b in sp:
            svg.rect(x(a), ry - 9, x(b) - x(a), 18, fill=colour, rx=3)
        row_label(svg, left - 12, ry, label)
        ry += 34

    # the times on the bars that matter most: when the undead stop and start burning
    for a, b in rows[0][1]:
        for t in (a, b):
            if 0 < t < period:
                svg.text(x(t), top + 92 + 20, '%s' % format(t, ','), size=10.5, fill='@muted', anchor='middle')

    bottom = ry - 8
    svg.behind(day_axis, svg, x, left, right, top - 6, bottom, period)
    svg.h = bottom + 44
    return svg


@diagram('Villager schedule')
def villager_schedule():
    tl = pack_json('minecraft/timeline/villager_schedule.json')
    period = tl['period_ticks']
    W, left, right = 760, 110, 740
    x = Scale(0, period, left, right)
    svg = Svg(W, 190, 'When adult and baby villagers work, meet, play, idle and rest over one day')
    colours = {'work': '@green', 'meet': '@amber', 'play': '@teal', 'idle': '@grey_soft', 'rest': '@blue'}
    top, ry = 16, 30
    for label, track in (('Adults', 'minecraft:gameplay/villager_activity'), ('Babies', 'minecraft:gameplay/baby_villager_activity')):
        frames = keyframes(tl['tracks'][track])
        acts = sorted({v for _, v in frames})
        for act in acts:
            for a, b in spans(frames, period, act):
                name = act.split(':')[1]
                svg.rect(x(a), ry - 12, x(b) - x(a), 24, fill=colours[name], rx=3)
                if x(b) - x(a) > 44:
                    ink = '@ink' if name == 'idle' else '@paper'
                    svg.text((x(a) + x(b)) / 2, ry, name, size=SMALL, fill=ink, anchor='middle', bold=True)
        svg.text(left - 12, ry, label, anchor='end')
        ry += 40
    bottom = ry - 16
    svg.behind(day_axis, svg, x, left, right, top, bottom, period)
    svg.h = bottom + 46
    return svg
