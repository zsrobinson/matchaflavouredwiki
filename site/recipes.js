// The recipe browser (the page "Matcha Flavoured Wiki:Recipe browser"; tools/export_static.py appends
// this to _static/site.js after site/search.js).
//
// Type an item and the page shows, the way an article does, how it is obtained (every recipe and
// trade that makes it) and what it is used for (every recipe that takes it, tags included: Oak Planks
// finds the recipes for "Any Planks"), each on the station screen the articles use, and a crafting
// tree that follows each ingredient down to raw materials. A station filter narrows every list, and
// with no item it lists that station's recipes. The data is _static/recipes.json
// (tools/recipe_browser.py): the recipes, and each slot's HTML as the wiki's Module:Inventory slot
// renders it, so the slots cycle (Gadget-animatedIcons.js) and show their in-game tooltips
// (Gadget-mfwTooltip.js) as everywhere else. Item names match as the search box matches titles
// (site/search.js: case, typos, British spellings, plurals, vanilla names).
//
// The data functions are plain and exported under Node for tests/recipes.test.mjs.
(function () {
	'use strict';

	// ---- Stations: Module:Station's screens, as that module draws them ----------------------------
	// Slot coordinates are in texture pixels (the top-left of the 16x16 item); screens show at 2x.
	var FURNACE = [['Input', 56, 17], ['Output', 116, 35]];
	var STATIONS = {
		crafting: { name: 'Crafting Table', group: 'Crafting', slots: [['A1', 30, 17], ['B1', 48, 17], ['C1', 66, 17],
			['A2', 30, 35], ['B2', 48, 35], ['C2', 66, 35], ['A3', 30, 53], ['B3', 48, 53], ['C3', 66, 53], ['Output', 124, 35]] },
		oven: { name: 'Oven', title: 'Oven', group: 'Cooking', slots: FURNACE, burns: true },
		kiln: { name: 'Mud Kiln', title: 'Mud Kiln', group: 'Cooking', slots: FURNACE, burns: true },
		kindling: { name: 'Kindling', title: 'Kindling', group: 'Cooking', slots: FURNACE, fire: true, arrow: 'oven' },
		blast: { name: 'Blast Furnace', title: 'Blast Furnace', group: 'Blasting', slots: FURNACE, burns: true },
		smithing: { name: 'Smithing Table', group: 'Smithing', slots: [['Template', 8, 48], ['Base', 26, 48], ['Addition', 44, 48], ['Output', 98, 48]] },
		stonecutter: { name: 'Stonecutter', title: 'Stonecutter', group: 'Stonecutting', slots: [['Input', 20, 33], ['Output', 143, 33]] },
		trade: { name: 'Villager trades', group: 'Trading', page: 'Trading' }
	};
	var ORDER = ['crafting', 'oven', 'kiln', 'kindling', 'blast', 'smithing', 'stonecutter', 'trade'];
	var GROUPS = ['Crafting', 'Cooking', 'Blasting', 'Smithing', 'Stonecutting', 'Trading'];
	// the order ingredients are listed in (a crafting grid by rows, as the articles' tables do)
	var SLOT_ORDER = ['Template', 'Base', 'Addition', 'Input', '1', '2', 'A1', 'B1', 'C1', 'A2', 'B2', 'C2', 'A3', 'B3', 'C3'];

	// ---- Data ----------------------------------------------------------------------------------
	// "Oak Log;Birch Log" or "Obol,3" -> [{name, count}]
	function parseSlot(text) {
		return String(text).split(';').map(function (s) { return s.trim(); }).filter(Boolean).map(function (s) {
			var m = s.match(/^(.*?),(\d+)$/);
			return m ? { name: m[1].trim(), count: +m[2] } : { name: s, count: 1 };
		});
	}
	// A row's input slots in listing order, the same slot text counted once: [[text, count]]
	function tally(row) {
		var out = [], at = {};
		SLOT_ORDER.forEach(function (k) {
			var t = row.g[k];
			if (!t) return;
			var n = parseSlot(t)[0].count;
			var name = t.replace(/,\d+$/, '');
			if (at[name] === undefined) { at[name] = out.length; out.push([name, 0]); }
			out[at[name]][1] += n;
		});
		return out;
	}
	// The item names a slot text accepts: its alternatives, and a tag alias's members
	function members(d, text) {
		var out = [];
		parseSlot(text).forEach(function (p) {
			(d.a[p.name] || [p.name]).forEach(function (n) { if (out.indexOf(n) < 0) out.push(n); });
		});
		return out;
	}

	// recipes.json -> lookups: rows by output and by input (a tag's members and the tag itself)
	function prepare(d) {
		var db = { d: d, rows: d.r, made: {}, used: {}, names: {}, from: {}, world: {} };
		(d.w || []).forEach(function (n) { db.world[n] = true; });
		function add(map, k, i) { (map[k] = map[k] || []).push(i); }
		function name(n) { db.names[n] = db.names[n] || { made: 0, used: 0 }; return db.names[n]; }
		d.r.forEach(function (r, i) {
			r.i = i;
			add(db.made, r.o, i);
			name(r.o).made++;
			var seen = {};
			Object.keys(r.g).forEach(function (k) {
				var text = r.g[k].replace(/,\d+$/, '');
				parseSlot(text).map(function (p) { return p.name; }).concat(members(d, text)).forEach(function (n) {
					// what is made from n: recipes that take it, or any of a tag with it (not a list of
					// alternatives: melting any iron tool back into an ingot doesn't make tools from ingots)
					if (r.s !== 'trade' && text.indexOf(';') < 0) (db.from[n] = db.from[n] || {})[r.o] = true;
					if (seen[n]) return;
					seen[n] = 1;
					add(db.used, n, i);
					name(n).used++;
				});
			});
		});
		return db;
	}
	function made(db, name, station) {
		return (db.made[name] || []).map(function (i) { return db.rows[i]; }).filter(function (r) { return !station || r.s === station; });
	}
	function used(db, name, station) {
		return (db.used[name] || []).map(function (i) { return db.rows[i]; }).filter(function (r) { return !station || r.s === station; });
	}

	// ---- Names ---------------------------------------------------------------------------------
	// The title matcher's rows (site/search.js: prepare) for every item and tag that has a recipe or a use
	function nameRows(db) {
		return Object.keys(db.names).sort().map(function (n) {
			var c = db.names[n], row = { t: n, u: n, n: c.made + c.used };
			if (db.d.n[n]) row.a = [db.d.n[n]];
			return row;
		});
	}
	// Items matching a query, best first: [{name, alias, exact}]
	function matchNames(S, index, query, limit) {
		// a tag ("Any Planks") before its members when they match as well
		return S.match(index, query, (limit || 8) * 3).map(function (m) {
			return { name: m.row.t, alias: m.alias, exact: m.base >= 950, score: m.base, rank: m.score + (/^Any /.test(m.row.t) ? 15 : 0) };
		}).sort(function (a, b) { return b.rank - a.rank; }).slice(0, limit || 8);
	}

	// ---- Crafting tree -------------------------------------------------------------------------
	// A recipe that undoes another: one of its slots takes only things made from its output (Coal
	// from a Block of Coal, Oak Planks from Oak Slabs, an ingot from nuggets). The tree lists these
	// last, and an item the world gives whose every recipe undoes another is a raw material (Coal is
	// mined; Oak Slabs, which only drop themselves, are still made from planks).
	function reverses(db, r) {
		var from = db.from[r.o] || {};
		return r.s !== 'trade' && tally(r).some(function (t) { return members(db.d, t[0]).every(function (m) { return from[m]; }); });
	}
	// Each item's depth: 0 for a raw material (no recipe), else the fewest steps down to raw
	// materials over its recipes (trades aside). Relaxed until nothing changes, so loops (ingot <->
	// block) can't hold it up. Items made only from each other (Oak Log and Oak Wood, a loop nothing
	// outside it feeds) are gathered, not made: that loop becomes raw materials, and the rest is
	// relaxed again, until every item has a depth.
	function depths(db) {
		if (db.depth) return db.depth;
		var depth = {};
		function of(name) { return depth[name] === undefined ? (db.made[name] && db.made[name].some(crafted) ? Infinity : 0) : depth[name]; }
		function crafted(i) { return db.rows[i].s !== 'trade' && !(db.world[db.rows[i].o] && undone(db.rows[i].o)); }
		function undone(name) { return db.made[name].every(function (i) { return db.rows[i].s === 'trade' || reverses(db, db.rows[i]); }); }
		function slotDepth(text) { return Math.min.apply(null, members(db.d, text).map(of)); }
		function relax() {
			var changed = true, rounds = 0;
			while (changed && rounds++ < 200) {
				changed = false;
				Object.keys(db.made).forEach(function (name) {
					var best = of(name);
					db.made[name].forEach(function (i) {
						var r = db.rows[i];
						if (!crafted(i)) return;
						var dd = 1 + Math.max.apply(null, [0].concat(tally(r).map(function (t) { return slotDepth(t[0]); })));
						if (dd < best) best = dd;
					});
					if (depth[name] !== best) { depth[name] = best; changed = true; }
				});
			}
		}
		// the items an unmade item waits on: every unmade member of each slot of each of its recipes
		function waits(name) {
			var out = [];
			db.made[name].forEach(function (i) {
				var r = db.rows[i];
				if (!crafted(i)) return;
				tally(r).forEach(function (t) {
					members(db.d, t[0]).forEach(function (m) { if (of(m) === Infinity && out.indexOf(m) < 0) out.push(m); });
				});
			});
			return out;
		}
		// Tarjan's strongly connected components of the unmade items; a component that waits on
		// nothing outside itself is a gathered loop
		function gathered() {
			var todo = Object.keys(db.made).filter(function (n) { return of(n) === Infinity; }).sort();
			var num = {}, low = {}, stack = [], on = {}, next = 0, found = [];
			function visit(v) {
				num[v] = low[v] = next++;
				stack.push(v); on[v] = true;
				waits(v).forEach(function (w) {
					if (num[w] === undefined) { visit(w); low[v] = Math.min(low[v], low[w]); } else if (on[w]) low[v] = Math.min(low[v], num[w]);
				});
				if (low[v] !== num[v]) return;
				var comp = [], w;
				do { w = stack.pop(); on[w] = false; comp.push(w); } while (w !== v);
				var closed = comp.every(function (x) { return waits(x).every(function (y) { return comp.indexOf(y) >= 0; }); });
				if (closed) found = found.concat(comp);
			}
			todo.forEach(function (v) { if (num[v] === undefined) visit(v); });
			return found;
		}
		relax();
		for (var round = 0; round < 50; round++) {
			var loops = gathered();
			if (!loops.length) break;
			loops.forEach(function (n) { depth[n] = 0; });
			relax();
		}
		db.depth = depth;
		return depth;
	}
	function depthOf(db, name) {
		var dd = depths(db)[name];
		return dd === undefined ? 0 : dd;
	}
	// The recipes a tree can use for an item, easiest first: fewest steps to raw materials (a recipe
	// that undoes another last), then the station's order (a crafting table before a stonecutter),
	// then fewer kinds of ingredient
	function treeRecipes(db, name) {
		var depth = depths(db);
		function cost(r) {
			return 1 + Math.max.apply(null, [0].concat(tally(r).map(function (t) {
				return Math.min.apply(null, members(db.d, t[0]).map(function (n) { return depth[n] === undefined ? 0 : depth[n]; }));
			})));
		}
		return made(db, name).filter(function (r) { return r.s !== 'trade'; }).map(function (r) {
			return { r: r, cost: cost(r) + (reverses(db, r) ? 1000 : 0) };
		}).sort(function (a, b) {
			return a.cost - b.cost || ORDER.indexOf(a.r.s) - ORDER.indexOf(b.r.s) || tally(a.r).length - tally(b.r).length || a.r.i - b.r.i;
		}).map(function (x) { return x.r; });
	}
	// The member a tree follows for a slot with several items: the easiest to make, then one the world
	// gives (Raw Iron, not Iron Horse Armor), then the first
	function easiest(db, text) {
		var ms = members(db.d, text);
		return ms.slice().sort(function (a, b) {
			return depthOf(db, a) - depthOf(db, b) || (db.world[b] ? 1 : 0) - (db.world[a] ? 1 : 0) || ms.indexOf(a) - ms.indexOf(b);
		})[0];
	}
	// The tree for `need` of a slot text: {text, name, need, recipe, recipes, crafts, children, loop}.
	// choices: {itemName: recipe row index or -1 for "use as it is", 'any:<slot text>': member name}, the reader's picks.
	function tree(db, text, need, choices, path) {
		choices = choices || {};
		path = path || [];
		var ms = members(db.d, text);
		var name = ms.length > 1 ? (ms.indexOf(choices['any:' + text]) >= 0 ? choices['any:' + text] : easiest(db, text)) : ms[0];
		var node = { text: text, name: name, need: need, children: [] };
		if (path.indexOf(name) >= 0) { node.loop = true; return node; }
		var rs = treeRecipes(db, name);
		node.recipes = rs;
		if (!rs.length || path.length >= 16) return node;
		var r = rs.filter(function (x) { return x.i === choices[name]; })[0] || rs[0];
		if (!depthOf(db, name) && choices[name] === undefined) return node;  // a raw material, or gathered (see depths)
		if (choices[name] === -1 && path.length) return node;  // the reader has it already
		node.recipe = r;
		node.crafts = Math.ceil(need / (r.c || 1));
		node.children = tally(r).map(function (t) { return tree(db, t[0], t[1] * node.crafts, choices, path.concat(name)); });
		return node;
	}
	// The raw materials a tree ends in, most first: [[slot text, count]]
	function totals(node) {
		var sum = {}, order = [];
		(function walk(n) {
			if (n.children.length) { n.children.forEach(walk); return; }
			var k = n.loop || n.text.indexOf(';') >= 0 ? n.name : n.text;  // a tag stays a tag: any of its members will do
			if (sum[k] === undefined) { sum[k] = 0; order.push(k); }
			sum[k] += n.need;
		})(node);
		return order.map(function (k) { return [k, sum[k]]; }).sort(function (a, b) { return b[1] - a[1] || order.indexOf(a[0]) - order.indexOf(b[0]); });
	}

	var api = { STATIONS: STATIONS, parseSlot: parseSlot, tally: tally, members: members, prepare: prepare, made: made, used: used,
		nameRows: nameRows, matchNames: matchNames, depths: depths, treeRecipes: treeRecipes, tree: tree, totals: totals };
	if (typeof module !== 'undefined' && module.exports) { module.exports = api; }
	if (typeof document === 'undefined') return;

	var root = document.getElementById('mfw-recipes');
	if (!root || !window.mfwSearch) return;
	var S = window.mfwSearch;

	// ---- Drawing -------------------------------------------------------------------------------
	var db, index;
	function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
	function wikiUrl(title) { return '/w/' + encodeURIComponent(title.replace(/ /g, '_')).replace(/%2F/g, '/').replace(/%3A/g, ':'); }
	function px(n) { return n * 2 + 'px'; }
	function at(x, y) { return ' style="left:' + px(x) + ';top:' + px(y) + '"'; }
	// A slot, with a stack size as Module:Inventory slot draws one; plain: no link (the stonecutter's list)
	function slot(text, count, plain) {
		var name = text.replace(/,\d+$/, ''), m = text.match(/,(\d+)$/);
		count = count || (m ? +m[1] : 1);
		var h = db.d.h[name];
		if (!h) {
			// alternatives ("Oak Log;Birch Log") cycle like a tag's members
			var parts = parseSlot(name).filter(function (p) { return db.d.h[p.name]; });
			if (!parts.length) return '<span class="invslot"></span>';
			h = parts.length === 1 ? db.d.h[parts[0].name] : '<span class="invslot animated">' + parts.map(function (p, i) {
				return db.d.h[p.name].replace(/^<span class="invslot[^"]*">/, '').replace(/<\/span>$/, '')
					.replace('class="invslot-item', 'class="invslot-item' + (i ? '' : ' animated-active'));
			}).join('') + '</span>';
		}
		if (plain) h = h.replace(/<a [^>]*>|<\/a>/g, '');
		if (count > 1) {
			var tmp = document.createElement('span');
			tmp.innerHTML = h;
			Array.prototype.forEach.call(tmp.querySelectorAll('.invslot-item'), function (item) {
				var a = item.querySelector('a');
				var size = '<span class="invslot-stacksize">' + count + '</span>';
				item.insertAdjacentHTML('beforeend', a && !plain ? '<a href="' + esc(a.getAttribute('href')) + '">' + size + '</a>' : size);
			});
			h = tmp.innerHTML;
		}
		return h;
	}
	// A link to an item's page (here, or minecraft.wiki); a tag alias explains its members, as the tables do
	function link(name, label) {
		if (db.d.a[name]) return '<span class="explain" title="' + esc(db.d.a[name].join(', ')) + '">' + esc(name.replace(/^Any (.)/, function (m, c) { return 'Any ' + c.toLowerCase(); })) + '</span>';
		var u = db.d.u[name];
		return u ? '<a href="' + esc(u) + '"' + (/^https?:/.test(u) ? ' class="extiw"' : '') + ' title="' + esc(name) + '">' + esc(label || name) + '</a>' : esc(label || name);
	}
	function pageLink(title, label) {
		return '<a href="' + wikiUrl(title) + '" title="' + esc(title) + '">' + esc(label || title) + '</a>';
	}
	function slotLinks(text) {
		return parseSlot(text).map(function (p) { return link(p.name); }).join(' or ');
	}
	function ingredients(row) {
		return tally(row).map(function (t) { return (t[1] > 1 ? t[1] + ' × ' : '') + slotLinks(t[0]); }).join(' +<br>');
	}
	// The station screen of one recipe (Module:Station: screen), or a villager's offer (Module:Station: trade)
	function screen(r) {
		var out = r.o + (r.c > 1 ? ',' + r.c : '');
		if (r.s === 'trade') {
			return '<span class="mfui-trade">' + [['1', 5, 1], ['2', 35, 1]].filter(function (p) { return r.g[p[0]]; }).map(function (p) {
				return '<span class="mfui-slot"' + at(p[1], p[2]) + '>' + slot(r.g[p[0]]) + '</span>';
			}).join('') + '<span class="mfui-slot"' + at(68, 1) + '>' + slot(out) + '</span><span class="mfui-trade-arrow"' + at(55, 4) + '></span></span>';
		}
		var st = STATIONS[r.s], h = '<div class="mfui mfui-' + r.s + '" role="figure">';
		if (st.title) h += '<span class="mfui-title"' + at(8, 6) + '><a href="' + wikiUrl(st.title) + '" title="' + esc(st.title) + '">' + esc(st.title) + '</a></span>';
		if (st.burns) h += '<span class="mfui-lit"' + at(56, 36) + '></span>';
		if (st.fire) h += '<span class="mfui-campfire" style="left:112px;top:74px" title="Kindling"></span>';
		if (st.burns || st.fire) {
			var t = r.t ? Math.min(Math.max(r.t, 1), 20) : 0;
			h += '<span class="mfui-progress mfui-progress-' + (st.arrow || r.s) + '" style="left:158px;top:68px' + (t ? ';animation-duration:' + t + 's' : '') + '"></span>';
		}
		if (r.l) h += '<span class="mfui-shapeless"' + at(156, 5) + ' title="Shapeless: the ingredients can go anywhere in the grid."></span>';
		if (r.s === 'stonecutter') h += '<span class="mfui-stonecutter-selected"' + at(52, 14) + '></span><span class="mfui-stonecutter-scroller"' + at(119, 15) + '></span>';
		st.slots.forEach(function (p) {
			var text = p[0] === 'Output' ? out : r.g[p[0]];
			if (text) h += '<span class="mfui-slot' + (p[0] === 'Output' ? ' mfui-output' : '') + '"' + at(p[1], p[2]) + '>' + slot(text) + '</span>';
		});
		if (r.s === 'stonecutter') h += '<span class="mfui-slot mfui-slot-plain"' + at(52, 15) + '>' + slot(r.o, 1, true) + '</span>';
		h += '</div>';
		var note = [];
		if (r.t) note.push(r.t + ' s' + (r.x ? ', ' + r.x + ' XP' : ''));
		if (r.s === 'kindling') note.push('also on ' + link('Soul Kindling'));
		return '<div class="mfui-figure">' + h + (note.length ? '<div class="mfui-caption">' + note.join(' · ') + '</div>' : '') + '</div>';
	}
	// A slot's text in a few words: "Iron Pickaxe or …" for a long list of alternatives
	function short(text) {
		var ps = parseSlot(text);
		return ps[0].name + (ps.length > 1 ? ' or …' : '');
	}
	function heading(level, text, id) {
		return '<div class="mw-heading mw-heading' + level + '"><h' + level + (id ? ' id="' + esc(id) + '"' : '') + '>' + text + '</h' + level + '></div>';
	}
	// One table per kind of station, as an article's Obtaining and Usage sections have them
	var PAGE = 25;
	function tables(rows, key) {
		var groups = {};
		rows.forEach(function (r) { (groups[STATIONS[r.s].group] = groups[STATIONS[r.s].group] || []).push(r); });
		var names = GROUPS.filter(function (g) { return groups[g]; });
		return names.map(function (g) {
			var rs = groups[g], trade = g === 'Trading', more = rs.length > PAGE;
			var head = trade ? '<tr><th>Name</th><th>Villager wants</th><th>Offer</th></tr>' : '<tr><th>Name</th><th>Ingredients</th><th>Recipe</th></tr>';
			return (names.length > 1 ? '<p><b>' + g + '</b></p>' : '') +
				'<table class="wikitable recipe-table mfw-rb-table" data-key="' + esc(key + ':' + g) + '"><tbody>' + head +
				rs.slice(0, PAGE).map(tableRow).join('') + '</tbody></table>' +
				(more ? '<p class="mfw-rb-more"><button type="button" class="mfw-rb-button" data-more="' + esc(key + ':' + g) + '">Show all ' + rs.length + ' recipes</button></p>' : '');
		}).join('');
	}
	var pending = {};  // table key -> rows not drawn yet
	function tableRow(r) {
		if (r.s === 'trade') {
			return '<tr><td>' + link(r.o) + '</td><td>' + tally(r).map(function (t) { return (t[1] > 1 ? t[1] + ' × ' : '') + slotLinks(t[0]); }).join(' +<br>') +
				'<br><small><a href="' + wikiUrl(r.p) + '">' + esc(r.p) + '</a>, ' + esc(r.lv) + '</small></td><td>' + screen(r) + '</td></tr>';
		}
		return '<tr><td>' + link(r.o) + (r.v ? ' <small>(vanilla recipe)</small>' : '') + '</td><td class="ingredients">' + ingredients(r) + '</td><td>' + screen(r) + '</td></tr>';
	}
	function tablesWithRest(rows, key) {
		var groups = {};
		rows.forEach(function (r) { (groups[STATIONS[r.s].group] = groups[STATIONS[r.s].group] || []).push(r); });
		Object.keys(groups).forEach(function (g) { pending[key + ':' + g] = groups[g].slice(PAGE); });
		return tables(rows, key);
	}

	// The crafting tree: each ingredient under what it makes, as far as raw materials
	var choices = {};
	function treeHtml(node, top) {
		var h = '<li' + (node.children.length ? ' class="mfw-rb-open"' : '') + '><span class="mfw-rb-node">';
		h += node.children.length ? '<button type="button" class="mfw-rb-toggle" aria-expanded="true" title="Hide the ingredients"></button>' : '<span class="mfw-rb-toggle-space"></span>';
		h += slot(node.text.indexOf(';') < 0 ? node.text : node.name, node.need) + ' <span class="mfw-rb-label">' + (node.need > 1 ? node.need + ' × ' : '') + link(node.text.indexOf(';') < 0 ? node.text : node.name) + '</span>';
		if (node.text !== node.name && node.recipe) h += ' <span class="mfw-rb-how">as ' + link(node.name) + '</span>';
		var ms = members(db.d, node.text);
		if (ms.length > 1 && node.recipe) {  // which member to make; a raw tag is any of them
			h += ' <select class="mfw-rb-pick" data-any="' + esc(node.text) + '" aria-label="Which item">' + ms.map(function (m) {
				return '<option' + (m === node.name ? ' selected' : '') + '>' + esc(m) + '</option>';
			}).join('') + '</select>';
		}
		if (node.loop) {
			h += ' <span class="mfw-rb-how">(already above: a loop)</span>';
		} else if (node.recipe) {
			h += ' <span class="mfw-rb-how">' + (node.crafts > 1 ? node.crafts + ' × ' : '') + link(STATIONS[node.recipe.s].name) + '</span>';
		} else if (!top) {
			h += ' <span class="mfw-rb-how">' + (made(db, node.name, 'trade').length ? 'raw material, or traded' : 'raw material') + '</span>';
		}
		// the recipe to follow, or none: any ingredient can be taken as it is, or made after all
		// (a raw material only when a recipe makes it from something else: not Raw Iron from its block)
		if (!node.loop && node.recipes && node.recipes.length && (!top || node.recipes.length > 1) &&
				(node.recipe || node.recipes.some(function (r) { return !reverses(db, r); }))) {
			h += ' <select class="mfw-rb-pick" data-item="' + esc(node.name) + '" aria-label="How to get ' + esc(node.name) + '">' +
				(top ? '' : '<option value="-1"' + (node.recipe ? '' : ' selected') + '>As it is</option>') + node.recipes.map(function (r, i) {
					return '<option value="' + r.i + '"' + (r === node.recipe ? ' selected' : '') + '>' + esc(STATIONS[r.s].name + ': ' +
						tally(r).map(function (t) { return (t[1] > 1 ? t[1] + ' ' : '') + short(t[0]); }).join(', ')) + '</option>';
				}).join('') + '</select>';
		}
		h += '</span>';
		if (node.children.length) h += '<ul>' + node.children.map(function (c) { return treeHtml(c); }).join('') + '</ul>';
		return h + '</li>';
	}
	function treeSection(name) {
		var node = tree(db, name, 1, choices);
		if (!node.recipe) return '';
		var sum = totals(node);
		return heading(2, 'Crafting tree', 'Crafting_tree') +
			'<p>Everything that goes into one ' + link(name) + ', down to raw materials. Where there is a choice, the tree follows the recipe with the fewest steps; pick another from the list beside it.</p>' +
			'<ul class="mfw-rb-tree">' + treeHtml(node, true) + '</ul>' +
			'<p><b>Raw materials:</b></p><ul class="mfw-rb-totals">' + sum.map(function (t) {
				return '<li>' + slot(t[0], t[1]) + ' <span>' + (t[1] > 1 ? t[1] + ' × ' : '') + slotLinks(t[0]) + '</span></li>';
			}).join('') + '</ul>';
	}

	// ---- The page --------------------------------------------------------------------------------
	root.innerHTML =
		'<form class="mfw-rb-form" role="search" action="">' +
		'<div class="mfw-rb-box"><input type="search" id="mfw-rb-q" name="q" placeholder="Item, for example Bread or Iron Ingot" aria-label="Item" ' +
		'autocomplete="off" spellcheck="false" role="combobox" aria-autocomplete="list" aria-controls="mfw-rb-suggest" aria-expanded="false">' +
		'<div id="mfw-rb-suggest" class="mfw-suggest" role="listbox" aria-label="Items" hidden></div></div>' +
		'<select id="mfw-rb-station" name="station" aria-label="Station"><option value="">All stations and trades</option>' +
		ORDER.map(function (k) { return '<option value="' + k + '">' + esc(STATIONS[k].name) + '</option>'; }).join('') + '</select>' +
		'<button type="submit">Look up</button></form>' +
		'<div id="mfw-rb-out" aria-live="polite"><p>Loading the recipes…</p></div>';
	var form = root.querySelector('form'), input = document.getElementById('mfw-rb-q'), station = document.getElementById('mfw-rb-station');
	var out = document.getElementById('mfw-rb-out'), box = document.getElementById('mfw-rb-suggest');

	function intro() {
		var counts = {};
		db.rows.forEach(function (r) { counts[r.s] = (counts[r.s] || 0) + 1; });
		return '<p>Type an item above to see how it is made and what it makes. Or browse a station:</p>' +
			'<table class="wikitable mfw-rb-stations"><tbody><tr><th colspan="2">Station</th><th>Recipes</th></tr>' + ORDER.map(function (k) {
				var st = STATIONS[k];
				return '<tr><td>' + (db.d.h[st.name] ? slot(st.name) : '') + '</td><td>' + pageLink(st.page || st.name, st.name) + '</td>' +
					'<td><a href="?station=' + k + '" data-station="' + k + '">' + counts[k] + ' ' + (k === 'trade' ? 'offers' : 'recipes') + '</a></td></tr>';
			}).join('') + '</tbody></table>';
	}
	function show(name, st) {
		pending = {};
		if (!name) {
			if (!st) { out.innerHTML = intro(); return; }
			var all = db.rows.filter(function (r) { return r.s === st; });
			out.innerHTML = heading(2, esc(STATIONS[st].name), null) + '<p>' + all.length + ' ' + (st === 'trade' ? 'offers' : 'recipes') +
				', by what they make. See also ' + pageLink(STATIONS[st].page || STATIONS[st].name, STATIONS[st].name) + '.</p>' + tablesWithRest(all, 'all');
			return;
		}
		var mk = made(db, name, st), us = used(db, name, st);
		var nm = db.names[name] || { made: 0, used: 0 };
		var h = '<div class="mfw-rb-item">' + slot(name) + '<div><b>' + link(name) + '</b>' +
			(db.d.a[name] ? '<br><small>Any of: ' + db.d.a[name].map(function (m) { return link(m); }).join(', ') + '</small>' : '') +
			(db.d.n[name] ? '<br><small>' + esc(db.d.n[name]) + ' in vanilla</small>' : '') + '</div></div>';
		var filter = st ? ' at the ' + esc(STATIONS[st].name) : '';
		h += heading(2, 'Obtaining', 'Obtaining') + (mk.length ? tablesWithRest(mk, 'made') :
			'<p>No recipe' + (st ? filter : ' or trade') + ' makes ' + esc(name) + '.' + (nm.made ? ' <a href="?q=' + encodeURIComponent(name) + '" data-q="' + esc(name) + '">Show every station</a>.' : ' See its page for where to find it.') + '</p>');
		h += heading(2, 'Usage', 'Usage') + (us.length ? tablesWithRest(us, 'used') :
			'<p>No recipe' + filter + ' uses ' + esc(name) + '.' + (st && nm.used ? ' <a href="?q=' + encodeURIComponent(name) + '" data-q="' + esc(name) + '">Show every station</a>.' : '') + '</p>');
		h += treeSection(name);
		out.innerHTML = h;
	}
	function current() {
		var p = new URLSearchParams(location.search);
		return { q: (p.get('q') || '').trim(), station: STATIONS[p.get('station')] ? p.get('station') : '' };
	}
	// The item a query names: itself if it is one, else the best match
	function resolve(q) {
		if (!q) return null;
		if (db.names[q]) return q;
		var m = matchNames(S, index, q, 1)[0];
		return m && m.score >= 450 ? m.name : null;
	}
	function render(push) {
		var c = current(), name = resolve(c.q);
		input.value = name || c.q;
		station.value = c.station;
		choices = {};
		document.title = (name ? name + ' – ' : c.station ? STATIONS[c.station].name + ' – ' : '') + 'Recipe browser – Matcha Flavoured Wiki';
		if (c.q && !name) {
			out.innerHTML = '<p>No item matches “' + esc(c.q) + '”. Try the ' + '<a href="/search/?q=' + encodeURIComponent(c.q) + '">site search</a>.</p>';
			return;
		}
		show(name, c.station);
		if (push && root.getBoundingClientRect().top < 0) root.scrollIntoView();
	}
	function go(q, st, push) {
		var p = new URLSearchParams();
		if (q) p.set('q', q);
		if (st) p.set('station', st);
		var url = location.pathname + (p.toString() ? '?' + p : '');
		if (url !== location.pathname + location.search) history[push ? 'pushState' : 'replaceState'](null, '', url);
		render(push);
	}
	window.addEventListener('popstate', function () { render(false); });

	// ---- Suggestions, as the header box makes them ----------------------------------------------
	var active = -1;
	function thumb(name) {
		var m = (db.d.h[name] || '').match(/<img [^>]*src="([^"]+)"/);
		return '<span class="mfw-suggest-thumb">' + (m ? '<img src="' + esc(m[1]) + '" alt="" loading="lazy">' : '') + '</span>';
	}
	function suggest() {
		var q = input.value.trim();
		if (!q) { open(false); return; }
		var ms = matchNames(S, index, q, 8);
		box.innerHTML = ms.length ? ms.map(function (m, i) {
			var c = db.names[m.name];
			var note = m.alias ? esc(m.alias) + ' in vanilla' : (c.made ? c.made + ' way' + (c.made === 1 ? '' : 's') + ' to get' : 'raw material') +
				(c.used ? ' · used in ' + c.used : '');
			return '<a class="mfw-suggest-item" id="mfw-rb-s' + i + '" role="option" aria-selected="false" href="?q=' + encodeURIComponent(m.name) + '" data-q="' + esc(m.name) + '">' +
				thumb(m.name) + '<span class="mfw-suggest-text"><span class="mfw-suggest-title">' + esc(m.name) + '</span><span class="mfw-suggest-desc">' + note + '</span></span></a>';
		}).join('') : '<div class="mfw-suggest-empty">No item matches “' + esc(q) + '”.</div>';
		active = -1;
		open(true);
	}
	function open(on) {
		box.hidden = !on;
		input.setAttribute('aria-expanded', on ? 'true' : 'false');
		if (!on) { active = -1; input.removeAttribute('aria-activedescendant'); }
	}
	function highlight(i) {
		var all = box.querySelectorAll('.mfw-suggest-item');
		if (!all.length) return;
		if (all[active]) all[active].classList.remove('mfw-suggest-current'), all[active].setAttribute('aria-selected', 'false');
		active = (i + all.length + 1) % (all.length + 1) - 1;  // -1: back in the box
		if (active >= 0) {
			all[active].classList.add('mfw-suggest-current');
			all[active].setAttribute('aria-selected', 'true');
			input.setAttribute('aria-activedescendant', all[active].id);
		} else {
			input.removeAttribute('aria-activedescendant');
		}
	}
	input.addEventListener('input', function () { if (db) suggest(); });
	input.addEventListener('keydown', function (e) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			if (box.hidden) { suggest(); return; }
			e.preventDefault();
			highlight(active + (e.key === 'ArrowDown' ? 1 : -1));
		} else if (e.key === 'Escape') {
			open(false);
		}
	});
	input.addEventListener('blur', function () { setTimeout(function () { if (document.activeElement !== input) open(false); }, 150); });
	box.addEventListener('mousedown', function (e) { e.preventDefault(); });
	form.addEventListener('submit', function (e) {
		e.preventDefault();
		if (!db) return;
		var all = box.querySelectorAll('.mfw-suggest-item'), q = input.value.trim();
		var pick = !box.hidden && all[active] ? all[active].getAttribute('data-q') : resolve(q) || q;
		open(false);
		go(pick, station.value, true);
	});
	station.addEventListener('change', function () { if (db) go(resolve(input.value.trim()) || '', station.value, true); });

	// Links within the browser (suggestions, station counts), "Show all" buttons and the tree's controls
	root.addEventListener('click', function (e) {
		var a = e.target.closest('a[data-q], a[data-station]');
		if (a && !e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) {
			e.preventDefault();
			open(false);
			if (a.hasAttribute('data-station')) go('', a.getAttribute('data-station'), true);
			else go(a.getAttribute('data-q'), a.closest('#mfw-rb-suggest') ? station.value : '', true);
			return;
		}
		var more = e.target.closest('[data-more]');
		if (more) {
			var key = more.getAttribute('data-more'), table = out.querySelector('table[data-key="' + key.replace(/"/g, '\\"') + '"] > tbody');
			if (table && pending[key]) table.insertAdjacentHTML('beforeend', pending[key].map(tableRow).join(''));
			delete pending[key];
			more.parentNode.remove();
			return;
		}
		var toggle = e.target.closest('.mfw-rb-toggle');
		if (toggle) {
			var li = toggle.closest('li'), openNow = !li.classList.contains('mfw-rb-open');
			li.classList.toggle('mfw-rb-open', openNow);
			toggle.setAttribute('aria-expanded', openNow ? 'true' : 'false');
			toggle.title = openNow ? 'Hide the ingredients' : 'Show the ingredients';
		}
	});
	root.addEventListener('change', function (e) {
		var sel = e.target.closest('.mfw-rb-pick');
		if (!sel) return;
		if (sel.hasAttribute('data-item')) choices[sel.getAttribute('data-item')] = +sel.value;
		else choices['any:' + sel.getAttribute('data-any')] = sel.value;
		var c = current(), sec = out.querySelector('#Crafting_tree');
		if (!sec) return;
		var wrap = sec.parentNode, next;
		while ((next = wrap.nextSibling)) next.remove();  // the tree is the last section
		wrap.outerHTML = treeSection(resolve(c.q));
	});

	fetch(root.getAttribute('data-src')).then(function (r) { return r.json(); }).then(function (d) {
		db = prepare(d);
		index = S.prepare(nameRows(db));
		render(false);
	}).catch(function () {
		out.innerHTML = '<p>The recipes could not be loaded. Every item’s page also lists its recipes and uses.</p>';
	});
})();
