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


def fetch(url, binary=False):
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    return data if binary else data.decode('utf-8', 'replace')


def url_title(title):
    return title.replace(' ', '_')


def page_path(out, title):
    return os.path.join(out, 'w', url_title(title), 'index.html')


def href_for(title):
    return '/w/' + urllib.parse.quote(url_title(title), safe=":/'(),!*$@;=+&-._~")


class Exporter:
    def __init__(self, base, out):
        self.base = base.rstrip('/')
        self.out = out
        self.assets = {}  # load.php url -> static path

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
        doc = re.sub(r'<script[^>]*>.*?</script>', '', doc, flags=re.S)
        doc = re.sub(r'<script[^>]*src="[^"]*"[^>]*></script>', '', doc)
        doc = doc.replace('</body>', '<script src="/_static/site.js"></script>\n</body>')
        doc = doc.replace('class="client-nojs', 'class="client-js')
        # red links: keep the styling, remove the edit link
        doc = re.sub(r'<a href="[^"]*action=edit[^"]*redlink=1"([^>]*)>(.*?)</a>', r'<span class="new"\1>\2</span>', doc, flags=re.S)
        # absolute links back to the dev server -> site-relative
        doc = doc.replace(self.base + '/', '/')
        # links a static site can't serve
        doc = re.sub(r'<li id="(?:t-|ca-|pt-|n-recentchanges|n-randompage)[^"]*"[^>]*>.*?</li>', '', doc, flags=re.S)
        doc = re.sub(r'href="/index\.php\?title=Special:Search[^"]*"', 'href="/search/"', doc)
        doc = re.sub(r'<a href="/w/Special:[^"]*"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        doc = re.sub(r'<form action="/index\.php" id="searchform"', '<form action="/search/" id="searchform"', doc)
        doc = re.sub(r'<nav id="p-tb".*?</nav>', '', doc, flags=re.S)
        doc = re.sub(r'<ul id="footer-icons".*?</ul>', '', doc, flags=re.S)
        doc = re.sub(r'<li id="footer-info-lastmod".*?</li>', '', doc, flags=re.S)
        doc = re.sub(r'<div id="footer-places">.*?</div>|<ul id="footer-places">.*?</ul>', '', doc, flags=re.S)
        # image description pages are not exported: unlink files
        doc = re.sub(r'<a href="/w/File:[^"]*" class="mw-file-description"[^>]*>(.*?)</a>', r'\1', doc, flags=re.S)
        return doc

    def export_page(self, title, text):
        dest = page_path(self.out, title)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        m = re.match(r'\s*#REDIRECT\s*\[\[([^\]|#]+)(#[^\]|]*)?', text, re.I)
        if m:
            target = href_for(m.group(1).strip()) + (m.group(2) or '').replace(' ', '_')
            with open(dest, 'w', encoding='utf-8') as f:
                f.write('<!doctype html><meta charset="utf-8"><title>Redirect</title>'
                        '<link rel="canonical" href="%s"><meta http-equiv="refresh" content="0; url=%s">'
                        '<a href="%s">Redirect</a>' % (target, target, target))
            return 'redirect'
        doc = fetch(self.base + '/w/' + urllib.parse.quote(url_title(title)))
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(self.rewrite(doc))
        return 'page'


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

  // Light/dark theme toggle (Gadget-themeToggle).
  var KEY = 'mfw-theme';
  function getTheme() { try { return localStorage.getItem(KEY) || 'light'; } catch (e) { return 'light'; } }
  function applyTheme(t) {
    document.body.classList.remove('mfw-theme-light', 'mfw-theme-dark');
    document.body.classList.add('mfw-theme-' + t);
  }
  applyTheme(getTheme());
  var personal = document.querySelector('#p-personal ul');
  if (personal) {
    var li = document.createElement('li');
    li.id = 'pt-theme-toggle';
    li.className = 'mw-list-item';
    var a = document.createElement('a');
    a.href = '#'; a.title = 'Change theme'; a.className = 'oo-ui-icon-advanced';
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var t = getTheme() === 'light' ? 'dark' : 'light';
      try { localStorage.setItem(KEY, t); } catch (err) {}
      applyTheme(t);
    });
    li.appendChild(a);
    personal.insertBefore(li, personal.firstChild);
  }

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

  // Client-side title search.
  var form = document.getElementById('searchform');
  var input = document.getElementById('searchInput');
  var index = null;
  function load(cb) {
    if (index) return cb(index);
    fetch('/search.json').then(function (r) { return r.json(); }).then(function (d) { index = d; cb(d); });
  }
  function norm(s) { return s.toLowerCase().replace(/_/g, ' ').trim(); }
  function go(q) {
    load(function (titles) {
      var n = norm(q);
      var exact = titles.filter(function (t) { return norm(t) === n; })[0];
      if (exact) { location.href = '/w/' + encodeURIComponent(exact.replace(/ /g, '_')); return; }
      location.href = '/search/?q=' + encodeURIComponent(q);
    });
  }
  if (form && input) {
    form.addEventListener('submit', function (e) { e.preventDefault(); go(input.value); });
    var list = document.createElement('datalist');
    list.id = 'mfw-titles';
    input.setAttribute('list', 'mfw-titles');
    input.addEventListener('focus', function () {
      load(function (titles) {
        if (list.childElementCount) return;
        titles.forEach(function (t) { var o = document.createElement('option'); o.value = t; list.appendChild(o); });
      });
    }, { once: true });
    document.body.appendChild(list);
  }
  var results = document.getElementById('mfw-search-results');
  if (results) {
    var q = new URLSearchParams(location.search).get('q') || '';
    if (input) input.value = q;
    load(function (titles) {
      var n = norm(q), words = n.split(/\s+/).filter(Boolean);
      var hits = titles.filter(function (t) { var s = norm(t); return words.every(function (w) { return s.indexOf(w) !== -1; }); });
      hits.sort(function (a, b) { return (norm(a).indexOf(n) === 0 ? 0 : 1) - (norm(b).indexOf(n) === 0 ? 0 : 1) || a.length - b.length; });
      results.innerHTML = '<p>' + hits.length + ' page(s) matching <b></b>.</p><ul></ul>';
      results.querySelector('b').textContent = q;
      var ul = results.querySelector('ul');
      hits.slice(0, 300).forEach(function (t) {
        var li = document.createElement('li'); var a = document.createElement('a');
        a.href = '/w/' + encodeURIComponent(t.replace(/ /g, '_')); a.textContent = t;
        li.appendChild(a); ul.appendChild(li);
      });
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
    # MediaWiki needs each stylesheet URL fetched once before threads race on it
    first = next(iter(sorted(exportable)))
    ex.export_page('Matcha Flavoured Wiki', exportable.get('Matcha Flavoured Wiki', ('Main', '', ''))[1])

    done = {'page': 0, 'redirect': 0, 'error': 0}

    def job(item):
        title, (ns, text, layer) = item
        try:
            return ex.export_page(title, text)
        except Exception as e:
            print('!! %s: %s' % (title, e), file=sys.stderr)
            return 'error'
    with ThreadPoolExecutor(args.jobs) as pool:
        for r in pool.map(job, sorted(exportable.items())):
            done[r] += 1

    # site furniture
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, '_static', 'site.js'), 'w') as f:
        f.write(SITE_JS)
    for d in ('assets', 'images'):
        src = os.path.join(ROOT, 'site', d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(out, d), dirs_exist_ok=True)
    titles = sorted(t for t, p in exportable.items() if not re.match(r'\s*#REDIRECT', p[1], re.I))
    with open(os.path.join(out, 'search.json'), 'w', encoding='utf-8') as f:
        json.dump(titles + sorted(t for t, p in exportable.items() if re.match(r'\s*#REDIRECT', p[1], re.I)), f)
    # search page and root index, built from the main page's skin
    main_html = open(page_path(out, 'Matcha Flavoured Wiki'), encoding='utf-8').read()
    search = re.sub(r'(<div id="mw-content-text"[^>]*>).*?(<div class="printfooter")',
                    r'\1<div id="mfw-search-results"><p>Searching…</p></div>\2', main_html, flags=re.S)
    search = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading">Search results</h1>', search, flags=re.S)
    search = re.sub(r'<title>.*?</title>', '<title>Search - Matcha Flavoured Wiki</title>', search)
    search = re.sub(r'<div id="catlinks".*?</div></div>', '', search, flags=re.S)
    os.makedirs(os.path.join(out, 'search'), exist_ok=True)
    open(os.path.join(out, 'search', 'index.html'), 'w', encoding='utf-8').write(search)
    root_redirect = ('<!doctype html><meta charset="utf-8"><title>Matcha Flavoured Wiki</title>'
                     '<meta http-equiv="refresh" content="0; url=/w/Matcha_Flavoured_Wiki">'
                     '<a href="/w/Matcha_Flavoured_Wiki">Matcha Flavoured Wiki</a>')
    open(os.path.join(out, 'index.html'), 'w').write(root_redirect)
    shutil.copy(page_path(out, 'Matcha Flavoured Wiki'), os.path.join(out, '404.html'))
    # host hints: Netlify/Cloudflare Pages redirects, and disable Jekyll on GitHub Pages
    open(os.path.join(out, '_redirects'), 'w').write('/  /w/Matcha_Flavoured_Wiki  302\n/w/Main_Page  /w/Matcha_Flavoured_Wiki  301\n')
    open(os.path.join(out, '.nojekyll'), 'w').close()
    print('exported %(page)d pages, %(redirect)d redirects, %(error)d errors -> ' % done + out)


if __name__ == '__main__':
    main()
