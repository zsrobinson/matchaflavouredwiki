<?php
# Git transparency: every page links to its source file in the repository
# (the Talk, Edit / "Write this page", "View source" and "View history" tabs, and a footer line).
# Loaded from LocalSettings.php. site/repo.json holds the repository URL and branch and the public site;
# the wiki/ folder is mounted at /var/www/wiki so the page's file can be found.

$mfwRepo = json_decode( file_get_contents( __DIR__ . '/repo.json' ), true );

/** Repository path of a page's source file and its layer: pages, generated or missing. */
function mfwSourcePath( $title ) {
	$folders = [ NS_MAIN => 'Main', NS_PROJECT => 'Project', NS_FILE => 'File', NS_MEDIAWIKI => 'MediaWiki',
		NS_TEMPLATE => 'Template', NS_HELP => 'Help', NS_CATEGORY => 'Category', 828 => 'Module' ];
	$ns = $title->getNamespace();
	if ( !isset( $folders[$ns] ) ) {
		return null;
	}
	$name = str_replace( '/', '%2F', $title->getText() );
	if ( $ns === 828 && !str_ends_with( $name, '%2Fdoc' ) ) {
		$file = $name . '.lua';
	} elseif ( preg_match( '/\.(css|js|json)$/', $name ) ) {
		$file = $name;
	} else {
		$file = $name . '.wiki';
	}
	foreach ( [ 'pages', 'generated' ] as $layer ) {
		$rel = "wiki/$layer/{$folders[$ns]}/$file";
		if ( file_exists( "/var/www/$rel" ) ) {
			return [ $rel, $layer ];
		}
	}
	return [ "wiki/pages/{$folders[$ns]}/$file", 'missing' ];
}

function mfwGitHubUrl( $kind, $path ) {
	global $mfwRepo;
	$enc = implode( '/', array_map( 'rawurlencode', explode( '/', $path ) ) );
	return "{$mfwRepo['url']}/$kind/{$mfwRepo['branch']}/$enc";
}

function mfwNewFileUrl( $path ) {
	global $mfwRepo;
	$dir = implode( '/', array_map( 'rawurlencode', explode( '/', dirname( $path ) ) ) );
	return "{$mfwRepo['url']}/new/{$mfwRepo['branch']}/$dir?filename=" . rawurlencode( basename( $path ) );
}

/** GitHub's "Problem with a page" issue form (.github/ISSUE_TEMPLATE/page.yml), with the page filled in. */
function mfwIssueUrl( $title, $path ) {
	global $mfwRepo;
	$page = $mfwRepo['site'] . '/w/' . wfUrlencode( $title->getPrefixedDBkey() );
	return "{$mfwRepo['url']}/issues/new?" . http_build_query( [
		'template' => 'page.yml',
		'title' => '[' . $title->getPrefixedText() . '] ',
		'page' => "$page ($path)",
	], '', '&', PHP_QUERY_RFC3986 );
}

// Tabs as on minecraft.wiki: Page and Talk on the left, Read, Edit, View source and View history on
// the right, with Page and Read highlighted. Everything but Page and Read goes to GitHub: Talk opens an
// issue about the page, Edit opens its file in GitHub's editor (which forks and opens a pull request).
$wgHooks['SkinTemplateNavigation::Universal'][] = static function ( $skin, &$links ) {
	$title = $skin->getTitle();
	if ( !$title || $title->isSpecialPage() ) {
		return;
	}
	$src = mfwSourcePath( $title );
	if ( !$src ) {
		return;
	}
	[ $path, $layer ] = $src;
	$here = $title->getLocalURL();
	$native = reset( $links['namespaces'] );
	$links['namespaces'] = [
		'mfw-page' => [ 'text' => $native['text'] ?? 'Page', 'href' => $here, 'class' => 'selected' ],
		'mfw-talk' => [ 'text' => 'Talk', 'href' => mfwIssueUrl( $title, $path ) ],
	];
	$links['views'] = [ 'mfw-read' => [ 'text' => 'Read', 'href' => $here, 'class' => 'selected' ] ];
	if ( $layer === 'pages' ) {
		$links['views']['mfw-edit'] = [ 'text' => 'Edit', 'href' => mfwGitHubUrl( 'edit', $path ) ];
	} else {
		// generated or missing: a hand-written file at this path replaces the generated page
		$links['views']['mfw-edit'] = [ 'text' => 'Write this page',
			'href' => mfwNewFileUrl( str_replace( 'wiki/generated/', 'wiki/pages/', $path ) ) ];
	}
	if ( $layer !== 'missing' ) {
		$links['views']['mfw-source'] = [ 'text' => 'View source', 'href' => mfwGitHubUrl( 'blob', $path ) ];
		$links['views']['mfw-history'] = [ 'text' => 'View history', 'href' => mfwGitHubUrl( 'commits', $path ) ];
	}
};

/** URL of an uploaded file (an item icon), or null. */
function mfwFileUrl( $name ) {
	$file = \MediaWiki\MediaWikiServices::getInstance()->getRepoGroup()->findFile( $name );
	return $file ? $file->getUrl() : null;
}

/** The pack version the wiki describes (the generated Template:Data/Current version). */
function mfwPackVersion() {
	$text = @file_get_contents( '/var/www/wiki/generated/Template/Data%2FCurrent version.wiki' );
	return ( $text && preg_match( '/<includeonly>([^<]+)<\/includeonly>/', $text, $m ) ) ? trim( $m[1] ) : null;
}

// Footer, after minecraft.wiki's: a record of where the page comes from (four tiles with the game's
// icons), then the license and disclosure (MediaWiki:Copyright-footer), a row of links and the badges
// ($wgFooterIcons). The page's last-edit date comes from git, so tools/export_static.py fills it in;
// the live wiki shows a link to the history instead.
$wgHooks['SkinAddFooterLinks'][] = static function ( $skin, $key, &$footerItems ) {
	$title = $skin->getTitle();
	if ( !$title || $title->isSpecialPage() ) {
		return;
	}
	$src = mfwSourcePath( $title );
	$about = \MediaWiki\Title\Title::newFromText( 'Matcha Flavoured Wiki:About' );
	if ( $key === 'places' ) {
		$contrib = \MediaWiki\Title\Title::newFromText( 'Matcha Flavoured Wiki:Contributing' );
		// after MediaWiki's own "About Matcha Flavoured Wiki" (its privacy and disclaimer links are
		// switched off by MediaWiki:Privacy and MediaWiki:Disclaimers)
		$footerItems['mfw-contributing'] = '<a href="' . htmlspecialchars( $contrib->getLocalURL() ) . '">Contributing</a>';
		if ( $src ) {
			$footerItems['mfw-report'] = '<a href="' . htmlspecialchars( mfwIssueUrl( $title, $src[0] ) ) . '">Report a problem</a>';
		}
		global $mfwRepo;
		$footerItems['mfw-github'] = '<a href="' . htmlspecialchars( $mfwRepo['url'] ) . '">Source on GitHub</a>';
		return;
	}
	if ( $key !== 'info' ) {
		return;
	}
	// each tile is one link, so the whole card is clickable
	$tile = static function ( $icon, $label, $value, $href ) {
		$url = mfwFileUrl( $icon );
		$img = $url ? '<img src="' . htmlspecialchars( $url ) . '" width="32" height="32" alt="">' : '';
		return '<a class="mfw-rec" href="' . htmlspecialchars( $href ) . "\">$img<span><span class=\"mfw-rec-l\">$label</span>" .
			"<span class=\"mfw-rec-v\">$value</span></span></a>";
	};
	$tiles = '';
	if ( $src && $src[1] !== 'missing' ) {
		[ $path ] = $src;
		$tiles .= $tile( 'Book and Quill.png', 'Source file', '<code>' . htmlspecialchars( $path ) . '</code>',
			mfwGitHubUrl( 'blob', $path ) );
		$tiles .= $tile( 'Clock.png', 'Last edited',
			'<span class="mfw-lastmod" data-src="' . htmlspecialchars( $path ) . '">View history</span>',
			mfwGitHubUrl( 'commits', $path ) );
	}
	$version = mfwPackVersion();
	if ( $version ) {
		$page = \MediaWiki\Title\Title::newFromText( "Matcha Flavoured $version" );
		$tiles .= $tile( 'Compass.png', 'Describes', 'Matcha Flavoured ' . htmlspecialchars( $version ), $page->getLocalURL() );
	}
	$tiles .= $tile( 'Written Book.png', 'Written from', "the pack's code, release notes and the developer's videos only",
		$about->getLocalURL() . '#How_it_is_written' );
	$footerItems['mfw-record'] = "<div class=\"mfw-recs\">$tiles</div>";
};
