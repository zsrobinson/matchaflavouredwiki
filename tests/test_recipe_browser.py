"""The recipe browser's data (tools/recipe_browser.py), built here from a small stand-in for
tools/generate.py so the test needs no build/data.json."""
from pathlib import Path
from types import SimpleNamespace
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import recipe_browser as rb


def fake_generate():
    aliases = {}

    def slot_text(ing):
        if ing is None:
            return ''
        names = list(dict.fromkeys(ing['names']))
        if ing.get('tag') and len(names) > 1:
            aliases['Any Planks'] = names
            return 'Any Planks'
        return ';'.join(names)

    shaped = {'type': 'minecraft:crafting_shaped', 'station': 'Crafting Table', 'origin': 'pack', 'id': 'matcha:stick',
              'pattern': ['#', '#'], 'key': {'#': {'names': ['Oak Planks', 'Birch Planks'], 'tag': 'minecraft:planks'}},
              'output': {'name': 'Stick', 'count': 4}}
    cooked = {'type': 'minecraft:smelting', 'station': 'Oven', 'origin': 'vanilla', 'id': 'minecraft:bread',
              'input': {'names': ['Dough']}, 'output': {'name': 'Bread'}, 'cookingtime': 100, 'experience': 0.35}
    shapeless = {'type': 'minecraft:crafting_shapeless', 'station': 'Crafting Table', 'origin': 'pack', 'id': 'matcha:dough',
                 'ingredients': [{'names': ['Flour']}, {'names': ['Flour']}, {'names': ['Egg', 'Blue Egg']}], 'output': {'name': 'Dough'}}
    debug = dict(shapeless, id='debug:door', output={'name': 'Copper Eye Door'})
    trade = {'wants': {'name': 'Obol', 'count': 3}, 'additional_wants': None, 'gives': {'name': 'Bread', 'count': 2}}
    return SimpleNamespace(
        ALL_RECIPES=[shaped, shapeless, debug], VANILLA_KEPT=[cooked], ALIASES=aliases,
        TRADES={'farmer': {'level_1': [trade], 'level_1_meta': {}}}, PROF={'farmer': 'Farmer'},
        ITEMS={'Obol': {'renamed_vanilla': True, 'vanilla_name': 'Emerald', 'base_id': 'minecraft:emerald'},
               'Bread': {'renamed_vanilla': True, 'vanilla_name': 'Bread', 'base_id': 'minecraft:bread'},
               'Dough': {'base_id': 'minecraft:dough'}},
        # (category, label, loot table, ...), as generate.SOURCES has them
        SOURCES={'Oak Planks': [('Chest loot', 'chest', 'minecraft:chests/village')],
                 'Egg': [('Gameplay', 'chicken', 'minecraft:gameplay/chicken_lay')],
                 'Dough': [('Block drops', 'dough', 'minecraft:blocks/dough')]},
        slot_text=slot_text, safe=lambda n: n, slot_name=lambda s: s.get('variant') or s['name'],
        cook_ticks=lambda r: r.get('cookingtime') or 200)


class RowTests(unittest.TestCase):
    def setUp(self):
        self.data, self.names = rb.build(fake_generate())
        self.rows = self.data['r']

    def row(self, output, station):
        return next(r for r in self.rows if r['o'] == output and r['s'] == station)

    def test_every_station_and_the_trades(self):
        self.assertEqual(sorted((r['o'], r['s']) for r in self.rows),
                         [('Bread', 'oven'), ('Bread', 'trade'), ('Dough', 'crafting'), ('Stick', 'crafting')])

    def test_developer_recipes_are_left_out(self):
        self.assertNotIn('Copper Eye Door', [r['o'] for r in self.rows])

    def test_slots_are_module_station_names(self):
        self.assertEqual(self.row('Stick', 'crafting'), {'s': 'crafting', 'g': {'A1': 'Any Planks', 'A2': 'Any Planks'}, 'o': 'Stick', 'c': 4})
        self.assertEqual(self.row('Dough', 'crafting')['g'], {'A1': 'Flour', 'B1': 'Flour', 'C1': 'Egg;Blue Egg'})
        self.assertEqual(self.row('Dough', 'crafting')['l'], 1)

    def test_cooking_time_experience_and_vanilla(self):
        self.assertEqual(self.row('Bread', 'oven'), {'s': 'oven', 'g': {'Input': 'Dough'}, 'o': 'Bread', 't': 5, 'x': 0.35, 'v': 1})

    def test_trades_name_the_villager(self):
        self.assertEqual(self.row('Bread', 'trade'), {'s': 'trade', 'g': {'1': 'Obol,3'}, 'o': 'Bread', 'c': 2, 'p': 'Farmer', 'lv': 'Novice'})

    def test_aliases_vanilla_names_and_world_sources(self):
        self.assertEqual(self.data['a'], {'Any Planks': ['Oak Planks', 'Birch Planks']})
        self.assertEqual(self.data['n'], {'Obol': 'Emerald'})  # not Bread, whose vanilla name is its own
        # chest loot, or a placed block dropping itself, doesn't make a raw material
        self.assertEqual(self.data['w'], ['Egg'])

    def test_every_slot_is_rendered(self):
        for n in ('Oak Planks', 'Birch Planks', 'Any Planks', 'Egg', 'Blue Egg', 'Obol', 'Crafting Table', 'Stonecutter'):
            self.assertIn(n, self.names)
        self.assertNotIn('Obol,3', self.names)
        self.assertNotIn('Egg;Blue Egg', self.names)


class SlotTests(unittest.TestCase):
    def test_slot_names(self):
        self.assertEqual(rb.slot_names('Oak Log;Birch Log'), ['Oak Log', 'Birch Log'])
        self.assertEqual(rb.slot_names('Obol,3'), ['Obol'])

    def test_render_slots_splits_one_parse_per_batch(self):
        def parse(base, text):
            names = re.findall(r'\|1=([^}]*)\}\}', text)
            return ''.join('<div class="mfw-rb-cut" data-n="%d"><span class="invslot"><a href="/w/%s">'
                           '<img alt="%s.png: Inventory sprite for %s in Minecraft" src="/images/x.png" data-file-width="128"></a></span></div>'
                           % (i, n.replace(' ', '_'), n, n) for i, n in enumerate(names))
        with mock.patch.object(rb, 'parse', side_effect=parse) as p, mock.patch.object(rb, 'BATCH', 2):
            out = rb.render_slots('http://wiki', ['Bread', 'Oak Planks', 'Stick'])
        self.assertEqual(p.call_count, 2)
        self.assertEqual(out['Oak Planks'], '<span class="invslot"><a href="/w/Oak_Planks"><img alt="Oak Planks" src="/images/x.png"></a></span>')
        self.assertEqual(rb.slot_link(out['Stick']), '/w/Stick')

    def test_a_missing_slot_fails_the_export(self):
        with mock.patch.object(rb, 'parse', return_value='<div class="mfw-rb-cut" data-n="0"><strong class="error">x</strong></div>'):
            with self.assertRaises(RuntimeError):
                rb.render_slots('http://wiki', ['Nothing'])

    def test_spoilers_are_the_pages_and_sections_a_box_covers(self):
        import tempfile
        box = '<table class="messagebox spoiler" data-mfw-spoiler="1">'
        pages = {
            'Secret_Stew': '<p>Lead.</p>' + box + '<p class="mfw-spoiler-body">x</p><div class="mw-heading mw-heading2 mfw-spoiler-body"><h2 id="Obtaining">O</h2></div>',
            'Pizza': '<div class="mw-heading mw-heading2"><h2 id="Kinds">K</h2></div>' + box +
                     '<div class="mw-heading mw-heading3 mfw-spoiler-body"><h3 id="Warped_Pizza">W</h3></div>'
                     '<div class="mw-heading mw-heading2"><h2 id="Mushroom_Pizza">M</h2></div>'
                     '<div class="mw-heading mw-heading2"><h2 id="Chorus_pizza">C</h2></div>' + box.replace('"1"', '"2"') +
                     '<p class="mfw-spoiler-body">x</p><div class="mw-heading mw-heading2"><h2 id="History">H</h2></div>',
            'Bread': '<p>Lead.</p><div class="mw-heading mw-heading2"><h2 id="Uses">U</h2></div>' + box + '<p class="mfw-spoiler-body">x</p>',
        }
        with tempfile.TemporaryDirectory() as out:
            Path(out, 'w').mkdir()
            for t, h in pages.items():
                Path(out, 'w', t + '.html').write_text(h, encoding='utf-8')
            links = {'Secret Stew': '/w/Secret_Stew', 'Warped Pizza': '/w/Pizza#Warped_Pizza', 'Mushroom Pizza': '/w/Pizza#Mushroom_Pizza', 'Chorus Pizza': '/w/Pizza#Chorus_pizza',
                     'Bread': '/w/Bread', 'Stone': 'https://minecraft.wiki/w/Stone', 'Missing': '/w/Missing'}
            self.assertEqual(rb.spoilers(out, links), ['Chorus Pizza', 'Secret Stew', 'Warped Pizza'])


if __name__ == '__main__':
    unittest.main()
