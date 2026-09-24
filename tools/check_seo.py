#!/usr/bin/env python3
"""Validate exported indexing signals before deployment. No network or dependencies required."""
import argparse
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import seo


class Signals(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.canonicals = []
        self.descriptions = []
        self.noindex = False
        self.og_image = None
        self.icons = []
        self.h1 = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs.get('href', ''))
        if tag == 'link' and attrs.get('rel') == 'icon':
            self.icons.append(attrs.get('href', ''))
        if tag == 'meta' and attrs.get('property') == 'og:image':
            self.og_image = attrs.get('content', '')
        if tag == 'meta':
            if attrs.get('name') == 'description':
                self.descriptions.append(attrs.get('content', ''))
            if attrs.get('name') == 'robots':
                self.noindex |= 'noindex' in attrs.get('content', '').lower()
        if tag == 'h1':
            self.h1 += 1


def check(out):
    out = Path(out)
    errors = []
    indexed = set()
    for path in sorted(out.rglob('*.html')):
        rel = path.relative_to(out).as_posix()
        doc = path.read_text(encoding='utf-8')
        signals = Signals(doc)
        if rel in ('404.html', 'search/index.html') or rel.startswith('w/Special:'):
            if not signals.noindex or signals.canonicals or 'application/ld+json' in doc:
                errors.append('%s: utility page must be noindex without inherited canonical/schema' % rel)
            continue
        if not rel.startswith('w/') and rel != 'index.html':
            continue
        title = rel[2:-5].replace('_', ' ') if rel.startswith('w/') else 'Matcha Flavoured Wiki'
        expected = seo.page_url(title)
        if signals.canonicals != [expected]:
            errors.append('%s: canonical does not match %s' % (rel, expected))
        if len(signals.descriptions) != 1 or not signals.descriptions[0].strip():
            errors.append('%s: missing/duplicate/empty description' % rel)
        if signals.h1 != 1:
            errors.append('%s: expected one h1' % rel)
        if not any(icon.split('?')[0] == '/favicon.ico' for icon in signals.icons):
            errors.append('%s: no link to /favicon.ico' % rel)
        if not signals.noindex:
            indexed.add(expected)
            # link previews and image results use the share card (tools/og.py)
            card = (signals.og_image or '').split('?')[0]
            if not card.startswith(seo.SITE + '/og/') or not (out / card[len(seo.SITE) + 1:]).is_file():
                errors.append('%s: og:image is not an exported share card: %s' % (rel, signals.og_image))
    for required in ('index.html', 'search/index.html', '404.html', 'robots.txt', 'sitemap.xml',
                     'favicon.ico', 'apple-touch-icon.png', 'assets/icon-96.png', 'assets/icon-192.png'):
        if not (out / required).is_file():
            errors.append('Missing %s' % required)
    try:
        urls = [node.text for node in ET.parse(out / 'sitemap.xml').findall('.//{*}loc')]
        errors.extend('Duplicate sitemap URL: %s' % url for url, count in Counter(urls).items() if count > 1)
        errors.extend('Sitemap URL missing or noindex: %s' % url for url in sorted(set(urls) - indexed))
        errors.extend('Indexable page absent from sitemap: %s' % url for url in sorted(indexed - set(urls)))
    except (OSError, ET.ParseError) as error:
        errors.append('Cannot read sitemap: %s' % error)
    robots = (out / 'robots.txt').read_text() if (out / 'robots.txt').exists() else ''
    if 'Sitemap: %s/sitemap.xml' % seo.SITE not in robots:
        errors.append('robots.txt does not advertise the canonical sitemap')
    if 'Disallow: /search/' in robots:
        errors.append('Search must be crawlable so its noindex can be read')
    return errors, len(indexed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', nargs='?', default=str(Path(seo.ROOT) / 'dist'))
    args = parser.parse_args()
    errors, count = check(args.out)
    for error in errors:
        print(error, file=sys.stderr)
    print('%d indexable URLs; %d SEO errors' % (count, len(errors)))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
