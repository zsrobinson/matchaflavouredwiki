"""The update report (tools/update_report.py) compares the data before and after an update. A thing that
only moved to another namespace (1.12.2-beta moved most of `main:` to `matcha:`) is compared under its new
ID, so the checklist lists what changed instead of every ID twice."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from update_report import lore_words, moved_ids, rename_ids


def data(recipes=(), advancements=None, enchantments=None, items=None, trades=None):
    return {'recipes': list(recipes), 'advancements': advancements or {}, 'enchantments': enchantments or {},
            'loot': {}, 'functions': {}, 'items': items or {}, 'trades': trades or {}}


class MovedIdTests(unittest.TestCase):
    def test_namespace_move(self):
        a = data([{'id': 'main:blast/sand'}], {'main:fish/root': {'parent': None},
                                                'main:fish/gar': {'parent': 'main:fish/root'}},
                 {'main:reach': {}, 'main:warding0': {}})
        b = data([{'id': 'matcha:blast/sand'}], {'matcha:fish/root': {'parent': None},
                                                  'matcha:fish/gar': {'parent': 'matcha:fish/root'}},
                 {'main:reach': {}, 'matcha:warding_1': {}})
        moved = moved_ids(a, b)
        # main:reach stayed; main:warding0 was renamed, not moved: the report shows it as removed and new
        self.assertEqual(moved, {'main:blast/sand': 'matcha:blast/sand', 'main:fish/root': 'matcha:fish/root',
                                 'main:fish/gar': 'matcha:fish/gar'})
        self.assertEqual(rename_ids(a['advancements'], moved), b['advancements'])

    def test_trades(self):
        a = data(trades={'cartographer': {'1': [{'id': 'minecraft:cartographer/1/shipwreck'}]}})
        b = data(trades={'cartographer': {'1': [{'id': 'matcha:cartographer/1/shipwreck'}]}})
        self.assertEqual(moved_ids(a, b), {'minecraft:cartographer/1/shipwreck': 'matcha:cartographer/1/shipwreck'})

    def test_item_models(self):
        a = data(items={'Echo Eel': {'models': ['echo_fish'], 'components': {'item_model': 'echo_fish',
                                                                               'custom_name': 'echo_fish'}},
                        'Amber': {'models': ['matcha:amber', 'minecraft:amber'], 'components': {}}})
        b = data(items={'Echo Eel': {'models': ['matcha:echo_fish'], 'components': {}},
                        'Amber': {'models': ['matcha:amber'], 'components': {}}})
        moved = moved_ids(a, b)
        self.assertEqual(moved['minecraft:amber'], 'matcha:amber')
        # a bare model ID is renamed only where a model is expected
        self.assertEqual(rename_ids(a['items']['Echo Eel']['components'], moved),
                         {'item_model': 'matcha:echo_fish', 'custom_name': 'echo_fish'})
        crit = {'item': {'components': {'minecraft:item_model': 'echo_fish'}}}
        self.assertEqual(rename_ids(crit, moved), {'item': {'components': {'minecraft:item_model': 'matcha:echo_fish'}}})

    def test_nothing_moved(self):
        a = data([{'id': 'matcha:x'}])
        self.assertEqual(moved_ids(a, a), {})
        self.assertIs(rename_ids(a, {}), a)


class LoreTests(unittest.TestCase):
    def test_glyphs_only(self):
        # Adamant Boots: 1.12.1-alpha wrote symbols, 1.12.2-beta the pack's own glyphs
        self.assertEqual(lore_words(['🛡 3', '💥🚫 1', 'Set Bonus:']),
                         lore_words(['⟦Armor⟧ 3', '⟦Knockback resistance⟧ 1', 'Set Bonus:']))

    def test_words_and_numbers_count(self):
        self.assertNotEqual(lore_words(['🗡 9']), lore_words(['⟦Attack damage⟧ 7']))
        self.assertNotEqual(lore_words(['Repaired with:', 'Iron']), lore_words(['Repaired with:', 'Copper']))


if __name__ == '__main__':
    unittest.main()
