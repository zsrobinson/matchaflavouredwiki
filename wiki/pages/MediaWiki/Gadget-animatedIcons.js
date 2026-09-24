/* Cycling slots and pictures (.animated), after minecraft.wiki's Gadget-site.js.
   One clock drives them all: every 2 seconds each .animated shows frame (tick mod its frame count),
   and a subframe container shows subframe (its number of full cycles mod its subframe count). So
   slots with the same frames always show the same variant: the slots of a recipe screen (Oak Planks
   in, Oak Fence Gate out), and a family page's infobox with its screens. While one is paused
   (.animated-paused: the tooltip is showing its frame), the clock stops, so everything stays in step.
   Pausing only the hovered slot, as minecraft.wiki does, left it a frame or more behind for good.
   Plain DOM (no jQuery): the static export (tools/export_static.py) ships this file as is. */
( function () {
	'use strict';
	var tick = 0;

	function show( parent, index ) {
		var frames = parent.children;
		var n = frames.length;
		for ( var i = 0; i < n; i++ ) {
			frames[ i ].classList.toggle( 'animated-active', i === index % n );
		}
		return frames[ index % n ];
	}

	setInterval( function () {
		if ( document.hidden || document.querySelector( '.animated-paused' ) ) {
			return;
		}
		tick++;
		var els = document.querySelectorAll( '.animated' );
		for ( var i = 0; i < els.length; i++ ) {
			var el = els[ i ];
			var n = el.children.length;
			if ( !n ) {
				continue;
			}
			var frame = show( el, tick );
			if ( frame && frame.classList.contains( 'animated-subframe' ) ) {
				show( frame, Math.floor( tick / n ) );
			}
		}
	}, 2000 );
}() );