"""Regression tests for canonical targets and utility pages."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import seo


class SEOTests(unittest.TestCase):
    def test_chain_preserves_final_fragment_and_home(self):
        aliases = {'Old': '/w/Middle#old', 'Middle': '/w/Target#section', 'Main_Page': '/w/Matcha_Flavoured_Wiki'}
        result = seo.resolve_redirects(aliases, ['Target', 'Matcha Flavoured Wiki'])
        self.assertEqual(result['Old'], '/w/Target#section')
        self.assertEqual(result['Main_Page'], '/')

    def test_fragment_survives_when_next_hop_has_none(self):
        self.assertEqual(seo.resolve_redirects({'A': '/w/B#part', 'B': '/w/Target'}, ['Target'])['A'], '/w/Target#part')

    def test_target_case_and_encoding(self):
        self.assertEqual(seo.resolve_redirects({'A': '/w/mud_kiln'}, ['Mud Kiln'])['A'], '/w/Mud_Kiln')

    def test_invalid_redirects_stop_export(self):
        for redirects in ({'A': '/w/A'}, {'A': '/w/B', 'B': '/w/A'}, {'A': '/w/Missing'}):
            with self.subTest(redirects=redirects), self.assertRaises(ValueError):
                seo.resolve_redirects(redirects, ['Target'])

    def test_utility_pages_do_not_inherit_homepage_signals(self):
        doc = seo.apply('<html><head><title>Home</title></head><body><h1>Search</h1></body></html>',
                        'Matcha Flavoured Wiki', {'is_main': True})
        utility = seo.utility_page(doc, 'Search results')
        self.assertIn('noindex, follow', utility)
        self.assertNotIn('rel="canonical"', utility)
        self.assertNotIn('application/ld+json', utility)
        self.assertNotIn('og:', utility)
        self.assertIn('<title>Search results – Matcha Flavoured Wiki</title>', utility)
        self.assertIn('<h1>Search</h1>', utility)


if __name__ == '__main__':
    unittest.main()
