/* Page previews, like minecraft.wiki's (the Popups extension): resting the mouse on a link to
   another article shows a card with the page's lead paragraph and its infobox picture.
   There is no API behind it: the card is read from the linked page itself (same origin, fetched
   once and cached), so the live wiki and the static export behave the same. Links in inventory
   slots keep their in-game tooltip (Gadget-mfwTooltip.js); touch screens get no previews, as on
   minecraft.wiki. Markup follows Popups (.mwe-popups), so the vendored dark theme applies;
   styles: MediaWiki:Common.css.
   Plain DOM (no jQuery): the static export (tools/export_static.py) ships this file as is. */
( function () {
	'use strict';
	var SHOW_DELAY = 500, HIDE_DELAY = 300, POINTER = 26, GAP = 8;
	var cache = {};
	var card = null;
	var link = null;      // the link the card is for (or is waiting to show for)
	var showTimer = 0, hideTimer = 0;
	var mouseX = null;

	// An article on this wiki: /w/Title, no namespace, not a red link, not the current page
	function target( a ) {
		if ( !a || !a.closest || a.classList.contains( 'new' ) || !a.closest( '#mw-content-text' ) ||
			a.closest( '.invslot, .mwe-popups, #toc, .mw-editsection' ) || a.querySelector( 'img' ) ||
			// a hidden spoiler (Gadget-mfwShell.js) gets no preview until it is clicked
			( document.documentElement.classList.contains( 'mfw-hide-spoilers' ) &&
				a.closest( '.mfw-spoiler:not(.mfw-spoiler-shown), .mfw-spoiler-body:not(.mfw-spoiler-shown)' ) ) ) {
			return null;
		}
		var url;
		try {
			url = new URL( a.getAttribute( 'href' ) || '', location.href );
		} catch ( e ) {
			return null;
		}
		if ( url.origin !== location.origin || url.search || !/^\/w\/[^:]+$/.test( decodeURIComponent( url.pathname ) ) ||
			url.pathname === location.pathname ) {
			return null;
		}
		return url.pathname;
	}

	// The first real paragraph of the article (as tools/seo.py picks the description), with links
	// unwrapped and footnote markers dropped, and the infobox picture
	function extract( html ) {
		var doc = new DOMParser().parseFromString( html, 'text/html' );
		var body = doc.querySelector( '#mw-content-text .mw-parser-output' );
		if ( !body ) {
			return null;
		}
		var paras = body.querySelectorAll( ':scope > p' ), p = null;
		for ( var i = 0; i < paras.length; i++ ) {
			if ( paras[ i ].textContent.trim().length > 40 ) {
				p = paras[ i ];
				break;
			}
		}
		if ( !p ) {
			return null;
		}
		p.querySelectorAll( 'sup.reference, .mf-tip' ).forEach( function ( el ) {
			el.remove();
		} );
		p.querySelectorAll( 'a' ).forEach( function ( a ) {
			a.replaceWith.apply( a, a.childNodes );
		} );
		var img = body.querySelector( '.infobox-imagearea img' );
		return {
			html: p.innerHTML.trim(),
			spoiler: p.classList.contains( 'mfw-spoiler-body' ),  // covered by a {{Spoiler}} box (site/Spoilers.php)
			img: img && {
				src: img.getAttribute( 'src' ),
				w: +img.getAttribute( 'data-file-width' ) || img.width,
				h: +img.getAttribute( 'data-file-height' ) || img.height,
				pixel: !!img.closest( '.pixel-image' )
			}
		};
	}

	function load( path ) {
		if ( !cache[ path ] ) {
			cache[ path ] = fetch( path, { credentials: 'same-origin' } ).then( function ( r ) {
				return r.ok ? r.text() : '';
			} ).then( extract, function () {
				return null;
			} );
		}
		return cache[ path ];
	}

	function build( data, href ) {
		// a page's lead covered by {{Spoiler}}, while the reader hides spoilers (Gadget-mfwShell.js)
		if ( data.spoiler && document.documentElement.classList.contains( 'mfw-hide-spoilers' ) ) {
			data = { html: null, img: null };
		}
		var el = document.createElement( 'div' );
		// wide pictures (structure views) go on top, square and tall ones (icons, mobs) at the side
		var wide = data.img && data.img.w > data.img.h * 1.3;
		var tall = data.img && !wide;
		el.className = 'mwe-popups mwe-popups-type-page ' + ( tall ? 'mwe-popups-is-tall' : 'mwe-popups-is-not-tall' );
		el.setAttribute( 'role', 'tooltip' );
		var box = document.createElement( 'div' );
		box.className = 'mwe-popups-container';
		if ( data.img ) {
			var pic = document.createElement( 'a' );
			pic.className = 'mwe-popups-discreet';
			pic.href = href;
			pic.tabIndex = -1;
			var img = document.createElement( 'img' );
			img.className = 'mwe-popups-thumbnail' + ( data.img.pixel ? ' mfw-popups-pixel' : '' );
			img.src = data.img.src;
			img.alt = '';
			pic.appendChild( img );
			box.appendChild( pic );
		}
		var text = document.createElement( 'a' );
		text.className = 'mwe-popups-extract';
		text.dir = 'ltr';
		text.href = href;
		text.tabIndex = -1;
		var p = document.createElement( 'p' );
		if ( data.html === null ) {
			p.textContent = 'Spoiler: hidden by your spoiler setting.';
		} else {
			p.innerHTML = data.html;
		}
		text.appendChild( p );
		box.appendChild( text );
		el.appendChild( box );
		el.addEventListener( 'mouseenter', function () {
			clearTimeout( hideTimer );
		} );
		el.addEventListener( 'mouseleave', scheduleHide );
		return el;
	}

	// Below the line of the link the pointer is on, the pointer's arrow over the mouse; flipped
	// above the link near the bottom of the screen, and to the left near the right edge
	function place( a ) {
		var rects = a.getClientRects(), r = rects[ 0 ];
		for ( var i = 0; i < rects.length && mouseX !== null; i++ ) {
			if ( mouseX >= rects[ i ].left && mouseX <= rects[ i ].right ) {
				r = rects[ i ];
			}
		}
		var x = mouseX !== null && mouseX >= r.left && mouseX <= r.right ? mouseX : r.left + Math.min( r.width / 2, POINTER );
		var doc = document.documentElement;
		var w = card.offsetWidth, h = card.offsetHeight;
		var flipX = x - POINTER + w > doc.clientWidth && x + POINTER - w >= 0;
		var flipY = r.bottom + GAP + h > doc.clientHeight && r.top - GAP - h >= 0;
		card.classList.toggle( 'flipped-x', flipX && !flipY );
		card.classList.toggle( 'flipped-y', flipY && !flipX );
		card.classList.toggle( 'flipped-x-y', flipX && flipY );
		var left = flipX ? x + POINTER - w : Math.max( 0, x - POINTER );
		card.style.left = ( left + window.scrollX ) + 'px';
		card.style.top = ( ( flipY ? r.top - GAP - h : r.bottom + GAP ) + window.scrollY ) + 'px';
		card.classList.remove( 'mwe-popups-fade-in-up', 'mwe-popups-fade-in-down' );
		card.classList.add( flipY ? 'mwe-popups-fade-in-down' : 'mwe-popups-fade-in-up' );
	}

	function hide() {
		clearTimeout( showTimer );
		clearTimeout( hideTimer );
		if ( link && link.hasAttribute( 'data-mfw-title' ) ) {
			link.setAttribute( 'title', link.getAttribute( 'data-mfw-title' ) );
			link.removeAttribute( 'data-mfw-title' );
		}
		link = null;
		if ( card ) {
			card.remove();
			card = null;
		}
	}

	function scheduleHide() {
		clearTimeout( hideTimer );
		hideTimer = setTimeout( hide, HIDE_DELAY );
	}

	function start( a, path ) {
		if ( a === link ) {
			clearTimeout( hideTimer );
			return;
		}
		hide();
		link = a;
		// the browser's own title tooltip would show on top of the card
		if ( a.hasAttribute( 'title' ) ) {
			a.setAttribute( 'data-mfw-title', a.getAttribute( 'title' ) );
			a.removeAttribute( 'title' );
		}
		var ready = load( path );
		showTimer = setTimeout( function () {
			ready.then( function ( data ) {
				if ( link !== a || !data ) {
					return;
				}
				card = build( data, a.href );
				document.body.appendChild( card );
				place( a );
			} );
		}, SHOW_DELAY );
	}

	document.addEventListener( 'pointerover', function ( e ) {
		if ( e.pointerType !== 'mouse' ) {
			return;
		}
		var a = e.target.closest && e.target.closest( 'a' );
		var path = target( a );
		if ( path ) {
			mouseX = e.clientX;
			start( a, path );
		}
	} );
	document.addEventListener( 'pointerout', function ( e ) {
		if ( link && e.pointerType === 'mouse' && !link.contains( e.relatedTarget ) ) {
			scheduleHide();
		}
	} );
	document.addEventListener( 'focusin', function ( e ) {
		var path = target( e.target.closest && e.target.closest( 'a' ) );
		if ( path && e.target.matches( ':focus-visible' ) ) {
			mouseX = null;
			start( e.target.closest( 'a' ), path );
		}
	} );
	document.addEventListener( 'focusout', function () {
		if ( link && mouseX === null ) {
			hide();
		}
	} );
	document.addEventListener( 'keydown', function ( e ) {
		if ( e.key === 'Escape' ) {
			hide();
		}
	} );
	document.addEventListener( 'click', hide, true );
}() );
