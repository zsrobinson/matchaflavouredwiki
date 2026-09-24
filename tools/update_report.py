#!/usr/bin/env python3
"""The checklist for a pack update: everything that changed upstream, and the pages to check for each.

`git diff wiki/generated` shows what the generated tables now say, but a big update changes thousands of
those files, and the prose (and whatever the generator doesn't read: functions, worldgen, structures)
has no diff at all. This lists every change once, as a checklist, with the hand-written pages that
depend on it: pages titled after the thing, pages citing the changed file with {{Source|...}}, and pages
that mention it by name. The autopilot works through the list and ticks it off in the PR.

  tools/update_report.py --snapshot   before updating: keep build/data.json as the baseline
                                      (build/data.before.json)
  tools/update_report.py              after tools/fetch_sources.sh --update and tools/extract.py:
                                      write build/update-report.md and print a summary

Sections:
  1. Data changes: items, recipes, loot tables, trades, enchantments, advancements and names (lang),
     from comparing the two data.json files. The generated tables already show these; the pages listed
     may repeat the old facts in prose.
  2. Source files the generator doesn't read (functions, worldgen, structures, predicates...): only
     reading the diff can tell what changed. Grouped by folder.
  3. Pages citing files that were deleted or moved.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_xml  # noqa: E402

SRC = os.path.join(ROOT, 'source', 'matcha-flavoured')
DATA = os.path.join(ROOT, 'build', 'data.json')
BEFORE = os.path.join(ROOT, 'build', 'data.before.json')
OUT = os.path.join(ROOT, 'build', 'update-report.md')
MAX_PAGES = 12  # page names listed per line; the count is always given

# Source paths the generator turns into data (section 1 covers them). Everything else is prose-only.
DATA_BACKED = [
    (r'^MF_datapack/data/[^/]+/recipe/', 'recipes'),
    (r'^MF_datapack/data/[^/]+/loot_table/', 'loot tables'),
    (r'^MF_datapack/data/[^/]+/(villager_trade|trade_set|tags/villager_trade)/', 'trades'),
    (r'^MF_datapack/data/[^/]+/enchantment/', 'enchantments'),
    (r'^MF_datapack/data/[^/]+/advancement/', 'advancements'),
    (r'^MF_datapack/data/[^/]+/tags/item/', 'item tags (recipe ingredients)'),
    (r'^MF_resourcepack/assets/[^/]+/lang/en_us\.json$', 'names (lang)'),
    (r'^MF_resourcepack/assets/[^/]+/(textures|models|items)/', 'icons and screens (tools/images.py)'),
    (r'^MF_resourcepack/assets/[^/]+/lang/', 'other languages (not used)'),
]


def git(*args):
    return subprocess.run(['git', '-C', SRC] + list(args), capture_output=True, text=True, check=True).stdout


# ---------------------------------------------------------------- the hand-written pages
class Pages:
    def __init__(self):
        pages = build_xml.collect()
        self.text = {t: p[1] for t, p in pages.items() if p[2] == 'pages' and p[0] in ('Main', 'Project')}
        self.redirect = {}
        for t, s in list(self.text.items()):
            m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)', s, re.I)
            if m:
                self.redirect[t] = m.group(1).strip()
                del self.text[t]
        self.cites = defaultdict(set)  # source path -> pages citing it
        for t, s in self.text.items():
            for m in re.finditer(r'\{\{Source\|([^}|]+)', s):
                self.cites[m.group(1).strip()].add(t)
        self.lower = {t: s.lower() for t, s in self.text.items()}

    def titled(self, name):
        t = self.redirect.get(name, name)
        return t if t in self.text else None

    def citing(self, path):
        return self.cites.get(path, set())

    def mentioning(self, name):
        if len(name) < 3:
            return set()
        pat = re.compile(r'(?<![\w-])' + re.escape(name.lower()) + r'(?![\w-])')
        return {t for t, s in self.lower.items() if pat.search(s)}

    def containing(self, text):
        return {t for t, s in self.text.items() if text in s}


def page_list(pages, first=()):
    """'[[A]], [[B]] and 3 more', with the most relevant pages first."""
    first = [p for p in first if p]
    names = list(dict.fromkeys(first + sorted(set(pages) - set(first))))
    if not names:
        return 'no hand-written page'
    shown = ', '.join('[[%s]]' % n for n in names[:MAX_PAGES])
    return shown + (' and %d more' % (len(names) - MAX_PAGES) if len(names) > MAX_PAGES else '')


def line(text, pages=(), first=(), always=False, then=''):
    """A report line and whether it needs a person: it names a hand-written page, or always does.
    Lines that don't are covered by the generated tables alone."""
    first = [p for p in first if p]
    return text + ': ' + page_list(pages, first) + then, always or bool(set(pages) | set(first))


def short(v, n=90):
    s = json.dumps(v, ensure_ascii=False, sort_keys=True) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n - 1] + '…'


def verb(old, new, changed):
    return 'New' if not old else 'Removed' if not new else 'Changed (%s)' % ', '.join(changed)


# ---------------------------------------------------------------- data changes
ID = re.compile(r'(?<![\w.\-/:#])[a-z0-9_.\-]+:[a-z0-9_./\-]+')


def moved_ids(a, b):
    """{old ID: new ID} for every recipe, advancement, enchantment, loot table, function, trade and item
    model that is gone after the update while the same path exists under another namespace (1.12.2-beta
    moved most of `main:` to `matcha:`). Such a move changes the ID and every reference to it, and
    nothing a reader sees, so the report compares the old data under the new IDs."""
    def ids(d):
        trades = [t['id'] for levels in d['trades'].values() for ts in levels.values() if isinstance(ts, list) for t in ts]
        return set([r['id'] for r in d['recipes']] + list(d['advancements']) + list(d['enchantments']) +
                   list(d['loot']) + list(d.get('functions', {})) + trades)
    old, new = ids(a), ids(b)
    by_path = defaultdict(list)
    for i in new - old:
        by_path[i.split(':', 1)[-1]].append(i)
    moved = {i: by_path[i.split(':', 1)[-1]][0] for i in old - new if len(by_path.get(i.split(':', 1)[-1], ())) == 1}
    # item models, per item (`minecraft:echo_fish`, also written `echo_fish`, → `matcha:echo_fish`)
    for name in set(a['items']) & set(b['items']):
        ma, mb = (set(d['items'][name]['models']) for d in (a, b))
        for m in ma - mb:
            to = [n for n in mb if n.split(':', 1)[-1] == m.split(':', 1)[-1]]
            if len(to) == 1:
                moved[m] = to[0]
                if m.startswith('minecraft:'):
                    moved[m.split(':', 1)[1]] = to[0]
    return moved


MODEL_KEYS = ('item_model', 'minecraft:item_model', 'model')


def rename_ids(v, moved, key=None):
    """v with every moved ID (a string, a key, or part of a longer string) written as its new ID. A bare
    model ID (`echo_fish`) is only renamed where a model is expected."""
    if not moved:
        return v
    if isinstance(v, dict):
        return {rename_ids(k, moved): rename_ids(x, moved, k) for k, x in v.items()}
    if isinstance(v, list):
        return [rename_ids(x, moved, key) for x in v]
    if isinstance(v, str):
        if key in MODEL_KEYS and ':' not in v:
            return moved.get(v, v)
        return ID.sub(lambda m: moved.get(m.group(0), m.group(0)), v)
    return v


def diff_dicts(old, new, fields=None):
    keys = fields or sorted(set(old) | set(new))
    return [k for k in keys if old.get(k) != new.get(k)]


def item_lines(a, b, pages):
    out = []
    ia, ib = a['items'], b['items']
    added, removed = sorted(set(ib) - set(ia)), sorted(set(ia) - set(ib))
    # a removed and an added item with the same model or base item and components is probably a rename
    for old in list(removed):
        for new in added:
            same_model = set(ia[old]['models']) & set(ib[new]['models'])
            same_item = ia[old]['base_id'] == ib[new]['base_id'] and ia[old]['components'] == ib[new]['components']
            if same_model or same_item:
                out.append(line('Renamed? **%s** → **%s**' % (old, new), pages.mentioning(old), [pages.titled(old)],
                                always=True, then='. Move or redirect the article and fix the links.'))
                removed.remove(old)
                added.remove(new)
                break
    for name in removed:
        out.append(line('Removed item **%s**' % name, pages.mentioning(name), [pages.titled(name)], always=True,
                        then='. Say it was removed and when, add it to "Removed features", keep its History.'))
    for name in added:
        src = ', '.join(sorted({s['src'] for s in ib[name]['sources']})[:2])
        out.append(line('New item **%s** (%s)' % (name, src), [], [pages.titled(name)], always=True,
                        then='. It gets a generated stub; write an article unless it is a minor variant.'))
    for name in sorted(set(ia) & set(ib)):
        ca = dict(ia[name]['components'], base_id=ia[name]['base_id'])
        cb = dict(ib[name]['components'], base_id=ib[name]['base_id'])
        ca.pop('lore_rich', None)
        cb.pop('lore_rich', None)
        changed = diff_dicts(ca, cb)
        if changed:
            what = '; '.join('%s: %s → %s' % (k, short(ca.get(k), 60), short(cb.get(k), 60)) for k in changed[:4])
            out.append(line('Changed item **%s** (%s)' % (name, what), pages.mentioning(name), [pages.titled(name)]))
    return out


def recipe_lines(a, b, pages):
    ra, rb = ({r['id']: r for r in d['recipes']} for d in (a, b))
    fields = ('type', 'output', 'grid', 'ingredients', 'input', 'cookingtime', 'experience', 'template', 'base', 'addition')
    out = []
    for rid in sorted(set(ra) | set(rb)):
        old, new = ra.get(rid), rb.get(rid)
        changed = diff_dicts(old or {}, new or {}, fields)
        if old and new and not changed:
            continue
        r = new or old
        item = r['output']['name']
        out.append(line('%s recipe `%s` for **%s** (%s)' % (verb(old, new, changed), rid, item, r['station']),
                        pages.citing(r['src']), [pages.titled(item)]))
    return out


def loot_lines(a, b, pages):
    out = []
    la, lb = a['loot'], b['loot']
    for lid in sorted(set(la) | set(lb)):
        old, new = la.get(lid), lb.get(lid)
        if old and new and old['entries'] == new['entries']:
            continue
        t = new or old
        items = sorted({e['item'] for e in t['entries'] if e.get('item')})[:6]
        out.append(line('%s loot table `%s` (%s)' % (verb(old, new, []).split(' (')[0], lid, ', '.join(items) or 'nested tables'),
                        pages.citing(t['src'])))
    return out


def trade_lines(a, b, pages):
    def flat(d):
        out = {}
        for prof, levels in d['trades'].items():
            for level, trades in levels.items():
                if isinstance(trades, list):
                    for t in trades:
                        out[(d['professions'].get(prof, prof), level, t['id'])] = t
        return out
    ta, tb = flat(a), flat(b)
    out = []
    for key in sorted(set(ta) | set(tb)):
        old, new = ta.get(key), tb.get(key)
        if old and new and dict(old, src=None) == dict(new, src=None):  # a moved file is in "Source files"
            continue
        prof, level, tid = key
        t = new or old
        gives = (t.get('gives') or {}).get('name')
        out.append(line('%s trade: %s %s, `%s` gives %s' % (verb(old, new, diff_dicts(old or {}, new or {})), prof,
                                                          level.replace('_', ' '), tid, gives),
                        pages.citing(t['src']), [pages.titled(prof)]))
    return out


def ench_lines(a, b, pages):
    fields = ('name', 'max_level', 'weight', 'anvil_cost', 'slots', 'supported_items', 'primary_items',
              'exclusive_set', 'effects')
    out = []
    for eid in sorted(set(a['enchantments']) | set(b['enchantments'])):
        old, new = a['enchantments'].get(eid), b['enchantments'].get(eid)
        changed = diff_dicts(old or {}, new or {}, fields)
        if old and new and not changed:
            continue
        out.append(line('%s enchantment `%s`' % (verb(old, new, changed), eid), pages.citing((new or old)['src'])))
    return out


def adv_lines(a, b, pages):
    fields = ('title', 'description', 'parent', 'frame', 'hidden', 'rewards', 'criteria_raw', 'requirements')
    out = []
    for aid in sorted(set(a['advancements']) | set(b['advancements'])):
        old, new = a['advancements'].get(aid), b['advancements'].get(aid)
        changed = diff_dicts(old or {}, new or {}, fields)
        if old and new and not changed:
            continue
        v = new or old
        title = v.get('title')
        out.append(line('%s advancement `%s`%s' % (verb(old, new, changed), aid, ' "%s"' % title if title else ''),
                        pages.citing(v['src']) | (pages.mentioning(title) if title else set()),
                        [pages.titled(title) if title else None, 'Advancements' if title else None]))
    return out


def lang_lines(a, b, pages):
    la, lb = a['lang_pack'], b['lang_pack']
    out = []
    for k in sorted(set(la) | set(lb)):
        old, new = la.get(k), lb.get(k)
        if old == new:
            continue
        if old and new:
            # pages quoting the old text (names, tooltips, advancement text) now show it wrong
            out.append(line('Text `%s`: "%s" → "%s"' % (k, short(old, 70), short(new, 70)),
                            pages.containing(old) if len(old) >= 4 else ()))
        else:
            out.append(('%s text `%s`: "%s"' % ('New' if new else 'Removed', k, short(new or old, 90)), False))
    return out


# ---------------------------------------------------------------- source files the generator doesn't read
def file_lines(frm, to, pages):
    rows = [line.split('\t') for line in git('diff', '--name-status', '-M', frm, to).splitlines()]
    known_dirs = set(os.path.dirname(p) for p in git('ls-tree', '-r', '--name-only', frm).splitlines())
    covered = defaultdict(int)
    groups = defaultdict(list)
    deleted = []
    for row in rows:
        status, paths = row[0][0], row[1:]
        path = paths[-1]
        if status in 'DR':
            deleted.append(paths[0])
        if path == 'changelog.md':
            continue  # a line of its own
        area = next((label for pat, label in DATA_BACKED if re.search(pat, path)), None)
        if area:
            covered[area] += 1
        else:
            groups[os.path.dirname(path)].append((status, paths))
    out = []
    for folder in sorted(groups):
        files = groups[folder]
        new_kind = folder not in known_dirs and not any(d.startswith(folder + '/') for d in known_dirs)
        where = '`%s/`' % folder if folder else 'The repository root'
        cited = set()
        for _, paths in files:
            for p in paths:
                cited |= pages.citing(p)
        names = ', '.join('%s %s' % (s, os.path.basename(p[-1])) for s, p in files[:8])
        more = ' and %d more' % (len(files) - 8) if len(files) > 8 else ''
        out.append(('%s (%d file%s: %s%s)%s. Read the diff. Pages citing these files: %s' % (
            where, len(files), '' if len(files) == 1 else 's', names, more,
            ' **New folder: does tools/extract.py need to read it?**' if new_kind else '',
            page_list(cited) if cited else 'none (search the pages for the feature)'), True))
    return out, covered, deleted


def main():
    if '--snapshot' in sys.argv:
        shutil.copyfile(DATA, BEFORE)
        print('baseline: build/data.before.json (pack %s)' % json.load(open(BEFORE))['meta']['git_head'][:8])
        return 0
    if not os.path.exists(BEFORE):
        sys.exit('No baseline. Before updating, run tools/extract.py and tools/update_report.py --snapshot.')
    a, b = json.load(open(BEFORE, encoding='utf-8')), json.load(open(DATA, encoding='utf-8'))
    frm, to = a['meta']['git_head'], b['meta']['git_head']
    moved = moved_ids(a, b)
    a = rename_ids(a, moved)
    pages = Pages()
    commits = git('log', '--oneline', '--no-merges', '%s..%s' % (frm, to)).splitlines()

    files, covered, deleted = file_lines(frm, to, pages)
    stale = []
    for path in sorted(deleted):
        if pages.citing(path):
            stale.append(('`%s` is gone: %s cite it. Update the facts and the citation.' % (path, page_list(pages.citing(path))), True))
    sections = [
        ('Items', item_lines(a, b, pages)),
        ('Names and texts (lang)', lang_lines(a, b, pages)),
        ('Recipes', recipe_lines(a, b, pages)),
        ('Loot tables', loot_lines(a, b, pages)),
        ('Villager trades', trade_lines(a, b, pages)),
        ('Enchantments', ench_lines(a, b, pages)),
        ('Advancements', adv_lines(a, b, pages)),
        ('Source files the generator does not read', files),
        ('Pages citing deleted or moved files', stale),
    ]
    md = ['# Update report: %s..%s' % (frm[:8], to[:8]), '',
          '%d commits. Pack: "%s" → "%s".' % (len(commits), a['meta']['pack_description'].splitlines()[-1],
                                             b['meta']['pack_description'].splitlines()[-1]), '',
          'Work through every line: fix the pages it names (or confirm they are still right) and tick it. '
          'Lines under one heading can go to one agent.', '']
    by_ns = defaultdict(int)
    for o, n in {(o if ':' in o else 'minecraft:' + o, n) for o, n in moved.items()}:  # `x` is `minecraft:x`
        by_ns['`%s:` → `%s:`' % (o.split(':')[0], n.split(':')[0])] += 1
    if by_ns:
        md += ['%d IDs moved to another namespace (%s). The old data is compared under the new IDs.' % (
            sum(by_ns.values()), ', '.join('%s %d' % kv for kv in sorted(by_ns.items()))), '']
    if covered:
        md += ['Changed files the generator reads (the tables below and `git diff wiki/generated` cover them): ' +
               ', '.join('%s %d' % (k, v) for k, v in sorted(covered.items())) + '.', '']
    if 'changelog.md' in git('diff', '--name-only', frm, to).split():
        md += ['- [ ] `changelog.md` changed: read `git -C source/matcha-flavoured diff %s..%s -- changelog.md`.' % (frm[:8], to[:8]), '']
    todo = covered_only = 0
    for title, lines in sections:
        work = [text for text, needs in lines if needs]
        rest = [text for text, needs in lines if not needs]
        todo += len(work)
        covered_only += len(rest)
        if work:
            md += ['## %s (%d)' % (title, len(work)), ''] + ['- [ ] ' + t for t in work] + ['']
        if rest:
            md += ['<details><summary>%s: %d more change%s no hand-written page depends on (the generated tables '
                   'show them)</summary>' % (title, len(rest), '' if len(rest) == 1 else 's'), '']
            md += ['- ' + t.replace(': no hand-written page', '') for t in rest] + ['', '</details>', '']
    md += ['## Commits', ''] + ['- ' + c for c in commits[:300]]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md) + '\n')
    print('%s: %d commits, %d checklist lines (%s); %d more changes covered by the generated tables' % (
        os.path.relpath(OUT, ROOT), len(commits), todo,
        ', '.join('%s %d' % (t, sum(n for _, n in l)) for t, l in sections if any(n for _, n in l)) or 'nothing',
        covered_only))
    return 0


if __name__ == '__main__':
    sys.exit(main())
