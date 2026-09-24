// Access key labels on the static site (site/accesskeys.js), as MediaWiki's jquery.accessKeyLabel shows them.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { test } from 'node:test';

const A = createRequire(import.meta.url)('../site/accesskeys.js');

test('Apple systems use Control and Option, everything else Alt and Shift', () => {
  assert.equal(A.modifiers({ platform: 'MacIntel', userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' }), 'ctrl-option-');
  assert.equal(A.modifiers({ userAgentData: { platform: 'macOS' }, platform: '' }), 'ctrl-option-');
  assert.equal(A.modifiers({ platform: 'iPad', userAgent: '' }), 'ctrl-option-');
  assert.equal(A.modifiers({ platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/140.0' }), 'alt-shift-');
  assert.equal(A.modifiers({ userAgentData: { platform: 'Linux' }, platform: 'Linux x86_64', userAgent: 'Chrome/140' }), 'alt-shift-');
  assert.equal(A.modifiers({}), 'alt-shift-');
});

test('the key in brackets at the end of a tooltip gets the modifiers', () => {
  assert.equal(A.label('Load a random page [x]', 'x', 'alt-shift-'), 'Load a random page [alt-shift-x]');
  assert.equal(A.label('Visit the main page [z]', 'z', 'ctrl-option-'), 'Visit the main page [ctrl-option-z]');
});

test('other tooltips are left alone', () => {
  assert.equal(A.label('Search Matcha Flavoured Wiki [/]', 'f', 'alt-shift-'), 'Search Matcha Flavoured Wiki [/]');
  assert.equal(A.label('Printable version [p] of this page', 'p', 'alt-shift-'), 'Printable version [p] of this page');
  assert.equal(A.label('', 'x', 'alt-shift-'), '');
  assert.equal(A.label('Load a random page [alt-shift-x]', 'x', 'alt-shift-'), 'Load a random page [alt-shift-x]');
});
