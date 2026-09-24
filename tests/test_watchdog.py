"""The watchdog's checks (tools/watchdog.py), on fixtures: no network."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import watchdog

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
TREE = 'a' * 40


def version(id, number, days_ago):
    return {'id': id, 'version_number': number, 'date_published': (NOW - timedelta(days=days_ago)).isoformat().replace('+00:00', 'Z')}


class ReleaseTests(unittest.TestCase):
    VERSIONS = [version('old', '1.12', 40), version('new', '1.13', 5)]

    def test_every_version_handled(self):
        errors, notes = watchdog.check_release(self.VERSIONS, {'old', 'new'}, NOW)
        self.assertEqual(errors, [])
        self.assertIn('1.13', notes[0])

    def test_new_release_within_grace(self):
        errors, notes = watchdog.check_release(self.VERSIONS, {'old'}, NOW - timedelta(days=3))
        self.assertEqual(errors, [])
        self.assertIn('grace', notes[0])

    def test_stale_release_fails(self):
        errors, _ = watchdog.check_release(self.VERSIONS, {'old'}, NOW)
        self.assertEqual(len(errors), 1)
        self.assertIn('1.13', errors[0])
        self.assertIn('5.0 days', errors[0])

    def test_oldest_unhandled_release_counts(self):
        # a second release the day before the check doesn't restart the clock
        versions = self.VERSIONS + [version('newer', '1.13.1', 1)]
        errors, _ = watchdog.check_release(versions, {'old'}, NOW)
        self.assertIn('1.13 ', errors[0])
        self.assertIn('1.13.1 (newer)', errors[0])


class StampTests(unittest.TestCase):
    def test_match(self):
        errors, notes = watchdog.check_stamp({'tree': TREE, 'source_commit': 'f' * 40}, TREE, NOW - timedelta(days=9), NOW)
        self.assertEqual(errors, [])
        self.assertIn('serves main', notes[0])

    def test_mismatch_within_grace(self):
        errors, notes = watchdog.check_stamp({'tree': 'b' * 40}, TREE, NOW - timedelta(minutes=30), NOW)
        self.assertEqual(errors, [])
        self.assertIn('grace', notes[0])

    def test_mismatch_after_grace_fails(self):
        errors, _ = watchdog.check_stamp({'tree': 'b' * 40}, TREE, NOW - timedelta(hours=3), NOW)
        self.assertEqual(len(errors), 1)
        self.assertIn('serves tree bbbbbbbbbb, but main is tree aaaaaaaaaa', errors[0])
        self.assertIn('deploy.yml', errors[0])

    def test_missing_stamp_fails_clearly(self):
        errors, _ = watchdog.check_stamp(None, TREE, NOW - timedelta(hours=3), NOW)
        self.assertIn('has no build stamp (/_static/build.json)', errors[0])

    def test_unreadable_stamp_is_a_mismatch(self):
        errors, _ = watchdog.check_stamp({}, TREE, NOW - timedelta(hours=3), NOW)
        self.assertEqual(len(errors), 1)

    def test_written_stamp_names_the_checkout(self):
        out = tempfile.mkdtemp()
        watchdog.write_stamp(out)
        stamp = json.loads((Path(out) / '_static' / 'build.json').read_text())
        self.assertEqual(stamp['tree'], watchdog.git('rev-parse', 'HEAD^{tree}'))
        self.assertEqual(stamp['source_commit'], open(watchdog.LOCK).read().strip())


class PageTests(unittest.TestCase):
    def test_all_ok(self):
        self.assertEqual(watchdog.check_pages({'/': 200, '/w/Food': 200})[0], [])

    def test_down(self):
        errors, _ = watchdog.check_pages({'/': 200, '/w/Food': 404, '/search/': '<urlopen error timed out>'})
        self.assertEqual(len(errors), 2)
        self.assertIn('/w/Food answers 404', errors[0])


class DeployRunTests(unittest.TestCase):
    def run_(self, conclusion, status='completed', sha='1234567890'):
        return {'status': status, 'conclusion': conclusion, 'head_sha': sha, 'html_url': 'https://github.com/x/runs/1'}

    def test_success(self):
        self.assertEqual(watchdog.check_deploy_runs([self.run_('success')])[0], [])

    def test_failure(self):
        errors, _ = watchdog.check_deploy_runs([self.run_('failure'), self.run_('success')])
        self.assertIn('ended "failure"', errors[0])

    def test_running_and_cancelled_runs_are_skipped(self):
        runs = [self.run_(None, status='in_progress'), self.run_('cancelled'), self.run_('success')]
        self.assertEqual(watchdog.check_deploy_runs(runs)[0], [])
        runs[2] = self.run_('failure')
        self.assertEqual(len(watchdog.check_deploy_runs(runs)[0]), 1)


if __name__ == '__main__':
    unittest.main()
