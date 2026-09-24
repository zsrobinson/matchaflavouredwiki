/* Image viewer: clicking a picture (an infobox image, a thumbnail, a gallery image or a diagram)
   opens it over the page at the largest size that fits, as other wikis do. Renders open their
   full-size file from /images/full/ (tools/images.py keeps them at twice the size pages use);
   diagrams are SVG and scale freely; textures and icons scale by whole pixels. A picture larger
   than the screen opens fitted, and clicking it shows it at full size, scrolling. Escape, the
   close button, a click beside the picture or the browser's back button closes it.
   Styles: #mfw-zoom in Gadget-mfw-ui.css.
   Plain DOM (no jQuery): the static export (tools/export_static.py) ships this file as is. */
( function () {
	'use strict';
	var TARGETS = [
		'.infobox-imagearea > div:not(.infobox-invimages) img',
		'figure[typeof^="mw:File"] img',
		'.gallerybox img',
		'.mfw-diagram img'
	].join( ',' );
	var box, stage, pic, caption, original, closer;
	var state = null;  // the open picture: {img, full, w, h, kind, zoomed}
	var returnFocus = null;
	var pushed = false;

	function zoomable( img ) {
		if ( !img.closest( '.mw-parser-output' ) || !img.matches( TARGETS ) ) {
			return false;
		}
		// a picture that links somewhere else keeps its link
		var link = img.closest( 'a' );
		return !link || link.classList.contains( 'mw-file-description' );
	}

	function mark( root ) {
		Array.prototype.forEach.call( root.querySelectorAll( TARGETS ), function ( img ) {
			if ( !zoomable( img ) ) {
				return;
			}
			img.classList.add( 'mfw-zoomable' );
			if ( !img.closest( 'a' ) ) {
				img.setAttribute( 'tabindex', '0' );
				img.setAttribute( 'role', 'button' );
			}
			img.setAttribute( 'aria-label', 'View ' + ( img.getAttribute( 'alt' ) || 'image' ) + ' larger' );
		} );
	}

	function stripQuery( url ) {
		return url.split( '#' )[ 0 ].split( '?' )[ 0 ];
	}

	// The file behind a picture: a thumbnail's original (/images/thumb/a/ab/Name.png/250px-Name.png)
	function fileUrl( img ) {
		var src = img.currentSrc || img.src;
		return src.replace( /\/thumb(\/[0-9a-f]\/[0-9a-f]{2}\/[^\/?#]+)\/[^\/?#]+/, '$1' );
	}

	function kindOf( img, url ) {
		if ( /\.svg$/i.test( stripQuery( url ) ) ) {
			return 'svg';
		}
		return img.closest( '.pixel-image' ) || img.classList.contains( 'pixel-image' ) ? 'pixel' : 'photo';
	}

	function captionOf( img ) {
		var holder = img.closest( 'figure, .gallerybox, .mfw-diagram, .infobox' );
		var el = holder && holder.querySelector( 'figcaption, .gallerytext, .mfw-diagram-caption, .infobox-caption' );
		if ( !el && holder && holder.classList.contains( 'infobox' ) ) {
			el = holder.querySelector( '.infobox-title' );
		}
		if ( el && el.textContent.trim() ) {
			var copy = el.cloneNode( true );
			// slot tooltips inside a caption would show as text here
			Array.prototype.forEach.call( copy.querySelectorAll( '.mf-tip' ), function ( t ) {
				t.remove();
			} );
			return copy.innerHTML;
		}
		return null;
	}

	function build() {
		box = document.createElement( 'div' );
		box.id = 'mfw-zoom';
		box.setAttribute( 'role', 'dialog' );
		box.setAttribute( 'aria-modal', 'true' );
		box.setAttribute( 'aria-label', 'Image viewer' );
		box.hidden = true;
		box.innerHTML = '<div class="mfw-zoom-stage"><img class="mfw-zoom-img" alt=""></div>' +
			'<div class="mfw-zoom-bar"><div class="mfw-zoom-caption"></div>' +
			'<a class="mfw-zoom-original" target="_blank" rel="noopener">Open original</a>' +
			'<button type="button" class="mfw-zoom-close" aria-label="Close">×</button></div>';
		document.body.appendChild( box );
		stage = box.querySelector( '.mfw-zoom-stage' );
		pic = box.querySelector( '.mfw-zoom-img' );
		caption = box.querySelector( '.mfw-zoom-caption' );
		original = box.querySelector( '.mfw-zoom-original' );
		closer = box.querySelector( '.mfw-zoom-close' );
		closer.addEventListener( 'click', close );
		stage.addEventListener( 'click', function ( e ) {
			if ( e.target === pic ) {
				toggle( e );
			} else {
				close();
			}
		} );
		window.addEventListener( 'resize', function () {
			if ( state ) {
				layout();
			}
		} );
	}

	// The scale that fits the picture in the stage, and the one clicking it switches to
	function scales() {
		var room = stage.getBoundingClientRect();
		var fit = Math.min( ( room.width - 32 ) / state.w, ( room.height - 32 ) / state.h );
		if ( state.kind === 'pixel' ) {
			// whole pixels, at least the picture's own size
			fit = fit >= 1 ? Math.floor( fit ) : fit;
			return { fit: fit, zoom: fit < 1 ? 1 : fit };
		}
		if ( state.kind === 'svg' ) {
			fit = Math.min( fit, 3 );
			return { fit: fit, zoom: Math.max( fit * 2, 1.5 ) };
		}
		fit = Math.min( fit, 1 );  // never blow up a render past its file
		return { fit: fit, zoom: 1 };
	}

	function layout() {
		var s = scales();
		var zooms = s.zoom > s.fit * 1.15;
		if ( !zooms ) {
			state.zoomed = false;
		}
		var scale = state.zoomed ? s.zoom : s.fit;
		pic.style.width = Math.round( state.w * scale ) + 'px';
		pic.style.height = Math.round( state.h * scale ) + 'px';
		box.classList.toggle( 'mfw-zoom-can-zoom', zooms && !state.zoomed );
		box.classList.toggle( 'mfw-zoom-zoomed', state.zoomed );
	}

	function toggle( e ) {
		var s = scales();
		if ( !( s.zoom > s.fit * 1.15 ) ) {
			return;
		}
		// keep the point under the pointer where it is
		var r = pic.getBoundingClientRect();
		var fx = ( e.clientX - r.left ) / r.width;
		var fy = ( e.clientY - r.top ) / r.height;
		var room = stage.getBoundingClientRect();
		state.zoomed = !state.zoomed;
		layout();
		if ( state.zoomed ) {
			stage.scrollLeft = fx * pic.offsetWidth + pic.offsetLeft - ( e.clientX - room.left );
			stage.scrollTop = fy * pic.offsetHeight + pic.offsetTop - ( e.clientY - room.top );
		}
	}

	function open( img ) {
		if ( !box ) {
			build();
		}
		var url = fileUrl( img );
		var kind = kindOf( img, url );
		var w = img.naturalWidth || +img.getAttribute( 'data-file-width' ) || img.width;
		var h = img.naturalHeight || +img.getAttribute( 'data-file-height' ) || img.height;
		if ( kind === 'svg' ) {  // an SVG's natural size is its drawing size
			w = +img.getAttribute( 'data-file-width' ) || w;
			h = +img.getAttribute( 'data-file-height' ) || h;
		}
		state = { img: img, full: url, w: w, h: h, kind: kind, zoomed: false };
		pic.className = 'mfw-zoom-img' + ( kind === 'pixel' ? ' mfw-zoom-pixel' : '' );
		pic.alt = img.getAttribute( 'alt' ) || '';
		pic.src = url;
		var text = captionOf( img );
		caption.innerHTML = text || '';
		caption.hidden = !text;
		original.href = url;
		returnFocus = document.activeElement;
		document.documentElement.classList.add( 'mfw-zoom-open' );
		box.hidden = false;
		stage.scrollTop = stage.scrollLeft = 0;
		layout();
		closer.focus();
		if ( kind === 'photo' ) {
			fullSize( img, url );
		}
		if ( !pushed && window.history && history.pushState ) {
			history.pushState( { mfwZoom: true }, '' );
			pushed = true;
		}
	}

	// Renders have a file twice the size in /images/full/; show it once it's loaded
	function fullSize( img, url ) {
		var name = stripQuery( url ).split( '/' ).pop();
		var big = new Image();
		var current = state;
		big.onload = function () {
			if ( state !== current ) {
				return;
			}
			state.w = big.naturalWidth;
			state.h = big.naturalHeight;
			state.full = big.src;
			pic.src = big.src;
			original.href = big.src;
			layout();
		};
		big.src = '/images/full/' + name;
	}

	function hide() {
		if ( !state ) {
			return;
		}
		box.hidden = true;
		pic.removeAttribute( 'src' );
		state = null;
		document.documentElement.classList.remove( 'mfw-zoom-open' );
		if ( returnFocus && returnFocus.focus ) {
			returnFocus.focus();
		}
	}

	function close() {
		if ( pushed ) {
			history.back();  // popstate hides it
		} else {
			hide();
		}
	}

	window.addEventListener( 'popstate', function () {
		pushed = false;
		hide();
	} );

	document.addEventListener( 'click', function ( e ) {
		if ( e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey ) {
			return;  // new tab or window: the link's own behaviour
		}
		var t = e.target;
		var img = t.closest && ( t.matches( 'img.mfw-zoomable' ) ? t :
			t.closest( 'a.mw-file-description' ) && t.closest( 'a.mw-file-description' ).querySelector( 'img.mfw-zoomable' ) );
		if ( img ) {
			e.preventDefault();
			open( img );
		}
	} );

	document.addEventListener( 'keydown', function ( e ) {
		if ( state ) {
			if ( e.key === 'Escape' ) {
				e.preventDefault();
				close();
			} else if ( e.key === 'Tab' ) {  // keep focus in the viewer
				var stops = [ original, closer ];
				var i = stops.indexOf( document.activeElement );
				e.preventDefault();
				stops[ ( i + ( e.shiftKey ? stops.length - 1 : 1 ) ) % stops.length ].focus();
			}
			return;
		}
		if ( ( e.key === 'Enter' || e.key === ' ' ) && e.target.matches && e.target.matches( 'img.mfw-zoomable' ) ) {
			e.preventDefault();
			open( e.target );
		}
	} );

	if ( document.readyState === 'loading' ) {
		document.addEventListener( 'DOMContentLoaded', function () {
			mark( document );
		} );
	} else {
		mark( document );
	}
}() );
