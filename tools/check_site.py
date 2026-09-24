#!/usr/bin/env python3
"""Render every page in the running wiki and report problems.

  tools/check_site.py            hand-written pages (wiki/pages) — the ones prose lives in
  tools/check_site.py --all      every page, including generated stubs and data templates

Reports template/Lua errors per page, and red links aggregated by target (most-wanted first),
and missing images. Exit status 1 if any page has errors. A secret item's name that a reader would see
with spoilers hidden (the default; site/Spoilers.php) is an error too.
"""
import html
from html.parser import HTMLParser
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
SECRETS = None  # regex of the secret items' names (MediaWiki:Mfw-secrets), set by main()
REDIRECTS = set()


class ShownText(HTMLParser):
    """The text a reader sees with spoilers hidden: not in a hidden spoiler (site/Spoilers.php), a slot's
    hidden tooltip (.mf-tip), a script or a style. External links are left out too: a reference's
    source file name (cooking_recipes/gnocchi_recipe.json) is not a spoiler."""
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}
    HIDING = re.compile(r'(?:^|\s)(?:mfw-spoiler|mfw-spoiler-body|mf-tip)(?:\s|$)')

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.text = [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        cls = dict(attrs).get('class') or ''
        hidden = tag in ('script', 'style') or bool(self.HIDING.search(cls)) or (tag == 'a' and 'external' in cls.split())
        self.stack.append((tag, hidden or bool(self.stack and self.stack[-1][1])))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if not (self.stack and self.stack[-1][1]):
            self.text.append(data)


def spoiler_leaks(title):
    """The page as readers get it (action=render skips site/Spoilers.php's hook), its content only."""
    if not SECRETS or title in REDIRECTS:
        return []
    url = BASE + '/w/' + urllib.parse.quote(title.replace(' ', '_'))
    try:
        body = urllib.request.urlopen(url, timeout=120).read().decode('utf-8', 'replace')
    except Exception as e:
        return ['could not view: %s' % e]
    start, end = body.find('id="mw-content-text"'), body.find('class="printfooter"')
    p = ShownText()
    p.feed(body[start:end] if start >= 0 and end > start else body)
    text = ' '.join(' '.join(p.text).split())
    return ['names the secret "%s" with spoilers hidden: "...%s..."' % (m.group(1), text[max(0, m.start() - 50):m.end() + 30])
            for m in SECRETS.finditer(text) if m.group(1).lower() != title.lower()][:3]


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
    # past the 2 MB include limit MediaWiki stops expanding templates and prints a bare link instead
    # (category listings and template docs link templates by name on purpose)
    unexpanded = [] if title.startswith(('Template:', 'Category:')) else re.findall(r'<a [^>]*title="(Template:[^"]+)"[^>]*>Template:', body)
    for m in unexpanded[:3]:
        errs.append('template not expanded (include size limit?): ' + html.unescape(m))
    # wikitext that failed to parse shows up as literal brackets (e.g. an image inside a link label)
    visible = re.sub(r'<(script|style|code|pre)[^>]*>.*?</\1>', '', body, flags=re.S)
    for m in re.findall(r'\[\[[^\]<]{1,80}\]\]|\{\{[^}<]{1,80}\}\}', re.sub(r'<[^>]+>', '', visible))[:3]:
        errs.append('unparsed wikitext: ' + m)
    red = set(html.unescape(m) for m in re.findall(r'class="new" title="([^"]+) \(page does not exist\)"', body))
    files = [r for r in red if r.startswith('File:')]
    # a missing image links to Special:Upload instead of carrying the "(page does not exist)" title
    files += sorted(set('File:' + html.unescape(urllib.parse.unquote(m)).replace('_', ' ')
                        for m in re.findall(r'wpDestFile=([^"&]+)', body)) - set(files))
    red = [r for r in red if not r.startswith('File:')]
    errs += spoiler_leaks(title)
    return title, errs, red, files


def main():
    global SECRETS
    pages = build_xml.collect()
    REDIRECTS.update(t for t, p in pages.items() if re.match(r'\s*#REDIRECT', p[1], re.I))
    names = [s.strip() for s in pages.get('MediaWiki:Mfw-secrets', ('', ''))[1].split('\n') if s.strip()]
    if names:
        SECRETS = re.compile(r'(?<!\w)(%s)(?:e?s)?(?!\w)' % '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)), re.I)
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
