#!/usr/bin/env python3
"""Render structures, mobs and armor from the pack's files into wiki/renders/ (committed).

Every render is an entry in tools/renders.json; its key is the wiki file name (File:<key>.png).
A render is redrawn only when its inputs change: the entry itself, the pinned pack and Minecraft
versions, or the renderer's code. The hashes are kept in wiki/renders/inputs.json.

  python3 tools/render.py              render what is missing or out of date
  python3 tools/render.py Abbey ...    only renders whose name contains one of the words
  python3 tools/render.py --force      redraw everything
  python3 tools/render.py --check      list out-of-date, missing and unused renders; exit 1 if any
  python3 tools/render.py --audit      list pages and pack templates that should have a picture and
                                       don't (the rules in wiki/STYLE.md, "Pictures"); exit 1 if any

Needs Node and a Chromium (the first run installs tools/render's npm packages; set MFW_CHROMIUM
to a Chromium binary if Playwright's browsers aren't installed). The drawing is done by
tools/render/render.mjs in WebGL; see tools/render/src/ for the structure, jigsaw and entity code.
"""
import glob
import hashlib
import json
import os
import re
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
ZOOM = 2  # files are kept at twice an entry's width, so they stay sharp in the image viewer and on dense screens


def zoom(entry):
    """How many times its entry's width a render's file is: structures carry the most detail, so a whole
    structure gets 4 and a piece 3; mobs and armor get ZOOM. Pages show a copy at the entry's width
    (tools/images.py), so this changes only what the image viewer shows."""
    if entry.get('kind') == 'structure':
        return 4 if 'jigsaw' in entry else 3
    return ZOOM


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
    """Trim the transparent border and scale the supersampled drawing down to its final width (zoom() times the
    entry's width, or less once the border is trimmed)."""
    im = Image.open(raw).convert('RGBA')
    bbox = im.getchannel('A').getbbox()
    if bbox:
        im = im.crop(bbox)
    w = min(width, im.width // SUPERSAMPLE) if width else im.width // SUPERSAMPLE
    im = im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)
    im.save(dest, optimize=True)


# ---- coverage audit: which pages and templates should have a picture (wiki/STYLE.md, "Pictures")

MOB = re.compile(r'\bmob\b|\[\[Villager\]\] profession', re.I)
STRUCTURE = re.compile(r'structure', re.I)
INFOBOX_TYPE = re.compile(r'\{\{Infobox\b[^}]*?\|\s*type\s*=\s*([^\n|]*)', re.S)
INFOBOX_IMAGE = re.compile(r'\{\{Infobox\b[^}]*?\|\s*image\s*=\s*[^\s|}]', re.S)


def pages():
    """Title -> text for every article, the hand-written page winning over the generated one."""
    out = {}
    for d in ('generated', 'pages'):
        for f in glob.glob(os.path.join(ROOT, 'wiki', d, 'Main', '*.wiki')):
            out[os.path.basename(f)[:-5].replace('%2F', '/')] = open(f, encoding='utf-8').read()
    return out


def pack_templates():
    base = os.path.join(ROOT, 'source', 'matcha-flavoured', 'MF_datapack', 'data')
    ids = []
    for f in glob.glob(os.path.join(base, '*', 'structure', '**', '*.nbt'), recursive=True):
        ns, _, rel = os.path.relpath(f, base).partition(os.sep + 'structure' + os.sep)
        ids.append(f'{ns}:{rel[:-4]}'.replace(os.sep, '/'))
    return sorted(ids)


def audit():
    """Everything the picture rules ask for that is neither rendered nor skipped with a reason."""
    manifest = json.load(open(MANIFEST, encoding='utf-8'))
    renders, skip = manifest['renders'], manifest.get('skip', {})
    text = pages()
    used = {n for n in renders if any(n + '.png' in t for t in text.values())}
    gaps = []
    for title, t in sorted(text.items()):
        m = INFOBOX_TYPE.search(t)
        kind = m and m.group(1)
        if kind and (MOB.search(kind) or STRUCTURE.search(kind)) and not INFOBOX_IMAGE.search(t):
            gaps.append((title, 'mob' if MOB.search(kind) else 'structure', 'no picture in the infobox'))
        if re.search(r'(equipment|armor)$', title) and '=== Armor ===' in t and not re.search(r'armor render\.png', t):
            gaps.append((title, 'armor set', 'no armor render in === Armor ==='))
    shown = set()
    for n in used:
        tpl = renders[n].get('template')
        shown.update(tpl if isinstance(tpl, list) else [tpl] if tpl else [])
    templates = pack_templates()
    for tpl in templates:
        if tpl not in shown:
            gaps.append(('template:' + tpl, 'structure piece', 'not shown in any gallery'))
    todo = [g for g in gaps if g[0] not in skip]
    unused = sorted(set(renders) - used)
    stale_skips = sorted(k for k in skip if k not in {g[0] for g in gaps})
    return todo, unused, stale_skips, skip, templates


def print_audit():
    todo, unused, stale_skips, skip, templates = audit()
    for key, kind, why in todo:
        print(f'needs a picture: {key} ({kind}: {why})')
    for n in unused:
        print(f'unused render: {n} (no page shows it; remove it from tools/renders.json or use it)')
    for k in stale_skips:
        print(f'stale skip: {k} (it has a picture now, or no longer exists; remove it from "skip")')
    by_reason = {}
    for k, why in skip.items():
        by_reason.setdefault(why, []).append(k)
    print(f'{len(skip)} skipped, by reason:')
    for why, keys in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
        print(f'  {len(keys):3}  {why}')
    if not templates:
        print('(source/ is missing: run tools/fetch_sources.sh to audit the structure templates too)')
    if todo or unused or stale_skips:
        print('For each: add a render (tools/renders.json) and show it on the page, or add the key to '
              '"skip" in tools/renders.json with the reason. See wiki/STYLE.md, "Pictures".')
        sys.exit(1)
    print('picture coverage complete')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--audit' in sys.argv:
        return print_audit()
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
    jobs = [dict(renders[n], name=n, width=renders[n].get('width', 400) * zoom(renders[n]) * SUPERSAMPLE) for n in todo]
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
            finish(os.path.join(tmp, r['name'] + '.png'), os.path.join(OUT, r['name'] + '.png'), renders[r['name']].get('width', 400) * zoom(renders[r['name']]))
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
