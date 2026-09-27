"""Site icons and share cards (tools/og.py)."""
from pathlib import Path
import io
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import og


class IconTests(unittest.TestCase):
    def test_icons_are_multiples_of_48(self):
        # Google shows a site's favicon only if it is square and a multiple of 48px
        with tempfile.TemporaryDirectory() as out:
            og.site_icons(out)
            for size in (48, 96, 192):
                self.assertEqual(Image.open(os.path.join(out, 'assets', 'icon-%d.png' % size)).size, (size, size))
            self.assertEqual(Image.open(os.path.join(out, 'apple-touch-icon.png')).size, (180, 180))
            self.assertIn((48, 48), Image.open(os.path.join(out, 'favicon.ico')).info['sizes'])
        for name in ('/favicon.ico', '/assets/icon-96.png', '/assets/icon-192.png', '/apple-touch-icon.png'):
            self.assertIn(name, og.ICON_TAGS)

    def test_logo_art_is_the_logo(self):
        art = og.logo_art()
        logo = Image.open(og.LOGO).convert('RGBA')
        self.assertEqual(art.size, logo.size)
        self.assertEqual(art.tobytes(), logo.tobytes())

    def test_non_square_logo_is_centered_without_stretching(self):
        from unittest.mock import patch
        art = Image.new('RGBA', (18, 21), (30, 160, 80, 255))
        with patch.object(og, 'logo_art', return_value=art):
            icon = og.fit_logo(48)
        self.assertEqual(icon.size, (48, 48))
        self.assertEqual(icon.getbbox(), (6, 3, 42, 45))
        self.assertEqual(set(icon.getdata()), {(0, 0, 0, 0), (30, 160, 80, 255)})

    def test_card_paths_are_stable_and_safe(self):
        self.assertEqual(og.card_path('Matcha Flavoured Wiki:About'), og.card_path('Matcha Flavoured Wiki:About'))
        self.assertRegex(og.card_path('A/B: "C"'), r'^/og/[0-9a-f]{16}\.png$')


@unittest.skipUnless(os.path.exists(og.FONT_JSON), 'needs the game font (tools/fetch_sources.sh)')
class CardTests(unittest.TestCase):
    def test_card_is_1200x630_and_reproducible(self):
        png = og.card('Crystal Heart', None, 'Items')
        self.assertEqual(png, og.card('Crystal Heart', None, 'Items'))
        self.assertEqual(Image.open(io.BytesIO(png)).size, (1200, 630))

    def test_long_titles_fit(self):
        og.card('Snout Armor Trim Smithing Template of Unusual Length', None, 'Items')
        for line in og.wrap('Snout Armor Trim Smithing Template', 600, 5):
            self.assertLessEqual(og.text_width(line) * 5, 600)

    def test_accented_titles_use_the_game_glyphs(self):
        self.assertEqual(og.normalize('Piñata’s – end'), "Piñata's - end")


if __name__ == '__main__':
    unittest.main()
