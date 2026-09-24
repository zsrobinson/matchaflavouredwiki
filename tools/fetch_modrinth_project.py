#!/usr/bin/env python3
"""Save the Modrinth project page of Matcha Flavoured (its description and gallery captions) to
sources/modrinth_project.md (committed: the developer's own words, a primary source like the videos).

  tools/fetch_modrinth_project.py            fetch and write the file; `git diff sources/modrinth_project.md`
                                             then shows exactly what the developer changed
  tools/fetch_modrinth_project.py --check    exit 10 if the live page differs from the file, 0 if not

Only what the developer writes is kept (title, summary, body, gallery titles and captions, links). Counters,
timestamps and the version list, which change on their own (downloads, "updated", each release), are left
out, so the file changes only when the text does. tools/check_upstream.py uses snapshot() to report a change.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sources', 'modrinth_project.md')
API = 'https://api.modrinth.com/v2/project/matcha-flavoured'
PAGE = 'https://modrinth.com/datapack/matcha-flavoured'


def snapshot():
    """The project page as markdown, from the Modrinth API."""
    req = urllib.request.Request(API, headers={'User-Agent': 'matchaflavouredwiki-autopilot'})
    p = json.load(urllib.request.urlopen(req, timeout=60))
    md = ['<!-- Saved by tools/fetch_modrinth_project.py from %s (%s). Don\'t edit by hand. -->' % (API, PAGE), '',
          '# %s' % p['title'], '', '> %s' % p['description'].strip(), '',
          '## Description', '', p['body'].replace('\r\n', '\n').strip(), '', '## Gallery', '']
    # Modrinth returns the gallery in no fixed order: sort by its ordering, then by upload time
    for g in sorted(p.get('gallery') or [], key=lambda g: (g.get('ordering', 0), g.get('created', ''))):
        md += ['### %s' % (g.get('title') or '(untitled)'), '',
               (g.get('description') or '').strip() or '(no caption)', '',
               '- Image: %s' % (g.get('raw_url') or g.get('url')),
               '- Uploaded: %s%s' % ((g.get('created') or '')[:10], ', featured' if g.get('featured') else ''), '']
    links = [(k, p.get(k)) for k in ('source_url', 'issues_url', 'wiki_url', 'discord_url') if p.get(k)]
    links += [('donation: ' + d.get('platform', d.get('id', '')), d.get('url')) for d in p.get('donation_urls') or []]
    if links:
        md += ['## Links', ''] + ['- %s: %s' % kv for kv in links] + ['']
    md += ['## Project', '', '- License: %s' % (p.get('license') or {}).get('id'),
           '- Categories: %s' % ', '.join((p.get('categories') or []) + (p.get('additional_categories') or []))]
    return '\n'.join(md) + '\n'


def saved():
    return open(OUT, encoding='utf-8').read() if os.path.exists(OUT) else ''


def main():
    text = snapshot()
    if '--check' in sys.argv:
        return 10 if text != saved() else 0
    changed = text != saved()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)
    print('%s: %s' % (os.path.relpath(OUT, ROOT), 'changed (read `git diff %s`)' % os.path.relpath(OUT, ROOT)
                      if changed else 'unchanged'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
