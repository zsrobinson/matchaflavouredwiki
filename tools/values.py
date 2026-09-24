#!/usr/bin/env python3
"""{{Value|<item>|<field>}} outside the wiki: the same lookup as Module:Value, from build/values.json
(written by tools/generate.py next to Module:Data/Values).

  tools/values.py "Canned Golden Apples"          every field and format the item has
  tools/values.py --against origin/main           proof for a conversion: every hand-written page
      changed since that commit must read exactly as before once each {{Value}} is replaced by its
      text. Exit 1 on any difference (a typed number that disagreed with the data, or a wrong field).
  tools/values.py --suggest "Title" ...           typed numbers on those pages that equal a value of
      an item the page names, with the {{Value}} call that would produce them (a writer's aid;
      whether the sentence states that item's own value is a judgement the tool can't make)
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALUES_JSON = os.path.join(ROOT, 'build', 'values.json')
CALL = re.compile(r'\{\{\s*Value\s*\|((?:[^{}]|\{\{[^{}]*\}\})*)\}\}')
_VALUES = None


def values():
    global _VALUES
    if _VALUES is None:
        _VALUES = json.load(open(VALUES_JSON, encoding='utf-8'))
    return _VALUES


def parse(inner):
    """The arguments of one {{Value|...}} call: (item, field, effect, station, format)."""
    pos, named = [], {}
    for a in inner.split('|'):
        if '=' in a:
            k, v = a.split('=', 1)
            named[k.strip()] = v.strip()
        else:
            pos.append(a.strip())
    pos += [''] * 2
    return pos[0], pos[1], named.get('effect', ''), named.get('station', ''), named.get('format', ''), \
        set(named) - {'effect', 'station', 'format'}


def lookup(inner):
    """(text, None) for one call, or (None, error) as Module:Value would report it."""
    item, field, effect, station, fmt, extra = parse(inner)
    if extra:
        return None, 'unknown parameter %s' % ', '.join(sorted(extra))
    v = values().get(item)
    if v is None:
        return None, 'no values for the item "%s"' % item
    key = field + (':' + effect if effect else ':' + station if station else '')
    if key not in v:
        return None, '%s has no "%s" (it has: %s)' % (item, key, ', '.join(sorted(v)))
    if 'error' in v[key]:
        return None, v[key]['error']
    text = v[key].get(fmt or '1')
    if text is None:
        return None, 'no format "%s" for %s (formats: %s)' % (fmt, key, ', '.join(sorted(k for k in v[key] if k != '1')))
    return text, None


def expand(text):
    """text with every {{Value}} replaced by its wikitext (a heal stays {{Hp|n}}), and the errors."""
    errors = []

    def sub(m):
        t, err = lookup(m.group(1))
        if err:
            errors.append('{{Value|%s}}: %s' % (m.group(1), err))
            return m.group(0)
        return t
    return CALL.sub(sub, text), errors


def against(ref):
    out = subprocess.run(['git', '-C', ROOT, 'diff', '-z', '--name-only', ref, '--', 'wiki/pages'], capture_output=True, text=True, check=True)
    bad = checked = calls = 0
    for path in filter(None, out.stdout.split('\0')):
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        new = open(full, encoding='utf-8').read()
        n = len(CALL.findall(new))
        if not n or not path.endswith('.wiki') or path.endswith('Template/Value.wiki'):
            continue
        old = subprocess.run(['git', '-C', ROOT, 'show', '%s:%s' % (ref, path)], capture_output=True, text=True)
        checked += 1
        calls += n
        text, errors = expand(new)
        if errors or old.returncode or text != old.stdout:
            bad += 1
            print('DIFFERS %s' % path)
            for e in errors:
                print('    ' + e)
            if not old.returncode:
                import difflib
                for line in difflib.unified_diff(old.stdout.splitlines(), text.splitlines(), 'before', 'after (values filled in)', n=0, lineterm=''):
                    print('    ' + line)
    print('%d pages with %d {{Value}} calls checked against %s: %d differ' % (checked, calls, ref, bad))
    return 1 if bad else 0


def suggest(titles):
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    import build_xml
    pages = build_xml.collect()
    vals = values()
    for title in titles:
        text = pages[title][1]
        names = {title} | {m.strip() for m in re.findall(r'\[\[([^|\]#]+)', text)} | \
            {m.strip() for m in re.findall(r'\{\{(?:ItemLink|Slot|Infobox auto)\|([^|}]+)', text)}
        names = {n[0].upper() + n[1:] for n in names if n}
        found = []
        for n in sorted(names):
            for fld, fmts in vals.get(n, {}).items():
                for fmt, t in fmts.items():
                    if fmt in ('ticks', 'raw', 'secs', 'error') or len(t) < 2 or (fmt != '1' and t == fmts.get('1')):
                        continue
                    for m in re.finditer(re.escape(t) + r'(?!\d|\.\d)', text):
                        if m.start() and (text[m.start() - 1].isdigit() or text[m.start() - 1] == '.'):
                            continue
                        f, e = fld.split(':', 1) if ':' in fld else (fld, '')
                        call = '{{Value|%s|%s%s%s}}' % (n, f, ('|effect=' if f in ('level', 'duration') else '|station=') + e if e else '',
                                                        '' if fmt == '1' else '|format=' + fmt)
                        line = text.count('\n', 0, m.start()) + 1
                        found.append((line, t, call))
        print('== %s' % title)
        for line, t, call in sorted(set(found)):
            print('  line %d: %s  ←  %s' % (line, t, call))


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--against':
        return against(sys.argv[2])
    if len(sys.argv) > 2 and sys.argv[1] == '--suggest':
        return suggest(sys.argv[2:])
    for name in sys.argv[1:]:
        v = values().get(name)
        print(json.dumps(v, ensure_ascii=False, indent=1) if v else 'no values for "%s"' % name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
