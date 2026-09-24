<?php
# Spoiler scopes for the "hide spoilers" toggle (MediaWiki:Gadget-mfwShell.js, site/theme-boot.js).
# {{Spoiler}} is a warning box at the start of what it covers: the rest of its section, up to the
# next heading of the same or a higher level (a box in the lead covers the rest of the page). CSS
# can't select "the siblings up to the next heading", so every element in that range is marked here
# with class="mfw-spoiler-body" and the box's number (data-mfw-spoiler="N", on the box as well).
# The marks change nothing on their own: only html.mfw-hide-spoilers (the reader's choice) hides them,
# before first paint. Loaded from LocalSettings.php; only pages with a spoiler box are touched.

use MediaWiki\Tidy\RemexCompatFormatter;
use Wikimedia\RemexHtml\HTMLData;
use Wikimedia\RemexHtml\Serializer\Serializer;
use Wikimedia\RemexHtml\Serializer\SerializerNode;
use Wikimedia\RemexHtml\Tokenizer\Tokenizer;
use Wikimedia\RemexHtml\TreeBuilder\Dispatcher;
use Wikimedia\RemexHtml\TreeBuilder\TreeBuilder;

class MfwSpoilerFormatter extends RemexCompatFormatter {
	/** @var array per parent element: the current section level and the open spoiler, if any */
	private $siblings = [];
	private $count = 0;

	public function element( SerializerNode $parent, SerializerNode $node, $contents ) {
		// siblings close in document order, so each parent's state walks its children in order
		$s = $this->siblings[$parent->id] ?? [ 'level' => 0, 'spoiler' => 0, 'from' => 0 ];
		$class = $node->attrs['class'] ?? '';
		$level = null;
		if ( preg_match( '/(?:^|\s)mw-heading([1-6])(?:\s|$)/', $class, $m ) ) {
			$level = (int)$m[1];
		} elseif ( preg_match( '/^h([1-6])$/', $node->name, $m ) ) {
			$level = (int)$m[1];
		}
		if ( $level !== null ) {
			if ( $s['spoiler'] && $level <= $s['from'] ) {
				$s['spoiler'] = 0;
			}
			$s['level'] = $level;
		}
		$mark = null;
		if ( $node->name === 'table' && preg_match( '/(?:^|\s)messagebox(?:\s|$)/', $class )
			&& preg_match( '/(?:^|\s)spoiler(?:\s|$)/', $class ) ) {
			$s['spoiler'] = ++$this->count;
			$s['from'] = $s['level'];
			$mark = [ 'data-mfw-spoiler' => (string)$s['spoiler'] ];
		} elseif ( $s['spoiler'] ) {
			$mark = [ 'class' => trim( "$class mfw-spoiler-body" ), 'data-mfw-spoiler' => (string)$s['spoiler'] ];
		}
		$this->siblings[$parent->id] = $s;
		if ( $mark ) {
			$node = clone $node;
			$node->attrs = $node->attrs->clone();
			foreach ( $mark as $k => $v ) {
				$node->attrs[$k] = $v;
			}
		}
		return parent::element( $parent, $node, $contents );
	}
}

/** The page HTML with its spoiler scopes marked (unchanged if it has no spoiler box). */
function mfwMarkSpoilers( string $html ): string {
	if ( !preg_match( '/class="messagebox spoiler/', $html ) ) {
		return $html;
	}
	$serializer = new Serializer( new MfwSpoilerFormatter() );
	$treeBuilder = new TreeBuilder( $serializer, [ 'ignoreErrors' => true, 'ignoreNulls' => true ] );
	$tokenizer = new Tokenizer( new Dispatcher( $treeBuilder ), $html, [
		// as MediaWiki's own tidy pass (RemexDriver), which RemexCompatFormatter expects
		'ignoreErrors' => true, 'ignoreCharRefs' => true, 'ignoreNulls' => true, 'skipPreprocess' => true,
	] );
	$tokenizer->execute( [ 'fragmentNamespace' => HTMLData::NS_HTML, 'fragmentName' => 'body' ] );
	return $serializer->getResult();
}

$wgHooks['OutputPageBeforeHTML'][] = static function ( $out, &$text ) {
	$text = mfwMarkSpoilers( $text );
};
