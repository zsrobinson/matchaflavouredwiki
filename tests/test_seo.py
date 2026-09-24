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

    def test_indexable_page_has_large_share_card(self):
        card = seo.SITE + '/og/0123456789abcdef.png?v=abc'
        tags, _ = seo.head_tags('Crystal Heart', '', {'card': card, 'image': '/images/4/42/Crystal_Heart.png',
                                                      'published': '2026-09-22T00:00:00-04:00', 'lastmod': '2026-09-24T00:00:00-04:00'})
        self.assertIn('<meta property="og:image" content="%s">' % card, tags)
        self.assertIn('<meta property="og:image:width" content="1200">', tags)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', tags)
        self.assertIn('<meta name="robots" content="max-image-preview:large">', tags)
        self.assertIn('"image": ["%s", "%s/images/4/42/Crystal_Heart.png"]' % (card, seo.SITE), tags)
        self.assertIn('"datePublished": "2026-09-22T00:00:00-04:00"', tags)

    def test_noindex_page_keeps_small_preview(self):
        tags, _ = seo.head_tags('Oak Door', '', {'noindex': True, 'image': '/images/a/ab/Oak_Door.png'})
        self.assertIn('<meta name="twitter:card" content="summary">', tags)
        self.assertIn('noindex, follow', tags)
        self.assertNotIn('max-image-preview', tags)
        self.assertNotIn('og:image:width', tags)

    def test_utility_pages_do_not_inherit_homepage_signals(self):
        doc = seo.apply('<html><head><title>Home</title></head><body><h1>Search</h1></body></html>',
                        'Matcha Flavoured Wiki', {'is_main': True, 'card': seo.SITE + '/og/x.png'})
        utility = seo.utility_page(doc, 'Search results')
        self.assertIn('noindex, follow', utility)
        self.assertNotIn('rel="canonical"', utility)
        self.assertNotIn('application/ld+json', utility)
        self.assertNotIn('og:', utility)
        self.assertNotIn('max-image-preview', utility)
        self.assertIn('<title>Search results – Matcha Flavoured Wiki</title>', utility)
        self.assertIn('<h1>Search</h1>', utility)

    def test_hearts_become_words_in_the_description(self):
        heart = '<a href="/w/Health" title="Health"><span class="mf-heart" role="img" aria-label="heart"></span></a>'
        half = '<a href="/w/Health" title="Health"><span class="mf-heart mf-heart-half" role="img" aria-label="half a heart"></span></a>'
        doc = ('<div id="mw-content-text"><p><b>Bread</b> is baked dough. It heals <span class="nowrap">4 (%s × 2)</span>, '
               'a crumb <span class="nowrap">2 (%s × 1)</span> and a seed <span class="nowrap">1 (%s × 0.5)</span>.</p>'
               % (heart, heart, half))
        self.assertEqual(seo.lead_description(doc), 'Bread is baked dough. It heals 4 (2 hearts), a crumb 2 (1 heart) '
                                                    'and a seed 1 (half a heart).')


if __name__ == '__main__':
    unittest.main()
