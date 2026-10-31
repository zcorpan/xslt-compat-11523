# Compat impact of removing XSLT (whatwg/html#11523)

Proposed change: remove XSLT from the web platform, both the `<?xml-stylesheet type="text/xsl"?>`
processing instruction and the `XSLTProcessor` API.

## Summary

- In the 2026-09-01 HTTP Archive crawl, 632 pages applied an XSLT processing instruction
  (0.001% of desktop pages, 0.0015% of mobile) and 2,418 constructed an `XSLTProcessor` (0.0057%
  desktop, 0.0042% mobile). No page did both.
- Loading a random sample of 200 of them in Chrome with XSLT on and off, by manual review:
  12 broken, 85 worse, 68 no visible change, 35 not assessable (load error, 4xx/5xx).
- Extrapolated: about 120 broken pages (roughly 0.00025% of crawled pages) and about 1,260 worse.
- Broken: pages whose XML is the human-facing document (a customer portal, a university phone
  directory, the DWD Climate Data Center, a parcel carrier login, an event flyer);
  SinglePlatform's restaurant menu widget; some Flarum forums that fail to boot or render an empty
  tags page.
- Worse: mostly SEO sitemaps and RSS/Atom feeds, which show the raw XML viewer, and Flarum forums,
  which lose tags, labels, excerpts, and "best answer". Flarum ships an XSLT polyfill since
  flarum/framework#4359 (2.x) and flarum/framework#4644 (1.x); these sites haven't updated.
- No visible change: MathJax 2.x's `mml3.js` (feature detection handles it) and EBSCO's Flipster
  widget, which seems to transform server-side now.
- Chrome's field rate for `XSLTProcessor` (chromestatus, 0.01–0.08% of page loads in October 2026)
  is several times the crawl's. That may mean the crawl undercounts (it mostly doesn't visit feeds,
  sitemaps, deep links, intranets, and logged-in pages), or that `XSLTProcessor` is on a few heavily
  used pages; field rates count page loads, not pages.

- Of the 26 pages the August 2025 analysis rated broken, 12 still break, 9 are fine now, and 5
  don't load (section 4).

## 1. HTTP Archive

`hits.sql` lists every page in the 2026-09-01 crawl (`httparchive.crawl.pages`, both clients, root
and non-root pages) whose `features` hit one of these Blink use counters:

- `XSLProcessingInstruction` (78): counted in `DocumentXSLT::ApplyXSLTransform`, so only when a
  processing instruction's transform actually runs.
- `XSLTProcessor` (79): counted in the `XSLTProcessor` constructor, so on every
  `new XSLTProcessor()`, whether or not it transforms anything.
- `XSLPIInSVGImage` (5777), `XSLPIInSVGStandaloneDoc` (5778): no hits.

`totals.sql` gives the denominators. Results in `hits.csv` and `totals.csv`:

| | desktop | mobile |
|---|---|---|
| Pages crawled (root + non-root) | 21,352,534 | 28,328,765 |
| `XSLProcessingInstruction` (root / non-root) | 208 (84 / 124) | 424 (72 / 352) |
| `XSLTProcessor` (root / non-root) | 1,217 (666 / 551) | 1,201 (641 / 560) |

The crawl ran in Chrome before XSLT was disabled in stable. Crawls from after that won't show
these pages, because counter 78 only fires when a transform runs.

## 2. Live comparison on a sample

`sample.py` picks 50 pages per counter and client (four strata, 200 pages), ordered by the SHA-256
of the page URL plus a fixed seed (`sample.jsonl`).

`compare.py` loads each page in Chrome Canary 158.0.8108.0 via Playwright: desktop at 1366×768,
mobile at 360×640 with a mobile UA and touch. It waits for `load` and 3s, then records the URL,
content type, title, whether the XML viewer is shown, the first 3,000 characters of text, page
errors, the same for each frame, and the stacks of `XSLTProcessor` constructions, and takes a
full-page screenshot at CSS-pixel scale (cropped to 4,000px):

1. **A**: XSLT on (`--enable-features=XSLT --disable-features=GenerateXSLTWarningBanner`; the
   banner is Chrome's deprecation notice injected into transformed documents).
2. **A2**: the same again, to separate page noise (carousels, animations, ads).
3. **B**: XSLT off (`--disable-features=XSLT`), which is what Chrome ships.

Before the run, it checks both settings on `sanity/doc.xml`. Raw measurements are in
`out/results.jsonl`.

`analyze.py` rates the clear cases (`out/auto.csv`):

- *not assessable*: load error or HTTP 4xx/5xx with XSLT on.
- *no visible change*: A vs B text and pixel differences within the A vs A2 noise.
- *worse*: B shows the XML viewer for a sitemap, feed, or OAI endpoint (by URL, title, or text).

It writes A|B pairs for the other 55 pages to `out/review/`, which I reviewed by hand. Final
ratings with notes are in `out/review.csv`. One page needed a recheck with `recheck.py`
(`out/review/189-recheck.png`): a spinner in B was page timing.

| Stratum | Pages hit | Sampled | Broken | Worse | No visible change | Not assessable |
|---|---|---|---|---|---|---|
| 78 desktop | 208 | 50 | 6 | 13 | 13 | 18 |
| 78 mobile | 424 | 50 | 3 | 34 | 5 | 8 |
| 79 desktop | 1,217 | 50 | 0 | 20 | 25 | 5 |
| 79 mobile | 1,201 | 50 | 3 | 18 | 25 | 4 |

`extrapolate.py` scales each stratum by (count / 50) × stratum size, with exact binomial 95%
intervals summed per counter (`out/summary.md`):

| Counter | Broken | Worse | No visible change | Not assessable |
|---|---|---|---|---|
| 78 | ~50 (15–121) | ~342 (256–425) | ~96 (45–176) | ~143 (78–229) |
| 79 | ~72 (15–285) | ~919 (597–1,277) | ~1,209 (859–1,559) | ~218 (67–496) |

What's behind the ratings:

- **78, broken:** the XML document is the page and B shows raw XML: MD Medicus customer portal,
  Pécs University phone directory, DWD Climate Data Center (homepage and imprint), DX Despatch
  login, a Buddhist society event flyer. The same sites appear in both clients.
- **78, worse:** Yoast, Rank Math, and AIOSEO sitemaps; RSS/Atom feeds; an OAI-PMH endpoint; a
  personal site whose embedded RSS iframe shows raw XML.
- **78, no visible change:** library sites with EBSCO's Flipster carousel (the counter fired in the
  crawl but the widget renders the same live), and pages where the XSLT frame isn't visible.
- **79, broken:** SinglePlatform's menu widget falls back to `ActiveXObject`, throws, and the menu
  is missing (`out/review/164.png`, `out/review/164-lower.png`); one Flarum forum fails to boot
  and shows its no-JS fallback; one Flarum `/tags` page renders empty.
- **79, worse:** Flarum forums: `XSLTProcessor is not defined` (or `ActiveXObject is not defined`)
  stops extensions that initialize later, so tags, tag labels, excerpts, and "best answer" are
  missing while posts render. Also a few sites missing a hero banner.
- **79, no visible change:** MathJax 2.x `mml3.js`; Flarum forums that seem to be on the polyfill already.

## 3. Top 100k pages

None of the sampled pages is in the top 100k CrUX rank buckets, so `top100k.jsonl` runs all 13
hits there through the same steps (`out-top100k/`). With review: 10 no visible change (MathJax,
nothing.community on Flarum, seemingly with the polyfill; redalyc; illuminateed), 3 not assessable (dict.leo.org
and athome.co.jp return 403/405). Two needed a recheck with `recheck.py`
(`out-top100k/review/*-recheck.png`): the differences were page timing.

## 4. Pages rated broken in August 2025

The [August 2025 analysis](https://github.com/whatwg/html/issues/11523#issuecomment-3200690662)
(desktop, `XSLProcessingInstruction` only) rated 26 pages as having essential functionality broken
without XSLT (`followup-2025/sheet-2025.csv`, exported from its spreadsheet). `select.py` lists them
with whether they hit the counters in the 2026-09-01 crawl (17 did). `check.py` loads each one
desktop-sized in Chrome Canary 158.0.8108.0 with XSLT on and off, on 2026-10-19
(`results.jsonl`, `review/`). Ratings in `review.csv`:

- 12 still broken: raw XML as the page (sudoc.abes.fr twice, dikrom.com, mahabodhi.org, Saxonica's
  download page, two livetrail pages, whose transform now redirects to a new site), or unstyled
  text in an iframe (two CELCAT Web Publisher timetables, intra-mart's API docs, olrb.gov.on.ca's
  notices, rs-r.co.jp's new items).
- 9 fine now: 5 Avionté RD Web Access login pages render the same without XSLT; my.yomiuri.co.jp
  and np2c.edu.hk no longer use XSLT; jadual.ums.edu.my redirects to a login page without it;
  saxonica.com's root redirects to an HTML version when `XSLTProcessor` is missing (it already did
  in July 2025, per the Wayback Machine).
- 5 not assessable: timeout, DNS failure (2), HTTP 401, HTTP 500.

Microsoft says RD Web Access stops rendering as expected without XSLT (MC1491832, KB5130994,
October 2026), presumably beyond the login page, which neither the crawl nor this check reaches.

## 5. XSLT polyfill extensions

To find bugs in the [XSLT polyfill](https://github.com/mfreed7/xslt_polyfill) and the extensions
that ship it, `ext-compare.py` loads all 239 pages from sections 2–4 (`sample.jsonl`,
`top100k.jsonl`, `followup-2025/broken-2025.csv`) on 2026-10-31, each in a fresh profile:

- Chrome Canary 158.0.8110.0 via Playwright. **A**, **A2**: `--enable-features=XSLT`, no
  extension. **E**: `--disable-features=XSLT` with
  [mfreed7/xslt_extension](https://github.com/mfreed7/xslt_extension) 1.0.26 (polyfill 1.0.33),
  loaded with CDP `Extensions.loadUnpacked`, since Chrome ignores `--load-extension`.
- Firefox Nightly 161.0a1 via geckodriver. **A**, **A2**: `dom.xslt.enabled` true, no extension.
  **E**: `dom.xslt.enabled` false with [zcorpan/xslt_extension](https://github.com/zcorpan/xslt_extension)
  1.0.26 (the same content script and polyfill) as a temporary add-on. Mobile pages get a mobile
  UA and a 360×640 window, but no meta viewport.

It records the same measurements as `compare.py`, waiting 5s after `load`, plus console messages,
exceptions, whether `XSLTProcessor` is native or the polyfill, and whether the polyfill's spinner
is still shown. `ext-analyze.py` flags pages where E differs from A beyond the A vs A2 noise, shows
raw XML in the page or a frame, still shows the spinner, or logs errors or exceptions that A and A2
don't (`out-ext-*/auto.csv`), and writes A|E pairs for them to `out-ext-*/review/`:

| | Chrome | Firefox |
|---|---|---|
| Flagged | 72 | 66 |
| Same as native | 118 | 158 |
| Not assessable | 49 | 15 |

Chrome has more not assessable mostly because it counts navigation and screenshot timeouts as
load errors, while the Firefox path measures the page anyway.

I spot-checked the flagged pairs and traced them to distinct causes. Most flagged pages are
sitemaps and feeds with small rendering differences. Others are pages where the transform fails
and raw XML or an error shows, or where page scripts throw only with the extension. Some were page
noise or server failures. Each cause was reproduced in both browsers on a minimal page in
`ext-repro/www/` (`ext-repro/run.py`, output in `ext-repro/results-*.txt`).

The findings are reported with `xslt-compat-11523` in the title:
[polyfill issues](https://github.com/mfreed7/xslt_polyfill/issues?q=is%3Aissue%20%22xslt-compat-11523%22%20in%3Atitle),
[extension issues](https://github.com/mfreed7/xslt_extension/issues?q=is%3Aissue%20%22xslt-compat-11523%22%20in%3Atitle).

## Not covered

- Pages the crawl rarely visits: feeds, sitemaps, deep links, intranets, logged-in pages.
- Interaction: logged-in Flarum use, such as the composer, which likely uses the same formatter.
- CAP emergency alerts: not in the sample. Chrome special-cases them until Chrome 176.
- Engines other than Chromium. Firefox has its own XSLT implementation (`dom.xslt.enabled`).

## Query bytes

All on the 2026-09-01 crawl, run on 2026-10-17:

| Query | Bytes processed |
|---|---|
| `hits.sql` | 209.1 GB |
| `totals.sql` | 0.9 GB |
| `hits.sql` on a 1% `TABLESAMPLE` (prototype, not included) | 2.1 GB |

## Reproduce

```sh
bq query --use_legacy_sql=false --format=csv --max_rows=1000000 < hits.sql > hits.csv
bq query --use_legacy_sql=false --format=csv < totals.sql > totals.csv
python3 sample.py hits.csv sample.jsonl
python3 -m venv .venv && .venv/bin/pip install playwright pillow
CHROME="/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
.venv/bin/python compare.py "$CHROME" sample.jsonl out
.venv/bin/python analyze.py out
# review out/review/*.png by hand and record ratings in out/review.csv
python3 extrapolate.py out/review.csv sample.jsonl > out/summary.md
.venv/bin/python recheck.py "$CHROME" <url> <360|1366> <out.png>
cd followup-2025
python3 select.py sheet-2025.csv ../hits.csv broken-2025.csv
../.venv/bin/python check.py "$CHROME" broken-2025.csv . > results.jsonl
cd ..
.venv/bin/pip install selenium
FIREFOX="/Applications/Firefox Nightly.app/Contents/MacOS/firefox"
export GECKODRIVER=<path to geckodriver>
.venv/bin/python ext-compare.py chrome "$CHROME" ../../mfreed7/xslt_extension out-ext-chrome
.venv/bin/python ext-compare.py firefox "$FIREFOX" ../xslt_extension out-ext-firefox
.venv/bin/python ext-analyze.py out-ext-chrome
.venv/bin/python ext-analyze.py out-ext-firefox
.venv/bin/python ext-repro/run.py chrome ../../mfreed7/xslt_extension
.venv/bin/python ext-repro/run.py firefox ../xslt_extension
```

Any Chrome with the `XSLT` feature works; check that `compare.py`'s sanity check passes for both
settings. The run used Playwright 1.64.0 and Pillow 13.0.0. The first 191 pages ran before
`compare.py` had its 90s per-visit timeout; three pages hung and stalled the run, which was then
resumed for the remaining nine (`run.log`). Live pages change, so a rerun won't match exactly.
Full-page screenshots (`out/shots/`, 190 MB) aren't committed; `compare.py` regenerates them.

Browser output was scrubbed for publishing with `scrub.py` (`python3 scrub.py 'hits.csv,sample.jsonl,top100k.jsonl,followup-2025/*.csv' 'out/results.jsonl,out-top100k/results.jsonl,followup-2025/results.jsonl' <IP>`):
the tester's IP replaced with `[client IP]`, and query strings and fragments stripped from URLs
other than crawl URLs and script URLs in `xsltStacks`. The analysis outputs are unchanged.
`out-ext-chrome/results.jsonl` and `out-ext-firefox/results.jsonl` were scrubbed the same way
before `ext-analyze.py` ran; stripping query strings made two console messages match A, so
Chrome had 74 flagged pages before scrubbing. The extension runs used Playwright 1.64.1, Selenium
4.52.0, and geckodriver 0.37.1.
