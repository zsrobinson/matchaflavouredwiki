// The title search behind the header box, the search page and the 404 page (site/search.js).
// Each case is a way readers search that the full-text index alone got wrong.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const S = createRequire(import.meta.url)('../site/search.js');

// Rows as tools/search_index.py writes them: t title, u URL, n pages linking here, k kind, a redirects
const rows = [
  { t: 'Fish', u: '/w/Fish', n: 40 },
  { t: 'Fishing', u: '/w/Fishing', n: 73 },
  { t: 'Fishing Rod', u: '/w/Fishing_Rod', n: 30 },
  { t: 'Tropical Fish', u: '/w/Tropical_Fish', n: 5 },
  { t: 'Flying Fish', u: '/w/Flying_Fish', n: 5 },
  { t: 'Fisherman', u: '/w/Fisherman', n: 20 },
  { t: 'Category:Fishing', u: '/w/Category:Fishing', k: 'category' },
  { t: 'Estus', u: '/w/Estus', n: 30 },
  { t: 'Estus Ash', u: '/w/Estus_Ash', n: 60 },
  { t: 'Estus Flask', u: '/w/Estus_Flask', n: 7 },
  { t: 'Raw Estus', u: '/w/Raw_Estus', n: 30, a: ['Blaze Powder'] },
  { t: 'Stabilized Estus', u: '/w/Stabilized_Estus', n: 10 },
  { t: 'Armor', u: '/w/Armor', n: 55, a: ['Armour'] },
  { t: 'Armoured Catfish', u: '/w/Armoured_Catfish', n: 3 },
  { t: 'Mud Kiln', u: '/w/Mud_Kiln', n: 50 },
  { t: 'Cook', u: '/w/Cook', n: 20 },
  { t: 'Cooking', u: '/w/Cooking', n: 60 },
  { t: 'Cooked Fish', u: '/w/Cooked_Fish', n: 10 },
  { t: 'Weapons', u: '/w/Weapons', n: 30, a: [['Swords', 'Swords'], ['Axes', 'Axes']] },
  { t: 'Iron Sword', u: '/w/Iron_Sword', n: 5 },
  { t: 'Sulfur blocks', u: '/w/Sulfur_blocks', n: 20, a: ['Sulfur'] },
  { t: 'Sulfur Chunk', u: '/w/Sulfur_Chunk', n: 20 },
  { t: 'Buñuelo', u: '/w/Bu%C3%B1uelo', n: 2 },
  { t: 'Pickles & Jam', u: '/w/Pickles_%26_Jam', n: 2 },
  { t: "Angler's Almanac", u: "/w/Angler's_Almanac", n: 2 },
  { t: 'Obol', u: '/w/Obol', n: 229, a: ['Emerald'] },
  { t: 'Block of Obol', u: '/w/Block_of_Obol', n: 10 },
  { t: 'Cinnabar', u: '/w/Cinnabar', n: 20 },
  { t: 'Wandering Trader', u: '/w/Wandering_Trader', n: 20 },
  { t: 'Villager', u: '/w/Villager', n: 40 },
  { t: 'Oak Planks', u: '/w/Oak_Planks', n: 20, k: 'generated' },
  { t: 'Matcha Flavoured Wiki:About', u: '/w/Matcha_Flavoured_Wiki:About', k: 'project' },
];
const index = S.prepare(rows);
const top = (q, n = 1) => S.match(index, q, n).map(m => m.row.t);

for (const [query, first] of [
  ['fishing', 'Fishing'],           // not Tropical Fish or Flying Fish ("fishing" stems to "fish" in Pagefind)
  ['Fishing', 'Fishing'],
  ['FISH', 'Fish'],
  ['mud kiln', 'Mud Kiln'],
  ['mudkiln', 'Mud Kiln'],          // spaces left out
  ['kil', 'Mud Kiln'],              // a later word, as you type
  ['est', 'Estus'],                 // finishing the word before adding words, though Estus Ash is linked more
  ['armour', 'Armor'],              // a redirect
  ['blaze powder', 'Raw Estus'],    // the vanilla name
  ['sulphur', 'Sulfur blocks'],     // British spelling, through the Sulfur redirect
  ['stabilised estus', 'Stabilized Estus'],
  ['swords', 'Weapons'],            // a redirect to a section
  ['sword', 'Weapons'],             // singular of a redirect
  ['bunuelo', 'Buñuelo'],           // accents
  ['pickles and jam', 'Pickles & Jam'],
  ['anglers almanac', "Angler's Almanac"],
  ['estis', 'Estus'],               // typos
  ['cinabar', 'Cinnabar'],
  ['fishign', 'Fishing'],
  ['wandring trader', 'Wandering Trader'],
  ['vilager', 'Villager'],
  ['how to get obol', 'Obol'],      // questions
  ['how do i cook', 'Cooking'],     // "how to <verb>" is the -ing page before the villager
  ['where to find cinnabar', 'Cinnabar'],
  ['fishing rod enchantments', 'Fishing Rod'],
  ['oak planks', 'Oak Planks'],
  ['about', 'Matcha Flavoured Wiki:About'],
]) {
  test(`"${query}" finds ${first} first`, () => assert.equal(top(query)[0], first));
}

test('category pages come after the articles they are named like', () => {
  const ts = top('fishing', 10);
  assert.ok(ts.indexOf('Category:Fishing') > ts.indexOf('Fishing Rod'), ts.join(', '));
});

test('one row per page, reporting the redirect that matched', () => {
  const [m] = S.match(index, 'blaze powder', 5);
  assert.equal(m.row.t, 'Raw Estus');
  assert.equal(m.alias, 'Blaze Powder');
  assert.equal(S.match(index, 'armour', 1)[0].alias, null);  // one spelling of the title itself, not the redirect
  assert.equal(S.match(index, 'armor', 5).filter(x => x.row.t === 'Armor').length, 1);
  const [s] = S.match(index, 'swords', 1);
  assert.equal(s.anchor, 'Swords');
});

test('questions match whole words, not the start of a longer one', () => {
  const idx = S.prepare([{ t: 'Cooking', u: '/w/Cooking' }, { t: 'Cheese', u: '/w/Cheese', a: ['Cookie'] }]);
  assert.deepEqual(S.match(idx, 'how to cook', 5).map(m => m.row.t), ['Cooking']);
  assert.deepEqual(S.match(idx, 'cook', 5).map(m => m.row.t).sort(), ['Cheese', 'Cooking']);  // typed as is, it may be either
});

test('nothing for an empty query or noise', () => {
  assert.deepEqual(top('', 5), []);
  assert.deepEqual(top('   ', 5), []);
  assert.deepEqual(top('zzqx', 5), []);
});

test('folding: case, accents, apostrophes, ampersands, punctuation', () => {
  assert.equal(S.fold("Angler's  Almanac!"), 'anglers almanac');
  assert.equal(S.fold('Buñuelo'), 'bunuelo');
  assert.equal(S.fold('Pickles & Jam'), 'pickles and jam');
  assert.equal(S.key('Grey Sulphur Armour').raw, 'gray sulfur armor');
  assert.equal(S.key('Leaves Axes Berries Estus Glass').stem, 'leave axe berry estus glass');
});

test('distance counts a swapped pair as one edit and stops past the limit', () => {
  assert.equal(S.distance('ramne', 'ramen', 2), 1);
  assert.equal(S.distance('cinabar', 'cinnabar', 2), 1);
  assert.equal(S.distance('abc', 'xyzw', 1), 2);
});
