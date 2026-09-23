// Shell behaviour shared by the live wiki (as a gadget) and the static export (copied into
// /_static/site.js by tools/export_static.py): dark-mode toggle and collapsible sidebar sections
// on desktop (Vector), the dark-mode toggle in the menu drawer on mobile (Minerva).
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
		// Minerva's own night mode follows along, as on minecraft.wiki
		var h = document.documentElement;
		h.classList.remove( 'skin-theme-clientpref-day', 'skin-theme-clientpref-night', 'skin-theme-clientpref-os' );
		h.classList.add( t === 'dark' ? 'skin-theme-clientpref-night' : 'skin-theme-clientpref-day' );
		h.style.colorScheme = t;
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

		// Mobile: "Toggle dark mode" in the menu drawer (minecraft.wiki's darkmode gadget puts it there too).
		var mobileNav = document.querySelector( '#mw-mf-page-left #p-navigation' );
		if ( mobileNav && !document.getElementById( 'pt-dm-toggle' ) ) {
			var item = document.createElement( 'li' );
			item.id = 'pt-dm-toggle';
			item.className = 'toggle-list-item mw-list-item';
			item.innerHTML = '<a class="toggle-list-item__anchor" href="#" role="button">' +
				'<span class="minerva-icon minerva-icon-portletlink-pt-dm-toggle"></span>' +
				'<span class="toggle-list-item__label">Toggle dark mode</span></a>';
			item.firstChild.addEventListener( 'click', toggleTheme );
			mobileNav.appendChild( item );
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
