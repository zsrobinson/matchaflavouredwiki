<?php
# Git transparency: every page links to its source file in the repository
# ("Edit on GitHub" / "Write this page", "View source", "View history" tabs and a footer line).
# Loaded from LocalSettings.php. site/repo.json holds the repository URL and branch;
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
	if ( $layer === 'pages' ) {
		$links['views']['mfw-edit'] = [ 'text' => 'Edit on GitHub', 'href' => mfwGitHubUrl( 'edit', $path ) ];
	} else {
		// generated or missing: a hand-written file at this path replaces the generated page
		$links['views']['mfw-edit'] = [ 'text' => 'Write this page',
			'href' => mfwNewFileUrl( str_replace( 'wiki/generated/', 'wiki/pages/', $path ) ) ];
	}
	if ( $layer !== 'missing' ) {
		$links['views']['mfw-source'] = [ 'text' => 'View source', 'href' => mfwGitHubUrl( 'blob', $path ) ];
		$links['views']['mfw-history'] = [ 'text' => 'View history', 'href' => mfwGitHubUrl( 'commits', $path ) ];
	}
	if ( $skin->getSkinName() === 'minerva' ) {
		// Mobile: Minerva shows view links that have an icon as page-action buttons under the title
		$icons = [ 'mfw-edit' => 'edit', 'mfw-source' => 'wikiText', 'mfw-history' => 'history' ];
		foreach ( $icons as $key => $icon ) {
			if ( isset( $links['views'][$key] ) ) {
				$links['views'][$key]['icon'] = $icon;
			}
		}
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
