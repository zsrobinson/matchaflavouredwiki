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
	// Phones, up to the 720px of MediaWiki:Vector.css's mobile layout, as on minecraft.wiki's mobile
	// site: a header with menu and search buttons, the sidebar as a menu drawer, collapsible sections.
	// The header and drawer entry are always built (CSS hides them on wider screens).
	var PHONE = '(max-width: 720px)';
	function icon( d ) {
		return '<svg width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="' + d + '"/></svg>';
	}
	function initMobileHeader() {
		var b = document.body, panel = document.getElementById( 'mw-panel' );
		if ( !panel ) {
			return;
		}
		var header = document.createElement( 'div' );
		header.id = 'mfw-mobile-header';
		header.className = 'noprint';
		header.innerHTML =
			'<button type="button" id="mfw-menu-button" aria-label="Main menu" aria-expanded="false">' + icon( 'M1 3v2h18V3zm0 8h18V9H1zm0 6h18v-2H1z' ) + '</button>' +
			'<a href="/">Matcha Flavoured Wiki</a>' +
			'<button type="button" id="mfw-search-button" aria-label="Search">' + icon( 'M12.2 13.6a7 7 0 1 1 1.4-1.4l5.4 5.4-1.4 1.4zM3 8a5 5 0 1 0 10 0A5 5 0 0 0 3 8' ) + '</button>' +
			'<button type="button" id="mfw-search-close" aria-label="Close search">' + icon( 'm5.83 9 5.58-5.58L10 2l-8 8 8 8 1.41-1.41L5.83 11H18V9z' ) + '</button>';
		b.insertBefore( header, b.firstChild );
		// the drawer's first entry toggles dark mode, as in minecraft.wiki's mobile menu
		var dark = document.createElement( 'a' );
		dark.id = 'mfw-drawer-dark';
		dark.href = '#';
		dark.setAttribute( 'role', 'button' );
		dark.innerHTML = icon( 'M8.4 1.2a8.3 8.3 0 1 0 10.4 10.4A7 7 0 0 1 8.4 1.2' ) + 'Toggle dark mode';
		dark.addEventListener( 'click', toggleTheme );
		panel.insertBefore( dark, panel.firstChild );

		var menuButton = document.getElementById( 'mfw-menu-button' );
		function setMenu( open ) {
			b.classList.toggle( 'mfw-menu-open', open );
			menuButton.setAttribute( 'aria-expanded', String( open ) );
		}
		function setSearch( open ) {
			b.classList.toggle( 'mfw-search-open', open );
			var input = open && document.querySelector( '#p-search input:not([type="hidden"])' );
			if ( input ) {
				input.focus();
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
	}

	// Collapsible sections, as MobileFrontend does on minecraft.wiki: each level-2 heading toggles
	// the content up to the next one. The lead (with the infobox) stays open, and the main page and
	// pages without level-2 headings are left alone. Collapsed content is hidden="until-found", so
	// find-in-page opens it; a #fragment (a footnote or a link from another page) opens its section.
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
			section.id = 'mfw-section-' + i;
			while ( h.nextSibling && !( h.nextSibling.classList && h.nextSibling.classList.contains( 'mw-heading2' ) ) ) {
				section.appendChild( h.nextSibling );
			}
			h.parentNode.insertBefore( section, h.nextSibling );
			h.classList.add( 'mfw-section-heading' );
			h.setAttribute( 'role', 'button' );
			h.setAttribute( 'tabindex', '0' );
			h.setAttribute( 'aria-controls', section.id );
			setOpen( h, false );
			section.addEventListener( 'beforematch', function () {
				setOpen( h, true );
			} );
		} );
		function toggle( e ) {
			var h = e.target.closest( '.mfw-section-heading' );
			if ( h && ( e.type === 'click' ? !e.target.closest( 'a[href]' ) : e.key === 'Enter' || e.key === ' ' ) ) {
				e.preventDefault();
				setOpen( h, !h.classList.contains( 'mfw-open' ) );
			}
		}
		content.addEventListener( 'click', toggle );
		content.addEventListener( 'keydown', toggle );
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
		reveal();
		window.addEventListener( 'hashchange', reveal );
		// widened past phone width: show everything
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
