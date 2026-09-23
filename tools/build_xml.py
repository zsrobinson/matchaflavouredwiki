#!/usr/bin/env python3
"""Pack wiki/pages (hand-written) and wiki/generated (from tools/generate.py)
into build/import.xml, a MediaWiki export dump for maintenance/importDump.php.

File layout: wiki/<pages|generated>/<Namespace>/<name><ext>
  - <Namespace> is a folder: Main, Template, Module, MediaWiki, Category, Project, Help, File
  - '/' in a title is written as '%2F' in the file name
  - Module pages end in .lua; titles already ending in .css/.js/.json keep that; all else .wiki
A hand-written page always wins over a generated page with the same title.
"""
import datetime
import os
import sys
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = {'Main': 0, 'Project': 4, 'File': 6, 'MediaWiki': 8, 'Template': 10, 'Help': 12,
      'Category': 14, 'Module': 828}
PREFIX = {'Main': '', 'Project': 'Matcha Flavoured Wiki:'}


def title_of(ns, fname):
    name = fname
    for ext in ('.wiki', '.lua'):
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    name = name.replace('%2F', '/').replace('%3A', ':')
    prefix = PREFIX.get(ns, ns + ':')
    return prefix + name


def model_of(ns, title):
    if ns == 'Module' and not title.endswith('/doc'):
        return 'Scribunto', 'text/plain'
    if title.endswith('.css'):
        return 'css', 'text/css'
    if title.endswith('.js'):
        return 'javascript', 'text/javascript'
    if title.endswith('.json'):
        return 'json', 'application/json'
    return 'wikitext', 'text/x-wiki'


def collect():
    # wiki/generated is swapped atomically by tools/generate.py; retry if we catch it mid-swap
    import time
    for attempt in range(20):
        try:
            return _collect()
        except FileNotFoundError:
            time.sleep(1)
    return _collect()


def _collect():
    pages = {}
    for layer in ('generated', 'pages'):  # later layer overrides
        base = os.path.join(ROOT, 'wiki', layer)
        for ns in sorted(os.listdir(base)) if os.path.isdir(base) else []:
            d = os.path.join(base, ns)
            if not os.path.isdir(d) or ns not in NS:
                continue
            for fname in sorted(os.listdir(d)):
                if fname.startswith('.'):
                    continue
                with open(os.path.join(d, fname), encoding='utf-8') as f:
                    text = f.read()
                title = title_of(ns, fname)
                pages[title] = (ns, text, layer)
    return pages


def main():
    import hashlib
    pages = collect()
    # --changed: only pages whose text differs from the last successful import (fast iteration)
    hashes_path = os.path.join(ROOT, 'build', 'import_hashes.json')
    try:
        import json
        old = json.load(open(hashes_path))
    except Exception:
        old = {}
    new = {t: hashlib.sha1(p[1].encode()).hexdigest() for t, p in pages.items()}
    if '--changed' in sys.argv:
        pages = {t: p for t, p in pages.items() if old.get(t) != new[t]}
    import json
    with open(hashes_path + '.pending', 'w') as f:
        json.dump(new, f)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = ['<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11" xml:lang="en">',
           '<siteinfo><sitename>Matcha Flavoured Wiki</sitename><dbname>matchawiki</dbname><case>first-letter</case>',
           '<namespaces>' + ''.join('<namespace key="%d" case="first-letter">%s</namespace>' % (
               v, escape('Matcha Flavoured Wiki' if k == 'Project' else ('' if k == 'Main' else k))) for k, v in NS.items()) +
           '</namespaces></siteinfo>']
    for title, (ns, text, layer) in sorted(pages.items()):
        model, fmt = model_of(ns, title)
        out.append('<page><title>%s</title><ns>%d</ns><revision><timestamp>%s</timestamp>'
                   '<contributor><username>MatchaBot</username></contributor>'
                   '<comment>%s</comment><model>%s</model><format>%s</format>'
                   '<text xml:space="preserve">%s</text></revision></page>' % (
                       escape(title), NS[ns], ts, 'Sync from repository (%s)' % layer, model, fmt, escape(text)))
    out.append('</mediawiki>')
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    with open(os.path.join(ROOT, 'build', 'import.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    with open(os.path.join(ROOT, 'build', 'titles.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(sorted(pages)))
    print('pages:', len(pages), '(hand %d, generated %d)' % (
        sum(1 for p in pages.values() if p[2] == 'pages'), sum(1 for p in pages.values() if p[2] == 'generated')),
        file=sys.stderr)


if __name__ == '__main__':
    main()
