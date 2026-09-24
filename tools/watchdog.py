#!/usr/bin/env python3
"""Watchdog: fail loudly when the wiki has gone stale or the site is down.

The wiki is kept current by the daily autopilot routine (AUTOPILOT.md) and published by
.github/workflows/deploy.yml. If the routine stops running or a deploy fails, nothing else would
notice. This script checks only facts anyone can observe from outside, and
.github/workflows/watchdog.yml runs it every day; GitHub emails the repository owner when a
scheduled workflow fails.

It fails (exit 1, one `::error::` line per problem) when:
  - a Modrinth version of the pack that the wiki hasn't handled (not in tools/upstream.json) was
    published more than RELEASE_GRACE ago: the autopilot should have opened, and merged, its PR by then;
  - https://matchaflavou.red isn't serving the build of the checked-out commit (the build stamp,
    /_static/build.json, names another tree, or there is none) more than DEPLOY_GRACE after that
    commit was made;
  - the home page, a key article or the search page doesn't answer 200;
  - the latest finished Build and deploy run on main failed.
Exit 2 means a check couldn't be made (Modrinth or GitHub unreachable); that fails the job too.

  tools/watchdog.py                       run every check against the live site (the checkout must be main)
  tools/watchdog.py --site URL            another deployment, e.g. a PR preview
  tools/watchdog.py --stamp OUT_DIR       write OUT_DIR/_static/build.json (tools/export_static.py does)

The build stamp names the git *tree* the export was built from, not the commit: deploy.yml's fast path
deploys the preview check.yml built from the PR merged into main, a commit that never lands on main
but has exactly the tree of main's squash commit. A tree changes only when a file does, so an unchanged
repository still exports the same bytes.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, 'tools', 'upstream.json')
LOCK = os.path.join(ROOT, 'tools', 'source.lock')
SITE = 'https://matchaflavou.red'
STAMP_PATH = '/_static/build.json'
PAGES = ('/', '/w/Food', '/search/')
MODRINTH = 'https://api.modrinth.com/v2/project/matcha-flavoured/version'
REPO = 'zsrobinson/matchaflavouredwiki'
RELEASE_GRACE = timedelta(days=3)
DEPLOY_GRACE = timedelta(hours=2)
AGENT = 'matchaflavouredwiki-watchdog'


def git(*args):
    return subprocess.run(['git', '-C', ROOT] + list(args), capture_output=True, text=True, check=True).stdout.strip()


def build_stamp():
    """What the export was built from: the repository tree and the pinned pack commit."""
    return {'tree': git('rev-parse', 'HEAD^{tree}'), 'source_commit': open(LOCK).read().strip()}


def write_stamp(out):
    os.makedirs(os.path.join(out, '_static'), exist_ok=True)
    with open(os.path.join(out, STAMP_PATH.lstrip('/')), 'w') as f:
        json.dump(build_stamp(), f, indent=1)
        f.write('\n')


def parse_time(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def age(delta):
    hours = delta.total_seconds() / 3600
    return '%.1f days' % (hours / 24) if hours >= 48 else '%.1f hours' % hours


# Each check returns (errors, notes): errors fail the job, notes are printed as they are.

def check_release(versions, handled, now):
    """versions: Modrinth's version list; handled: the ids in tools/upstream.json."""
    new = sorted((v for v in versions if v['id'] not in handled), key=lambda v: v['date_published'])
    if not new:
        newest = max(versions, key=lambda v: v['date_published']) if versions else None
        return [], ['release: the wiki has handled every Modrinth version' +
                    (' (newest %s, %s)' % (newest['version_number'], newest['date_published'][:10]) if newest else '')]
    oldest = new[0]
    waited = now - parse_time(oldest['date_published'])
    names = ', '.join('%s (%s)' % (v['version_number'], v['id']) for v in new)
    if waited > RELEASE_GRACE:
        return ['release: Modrinth version %s was published %s ago (%s) and the wiki still hasn\'t been updated for it '
                '(not in tools/upstream.json). The autopilot routine has stopped, or its PR is stuck: '
                'look for an open PR labelled autopilot, else run AUTOPILOT.md by hand. Unhandled: %s'
                % (oldest['version_number'], age(waited), oldest['date_published'][:10], names)], []
    return [], ['release: %s published %s ago, within the %s grace for the autopilot' % (names, age(waited), age(RELEASE_GRACE))]


def check_stamp(stamp, tree, committed, now, site=SITE):
    """stamp: the live /_static/build.json (None if missing); tree, committed: main's tree and commit time."""
    waited = now - committed
    if stamp is not None and stamp.get('tree') == tree:
        return [], ['deploy: %s serves main\'s build (tree %s, pack %s)' % (site, tree[:10], (stamp.get('source_commit') or '?')[:10])]
    problem = ('%s has no build stamp (%s)' % (site, STAMP_PATH) if stamp is None else
               '%s serves tree %s, but main is tree %s' % (site, (stamp.get('tree') or '?')[:10], tree[:10]))
    if waited <= DEPLOY_GRACE:
        return [], ['deploy: %s; main changed %s ago, still within the %s deploy grace' % (problem, age(waited), age(DEPLOY_GRACE))]
    return ['deploy: %s, %s after main\'s last commit. Build and deploy failed or never ran: read its log '
            '(https://github.com/%s/actions/workflows/deploy.yml); an expired CLOUDFLARE_API_TOKEN fails there.'
            % (problem, age(waited), REPO)], []


def check_pages(statuses, site=SITE):
    """statuses: {path: HTTP status, or an error message}."""
    bad = {p: s for p, s in statuses.items() if s != 200}
    if not bad:
        return [], ['pages: %s all answer 200' % ', '.join(statuses)]
    return ['pages: %s%s answers %s' % (site, p, s) for p, s in bad.items()], []


def check_deploy_runs(runs):
    """runs: GitHub's workflow runs of deploy.yml on main, newest first. Cancelled runs were superseded
    by a newer push (deploy.yml cancels in progress), so they don't count."""
    done = [r for r in runs if r.get('status') == 'completed' and r.get('conclusion') != 'cancelled']
    if not done:
        return [], ['deploy run: no finished Build and deploy run on main yet']
    last = done[0]
    if last['conclusion'] == 'success':
        return [], ['deploy run: the latest Build and deploy on main succeeded (%s, %s)' % (last['head_sha'][:7], last.get('updated_at', '?'))]
    return ['deploy run: the latest Build and deploy on main ended "%s" (commit %s): %s'
            % (last['conclusion'], last['head_sha'][:7], last.get('html_url', ''))], []


# Fetching

def get(url, headers=None):
    req = urllib.request.Request(url, headers=dict({'User-Agent': AGENT}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read()


def fetch_stamp(site):
    try:
        status, body = get(site + STAMP_PATH, {'Cache-Control': 'no-cache'})
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    try:
        return json.loads(body)
    except ValueError:
        return {}  # something else answered: counts as a mismatch


def fetch_statuses(site):
    statuses = {}
    for path in PAGES:
        try:
            statuses[path] = get(site + path)[0]
        except urllib.error.HTTPError as e:
            statuses[path] = e.code
        except Exception as e:  # DNS, TLS, timeout: the site is down for readers too
            statuses[path] = '%s' % e
    return statuses


def fetch_deploy_runs():
    headers = {'Accept': 'application/vnd.github+json'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    url = 'https://api.github.com/repos/%s/actions/workflows/deploy.yml/runs?branch=main&per_page=20' % REPO
    return json.loads(get(url, headers)[1])['workflow_runs']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default=SITE)
    ap.add_argument('--stamp', metavar='OUT_DIR', help='write the build stamp into an export and exit')
    args = ap.parse_args()
    if args.stamp:
        write_stamp(args.stamp)
        return 0
    site = args.site.rstrip('/')
    now = datetime.now(timezone.utc)
    handled = set(json.load(open(STATE)).get('modrinth_versions', []))
    errors, notes, unreachable = [], [], []

    def run(name, check):
        try:
            found, noted = check()
        except Exception as e:  # a check we couldn't make is a failure too, but a different one
            unreachable.append('%s: could not check: %s' % (name, e))
            return
        errors.extend(found)
        notes.extend(noted)

    run('release', lambda: check_release(json.loads(get(MODRINTH)[1]), handled, now))
    run('deploy', lambda: check_stamp(fetch_stamp(site), git('rev-parse', 'HEAD^{tree}'),
                                      parse_time(git('log', '-1', '--format=%cI')), now, site))
    run('pages', lambda: check_pages(fetch_statuses(site), site))
    run('deploy run', lambda: check_deploy_runs(fetch_deploy_runs()))

    for n in notes:
        print(n)
    for e in errors + unreachable:
        print('::error::' + e)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as f:
            f.write('## Watchdog\n\n' + ''.join('- :x: %s\n' % e for e in errors + unreachable) +
                    ''.join('- :white_check_mark: %s\n' % n for n in notes))
    if errors:
        return 1
    return 2 if unreachable else 0


if __name__ == '__main__':
    sys.exit(main())
