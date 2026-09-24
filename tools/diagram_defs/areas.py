"""Effects with a reach: radius maps drawn to scale around their source, one panel per level."""
import re

from diagrams import SMALL, STYLE, Svg, block_grid, diagram, legend, mcfunction, need, text_width


def rings(svg, cx, cy, scale, layers, grid_half=None):
    """Concentric areas around a source, biggest first so the smaller ones sit on top. The game
    measures these as straight-line distance to a mob's exact position, so they're true circles
    (slices of a sphere); styles with a block grid draw them over it, translucent, for scale.
    layers: [(radius, fill, edge, dash)]"""
    grid = STYLE.get('grid')
    if grid:
        block_grid(svg, cx, cy, scale, grid_half or int(max(l[0] for l in layers)) + 2)
    for r, fill, edge, dash in sorted(layers, key=lambda l: -l[0]):
        svg.circle(cx, cy, r * scale, fill=fill, stroke=edge, sw=1.5, dash=dash, opacity=0.72 if grid and fill != 'none' else None)


def source_dot(svg, cx, cy):
    svg.circle(cx, cy, 4, fill='@ink')


def scale_bar(svg, x, y, blocks, scale):
    svg.line(x, y, x + blocks * scale, y, stroke='@muted', sw=1.5)
    for px in (x, x + blocks * scale):
        svg.line(px, y - 4, px, y + 4, stroke='@muted', sw=1.5)
    svg.text(x + blocks * scale / 2, y + 13, '%d blocks' % blocks, size=SMALL, fill='@muted', anchor='middle')


def distance(line):
    return int(re.search(r'distance=\.\.(\d+)', line).group(1))


@diagram('Warding')
def warding():
    levels = []
    for lv in range(1, 5):
        src = mcfunction('matcha/function/enchantment_effects/warding/power_%d.mcfunction' % lv)
        lines = [l for l in src.splitlines() if l.startswith('execute')]
        slow = distance(next(l for l in lines if 'apply_slowness' in l))
        damage = distance(next(l for l in lines if l.startswith('execute as @n[distance=')))
        wither = next((distance(l) for l in lines if 'type=wither]' in l), None)
        hit = need(r'@n\[distance=\.\.\d+,type=#matcha:warding_targets[^\]]*\] run function \S+ \{damage:(\d+)\}', src,
                   'warding damage %d' % lv, cast=int)
        levels.append((lv, slow, damage, wither, hit))
    biggest = max(max(l[1], l[3] or 0) for l in levels)
    panel, W = 190, 760
    scale = (panel / 2 - 8) / (biggest + 2)
    svg = Svg(W, 0, "Warding's slowing, damage and Wither radii at levels 1 to 4, to scale")
    cy = 30 + panel / 2
    for i, (lv, slow, damage, wither, hit) in enumerate(levels):
        cx = panel * i + panel / 2
        layers = [(slow, '@blue_soft', '@blue', None), (damage, '@red_soft', '@red', None)]
        if wither:
            layers.append((wither, 'none', '@purple', '5 4'))
        rings(svg, cx, cy, scale, layers, grid_half=int(biggest) + 2)
        source_dot(svg, cx, cy)
        svg.text(cx, 14, 'Warding %d' % lv, anchor='middle', bold=True)
        y = cy + panel / 2 + 8
        svg.text(cx, y, 'Slowing: %d blocks' % slow, size=SMALL, fill='@blue', anchor='middle')
        svg.text(cx, y + 17, 'Damage: %d blocks' % damage, size=SMALL, fill='@red', anchor='middle')
        svg.text(cx, y + 34, 'Wither: %s' % ('%d blocks' % wither if wither else 'never'), size=SMALL,
                 fill='@purple', anchor='middle')
    y = cy + panel / 2 + 70
    legend(svg, 12, y, [('@blue_soft', 'Every undead mob slowed', 'box'), ('@red_soft', 'One target damaged each pulse', 'box'),
                        ('@purple', 'Wither targeted first', 'dash')])
    scale_bar(svg, W - 12 - 8 * scale, y - 4, 8, scale)
    svg.h = y + 18
    return svg


@diagram('Doom')
def doom():
    """A small aside beside the page's table: the four reaches to scale, each ring labelled at its top."""
    levels = []
    for lv in range(1, 5):
        check = mcfunction('matcha/function/enchantment_effects/adamant_effects/check_doom_%d.mcfunction' % lv)
        apply = mcfunction('matcha/function/enchantment_effects/adamant_effects/apply_doom_%d.mcfunction' % lv)
        levels.append((lv, int(need(r'distance=\.\.(\d+)', check, 'doom radius %d' % lv)),
                       need(r'damage @s (\d+)', apply, 'doom damage %d' % lv)))
    W, size = 360, 300
    biggest = max(r for _, r, _ in levels)
    scale = (size / 2 - 4) / (biggest + 2)
    svg = Svg(W, 0, "Doom's reach for one to four pieces of adamant armor, to scale")
    cx, cy = W / 2, size / 2
    palette = ['@red_soft', '@amber_soft', '@purple_soft', '@grey_soft']
    rings(svg, cx, cy, scale, [(r, palette[i], '@rule', None) for i, (_, r, _) in enumerate(levels)])
    source_dot(svg, cx, cy)
    for lv, r, _ in levels:  # each ring's reach just inside its top edge
        svg.text(cx, cy - r * scale + 11, '%d' % r, size=SMALL, anchor='middle')
    # the key: pieces worn, reach and damage, in the rings' colours
    y = size + 20
    for lv, r, dmg in levels:
        svg.rect(12, y - 7, 14, 14, fill=palette[lv - 1], stroke='@rule', rx=2)
        pieces = {1: '1 piece', 2: '2 pieces', 3: '3 pieces', 4: 'Full set'}[lv]
        svg.text(34, y, '%s: %d blocks,' % (pieces, r), size=SMALL, fill='@ink')
        svg.hp(34 + text_width('%s: %d blocks, ' % (pieces, r), SMALL), y, dmg, size=SMALL, fill='@muted')
        y += 19
    svg.h = y - 4
    return svg
