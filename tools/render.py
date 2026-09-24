#!/usr/bin/env python3
"""Render structures, mobs and armor from the pack's files into wiki/renders/ (committed).

Every render is an entry in tools/renders.json; its key is the wiki file name (File:<key>.png).
A render is redrawn only when its inputs change: the entry itself, the pinned pack and Minecraft
versions, or the renderer's code. The hashes are kept in wiki/renders/inputs.json.

  python3 tools/render.py              render what is missing or out of date
  python3 tools/render.py Abbey ...    only renders whose name contains one of the words
  python3 tools/render.py --force      redraw everything
  python3 tools/render.py --check      list out-of-date, missing and unused renders; exit 1 if any

Needs Node and a Chromium (the first run installs tools/render's npm packages; set MFW_CHROMIUM
to a Chromium binary if Playwright's browsers aren't installed). The drawing is done by
tools/render/render.mjs in WebGL; see tools/render/src/ for the structure, jigsaw and entity code.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'tools', 'renders.json')
OUT = os.path.join(ROOT, 'wiki', 'renders')
INPUTS = os.path.join(OUT, 'inputs.json')
TOOL = os.path.join(ROOT, 'tools', 'render')
SUPERSAMPLE = 2  # drawn at twice the size, then scaled down: smooth edges without MSAA artifacts


def code_hash():
    """The renderer's own code: a change to it redraws everything."""
    h = hashlib.sha1()
    files = [os.path.abspath(__file__)] + [os.path.join(TOOL, f) for f in ('render.mjs', 'package.json', 'package-lock.json')]
    files += sorted(os.path.join(TOOL, 'src', f) for f in os.listdir(os.path.join(TOOL, 'src')))
    for rel in ('tools/source.lock', 'tools/mc_version.txt'):  # these fix every file under source/
        files.append(os.path.join(ROOT, rel))
    for f in files:
        h.update(os.path.relpath(f, ROOT).encode() + b'\0' + open(f, 'rb').read())
    return h.hexdigest()


def entry_hash(name, entry, code):
    return hashlib.sha1((code + name + json.dumps(entry, sort_keys=True)).encode()).hexdigest()


def load():
    renders = json.load(open(MANIFEST, encoding='utf-8'))['renders']
    old = json.load(open(INPUTS)) if os.path.exists(INPUTS) else {}
    code = code_hash()
    want = {name: entry_hash(name, e, code) for name, e in renders.items()}
    return renders, old, want


def status():
    renders, old, want = load()
    stale = [n for n in renders if old.get(n) != want[n] or not os.path.exists(os.path.join(OUT, n + '.png'))]
    unused = sorted(f[:-4] for f in os.listdir(OUT) if f.endswith('.png') and f[:-4] not in renders) if os.path.isdir(OUT) else []
    return renders, old, want, stale, unused


def finish(raw, dest, width):
    """Trim the transparent border and scale the supersampled drawing down to its final width."""
    im = Image.open(raw).convert('RGBA')
    bbox = im.getchannel('A').getbbox()
    if bbox:
        im = im.crop(bbox)
    w = min(width, im.width // SUPERSAMPLE) if width else im.width // SUPERSAMPLE
    im = im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)
    im.save(dest, optimize=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    renders, old, want, stale, unused = status()
    if '--check' in sys.argv:
        for n in stale:
            print('out of date:' if n in old else 'missing:', n)
        for n in unused:
            print('not in tools/renders.json:', n)
        if stale or unused:
            print('Run python3 tools/render.py and commit wiki/renders/.')
            sys.exit(1)
        print('renders up to date (%d)' % len(renders))
        return
    todo = list(renders) if '--force' in sys.argv else stale
    if args:
        todo = [n for n in renders if any(a.lower() in n.lower() for a in args)]
    if not todo:
        print('renders up to date (%d)' % len(renders))
        return
    if not os.path.isdir(os.path.join(TOOL, 'node_modules')):
        subprocess.run(['npm', 'ci' if os.path.exists(os.path.join(TOOL, 'package-lock.json')) else 'install', '--silent'], cwd=TOOL, check=True)
    os.makedirs(OUT, exist_ok=True)
    jobs = [dict(renders[n], name=n, width=renders[n].get('width', 400) * SUPERSAMPLE) for n in todo]
    with tempfile.TemporaryDirectory() as tmp:
        jobs_file = os.path.join(tmp, 'jobs.json')
        json.dump(jobs, open(jobs_file, 'w'))
        proc = subprocess.run(['node', os.path.join(TOOL, 'render.mjs'), jobs_file, tmp], capture_output=True, text=True)
        done = {}
        for line in proc.stdout.splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if 'error' in r:
                print('FAILED', r['name'], r['error'].splitlines()[0])
                continue
            warn = [f'{k}: {r[k]}' for k in ('unknownBlocks', 'missingTextures') if r.get(k)]
            print('rendered', r['name'], *warn)
            finish(os.path.join(tmp, r['name'] + '.png'), os.path.join(OUT, r['name'] + '.png'), renders[r['name']].get('width'))
            done[r['name']] = want[r['name']]
        if proc.returncode and not done:
            sys.stderr.write(proc.stderr[-3000:])
    old = {n: h for n, h in old.items() if n in renders}
    old.update(done)
    with open(INPUTS, 'w') as f:
        json.dump(dict(sorted(old.items())), f, indent=1)
        f.write('\n')
    for n in unused:
        print('not in tools/renders.json (delete it if it is no longer used):', n)
    if len(done) < len(todo):
        sys.exit(1)


if __name__ == '__main__':
    main()
