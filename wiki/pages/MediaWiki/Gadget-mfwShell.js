// Shell behaviour shared by the live wiki (as a gadget) and the static export (copied into
// /_static/site.js by tools/export_static.py): dark-mode toggle and collapsible sidebar sections.
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
			a.addEventListener( 'click', function ( e ) {
				e.preventDefault();
				var t = getTheme() === 'light' ? 'dark' : 'light';
				try { localStorage.setItem( KEY, t ); } catch ( err ) {}
				applyTheme( t );
			} );
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
	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', init );
	} else {
		init();
	}
}() );
