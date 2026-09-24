"""Search data for the static export (tools/export_static.py).

The header search box suggests pages by title first, the way a wiki's search does, and fills the rest
with Pagefind's full-text results. This module builds what the title search needs:

  _static/search-titles.json   one row per page: title, URL, picture, short description, how many
                               pages link to it, whether it is a generated or category page, and
                               the redirects that lead to it (so "Armour" or "Blaze Powder" finds it)
  images/search/<name>.png     small copies of pictures too large for a 40px slot (structure and
                               mob renders); item icons are small already and are used as they are

The same picture is the page's Pagefind image, so the header box and the search page agree. The
matching itself is in site/search.js. Rows are sorted and the thumbnails are drawn deterministically,
so an unchanged site exports byte for byte the same.
"""
import html
import json
import os
import re
import threading
import urllib.parse

THUMB = 80  # px: 2x the 40px slot in the suggestions
THUMB_OVER = 24 * 1024  # bytes: pictures larger than this get a thumbnail
_lock = threading.Lock()  # pages export on several threads


def _src(tag):
    m = re.search(r'\ssrc="([^"]+)"', tag)
    return html.unescape(m.group(1)) if m else None


def page_image(doc, title):
    """The picture that stands for a page, as a site path (or None):
    1. the item icon in the infobox's inventory slot;
    2. the infobox picture (mob and villager renders, structure views, effect icons);
    3. a file named after the page (File:<Title>.png);
    4. the first thumbnail or gallery picture in the article (armor sets, structure pieces).
    Inline icons in text and tables are not used: they show some other item."""
    m = re.search(r'<div class="infobox-invimages">.*?(<img [^>]*>)', doc, re.S)
    if m:
        return _src(m.group(1))
    m = re.search(r'<div class="infobox-imagearea[^"]*">.*?(<img [^>]*>)', doc, re.S)
    if m:
        return _src(m.group(1))
    name = title.split(':', 1)[-1].replace(' ', '_') + '.png'
    for img in re.findall(r'<img [^>]*>', doc):
        src = _src(img) or ''
        if urllib.parse.unquote(src.split('?')[0]).rsplit('/', 1)[-1] == name:
            return src
    body = doc.split('id="mw-content-text"', 1)[-1].split('class="printfooter"', 1)[0]
    m = re.search(r'<(?:figure|li class="gallerybox"|div class="thumb)[^>]*>.*?(<img [^>]*>)', body, re.S)
    if m:
        return _src(m.group(1))
    return None


def thumbnail(out, src, images_dir):
    """A small copy of a large wiki picture, at /images/search/<name>; small pictures as they are.
    images_dir is where the wiki's /images/ files are (site/images)."""
    if not src or not src.startswith('/images/'):
        return src
    src = src.split('?')[0]
    path = os.path.join(images_dir, urllib.parse.unquote(src)[len('/images/'):])
    if not os.path.exists(path) or os.path.getsize(path) <= THUMB_OVER:
        return src
    name = os.path.basename(path)
    dest = os.path.join(out, 'images', 'search', name)
    with _lock:
        if not os.path.exists(dest):
            from PIL import Image
            im = Image.open(path).convert('RGBA')
            bbox = im.getbbox()  # renders sit on transparent margins
            if bbox:
                im = im.crop(bbox)
            im.thumbnail((THUMB, THUMB), Image.LANCZOS)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            im.save(dest, optimize=True)
    return '/images/search/' + urllib.parse.quote(name)


def short_description(doc, limit=110):
    """The lead sentence, shortened to one line in the suggestions."""
    import seo
    text = seo.lead_description(doc)
    if not text:
        return ''
    text = re.split(r'(?<=[.!?])\s', text, 1)[0]
    if len(text) > limit:
        cut = text[:limit - 1]
        text = cut[:cut.rfind(' ')].rstrip(',;:') + '…'
    return text


def link_targets(doc):
    """Titles the article body links to (each counted once per page)."""
    body = doc.split('id="mw-content-text"', 1)[-1].split('class="printfooter"', 1)[0]
    body = re.sub(r'<table[^>]*class="navbox.*?</table>', '', body, flags=re.S)  # every page in a set links its siblings
    return {urllib.parse.unquote(t).replace('_', ' ') for t in re.findall(r'href="/w/([^"#?]+)', body)}


def write(out, pages, redirects, case_redirects):
    """pages: title -> dict(url, image, desc, kind, links); redirects: alias title -> target URL
    ('/w/Target#anchor'). Writes _static/search-titles.json."""
    inbound = {}
    for title, p in pages.items():
        for t in p['links']:
            t = case_redirects.get(t, t)
            if t != title:
                inbound[t] = inbound.get(t, 0) + 1
    by_url = {p['url']: t for t, p in pages.items()}
    aliases = {}
    for alias, target in sorted(redirects.items()):
        alias = alias.replace('_', ' ')
        path, _, anchor = target.partition('#')
        title = by_url.get(path)
        if title is None:
            continue
        aliases.setdefault(title, []).append([alias, anchor] if anchor else alias)
    rows = []
    for title in sorted(pages):
        p = pages[title]
        row = {'t': title, 'u': p['url']}
        if p['image']:
            row['i'] = p['image']
        if p['desc']:
            row['d'] = p['desc']
        if inbound.get(title):
            row['n'] = inbound[title]
        if p['kind'] != 'article':
            row['k'] = p['kind']
        if title in aliases:
            row['a'] = aliases[title]
        rows.append(row)
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, '_static', 'search-titles.json'), 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, separators=(',', ':'))
    return rows
