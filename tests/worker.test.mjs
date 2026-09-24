import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test } from 'node:test';

// Load the actual Worker with a small table; no runtime/build dependencies needed.
const source = await readFile(new URL('../src/worker.js', import.meta.url), 'utf8');
const table = { redirects: { Main_Page: '/', Emerald: '/w/Obol', Hearts: '/w/Health#Maximum_health' },
  titles: { mud_kiln: 'Mud_Kiln', obol: 'Obol', health: 'Health', matcha_flavoured_wiki: 'Matcha_Flavoured_Wiki', 'category:food': 'Category:Food' },
  random: ['/w/Mud_Kiln', '/w/Obol', '/w/Health'] };
const { default: worker } = await import('data:text/javascript;base64,' + Buffer.from(source.replace('import table from "./redirects.json";', `const table = ${JSON.stringify(table)};`)).toString('base64'));
const env = { ASSETS: { fetch: async () => new Response('asset', {status: 404}) } };

for (const [path, target] of [
  ['/w/mud_kiln', '/w/Mud_Kiln'], ['/w/Mud_Kiln/', '/w/Mud_Kiln'],
  ['/w/Mud_Kiln.html', '/w/Mud_Kiln'], ['/w/emerald', '/w/Obol'],
  ['/w/Main_Page', '/'], ['/w/matcha_flavoured_wiki', '/'],
  ['/w/Hearts?q=test', '/w/Health?q=test#Maximum_health'],
  ['/w/Category%3AFood', '/w/Category:Food'],
]) {
  test(`permanent canonical redirect: ${path}`, async () => {
    const response = await worker.fetch(new Request('https://matchaflavou.red' + path), env);
    assert.equal(response.status, 301);
    assert.equal(response.headers.get('location'), 'https://matchaflavou.red' + target);
  });
}
test('alternate hostname and path consolidate in a single hop', async () => {
  const response = await worker.fetch(new Request('https://matchaflavoured.org/w/emerald?q=1'), env);
  assert.equal(response.headers.get('location'), 'https://matchaflavou.red/w/Obol?q=1');
});
for (const path of ['/w/Mud_Kiln', '/w/Category:Food', '/w/Missing', '/w/%FF', '/w/constructor', '/w/__proto__']) {
  test(`passes through without a redirect loop: ${path}`, async () => {
    assert.equal((await worker.fetch(new Request('https://matchaflavou.red' + path), env)).status, 404);
  });
}
test('previews on workers.dev are served in place and kept out of search', async () => {
  const response = await worker.fetch(new Request('https://pr-7-matcha-flavoured-wiki.example.workers.dev/w/mud_kiln'), env);
  assert.equal(response.headers.get('location'), 'https://pr-7-matcha-flavoured-wiki.example.workers.dev/w/Mud_Kiln');
  const page = await worker.fetch(new Request('https://pr-7-matcha-flavoured-wiki.example.workers.dev/w/Mud_Kiln'), env);
  assert.equal(page.headers.get('x-robots-tag'), 'noindex');
  assert.equal(page.status, 404);
});
test('the canonical host is indexable', async () => {
  const response = await worker.fetch(new Request('https://matchaflavou.red/w/Mud_Kiln'), env);
  assert.equal(response.headers.get('x-robots-tag'), null);
});
test('?v= (a file version from tools/fingerprint.py) is cached for good and looked up without the query', async () => {
  let asked;
  const assets = { ASSETS: { fetch: async (request) => { asked = request.url; return new Response('css', { headers: { 'Cache-Control': 'public, max-age=0, must-revalidate' } }); } } };
  const response = await worker.fetch(new Request('https://matchaflavou.red/_rl/1.css?v=abc'), assets);
  assert.equal(asked, 'https://matchaflavou.red/_rl/1.css');
  assert.equal(response.headers.get('cache-control'), 'public, max-age=31536000, immutable');
  assert.equal(await response.text(), 'css');
});
test('unversioned files, pages and missing versions keep revalidating', async () => {
  for (const path of ['/_rl/1.css', '/w/Mud_Kiln', '/search/?q=oven']) {
    assert.equal((await worker.fetch(new Request('https://matchaflavou.red' + path), env)).headers.get('cache-control'), null);
  }
  assert.equal((await worker.fetch(new Request('https://matchaflavou.red/_rl/gone.css?v=abc'), env)).headers.get('cache-control'), null);
});
test('Special:Random sends each visit to an indexed article, uncached and not permanent', async () => {
  const seen = new Set();
  for (let i = 0; i < 60; i++) {
    for (const path of ['/w/Special:Random', '/w/Special%3ARandom', '/w/special:randompage']) {
      const response = await worker.fetch(new Request('https://matchaflavou.red' + path), env);
      assert.equal(response.status, 302);
      assert.equal(response.headers.get('cache-control'), 'no-store');
      seen.add(response.headers.get('location'));
    }
  }
  assert.deepEqual([...seen].sort(), table.random.map((p) => 'https://matchaflavou.red' + p).sort());
});
test('Special:Random from another hostname lands on the canonical host in one hop', async () => {
  const response = await worker.fetch(new Request('https://matchaflavoured.org/w/Special:Random'), env);
  assert.match(response.headers.get('location'), /^https:\/\/matchaflavou\.red\/w\//);
});
test('Special:Random on a preview stays on the preview', async () => {
  const response = await worker.fetch(new Request('https://pr-7-matcha-flavoured-wiki.example.workers.dev/w/Special:Random'), env);
  assert.match(response.headers.get('location'), /^https:\/\/pr-7-matcha-flavoured-wiki\.example\.workers\.dev\/w\//);
});
