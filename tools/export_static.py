#!/usr/bin/env python3
"""Export the running wiki to a fully static site in dist/ (deployable to any static host).

  tools/export_static.py [--out dist] [--base http://localhost:8080]

Every page (all namespaces in the repo, plus categories) is rendered by MediaWiki once and
saved as dist/w/<Title>/index.html, so URLs stay the same as the live wiki (/w/Page_title).
MediaWiki's dynamic JavaScript is replaced by one small static script (_static/site.js) that
provides the few behaviours the pages need: animated recipe slots, the light/dark toggle,
collapsible and sortable tables, and client-side title search (search.json). Stylesheets
served by load.php are fetched once and saved as static files. Redirect pages become
meta-refresh stubs. Links to things a static site cannot do (editing, history, special
pages) are removed.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build_xml  # noqa: E402
import seo  # noqa: E402


def fetch(url, binary=False):
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    return data if binary else data.decode('utf-8', 'replace')


def url_title(title):
    return title.replace(' ', '_')


def page_path(out, title):
    # /w/Title -> w/Title.html: Cloudflare (html_handling), GitHub Pages and Netlify all serve
    # extensionless URLs from .html files without a redirect.
    return os.path.join(out, 'w', url_title(title) + '.html')


def href_for(title):
    return '/w/' + urllib.parse.quote(url_title(title), safe=":/'(),!*$@;=+&-._~")


class Exporter:
    def __init__(self, base, out):
        self.base = base.rstrip('/')
        self.out = out
        self.assets = {}  # load.php url -> static path
        self.case_redirects = {}  # title -> target, for redirects that only change capitalisation
        self.redirects = {}  # 'Old_title' -> '/w/Target#anchor' (served as 301 by the Worker)
        self.indexed = {}  # title -> lastmod, for the sitemap
        self.dates = seo.git_dates()

    # --- stylesheets from load.php -------------------------------------------------
    def static_css(self, href):
        href = html.unescape(href)
        if href in self.assets:
            return self.assets[href]
        css = fetch(self.base + href if href.startswith('/') else href)
        # pull in images referenced by the stylesheet
        def repl(m):
            u = m.group(1).strip('\'"')
            if u.startswith('data:') or u.startswith('http'):
                return m.group(0)
            if not u.startswith('/'):
                return m.group(0)
            self.copy_url(u.split('?')[0])
            return 'url("%s")' % u.split('?')[0]
        css = re.sub(r'url\(([^)]+)\)', repl, css)
        name = '/_rl/%s.css' % hashlib.sha1(href.encode()).hexdigest()[:16]
        os.makedirs(os.path.join(self.out, '_rl'), exist_ok=True)
        with open(os.path.join(self.out, name.lstrip('/')), 'w', encoding='utf-8') as f:
            f.write(css)
        self.assets[href] = name
        return name

    def copy_url(self, path):
        """Mirror a static file (skin images etc.) from the wiki into dist."""
        dest = os.path.join(self.out, urllib.parse.unquote(path).lstrip('/'))
        if os.path.exists(dest):
            return
        try:
            data = fetch(self.base + path, binary=True)
        except Exception:
            return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as f:
            f.write(data)

    # --- pages ----------------------------------------------------------------------
    def rewrite(self, doc):
        # stylesheets: load.php -> static file
        doc = re.sub(r'<link rel="stylesheet" href="(/load\.php\?[^"]+)"',
                     lambda m: '<link rel="stylesheet" href="%s"' % self.static_css(m.group(1)), doc)
        # drop all MediaWiki scripts (the startup module loads more code dynamically)
        doc = re.sub(r'<script[^>]*>.*?</script>', lambda m: m.group(0) if 'mfw-theme' in m.group(0) else '', doc, flags=re.S)
        doc = re.sub(r'<script[^>]*src="[^"]*"[^>]*></script>', '', doc)
        doc = doc.replace('</head>', HEAD_EXTRA + '</head>', 1)
        doc = re.sub(r'(<body[^>]*>)', r'\1' + THEME_BOOT, doc, count=1)
        doc = doc.replace('</body>', '<script src="/_static/site.js"></script>\n</body>')
        # Pagefind: index only the article body; title, categories and item icon as metadata
        doc = doc.replace('<div id="mw-content-text"', '<div id="mw-content-text" data-pagefind-body', 1)
        doc = re.sub(r'<h1 id="firstHeading"', '<h1 id="firstHeading" data-pagefind-meta="title"', doc, count=1)
        doc = re.sub(r'<table class="navbox', '<table data-pagefind-ignore class="navbox', doc)
        doc = re.sub(r'<div id="toc"', '<div data-pagefind-ignore id="toc"', doc)
        for pat in (r'<div class="printfooter"', r'<ol class="references"', r'<div class="mcui', r'<span class="mcui'):
            doc = re.sub(pat, lambda m: m.group(0).replace(' ', ' data-pagefind-ignore ', 1), doc)
        doc = re.sub(r'(<div id="catlinks".*?</div></div>)', lambda m: re.sub(r'<a href="/w/Category:[^"]*" title="Category:[^"]*">([^<]*)</a>',
                     lambda a: a.group(0).replace('<a ', '<a data-pagefind-filter="category" ', 1), m.group(1)), doc, flags=re.S)
        # item icon as the search result image: the first inventory slot image in the infobox
        doc = re.sub(r'(<div class="infobox-invimages">.*?<img )', r'\1data-pagefind-meta="image[src]" ', doc, count=1, flags=re.S)
        doc = doc.replace('class="client-nojs', 'class="client-js')
        # red links: keep the styling, remove the edit link
        doc = re.sub(r'<a href="[^"]*action=edit[^"]*redlink=1"([^>]*)>(.*?)</a>', r'<span class="new"\1>\2</span>', doc, flags=re.S)
        # legacy Vector forces a 1120px desktop viewport on phones; the vendored minecraft.wiki CSS
        # already has narrow-screen rules (sidebar below the content, scrolling tables), so let it apply
        doc = doc.replace('<meta name="viewport" content="width=1120">',
                          '<meta name="viewport" content="width=device-width, initial-scale=1">', 1)
        # absolute links back to the dev server -> site-relative
        doc = doc.replace(self.base + '/', '/')
        # MediaWiki endpoints that don't exist on the static site: API discovery, the recent-changes
        # feed, and the print footer's permanent link (point it at the page's public URL instead)
        doc = re.sub(r'<link rel="(?:EditURI|alternate)" type="application/(?:rsd|atom)\+xml"[^>]*>\n?', '', doc)
        doc = re.sub(r'<a dir="ltr" href="/index\.php\?title=([^"&]+)&amp;oldid=\d+">[^<]*</a>',
                     lambda m: '<a dir="ltr" href="/w/%s">%s/w/%s</a>' % (m.group(1), seo.SITE, m.group(1)), doc)
        # links to capitalisation redirects go straight to the article (case-insensitive file
        # systems can't hold both "Mud_kiln.html" and "Mud_Kiln.html")
        def fix(m):
            t = urllib.parse.unquote(m.group(1)).replace('_', ' ')
            tgt = self.case_redirects.get(t)
            return 'href="%s%s"' % (href_for(tgt), m.group(2) or '') if tgt else m.group(0)
        doc = re.sub(r'href="/w/([^"#?]+)(#[^"]*)?"', fix, doc)
        doc = doc.replace('href="/w/Matcha_Flavoured_Wiki"', 'href="/"')  # the main page is served at /
        # links a static site can't serve
        doc = re.sub(r'<li id="(?:t-|ca-(?!mfw-)|pt-|n-recentchanges|n-randompage)[^"]*"[^>]*>.*?</li>', '', doc, flags=re.S)
        doc = re.sub(r'href="/index\.php\?title=Special:Search[^"]*"', 'href="/search/"', doc)
        doc = re.sub(r'<a href="/w/Special:[^"]*"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        doc = re.sub(r'<form action="/index\.php" id="searchform".*?</form>',
                     '<pagefind-searchbox id="mfw-searchbox" instance="header" placeholder="Search Matcha Flavoured Wiki" max-results="8" '
                     'show-sub-results shortcut="/"></pagefind-searchbox>', doc, flags=re.S)
        doc = re.sub(r'<nav id="p-tb".*?</nav>', '', doc, flags=re.S)
        doc = re.sub(r'<ul id="footer-icons".*?</ul>', '', doc, flags=re.S)
        doc = re.sub(r'<li id="footer-info-lastmod".*?</li>', '', doc, flags=re.S)
        doc = re.sub(r'<div id="footer-places">.*?</div>|<ul id="footer-places">.*?</ul>', '', doc, flags=re.S)
        # image description pages are not exported: unlink files
        doc = re.sub(r'<a href="/w/File:[^"]*" class="mw-file-description"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        return doc

    def export_page(self, title, text, ns='Main'):
        if title in self.case_redirects:
            return 'case'  # served by link rewriting and the 404 fallback, not a file
        dest = page_path(self.out, title)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)(#[^\]|]*)?', text, re.I)
        if m:
            # real 301 from the Worker (src/redirects.json), no stub file
            self.redirects[url_title(title)] = href_for(m.group(1).strip()) + (m.group(2) or '').replace(' ', '_')
            return 'redirect'
        doc = self.rewrite(fetch(self.base + '/w/' + urllib.parse.quote(url_title(title))))
        src, layer = seo.source_file(title, ns)
        is_main = title == 'Matcha Flavoured Wiki'
        info = {'layer': layer, 'lastmod': self.dates.get(src), 'categories': seo.categories(doc),
                'image': seo.infobox_image(doc), 'is_main': is_main,
                # generated pages (vanilla items, data-only pages) are thin: keep them out of the index
                'noindex': layer == 'generated' and not is_main}
        doc = seo.apply(doc, title, info)
        if not info['noindex']:
            self.indexed[title] = info['lastmod']
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(doc)
        return 'page'


HEAD_EXTRA = ('<link rel="stylesheet" href="/pagefind/pagefind-component-ui.css">'
              '<link rel="stylesheet" href="/_static/site.css">'
              '<script type="module" src="/pagefind/pagefind-component-ui.js"></script>')
THEME_BOOT = ''  # the head script from site/theme-boot.js is already in the page (added by LocalSettings.php)

SITE_CSS = r"""/* Pagefind Component UI, styled to sit in minecraft.wiki's search slot and palette. */
#p-search pagefind-searchbox, #mfw-searchbox {
  --pf-font: inherit;
  --pf-border-radius: 0;
  --pf-input-height: 28px;
  --pf-input-font-size: 13px;
  --pf-searchbox-max-width: 100%;
  --pf-background: #fff;
  --pf-border: #888;
  --pf-border-focus: #6BA41E;
  --pf-text: #202122;
  --pf-text-secondary: #54595d;
  --pf-text-muted: #72777d;
  --pf-hover: #eaf3dd;
  --pf-mark: #3d7a0e;
  --pf-dropdown-z-index: 1000;
  display: block;
  width: 100%;
}
#p-search { width: 20vw; min-width: 16em; max-width: 26em; }
@media screen and (max-width: 720px) {
  #p-search { width: auto; min-width: 0; max-width: none; float: none; margin: 0.5em 1em 0 1em; }
  #p-search pagefind-searchbox { width: 100%; }
}
#mfw-search-page {
  --pf-font: inherit;
  --pf-border-radius: 2px;
  --pf-border-focus: #6BA41E;
  --pf-mark: #3d7a0e;
  --pf-image-width: 48px;
  --pf-image-height: 48px;
}
#mfw-search-page .mfw-search-layout { display: grid; grid-template-columns: 14em minmax(0, 1fr); gap: 1.5em; margin-top: 1em; }
#mfw-search-page .mfw-search-layout > div { min-width: 0; overflow: hidden; }
#mfw-search-page mark, #mfw-searchbox mark { font-weight: bold; background: none; }
@media (max-width: 800px) { #mfw-search-page .mfw-search-layout { grid-template-columns: 1fr; } }
#mfw-search-page img, #mfw-searchbox img { image-rendering: pixelated; }
body.wgl-theme-dark #p-search pagefind-searchbox, body.wgl-theme-dark #mfw-searchbox, body.wgl-theme-dark #mfw-search-page {
  --pf-background: #1f1f1f;
  --pf-border: #555;
  --pf-text: #e6e6e6;
  --pf-text-secondary: #c0c0c0;
  --pf-text-muted: #9a9a9a;
  --pf-hover: #2f3a24;
  --pf-mark: #9ed36a;
}
"""

SITE_JS = r"""// Static replacement for the MediaWiki scripts the wiki uses.
(function () {
  'use strict';
  // Animated inventory slots (cycling ingredients), as Gadget-animatedIcons does.
  setInterval(function () {
    if (document.hidden) return;
    document.querySelectorAll('.animated').forEach(function (el) {
      if (el.classList.contains('animated-paused')) return;
      var cur = el.querySelector(':scope > .animated-active');
      var next = (cur && cur.nextElementSibling) || el.firstElementChild;
      if (cur) cur.classList.remove('animated-active');
      if (next) next.classList.add('animated-active');
    });
  }, 2000);

  // Collapsible tables (mw-collapsible).
  document.querySelectorAll('table.mw-collapsible').forEach(function (tbl) {
    var head = tbl.querySelector('tr');
    if (!head) return;
    var cell = head.lastElementChild;
    var btn = document.createElement('span');
    btn.className = 'mw-collapsible-toggle';
    btn.style.cssText = 'float:right;cursor:pointer;font-weight:normal;font-size:0.9em';
    function set(collapsed) {
      Array.prototype.slice.call(tbl.rows, 1).forEach(function (r) { r.style.display = collapsed ? 'none' : ''; });
      btn.textContent = collapsed ? '[show]' : '[hide]';
    }
    btn.addEventListener('click', function () { set(btn.textContent === '[show]' ? false : true); });
    cell.appendChild(btn);
    set(tbl.classList.contains('mw-collapsed'));
  });

  // Sortable tables (wikitable sortable).
  document.querySelectorAll('table.sortable').forEach(function (tbl) {
    var head = tbl.querySelector('tr');
    if (!head) return;
    Array.prototype.forEach.call(head.cells, function (th, idx) {
      th.style.cursor = 'pointer';
      th.addEventListener('click', function () {
        var rows = Array.prototype.slice.call(tbl.rows, 1).filter(function (r) { return r.cells.length > idx; });
        var dir = th.dataset.dir === 'asc' ? -1 : 1;
        th.dataset.dir = dir === 1 ? 'asc' : 'desc';
        function key(r) {
          var c = r.cells[idx];
          var v = c.getAttribute('data-sort-value') || c.textContent.trim();
          var n = parseFloat(v.replace(/[^0-9.\-]/g, ''));
          return isNaN(n) || /[a-z]/i.test(v.replace(/^[0-9.\-\s%]+/, '')) && isNaN(parseFloat(v)) ? v.toLowerCase() : n;
        }
        rows.sort(function (a, b) {
          var x = key(a), y = key(b);
          return (x > y ? 1 : x < y ? -1 : 0) * dir;
        });
        var body = rows.length ? rows[0].parentNode : tbl.tBodies[0];
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });

  // Search page: prefill from ?q= so the header searchbox's "see all results" lands here.
  var q = new URLSearchParams(location.search).get('q');
  if (q && document.getElementById('mfw-search-page')) {
    customElements.whenDefined('pagefind-input').then(function () {
      var input = document.querySelector('#mfw-search-page pagefind-input input');
      if (input) { input.value = q; input.dispatchEvent(new Event('input', { bubbles: true })); }
    });
  }
})();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    ap.add_argument('--base', default='http://localhost:8080')
    ap.add_argument('--jobs', type=int, default=8)
    args = ap.parse_args()
    out = args.out
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    ex = Exporter(args.base, out)

    pages = build_xml.collect()
    exportable = {t: p for t, p in pages.items() if p[0] in ('Main', 'Category', 'Project', 'Help')}
    for t, p in exportable.items():
        m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)\]\]', p[1], re.I)
        if m and m.group(1).strip().lower() == t.lower() and m.group(1).strip() != t:
            ex.case_redirects[t] = m.group(1).strip()
    # MediaWiki needs each stylesheet URL fetched once before threads race on it
    first = next(iter(sorted(exportable)))
    ex.export_page('Matcha Flavoured Wiki', exportable.get('Matcha Flavoured Wiki', ('Main', '', ''))[1])

    done = {'page': 0, 'redirect': 0, 'error': 0, 'case': 0}

    def job(item):
        title, (ns, text, layer) = item
        try:
            return ex.export_page(title, text, ns)
        except Exception as e:
            print('!! %s: %s' % (title, e), file=sys.stderr)
            return 'error'
    with ThreadPoolExecutor(args.jobs) as pool:
        for r in pool.map(job, sorted(exportable.items())):
            done[r] += 1

    if done['error']:
        raise RuntimeError('Static export failed for %d pages; refusing to publish a partial site' % done['error'])

    # site furniture
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, '_static', 'site.js'), 'w') as f:
        # the same shell and tooltip scripts the live wiki runs as gadgets, then the static-only behaviours
        for gadget in ('Gadget-mfwShell.js', 'Gadget-mfwTooltip.js'):
            f.write(open(os.path.join(ROOT, 'wiki', 'pages', 'MediaWiki', gadget), encoding='utf-8').read())
            f.write('\n')
        f.write(SITE_JS)
    with open(os.path.join(out, '_static', 'site.css'), 'w') as f:
        f.write(SITE_CSS)
    for d in ('assets', 'images'):
        src = os.path.join(ROOT, 'site', d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(out, d), dirs_exist_ok=True)
    titles = sorted(t for t, p in exportable.items() if not re.match(r'\s*#REDIRECT', p[1], re.I))
    # search.json: canonical titles, used by the 404 page's case-insensitive lookup
    with open(os.path.join(out, 'search.json'), 'w', encoding='utf-8') as f:
        json.dump(titles + sorted(t for t, p in exportable.items() if re.match(r'\s*#REDIRECT', p[1], re.I) and t not in ex.case_redirects), f)
    # search page and root index, built from the main page's skin
    main_html = open(page_path(out, 'Matcha Flavoured Wiki'), encoding='utf-8').read()
    search_body = ('<div id="mfw-search-page"><pagefind-input autofocus placeholder="Search Matcha Flavoured Wiki"></pagefind-input>'
                   '<div class="mfw-search-layout"><div><pagefind-filter-pane></pagefind-filter-pane></div>'
                   '<div><pagefind-summary></pagefind-summary><pagefind-results show-images show-sub-results></pagefind-results></div></div></div>')
    search = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                    lambda m: '<div id="mw-content-text">' + search_body + m.group(2), main_html, flags=re.S)
    search = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Search results</h1>', search, flags=re.S)
    search = re.sub(r'<title>.*?</title>', '<title>Search - Matcha Flavoured Wiki</title>', search)
    search = re.sub(r'<div id="catlinks".*?</div></div>', '', search, flags=re.S)
    search = seo.utility_page(search, 'Search results')
    os.makedirs(os.path.join(out, 'search'), exist_ok=True)
    open(os.path.join(out, 'search', 'index.html'), 'w', encoding='utf-8').write(search)
    root_redirect = ('<!doctype html><meta charset="utf-8"><title>Matcha Flavoured Wiki</title>'
                     '<meta http-equiv="refresh" content="0; url=/w/Matcha_Flavoured_Wiki">'
                     '<a href="/w/Matcha_Flavoured_Wiki">Matcha Flavoured Wiki</a>')
    # the main page is served at / (its canonical URL); /w/Matcha_Flavoured_Wiki stays as an alias
    shutil.copy(page_path(out, 'Matcha Flavoured Wiki'), os.path.join(out, 'index.html'))
    # 404 page: the main page's shell with a not-found message and a case-insensitive redirect
    nf = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                lambda m: '<div id="mw-content-text"><p>There is no page with this title. Try the search box above.</p>' + m.group(2),
                main_html, flags=re.S)
    nf = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Page not found</h1>', nf, flags=re.S)
    nf = nf.replace('</head>', '<script>(function(){var m=location.pathname.match(/^\\/w\\/(.+)$/);if(!m)return;'
                    'fetch("/search.json").then(function(r){return r.json()}).then(function(ts){'
                    'var want=decodeURIComponent(m[1]).replace(/_/g," ").toLowerCase();'
                    'for(var i=0;i<ts.length;i++){if(ts[i].toLowerCase()===want){location.replace("/w/"+encodeURIComponent(ts[i].replace(/ /g,"_")));return}}})})();</script></head>', 1)
    nf = seo.utility_page(nf, 'Page not found')
    open(os.path.join(out, '404.html'), 'w', encoding='utf-8').write(nf)
    # host hints: Netlify/Cloudflare Pages redirects, and disable Jekyll on GitHub Pages
    ex.redirects['Main_Page'] = '/'
    seo.write_site_files(out, ex.indexed, ex.redirects, titles)
    open(os.path.join(out, '.nojekyll'), 'w').close()
    # full-text search index (Pagefind); the component UI is served from /pagefind/
    import subprocess
    subprocess.run(['npx', '-y', 'pagefind@1.5.2', '--site', out, '--quiet'], check=True)
    print('exported %(page)d pages, %(redirect)d redirects, %(error)d errors -> ' % done + out)


if __name__ == '__main__':
    main()
