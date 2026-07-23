"""
Live capture script (Phase 1, step 2-5).

This does three things in one run:
  1. Intercepts the real GraphQL response from Meta Ad Library and prints
     its top-level shape so GRAPHQL_URL_PATTERN and field paths in
     _parse_graphql_payload can be confirmed/updated.
  2. Calls run_scrape() against one keyword+country combo.
  3. Writes results to results.json.

Run from the scraper/ directory:
  python3 live_capture.py
"""
import json
import sys
import os
import shutil

KEYWORD  = "funnel audit"
COUNTRY  = "US"
PAGE_IDS = []       # leave empty for keyword-only first run

# Use system Chromium on NixOS (Playwright's downloaded headless shell
# can't find NixOS's non-FHS library paths). Fall back to Playwright's
# own binary if nothing is found in PATH.
CHROMIUM_EXECUTABLE = shutil.which("chromium") or shutil.which("chromium-browser") or None

# Throttle the scroll loops when doing the initial capture so we get
# enough data without hammering the site.
SCROLL_STEPS = 3

# -----------------------------------------------------------------------
# Step 1 — intercept raw GraphQL responses before running run_scrape,
# so we can print the real payload shape for inspection.
# -----------------------------------------------------------------------
from playwright.sync_api import sync_playwright
from url_builder import build_search_url
from rate_limiter import RateLimiter
from scraper import run_scrape, GRAPHQL_URL_PATTERN

captured_raw = []   # will hold raw dict payloads for shape inspection


def _on_response(response):
    if GRAPHQL_URL_PATTERN in response.url and response.request.method == "POST":
        try:
            data = response.json()
            captured_raw.append({"url": response.url, "payload": data})
        except Exception:
            pass


def print_shape(obj, prefix="", max_depth=4, _depth=0):
    """Recursively print the key structure of a JSON blob."""
    if _depth > max_depth:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            print(f"{prefix}{k}:")
            print_shape(v, prefix + "  ", max_depth, _depth + 1)
    elif isinstance(obj, list):
        print(f"{prefix}[list, len={len(obj)}]")
        if obj:
            print_shape(obj[0], prefix + "  [0] ", max_depth, _depth + 1)
    else:
        print(f"{prefix}{type(obj).__name__} = {repr(obj)[:80]}")


print("=" * 60)
print(f"Live capture: keyword={KEYWORD!r}  country={COUNTRY}")
print(f"GRAPHQL_URL_PATTERN = {GRAPHQL_URL_PATTERN!r}")
print("=" * 60)

_launch_kwargs = {"headless": True}
if CHROMIUM_EXECUTABLE:
    _launch_kwargs["executable_path"] = CHROMIUM_EXECUTABLE
    print(f"Using system Chromium: {CHROMIUM_EXECUTABLE}")

with sync_playwright() as p:
    browser = p.chromium.launch(**_launch_kwargs)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()

    # Register raw interceptor to capture shape
    page.on("response", _on_response)

    # Navigate to the Ad Library search URL
    search_url = build_search_url(KEYWORD, country=COUNTRY)
    print(f"\nNavigating to:\n  {search_url}\n")

    try:
        page.goto(search_url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print(f"[WARN] goto raised: {e} — continuing anyway")

    # Scroll a few times to trigger paged GraphQL calls
    for i in range(SCROLL_STEPS):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2500)

    # -----------------------------------------------------------------------
    # Step 1 result — print captured payload shapes
    # -----------------------------------------------------------------------
    print(f"\nCaptured {len(captured_raw)} GraphQL response(s) matching {GRAPHQL_URL_PATTERN!r}\n")

    if not captured_raw:
        print(
            "[WARNING] No GraphQL responses intercepted.\n"
            "Possible causes:\n"
            "  - The endpoint path has changed (update GRAPHQL_URL_PATTERN in scraper.py)\n"
            "  - Meta returned results via a different mechanism (check the DOM fallback path)\n"
            "  - The page showed a captcha/checkpoint (check visible_text below)\n"
        )
        print("Visible page text (first 600 chars):")
        print(page.inner_text("body")[:600])
    else:
        for i, item in enumerate(captured_raw[:2]):   # show at most first 2
            print(f"--- Response {i+1} shape (URL: {item['url']}) ---")
            print_shape(item["payload"])
            print()

        # Save raw payload for manual inspection
        with open("captured_payload.json", "w") as f:
            json.dump(captured_raw[:2], f, indent=2, default=str)
        print("Raw payload(s) saved to scraper/captured_payload.json for manual diff.\n")

    page.remove_listener("response", _on_response)
    browser.close()

# -----------------------------------------------------------------------
# Step 2 — run run_scrape() with a fresh browser and the existing field
# paths so we can see how many results come through.
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("Running run_scrape() with existing field paths ...")
print("=" * 60 + "\n")

with sync_playwright() as p:
    browser = p.chromium.launch(**_launch_kwargs)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()

    limiter = RateLimiter(min_delay_s=5.0, max_delay_s=10.0, max_requests_per_session=40)
    session = run_scrape(page, limiter, keyword=KEYWORD, country=COUNTRY, page_ids=PAGE_IDS)

    browser.close()

# -----------------------------------------------------------------------
# Step 3 — report and persist
# -----------------------------------------------------------------------
print(f"session_status   : {session.session_status}")
print(f"urls_attempted   : {session.urls_attempted}")
print(f"urls_blocked     : {session.urls_blocked}")
print(f"graphql_hits     : {session.graphql_hits}")
print(f"dom_fallback_used: {session.dom_fallback_used}")
print(f"total results    : {len(session.results)}")

if session.results:
    print("\nFirst 10 results (spot-check against the real Ad Library page):")
    for r in session.results[:10]:
        print(
            f"  [{r.status:12s}] {r.source:12s} | "
            f"{(r.advertiser_name or 'N/A'):40s} | "
            f"{r.final_url or r.raw_href or 'NO URL'}"
        )

# Persist all results to JSON
output = {
    "keyword":           session.keyword,
    "country":           session.country,
    "page_ids":          session.page_ids,
    "session_status":    session.session_status,
    "urls_attempted":    session.urls_attempted,
    "urls_blocked":      session.urls_blocked,
    "graphql_hits":      session.graphql_hits,
    "dom_fallback_used": session.dom_fallback_used,
    "results": [
        {
            "library_id":      r.library_id,
            "advertiser_name": r.advertiser_name,
            "raw_href":        r.raw_href,
            "final_url":       r.final_url,
            "status":          r.status,
            "source":          r.source,
        }
        for r in session.results
    ],
}
with open("results.json", "w") as f:
    json.dump(output, f, indent=2)

print(f"\nAll {len(session.results)} results written to scraper/results.json")
