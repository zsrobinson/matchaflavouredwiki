#!/usr/bin/env python3
"""Find hand-written pages that went stale against the pack, without rendering anything.

The data templates fail quietly: {{Infobox auto}} for an item that no longer exists falls back to an
empty infobox, and {{Recipes|Old name}} prints "None." after a rename. Rendering can't tell those from
real "none"s, so this checks them against build/data.json (run tools/extract.py and tools/generate.py
first). Checks:
  - {{Infobox auto}}, {{Recipes}}, {{Uses}}, {{Sources}}: the item (the page title, or the first
    argument) exists in the pack, unless the page is a {{Vanilla}} item or a removed feature;
  - every {{Data/...}} transclusion exists in wiki/generated;
  - every {{Source|path}} exists in the pack at the commit in tools/source.lock (these link to GitHub;
    a missing file means the page describes something that moved or is gone).

  tools/lint_pages.py        exit 1 on any problem
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_xml  # noqa: E402

SRC = os.path.join(ROOT, 'source', 'matcha-flavoured')
ITEM_TEMPLATE = re.compile(r'\{\{\s*(Infobox auto|Recipes|Uses|Sources)\s*(?:\|([^|{}]*))?(?=[|}])')


def main():
    data = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
    items = set(data['items'])
    lock = open(os.path.join(ROOT, 'tools', 'source.lock')).read().strip()
    if data['meta']['git_head'] != lock:
        sys.exit('build/data.json is from %s, not the pinned %s: run tools/extract.py' % (data['meta']['git_head'][:8], lock[:8]))
    files = set(subprocess.run(['git', '-C', SRC, 'ls-tree', '-r', '--name-only', lock],
                               capture_output=True, text=True, check=True).stdout.splitlines())
    pages = build_xml.collect()
    problems = []
    for title, (ns, text, layer) in sorted(pages.items()):
        if layer != 'pages' or ns not in ('Main', 'Project') or re.match(r'\s*#REDIRECT', text, re.I):
            continue
        text = re.sub(r'<(nowiki|pre)>.*?</\1>', '', text, flags=re.S)  # examples in documentation
        exempt = '{{Vanilla' in text or '[[Category:Removed features' in text
        for m in ITEM_TEMPLATE.finditer(text):
            arg = (m.group(2) or '').strip()
            name = arg if arg and '=' not in arg else title
            if name not in items and not exempt:
                problems.append('%s: {{%s}} names "%s", which is not an item in the pack (renamed or removed? '
                                'a removed feature goes in [[Category:Removed features]])' % (title, m.group(1), name))
        for m in re.finditer(r'\{\{\s*(Data/[^|}]+)', text):
            if 'Template:' + m.group(1).strip() not in pages:
                problems.append('%s: {{%s}} is not generated any more' % (title, m.group(1).strip()))
        for m in re.finditer(r'\{\{\s*Source\s*\|([^|}]+)', text):
            path = m.group(1).strip()
            if '...' not in path and path not in files and not any(f.startswith(path.rstrip('/') + '/') for f in files):
                problems.append('%s: {{Source|%s}} does not exist in the pack at %s' % (title, path, lock[:8]))
    for p in problems:
        print(p)
    print('%d problem%s' % (len(problems), '' if len(problems) == 1 else 's'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
