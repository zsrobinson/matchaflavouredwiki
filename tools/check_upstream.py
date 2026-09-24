#!/usr/bin/env python3
"""Cheap daily check: has anything the wiki is built from changed upstream?

Compares the live upstream state with what the wiki was last updated against (the releases and videos in
tools/upstream.json) and prints a JSON report. Exit codes:
  0  nothing changed: stop here
  10 something changed: run the update procedure in AUTOPILOT.md
  2  a source could not be checked (network etc.); retry tomorrow, don't update

Watched sources:
  - Modrinth versions of matcha-flavoured: new releases. The wiki describes the newest release, the
    version players download, pinned to the commit it was made from (tools/release_commit.py). Commits
    on the repository's main between releases are unreleased work and don't count as a change.
  - the developer's YouTube uploads (Klei_Wright): new videos, which may explain design changes
The report also lists the repository's branches (`branches`, e.g. a port to the next Minecraft version).
They don't count as a change; AUTOPILOT.md rehearses ports with tools/dry_run.sh.

  tools/check_upstream.py                 report only
  tools/check_upstream.py --record REPORT after a successful update: mark the releases and videos in
                                          REPORT (this script's earlier output) as done. It records what
                                          the update handled, not what upstream has now: anything that
                                          appeared during the update is still new tomorrow.
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'tools', 'upstream.json')
LOCK = os.path.join(ROOT, 'tools', 'source.lock')
REPO = 'https://github.com/kleiwright/matcha-flavoured.git'
MODRINTH = 'https://api.modrinth.com/v2/project/matcha-flavoured/version'
CHANNEL = 'https://www.youtube.com/@kleiwright/videos'


def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True).stdout


def upstream():
    heads = dict(reversed(line.split('\t')) for line in run(['git', 'ls-remote', '--heads', REPO]).splitlines())
    branches = {ref[len('refs/heads/'):]: sha for ref, sha in heads.items()}
    req = urllib.request.Request(MODRINTH, headers={'User-Agent': 'matchaflavouredwiki-autopilot'})
    versions = json.load(urllib.request.urlopen(req, timeout=60))
    releases = sorted(({'id': v['id'], 'version': v['version_number'], 'name': v['name'],
                        'date': v['date_published'], 'loaders': v['loaders']} for v in versions),
                      key=lambda v: v['date'])
    try:
        out = run(['yt-dlp', '--flat-playlist', '--print', '%(id)s\t%(title)s', CHANNEL], timeout=300)
        videos = [dict(zip(('id', 'title'), line.split('\t', 1))) for line in out.splitlines() if '\t' in line]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        videos = None  # YouTube unreachable: skip this source today (a missing yt-dlp is an error)
    return {'branches': branches, 'modrinth': releases, 'videos': videos}


def record(state, report_path):
    """Mark what an update handled as done. The pack commit needs no record: it is tools/source.lock."""
    report = json.load(open(report_path))
    if report.get('status') not in ('changed', 'unchanged'):
        sys.exit('check_upstream.py: %s is not a report from this script' % report_path)
    state = {'modrinth_versions': sorted(set(state.get('modrinth_versions', [])) |
                                         {r['id'] for r in report['new_releases']}),
             'videos': sorted(set(state.get('videos', [])) | {v['id'] for v in report['new_videos']}),
             'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    with open(STATE, 'w') as f:
        json.dump(state, f, indent=1)
        f.write('\n')
    print('recorded upstream state')
    return 0


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if '--record' in sys.argv:
        args = sys.argv[sys.argv.index('--record') + 1:]
        if not args:
            sys.exit('usage: check_upstream.py --record REPORT  (the JSON this script printed before the update)')
        return record(state, args[0])
    try:
        now = upstream()
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}))
        return 2
    known_versions = set(state.get('modrinth_versions', []))
    known_videos = set(state.get('videos', []))
    report = {
        'pinned_commit': open(LOCK).read().strip(),  # the commit the wiki is built from
        'new_releases': [r for r in now['modrinth'] if r['id'] not in known_versions],
        'new_videos': [v for v in (now['videos'] or []) if v['id'] not in known_videos],
        'videos_checked': now['videos'] is not None,
        'branches': now['branches'],
    }
    changed = report['new_releases'] or report['new_videos']
    report['status'] = 'changed' if changed else 'unchanged'
    print(json.dumps(report, indent=1))
    return 10 if changed else 0


if __name__ == '__main__':
    sys.exit(main())
