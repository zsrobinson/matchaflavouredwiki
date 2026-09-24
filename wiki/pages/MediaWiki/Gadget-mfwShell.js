// Shell behaviour shared by the live wiki (as a gadget) and the static export (copied into
// /_static/site.js by tools/export_static.py): dark-mode toggle and collapsible sidebar sections,
// and on phones the mobile header, menu drawer and collapsible sections (MediaWiki:Vector.css).
// The theme class itself is applied before first paint by the inline head script
// (site/theme-boot.js), so this only wires up the toggle.
( function () {
	'use strict';
	var KEY = 'mfw-theme';
	function getTheme() {
		try {
			return localStorage.getItem( KEY ) ||
				( window.matchMedia && matchMedia( '(prefers-color-scheme: dark)' ).matches ? 'dark' : 'light' );
		} catch ( e ) {
			return 'light';
		}
	}
	function applyTheme( t ) {
		var b = document.body;
		b.classList.remove( 'wgl-theme-light', 'wgl-theme-dark', 'wgl-lightmode', 'wgl-darkmode' );
		b.classList.add( 'wgl-theme-' + t, 'wgl-' + t + 'mode' );
		document.documentElement.style.colorScheme = t;
	}
	function toggleTheme( e ) {
		e.preventDefault();
		var t = getTheme() === 'light' ? 'dark' : 'light';
		try { localStorage.setItem( KEY, t ); } catch ( err ) {}
		applyTheme( t );
	}
	// Phones: up to the 720px of MediaWiki:Vector.css's mobile layout
	var PHONE = '(max-width: 720px)';
	function isPhone() {
		return !!window.matchMedia && matchMedia( PHONE ).matches;
	}
	function onPhoneChange( fn ) {
		if ( window.matchMedia ) {
			var mq = matchMedia( PHONE );
			// Safari before 14 only has addListener
			return mq.addEventListener ? mq.addEventListener( 'change', fn ) : mq.addListener( fn );
		}
	}
	function attrs( el, map ) {
		for ( var k in map ) {
			if ( map[ k ] === null ) {
				el.removeAttribute( k );
			} else {
				el.setAttribute( k, map[ k ] );
			}
		}
	}

	// Reader toggles beside dark mode, remembered per browser and applied before first paint by
	// site/theme-boot.js (classes on <html>):
	// * width: minecraft.wiki's fixed-width toggle (its fixedWidthToggle gadget): full width by
	//   default, limited to 1200px on screens wider than that (MediaWiki:Vector.css).
	// * spoilers: off by default; on, html.mfw-hide-spoilers hides what {{Spoiler}} covers (marked by
	//   site/Spoilers.php) and hidden-advancement rows (.mfw-spoiler) until they are clicked
	//   (MediaWiki:Common.css).
	var PREFS = {
		width: { key: 'mfw-width', on: 'fixed', cls: 'mfw-fixed-width' },
		spoilers: { key: 'mfw-spoilers', on: 'hide', cls: 'mfw-hide-spoilers' }
	};
	var root = document.documentElement;
	function prefOn( name ) {
		return root.classList.contains( PREFS[ name ].cls );
	}
	var prefListeners = [];
	function setPref( name, on ) {
		var p = PREFS[ name ];
		root.classList.toggle( p.cls, on );
		try {
			if ( on ) {
				localStorage.setItem( p.key, p.on );
			} else {
				localStorage.removeItem( p.key );
			}
		} catch ( e ) {}
		prefListeners.forEach( function ( fn ) {
			fn();
		} );
	}
	function onPrefChange( fn ) {
		prefListeners.push( fn );
		fn();
	}
	function spoilerTitle() {
		return prefOn( 'spoilers' ) ? 'Show spoilers' : 'Hide spoilers';
	}
	// the personal-bar buttons, styled like #pt-dm-toggle (MediaWiki:Vector.css)
	function addPrefToggle( personal, before, id, name, title ) {
		var li = document.createElement( 'li' );
		li.id = id;
		li.className = 'mw-list-item mfw-pref-toggle';
		var a = document.createElement( 'a' );
		a.href = '#';
		a.setAttribute( 'role', 'button' );
		a.addEventListener( 'click', function ( e ) {
			e.preventDefault();
			setPref( name, !prefOn( name ) );
		} );
		li.appendChild( a );
		personal.insertBefore( li, before );
		onPrefChange( function () {
			var t = title();
			a.title = t;
			a.setAttribute( 'aria-label', t );
			a.setAttribute( 'aria-pressed', String( prefOn( name ) ) );
		} );
		return li;
	}
	// A hidden spoiler is shown by clicking it (or Enter/Space on the box); a #fragment inside one
	// shows it too. Showing lasts until the page is left.
	function initSpoilers() {
		function hiddenAt( el ) {
			if ( !prefOn( 'spoilers' ) || !el || !el.closest ) {
				return null;
			}
			return el.closest( '[data-mfw-spoiler]:not(.mfw-spoiler-shown), .mfw-spoiler:not(.mfw-spoiler-shown)' );
		}
		function show( el ) {
			var n = el.getAttribute( 'data-mfw-spoiler' );
			var els = n ? document.querySelectorAll( '[data-mfw-spoiler="' + n + '"]' ) : [ el ];
			Array.prototype.forEach.call( els, function ( x ) {
				x.classList.add( 'mfw-spoiler-shown' );
				if ( x.matches( 'table.messagebox' ) ) {
					attrs( x, { role: null, tabindex: null, title: null } );
				}
			} );
		}
		var boxes = document.querySelectorAll( 'table.messagebox.spoiler[data-mfw-spoiler]' );
		onPrefChange( function () {
			var on = prefOn( 'spoilers' );
			Array.prototype.forEach.call( boxes, function ( box ) {
				var hidden = on && !box.classList.contains( 'mfw-spoiler-shown' );
				attrs( box, hidden ? { role: 'button', tabindex: '0', title: 'Show spoiler' } : { role: null, tabindex: null, title: null } );
			} );
			document.querySelectorAll( '.mfw-spoiler' ).forEach( function ( el ) {
				attrs( el, { title: on && !el.classList.contains( 'mfw-spoiler-shown' ) ? 'Show spoiler' : null } );
			} );
		} );
		document.addEventListener( 'click', function ( e ) {
			var el = hiddenAt( e.target );
			if ( el ) {
				e.preventDefault();
				e.stopPropagation();
				show( el );
			}
		}, true );
		document.addEventListener( 'keydown', function ( e ) {
			var el = ( e.key === 'Enter' || e.key === ' ' ) && hiddenAt( e.target );
			if ( el && el === e.target ) {
				e.preventDefault();
				show( el );
			}
		} );
		function reveal() {
			var el = null;
			try {
				el = document.getElementById( decodeURIComponent( location.hash.slice( 1 ) ) );
			} catch ( e ) {}
			var hidden = hiddenAt( el );
			if ( hidden ) {
				show( hidden );
				el.scrollIntoView();
			}
		}
		reveal();
		window.addEventListener( 'hashchange', reveal );
	}
	function init() {
		applyTheme( getTheme() );

		// Dark mode toggle in the personal bar (#pt-dm-toggle is styled by minecraft.wiki's CSS).
		var personal = document.querySelector( '#p-personal ul' );
		if ( personal && !document.getElementById( 'pt-dm-toggle' ) ) {
			var li = document.createElement( 'li' );
			li.id = 'pt-dm-toggle';
			li.className = 'mw-list-item';
			var a = document.createElement( 'a' );
			a.href = '#';
			a.title = 'Toggle dark mode';
			a.setAttribute( 'aria-label', 'Toggle dark mode' );
			a.addEventListener( 'click', toggleTheme );
			li.appendChild( a );
			personal.insertBefore( li, personal.firstChild );
			// width then dark mode, as on minecraft.wiki, with the spoiler toggle first
			var fw = addPrefToggle( personal, li, 'pt-fw-toggle', 'width', function () {
				return 'Toggle fixed width';
			} );
			addPrefToggle( personal, fw, 'pt-sp-toggle', 'spoilers', spoilerTitle );
			var portlet = personal.closest( '.mw-portlet' );
			if ( portlet ) {
				portlet.classList.remove( 'emptyPortlet' );
			}
		}

		// Collapsible sidebar sections, remembered per section. On phones the sidebar is the menu
		// drawer, a plain list: its headings are just labels there.
		var state = {};
		try { state = JSON.parse( localStorage.getItem( 'mfw-sidebar' ) || '{}' ); } catch ( e ) {}
		var sideHeadings = [];
		document.querySelectorAll( '#mw-panel nav.vector-menu-portal' ).forEach( function ( nav ) {
			var h = nav.querySelector( '.vector-menu-heading' );
			if ( !h || nav.id === 'p-navigation' ) {
				return;
			}
			if ( state[ nav.id ] ) {
				nav.classList.add( 'collapsed' );
			}
			sideHeadings.push( h );
			function toggle() {
				if ( isPhone() ) {
					return;
				}
				var c = nav.classList.toggle( 'collapsed' );
				h.setAttribute( 'aria-expanded', String( !c ) );
				state[ nav.id ] = c;
				try { localStorage.setItem( 'mfw-sidebar', JSON.stringify( state ) ); } catch ( e ) {}
			}
			h.addEventListener( 'click', toggle );
			h.addEventListener( 'keydown', function ( e ) {
				if ( e.key === 'Enter' || e.key === ' ' ) {
					e.preventDefault();
					toggle();
				}
			} );
		} );
		function sidebarRoles() {
			var phone = isPhone();
			sideHeadings.forEach( function ( h ) {
				attrs( h, phone ? { role: null, tabindex: null, 'aria-expanded': null } : {
					role: 'button', tabindex: '0', 'aria-expanded': String( !h.parentNode.classList.contains( 'collapsed' ) )
				} );
			} );
		}
		sidebarRoles();
		onPhoneChange( sidebarRoles );
		initSpoilers();
	}
	// Phones, as on minecraft.wiki's mobile site: a header with menu and search buttons, the sidebar
	// as a menu drawer, and collapsible sections. The header and drawer are always built (CSS shows
	// them only on phones, and only once html.mfw-js says this script runs).
	function icon( d, evenodd ) {
		return '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor"' +
			( evenodd ? ' fill-rule="evenodd"' : '' ) + ' d="' + d + '"/></svg>';
	}
	// OOUI's eye icons, as the personal bar's (MediaWiki:Vector.css)
	var EYE = 'M10 14.5a4.5 4.5 0 1 1 4.5-4.5 4.5 4.5 0 0 1-4.5 4.5M10 3C3 3 0 10 0 10s3 7 10 7 10-7 10-7-3-7-10-7m0 4.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5';
	var EYE_CLOSED = 'M12.49 9.94A2.5 2.5 0 0 0 10 7.5zM8.2 5.9a4.4 4.4 0 0 1 1.8-.4 4.5 4.5 0 0 1 4.5 4.5 4.3 4.3 0 0 1-.29 1.55L17 14.14A14 14 0 0 0 20 10s-3-7-10-7a9.6 9.6 0 0 0-4 .85zM2 2 1 3l2.55 2.4A13.9 13.9 0 0 0 0 10s3 7 10 7a9.7 9.7 0 0 0 4.64-1.16L18 19l1-1zm8 12.5A4.5 4.5 0 0 1 5.5 10a4.45 4.45 0 0 1 .6-2.2l1.53 1.44a2.5 2.5 0 0 0-.13.76 2.49 2.49 0 0 0 3.41 2.32l1.54 1.45a4.47 4.47 0 0 1-2.45.73';
	function initMobileHeader() {
		var b = document.body, panel = document.getElementById( 'mw-panel' );
		if ( !panel ) {
			return;
		}
		document.documentElement.classList.add( 'mfw-js' );
		var header = document.createElement( 'div' );
		header.id = 'mfw-mobile-header';
		header.className = 'noprint';
		header.innerHTML =
			'<button type="button" id="mfw-menu-button" aria-label="Main menu" aria-controls="mw-panel" aria-expanded="false">' + icon( 'M1 3v2h18V3zm0 8h18V9H1zm0 6h18v-2H1z' ) + '</button>' +
			'<a href="/">Matcha Flavoured Wiki</a>' +
			'<button type="button" id="mfw-search-button" aria-label="Search">' + icon( 'M12.2 13.6a7 7 0 1 1 1.4-1.4l5.4 5.4-1.4 1.4zM3 8a5 5 0 1 0 10 0A5 5 0 0 0 3 8' ) + '</button>' +
			'<button type="button" id="mfw-search-close" aria-label="Close search">' + icon( 'm5.83 9 5.58-5.58L10 2l-8 8 8 8 1.41-1.41L5.83 11H18V9z' ) + '</button>';
		b.insertBefore( header, b.firstChild );
		// the drawer's first entry toggles dark mode, as in minecraft.wiki's mobile menu
		var dark = document.createElement( 'button' );
		dark.type = 'button';
		dark.id = 'mfw-drawer-dark';
		dark.innerHTML = icon( 'M8.4 1.2a8.3 8.3 0 1 0 10.4 10.4A7 7 0 0 1 8.4 1.2' ) + 'Toggle dark mode';
		dark.addEventListener( 'click', toggleTheme );
		panel.insertBefore( dark, panel.firstChild );
		// then the spoiler toggle (no width toggle: phones have no room to spare, as on minecraft.wiki)
		var spoilers = document.createElement( 'button' );
		spoilers.type = 'button';
		spoilers.id = 'mfw-drawer-spoilers';
		spoilers.addEventListener( 'click', function () {
			setPref( 'spoilers', !prefOn( 'spoilers' ) );
		} );
		panel.insertBefore( spoilers, dark.nextSibling );
		onPrefChange( function () {
			var on = prefOn( 'spoilers' );
			spoilers.setAttribute( 'aria-pressed', String( on ) );
			spoilers.innerHTML = icon( on ? EYE : EYE_CLOSED, on ) + spoilerTitle();
		} );
		// the Talk tab becomes a button after the article, as on the mobile site
		var talk = document.querySelector( '#ca-mfw-talk a' ), content = document.getElementById( 'content' );
		if ( talk && content ) {
			var button = document.createElement( 'a' );
			button.id = 'mfw-talk-button';
			button.className = 'noprint';
			button.href = talk.href;
			button.innerHTML = icon( 'M0 8v8a2 2 0 0 0 2 2h1v3l3-3h8a2 2 0 0 0 2-2v-2H4V8zm18-7H6a2 2 0 0 0-2 2v8h14l2 2V3a2 2 0 0 0-2-2' ) + 'Talk';
			content.appendChild( button );
		}

		var menuButton = document.getElementById( 'mfw-menu-button' );
		var searchButton = document.getElementById( 'mfw-search-button' );
		// while the drawer is open, the rest of the page is inert (focus stays in the drawer)
		var rest = [ header, document.getElementById( 'mw-head' ), document.getElementById( 'content' ), document.getElementById( 'footer' ) ];
		function setMenu( open, quiet ) {
			if ( open === b.classList.contains( 'mfw-menu-open' ) ) {
				return;
			}
			b.classList.toggle( 'mfw-menu-open', open );
			menuButton.setAttribute( 'aria-expanded', String( open ) );
			rest.forEach( function ( el ) {
				if ( el ) {
					el.inert = open;
				}
			} );
			var target = open ? panel.querySelector( 'li a[href]' ) : menuButton;
			if ( target && !quiet ) {
				target.focus();
			}
		}
		function setSearch( open, quiet ) {
			if ( open === b.classList.contains( 'mfw-search-open' ) ) {
				return;
			}
			b.classList.toggle( 'mfw-search-open', open );
			var target = open ? document.querySelector( '#p-search input:not([type="hidden"])' ) : searchButton;
			if ( target && !quiet ) {
				target.focus();
			}
		}
		// one listener: the header buttons, and a tap beside the open drawer closes it
		document.addEventListener( 'click', function ( e ) {
			var t = e.target;
			if ( t.closest( '#mfw-menu-button' ) ) {
				setMenu( !b.classList.contains( 'mfw-menu-open' ) );
			} else if ( b.classList.contains( 'mfw-menu-open' ) && !panel.contains( t ) ) {
				setMenu( false );
			} else if ( t.closest( '#mfw-search-button, #mfw-search-close' ) ) {
				setSearch( t.closest( '#mfw-search-button' ) !== null );
			}
		} );
		document.addEventListener( 'keydown', function ( e ) {
			if ( e.key === 'Escape' ) {
				setMenu( false );
				setSearch( false );
			}
		} );
		function closeAll() {
			setMenu( false, true );
			setSearch( false, true );
		}
		// a page restored from the back/forward cache, or a window widened past phone width
		window.addEventListener( 'pageshow', closeAll );
		onPhoneChange( closeAll );
	}

	// Collapsible sections, as MobileFrontend does on minecraft.wiki: a button in each level-2
	// heading (the disclosure pattern) toggles the content up to the next one. The lead (with the
	// infobox) stays open, and the main page and pages without level-2 headings are left alone.
	// Collapsed content is hidden="until-found", so find-in-page opens it; a #fragment (a footnote
	// or a link from another page) opens its section. Wider than a phone, everything is open and
	// the headings are plain headings again.
	function initSections() {
		var content = document.querySelector( '#mw-content-text > .mw-parser-output' );
		if ( !content || document.body.classList.contains( 'page-Matcha_Flavoured_Wiki' ) ) {
			return;
		}
		var headings = Array.prototype.filter.call( content.children, function ( el ) {
			return el.classList.contains( 'mw-heading2' );
		} );
		function setOpen( h, open ) {
			var button = h.querySelector( '.mfw-section-toggle' );
			h.classList.toggle( 'mfw-open', open );
			if ( button ) {
				button.setAttribute( 'aria-expanded', String( open ) );
			}
			attrs( h.nextElementSibling, { hidden: open ? null : 'until-found' } );
		}
		function setButtons( phone ) {
			headings.forEach( function ( h ) {
				var h2 = h.querySelector( 'h2' ), button = h2 && h2.querySelector( '.mfw-section-toggle' );
				if ( phone && h2 && !button ) {
					button = document.createElement( 'button' );
					attrs( button, { type: 'button', 'class': 'mfw-section-toggle', 'aria-controls': h.nextElementSibling.id } );
					while ( h2.firstChild ) {
						button.appendChild( h2.firstChild );
					}
					h2.appendChild( button );
					setOpen( h, h.classList.contains( 'mfw-open' ) );
				} else if ( !phone && button ) {
					while ( button.firstChild ) {
						h2.insertBefore( button.firstChild, button );
					}
					h2.removeChild( button );
					setOpen( h, true );
				}
			} );
		}
		headings.forEach( function ( h, i ) {
			var section = document.createElement( 'div' );
			section.className = 'mfw-section';
			section.id = 'mfw-section-' + i;
			while ( h.nextSibling && !( h.nextSibling.classList && h.nextSibling.classList.contains( 'mw-heading2' ) ) ) {
				section.appendChild( h.nextSibling );
			}
			h.parentNode.insertBefore( section, h.nextSibling );
			h.classList.add( 'mfw-section-heading' );
			section.addEventListener( 'beforematch', function () {
				setOpen( h, true );
			} );
		} );
		setButtons( true );
		function reveal() {
			var el = null;
			try {
				el = document.getElementById( decodeURIComponent( location.hash.slice( 1 ) ) );
			} catch ( e ) {}
			var h = el && ( el.closest( '.mfw-section-heading' ) || ( el.closest( '.mfw-section' ) || {} ).previousElementSibling );
			if ( h && !h.classList.contains( 'mfw-open' ) ) {
				setOpen( h, true );
				el.scrollIntoView();
			}
		}
		// the whole heading toggles its section (its button also takes Enter and Space); a same-page
		// link opens the section it points into, even when the #fragment is already in the address
		document.addEventListener( 'click', function ( e ) {
			var h = e.target.closest( '.mfw-section-heading' );
			if ( h && isPhone() && !e.target.closest( 'a[href]' ) ) {
				setOpen( h, !h.classList.contains( 'mfw-open' ) );
			} else if ( e.target.closest( 'a[href^="#"]' ) ) {
				setTimeout( reveal );
			}
		} );
		reveal();
		window.addEventListener( 'hashchange', reveal );
		onPhoneChange( function () {
			setButtons( isPhone() );
		} );
		// printing shows every section
		window.addEventListener( 'beforeprint', function () {
			headings.forEach( function ( h ) {
				setOpen( h, true );
			} );
		} );
	}

	function initMobile() {
		if ( document.getElementById( 'mfw-mobile-header' ) ) {
			return;  // already ran
		}
		initMobileHeader();
		if ( isPhone() ) {
			initSections();
		}
	}

	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', init );
		document.addEventListener( 'DOMContentLoaded', initMobile );
	} else {
		init();
		initMobile();
	}
}() );
