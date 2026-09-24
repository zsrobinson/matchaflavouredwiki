// Search for the static site (tools/export_static.py appends this to _static/site.js).
//
// A wiki's search box finds pages by name first. Pagefind alone ranks by the words in the text, so
// "fishing" used to list Tropical Fish and Flying Fish (short pages, and "fishing" stems to "fish")
// before the Fishing page, typos found nothing, and redirects like "Armour" did not exist for it.
// So the box does what MediaWiki's does: it matches titles and redirects (search_index.py writes
// _static/search-titles.json), forgiving case, punctuation, accents, British spellings, plurals,
// typos and question words, with each page's picture; then it fills the list with Pagefind's
// full-text results. The search page draws the same list in full, with the sections that matched and a
// category filter (Pagefind is only the full-text engine here, not the interface), and the 404 page
// offers the pages closest to the address.
//
// The matching functions are plain and exported under Node for tests/search.test.mjs.
(function () {
	'use strict';

	// ---- Matching ------------------------------------------------------------------------------
	// One spelling for words the wiki (or its readers) write two ways
	var SPELLING = {
		armour: 'armor', armoured: 'armored', colour: 'color', coloured: 'colored', colours: 'colors',
		flavour: 'flavor', flavoured: 'flavored', flavours: 'flavors', favour: 'favor', favourite: 'favorite',
		grey: 'gray', jewellery: 'jewelry', sulphur: 'sulfur', sulphurous: 'sulfurous',
		stabilised: 'stabilized', stabilise: 'stabilize', archaeologist: 'archeologist', archaeology: 'archeology',
		archaeologists: 'archeologists', centre: 'center', metre: 'meter', fibre: 'fiber', mould: 'mold',
		plough: 'plow', honour: 'honor', savoury: 'savory', harbour: 'harbor', neighbour: 'neighbor'
	};
	// Words that wrap a question around the thing asked about ("how do I get obol")
	var LEAD = /^(?:(?:how|where|what|which|who|when|why)(?: (?:do|does|did|can|could|should|would|to|is|are|was|i|you|we|much|many|long))*|(?:can|do|does|is|are) (?:i|you|we)|(?:the )?best(?: way(?: to)?)?|ways? to|guide(?: to| for)?)(?: |$)/;
	var VERB = /^(?:get|getting|make|making|craft|crafting|find|finding|obtain|use|using|build|unlock|farm|breed|tame|cure|kill|beat|defeat|summon|spawn|brew|smelt|grow|upgrade|reach|go|enter|catch)(?: |$)/;
	var ARTICLE = /^(?:a|an|the|some|my)(?: |$)/;
	var TAIL = / (?:do|does|work|works|list|guide|recipe|recipes|wiki|in minecraft|in matcha flavou?red)$/;

	function fold(s) {
		return String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
			.replace(/&/g, ' and ').replace(/['’‘`´]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
	}
	function stem(w) {
		if (w.length <= 3 || /\d/.test(w)) return w;
		if (/ies$/.test(w)) return w.slice(0, -3) + 'y';
		if (/(?:ss|us|is|os|as)$/.test(w)) return w;
		return w.replace(/s$/, '');
	}
	// A name (or a query) in every form the matcher compares
	function key(s) {
		var words = fold(s).split(' ').filter(Boolean).map(function (w) { return SPELLING[w] || w; });
		var stems = words.map(stem);
		return { raw: words.join(' '), stem: stems.join(' '), compact: words.join(''), words: words, stems: stems };
	}

	// Damerau-Levenshtein distance, giving up (returning max + 1) once it exceeds max
	function distance(a, b, max) {
		if (Math.abs(a.length - b.length) > max) return max + 1;
		var prev2 = null, prev = [], cur, i, j;
		for (j = 0; j <= b.length; j++) prev[j] = j;
		for (i = 1; i <= a.length; i++) {
			cur = [i];
			var best = i;
			for (j = 1; j <= b.length; j++) {
				var cost = a[i - 1] === b[j - 1] ? 0 : 1;
				var v = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
				if (prev2 && i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) v = Math.min(v, prev2[j - 2] + 1);
				cur[j] = v;
				if (v < best) best = v;
			}
			if (best > max) return max + 1;
			prev2 = prev;
			prev = cur;
		}
		return prev[b.length];
	}
	function allowed(len) { return len < 4 ? 0 : len < 7 ? 1 : len < 11 ? 2 : 3; }

	// How well one query form matches one name; 0 for not at all. Rough bands: 1000 exact, 950 exact
	// but for plurals or spaces, 800 the name starts with the query, 700 its words start with the query's
	// words, 520 one typo, 500 the query mentions the whole name, 450 each word nearly matches.
	function score(q, n) {
		if (!q.raw || !n.raw) return 0;
		if (q.raw === n.raw) return 1000;
		if (q.stem === n.stem) return 970;
		if (q.compact.length >= 4 && q.compact === n.compact) return 950;
		// completions: shorter first, and finishing the word before adding words ("est": Estus, then Estus Ash)
		var extra = Math.min(100, 4 * (n.raw.length - q.raw.length) + 12 * (n.words.length - q.words.length));
		if (n.raw.indexOf(q.raw) === 0) return 800 - extra;
		if (q.compact.length >= 4 && n.compact.indexOf(q.compact) === 0) return 780 - extra;
		var best = 0;
		// every query word starts a different word of the name ("kil" -> Mud Kiln, "sword iron" -> Iron Sword)
		var used = [], i, j, ok = true, moved = 0;
		for (i = 0; i < q.stems.length && ok; i++) {
			ok = false;
			for (j = 0; j < n.stems.length; j++) {
				if (used[j]) continue;
				var last = i === q.stems.length - 1;
				if (n.stems[j] === q.stems[i] || n.words[j] === q.words[i] || (last && n.words[j].indexOf(q.words[i]) === 0)) {
					used[j] = true; ok = true; if (j !== i) moved++; break;
				}
			}
		}
		if (ok) best = 700 - 15 * (n.words.length - q.words.length) - 10 * moved;
		// a typo in the whole name
		var d = distance(q.raw, n.raw, allowed(q.raw.length));
		if (d <= allowed(q.raw.length)) best = Math.max(best, 600 - 80 * d);
		d = distance(q.compact, n.compact, allowed(q.compact.length));
		if (d <= allowed(q.compact.length)) best = Math.max(best, 590 - 80 * d);
		// the query names the page and says more ("fishing rod enchantments" -> Fishing Rod)
		if (q.stems.length > n.stems.length) {
			var all = n.stems.every(function (s) { return q.stems.indexOf(s) >= 0; });
			if (all) best = Math.max(best, 500 + 25 * n.stems.length - 10 * (q.stems.length - n.stems.length));
		}
		// each query word is close to a different word of the name (typos while typing)
		if (!best || best < 450) {
			var total = 0;
			used = [];
			ok = true;
			for (i = 0; i < q.words.length && ok; i++) {
				var w = q.words[i], m = allowed(w.length), found = -1, fd = m + 1;
				for (j = 0; j < n.words.length; j++) {
					if (used[j]) continue;
					var nw = n.words[j];
					var dd = distance(w, nw, m);
					if (i === q.words.length - 1 && nw.length > w.length) dd = Math.min(dd, distance(w, nw.slice(0, w.length), m));
					if (dd < fd) { fd = dd; found = j; }
				}
				if (found < 0 || fd > m) ok = false; else { used[found] = true; total += fd; }
			}
			if (ok && total) best = Math.max(best, 450 - 60 * total - 15 * (n.words.length - q.words.length));
		}
		return Math.max(0, best);
	}

	// The forms a query is tried in: as typed, without the question around it, and "how to cook" as "cooking"
	function variants(query) {
		var out = [{ k: key(query), bonus: 0 }];
		var s = out[0].k.raw, t = s, prev;
		if (s.indexOf(' ') < 0) return out;
		do {
			prev = t;
			t = t.replace(LEAD, '').replace(VERB, '').replace(ARTICLE, '').replace(TAIL, '');
		} while (t !== prev && t);
		if (t && t !== s) {
			out.push({ k: key(t), bonus: -20 });
			if (/^(?:how|what|where) /.test(s) && t.indexOf(' ') < 0) {
				var ing = /e$/.test(t) && !/ee$/.test(t) ? t.slice(0, -1) + 'ing' : t + 'ing';
				out.push({ k: key(ing), bonus: -10 }, { k: key(t + t.slice(-1) + 'ing'), bonus: -15 });
			}
		}
		return out;
	}

	// search-titles.json rows -> what the matcher needs, once
	function prepare(rows) {
		return rows.map(function (r) {
			var names = [{ k: key(r.t.replace(/^[^:]*:/, '')), alias: null }];
			if (r.t.indexOf(':') > 0) names.push({ k: key(r.t), alias: null });
			(r.a || []).forEach(function (a) {
				var name = typeof a === 'string' ? a : a[0];
				names.push({ k: key(name), alias: name, anchor: typeof a === 'string' ? '' : a[1] });
			});
			// pages many others link to first; categories only after the articles
			var weight = Math.min(40, 6 * Math.log2(1 + (r.n || 0)));
			weight += r.k === 'category' ? -260 : r.k === 'project' ? -40 : r.k === 'generated' ? -10 : 0;
			return { row: r, names: names, weight: weight };
		});
	}

	// Best matches for a query: [{row, score, alias, anchor}], best first, one per page
	function match(index, query, limit) {
		var vs = variants(query), out = [];
		if (!vs[0].k.raw) return out;
		index.forEach(function (e) {
			var best = 0, via = null;
			e.names.forEach(function (n) {
				vs.forEach(function (v) {
					var s = score(v.k, n.k);
					// a question's words are whole and spelled out: "how to cook" is not a Cookie
					if (v.bonus && s < 950 && !v.k.stems.every(function (w) { return n.k.stems.indexOf(w) >= 0; })) return;
					if (!s) return;
					s += v.bonus + (n.alias ? -8 : 0);
					if (s > best) { best = s; via = n; }
				});
			});
			if (best >= 330) out.push({ row: e.row, score: best + e.weight, base: best, alias: via.alias, anchor: via.anchor });
		});
		out.sort(function (a, b) { return b.score - a.score || a.row.t.length - b.row.t.length || (a.row.t < b.row.t ? -1 : 1); });
		return out.slice(0, limit || 10);
	}

	// ---- One result list for the box and the page -----------------------------------------------
	// Title matches first (strong ones, at most 6), then Pagefind's full-text results for pages not
	// already listed. The box shows the first 8 rows; the search page shows them all, so its first
	// 8 are the box's. Rows: {url, page, title, image, note (HTML), sections}.
	function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
	function pageUrl(u) { return u.replace(/\.html(?=$|#)/, '').replace(/^\/index(?=$|#)/, '/'); }
	// Title matches worth showing: the strong ones, and a few weak ones when there is little else
	function pick(ms) {
		var strong = ms.filter(function (m) { return m.base >= 560; });
		return (strong.length >= 3 ? strong : ms).slice(0, 6);
	}
	function titleRows(index, query, category) {
		var ms = match(index, query, category ? 1e4 : 10);
		if (category) ms = ms.filter(function (m) { return (m.row.c || []).indexOf(category) >= 0; });
		return pick(ms).map(function (m) {
			return { url: m.row.u + (m.anchor ? '#' + m.anchor : ''), page: m.row.u, title: m.row.t, image: m.row.i || null,
				note: m.alias ? 'redirected from ' + esc(m.alias) : esc(m.row.d || ''), sections: [], exact: m.base >= 950 };
		});
	}
	// Pagefind result data -> rows, after the title rows; a page already listed by title gets its sections
	function merge(rows, datas) {
		var out = rows.map(function (r) { return Object.assign({}, r, { sections: r.sections.slice() }); });
		var byPage = {};
		out.forEach(function (r) { byPage[r.page] = r; });
		datas.forEach(function (d) {
			var u = pageUrl(d.url);
			var sections = (d.sub_results || []).filter(function (x) { return x.anchor; }).slice(0, 3).map(function (x) {
				// Pagefind's section excerpt starts with the heading itself: drop it
				var M = '(?:</?mark>)*', lead = new RegExp('^' + M + x.title.split('').map(function (c) {
					return c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
				}).join(M) + M + '\\.?' + M + '\\s*', 'i');
				return { url: pageUrl(x.url), title: x.title, excerpt: (x.excerpt || '').replace(lead, '') };
			});
			if (byPage[u]) {
				if (!byPage[u].sections.length) byPage[u].sections = sections;
				return;
			}
			byPage[u] = { url: u, page: u, title: (d.meta && d.meta.title) || u, image: (d.meta && d.meta.image) || null,
				note: d.excerpt || '', sections: sections };
			out.push(byPage[u]);
		});
		return out;
	}

	var api = { fold: fold, key: key, stem: stem, distance: distance, score: score, variants: variants, prepare: prepare,
		match: match, pick: pick, titleRows: titleRows, merge: merge, pageUrl: pageUrl };
	if (typeof module !== 'undefined' && module.exports) { module.exports = api; }
	if (typeof document === 'undefined') return;

	// ---- Data ----------------------------------------------------------------------------------
	var form = document.getElementById('searchform');
	var input = document.getElementById('searchInput');
	if (!form || !input) return;
	var page = document.getElementById('mfw-search-page');
	// Pagefind's ranking, tuned on this wiki's pages: title words count double the default, short pages
	// are favoured much less (item pages are short and used to bury the articles), words close to the
	// query in length count more, and a word repeated many times saturates sooner.
	var RANKING = { metaWeights: { title: 10 }, pageLength: 0.2, termSimilarity: 5, termSaturation: 1 };
	var titlesPromise, pagefindPromise;
	function titles() {
		titlesPromise = titlesPromise || fetch(form.dataset.titles).then(function (r) { return r.json(); }).then(prepare)
			.catch(function () { titlesPromise = null; return []; });
		return titlesPromise;
	}
	function pagefind() {
		pagefindPromise = pagefindPromise || import(form.dataset.pagefind).then(function (pf) {
			// the search page shows two lines of excerpt, the box one
			return pf.options({ ranking: RANKING, excerptLength: page ? 30 : 14 }).then(function () { pf.init(); return pf; });
		}).catch(function () { pagefindPromise = null; return null; });
		return pagefindPromise;
	}
	// Pagefind's results for a query, with the data of results [from, to)
	function fullText(query, category) {
		return pagefind().then(function (pf) {
			return pf ? pf.search(query, category ? { filters: { category: [category] } } : {}) : null;
		});
	}
	function load(res, from, to) {
		return res ? Promise.all(res.results.slice(from, to).map(function (r) { return r.data(); })) : Promise.resolve([]);
	}

	// ---- Drawing a row -------------------------------------------------------------------------
	var PLACEHOLDER = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M19 3H1v14h18zM3 14l3.5-4.5 2.5 3 3.5-4.5 4.5 6z"/></svg>';
	function thumb(src) {
		return '<span class="mfw-suggest-thumb' + (/Glyph_/.test(src || '') ? ' mfw-suggest-glyph' : '') + '">' +
			(src ? '<img src="' + esc(src) + '" alt="" loading="lazy" decoding="async">' : PLACEHOLDER) + '</span>';
	}
	function body(r) {
		return thumb(r.image) + '<span class="mfw-suggest-text"><span class="mfw-suggest-title">' + esc(r.title) + '</span>' +
			(r.note ? '<span class="mfw-suggest-desc">' + r.note + '</span>' : '') + '</span>';
	}
	// the search page's and the 404 page's rows: the same row, larger, with the sections that matched
	function result(r) {
		return '<li class="mfw-result"><a class="mfw-result-main" href="' + esc(r.url) + '">' + body(r) + '</a>' +
			(r.sections.length ? '<ul class="mfw-result-sections">' + r.sections.map(function (x) {
				return '<li><a href="' + esc(x.url) + '">' + esc(x.title) + '</a> <span>' + x.excerpt + '</span></li>';
			}).join('') + '</ul>' : '') + '</li>';
	}

	// ---- The header box's suggestions ------------------------------------------------------------
	var MAX = 8;
	var box = document.createElement('div');
	box.id = 'mfw-suggest';
	box.className = 'mfw-suggest';
	box.setAttribute('role', 'listbox');
	box.setAttribute('aria-label', 'Search suggestions');
	box.hidden = true;
	(document.getElementById('simpleSearch') || form).appendChild(box);  // under the box's bevel, edge to edge
	input.setAttribute('role', 'combobox');
	input.setAttribute('aria-autocomplete', 'list');
	input.setAttribute('aria-controls', 'mfw-suggest');
	input.setAttribute('aria-expanded', 'false');
	var seq = 0, current = -1, timer;

	function items() { return box.querySelectorAll('.mfw-suggest-item, .mfw-suggest-footer'); }
	function highlight(i) {
		var all = items();
		if (current >= 0 && all[current]) all[current].classList.remove('mfw-suggest-current'), all[current].setAttribute('aria-selected', 'false');
		var n = all.length + 1;  // the rows, and -1 for back in the input
		current = ((i + 1) % n + n) % n - 1;
		if (current >= 0) {
			all[current].classList.add('mfw-suggest-current');
			all[current].setAttribute('aria-selected', 'true');
			input.setAttribute('aria-activedescendant', all[current].id);
			all[current].scrollIntoView({ block: 'nearest' });
		} else {
			input.removeAttribute('aria-activedescendant');
		}
	}
	function open(on) {
		box.hidden = !on;
		input.setAttribute('aria-expanded', on ? 'true' : 'false');
		document.body.classList.toggle('mfw-suggest-open', on);
		if (!on) { current = -1; input.removeAttribute('aria-activedescendant'); }
	}
	function render(q, rows, done) {
		var html = rows.slice(0, MAX).map(function (r) {
			return '<a class="mfw-suggest-item" href="' + esc(r.url) + '">' + body(r) + '</a>';
		}).join('');
		if (!rows.length && done) html += '<div class="mfw-suggest-empty">No pages match “' + esc(q) + '”.</div>';
		html += '<a class="mfw-suggest-footer" href="/search/?q=' + encodeURIComponent(q) + '">' +
			'<span class="mfw-suggest-thumb"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M12.2 13.6a7 7 0 1 1 1.4-1.4l5.4 5.4-1.4 1.4zM3 8a5 5 0 1 0 10 0A5 5 0 0 0 3 8"/></svg></span>' +
			'<span class="mfw-suggest-text">Search for pages containing <b>' + esc(q) + '</b></span></a>';
		var keep = current;
		box.innerHTML = html;
		Array.prototype.forEach.call(items(), function (a, i) { a.id = 'mfw-suggest-' + i; a.setAttribute('role', 'option'); a.setAttribute('aria-selected', 'false'); });
		current = -1;
		if (keep >= 0) highlight(Math.min(keep, items().length - 1));
		open(true);
	}
	function update() {
		var q = input.value.trim(), my = ++seq;
		if (!q) { open(false); return; }
		titles().then(function (index) {
			if (my !== seq) return;
			var rows = titleRows(index, q);
			render(q, rows, false);
			clearTimeout(timer);
			timer = setTimeout(function () {
				fullText(q).then(function (res) {
					if (my !== seq) return null;
					return load(res, 0, MAX + rows.length).then(function (ds) {
						if (my === seq) render(q, merge(rows, ds), true);
					});
				});
			}, 120);
		});
	}
	input.addEventListener('input', update);
	input.addEventListener('focus', function () { titles(); pagefind(); if (input.value.trim()) update(); });
	input.addEventListener('keydown', function (e) {
		if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
			if (box.hidden) { update(); return; }
			e.preventDefault();
			highlight(current + (e.key === 'ArrowDown' ? 1 : -1));
		} else if (e.key === 'Escape') {
			if (!box.hidden) { e.preventDefault(); open(false); }
		} else if (e.key === 'Tab') {
			open(false);
		}
	});
	// Enter: the highlighted suggestion; else the page with exactly that name (as MediaWiki's "Go");
	// else the search page
	form.addEventListener('submit', function (e) {
		var all = items(), q = input.value.trim();
		e.preventDefault();
		if (!q) return;
		if (!box.hidden && current >= 0 && all[current]) { location.href = all[current].href; return; }
		titles().then(function (index) {
			var top = titleRows(index, q)[0];
			location.href = top && top.exact ? top.url : '/search/?q=' + encodeURIComponent(q);
		});
	});
	box.addEventListener('mousedown', function (e) { e.preventDefault(); });  // keep focus in the input
	box.addEventListener('mousemove', function (e) {
		var a = e.target.closest('.mfw-suggest-item, .mfw-suggest-footer');
		if (a) highlight(Array.prototype.indexOf.call(items(), a));
	});
	input.addEventListener('blur', function () { setTimeout(function () { if (document.activeElement !== input) open(false); }, 150); });
	// "/" focuses the search box (the search page's own box there)
	document.addEventListener('keydown', function (e) {
		if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return;
		var t = e.target;
		if (t.isContentEditable || /^(?:INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
		e.preventDefault();
		(document.getElementById('mfw-search-q') || input).focus();
	});

	// ---- The search page: the same list, all of it, with a category filter -----------------------
	if (page) {
		var pq = document.getElementById('mfw-search-q'), pcat = document.getElementById('mfw-search-category');
		var list = document.getElementById('mfw-search-results'), summary = document.getElementById('mfw-search-summary');
		var more = document.getElementById('mfw-search-more');
		var PAGE = 20, pseq = 0, state = null, ptimer;
		var params = new URLSearchParams(location.search);
		pq.value = params.get('q') || '';
		pagefind().then(function (pf) {
			return pf && pf.filters().then(function (fs) {
				Object.keys(fs.category || {}).sort().forEach(function (c) { pcat.add(new Option(c, c)); });
				pcat.value = params.get('category') || '';
			});
		});
		var draw = function () {
			var s = state, rows = merge(s.rows, s.datas);
			list.innerHTML = rows.map(result).join('');
			var total = s.res ? s.res.results.length : 0, extra = rows.length - s.datas.length;  // title-only rows
			summary.textContent = !rows.length ? (s.res ? 'No pages match “' + s.q + '”' + (s.cat ? ' in ' + s.cat : '') + '.' : '')
				: s.res ? (s.loaded < total ? 'About ' : '') + (total + Math.max(0, extra)) + ' result' + (total + extra === 1 ? '' : 's') +
				' for “' + s.q + '”' + (s.cat ? ' in ' + s.cat : '') : '';
			more.hidden = !s.res || s.loaded >= total;
		};
		var run = function () {
			var q = pq.value.trim(), cat = pcat.value, my = ++pseq;
			var url = new URLSearchParams();
			if (q) url.set('q', q);
			if (q && cat) url.set('category', cat);
			history.replaceState(null, '', location.pathname + (url.toString() ? '?' + url : ''));
			document.title = (q ? '“' + q + '” – ' : '') + 'Search – Matcha Flavoured Wiki';
			if (!q) { list.innerHTML = ''; summary.textContent = ''; more.hidden = true; return; }
			titles().then(function (index) {
				if (my !== pseq) return null;
				state = { q: q, cat: cat, rows: titleRows(index, q, cat), datas: [], res: null, loaded: 0 };
				draw();
				return fullText(q, cat).then(function (res) {
					if (my !== pseq) return null;
					return load(res, 0, PAGE).then(function (ds) {
						if (my !== pseq) return;
						state.res = res; state.datas = ds; state.loaded = Math.min(PAGE, res ? res.results.length : 0);
						draw();
					});
				});
			});
		};
		pq.addEventListener('input', function () { clearTimeout(ptimer); ptimer = setTimeout(run, 150); });
		pcat.addEventListener('change', run);
		document.getElementById('mfw-search-form').addEventListener('submit', function (e) { e.preventDefault(); run(); });
		more.addEventListener('click', function () {
			var s = state, my = pseq;
			load(s.res, s.loaded, s.loaded + PAGE).then(function (ds) {
				if (my !== pseq) return;
				s.datas = s.datas.concat(ds); s.loaded = Math.min(s.loaded + PAGE, s.res.results.length);
				draw();
			});
		});
		if (pq.value.trim()) run();
	}

	// ---- The 404 page: the pages closest to the address ------------------------------------------
	var missing = document.getElementById('mfw-notfound-matches');
	var path = location.pathname.match(/^\/w\/(.+)$/);
	if (missing && path) {
		var wanted = decodeURIComponent(path[1]).replace(/_/g, ' ');
		titles().then(function (index) {
			var rows = titleRows(index, wanted).slice(0, 5);
			if (rows.length) missing.innerHTML = '<p>Pages with a similar name:</p><ul class="mfw-results">' + rows.map(result).join('') + '</ul>';
		});
	}
})();
