// The recipe browser's lookups and crafting tree (site/recipes.js), on a small recipes.json.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const require = createRequire(import.meta.url);
const R = require('../site/recipes.js');
const S = require('../site/search.js');

// Rows as tools/recipe_browser.py writes them
const data = () => ({
  a: { 'Any Planks': ['Oak Planks', 'Birch Planks'], 'Any Oak Logs': ['Oak Log', 'Oak Wood'], 'Any Coals': ['Coal', 'Charcoal'] },
  n: { Obol: 'Emerald' },
  w: ['Raw Iron', 'Coal'],
  u: {}, h: {},
  r: [
    { s: 'crafting', g: { A1: 'Any Planks', A2: 'Any Planks' }, o: 'Stick', c: 4 },
    { s: 'crafting', g: { A1: 'Any Oak Logs' }, o: 'Oak Planks', c: 4 },
    { s: 'crafting', g: { A1: 'Birch Log' }, o: 'Birch Planks', c: 4 },
    { s: 'crafting', g: { A1: 'Oak Slab', B1: 'Oak Slab' }, o: 'Oak Planks' },          // slabs back into planks
    { s: 'crafting', g: { A1: 'Oak Planks', B1: 'Oak Planks', C1: 'Oak Planks' }, o: 'Oak Slab', c: 6 },
    { s: 'crafting', g: { A1: 'Oak Log', B1: 'Oak Log', A2: 'Oak Log', B2: 'Oak Log' }, o: 'Oak Wood', c: 3 },
    { s: 'stonecutter', g: { Input: 'Oak Wood' }, o: 'Oak Log' },                        // only from each other
    { s: 'blast', g: { Input: 'Iron Sword;Iron Horse Armor;Raw Iron' }, o: 'Iron Ingot', t: 5 },  // melting, or raw iron
    { s: 'crafting', g: { A1: 'Iron Block' }, o: 'Iron Ingot', c: 9 },
    { s: 'crafting', g: { A1: 'Iron Ingot', B1: 'Iron Ingot', C1: 'Iron Ingot', A2: 'Iron Ingot', B2: 'Iron Ingot', C2: 'Iron Ingot', A3: 'Iron Ingot', B3: 'Iron Ingot', C3: 'Iron Ingot' }, o: 'Iron Block' },
    { s: 'crafting', g: { A1: 'Iron Ingot', A2: 'Iron Ingot', A3: 'Stick' }, o: 'Iron Sword' },
    { s: 'crafting', g: { A1: 'Block of Coal' }, o: 'Coal', c: 9 },
    { s: 'crafting', g: { A1: 'Any Coals', B1: 'Any Coals', C1: 'Any Coals', A2: 'Any Coals', B2: 'Any Coals', C2: 'Any Coals', A3: 'Any Coals', B3: 'Any Coals', C3: 'Any Coals' }, o: 'Block of Coal' },
    { s: 'oven', g: { Input: 'Any Oak Logs' }, o: 'Charcoal', t: 10 },
    { s: 'trade', g: { 1: 'Obol,3' }, o: 'Iron Sword', p: 'Weaponsmith', lv: 'Novice' },
  ],
});
const db = R.prepare(data());

test('slot text: alternatives and stack sizes', () => {
  assert.deepEqual(R.parseSlot('Oak Log;Birch Log'), [{ name: 'Oak Log', count: 1 }, { name: 'Birch Log', count: 1 }]);
  assert.deepEqual(R.parseSlot('Obol,3'), [{ name: 'Obol', count: 3 }]);
});

test('ingredients are counted in grid order', () => {
  assert.deepEqual(R.tally(R.made(db, 'Iron Sword', 'crafting')[0]), [['Iron Ingot', 2], ['Stick', 1]]);
  assert.deepEqual(R.tally(R.made(db, 'Iron Sword', 'trade')[0]), [['Obol', 3]]);
});

test('recipes by output, with the station filter', () => {
  assert.equal(R.made(db, 'Iron Sword').length, 2);
  assert.deepEqual(R.made(db, 'Iron Sword', 'trade').map(r => r.p), ['Weaponsmith']);
  assert.deepEqual(R.made(db, 'Iron Ingot', 'blast').map(r => r.s), ['blast']);
});

test('reverse lookup finds a tag\'s recipes from its members, and alternatives', () => {
  assert.deepEqual(R.used(db, 'Birch Planks').map(r => r.o), ['Stick']);
  assert.deepEqual(R.used(db, 'Any Planks').map(r => r.o), ['Stick']);
  assert.deepEqual(R.used(db, 'Raw Iron').map(r => r.o), ['Iron Ingot']);
  assert.deepEqual(R.used(db, 'Obol').map(r => r.o), ['Iron Sword']);
  assert.deepEqual(R.used(db, 'Iron Ingot').map(r => r.o).sort(), ['Iron Block', 'Iron Sword']);
});

test('names match as the search box matches titles', () => {
  const index = S.prepare(R.nameRows(db));
  const first = q => R.matchNames(S, index, q, 5)[0];
  assert.equal(first('iron swrod').name, 'Iron Sword');       // typo
  assert.equal(first('sticks').name, 'Stick');                // plural
  assert.equal(first('emerald').name, 'Obol');                // vanilla name
  assert.equal(first('emerald').alias, 'Emerald');
  assert.equal(first('planks').name, 'Any Planks');           // the tag before its members
  assert.equal(first('Oak Planks').exact, true);
});

const show = node => [node.need, node.text, node.recipe ? node.recipe.s : null, node.children.map(show)];

test('the tree follows the easiest recipe down to raw materials', () => {
  assert.deepEqual(show(R.tree(db, 'Iron Sword', 1)), [1, 'Iron Sword', 'crafting', [
    [2, 'Iron Ingot', 'blast', [[2, 'Iron Sword;Iron Horse Armor;Raw Iron', null, []]]],
    [1, 'Stick', 'crafting', [[2, 'Any Planks', 'crafting', [[1, 'Any Oak Logs', null, []]]]]],
  ]]);
  const t = R.tree(db, 'Iron Sword', 1);
  assert.equal(t.children[0].children[0].name, 'Raw Iron');               // not a melted sword or horse armor
  assert.deepEqual(R.totals(t), [['Raw Iron', 2], ['Any Oak Logs', 1]]);
});

test('stack sizes: crafts are rounded up by what a recipe makes', () => {
  const t = R.tree(db, 'Stick', 5);                            // 4 per craft: 2 crafts, 4 planks, 1 log
  assert.equal(t.crafts, 2);
  assert.deepEqual(R.totals(t), [['Any Oak Logs', 1]]);
});

test('recipes that undo another are not followed (ingot from block, planks from slabs, coal from its block)', () => {
  assert.equal(R.tree(db, 'Iron Ingot', 1).recipe.s, 'blast');
  assert.deepEqual(R.treeRecipes(db, 'Oak Planks').map(r => r.g.A1), ['Any Oak Logs', 'Oak Slab']);
  assert.equal(R.depths(db).Coal, 0);
  assert.equal(R.tree(db, 'Block of Coal', 1).children[0].name, 'Coal');  // not Charcoal from the oven
});

test('items made only from each other are gathered raw materials', () => {
  const dd = R.depths(db);
  assert.equal(dd['Oak Log'], 0);
  assert.equal(dd['Oak Planks'], 1);
  assert.equal(dd.Stick, 2);
  assert.ok(Object.values(dd).every(Number.isFinite));
});

test('a reader\'s choice can loop, and the tree stops there', () => {
  const planks = db.rows.findIndex(r => r.o === 'Oak Planks' && r.g.A1 === 'Oak Slab');
  const t = R.tree(db, 'Oak Planks', 1, { 'Oak Planks': planks });
  assert.equal(t.recipe.g.A1, 'Oak Slab');
  const slab = t.children[0];
  assert.equal(slab.children[0].name, 'Oak Planks');
  assert.equal(slab.children[0].loop, true);
  assert.deepEqual(slab.children[0].children, []);
});

test('a reader can pick a tag\'s member', () => {
  const t = R.tree(db, 'Stick', 1, { 'any:Any Planks': 'Birch Planks' });
  assert.equal(t.children[0].name, 'Birch Planks');
  assert.equal(t.children[0].children[0].name, 'Birch Log');
});

test('a reader can take an ingredient as it is, or make a raw one', () => {
  const t = R.tree(db, 'Iron Sword', 1, { 'Iron Ingot': -1 });
  assert.deepEqual(t.children[0].children, []);
  assert.deepEqual(R.totals(t)[0], ['Iron Ingot', 2]);
  const coal = db.rows.find(r => r.o === 'Coal').i;
  assert.equal(R.tree(db, 'Block of Coal', 1, { Coal: coal }).children[0].recipe.o, 'Coal');
});

test('a recipe choice names the item the tree follows, not the first of its list', () => {
  const blast = R.made(db, 'Iron Ingot', 'blast')[0];
  assert.equal(R.recipeLabel(db, blast), 'Blast Furnace: Raw Iron');
  assert.equal(R.recipeLabel(db, blast, { 'any:Iron Sword;Iron Horse Armor;Raw Iron': 'Iron Horse Armor' }), 'Blast Furnace: Iron Horse Armor');
  assert.equal(R.recipeLabel(db, R.made(db, 'Stick')[0]), 'Crafting Table: 2 Any Planks');  // a tag keeps its name
  assert.equal(R.recipeLabel(db, { s: 'blast', g: { Input: 'Raw Iron' }, o: 'Iron Ingot', v: 1 }), 'Blast Furnace: Raw Iron (vanilla recipe)');
});
