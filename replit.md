# Meta Ad Library Scraper

A Python pipeline that scrapes Meta's public Ad Library for ads matching a keyword and/or advertiser page IDs, returning normalized records ready for a scoring engine.

## Run & Operate

```bash
cd scraper
python3 test_orchestration.py   # mocked unit tests (no network needed)
python3 live_capture.py         # keyword search → results.json
python3 live_page_id.py         # page-ID search → results_page_id.json
```

## Stack

- Python 3.11 (Nix module), Playwright 1.61, BeautifulSoup4 4.15
- System Chromium via Nix (`chromium` package) — Playwright's downloaded headless shell can't find libs on NixOS
- pnpm workspaces (Node/TS monorepo scaffolding, not used by scraper)

## Where things live

| Path | Purpose |
|------|---------|
| `scraper/scraper.py` | Orchestration, GraphQL interception, session rollup |
| `scraper/dom_parser.py` | Fallback DOM parser (anchored on "Library ID:" markers) |
| `scraper/link_unwrapper.py` | Unwraps Meta's l.facebook.com redirect shims |
| `scraper/rate_limiter.py` | Per-session delay + budget enforcement |
| `scraper/url_builder.py` | Builds Ad Library search URLs (keyword / page-ID / combined) |
| `scraper/test_orchestration.py` | 6 mocked orchestration tests |
| `scraper/live_capture.py` | Live keyword scrape + GraphQL shape inspection |
| `scraper/live_page_id.py` | Live page-ID scrape |
| `scraper/CAPTURE_INSTRUCTIONS.md` | Steps to update GraphQL field paths via DevTools |
| `scraper/results.json` | Last keyword search output |
| `scraper/results_page_id.json` | Last page-ID search output |

## Architecture decisions

- **Primary path: GraphQL interception** — intercepts the page's own network responses instead of parsing rotating CSS class names; only breaks if Meta changes the GraphQL schema, not on layout updates.
- **Fallback: DOM parser** — anchored on "Library ID:" (policy-mandated disclosure text) not CSS classes. Cards with no outbound link get `needs_review` status, not silent drops.
- **DOM fallback runs per-URL** — only triggered when GraphQL interception returns nothing for a given URL, so one rate-limited URL doesn't force DOM fallback for the whole session.
- **Chromium via Nix, not Playwright's downloaded shell** — NixOS doesn't expose FHS-style library paths; `executable_path=shutil.which("chromium")` passed to `p.chromium.launch()`.

## Gotchas

- Run `python3 test_orchestration.py` from `scraper/` before modifying any of the 6 core modules.
- Removed `"0 results"` from `NO_RESULTS_MARKERS` in scraper.py — it false-positives on "~730 results" (substring match). The `"no ads match"` marker covers genuine zero-results pages.
- `_find_card_container` max depth is 10 (real page DOM has links at depth 7-8; boundary at depth 9 with 29 IDs).
- `_find_outbound_link` prefers `l.facebook.com` shim links and skips direct `www.facebook.com` profile links, which appear first in the card DOM.
- Meta rate-limits GraphQL responses aggressively from shared IP ranges. DOM fallback is the primary path in Replit. Use a fresh session or residential IP to capture un-rate-limited GraphQL responses for confirming field paths.

## Pointers

- See `scraper/README.md` for spot-check results and phase 1 done criteria status.
- See `scraper/CAPTURE_INSTRUCTIONS.md` for the manual DevTools step to confirm GraphQL field paths.
- See the `pnpm-workspace` skill for Node/TS workspace structure details.
