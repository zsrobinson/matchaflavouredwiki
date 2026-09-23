#!/usr/bin/env python3
"""Render every page in the running wiki and report problems.

  tools/check_site.py            hand-written pages (wiki/pages) — the ones prose lives in
  tools/check_site.py --all      every page, including generated stubs and data templates

Reports template/Lua errors per page, and red links aggregated by target (most-wanted first),
and missing images. Exit status 1 if any page has errors.
"""
import html
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_xml  # noqa: E402

BASE = 'http://localhost:8080'


def render(title):
    url = BASE + '/index.php?title=' + urllib.parse.quote(title.replace(' ', '_')) + '&action=render'
    try:
        body = urllib.request.urlopen(url, timeout=120).read().decode('utf-8', 'replace')
    except Exception as e:
        return title, ['could not render: %s' % e], [], []
    errs = [html.unescape(re.sub('<[^>]+>', '', m))[:200]
            for m in re.findall(r'class="(?:error|scribunto-error)[^"]*"[^>]*>(.*?)</(?:strong|span|div)>', body)]
    if 'Template loop detected' in body:
        errs.append('template loop')
    red = set(html.unescape(m) for m in re.findall(r'class="new" title="([^"]+) \(page does not exist\)"', body))
    files = [r for r in red if r.startswith('File:')]
    red = [r for r in red if not r.startswith('File:')]
    return title, errs, red, files


def main():
    pages = build_xml.collect()
    if '--all' in sys.argv:
        titles = sorted(pages)
    else:
        titles = sorted(t for t, p in pages.items() if p[2] == 'pages' and p[0] in ('Main', 'Project', 'Template'))
    with ThreadPoolExecutor(8) as ex:
        results = list(ex.map(render, titles))
    bad = 0
    wanted = Counter()
    wanted_from = defaultdict(list)
    missing_files = Counter()
    for title, errs, red, files in results:
        if errs:
            bad += 1
            print('ERROR %s' % title)
            for e in errs[:5]:
                print('    ', e)
        for r in red:
            wanted[r] += 1
            if len(wanted_from[r]) < 4:
                wanted_from[r].append(title)
        for f in files:
            missing_files[f] += 1
    print('\n%d pages checked, %d with errors' % (len(results), bad))
    print('%d distinct red-link targets' % len(wanted))
    for t, n in wanted.most_common(80):
        print('  %4d  %s   (e.g. %s)' % (n, t, ', '.join(wanted_from[t])))
    if missing_files:
        print('%d missing files' % len(missing_files))
        for t, n in missing_files.most_common(30):
            print('  %4d  %s' % (n, t))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
