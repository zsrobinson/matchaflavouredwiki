"""The 26.3 data format read as 26.2's (tools/mcformat.py). The examples are the pack's own files: its
26.3 branch next to the same file at the release the wiki describes."""
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from mcformat import Legacy
from update_report import meaning, real_time


class LegacyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # vanilla 26.3's predicate/tool/can_silk_touch.json
        self.silk = os.path.join(self.tmp.name, 'can_silk_touch.json')
        with open(self.silk, 'w') as f:
            json.dump({'type': 'minecraft:match_tool', 'predicate': {'predicates': {'minecraft:enchantments': [
                {'enchantments': 'minecraft:silk_touch', 'levels': {'min': 1}}]}}}, f)
        self.unknown = []
        self.legacy = Legacy(lambda pid: self.silk if pid == 'minecraft:tool/can_silk_touch' else None,
                             lambda kind, key, src: self.unknown.append((kind, key)))

    def tearDown(self):
        self.assertEqual(self.unknown, [])

    def test_26_2_comes_back_unchanged(self):
        # blocks/beetroots.json at the release: nothing to translate
        table = {'type': 'minecraft:block', 'functions': [{'function': 'minecraft:explosion_decay'}], 'pools': [
            {'rolls': 1.0, 'bonus_rolls': 0.0, 'conditions': [], 'entries': [{
                'type': 'minecraft:item', 'name': 'minecraft:beetroot',
                'conditions': [{'block': 'minecraft:beetroots', 'condition': 'minecraft:block_state_property',
                                'properties': {'age': '3'}},
                               {'condition': 'minecraft:inverted', 'term': {'condition': 'minecraft:survives_explosion'}}],
                'functions': [{'function': 'minecraft:set_count', 'count': {'min': 1, 'max': 3}}]}]}]}
        before = json.dumps(table)
        self.assertEqual(json.dumps(self.legacy.loot(table, 'x')), before)
        self.assertEqual(json.dumps(table), before)  # and the input isn't modified
        trade = {'wants': {'id': 'minecraft:emerald'}, 'given_item_modifiers': [{'function': 'minecraft:discard'}],
                 'merchant_predicate': {'condition': 'minecraft:location_check', 'predicate': {'biomes': '#x'}}}
        self.assertEqual(json.dumps(self.legacy.trade(trade, 'x')), json.dumps(trade))

    def test_loot_modifier_and_condition(self):
        # blocks/carrots.json on the 26.3 branch
        table = {'type': 'minecraft:block', 'modifier': {'type': 'minecraft:explosion_decay'}, 'pools': [{
            'bonus_rolls': 0,
            'condition': {'block': 'minecraft:carrots', 'type': 'minecraft:match_block', 'state': {'age': '7'}},
            'entries': [{'type': 'minecraft:loot_table', 'value': 'matcha:food/carrot', 'modifier': {
                'type': 'minecraft:sequence', 'functions': [
                    {'enchantment': 'minecraft:fortune', 'formula': 'minecraft:binomial_with_bonus_count',
                     'type': 'minecraft:apply_bonus', 'parameters': {'extra': 3, 'probability': 0.5714286}},
                    # the pack still spells some functions the 26.2 way; both are read
                    {'function': 'minecraft:set_count', 'count': 2}]}}],
            'rolls': 1}]}
        d = self.legacy.loot(table, 'x')
        self.assertEqual(d['functions'], [{'function': 'minecraft:explosion_decay'}])
        pool = d['pools'][0]
        self.assertEqual(list(pool), ['bonus_rolls', 'conditions', 'entries', 'rolls'])  # keys keep their places
        self.assertEqual(pool['conditions'], [{'block': 'minecraft:carrots', 'condition': 'minecraft:block_state_property',
                                               'properties': {'age': '7'}}])
        self.assertEqual([f['function'] for f in pool['entries'][0]['functions']],
                         ['minecraft:apply_bonus', 'minecraft:set_count'])

    def test_predicate_by_id_and_all_of(self):
        # vanilla 26.3's blocks/ender_chest.json and a 26.3 pool whose two conditions are one all_of
        entry = {'type': 'minecraft:alternatives', 'children': [
            {'type': 'minecraft:item', 'condition': 'minecraft:tool/can_silk_touch', 'name': 'minecraft:ender_chest'},
            {'type': 'minecraft:item', 'name': 'minecraft:obsidian',
             'condition': {'type': 'minecraft:inverted', 'term': 'minecraft:tool/can_silk_touch'},
             'modifier': [{'type': 'minecraft:set_count', 'count': 8}, {'type': 'minecraft:explosion_decay'}]}]}
        silk, obsidian = self.legacy.loot(entry, 'x')['children']
        self.assertEqual(silk['conditions'][0]['condition'], 'minecraft:match_tool')
        self.assertIn('silk_touch', json.dumps(silk['conditions']))
        self.assertEqual(obsidian['conditions'][0]['term']['condition'], 'minecraft:match_tool')
        self.assertEqual(obsidian['functions'], [{'function': 'minecraft:set_count', 'count': 8},
                                                 {'function': 'minecraft:explosion_decay'}])
        pool = {'condition': {'type': 'minecraft:all_of', 'terms': [
            {'type': 'minecraft:killed_by_player'}, {'type': 'minecraft:random_chance', 'chance': 0.5}]}}
        self.assertEqual(self.legacy.loot(pool, 'x')['conditions'], [
            {'condition': 'minecraft:killed_by_player'}, {'condition': 'minecraft:random_chance', 'chance': 0.5}])

    def test_missing_predicate_is_reported(self):
        self.assertEqual(self.legacy.cond('matcha:nope', 'x'), {'condition': 'minecraft:reference', 'name': 'matcha:nope'})
        self.assertEqual(self.unknown, [('condition', 'predicate matcha:nope, which does not exist')])
        self.unknown.clear()

    def test_tag_entry(self):
        # vanilla 26.3's entities/creeper.json: the music disc pool
        e = self.legacy.loot({'type': 'minecraft:tag', 'expand': True, 'items': '#minecraft:creeper_drop_music_discs'}, 'x')
        self.assertEqual(e, {'type': 'minecraft:tag', 'expand': True, 'name': 'minecraft:creeper_drop_music_discs'})

    def test_trades(self):
        # villager_trade/cartographer/1/witch_hut.json: an explorer map with a name, which the game throws
        # away only if it fails to make one (the discard is inside "filtered", not the trade's own)
        t = self.legacy.trade({'given_item_modifier': {'type': 'sequence', 'functions': [
            {'decoration': 'minecraft:swamp_hut', 'type': 'minecraft:exploration_map'},
            {'type': 'minecraft:set_name', 'name': {'translate': 'filled_map.explorer_swamp'}, 'target': 'item_name'},
            {'type': 'minecraft:filtered', 'item_filter': {'items': 'minecraft:filled_map'},
             'on_fail': {'type': 'minecraft:discard'}}]},
            'gives': {'id': 'minecraft:map'},
            'merchant_predicate': {'type': 'minecraft:entity_properties', 'entity': 'this', 'predicate': {}}}, 'x')
        self.assertEqual([f['function'] for f in t['given_item_modifiers']],
                         ['minecraft:exploration_map', 'minecraft:set_name', 'minecraft:filtered'])
        self.assertEqual(t['merchant_predicate']['condition'], 'minecraft:entity_properties')
        # villager_trade/butcher/5/filler.json: a placeholder the game discards
        t = self.legacy.trade({'gives': {'id': 'minecraft:emerald'}, 'given_item_modifier': {'type': 'minecraft:discard'}}, 'x')
        self.assertEqual(t['given_item_modifiers'], [{'function': 'minecraft:discard'}])

    def test_criteria(self):
        c = self.legacy.criteria({
            'catch': {'trigger': 'minecraft:fishing_rod_hooked', 'conditions': {
                'player': {'type': 'minecraft:entity_properties', 'entity': 'this',
                           'predicate': {'minecraft:type_specific/player': {'advancements': {'matcha:root': True}}}}}},
            'open': {'trigger': 'minecraft:default_block_use', 'conditions': {
                'location': {'type': 'minecraft:match_block', 'blocks': 'minecraft:oak_door', 'state': {'open': 'true'}}}},
            'craft': {'trigger': 'minecraft:recipe_crafted', 'conditions': {'recipes': 'matcha:blessing/feather_falling'}},
            'unlock': {'trigger': 'minecraft:recipe_unlocked', 'conditions': {'recipes': 'matcha:crafting/bricks'}},
        }, 'x')
        self.assertEqual(c['catch']['conditions']['player'], {'minecraft:type_specific/player': {'advancements': {'matcha:root': True}}})
        self.assertEqual(c['open']['conditions']['location'], [{'condition': 'minecraft:block_state_property',
                                                                'block': 'minecraft:oak_door', 'properties': {'open': 'true'}}])
        self.assertEqual(c['craft']['conditions'], {'recipe_id': 'matcha:blessing/feather_falling'})
        self.assertEqual(c['unlock']['conditions'], {'recipe': 'matcha:crafting/bricks'})


class ReportTests(unittest.TestCase):
    def test_same_meaning_is_not_a_change(self):
        # the same drop in the release's and the 26.3 branch's files, after extract.py read them
        old = [{'count': {'min': 1, 'max': 3}, 'conditions': [], 'rolls': 1.0,
                'crit': [{'condition': 'minecraft:entity_properties', 'entity': 'this', 'predicate': {'a': 1}}],
                'projectile': [{'condition': 'minecraft:entity_properties', 'entity': 'this'}]}]
        new = [{'count': {'type': 'minecraft:uniform', 'min': 1, 'max': 3}, 'conditions': None, 'rolls': 1,
                'crit': {'a': 1}}]
        self.assertEqual(meaning(old), meaning(new))
        self.assertNotEqual(meaning([{'count': {'min': 1, 'max': 3}}]), meaning([{'count': {'min': 1, 'max': 4}}]))

    def test_cooking_times_are_real_times(self):
        # matcha:blast/cobblestone_from_blasting_stone: 100 ticks in 26.2, 200 at twice the speed in 26.3
        r = {'type': 'minecraft:blasting', 'cookingtime': 100}
        self.assertEqual(real_time(r, {}), real_time(dict(r, cookingtime=200), {'cooking_speed': {'minecraft:blasting': 2.0}}))


if __name__ == '__main__':
    unittest.main()
