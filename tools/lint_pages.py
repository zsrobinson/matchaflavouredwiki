#!/usr/bin/env python3
"""Find hand-written pages that went stale against the pack, without rendering anything.

The data templates fail quietly: {{Infobox auto}} for an item that no longer exists falls back to an
empty infobox, and {{Recipes|Old name}} prints "None." after a rename. Rendering can't tell those from
real "none"s, so this checks them against build/data.json (run tools/extract.py and tools/generate.py
first). Checks:
  - {{Infobox auto}}, {{Recipes}}, {{Uses}}, {{Sources}}: the item (the page title, or the first
    argument) exists in the pack, unless the page is a {{Vanilla}} item or a removed feature;
  - every {{Data/...}} transclusion exists in wiki/generated, and every named argument it passes is
    one the generated template reads. Generated tables take hand-written notes keyed by row ID
    ({{Data/Advancements/tutorial|matcha:tutorial/root=...}}); a note whose row is gone is an error;
  - every {{Source|path}} exists in the pack at the commit in tools/source.lock (these link to GitHub;
    a missing file means the page describes something that moved or is gone), or at the commit given
    with at= (code only on main, for content marked {{Upcoming}}).
  - every {{Value|item|field}} names an item, field and format that build/values.json has (the same
    table as Module:Data/Values; tools/values.py);
  - no secret item (MediaWiki:Mfw-secrets) is named in plain text outside a {{Spoiler}} box. Spoilers are
    hidden by default: site/Spoilers.php hides links to secrets, but it can't see words (wiki/STYLE.md,
    "Spoilers"). Its own page may name it;
  - warning only: an article with {{Infobox auto}} that types its own item's heal amount after "heals"
    ({{Hp|n}} equal to the data) instead of {{Value|item|heals}}. Not an error, because the same
    number can be right to type (a comparison with another item, a vanilla value).

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
import values as value_lookup  # noqa: E402

SRC = os.path.join(ROOT, 'source', 'matcha-flavoured')
ITEM_TEMPLATE = re.compile(r'\{\{\s*(Infobox auto|Recipes|Uses|Sources)\s*(?:\|([^|{}]*))?(?=[|}])')


def transclusions(text, prefix):
    """(name, [top-level arguments]) for every {{<prefix>...}} in text, nested templates and links included."""
    for m in re.finditer(r'\{\{\s*(' + re.escape(prefix) + r'[^|}]*)', text):
        depth, i, args, start = 0, m.start(), [], None
        while i < len(text):
            two = text[i:i + 2]
            if two in ('{{', '[['):
                depth += 1
                i += 2
                continue
            if two in ('}}', ']]'):
                depth -= 1
                i += 2
                if depth == 0:
                    if start is not None:
                        args.append(text[start:i - 2])
                    break
                continue
            if text[i] == '|' and depth == 1:
                if start is not None:
                    args.append(text[start:i])
                start = i + 1
            i += 1
        yield m.group(1).strip(), args


LINKING = re.compile(r'\{\{\s*(?:ItemLink|Slot|EffectLink|Recipes|Uses|Sources|Infobox auto|Value|Source)\s*\|[^{}]*\}\}')


def spoiler_leaks(title, text, secrets):
    """(secret, context) for every secret named in words outside a {{Spoiler}} box's scope: the rest of
    its section (the whole page for a box in the lead). Links are left out: site/Spoilers.php hides them."""
    if not secrets:
        return []
    names = re.compile(r'\b(%s)(?:e?s)?\b' % '|'.join(re.escape(s) for s in sorted(secrets, key=len, reverse=True)), re.I)
    shown, level, hidden_from = [], 0, None
    for line in text.split('\n'):
        h = re.match(r'^(=+)\s*(.*?)\s*\1\s*$', line)
        if h:
            level = len(h.group(1))
            if hidden_from is not None and level <= hidden_from:
                hidden_from = None
        elif re.match(r'\s*\{\{\s*Spoiler\s*[|}]', line):
            hidden_from = level
            continue
        if hidden_from is None:
            shown.append(line)
    words = re.sub(r'<!--.*?-->|<code>.*?</code>', ' ', '\n'.join(shown), flags=re.S)  # a ref's quote is shown too
    words = LINKING.sub(' ', re.sub(r'\[\[[^\]]*\]\]', ' ', words))
    return [(m.group(1), ' '.join(words[max(0, m.start() - 40):m.end() + 40].split()))
            for m in names.finditer(words) if m.group(1).lower() != title.lower()]


def main():
    data = json.load(open(os.path.join(ROOT, 'build', 'data.json'), encoding='utf-8'))
    items = set(data['items'])
    lock = open(os.path.join(ROOT, 'tools', 'source.lock')).read().strip()
    if data['meta']['git_head'] != lock:
        sys.exit('build/data.json is from %s, not the pinned %s: run tools/extract.py' % (data['meta']['git_head'][:8], lock[:8]))
    trees = {}

    def exists(path, commit):
        if commit not in trees:
            out = subprocess.run(['git', '-C', SRC, 'ls-tree', '-r', '--name-only', commit], capture_output=True, text=True)
            trees[commit] = set(out.stdout.splitlines()) if out.returncode == 0 else None
        files = trees[commit]
        return files is not None and (path in files or any(f.startswith(path.rstrip('/') + '/') for f in files))
    pages = build_xml.collect()
    problems = []
    warnings = []
    vals = value_lookup.values()
    secrets = [s.strip() for s in pages.get('MediaWiki:Mfw-secrets', ('', ''))[1].split('\n') if s.strip()]
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
        for name, args in transclusions(text, 'Data/'):
            if 'Template:' + name not in pages:
                problems.append('%s: {{%s}} is not generated any more' % (title, name))
                continue
            body = pages['Template:' + name][1]
            for arg in args:
                key = arg.split('=', 1)[0].strip() if '=' in arg else None
                if key and '{{{%s|' % key not in body and '{{{%s}}}' % key not in body:
                    problems.append('%s: {{%s}} has no row or parameter "%s" (a note for something that is gone?)'
                                    % (title, name, key))
        for name, context in spoiler_leaks(title, text, secrets):
            problems.append('%s: names the secret "%s" outside a {{Spoiler}} box; link it or move it under the box: "...%s..."'
                            % (title, name, context))
        for m in value_lookup.CALL.finditer(text):
            _, err = value_lookup.lookup(m.group(1))
            if err:
                problems.append('%s: {{Value|%s}}: %s' % (title, m.group(1), err))
        own = re.search(r'\{\{\s*Infobox auto\s*(?:\|([^|{}=]*))?(?=[|}])', text)
        if own:
            item = (own.group(1) or '').strip() or title
            heal = vals.get(item, {}).get('heals', {}).get('1')
            for m in re.finditer(r'\bheal(?:s|ing)?\s+(\{\{Hp\|[^}]*\}\})', text):
                if m.group(1) == heal:
                    warnings.append('%s: "%s" types the item\'s own heal amount; use {{Value|%s|heals}}'
                                    % (title, m.group(0), item))
        for m in re.finditer(r'\{\{\s*Source\s*\|([^|}]+)((?:\|[^|}]*)*)\}\}', text):
            path = m.group(1).strip()
            at = re.search(r'\|\s*at\s*=\s*([0-9a-f]{7,40})', m.group(2))
            commit = at.group(1) if at else lock
            if '...' not in path and not exists(path, commit):
                problems.append('%s: {{Source|%s}} does not exist in the pack at %s' % (title, path, commit[:8]))
    for w in warnings:
        print('warning: ' + w)
    for p in problems:
        print(p)
    print('%d problem%s' % (len(problems), '' if len(problems) == 1 else 's'))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
