// Access key labels for the static site (tools/export_static.py appends this to _static/site.js).
//
// MediaWiki gives its links access keys (Main page [z], Random page [x], What links here [j],
// Printable version [p], search [f]) and its jquery.accessKeyLabel rewrites the "[x]" at the end of
// each tooltip into the keys this browser needs ("[alt-shift-x]", "[ctrl-option-x]" on a Mac). The
// export drops MediaWiki's scripts, so this does that rewrite. The live wiki runs MediaWiki's own.
(function () {
	'use strict';
	// What MediaWiki shows for today's browsers: Control and Option on Apple systems, Alt and Shift
	// elsewhere (Chrome, Edge and Firefox all take Alt+Shift; plain Alt clashes with their menus).
	function modifiers(nav) {
		var platform = (nav.userAgentData && nav.userAgentData.platform) || nav.platform || '';
		return /mac|iphone|ipad|ipod/i.test(platform) || /Macintosh|Mac OS X/.test(nav.userAgent || '') ? 'ctrl-option-' : 'alt-shift-';
	}
	// "Load a random page [x]" -> "Load a random page [alt-shift-x]"; a title that doesn't end in the
	// element's own key in brackets is left as it is
	function label(title, key, prefix) {
		if (!title || !key) return title;
		var end = '[' + key + ']';
		return title.slice(-end.length) === end ? title.slice(0, -end.length) + '[' + prefix + key + ']' : title;
	}
	var api = { modifiers: modifiers, label: label };
	if (typeof module !== 'undefined' && module.exports) { module.exports = api; }
	if (typeof document === 'undefined') return;

	var prefix = modifiers(navigator);
	document.querySelectorAll('[accesskey][title]').forEach(function (el) {
		el.title = label(el.title, el.getAttribute('accesskey'), prefix);
	});
})();
