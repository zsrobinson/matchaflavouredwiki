#!/usr/bin/env python3
"""Find the commit of the pack's repository that a Modrinth release was made from.

The wiki describes the release players download, not the newest commit on main. Upstream doesn't tag
releases, but a release is only a zip of the pack's folders, so its files identify the commit: this
downloads the release's zips and compares every file under data/ and assets/ with each commit
(all branches, the 60 days before publishing). The zips are made on Windows, so text files are
compared with Unix line endings.

  tools/release_commit.py                 the newest release (any type: release, beta or alpha)
  tools/release_commit.py 1.12.1-alpha    a given version number

Prints the commit (the newest one with identical files, committed before the release was published) and
exits 0. Exits 1 when no commit matches exactly and lists the closest ones: the release was then made
from files that were never committed, and a person has to decide. Exits 2 on network errors.
Needs source/matcha-flavoured (tools/fetch_sources.sh); fetch it first so every branch is current.
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.request
import zipfile
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.join(ROOT, 'source', 'matcha-flavoured')
MODRINTH = 'https://api.modrinth.com/v2/project/matcha-flavoured/version'
# where each top-level folder of a release zip lives in the repository (the second is the layout
# before 2026-09-07, when the repository had one combined pack)
LAYOUTS = [{'data': 'MF_datapack/data', 'assets': 'MF_resourcepack/assets'},
           {'data': 'Matcha_Flavoured/data', 'assets': 'Matcha_Flavoured/assets'}]


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'matchaflavouredwiki-autopilot'})
    return urllib.request.urlopen(req, timeout=120).read()


def git(*args):
    return subprocess.run(['git', '-C', REPO] + list(args), capture_output=True, text=True, check=True).stdout


def blob_id(data):
    if b'\0' not in data[:8000]:
        data = data.replace(b'\r\n', b'\n')  # a text file, zipped on Windows
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def release_files(version):
    """{path in zip: git blob id} for data/ and assets/ in every zip of the release."""
    files = {}
    for f in version['files']:
        data = get(f['url'])
        if hashlib.sha1(data).hexdigest() != f['hashes']['sha1']:
            raise IOError('%s: download does not match its sha1' % f['filename'])
        z = zipfile.ZipFile(io.BytesIO(data))
        for info in z.infolist():
            if not info.is_dir() and info.filename.split('/')[0] in ('data', 'assets'):
                files[info.filename] = blob_id(z.read(info))
    return files


TREES = {}


def commit_files(commit, tops):
    """{path as in the zip: blob id} for the given top-level folders, in the first layout that has them."""
    for layout in LAYOUTS:
        out = {}
        for top in tops:
            try:
                tree = git('rev-parse', '%s:%s' % (commit, layout[top])).strip()
            except subprocess.CalledProcessError:
                break
            if tree not in TREES:  # most commits share most trees
                TREES[tree] = {line.split('\t', 1)[1]: line.split()[2]
                               for line in git('ls-tree', '-r', tree).splitlines()}
            out.update({top + '/' + path: blob for path, blob in TREES[tree].items()})
        else:
            return out
    return {}


def main():
    try:
        versions = sorted(json.loads(get(MODRINTH)), key=lambda v: v['date_published'])
    except Exception as e:
        print('release_commit.py: %s' % e, file=sys.stderr)
        return 2
    wanted = sys.argv[1] if len(sys.argv) > 1 else versions[-1]['version_number']
    parts = [v for v in versions if v['version_number'] == wanted]  # a release can be several uploads (datapack, resource pack)
    if not parts:
        print('release_commit.py: no Modrinth version %s' % wanted, file=sys.stderr)
        return 1
    published = max(v['date_published'] for v in parts)
    try:
        files = release_files({'files': [f for v in parts for f in v['files']]})
    except Exception as e:
        print('release_commit.py: %s' % e, file=sys.stderr)
        return 2
    tops = sorted({p.split('/')[0] for p in files})
    when = datetime.fromisoformat(published.replace('Z', '+00:00'))
    commits = git('log', '--all', '--format=%H %cI', '--since', (when - timedelta(days=60)).isoformat(),
                  '--until', (when + timedelta(days=1)).isoformat()).split('\n')
    scored = []
    for line in filter(None, commits):
        commit, date = line.split()
        have = commit_files(commit, tops)
        wrong = sorted({p for p in files if have.get(p) != files[p]} | {p for p in have if p not in files})
        scored.append((len(wrong), datetime.fromisoformat(date) > when, date, commit, wrong))
    exact = [s for s in scored if s[0] == 0]
    if not scored:
        print('release_commit.py: the repository has no commits from the 60 days before %s' % wanted, file=sys.stderr)
        return 1
    if not exact:
        print('release_commit.py: no commit has exactly the files of %s (%d files). Closest:' % (wanted, len(files)),
              file=sys.stderr)
        for n, _, date, commit, wrong in sorted(scored)[:3]:
            print('  %s %s: %d files differ, e.g. %s' % (commit[:8], date, n, ', '.join(wrong[:3])), file=sys.stderr)
        return 1
    # several commits can match (later ones changed only the changelog); take the newest from before publishing
    _, _, date, commit, _ = max(exact, key=lambda s: (not s[1], s[2]))
    print('%s (published %s) = commit %s (%s): all %d files identical' % (wanted, published[:16], commit[:8], date, len(files)),
          file=sys.stderr)
    print(commit)
    return 0


if __name__ == '__main__':
    sys.exit(main())
