// Light/dark toggle, using minecraft.wiki's theme classes (wgl-theme-light / wgl-theme-dark),
// so the vendored minecraft.wiki dark theme (MediaWiki:Gadget-mcw-vector.css) applies.
( function ( $, mw ) {
	var KEY = 'mfw-theme';
	function get() {
		try { return localStorage.getItem( KEY ) || ( window.matchMedia && matchMedia( '(prefers-color-scheme: dark)' ).matches ? 'dark' : 'light' ); } catch ( e ) { return 'light'; }
	}
	function apply( t ) {
		document.body.classList.remove( 'wgl-theme-light', 'wgl-theme-dark', 'wgl-lightmode', 'wgl-darkmode' );
		document.body.classList.add( 'wgl-theme-' + t, 'wgl-' + t + 'mode' );
	}
	var theme = get();
	apply( theme );
	$( function () {
		var link = mw.util.addPortletLink( 'p-personal', '#', '', 'pt-dm-toggle', 'Toggle dark mode' );
		if ( !link ) {
			return;
		}
		$( link ).find( 'a' ).on( 'click', function ( e ) {
			e.preventDefault();
			theme = theme === 'light' ? 'dark' : 'light';
			try { localStorage.setItem( KEY, theme ); } catch ( err ) {}
			apply( theme );
		} );
	} );
}( jQuery, mediaWiki ) );
