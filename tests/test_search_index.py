"""Search data from the static export: each page's picture, and the title search's rows."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import search_index

BODY = '<div id="mw-content-text" data-pagefind-body>%s<div class="printfooter"></div></div>'


class PageImageTests(unittest.TestCase):
    def image(self, html, title='Page'):
        return search_index.page_image(html, title)

    def test_item_icon_first(self):
        doc = BODY % ('<div class="infobox-imagearea"><img src="/images/a/aa/Render.png"></div>'
                      '<div class="infobox-invimages"><span><img src="/images/b/bb/Obol.png?v=1"></span></div>')
        self.assertEqual(self.image(doc), '/images/b/bb/Obol.png?v=1')

    def test_infobox_picture_for_mobs_and_structures(self):
        doc = BODY % '<div class="infobox-imagearea animated-container"><img src="/images/9/98/Blaze_render.png"></div>'
        self.assertEqual(self.image(doc), '/images/9/98/Blaze_render.png')

    def test_file_named_after_the_page(self):
        doc = BODY % ('<p><img src="/images/1/11/Anvil.png"> text</p><p><img src="/images/c/c7/Fishing_Rod.png"></p>')
        self.assertEqual(self.image(doc, 'Fishing Rod'), '/images/c/c7/Fishing_Rod.png')

    def test_thumbnail_in_the_article(self):
        doc = BODY % ('<p><img src="/images/1/11/Anvil.png"></p>'
                      '<figure typeof="mw:File/Thumb"><img src="/images/5/56/Chainmail_armor_render.png"></figure>')
        self.assertEqual(self.image(doc, 'Chainmail armor'), '/images/5/56/Chainmail_armor_render.png')

    def test_inline_icons_are_not_the_page_picture(self):
        # Enchanting's first image is a prayer's icon in a table: no picture beats a wrong one
        doc = BODY % '<table><tr><td><img src="/images/1/19/Prayer_of_Aeolus.png"></td></tr></table>'
        self.assertIsNone(self.image(doc, 'Enchanting'))


class RowsTests(unittest.TestCase):
    def test_rows(self):
        out = tempfile.mkdtemp()
        pages = {
            'Armor': {'url': '/w/Armor', 'image': None, 'desc': 'Armor comes in sets.', 'kind': 'article',
                      'links': {'Obol', 'Mud kiln'}},
            'Obol': {'url': '/w/Obol', 'image': '/images/8/8f/Obol.png', 'desc': '', 'kind': 'article', 'links': {'Armor'}},
            'Mud Kiln': {'url': '/w/Mud_Kiln', 'image': None, 'desc': '', 'kind': 'article', 'links': {'Obol', 'Mud Kiln'}},
            'Category:Food': {'url': '/w/Category:Food', 'image': None, 'desc': '', 'kind': 'category', 'links': {'Obol'}},
        }
        redirects = {'Armour': '/w/Armor', 'Emerald': '/w/Obol', 'Hearts': '/w/Health#Maximum', 'Kiln': '/w/Mud_Kiln#Use'}
        rows = search_index.write(out, pages, redirects, {'Mud kiln': 'Mud Kiln'})
        self.assertEqual(rows, json.loads(Path(out, '_static', 'search-titles.json').read_text()))
        by = {r['t']: r for r in rows}
        self.assertEqual([r['t'] for r in rows], sorted(pages))
        self.assertEqual(by['Armor'], {'t': 'Armor', 'u': '/w/Armor', 'd': 'Armor comes in sets.', 'n': 1, 'a': ['Armour']})
        self.assertEqual(by['Obol']['n'], 3)              # linked from three other pages
        self.assertEqual(by['Mud Kiln']['n'], 1)          # the case redirect counts; its own link does not
        self.assertEqual(by['Mud Kiln']['a'], [['Kiln', 'Use']])
        self.assertEqual(by['Category:Food']['k'], 'category')
        self.assertNotIn('Health', by)                    # redirects to pages that aren't exported are dropped


if __name__ == '__main__':
    unittest.main()
