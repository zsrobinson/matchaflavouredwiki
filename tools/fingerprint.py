"""Cache busting for the static export (tools/export_static.py runs this last).

Every reference a page or stylesheet makes to a file of the site (/_rl/, /_static/, /assets/,
/images/, /pagefind/) gets ?v=<hash of that file's content>. The Worker (src/worker.js) serves
those URLs as cacheable for a year; everything else, pages included, revalidates on every view
(the Cache-Control in seo.py's _headers). A changed file is a new URL, so a browser can never pair
a new page or script with an old stylesheet, and an unchanged one is never downloaded twice.

The hashes come from the files' contents, so an unchanged site exports byte for byte the same.
"""
import hashlib
import os
import re
import urllib.parse

DIRS = ('_rl', '_static', 'assets', 'images', 'pagefind')
# a site-relative URL opening an attribute value, a url(), or a srcset entry; any query it had is replaced
REF = re.compile(r'''(?<=["'(\s,])(/(?:%s)/[^\s"'()<>?#,]+)(?:\?[^\s"'()<>#,]*)?''' % '|'.join(DIRS))


def file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.sha1(f.read()).hexdigest()[:10]


def versioned(text, hashes):
    """text with each reference to a known file carrying ?v=<its hash>."""
    def repl(m):
        h = hashes.get(urllib.parse.unquote(m.group(1)))
        return '%s?v=%s' % (m.group(1), h) if h else m.group(0)
    return REF.sub(repl, text)


def walk(out, dirs=None):
    for top in ([os.path.join(out, d) for d in dirs] if dirs else [out]):
        for root, _, files in os.walk(top):
            for name in files:
                yield os.path.join(root, name)


def rewrite(path, hashes):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    new = versioned(text, hashes)
    if new != text:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new)


def site_url(out, path):
    return '/' + os.path.relpath(path, out).replace(os.sep, '/')


def apply(out):
    """Version every reference in dist's stylesheets, then in its pages. Stylesheets go first:
    they point at images, and their own hashes must cover those references."""
    files = list(walk(out, DIRS))
    leaves = {site_url(out, p): file_hash(p) for p in files if not p.endswith('.css')}
    for p in files:
        if p.endswith('.css'):
            rewrite(p, leaves)
    hashes = {site_url(out, p): file_hash(p) for p in files}
    for p in walk(out):
        if p.endswith('.html'):
            rewrite(p, hashes)
    return len(hashes)
