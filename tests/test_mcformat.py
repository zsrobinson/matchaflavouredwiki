"""tools/mcformat.py"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mcformat import pack_format


class PackFormatTests(unittest.TestCase):
    """extract.py compares the pack's formats with the vanilla data's (data_pack_version 107, minor 1)."""
    def test_spellings(self):
        self.assertEqual(pack_format([107.1]), (107, 1))  # MF_datapack/pack.mcmeta at 1.12.2-beta
        self.assertEqual(pack_format(88.0), (88, 0))      # Matcha_Flavoured/pack.mcmeta at 1.12.1-alpha
        self.assertEqual(pack_format(88), (88, 0))
        self.assertEqual(pack_format([107, 1]), (107, 1))  # Minecraft's own [major, minor]
        self.assertIsNone(pack_format(None))

    def test_range(self):
        self.assertTrue(pack_format(88.0) <= (107, 1) <= pack_format(107.1))
        self.assertFalse(pack_format([121.0]) <= (107, 1))


if __name__ == '__main__':
    unittest.main()
