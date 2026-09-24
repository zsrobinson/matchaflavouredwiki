"""What links here, for the static export (tools/export_static.py).

MediaWiki's Tools menu links every page to Special:WhatLinksHere/<Title>, the pages that link to it. The
static site has no database to ask, so the export writes one page per exported page, at the same URL
(/w/Special:WhatLinksHere/<Title>), from the links it saw while exporting: every link in the page's
body, navboxes included, as MediaWiki counts them. Category listings are not links (MediaWiki's aren't
either), and links to redirects were already pointed at their target by the export, so the redirects
themselves are listed as "(redirect page)", as MediaWiki does. The pages are noindex (seo.utility_page),
and robots.txt keeps crawlers out of /w/Special:.
"""
import html
import os
import re
import urllib.parse

import seo

PREFIX = 'Special:WhatLinksHere/'
MAIN = 'Matcha Flavoured Wiki'  # linked as "/"


def links(doc):
    """Titles a rendered page links to (after the export's link rewriting)."""
    body = doc.split('id="mw-content-text"', 1)[-1].split('class="printfooter"', 1)[0]
    # a category page's member lists are generated, not links in its text
    body = re.split(r'<div id="mw-(?:subcategories|pages|category-media)"', body, maxsplit=1)[0]
    out = set()
    for path in re.findall(r'href="(/w/[^"#?]+|/)(?=[#?"])', body):
        if path == '/':
            out.add(MAIN)
            continue
        title = urllib.parse.unquote(html.unescape(path[3:])).replace('_', ' ')
        if not title.startswith('Special:'):
            out.add(title)
    return out


def invert(pages, redirects):
    """pages: title -> the titles it links to; redirects: alias -> the title it ends at.
    Returns title -> sorted rows (title, is_redirect) for every page in pages."""
    rows = {t: set() for t in pages}
    for title, targets in pages.items():
        for target in targets:
            if target != title and target in rows:
                rows[target].add((title, False))
    for alias, target in redirects.items():
        if target in rows:
            rows[target].add((alias, True))
    return {t: sorted(r, key=lambda row: (row[0].casefold(), row[0])) for t, r in rows.items()}


def body(title, rows, href_for):
    """The list, in MediaWiki's markup (ul#mw-whatlinkshere-list)."""
    esc = lambda s: html.escape(s, quote=True)
    here = '<a href="%s" title="%s">%s</a>' % (esc(href_for(title)), esc(title), esc(title))
    if not rows:
        return '<p>No pages link to %s.</p>' % here
    items = []
    for t, redirect in rows:
        if redirect:
            items.append('<li><a href="%s" class="mw-redirect" title="%s">%s</a> (redirect page)</li>'
                         % (esc(href_for(t)), esc(t), esc(t)))
        else:
            items.append('<li><a href="%s" title="%s">%s</a> ‎ <span class="mw-whatlinkshere-tools">'
                         '(<a href="%s" title="%s">← links</a>)</span></li>'
                         % (esc(href_for(t)), esc(t), esc(t), esc(href_for(PREFIX + t)), esc(PREFIX + t)))
    return ('<p>The following pages link to %s:</p>\n<ul id="mw-whatlinkshere-list">%s</ul>'
            % (here, '\n'.join(items)))


def shell(main_html):
    """The main page's skin as a special page (noindex, seo.utility_page), with \\x00SLOT\\x00 markers to fill."""
    doc = re.sub(r'<body class="([^"]*)"', lambda m: '<body class="%s"' % ' '.join(
        [c for c in m.group(1).split() if not re.match(r'(?:ns|page|rootpage)-', c)] +
        ['ns--1', 'ns-special', 'mw-special-Whatlinkshere', 'page-Special_WhatLinksHere', 'rootpage-Special_WhatLinksHere']), main_html, count=1)
    # tabs: "Special page" alone, as MediaWiki shows on special pages; no GitHub tabs, tools or page record
    tab = ('<li id="ca-nstab-special" class="selected mw-list-item"><a href="\x00HREF\x00" '
           'title="This is a special page, and it cannot be edited"><span>Special page</span></a></li>')
    doc = re.sub(r'(<nav id="p-namespaces".*?<ul class="vector-menu-content-list">).*?(</ul>)',
                 lambda m: m.group(1) + tab + m.group(2), doc, count=1, flags=re.S)
    doc = re.sub(r'(<nav id="p-views" class="[^"]*)(".*?<ul class="vector-menu-content-list">).*?(</ul>)', r'\1 emptyPortlet\2\3', doc, count=1, flags=re.S)
    doc = re.sub(r'<li id="footer-(?:info-mfw-record|places-mfw-report)">.*?</li>\s*', '', doc, flags=re.S)
    doc = re.sub(r'<div id="catlinks".*?</div></div>', '', doc, flags=re.S)
    doc = re.sub(r'<span hidden data-pagefind-meta[^>]*></span>', '', doc)
    doc = re.sub(r'<h1 id="firstHeading"[^>]*>.*?</h1>', '<h1 id="firstHeading" class="firstHeading mw-first-heading">\x00H1\x00</h1>', doc, count=1, flags=re.S)
    doc = re.sub(r'<div id="mw-content-subtitle"></div>', '<div id="mw-content-subtitle">← \x00BACK\x00</div>', doc, count=1)
    doc = re.sub(r'<div id="mw-content-text"[^>]*>.*?(<div[^>]*class="printfooter")',
                 lambda m: '<div id="mw-content-text" class="mw-body-content">\x00BODY\x00' + m.group(1), doc, count=1, flags=re.S)
    doc = seo.utility_page(doc, '\x00TITLE\x00')
    for slot in ('HREF', 'H1', 'BACK', 'BODY', 'TITLE'):
        assert doc.count('\x00%s\x00' % slot) == 1, 'backlinks.shell: no place for %s' % slot
    return doc


def write(out, main_html, pages, redirects, href_for, page_path):
    """pages: title -> the titles it links to (every exported page); redirects: alias -> resolved '/w/...' path."""
    by_path = {href_for(t): t for t in pages}
    by_path['/'] = MAIN
    aliases = {a.replace('_', ' '): by_path.get(target.partition('#')[0]) for a, target in redirects.items()}
    rows = invert(pages, {a: t for a, t in aliases.items() if t})
    base = shell(main_html)
    esc = lambda s: html.escape(s, quote=True)
    for title, r in rows.items():
        heading = 'Pages that link to "%s"' % title
        doc = (base.replace('\x00HREF\x00', esc(href_for(PREFIX + title)))
               .replace('\x00H1\x00', esc(heading))
               .replace('\x00BACK\x00', '<a href="%s" title="%s">%s</a>' % (esc(href_for(title)), esc(title), esc(title)))
               .replace('\x00TITLE\x00', esc(heading))
               .replace('\x00BODY\x00', body(title, r, href_for)))
        dest = page_path(out, PREFIX + title)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'w', encoding='utf-8') as f:
            f.write(doc)
    return len(rows)
