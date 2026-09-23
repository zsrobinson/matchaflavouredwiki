#!/usr/bin/env python3
"""Cheap daily check: has anything the wiki is built from changed upstream?

Compares the live upstream state with tools/upstream.json (what the wiki was last updated
against) and prints a JSON report. Exit codes:
  0  nothing changed: stop here
  10 something changed: run the update procedure in AUTOPILOT.md
  2  a source could not be checked (network etc.); retry tomorrow, don't update

Watched sources:
  - the pack's GitHub repository (kleiwright/matcha-flavoured), branch main: new commits
  - Modrinth versions of matcha-flavoured: new releases (release notes)
  - the developer's YouTube uploads (Klei_Wright): new videos, which may explain design changes

  tools/check_upstream.py            report only
  tools/check_upstream.py --record   after a successful update: write the current state to upstream.json
"""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'tools', 'upstream.json')
REPO = 'https://github.com/kleiwright/matcha-flavoured.git'
MODRINTH = 'https://api.modrinth.com/v2/project/matcha-flavoured/version'
CHANNEL = 'https://www.youtube.com/@kleiwright/videos'


def run(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True).stdout


def upstream():
    head = run(['git', 'ls-remote', REPO, 'refs/heads/main']).split()[0]
    req = urllib.request.Request(MODRINTH, headers={'User-Agent': 'matchaflavouredwiki-autopilot'})
    versions = json.load(urllib.request.urlopen(req, timeout=60))
    releases = sorted(({'id': v['id'], 'version': v['version_number'], 'name': v['name'],
                        'date': v['date_published'], 'loaders': v['loaders']} for v in versions),
                      key=lambda v: v['date'])
    try:
        out = run(['yt-dlp', '--flat-playlist', '--print', '%(id)s\t%(title)s', CHANNEL], timeout=300)
        videos = [dict(zip(('id', 'title'), line.split('\t', 1))) for line in out.splitlines() if '\t' in line]
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        videos = None  # yt-dlp missing or YouTube unreachable: skip this source today
    return {'matcha_commit': head, 'modrinth': releases, 'videos': videos}


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    try:
        now = upstream()
    except Exception as e:
        print(json.dumps({'status': 'error', 'error': str(e)}))
        return 2
    if '--record' in sys.argv:
        state = {'matcha_commit': now['matcha_commit'],
                 'modrinth_versions': [r['id'] for r in now['modrinth']],
                 'videos': [v['id'] for v in (now['videos'] or [])] or state.get('videos', []),
                 'recorded_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
        with open(STATE, 'w') as f:
            json.dump(state, f, indent=1)
            f.write('\n')
        print('recorded upstream state')
        return 0
    known_versions = set(state.get('modrinth_versions', []))
    known_videos = set(state.get('videos', []))
    report = {
        'new_commits': now['matcha_commit'] != state.get('matcha_commit'),
        'from_commit': state.get('matcha_commit'),
        'to_commit': now['matcha_commit'],
        'new_releases': [r for r in now['modrinth'] if r['id'] not in known_versions],
        'new_videos': [v for v in (now['videos'] or []) if v['id'] not in known_videos],
        'videos_checked': now['videos'] is not None,
    }
    changed = report['new_commits'] or report['new_releases'] or report['new_videos']
    report['status'] = 'changed' if changed else 'unchanged'
    print(json.dumps(report, indent=1))
    return 10 if changed else 0


if __name__ == '__main__':
    sys.exit(main())
