/* In-game tooltips for inventory slots, like minecraft.wiki's minetips: hovering (or focusing) a
   slot shows the item's name and lore in the game's tooltip frame, next to the pointer (on touch
   screens, a first tap shows it and a second follows the link).
   Each slot carries its tooltip as a hidden .mf-tip (Module:Tooltip); slots without one show the
   item's name. Animated slots pause while hovered. Styles: #minetip-tooltip in
   Gadget-mcw-common.css and Gadget-mfw-ui.css.
   Plain DOM (no jQuery): the static export (tools/export_static.py) ships this file as is. */
( function () {
	'use strict';
	var tip = null;
	var current = null;
	var touchAt = 0;  // time of the last touch pointerdown
	var tapped = null;

	// The mouse events a tap fires come within a second of its touch pointerdown; a mouse move or a
	// key press ends that (so keyboards and screen readers are never mistaken for taps)
	function tapping() {
		return Date.now() - touchAt < 1000;
	}

	function escapeHtml( s ) {
		var span = document.createElement( 'span' );
		span.textContent = s;
		return span.innerHTML;
	}

	function content( item ) {
		var src = item.querySelector( '.mf-tip' );
		if ( src ) {
			return src.innerHTML;
		}
		// No lore: the name alone, from the slot's (now moved) title
		var el = item.querySelector( '[data-mf-title]' );
		var title = el && el.getAttribute( 'data-mf-title' );
		return title ? '<span class="minetip-title">' + escapeHtml( title ) + '</span>' : '';
	}

	// The browser's own title tooltip would show on top of ours
	function takeTitles( item ) {
		var els = item.querySelectorAll( '[title]' );
		for ( var i = 0; i < els.length; i++ ) {
			els[ i ].setAttribute( 'data-mf-title', els[ i ].getAttribute( 'title' ) );
			els[ i ].removeAttribute( 'title' );
		}
	}

	function place( x, y ) {
		var doc = document.documentElement;
		var w = tip.offsetWidth, h = tip.offsetHeight;
		var left = x + 11, top = y - 34;
		if ( left + w > doc.clientWidth ) {
			left = Math.max( 0, x - 11 - w );
		}
		top = Math.max( 0, Math.min( top, doc.clientHeight - h ) );
		tip.style.left = left + 'px';
		tip.style.top = top + 'px';
	}

	// Below the slot (above it near the bottom of the screen), so the finger doesn't hide either
	function placeBy( r ) {
		var doc = document.documentElement;
		var w = tip.offsetWidth, h = tip.offsetHeight;
		var top = r.bottom + h + 4 > doc.clientHeight ? r.top - h - 4 : r.bottom + 4;
		tip.style.left = Math.max( 0, Math.min( r.left, doc.clientWidth - w ) ) + 'px';
		tip.style.top = Math.max( 0, top ) + 'px';
	}

	function hide() {
		if ( !current ) {
			return;
		}
		var anim = current.closest( '.animated' );
		if ( anim ) {
			anim.classList.remove( 'animated-paused' );
		}
		current = tapped = null;
		if ( tip ) {
			tip.style.display = 'none';
		}
	}

	function show( item ) {
		takeTitles( item );
		var html = content( item );
		if ( !html ) {
			hide();
			return false;
		}
		hide();
		if ( !tip ) {
			tip = document.createElement( 'div' );
			tip.id = 'minetip-tooltip';
			tip.setAttribute( 'aria-hidden', 'true' );
			document.body.appendChild( tip );
		}
		tip.innerHTML = html;
		tip.style.display = 'block';
		current = item;
		var anim = item.closest( '.animated' );
		if ( anim ) {
			anim.classList.add( 'animated-paused' );
		}
		return true;
	}

	function slotItem( target ) {
		var item = target && target.closest ? target.closest( '.invslot-item' ) : null;
		return item && item.querySelector( 'img' ) ? item : null;
	}

	document.addEventListener( 'mouseover', function ( e ) {
		var item = slotItem( e.target );
		if ( item === current || tapping() ) {
			return;
		}
		if ( !item ) {
			hide();
			return;
		}
		if ( show( item ) ) {
			place( e.clientX, e.clientY );
		}
	} );
	document.addEventListener( 'mousemove', function ( e ) {
		if ( current && !tapping() ) {
			place( e.clientX, e.clientY );
		}
	} );
	document.addEventListener( 'mouseout', function ( e ) {
		if ( current && !tapping() && !current.contains( e.relatedTarget ) && slotItem( e.relatedTarget ) !== current ) {
			hide();
		}
	} );
	// Keyboard users get the tooltip beside the focused slot
	document.addEventListener( 'focusin', function ( e ) {
		var item = !tapping() && slotItem( e.target );
		if ( item && show( item ) ) {
			var r = item.getBoundingClientRect();
			place( r.right - 11 + 4, r.top + 34 );
		}
	} );
	document.addEventListener( 'focusout', hide );
	// Touch screens have no hover, so the mouse events a tap fires are ignored: the first tap on a
	// slot shows its tooltip, a second tap follows the slot's link, a tap elsewhere hides it
	document.addEventListener( 'pointerdown', function ( e ) {
		touchAt = e.pointerType === 'touch' ? Date.now() : 0;
	}, true );
	document.addEventListener( 'pointermove', function ( e ) {
		if ( e.pointerType === 'mouse' ) {
			touchAt = 0;
		}
	}, true );
	document.addEventListener( 'keydown', function () {
		touchAt = 0;
	}, true );
	document.addEventListener( 'click', function ( e ) {
		var item = slotItem( e.target );
		if ( !tapping() ) {
			return;
		} else if ( !item ) {
			hide();
		} else if ( item !== tapped && show( item ) ) {
			e.preventDefault();
			tapped = item;
			placeBy( item.getBoundingClientRect() );
		}
	}, true );
	// any scroll, including a wide table's sideways scroll (scroll events don't bubble)
	window.addEventListener( 'scroll', hide, { capture: true, passive: true } );
}() );
