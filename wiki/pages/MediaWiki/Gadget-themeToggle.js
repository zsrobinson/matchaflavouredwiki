// Light/dark toggle in the personal menu, as on matchaflavoured.wiki.
// Standalone: the dark palette is in MediaWiki:Common.css under .mfw-theme-dark.
( function ( $, mw ) {
	var KEY = 'mfw-theme';
	function get() {
		try { return localStorage.getItem( KEY ) || 'light'; } catch ( e ) { return 'light'; }
	}
	function set( t ) {
		try { localStorage.setItem( KEY, t ); } catch ( e ) {}
	}
	function apply( t ) {
		document.body.classList.remove( 'mfw-theme-light', 'mfw-theme-dark' );
		document.body.classList.add( 'mfw-theme-' + t );
	}
	var theme = get();
	apply( theme );
	$( function () {
		var link = mw.util.addPortletLink( 'p-personal', '#', '', 'pt-theme-toggle', 'Change theme' );
		if ( !link ) {
			return;
		}
		$( link ).find( 'a' ).addClass( 'oo-ui-icon-advanced' ).on( 'click', function ( e ) {
			e.preventDefault();
			theme = theme === 'light' ? 'dark' : 'light';
			set( theme );
			apply( theme );
		} );
	} );
}( jQuery, mediaWiki ) );
