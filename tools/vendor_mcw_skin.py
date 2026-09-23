#!/usr/bin/env python3
"""Vendor minecraft.wiki's skin (site CSS, template styles, dark theme) into this wiki.

minecraft.wiki runs the same MediaWiki version and Vector legacy skin, so its site CSS
applies to our pages unchanged. This script downloads the readable CSS sources, resolves
their `filepath://Name.png` references to local copies in site/assets/mcw/, and writes:

  wiki/pages/MediaWiki/Gadget-mcw-common.css   MediaWiki:Common.css + Gadget-site-styles.css
  wiki/pages/MediaWiki/Gadget-mcw-vector.css   MediaWiki:Vector.css + Vector-theme-dark.css + gadget CSS

MediaWiki:Common.css and MediaWiki:Vector.css in this repo @import these and then apply
Matcha Flavoured's own branding and component styles on top. Rerun to pick up upstream
changes; the result is committed. minecraft.wiki content is CC BY-NC-SA 3.0.
"""
import os
import re
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'site', 'assets', 'mcw')
PAGES = os.path.join(ROOT, 'wiki', 'pages', 'MediaWiki')
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/130 Safari/537.36'}
BASE = 'https://minecraft.wiki'


def get(url, binary=False):
    # curl rather than urllib: the site's bot protection rejects Python's TLS client
    import subprocess
    r = subprocess.run(['curl', '-sfL', '-A', UA['User-Agent'], url], capture_output=True, timeout=120)
    if r.returncode != 0:
        raise IOError('HTTP error for %s' % url)
    return r.stdout if binary else r.stdout.decode('utf-8')


def raw(title):
    return get(BASE + '/index.php?title=' + urllib.parse.quote(title) + '&action=raw')


def gadget_css(module):
    return get(BASE + '/load.php?lang=en&only=styles&skin=vector&modules=' + module)


def localise(css):
    """filepath://X.png and /images/X.png -> /assets/mcw/X.png (downloaded)."""
    os.makedirs(ASSETS, exist_ok=True)

    def fetch_image(name):
        name = urllib.parse.unquote(name).replace(' ', '_')
        dest = os.path.join(ASSETS, name)
        if not os.path.exists(dest):
            try:
                data = get(BASE + '/images/' + urllib.parse.quote(name), binary=True)
                with open(dest, 'wb') as f:
                    f.write(data)
            except Exception as e:
                print('  missing image', name, e)
                return None
        return '/assets/mcw/' + urllib.parse.quote(name)

    def repl(m):
        q, url = m.group(1), m.group(2)
        name = None
        if url.startswith('filepath://'):
            name = url[len('filepath://'):]
        elif url.startswith('/images/'):
            name = url.split('?')[0].rsplit('/', 1)[-1]
        if not name:
            return m.group(0)
        local = fetch_image(name.split('?')[0])
        return 'url(%s%s%s)' % (q, local, q) if local else m.group(0)
    return re.sub(r'''url\(\s*(['"]?)([^'")]+)\1\s*\)''', repl, css)


def main():
    parts = {
        'Gadget-mcw-common.css': [('MediaWiki:Common.css', raw), ('MediaWiki:Gadget-site-styles.css', raw)],
        'Gadget-mcw-vector.css': [('MediaWiki:Vector.css', raw), ('MediaWiki:Vector-theme-dark.css', raw),
                           ('ext.gadget.darkmode', gadget_css), ('ext.gadget.stickyToc', gadget_css),
                           ('ext.gadget.sound-styles', gadget_css)],
    }
    for out, sources in parts.items():
        chunks = ['/* Vendored from minecraft.wiki by tools/vendor_mcw_skin.py. Do not edit; rerun the script.\n'
                  ' * Source pages: %s. Licensed CC BY-NC-SA 3.0 by the Minecraft Wiki. */' % ', '.join(s for s, _ in sources)]
        for src, fn in sources:
            print('fetching', src)
            chunks.append('\n/* ===== %s ===== */\n' % src + localise(fn(src)))
        with open(os.path.join(PAGES, out), 'w', encoding='utf-8') as f:
            f.write('\n'.join(chunks))
    print('images:', len(os.listdir(ASSETS)))


if __name__ == '__main__':
    main()
