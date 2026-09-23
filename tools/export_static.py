#!/usr/bin/env python3
"""Export the running wiki to a fully static site in dist/ (deployable to any static host).

  tools/export_static.py [--out dist] [--base http://localhost:8080]

Every page (all namespaces in the repo, plus categories) is rendered by MediaWiki once and
saved as dist/w/<Title>.html, so URLs stay the same as the live wiki (/w/Page_title). Each page
is also rendered by the mobile site (MobileFrontend + Minerva, as on minecraft.wiki) into
dist/mobile/w/<Title>.html; src/worker.js serves that copy to phones at the same URL.
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


def page_path(out, title, mobile=False):
    # /w/Title -> w/Title.html: Cloudflare (html_handling), GitHub Pages and Netlify all serve
    # extensionless URLs from .html files without a redirect. The mobile copy is under mobile/.
    return os.path.join(out, 'mobile' if mobile else '', 'w', url_title(title) + '.html')


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
        self.drawer = ''  # the desktop sidebar's sections, for the mobile menu drawer (see main())

    # --- stylesheets from load.php -------------------------------------------------
    def static_css(self, href):
        href = html.unescape(href)
        if href in self.assets:
            return self.assets[href]
        css = fetch(self.base + href if href.startswith('/') else href)
        # pull in images referenced by the stylesheet
        def repl(m):
            u = html.unescape(m.group(1).strip('\'"'))
            if u.startswith('data:') or u.startswith('http'):
                return m.group(0)
            if not u.startswith('/'):
                return m.group(0)
            if u.startswith('/load.php?'):
                return 'url("%s")' % self.static_image(u)
            self.copy_url(u.split('?')[0])
            return 'url("%s")' % u.split('?')[0]
        css = re.sub(r'url\(([^)]+)\)', repl, css)
        name = '/_rl/%s.css' % hashlib.sha1(href.encode()).hexdigest()[:16]
        os.makedirs(os.path.join(self.out, '_rl'), exist_ok=True)
        with open(os.path.join(self.out, name.lstrip('/')), 'w', encoding='utf-8') as f:
            f.write(css)
        self.assets[href] = name
        return name

    def static_image(self, href):
        """An image served by load.php (e.g. Minerva's icons) -> a static file under /_rl/."""
        if href in self.assets:
            return self.assets[href]
        data = fetch(self.base + href, binary=True)
        ext = '.svg' if data.lstrip()[:5] in (b'<?xml', b'<svg ') else '.png'
        name = '/_rl/%s%s' % (hashlib.sha1(href.encode()).hexdigest()[:16], ext)
        os.makedirs(os.path.join(self.out, '_rl'), exist_ok=True)
        with open(os.path.join(self.out, name.lstrip('/')), 'wb') as f:
            f.write(data)
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
    def rewrite(self, doc, mobile=False):
        # stylesheets: load.php -> static file
        doc = re.sub(r'<link rel="stylesheet" href="(/load\.php\?[^"]+)"',
                     lambda m: '<link rel="stylesheet" href="%s"' % self.static_css(m.group(1)), doc)
        # drop all MediaWiki scripts (the startup module loads more code dynamically)
        doc = re.sub(r'<script[^>]*>.*?</script>', lambda m: m.group(0) if 'mfw-theme' in m.group(0) else '', doc, flags=re.S)
        doc = re.sub(r'<script[^>]*src="[^"]*"[^>]*></script>', '', doc)
        doc = doc.replace('</head>', HEAD_EXTRA + '</head>', 1)
        doc = re.sub(r'(<body[^>]*>)', r'\1' + THEME_BOOT, doc, count=1)
        doc = doc.replace('</body>', '<script src="/_static/site.js"></script>\n</body>')
        if not mobile:
            doc = self.pagefind_tags(doc)
        doc = doc.replace('class="client-nojs', 'class="client-js')
        # red links: keep the styling, remove the edit link
        doc = re.sub(r'<a href="[^"]*action=edit[^"]*redlink=1"([^>]*)>(.*?)</a>', r'<span class="new"\1>\2</span>', doc, flags=re.S)
        # absolute links back to the dev server -> site-relative
        doc = doc.replace(self.base + '/', '/')
        # links to capitalisation redirects go straight to the article (case-insensitive file
        # systems can't hold both "Mud_kiln.html" and "Mud_Kiln.html")
        def fix(m):
            t = urllib.parse.unquote(m.group(1)).replace('_', ' ')
            tgt = self.case_redirects.get(t)
            return 'href="%s%s"' % (href_for(tgt), m.group(2) or '') if tgt else m.group(0)
        doc = re.sub(r'href="/w/([^"#?]+)(#[^"]*)?"', fix, doc)
        doc = doc.replace('href="/w/Matcha_Flavoured_Wiki"', 'href="/"')  # the main page is served at /
        # the "Mobile view" / "Desktop" footer links: src/worker.js handles ?mobileaction=
        doc = re.sub(r'href="/index\.php\?title=[^"&]*&amp;mobileaction=(toggle_view_\w+)"', r'href="?mobileaction=\1"', doc)
        doc = re.sub(r'href="/w/[^"?]*\?mobileaction=(toggle_view_\w+)"', r'href="?mobileaction=\1"', doc)
        # links a static site can't serve
        doc = re.sub(r'<li id="(?:t-|ca-(?!mfw-)|pt-|n-recentchanges|n-randompage)[^"]*"[^>]*>.*?</li>', '', doc, flags=re.S)
        doc = re.sub(r'href="/index\.php\?title=Special:Search[^"]*"', 'href="/search/"', doc)
        doc = re.sub(r'<a href="/w/Special:[^"]*"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        doc = re.sub(r'<ul id="footer-icons".*?</ul>', '', doc, flags=re.S)
        doc = re.sub(r'<li id="footer-info-lastmod".*?</li>', '', doc, flags=re.S)
        # footer links: only the switch between the mobile and desktop views
        doc = re.sub(r'<li id="footer-places-(?!mobileview|desktop-toggle)[^"]*".*?</li>\s*', '', doc, flags=re.S)
        # image description pages are not exported: unlink files
        doc = re.sub(r'<a href="/w/File:[^"]*" class="mw-file-description"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        return self.rewrite_mobile(doc) if mobile else self.rewrite_desktop(doc)

    def pagefind_tags(self, doc):
        """Pagefind indexes the desktop copy only: the article body, with title, categories and item icon as metadata."""
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
        return doc

    def rewrite_desktop(self, doc):
        doc = re.sub(r'<form action="/index\.php" id="searchform".*?</form>',
                     '<pagefind-searchbox id="mfw-searchbox" instance="header" placeholder="Search Matcha Flavoured Wiki" max-results="8" '
                     'show-sub-results shortcut="/"></pagefind-searchbox>', doc, flags=re.S)
        doc = re.sub(r'<nav id="p-tb".*?</nav>', '', doc, flags=re.S)
        return doc

    def rewrite_mobile(self, doc):
        """The mobile site (Minerva): header search, menu drawer and page actions for a static, git-edited wiki."""
        # no watchlist, accounts, mobile settings page, random page or disclaimers page
        doc = re.sub(r'<li id="page-actions-watch".*?</li>\s*', '', doc, flags=re.S)
        doc = re.sub(r'<ul id="(?:pt-preferences|p-personal)".*?</ul>\s*', '', doc, flags=re.S)
        doc = re.sub(r'<li class="toggle-list-item ?">\s*<a class="toggle-list-item__anchor menu__item--(?:random|disclaimers)".*?</li>\s*',
                     '', doc, flags=re.S)
        # menu drawer: the desktop sidebar's sections after Home (minecraft.wiki's mobileSidebar gadget does the same)
        doc = re.sub(r'(<div id="mw-mf-page-left"[^>]*>\s*<ul id="p-navigation".*?</ul>)', lambda m: m.group(1) + self.drawer, doc, count=1, flags=re.S)
        # header search: Pagefind's searchbox, opened by the search icon (or /search/ without JavaScript)
        doc = re.sub(r'<form role="search"[^>]*class="minerva-search-form">.*?</form>', MOBILE_SEARCH, doc, count=1, flags=re.S)
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
        url = self.base + '/w/' + urllib.parse.quote(url_title(title))
        doc = self.rewrite(fetch(url))
        mdoc = self.rewrite(fetch(url + '?useformat=mobile'), mobile=True)
        src, layer = seo.source_file(title, ns)
        is_main = title == 'Matcha Flavoured Wiki'
        info = {'layer': layer, 'lastmod': self.dates.get(src), 'categories': seo.categories(doc),
                'image': seo.infobox_image(doc), 'is_main': is_main,
                # generated pages (vanilla items, data-only pages) are thin: keep them out of the index
                'noindex': layer == 'generated' and not is_main}
        doc = seo.apply(doc, title, info)
        mdoc = seo.apply(last_edited(mdoc, info['lastmod']), title, info)
        if not info['noindex']:
            self.indexed[title] = info['lastmod']
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(doc)
        mdest = page_path(self.out, title, mobile=True)
        os.makedirs(os.path.dirname(mdest), exist_ok=True)
        with open(mdest, 'w', encoding='utf-8') as f:
            f.write(mdoc)
        return 'page'


def last_edited(doc, lastmod):
    """Minerva's "Last edited" bar: the page file's last commit, linking to its history on GitHub."""
    hist = re.search(r'id="ca-mfw-history" href="([^"]+)"', doc)
    if not hist or not lastmod:
        return re.sub(r'<a class="last-modified-bar".*?</a>', '', doc, count=1, flags=re.S)
    y, mo, d = (int(x) for x in lastmod[:10].split('-'))
    months = ('January February March April May June July August September October November December').split()
    bar = ('<a class="last-modified-bar" href="%s"><div class="post-content last-modified-bar__content">'
           '<span class="minerva-icon minerva-icon-size-medium minerva-icon--modified-history"></span>'
           '<span class="last-modified-bar__text"><span>Last edited on %d %s %d</span></span>'
           '<span class="minerva-icon minerva-icon-size-small minerva-icon--expand"></span></div></a>') % (hist.group(1), d, months[mo - 1], y)
    return re.sub(r'<a class="last-modified-bar".*?</a>', lambda m: bar, doc, count=1, flags=re.S)


def sidebar_drawer(doc):
    """The desktop sidebar's portlets as Minerva menu-drawer lists (the drawer already has Home)."""
    out = []
    for m in re.finditer(r'<nav id="(p-[^"]+)" class="[^"]*vector-menu-portal[^"]*".*?</nav>', doc, re.S):
        pid, block = m.group(1), m.group(0)
        if pid == 'p-tb':
            continue
        label = re.search(r'<span class="vector-menu-heading-label">(.*?)</span>', block, re.S)
        items = []
        for a in re.finditer(r'<li id="([^"]*)"[^>]*><a ([^>]*)>(.*?)</a>', block, re.S):
            attrs, text = a.group(2), re.sub(r'<[^>]+>', '', a.group(3)).strip()
            href = re.search(r'href="([^"]*)"', attrs)
            if not href or href.group(1) == '/':
                continue  # the main page is the drawer's Home
            ext = ' external' if href.group(1).startswith('http') else ''
            items.append('<li class="toggle-list-item"><a class="toggle-list-item__anchor%s" href="%s">'
                         '<span class="toggle-list-item__label">%s</span></a></li>' % (ext, href.group(1), text))
        if not items:
            continue
        heading = '' if pid == 'p-navigation' or not label else '<li class="mfw-drawer-heading">%s</li>' % label.group(1).strip()
        out.append('<ul id="%s-mobile" class="toggle-list__list mfw-drawer-section">%s%s</ul>' % (pid, heading, ''.join(items)))
    return ''.join(out)


HEAD_EXTRA = ('<link rel="stylesheet" href="/pagefind/pagefind-component-ui.css">'
              '<link rel="stylesheet" href="/_static/site.css">'
              '<script type="module" src="/pagefind/pagefind-component-ui.js"></script>')
MOBILE_SEARCH = (
    '<div class="minerva-search-form mfw-mobile-search">'
    '<button type="button" class="mfw-search-close cdx-button cdx-button--size-large cdx-button--icon-only cdx-button--weight-quiet" aria-label="Close search">'
    '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="m5.83 9 5.58-5.58L10 2l-8 8 8 8 1.41-1.41L5.83 11H18V9z"/></svg></button>'
    '<pagefind-searchbox id="mfw-searchbox" instance="header" placeholder="Search Matcha Flavoured Wiki" max-results="8" show-sub-results></pagefind-searchbox>'
    '<a href="/search/" id="searchIcon" role="button" class="cdx-button cdx-button--size-large cdx-button--fake-button cdx-button--fake-button--enabled '
    'cdx-button--icon-only cdx-button--weight-quiet skin-minerva-search-trigger"><span class="minerva-icon minerva-icon--search"></span><span>Search</span></a>'
    '</div>')
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
/* Mobile site (Minerva): the searchbox opens over the header from the search icon; inline from 720px */
.mfw-mobile-search { display: flex; align-items: center; }
.mfw-mobile-search .mfw-search-close { display: none; color: inherit; }
.mfw-mobile-search #mfw-searchbox { display: none; flex: 1; min-width: 0; --pf-input-height: 36px; --pf-input-font-size: 16px; --pf-border-radius: 2px; }
body.mfw-search-open .minerva-header > :not(.mfw-mobile-search) { display: none; }
body.mfw-search-open .mfw-mobile-search { flex: 1; }
body.mfw-search-open .mfw-mobile-search .mfw-search-close { display: inline-flex; }
body.mfw-search-open .mfw-mobile-search #mfw-searchbox { display: block; }
body.mfw-search-open .mfw-mobile-search #searchIcon { display: none; }
@media (min-width: 720px) {
  .mfw-mobile-search { flex: 0 1 24em; }
  .mfw-mobile-search #mfw-searchbox { display: block; }
  .mfw-mobile-search #searchIcon { display: none; }
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

  // Mobile site: collapsible sections, as MobileFrontend's Toggler does. Collapsed on phones,
  // open from 640px; a #fragment (a TOC or reference link) opens the section it's in, and
  // find-in-page opens collapsed sections too (hidden="until-found").
  var collapsed = window.matchMedia && matchMedia('(max-width: 639px)').matches;
  function setOpen(h, open) {
    var sec = h.nextElementSibling, ind = h.querySelector('.indicator');
    h.classList.toggle('open-block', open);
    h.setAttribute('aria-expanded', String(open));
    if (ind) ind.classList.toggle('mf-icon-rotate-flip', open);
    sec.classList.toggle('open-block', open);
    if (open) sec.removeAttribute('hidden'); else sec.setAttribute('hidden', 'until-found');
  }
  document.querySelectorAll('.mw-parser-output > .section-heading').forEach(function (h) {
    var sec = h.nextElementSibling;
    if (!sec || !sec.classList.contains('collapsible-block')) return;
    h.removeAttribute('onclick');
    h.classList.add('collapsible-heading');
    h.setAttribute('tabindex', '0');
    h.setAttribute('role', 'button');
    h.setAttribute('aria-controls', sec.id);
    sec.classList.add('collapsible-block-js');
    setOpen(h, !collapsed);
    h.addEventListener('click', function (e) {
      if (e.target.closest('a[href]')) return;
      e.preventDefault();
      setOpen(h, !h.classList.contains('open-block'));
    });
    h.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(h, !h.classList.contains('open-block')); }
    });
    sec.addEventListener('beforematch', function () { setOpen(h, true); });
  });
  function reveal() {
    var id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    var el = id && document.getElementById(id);
    if (!el) return;
    var head = el.closest('.collapsible-heading');
    var sec = head ? head.nextElementSibling : el.closest('.collapsible-block');
    if (sec && !sec.classList.contains('open-block')) {
      setOpen(sec.previousElementSibling, true);
      el.scrollIntoView();
    }
  }
  reveal();
  window.addEventListener('hashchange', reveal);

  // Mobile header search: the search icon opens Pagefind's searchbox over the header, like
  // Minerva's search overlay (without JavaScript the icon links to /search/).
  var searchIcon = document.querySelector('.mfw-mobile-search #searchIcon');
  if (searchIcon) {
    var closeSearch = function () { document.body.classList.remove('mfw-search-open'); };
    searchIcon.addEventListener('click', function (e) {
      e.preventDefault();
      document.body.classList.add('mfw-search-open');
      var input = document.querySelector('#mfw-searchbox input');
      if (input) input.focus();
    });
    document.querySelector('.mfw-search-close').addEventListener('click', closeSearch);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSearch(); });
  }

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


def shell_pages(out, main_html, mobile):
    base = os.path.join(out, 'mobile') if mobile else out
    # the shell is the main page's, but these aren't the main page (whose title is hidden)
    main_html = re.sub(r'(<body[^>]*) page-Matcha_Flavoured_Wiki page-Main_Page rootpage-Matcha_Flavoured_Wiki', r'\1 page-Search rootpage-Search',
                       main_html, count=1)
    search_body = ('<div id="mfw-search-page"><pagefind-input autofocus placeholder="Search Matcha Flavoured Wiki"></pagefind-input>'
                   '<div class="mfw-search-layout"><div><pagefind-filter-pane></pagefind-filter-pane></div>'
                   '<div><pagefind-summary></pagefind-summary><pagefind-results show-images show-sub-results></pagefind-results></div></div></div>')
    search = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                    lambda m: '<div id="mw-content-text">' + search_body + m.group(2), main_html, flags=re.S)
    search = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Search results</h1>', search, flags=re.S)
    search = re.sub(r'<title>.*?</title>', '<title>Search - Matcha Flavoured Wiki</title>', search)
    search = re.sub(r'<div id="catlinks".*?</div></div>', '', search, flags=re.S)
    os.makedirs(os.path.join(base, 'search'), exist_ok=True)
    open(os.path.join(base, 'search', 'index.html'), 'w', encoding='utf-8').write(search)
    # the main page is served at / (its canonical URL); /w/Matcha_Flavoured_Wiki stays as an alias
    shutil.copy(page_path(out, 'Matcha Flavoured Wiki', mobile), os.path.join(base, 'index.html'))
    # 404 page: the main page's shell with a not-found message and a case-insensitive redirect
    nf = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div[^>]*class="printfooter")',
                lambda m: '<div id="mw-content-text"><p>There is no page with this title. Try the search box above.</p>' + m.group(2),
                main_html, flags=re.S)
    nf = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Page not found</h1>', nf, flags=re.S)
    nf = nf.replace('</head>', '<script>(function(){var m=location.pathname.match(/^\\/w\\/(.+)$/);if(!m)return;'
                    'fetch("/search.json").then(function(r){return r.json()}).then(function(ts){'
                    'var want=decodeURIComponent(m[1]).replace(/_/g," ").toLowerCase();'
                    'for(var i=0;i<ts.length;i++){if(ts[i].toLowerCase()===want){location.replace("/w/"+encodeURIComponent(ts[i].replace(/ /g,"_")));return}}})})();</script></head>', 1)
    open(os.path.join(base, '404.html'), 'w', encoding='utf-8').write(nf)


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
    # the mobile menu drawer lists the desktop sidebar (MediaWiki:Sidebar), as rendered for the main page
    ex.drawer = sidebar_drawer(ex.rewrite(fetch(ex.base + '/w/Matcha_Flavoured_Wiki')))
    # MediaWiki needs each stylesheet URL fetched once before threads race on it
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

    # site furniture
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, '_static', 'site.js'), 'w') as f:
        # the same shell script the live wiki runs as a gadget, then the static-only behaviours
        f.write(open(os.path.join(ROOT, 'wiki', 'pages', 'MediaWiki', 'Gadget-mfwShell.js'), encoding='utf-8').read())
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
    # search page, root index and 404 page, built from the main page's skin (desktop and mobile)
    for mobile in (False, True):
        shell_pages(out, open(page_path(out, 'Matcha Flavoured Wiki', mobile), encoding='utf-8').read(), mobile)
    # host hints: Netlify/Cloudflare Pages redirects, and disable Jekyll on GitHub Pages
    ex.redirects['Main_Page'] = '/w/Matcha_Flavoured_Wiki'
    seo.write_site_files(out, ex.indexed, ex.redirects, titles)
    open(os.path.join(out, '.nojekyll'), 'w').close()
    # full-text search index (Pagefind); the component UI is served from /pagefind/
    import subprocess
    subprocess.run(['npx', '-y', 'pagefind@1.5.2', '--site', out, '--quiet'], check=True)
    print('exported %(page)d pages, %(redirect)d redirects, %(error)d errors -> ' % done + out)


if __name__ == '__main__':
    main()
