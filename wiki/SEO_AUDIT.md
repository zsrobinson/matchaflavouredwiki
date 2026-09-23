# SEO audit — 23 September 2026

The site has a strong technical foundation and deeper article coverage than the sampled generated catalogues. It does not yet have evidence of superior Google rankings or link authority. The strongest English competitors are matchaflavoured.wiki and matchaflavored.org; outperforming them requires useful, current answers and discovery as well as technical correctness. See [the cited competitor research](SEO_RESEARCH.md).

## Evidence and scope

- Inspected source, the existing local export, a fresh export and representative public HTTP responses. No Search Console access, backlink dataset or field performance data was available.
- Live homepage, Installation, robots.txt and sitemap.xml returned 200; an invented article returned a genuine 404. The alternate domain matchaflavoured.org redirected to matchaflavou.red with 301. Browser-source retrieval failure was an audit-tool limitation: direct HTTP requests succeeded.
- Existing local export: 1,736 HTML files and 694 sitemap URLs. Every indexable article had one canonical, description and H1; descriptions were unique. All 694 were reachable from the homepage through ordinary links: 57 at depth 1, 611 at depth 2, 24 at depth 3, one at depth 4, plus the homepage.
- The fresh export from this checkout produced 1,735 article/category/project pages, 617 aliases and 696 distinct indexable canonical URLs. These are build measurements, not Google's indexed-page count. Differences from the older local export reflect its older contents.
- This is a local, undeployed audit branch. No push, PR, deployment, Search Console mutation or outreach was performed.

## Findings and changes

| Priority | Finding | Local change / interpretation |
| --- | --- | --- |
| High | Search results inherited the homepage canonical, description and WebSite JSON-LD, and had no noindex. robots.txt prevented crawlers reading a future noindex. Confirmed on the live search URL. | Search now has a distinct title and `noindex, follow`; inherited canonical/social/schema tags are removed. Search is crawlable so the directive can be read. It stays outside the sitemap. |
| Medium | The genuine 404 page inherited homepage metadata and title. | Give it a correct title and noindex; remove inherited identity. The existing 404 HTTP status was already correct and remains the important exclusion signal. |
| Medium | Existing redirect table contained 56 chains. Live Black_Shulker_Box redirected to Black_Sack, and Main_Page to Matcha_Flavoured_Wiki before the final destination. | Flatten chains during export, preserving final section anchors; reject cycles and missing destinations. Main_Page resolves directly to `/`. |
| Medium | Known trailing-slash and `.html` article variants returned temporary 307 redirects. Alternate hostname plus alias could add another hop; lowercase aliases were not consistently recognized. | Worker emits a single 301 to the final canonical URL for known variants, combining host/path normalization and preserving query strings. Missing URLs still fall through to asset handling. |
| Medium | Export caught individual page errors and continued successfully, allowing an incomplete sitemap/site to reach deploy. | Fail the export on any page error. CI now runs redirect/metadata tests and validates sitemap membership, canonical URLs, descriptions, H1s and utility exclusions after export. |
| Medium | Homepage advertised **0 articles**, a misleading sign of incompleteness. | Remove the renderer's unreliable article/file counters; retain the supported-version line. Say “unofficial” in the visible introduction. |
| Low | Homepage title repeated both spellings, while its description was about 260 characters. | Use a shorter descriptive title and description focused on recipes and guides. Alternate spelling remains in WebSite alternateName metadata. Google can still rewrite either snippet; character counts are not ranking rules. |

These fixes remove avoidable ambiguity and build failures; none guarantees a ranking increase. Google's guidance supports [consistent canonical signals](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls), [crawlable noindex directives](https://developers.google.com/search/docs/crawling-indexing/block-indexing), and [accurate status codes](https://developers.google.com/search/docs/crawling-indexing/http-network-errors).

## Existing strengths to preserve

- Rendered article content, recipes and ordinary links are present before JavaScript runs. The GitHub Pages competitors sampled in the research return loading shells.
- Article titles, unique lead-derived descriptions, absolute canonicals, structured data and a sitemap already exist. This is not a site missing basic SEO tags.
- The indexable article set is well connected; the existing export revealed no orphan sitemap pages. The majority are within two clicks of the homepage.
- Generated-only pages remain deliberately noindex. Review and enrich worthwhile pages before admitting them to the index; article counts alone are not a useful competitive target.
- Pack source citations, version pages, GitHub transparency and primary-source update workflows provide a useful basis for reader trust and factual maintenance.

## Next priorities

1. **Verify launch indexing, not imagined penalties.** The owner has submitted the sitemap. In Search Console, check its successful fetch and last-read date, then inspect `/`, `/w/Installation`, `/w/Guide_for_new_players`, `/w/Mud_Kiln`, `/w/Death` and one detailed item page. Check Google's chosen canonical, rendered content and exclusion reason. A public search sample cannot establish whether Google has indexed the site. [Google says crawling can take days to weeks](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl); repeated requests do not accelerate it.
2. **Measure the actual player questions.** Use Search Console queries and landing pages to prioritize installation failures, first-day progression, steel/silver routes, healing/death, recipe unlocks and seeds/saplings. Existing Installation, Guide for new players, Progression and detail pages already cover much of this. Improve answer placement and internal links where query evidence reveals a gap; avoid duplicative keyword landing pages. All new gameplay claims require primary-source verification.
3. **Differentiate through reference utility.** The existing [content audit](AUDIT.md) still identifies a complete disabled-vanilla table, ingredient-chain recipe browser and progression-aware spoiler controls as opportunities. These are separate product changes, not prerequisites for indexing. The guide competitor's focused task navigation and the community wiki's contributor network deserve attention even where this site's data is deeper.
4. **Measure performance on real page types.** Run mobile Lighthouse/PageSpeed on the homepage, a large recipe page, a guide and an overview; review LCP, INP/interaction behavior, CLS and table usability. This audit did not measure Core Web Vitals and does not claim a speed advantage from static rendering alone. Field data may be unavailable until traffic grows.
5. **Tidy maintenance-page navigation.** The old export contains template/skin links in maintenance categories whose namespaces are not exported. These are not orphan indexable articles; review conversion to GitHub source links or plain text separately. Check a fresh build before treating old category members as current broken links.
6. **Improve freshness accounting when needed.** Sitemap lastmod currently tracks the page's own source commit. Generated transclusions can change an article without changing that source. A dependency-aware date would be more accurate; do not simply stamp all URLs with the build date. Keep dates honest and verify release-sensitive prose after updates.
7. **Earn relevant discovery.** Useful source-backed answers and shareable deep links can attract community references. No backlink inventory was available; no outreach or link-building action was taken. Avoid buying links or creating redundant domains/content to manipulate rankings.

After an eventual deployment, repeat live checks for search noindex, genuine 404s, final redirect targets and sitemap fetch. Review Search Console weekly for 4–8 weeks as a measurement window, not an indexing deadline. Track impressions/clicks across both spellings and task queries rather than judging success by one broad “wiki” search.

## Validation

- Complete static export: **1,735 pages, 617 redirects, 0 export errors**.
- `python3 tools/check_seo.py dist`: **696 indexable URLs, 0 SEO errors**.
- Regression tests: **5 Python tests and 15 Worker tests passed**.
- Exhaustive Worker exercise with the actual generated table: **1,735 canonical titles do not redirect; 617 aliases reach their destination in one hop**. This exercises Worker routing with an asset stub; it is not a production deployment test.
- Updated homepage parsed through the local MediaWiki API without saving it: unofficial introduction present, no parser errors or red links. The full export used the existing renderer's homepage text; the separately parsed homepage edit will enter the export after a normal import/build. No shared renderer content was changed.
- Reviewed the implementation diff and ran whitespace checks. Original checkout remains unchanged.

Reproduce after building/importing the wiki:

```sh
python3 -m unittest discover -s tests -v
node --test tests/worker.test.mjs
python3 tools/export_static.py --out dist
python3 tools/check_seo.py dist
```
