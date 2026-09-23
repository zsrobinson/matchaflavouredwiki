#!/usr/bin/env python3
"""Import specific hand-written pages into the running wiki and check how they render.

  tools/preview.py "Pumpkin Empanada" "Food" ...     (titles; Main namespace unless prefixed)
  tools/preview.py --file wiki/pages/Main/Food.wiki  (paths)
  tools/preview.py --check-only "Food"               (no import, just render checks)

For each page it reports: Lua/template errors, red links (pages that don't exist yet), and
missing files. Safe to run from several agents at once (unique temp file, retries on lock).
Screenshot a page with tools/screenshot.sh "Title" out.png
"""
import html
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_xml  # noqa: E402

BASE = 'http://localhost:8080'


def title_from_path(path):
    path = os.path.relpath(os.path.abspath(path), ROOT)
    parts = path.split(os.sep)
    return build_xml.title_of(parts[-2], parts[-1])


def import_titles(titles):
    pages = build_xml.collect()
    chosen = {t: pages[t] for t in titles if t in pages}
    missing = [t for t in titles if t not in pages]
    for t in missing:
        print('!! no file for', t)
    if not chosen:
        return
    from xml.sax.saxutils import escape
    import datetime
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    out = ['<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/" version="0.11" xml:lang="en">',
           '<siteinfo><sitename>Matcha Flavoured Wiki</sitename><namespaces>' +
           ''.join('<namespace key="%d">%s</namespace>' % (v, escape('Matcha Flavoured Wiki' if k == 'Project' else ('' if k == 'Main' else k)))
                   for k, v in build_xml.NS.items()) + '</namespaces></siteinfo>']
    for title, (ns, text, layer) in chosen.items():
        model, fmt = build_xml.model_of(ns, title)
        out.append('<page><title>%s</title><ns>%d</ns><revision><timestamp>%s</timestamp><contributor><username>Preview</username></contributor>'
                   '<model>%s</model><format>%s</format><text xml:space="preserve">%s</text></revision></page>' % (
                       escape(title), build_xml.NS[ns], ts, model, fmt, escape(text)))
    out.append('</mediawiki>')
    name = 'preview-%d.xml' % os.getpid()
    path = os.path.join(ROOT, 'build', name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    for attempt in range(8):
        r = subprocess.run(['docker', 'exec', 'matcha-wiki', 'php', 'maintenance/run.php', 'importDump',
                            '--no-updates', '/build/' + name], capture_output=True, text=True)
        if r.returncode == 0:
            break
        time.sleep(2 + attempt * 2)
    else:
        print('!! import failed:', r.stderr[-500:])
    subprocess.run(['docker', 'exec', '-i', 'matcha-wiki', 'php', 'maintenance/run.php', 'purgeList'],
                   input='\n'.join(chosen), capture_output=True, text=True)
    os.remove(path)


def check(title):
    url = BASE + '/index.php?title=' + urllib.parse.quote(title.replace(' ', '_')) + '&action=render'
    try:
        body = urllib.request.urlopen(url, timeout=60).read().decode('utf-8', 'replace')
    except Exception as e:
        print('== %s: could not render (%s)' % (title, e))
        return
    problems = []
    for pat, label in ((r'class="(?:error|scribunto-error)[^"]*"[^>]*>(.*?)</', 'error'),
                       (r'Template loop detected', 'template loop'),
                       (r'Expansion depth limit', 'expansion depth')):
        for m in re.finditer(pat, body):
            problems.append('%s: %s' % (label, html.unescape(re.sub('<[^>]+>', '', m.group(1) if m.groups() else m.group(0)))[:160]))
    red = sorted(set(html.unescape(m) for m in re.findall(r'class="new" title="([^"]+) \(page does not exist\)"', body)))
    files = [r for r in red if r.startswith('File:')]
    red = [r for r in red if not r.startswith('File:')]
    print('== %s: %d problem(s), %d red link(s), %d missing file(s), %d bytes' % (title, len(problems), len(red), len(files), len(body)))
    for p in problems[:20]:
        print('   !!', p)
    if red:
        print('   red links:', '; '.join(red[:60]))
    if files:
        print('   missing files:', '; '.join(files[:30]))


def main(argv):
    check_only = '--check-only' in argv
    argv = [a for a in argv if a != '--check-only']
    titles = []
    i = 0
    while i < len(argv):
        if argv[i] == '--file':
            titles.append(title_from_path(argv[i + 1]))
            i += 2
        else:
            titles.append(argv[i])
            i += 1
    if not titles:
        print(__doc__)
        return
    if not check_only:
        import_titles(titles)
    for t in titles:
        check(t)


if __name__ == '__main__':
    main(sys.argv[1:])
