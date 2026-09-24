"""Data for the recipe browser, the page "Matcha Flavoured Wiki:Recipe browser" of the static export.

The page itself is a hand-written project page (its lead, the station links and a placeholder the
script fills); site/recipes.js draws the browser in it: recipes by output or by ingredient, filtered
by station, each on the station screen the articles use, and a crafting tree down to raw materials.
This module builds what the script needs, at export time, into one file:

  _static/recipes.json
    r  one row per recipe and trade, from build/data.json through tools/generate.py's own helpers (so
       slot names, tag aliases, variants and counts are exactly what the article tables show):
         s station key (Module:Station's: crafting, oven, kiln, blast, kindling, smithing,
           stonecutter; trade for a villager's offer)
         g the input slots, by Module:Station's slot names (A1-C3, Input, Template/Base/Addition;
           1 and 2 for a trade's wants), each "Name" or "Name,count"
         o output name, c output count; l shapeless; t seconds and x experience of a cooking
           recipe; v a vanilla recipe the pack keeps; p and lv a trade's profession and level
    a  tag aliases ("Any Planks") -> the item names they stand for (Module:Inventory slot/Aliases)
    n  item name -> its vanilla name, where the pack renamed it (so "emerald" finds Obol)
    w  the items the world gives (block and mob drops, fishing, harvesting...: the Sources tables
       less chest loot, and less a block dropping itself), which the crafting tree takes as raw
       materials where a recipe only undoes another (Coal, not Coal from a Block of Coal) and prefers
       among a tag's members (Raw Iron, not Iron Horse Armor)
    u  item name -> the link its slots use (its page here, or minecraft.wiki)
    h  slot name -> the slot's HTML, rendered by the wiki's own Module:Inventory slot (icon, cycling
       frames, the in-game tooltip), so a screen drawn by the script is the article's screen

Everything is sorted, so an unchanged site exports byte for byte the same. To remove the browser,
delete this file, site/recipes.js, site/recipes.css, tests/recipes.test.mjs and the project page,
and the few lines in tools/export_static.py that name recipe_browser (see AGENTS.md).
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TITLE = 'Matcha Flavoured Wiki:Recipe browser'

STATIONS = {'Crafting Table': 'crafting', 'Oven': 'oven', 'Mud Kiln': 'kiln', 'Blast Furnace': 'blast',
            'Kindling': 'kindling', 'Smithing Table': 'smithing', 'Stonecutter': 'stonecutter'}
LEVELS = {'level_1': 'Novice', 'level_2': 'Apprentice', 'level_3': 'Journeyman', 'level_4': 'Expert',
          'level_5': 'Master', 'buying': 'Special offer', 'common': 'Common offer', 'uncommon': 'Uncommon offer'}
WORLD = {'Block drops', 'Mob drops', 'Fishing', 'Harvesting', 'Shearing', 'Gameplay', 'Archaeology'}
BATCH = 250  # slots per parse request: well under MediaWiki's 2 MB include limit


def number(x):
    return int(x) if float(x).is_integer() else x


def slot_names(text):
    """The item names in one slot's text ("Oak Log;Birch Log", "Obol,3") without counts."""
    return [re.sub(r',\d+$', '', n).strip() for n in text.split(';') if n.strip()]


def recipe_rows(g):
    """Every recipe and trade as a browser row; g is tools/generate.py (imported)."""
    rows = []
    for r in g.ALL_RECIPES + g.VANILLA_KEPT:
        if r['id'].startswith('debug:'):
            continue  # developer recipes (they need a command block), as in the Uses tables
        t = r['type'].split(':')[-1]
        slots = {}
        row = {'s': STATIONS[r['station']]}
        if t == 'crafting_shaped':
            for y, line in enumerate(r['pattern']):
                for x, ch in enumerate(line):
                    if ch != ' ':
                        slots['ABC'[x] + str(y + 1)] = g.slot_text(r['key'][ch])
        elif t == 'crafting_shapeless':
            for i, ing in enumerate(r['ingredients'][:9]):
                slots['ABC'[i % 3] + str(i // 3 + 1)] = g.slot_text(ing)
            row['l'] = 1
        elif t in ('smelting', 'smoking', 'blasting', 'campfire_cooking'):
            slots['Input'] = g.slot_text(r['input'])
            row['t'] = number(g.cook_ticks(r) / 20)
            if r.get('experience'):
                row['x'] = number(r['experience'])
        elif t == 'stonecutting':
            slots['Input'] = g.slot_text(r['input'])
        elif t == 'smithing_transform':
            for k in ('template', 'base', 'addition'):
                if r.get(k):
                    slots[k.title()] = g.slot_text(r[k])
        else:
            continue
        row['g'] = {k: v for k, v in slots.items() if v}
        row['o'] = g.safe(g.slot_name(r['output']))
        if r['output'].get('count', 1) > 1:
            row['c'] = r['output']['count']
        if r['origin'] != 'pack':
            row['v'] = 1
        rows.append(row)

    def stack(s):
        return (g.safe(g.slot_name(s)) + (',%d' % s['count'] if s.get('count', 1) > 1 else '')) if s else ''
    for prof in sorted(g.TRADES):
        for lk in sorted(k for k in g.TRADES[prof] if not k.endswith('_meta')):
            for t in g.TRADES[prof][lk]:
                if not t.get('gives'):
                    continue
                row = {'s': 'trade', 'g': {k: v for k, v in (('1', stack(t.get('wants'))), ('2', stack(t.get('additional_wants')))) if v},
                       'o': g.safe(g.slot_name(t['gives'])), 'p': g.PROF.get(prof, prof), 'lv': LEVELS.get(lk, lk)}
                if t['gives'].get('count', 1) > 1:
                    row['c'] = t['gives']['count']
                rows.append(row)
    # the order the tables show them in: by output, then station, as on the articles
    order = list(STATIONS.values()) + ['trade']
    rows.sort(key=lambda r: (r['o'].lower(), order.index(r['s']), json.dumps(r, sort_keys=True)))
    return rows


def build(g):
    """The data without the slot HTML: {'r': rows, 'a': aliases}; and every slot name the rows use."""
    rows = recipe_rows(g)  # fills g.ALIASES as a side effect of slot_text
    names = set()
    for r in rows:
        names.add(r['o'])
        for v in r['g'].values():
            names.update(slot_names(v))
    aliases = {k: v for k, v in sorted(g.ALIASES.items()) if k in names}
    for members in aliases.values():
        names.update(members)
    names.update(STATIONS)  # the stations' own icons, on the browser's first screen
    vanilla = {}
    for n in sorted(names):
        it = g.ITEMS.get(n)
        if it and it.get('renamed_vanilla') and it.get('vanilla_name') and it['vanilla_name'].lower() != n.lower():
            vanilla[n] = it['vanilla_name']
    def own_block(n, lid):  # a placed slab drops the slab: that says nothing about where slabs come from
        base = (g.ITEMS.get(n) or {}).get('base_id') or ''
        return lid.split(':')[-1] == 'blocks/' + base.split(':')[-1]
    world = sorted(n for n in names if any(src[0] in WORLD and not own_block(n, src[2]) for src in g.SOURCES.get(n, [])))
    return {'r': rows, 'a': aliases, 'n': vanilla, 'w': world}, sorted(names)


def parse(base, text):
    """Render wikitext with the running wiki's parser (as the page of the browser)."""
    body = urllib.parse.urlencode({'action': 'parse', 'format': 'json', 'formatversion': '2', 'contentmodel': 'wikitext',
                                   'prop': 'text', 'disablelimitreport': '1', 'wrapoutputclass': '', 'title': TITLE,
                                   'text': text}).encode()
    with urllib.request.urlopen(base.rstrip('/') + '/api.php', body, timeout=300) as r:
        data = json.load(r)
    if 'error' in data:
        raise RuntimeError('recipe browser: parse failed: %s' % data['error'])
    return data['parse']['text']


def render_slots(base, names, rewrite=lambda s: s):
    """name -> the HTML of its inventory slot, as Module:Station places it (no count: the script adds it)."""
    out = {}
    for i in range(0, len(names), BATCH):
        chunk = names[i:i + BATCH]
        text = ''.join('<div class="mfw-rb-cut" data-n="%d">{{#invoke:Inventory slot|slot|1=%s}}</div>' % (n, name)
                       for n, name in enumerate(chunk))
        parts = re.split(r'<div class="mfw-rb-cut" data-n="(\d+)">', parse(base, text))[1:]
        for n, part in zip(parts[::2], parts[1::2]):
            part = re.sub(r'</div>\s*$', '', part.strip())
            out[chunk[int(n)]] = slim(rewrite(part.strip()))
    missing = [n for n in names if not out.get(n) or 'class="error"' in out[n]]
    if missing:
        raise RuntimeError('recipe browser: no slot for %s' % ', '.join(missing[:10]))
    return out


def slim(slot_html):
    """Drop what the browser doesn't need from a slot: the file page's long alt text (the tooltip names
    the item) and attributes about the file."""
    slot_html = re.sub(r' alt="([^"]*?)\.png: Inventory sprite for [^"]*"', r' alt="\1"', slot_html)
    slot_html = re.sub(r' (?:data-file-width|data-file-height|decoding|data-pagefind-ignore)="[^"]*"', '', slot_html)
    return slot_html


def slot_link(slot_html):
    """The link a slot goes to (the first frame's), or None."""
    m = re.search(r'<a [^>]*href="([^"]+)"', slot_html)
    return html.unescape(m.group(1)) if m else None


def page(doc):
    """The browser's page in the export: MediaWiki writes the data's path as /&#95;static/, which
    tools/fingerprint.py wouldn't see (and so wouldn't version)."""
    return doc.replace('data-src="/&#95;static/', 'data-src="/_static/')


def write(out, base, rewrite=lambda s: s):
    """Build _static/recipes.json in the export (after the images are in place). rewrite is the
    exporter's link rewriting (redirects, red links, the site's own URLs). The slots' pictures get
    ?v=<hash> as tools/fingerprint.py versions the pages' (it doesn't read JSON), so browsers keep them."""
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import generate  # noqa: E402  (reads build/data.json)
    data, names = build(generate)
    slots = render_slots(base, names, rewrite)
    import fingerprint
    hashes = {}
    for v in slots.values():
        for ref in re.findall(r'"(/images/[^"?]+)', v):
            path = os.path.join(out, urllib.parse.unquote(ref).lstrip('/'))
            if ref not in hashes and os.path.exists(path):
                hashes[urllib.parse.unquote(ref)] = fingerprint.file_hash(path)
    slots = {k: fingerprint.versioned(v, hashes) for k, v in slots.items()}
    data['u'] = {n: slot_link(slots[n]) for n in names if n not in data['a'] and slot_link(slots[n])}
    data['h'] = slots
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, '_static', 'recipes.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    return len(data['r'])


if __name__ == '__main__':
    # tools/recipe_browser.py [--out dist] [--base http://localhost:8080]: rebuild only the data file
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    ap.add_argument('--base', default='http://localhost:8080')
    a = ap.parse_args()
    print('%d recipes -> %s' % (write(a.out, a.base), os.path.join(a.out, '_static', 'recipes.json')))
