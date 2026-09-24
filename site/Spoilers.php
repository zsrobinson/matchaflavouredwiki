<?php
# Spoilers are hidden by default (MediaWiki:Gadget-mfwShell.js, site/theme-boot.js), until clicked.
# This marks what gets hidden, in each page's HTML:
# - {{Spoiler}} is a warning box at the start of what it covers: the rest of its section, up to the
#   next heading of the same or a higher level (a box in the lead covers the rest of the page). CSS
#   can't select "the siblings up to the next heading", so every element in that range is marked
#   with class="mfw-spoiler-body" and the box's number (data-mfw-spoiler="N", on the box as well).
# - Secret items (MediaWiki:Mfw-secrets, written by tools/generate.py from the pack's data) are
#   hidden wherever they are named: each link to one gets class="mfw-spoiler", and so does a row of a
#   wikitable that links or names one, so its recipe or effects are hidden too. A secret's own page
#   isn't marked. Other plain text isn't: tools/lint_pages.py and tools/check_site.py report it.
# The marks change nothing on their own: html.mfw-hide-spoilers hides them, before first paint.
# Loaded from LocalSettings.php; pages with neither a box nor a secret are not touched.

use MediaWiki\MediaWikiServices;
use MediaWiki\Tidy\RemexCompatFormatter;
use Wikimedia\HtmlArmor\HtmlArmor;
use Wikimedia\RemexHtml\HTMLData;
use Wikimedia\RemexHtml\Serializer\Serializer;
use Wikimedia\RemexHtml\Serializer\SerializerNode;
use Wikimedia\RemexHtml\Tokenizer\Tokenizer;
use Wikimedia\RemexHtml\TreeBuilder\Dispatcher;
use Wikimedia\RemexHtml\TreeBuilder\TreeBuilder;

class MfwSpoilerFormatter extends RemexCompatFormatter {
	/** @var Serializer|null to look up a row's table */
	public $serializer;
	/** @var array lowercased secret titles => true */
	private $secrets;
	/** @var string|null a regex matching their names in text */
	private $names = null;
	/** @var array per parent element: the current section level and the open spoiler, if any */
	private $siblings = [];
	private $count = 0;

	public function __construct( array $secrets ) {
		parent::__construct();
		$this->secrets = $secrets;
		$this->names = mfwNamesRegex( $secrets );
	}

	private static function hasClass( $class, $name ) {
		return (bool)preg_match( '/(?:^|\s)' . preg_quote( $name, '/' ) . '(?:\s|$)/', $class );
	}

	/** The table a row belongs to (through its tbody or thead), or null. */
	private function tableOf( SerializerNode $parent ) {
		for ( $n = $parent, $i = 0; $n && $i < 2; $n = $this->serializer->getParentNode( $n ), $i++ ) {
			if ( $n->name === 'table' ) {
				return $n;
			}
		}
		return null;
	}

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
		$mark = [];
		if ( $node->name === 'table' && self::hasClass( $class, 'messagebox' ) && self::hasClass( $class, 'spoiler' ) ) {
			$s['spoiler'] = ++$this->count;
			$s['from'] = $s['level'];
			$mark['data-mfw-spoiler'] = (string)$s['spoiler'];
		} elseif ( $s['spoiler'] ) {
			$class = trim( "$class mfw-spoiler-body" );
			$mark = [ 'class' => $class, 'data-mfw-spoiler' => (string)$s['spoiler'] ];
		}
		// a link to a secret, and a wikitable row that has one
		$secret = false;
		if ( $node->name === 'a' && isset( $node->attrs['href'] ) ) {
			$secret = isset( $this->secrets[mfwLinkTitle( $node->attrs['href'] )] );
		} elseif ( $node->name === 'tr' && ( preg_match( '/class="(?:[^"]*\s)?mfw-spoiler(?:\s[^"]*)?"/', $contents )
			|| ( $this->names && preg_match( $this->names, html_entity_decode( strip_tags( $contents ) ) ) ) )
		) {
			// a row that links a secret or names one (a generated table's "Cooking Recipe (Gnocchi)")
			$table = $this->tableOf( $parent );
			$secret = $table && self::hasClass( $table->attrs['class'] ?? '', 'wikitable' );
		}
		if ( $secret ) {
			$mark['class'] = trim( "$class mfw-spoiler" );
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

/** The lowercased title a /w/ link points to ("" for anything else). */
function mfwLinkTitle( string $href ): string {
	if ( !preg_match( '#^/w/([^?\#]+)#', $href, $m ) ) {
		return '';
	}
	return mb_strtolower( str_replace( '_', ' ', rawurldecode( $m[1] ) ) );
}

/** The secret items, lowercased (MediaWiki:Mfw-secrets), without the page being viewed. */
function mfwSecrets( string $self ): array {
	$text = wfMessage( 'mfw-secrets' )->inContentLanguage();
	if ( $text->isDisabled() ) {
		return [];
	}
	$secrets = [];
	foreach ( preg_split( '/\n/', $text->plain() ) as $line ) {
		$t = mb_strtolower( trim( $line ) );
		if ( $t !== '' && $t !== $self ) {
			$secrets[$t] = true;
		}
	}
	return $secrets;
}

/** A regex matching the secrets' names in text (plurals too), or null. */
function mfwNamesRegex( array $secrets ) {
	if ( !$secrets ) {
		return null;
	}
	$quoted = array_map( static function ( $s ) {
		return preg_quote( $s, '/' );
	}, array_keys( $secrets ) );
	usort( $quoted, static function ( $a, $b ) {
		return strlen( $b ) - strlen( $a );
	} );
	// not \b: a name can end in punctuation ("You're Rich!")
	return '/(?<!\\w)(?:' . implode( '|', $quoted ) . ')(?:e?s)?(?!\\w)/iu';
}

/** The page HTML with its spoilers marked (unchanged if it has neither a spoiler box nor a secret). */
function mfwMarkSpoilers( string $html, array $secrets ): string {
	// a link to a secret has its name in its title attribute, so this finds links and words alike
	$names = mfwNamesRegex( $secrets );
	$named = $names && preg_match( $names, $html );
	if ( !$named && !preg_match( '/class="messagebox spoiler/', $html ) ) {
		return $html;
	}
	$formatter = new MfwSpoilerFormatter( $secrets );
	$serializer = new Serializer( $formatter );
	$formatter->serializer = $serializer;
	$treeBuilder = new TreeBuilder( $serializer, [ 'ignoreErrors' => true, 'ignoreNulls' => true ] );
	$tokenizer = new Tokenizer( new Dispatcher( $treeBuilder ), $html, [
		// as MediaWiki's own tidy pass (RemexDriver), which RemexCompatFormatter expects
		'ignoreErrors' => true, 'ignoreCharRefs' => true, 'ignoreNulls' => true, 'skipPreprocess' => true,
	] );
	$tokenizer->execute( [ 'fragmentNamespace' => HTMLData::NS_HTML, 'fragmentName' => 'body' ] );
	return $serializer->getResult();
}

$wgHooks['OutputPageBeforeHTML'][] = static function ( $out, &$text ) {
	$title = $out->getTitle();
	$text = mfwMarkSpoilers( $text, mfwSecrets( $title ? mb_strtolower( $title->getPrefixedText() ) : '' ) );
};
// category listings are built outside the page's HTML above: mark their links to secrets here
$wgHooks['CategoryViewer::generateLink'][] = static function ( $type, $title, $html, &$link ) {
	static $secrets = null;
	$secrets ??= mfwSecrets( '' );
	if ( $type === 'page' && isset( $secrets[mb_strtolower( $title->getPrefixedText() )] ) ) {
		$link = MediaWikiServices::getInstance()->getLinkRenderer()->makeLink( $title, new HtmlArmor( $html ), [ 'class' => 'mfw-spoiler' ] );
	}
};
