<?php
/**
 * Parse every page once and use that one render twice: for the links tables (categories,
 * page and template links, as maintenance/refreshLinks.php does) and for the parser cache,
 * so tools/check_site.py and tools/export_static.py don't parse the page again.
 * refreshLinks.php parses and discards, and runs on one core.
 *
 * Run one process per core, each taking every Nth page:
 *   php maintenance/run.php /var/www/site/renderPages.php --shard K --shards N
 * With the parser cache off (the local dev wiki), this refreshes the links tables only.
 */

use MediaWiki\Deferred\DeferredUpdates;
use MediaWiki\Maintenance\Maintenance;
use MediaWiki\MediaWikiServices;

require_once '/var/www/html/maintenance/Maintenance.php';

class RenderPages extends Maintenance {
	public function __construct() {
		parent::__construct();
		$this->addDescription( 'Fill the links tables and the parser cache from a single parse per page' );
		$this->addOption( 'shard', 'Which shard this process handles (0 to shards-1)', false, true );
		$this->addOption( 'shards', 'Number of processes sharing the work', false, true );
	}

	public function execute() {
		$shards = max( 1, (int)$this->getOption( 'shards', 1 ) );
		$shard = (int)$this->getOption( 'shard', 0 );
		// every Nth page id, not ranges: ids follow title order, and the expensive articles
		// and the cheap Template:Data pages sit in long runs
		$ids = $this->getReplicaDB()->newSelectQueryBuilder()
			->select( 'page_id' )
			->from( 'page' )
			->where( "page_id % $shards = $shard" )
			->orderBy( 'page_id' )
			->caller( __METHOD__ )
			->fetchFieldValues();
		$factory = MediaWikiServices::getInstance()->getWikiPageFactory();
		$start = microtime( true );
		$failed = 0;
		foreach ( $ids as $id ) {
			$page = $factory->newFromID( (int)$id );
			if ( !$page ) {
				continue;
			}
			try {
				// both calls share the page's DerivedPageDataUpdater, so the page is parsed once
				$page->updateParserCache( [ 'causeAction' => 'mfw-build' ] );
				$page->doSecondaryDataUpdates( [
					'recursive' => false,
					'defer' => DeferredUpdates::POSTSEND,
					'causeAction' => 'mfw-build',
				] );
				DeferredUpdates::doUpdates();
			} catch ( Throwable $e ) {
				$failed++;
				$this->error( $page->getTitle()->getPrefixedText() . ': ' . $e->getMessage() );
			}
		}
		$this->output( sprintf( "shard %d/%d: %d pages in %.0fs\n", $shard, $shards, count( $ids ),
			microtime( true ) - $start ) );
		if ( $failed ) {
			$this->fatalError( "$failed page(s) failed to render" );
		}
	}
}

$maintClass = RenderPages::class;
require_once RUN_MAINTENANCE_IF_MAIN;
