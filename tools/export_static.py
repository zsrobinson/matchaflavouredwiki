#!/usr/bin/env python3
"""Export the running wiki to a fully static site in dist/ (deployable to any static host).

  tools/export_static.py [--out dist] [--base http://localhost:8080]

Every page (all namespaces in the repo, plus categories) is rendered by MediaWiki once and
saved as dist/w/<Title>/index.html, so URLs stay the same as the live wiki (/w/Page_title).
MediaWiki's dynamic JavaScript is replaced by one small static script (_static/site.js) that
provides the few behaviours the pages need: animated recipe slots, the light/dark toggle,
collapsible and sortable tables, and search (search_index.py, site/search.js). Stylesheets
served by load.php are fetched once and saved as static files. Redirect pages become
meta-refresh stubs. Links to things a static site cannot do (editing, history, special
pages) are removed.
"""
import argparse
import datetime
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
import fingerprint  # noqa: E402
import search_index  # noqa: E402
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
        self.search = {}  # title -> the title search's row (search_index.write)

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
        doc = doc.replace('class="client-nojs', 'class="client-js')
        # CI builds serve pages from the parser cache, which stamps each one with a timestamp; with
        # it gone (and the limit report off in LocalSettings.php) an unchanged page exports identically
        doc = re.sub(r'<!-- Saved in parser cache with key [^>]*-->\n?', '', doc)
        # red links: keep the styling, remove the edit link
        doc = re.sub(r'<a href="[^"]*action=edit[^"]*redlink=1"([^>]*)>(.*?)</a>', r'<span class="new"\1>\2</span>', doc, flags=re.S)
        # legacy Vector forces a 1120px desktop viewport on phones; give them the device width, so they
        # get the mobile layout at the end of MediaWiki:Vector.css
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
        # MediaWiki's own search box, styled by minecraft.wiki's skin; site/search.js adds the suggestions.
        # Without the script it submits to the search page. The data paths get ?v= from fingerprint.py.
        doc = re.sub(r'<form action="/index\.php" id="searchform".*?</form>',
                     '<form action="/search/" id="searchform" class="vector-search-box-form" data-titles="/_static/search-titles.json" '
                     'data-pagefind="/pagefind/pagefind.js"><div id="simpleSearch" class="vector-search-box-inner">'
                     '<input class="vector-search-box-input" type="search" name="q" placeholder="Search Matcha Flavoured Wiki" '
                     'aria-label="Search Matcha Flavoured Wiki" autocapitalize="sentences" autocomplete="off" spellcheck="false" '
                     'title="Search Matcha Flavoured Wiki [/]" id="searchInput">'
                     '<input id="searchButton" class="searchButton" type="submit" title="Search the pages for this text" value="Search">'
                     '</div></form>', doc, flags=re.S)
        doc = re.sub(r'<nav id="p-tb".*?</nav>', '', doc, flags=re.S)
        doc = re.sub(r'<li id="footer-info-lastmod".*?</li>', '', doc, flags=re.S)
        # the footer's last-edit date, from git (site/GitLinks.php leaves a link to the history)
        def lastmod(m):
            date = self.dates.get(html.unescape(m.group(1)))
            if not date:
                return '<span class="mfw-lastmod">%s</span>' % m.group(2)
            d = datetime.date.fromisoformat(date[:10])
            return '<span class="mfw-lastmod">%d %s %d</span>' % (d.day, d.strftime('%B'), d.year)
        doc = re.sub(r'<span class="mfw-lastmod" data-src="([^"]*)">([^<]*)</span>', lambda m: lastmod(m), doc)
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
        # search: the page's picture (Pagefind's result image too), and its row in the title search
        image = search_index.thumbnail(self.out, search_index.page_image(doc, title), os.path.join(ROOT, 'site', 'images'))
        if image:
            doc = re.sub(r'(<h1 id="firstHeading".*?</h1>)', lambda m: m.group(1) + '<span hidden data-pagefind-meta="image[data-src]" data-src="%s"></span>' % html.escape(image), doc, count=1, flags=re.S)
        if ns == 'Category':
            # category pages are lists of links: they crowd out the articles in full-text results
            # (the title search still finds them)
            doc = doc.replace(' data-pagefind-body', '', 1)
        self.search[title] = {'url': '/' if is_main else href_for(title), 'image': image,
                              'desc': search_index.short_description(doc),
                              'kind': {'Category': 'category', 'Project': 'project'}.get(ns, 'generated' if layer == 'generated' else 'article'),
                              'links': search_index.link_targets(doc)}
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


HEAD_EXTRA = '<link rel="stylesheet" href="/_static/site.css">'
# only the search page loads Pagefind's component UI (175 kB); the header box uses pagefind.js directly
SEARCH_HEAD = ('<link rel="stylesheet" href="/pagefind/pagefind-component-ui.css">'
               '<script type="module" src="/pagefind/pagefind-component-ui.js"></script>')
THEME_BOOT = ''  # the head script from site/theme-boot.js is already in the page (added by LocalSettings.php)

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
        f.write(open(os.path.join(ROOT, 'site', 'search.js'), encoding='utf-8').read())
    shutil.copy(os.path.join(ROOT, 'site', 'search.css'), os.path.join(out, '_static', 'site.css'))
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
    # pages whose titles match (site/search.js) above Pagefind's full-text results
    search_body = ('<div id="mfw-search-page"><pagefind-input autofocus placeholder="Search Matcha Flavoured Wiki"></pagefind-input>'
                   '<div class="mfw-search-layout"><div><pagefind-filter-pane></pagefind-filter-pane></div>'
                   '<div><div id="mfw-title-matches"></div><pagefind-summary></pagefind-summary>'
                   '<pagefind-results show-images show-sub-results></pagefind-results></div></div></div>')
    search = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                    lambda m: '<div id="mw-content-text">' + search_body + m.group(2), main_html, flags=re.S)
    search = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Search results</h1>', search, flags=re.S)
    search = re.sub(r'<title>.*?</title>', '<title>Search - Matcha Flavoured Wiki</title>', search)
    search = re.sub(r'<div id="catlinks".*?</div></div>', '', search, flags=re.S)
    search = seo.utility_page(search, 'Search results').replace('</head>', SEARCH_HEAD + '</head>', 1)
    os.makedirs(os.path.join(out, 'search'), exist_ok=True)
    open(os.path.join(out, 'search', 'index.html'), 'w', encoding='utf-8').write(search)
    root_redirect = ('<!doctype html><meta charset="utf-8"><title>Matcha Flavoured Wiki</title>'
                     '<meta http-equiv="refresh" content="0; url=/w/Matcha_Flavoured_Wiki">'
                     '<a href="/w/Matcha_Flavoured_Wiki">Matcha Flavoured Wiki</a>')
    # the main page is served at / (its canonical URL); /w/Matcha_Flavoured_Wiki stays as an alias
    shutil.copy(page_path(out, 'Matcha Flavoured Wiki'), os.path.join(out, 'index.html'))
    with open(page_path(out, 'Matcha Flavoured Wiki'), 'r+', encoding='utf-8') as f:  # searched once, as /
        doc = f.read().replace(' data-pagefind-body', '', 1)
        f.seek(0), f.truncate(), f.write(doc)
    # 404 page: the main page's shell with a not-found message and a case-insensitive redirect
    nf = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                # site/search.js lists the pages whose titles are closest to the address
                lambda m: '<div id="mw-content-text"><p>There is no page with this title. Try the search box above.</p>'
                          '<div id="mfw-notfound-matches"></div>' + m.group(2),
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
    search_index.write(out, ex.search, seo.resolve_redirects(ex.redirects, titles), ex.case_redirects)
    open(os.path.join(out, '.nojekyll'), 'w').close()
    # full-text search index (Pagefind); the component UI is served from /pagefind/
    import subprocess
    subprocess.run(['npx', '-y', 'pagefind@1.5.2', '--site', out, '--quiet'], check=True)
    # last, once every file is in place: ?v=<content hash> on each stylesheet, script and image URL
    fingerprint.apply(out)
    print('exported %(page)d pages, %(redirect)d redirects, %(error)d errors -> ' % done + out)


if __name__ == '__main__':
    main()
