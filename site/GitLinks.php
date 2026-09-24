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

$wgHooks['SkinAddFooterLinks'][] = static function ( $skin, $key, &$footerItems ) {
	if ( $key !== 'info' ) {
		return;
	}
	$title = $skin->getTitle();
	$src = ( $title && !$title->isSpecialPage() ) ? mfwSourcePath( $title ) : null;
	if ( !$src || $src[1] === 'missing' ) {
		return;
	}
	[ $path, $layer ] = $src;
	$contrib = htmlspecialchars( \MediaWiki\Title\Title::newFromText( 'Matcha Flavoured Wiki:Contributing' )->getLocalURL() );
	$blob = htmlspecialchars( mfwGitHubUrl( 'blob', $path ) );
	$code = '<code>' . htmlspecialchars( $path ) . '</code>';
	if ( $layer === 'pages' ) {
		$footerItems['mfw-source'] = "This page's source is <a href=\"$blob\">$code</a>. To suggest a change, " .
			'<a href="' . htmlspecialchars( mfwGitHubUrl( 'edit', $path ) ) . '">edit it on GitHub</a> and open a pull request ' .
			"(<a href=\"$contrib\">how to contribute</a>).";
	} else {
		$footerItems['mfw-source'] = "This page is generated from the pack's source code (<a href=\"$blob\">$code</a>). " .
			'To add writing, <a href="' . htmlspecialchars( mfwNewFileUrl( str_replace( 'wiki/generated/', 'wiki/pages/', $path ) ) ) .
			"\">create a hand-written page</a> in its place (<a href=\"$contrib\">how to contribute</a>).";
	}
};
