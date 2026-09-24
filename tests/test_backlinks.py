"""What links here (tools/backlinks.py): which links count, and the list MediaWiki would show."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import backlinks


def href(title):
    return '/w/' + title.replace(' ', '_')


def page(content, before='', after=''):
    return ('<div id="p-Navigation"><a href="/w/Food">Food</a></div>' + before +
            '<div id="mw-content-text" class="mw-body-content">' + content +
            '<div class="printfooter">Retrieved from <a href="/w/Bread">x</a></div></div>'
            '<div id="catlinks"><a href="/w/Category:Food">Food</a></div>' + after)


class BacklinkTests(unittest.TestCase):
    def test_links_count_the_body_and_navboxes_only(self):
        doc = page('<p><a href="/w/Mud_Kiln#Recipes">kiln</a> <a href="/w/Pickles_%26_Jam">jam</a> <a href="/">home</a> '
                   '<a href="/w/Special:Random">random</a> <a href="#top">top</a> <a href="https://minecraft.wiki/w/Bread">x</a></p>'
                   '<table class="navbox"><tr><td><a href="/w/Obol?x=1">Obol</a></td></tr></table>')
        self.assertEqual(backlinks.links(doc), {'Mud Kiln', 'Pickles & Jam', 'Matcha Flavoured Wiki', 'Obol'})

    def test_category_member_lists_are_not_links(self):
        doc = page('<p>Things to eat. See <a href="/w/Cooking">Cooking</a>.</p>'
                   '<div id="mw-subcategories"><a href="/w/Category:Soups">Soups</a></div>'
                   '<div id="mw-pages"><a href="/w/Bread">Bread</a></div>')
        self.assertEqual(backlinks.links(doc), {'Cooking'})

    def test_invert_lists_linking_pages_and_redirects_but_not_self_links(self):
        rows = backlinks.invert({'Bread': {'Bread', 'Oven'}, 'Oven': {'Bread'}, 'apple': {'Bread'}, 'Category:Food': {'Bread'}},
                                {'Loaf': 'Bread', 'Stove': 'Oven', 'Gone': 'Missing'})
        self.assertEqual(rows['Bread'], [('apple', False), ('Category:Food', False), ('Loaf', True), ('Oven', False)])
        self.assertEqual(rows['Oven'], [('Bread', False), ('Stove', True)])
        self.assertEqual(rows['apple'], [])
        self.assertNotIn('Missing', rows)

    def test_body_is_mediawikis_list(self):
        out = backlinks.body('Bread', [('Oven', False), ('Loaf', True)], href)
        self.assertIn('The following pages link to <a href="/w/Bread" title="Bread">Bread</a>:', out)
        self.assertIn('<ul id="mw-whatlinkshere-list">', out)
        self.assertIn('<a href="/w/Special:WhatLinksHere/Oven" title="Special:WhatLinksHere/Oven">← links</a>', out)
        self.assertIn('<a href="/w/Loaf" class="mw-redirect" title="Loaf">Loaf</a> (redirect page)</li>', out)
        self.assertNotIn('Special:WhatLinksHere/Loaf', out)

    def test_nothing_links_here(self):
        self.assertEqual(backlinks.body('Pickles & Jam', [], href),
                         '<p>No pages link to <a href="/w/Pickles_&amp;_Jam" title="Pickles &amp; Jam">Pickles &amp; Jam</a>.</p>')


if __name__ == '__main__':
    unittest.main()
