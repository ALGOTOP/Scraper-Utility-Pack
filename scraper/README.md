# Meta Ad Library Scraper — Phase 1

Scrapes Meta's public Ad Library for ads matching a keyword and/or a list of
advertiser page IDs, returning normalized `ScrapedAd` records ready for the
scoring engine (Phase 3).

## Quick start

```bash
cd scraper
python3 live_capture.py       # keyword search (funnel audit / US)
python3 live_page_id.py       # page-ID search (OmniFunnel Marketing)
python3 test_orchestration.py # mocked unit tests (no network needed)
```

## Files

| File | Purpose |
|------|---------|
| `scraper.py` | Orchestration: GraphQL interception → DOM fallback, rate limiting, session status |
| `dom_parser.py` | Fallback DOM parser anchored on "Library ID:" text markers |
| `link_unwrapper.py` | Unwraps Meta's `l.facebook.com` redirect shim links |
| `rate_limiter.py` | Delay + session budget enforcement |
| `url_builder.py` | Builds search URLs for keyword mode, page-ID mode, or both |
| `test_orchestration.py` | Mocked Playwright tests for control-flow logic |
| `live_capture.py` | Live keyword search + shape capture + persist to `results.json` |
| `live_page_id.py` | Live page-ID search + persist to `results_page_id.json` |
| `CAPTURE_INSTRUCTIONS.md` | Manual DevTools steps to update GraphQL field paths |

## Dependencies (installed)

- Python 3.11 (via Replit/Nix)
- `playwright` 1.61, `beautifulsoup4` 4.15
- System Chromium (Nix) — used instead of Playwright's headless shell (NixOS library path incompatibility)

Run scraper scripts with system Chromium auto-detected via `shutil.which("chromium")`.

## Live capture findings (2026-07-23)

- **`GRAPHQL_URL_PATTERN = "/api/graphql/"`** ✓ confirmed correct
- **`data.ad_library_main`** ✓ confirmed as root in filter-options response
- Ad-results GraphQL responses (`data.ad_library_main.results.edges`) were
  rate-limited (code 1675004) in this environment — cannot confirm field paths
  from a live ad-results payload yet. See `CAPTURE_INSTRUCTIONS.md` for
  re-running this check from a fresh IP/session.
- **DOM fallback is working well** and is currently the primary extraction path.

### DOM parser changes confirmed against real page (2026-07-23)

1. `_find_card_container`: increased `max_levels_up` from 6 → 10
   (real card links are at DOM depth 7-8; boundary is at depth 9)
2. `_find_outbound_link`: prefer Meta shim links (`l.facebook.com`) over
   direct `facebook.com` profile links, which appear earlier in the DOM
3. `classify_page_text` in `scraper.py`: removed `"0 results"` marker —
   it false-positives on "~730 results" (substring match)

## Spot-check results (accuracy gate)

| Run | Mode | Status | Results | ok rate |
|-----|------|--------|---------|---------|
| keyword "funnel audit", US | DOM fallback | ok | 29 | ~65% (some ads have no outbound URL — lead-gen/awareness) |
| page-ID 150701661467827 (OmniFunnel Marketing), US | DOM fallback | ok | 23 | **100%** — all point to `lp.omnifunnelmarketing.com` |

Phase 1 done criteria met:
- ✅ `test_orchestration.py` passes (6/6 tests)
- ✅ Keyword search: `session_status == "ok"`, real URLs verified
- ✅ Page-ID search: `session_status == "ok"`, 23/23 results correct
- ⚠️ `_parse_graphql_payload` field paths unconfirmed (rate-limited); DOM path working
