// Shell behaviour shared by the live wiki (as a gadget) and the static export (copied into
// /_static/site.js by tools/export_static.py): dark-mode toggle and collapsible sidebar sections,
// and on phones the minecraft.wiki-style mobile header, menu drawer and collapsible sections
// (laid out by the phone-width section of MediaWiki:Vector.css; nothing here shows on desktop).
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
			var portlet = personal.closest( '.mw-portlet' );
			if ( portlet ) {
				portlet.classList.remove( 'emptyPortlet' );
			}
		}

		// Collapsible sidebar sections, remembered per section.
		var state = {};
		try { state = JSON.parse( localStorage.getItem( 'mfw-sidebar' ) || '{}' ); } catch ( e ) {}
		document.querySelectorAll( '#mw-panel nav.vector-menu-portal' ).forEach( function ( nav ) {
			var h = nav.querySelector( '.vector-menu-heading' );
			if ( !h || nav.id === 'p-navigation' ) {
				return;
			}
			if ( state[ nav.id ] ) {
				nav.classList.add( 'collapsed' );
			}
			h.setAttribute( 'role', 'button' );
			h.setAttribute( 'tabindex', '0' );
			h.setAttribute( 'aria-expanded', String( !nav.classList.contains( 'collapsed' ) ) );
			function toggle() {
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
	}
	// Phones (the same width as MediaWiki:Vector.css's mobile layout)
	var PHONE = '(max-width: 720px)';
	function icon( path ) {
		return '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="' + path + '"/></svg>';
	}
	var ICONS = {
		menu: 'M1 3v2h18V3zm0 8h18V9H1zm0 6h18v-2H1z',
		search: 'M12.2 13.6a7 7 0 1 1 1.4-1.4l5.4 5.4-1.4 1.4zM3 8a5 5 0 1 0 10 0A5 5 0 0 0 3 8',
		back: 'm5.83 9 5.58-5.58L10 2l-8 8 8 8 1.41-1.41L5.83 11H18V9z'
	};

	// Mobile header, as on minecraft.wiki's mobile site: menu button, logo and wiki name, search.
	// The menu opens the sidebar (#mw-panel) as a drawer; search shows the header search box.
	function initMobileHeader() {
		if ( document.getElementById( 'mfw-mobile-header' ) ) {
			return;
		}
		var logo = document.querySelector( '#p-logo a' );
		var header = document.createElement( 'div' );
		header.id = 'mfw-mobile-header';
		header.className = 'noprint';
		header.innerHTML =
			'<button type="button" class="mfw-header-button" id="mfw-menu-button" aria-label="Open main menu" aria-expanded="false">' + icon( ICONS.menu ) + '</button>' +
			'<a class="mfw-branding" href="' + ( logo ? logo.getAttribute( 'href' ) : '/' ) + '"><span class="mfw-branding-logo"></span>Matcha Flavoured Wiki</a>' +
			'<button type="button" class="mfw-header-button" id="mfw-search-button" aria-label="Search">' + icon( ICONS.search ) + '</button>' +
			'<button type="button" class="mfw-header-button" id="mfw-search-close" aria-label="Close search">' + icon( ICONS.back ) + '</button>';
		// the drawer's first entry toggles dark mode, as minecraft.wiki's mobile menu does
		var panel = document.getElementById( 'mw-panel' );
		if ( panel ) {
			var tools = document.createElement( 'div' );
			tools.id = 'mfw-drawer-tools';
			tools.innerHTML = '<ul><li><a href="#" role="button">Toggle dark mode</a></li></ul>';
			tools.querySelector( 'a' ).addEventListener( 'click', toggleTheme );
			panel.insertBefore( tools, panel.firstChild );
		}
		var mask = document.createElement( 'div' );
		mask.id = 'mfw-menu-mask';
		document.body.insertBefore( mask, document.body.firstChild );
		document.body.insertBefore( header, document.body.firstChild );

		var b = document.body, menuButton = document.getElementById( 'mfw-menu-button' );
		function setMenu( open ) {
			b.classList.toggle( 'mfw-menu-open', open );
			menuButton.setAttribute( 'aria-expanded', String( open ) );
		}
		function setSearch( open ) {
			b.classList.toggle( 'mfw-search-open', open );
			if ( open ) {
				var input = document.querySelector( '#p-search input[type="search"], #p-search input:not([type="hidden"])' );
				if ( input ) {
					input.focus();
				}
			}
		}
		menuButton.addEventListener( 'click', function () {
			setMenu( !b.classList.contains( 'mfw-menu-open' ) );
		} );
		mask.addEventListener( 'click', function () {
			setMenu( false );
		} );
		document.getElementById( 'mfw-search-button' ).addEventListener( 'click', function () {
			setSearch( true );
		} );
		document.getElementById( 'mfw-search-close' ).addEventListener( 'click', function () {
			setSearch( false );
		} );
		document.addEventListener( 'keydown', function ( e ) {
			if ( e.key === 'Escape' ) {
				setMenu( false );
				setSearch( false );
			}
		} );
	}

	// Collapsible sections on phones, as MobileFrontend does on minecraft.wiki: each level-2
	// heading toggles the content up to the next one. A #fragment (a contents or reference link)
	// opens the section it points into, and find-in-page opens collapsed sections too.
	function initSections() {
		var content = document.querySelector( '#mw-content-text > .mw-parser-output' );
		if ( !content || document.body.classList.contains( 'page-Matcha_Flavoured_Wiki' ) ) {
			return;
		}
		var headings = Array.prototype.filter.call( content.children, function ( el ) {
			return el.classList.contains( 'mw-heading2' );
		} );
		function setOpen( h, open ) {
			h.classList.toggle( 'mfw-open', open );
			h.setAttribute( 'aria-expanded', String( open ) );
			if ( open ) {
				h.nextElementSibling.removeAttribute( 'hidden' );
			} else {
				h.nextElementSibling.setAttribute( 'hidden', 'until-found' );
			}
		}
		headings.forEach( function ( h, i ) {
			var section = document.createElement( 'div' );
			section.className = 'mfw-section';
			section.id = 'mfw-section-' + ( i + 1 );
			while ( h.nextSibling && !( h.nextSibling.classList && h.nextSibling.classList.contains( 'mw-heading2' ) ) ) {
				section.appendChild( h.nextSibling );
			}
			h.parentNode.insertBefore( section, h.nextSibling );
			h.classList.add( 'mfw-section-heading' );
			h.setAttribute( 'role', 'button' );
			h.setAttribute( 'tabindex', '0' );
			h.setAttribute( 'aria-controls', section.id );
			setOpen( h, false );
			h.addEventListener( 'click', function ( e ) {
				if ( !e.target.closest( 'a[href]' ) ) {
					setOpen( h, !h.classList.contains( 'mfw-open' ) );
				}
			} );
			h.addEventListener( 'keydown', function ( e ) {
				if ( e.key === 'Enter' || e.key === ' ' ) {
					e.preventDefault();
					setOpen( h, !h.classList.contains( 'mfw-open' ) );
				}
			} );
			section.addEventListener( 'beforematch', function () {
				setOpen( h, true );
			} );
		} );
		function reveal() {
			var id;
			try {
				id = decodeURIComponent( location.hash.slice( 1 ) );
			} catch ( e ) {
				return;
			}
			var el = id && document.getElementById( id );
			if ( !el ) {
				return;
			}
			var h = el.closest( '.mfw-section-heading' );
			var section = h ? h.nextElementSibling : el.closest( '.mfw-section' );
			if ( section && section.hasAttribute( 'hidden' ) ) {
				setOpen( section.previousElementSibling, true );
				el.scrollIntoView();
			}
		}
		reveal();
		window.addEventListener( 'hashchange', reveal );
		// back to a desktop-width window: show everything
		matchMedia( PHONE ).addEventListener( 'change', function ( e ) {
			if ( !e.matches ) {
				headings.forEach( function ( h ) {
					setOpen( h, true );
				} );
			}
		} );
	}

	function initMobile() {
		initMobileHeader();
		if ( window.matchMedia && matchMedia( PHONE ).matches ) {
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
