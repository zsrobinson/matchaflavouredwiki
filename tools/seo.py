"""Search-engine optimisation for the static export (used by tools/export_static.py).

For every page: absolute canonical URL, meta description from the article's lead, Open Graph
and Twitter cards, JSON-LD (WebSite on the main page, Article + BreadcrumbList elsewhere),
and noindex for thin generated pages. For the site: sitemap.xml with git dates, robots.txt,
_headers (caching), and src/redirects.json, which the Worker uses to serve real 301s for
redirect pages and wrong-case URLs.
"""
import html
import json
import os
import re
import subprocess
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.environ.get('SITE_URL', 'https://matchaflavou.red').rstrip('/')
SITE_NAME = 'Matcha Flavoured Wiki'
DEFAULT_DESC = ('Unofficial Matcha Flavoured wiki for the Minecraft datapack: recipes, alloys, food, '
                'enchanting and progression guides verified against the pack’s source code.')
MAIN_TITLE = 'Matcha Flavoured Wiki – Minecraft Datapack Recipes & Guides'


def page_url(title):
    if title == 'Matcha Flavoured Wiki':
        return SITE + '/'  # the main page lives at the site root
    return SITE + '/w/' + urllib.parse.quote(title.replace(' ', '_'), safe=":/'(),!*$@;=+&-._~")


def git_dates():
    """Last commit date of every file under wiki/ (one git call)."""
    dates = {}
    try:
        out = subprocess.run(['git', '-C', ROOT, 'log', '--format=@%cI', '--name-only', '--', 'wiki'],
                             capture_output=True, text=True, timeout=120).stdout
    except Exception:
        return dates
    current = None
    for line in out.splitlines():
        if line.startswith('@'):
            current = line[1:]
        elif line and current and line not in dates:
            dates[line] = current
    return dates


def source_file(title, ns):
    """Repository path of the page's source file, preferring the hand-written layer."""
    import build_xml  # noqa
    name = title.split(':', 1)[1] if ns != 'Main' and ':' in title else title
    if ns == 'Project':
        name = title.split(':', 1)[1]
    fname = name.replace('/', '%2F') + '.wiki'
    for layer in ('pages', 'generated'):
        rel = 'wiki/%s/%s/%s' % (layer, ns, fname)
        if os.path.exists(os.path.join(ROOT, rel)):
            return rel, layer
    return None, None


def lead_description(doc):
    """First real paragraph of the article, as plain text, trimmed to ~160 characters."""
    body = doc.split('id="mw-content-text"', 1)[-1]
    for m in re.finditer(r'<p>(.*?)</p>', body, re.S):
        text = re.sub(r'<sup[^>]*>.*?</sup>', '', m.group(1), flags=re.S)
        # health glyphs ({{Hp}}): "8 (<img alt=Heart> × 4)" -> "8 (4 hearts)"
        text = re.sub(r'\(\s*<span class="glyph">.*?</span>\s*×\s*([\d.]+)\)', lambda g: '(%s heart%s)' % (g.group(1), '' if g.group(1) == '1' else 's'), text, flags=re.S)
        text = re.sub(r'<img [^>]*alt="([^"]*)"[^>]*>', r'\1', text)
        text = html.unescape(re.sub(r'<[^>]+>', '', text))
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 40:
            if len(text) > 160:
                cut = text[:157]
                text = cut[:cut.rfind(' ')].rstrip(',;:') + '…'
            return text
    return None


def head_tags(title, doc, info):
    """<head> additions for one page. info: dict(layer, lastmod, image, categories, is_main)."""
    url = page_url(title)
    desc = DEFAULT_DESC if info.get('is_main') else (lead_description(doc) or DEFAULT_DESC)
    image = info.get('image') or '/assets/Wiki.png'
    image = image if image.startswith('http') else SITE + image
    esc = lambda s: html.escape(s, quote=True)
    t = MAIN_TITLE if info.get('is_main') else '%s – %s' % (title, SITE_NAME)
    tags = [
        '<meta name="description" content="%s">' % esc(desc),
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:title" content="%s">' % esc(title if not info.get('is_main') else SITE_NAME),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % esc(url),
        '<meta property="og:type" content="%s">' % ('website' if info.get('is_main') else 'article'),
        '<meta property="og:image" content="%s">' % esc(image),
        '<meta name="twitter:card" content="summary">',
        '<meta name="twitter:title" content="%s">' % esc(t),
        '<meta name="twitter:description" content="%s">' % esc(desc),
    ]
    if info.get('noindex'):
        tags.append('<meta name="robots" content="noindex, follow">')
    publisher = {'@type': 'Organization', 'name': SITE_NAME, 'url': SITE + '/',
                 'logo': {'@type': 'ImageObject', 'url': SITE + '/assets/Wiki.png'}}
    if info.get('is_main'):
        ld = [{
            '@context': 'https://schema.org', '@type': 'WebSite', 'name': SITE_NAME,
            'alternateName': ['Matcha Flavored Wiki', 'Matcha Flavoured datapack wiki', 'Matcha Flavored datapack wiki'],
            'url': SITE + '/', 'description': DEFAULT_DESC,
            'potentialAction': {'@type': 'SearchAction', 'target': SITE + '/search/?q={search_term_string}',
                                'query-input': 'required name=search_term_string'},
            'publisher': publisher,
        }]
    else:
        article = {'@context': 'https://schema.org', '@type': 'Article', 'headline': title, 'description': desc,
                   'url': url, 'mainEntityOfPage': url, 'image': image, 'inLanguage': 'en',
                   'isPartOf': {'@type': 'WebSite', 'name': SITE_NAME, 'url': SITE + '/'},
                   'about': {'@type': 'VideoGame', 'name': 'Minecraft'},
                   'keywords': 'Matcha Flavoured, Matcha Flavored, Minecraft datapack, ' + title,
                   'publisher': publisher, 'author': {'@type': 'Organization', 'name': SITE_NAME, 'url': SITE + '/'}}
        if info.get('lastmod'):
            article['dateModified'] = info['lastmod']
        ld = [article]
        cats = info.get('categories') or []
        crumbs = [{'@type': 'ListItem', 'position': 1, 'name': SITE_NAME, 'item': SITE + '/'}]
        if cats:
            crumbs.append({'@type': 'ListItem', 'position': 2, 'name': cats[0], 'item': page_url('Category:' + cats[0])})
        crumbs.append({'@type': 'ListItem', 'position': len(crumbs) + 1, 'name': title, 'item': url})
        ld.append({'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': crumbs})
    tags += ['<script type="application/ld+json">%s</script>' % json.dumps(x, ensure_ascii=False).replace('</', '<\\/') for x in ld]
    return '\n'.join(tags), t


def apply(doc, title, info):
    tags, t = head_tags(title, doc, info)
    # drop MediaWiki's own social/robots tags (PageImages writes a relative og:image) so ours are the only ones
    doc = re.sub(r'<meta (?:property="og:[^"]*"|name="twitter:[^"]*"|name="robots"|name="description")[^>]*>\s*', '', doc)
    # canonical: MediaWiki's own tag (relative after rewriting) -> absolute production URL
    doc = re.sub(r'<link rel="canonical" href="[^"]*"\s*/?>', '', doc)
    tags = '<link rel="canonical" href="%s">\n' % html.escape(page_url(title), quote=True) + tags
    doc = re.sub(r'<title>.*?</title>', '<title>%s</title>' % html.escape(t), doc, count=1, flags=re.S)
    doc = doc.replace('</head>', tags + '\n</head>', 1)
    return doc


def utility_page(doc, title):
    """A search/error shell is not the homepage or an indexable article."""
    doc = re.sub(r'<link rel="canonical"[^>]*>\s*', '', doc)
    doc = re.sub(r'<meta (?:property="og:[^"]*"|name="twitter:[^"]*"|name="robots"|name="description")[^>]*>\s*', '', doc)
    doc = re.sub(r'<script type="application/ld\+json">.*?</script>\s*', '', doc, flags=re.S)
    doc = re.sub(r'<title>.*?</title>', '<title>%s – %s</title>' % (html.escape(title), SITE_NAME), doc, flags=re.S)
    return doc.replace('</head>', '<meta name="robots" content="noindex, follow">\n</head>', 1)


def resolve_redirects(redirects, titles):
    """Collapse aliases to real pages, preserving fragments; reject broken chains."""
    canonical = {t.lower().replace(' ', '_'): t for t in titles}
    resolved = {}
    for alias, target in redirects.items():
        seen = {alias}
        fragment = ''
        while True:
            path, separator, anchor = target.partition('#')
            if separator:
                fragment = '#' + anchor
            if path == '/':
                resolved[alias] = '/' + fragment
                break
            if not path.startswith('/w/'):
                raise ValueError('Non-wiki redirect target: %s -> %s' % (alias, target))
            key = urllib.parse.unquote(path[3:]).replace(' ', '_')
            if key in seen:
                raise ValueError('Redirect cycle: %s -> %s' % (alias, key))
            seen.add(key)
            if key in redirects:
                target = redirects[key]
                continue
            title = canonical.get(key.lower())
            if title is None:
                raise ValueError('Missing redirect target: %s -> %s' % (alias, key))
            resolved[alias] = page_url(title).removeprefix(SITE) + fragment
            break
    return resolved


def categories(doc):
    m = re.search(r'<div id="mw-normal-catlinks".*?</div>', doc, re.S)
    if not m:
        return []
    return [html.unescape(x) for x in re.findall(r'title="Category:([^"]+)"', m.group(0))]


def infobox_image(doc):
    m = re.search(r'<div class="infobox-imagearea[^"]*">.*?<img [^>]*src="([^"]+)"', doc, re.S)
    return m.group(1) if m else None


def write_site_files(out, indexed, redirects, titles):
    """sitemap.xml, robots.txt, _headers and src/redirects.json."""
    urls = []
    for title, lastmod in sorted(indexed.items()):
        loc = SITE + '/' if title == 'Matcha Flavoured Wiki' else page_url(title)
        urls.append('<url><loc>%s</loc>%s</url>' % (html.escape(loc), ('<lastmod>%s</lastmod>' % lastmod[:10]) if lastmod else ''))
    with open(os.path.join(out, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
                '\n'.join(urls) + '\n</urlset>\n')
    with open(os.path.join(out, 'robots.txt'), 'w') as f:
        f.write('User-agent: *\nAllow: /\nDisallow: /pagefind/\n\nSitemap: %s/sitemap.xml\n' % SITE)
    # Everything revalidates on every view (a 304 when unchanged). The pages reference stylesheets,
    # scripts and images with ?v=<content hash> (fingerprint.py), and the Worker lets browsers keep
    # those for a year. Files named without a version must not be cached on their own: after a deploy,
    # a phone kept the old Vector.css for days next to the new site.js.
    with open(os.path.join(out, '_headers'), 'w') as f:
        f.write('/*\n  Cache-Control: public, max-age=0, must-revalidate\n')
    # Worker redirect table: exact redirects and a lowercase index of real titles
    table = {'redirects': resolve_redirects(redirects, titles), 'titles': {t.lower().replace(' ', '_'): t.replace(' ', '_') for t in titles}}
    os.makedirs(os.path.join(ROOT, 'src'), exist_ok=True)
    with open(os.path.join(ROOT, 'src', 'redirects.json'), 'w', encoding='utf-8') as f:
        json.dump(table, f, ensure_ascii=False, separators=(',', ':'))
