"""Progression: how the pack's tiers and stations lead into each other."""
from diagrams import SMALL, Flow, Svg, data, diagram


def made_in(output, stations=('Mud Kiln', 'Blast Furnace', 'Oven', 'Furnace', 'Kindling')):
    """The first station of `stations` that has a recipe for an item."""
    have = {r.get('station') for r in data()['recipes'] if r['output']['name'] == output}
    return next((s for s in stations if s in have), None)


def alloys_on(base_piece):
    """Smithing recipes that put an alloy onto a base piece: [(result, alloy)]."""
    out = []
    for r in data()['recipes']:
        if r.get('station', '').startswith('Smithing') and base_piece in (r.get('base') or {}).get('names', []):
            out.append((r['output']['name'], r['addition']['names'][0]))
    return sorted(out)


@diagram('Equipment tiers')
def equipment_tiers():
    svg = Svg(760, 300, 'The equipment tiers: wood, copper, iron and diamond, and the alloys smithed onto each')
    f = Flow(svg)
    main = [('Wooden', 'Wood', 62, None), ('Copper', 'Copper', 250, 'Copper Ingot'),
            ('Iron', 'Iron', 440, 'Iron Ingot'), ('Diamond', 'Diamond', 640, 'Diamond')]
    y0, y1 = 44, 160
    for key, label, x, _ in main:
        f.node(key, x, y0, label, w=112, icon='%s Pickaxe' % key, bold=True)
    for (a, _, ax, _), (b, _, bx, made) in zip(main, main[1:]):
        # the station that smelts the next tier's material, as its icon on the arrow
        f.arrow(a, b)
        station = made_in(made)
        mx = (ax + 56 + bx - 56) / 2
        svg.icon(station, mx, y0 - 22, 26)
        svg.text(mx, y0 + 20, station, size=SMALL, fill='@muted', anchor='middle', fit=bx - ax - 116)
    # alloys, from the smithing recipes that take each base chestplate
    for key, _, x, _ in main[1:]:
        results = alloys_on('%s Chestplate' % key)
        xs = [x] if len(results) == 1 else [x - 57, x + 57]
        for (result, alloy), ax in zip(results, xs):
            name = result.replace(' Chestplate', '')
            f.node(name, ax, y1, name, w=108, icon='%s Pickaxe' % name, fill='@amber_soft', edge='@amber')
            f.arrow(key, name, colour='@amber')
    svg.text(440, y1 + 38, 'Alloys are smithed onto the base gear at a smithing table.', size=SMALL, fill='@muted', anchor='middle')
    f.node('Golden', 62, y1, 'Gold', w=108, icon='Golden Pickaxe', sub='side tier', dash='5 4')
    svg.h = y1 + 52
    return svg
