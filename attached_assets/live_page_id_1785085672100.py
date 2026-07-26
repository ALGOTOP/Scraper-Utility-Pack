"""
Phase 1 — page-ID mode spot-check run.
Tests the targeted-advertiser search path using a page ID we found from
the filter options response (OmniFunnel Marketing, count=10 ads).
"""
import json
import shutil
from playwright.sync_api import sync_playwright
from rate_limiter import RateLimiter
from scraper import run_scrape

COUNTRY  = "US"
PAGE_IDS = ["150701661467827"]  # OmniFunnel Marketing — confirmed 10 ads

CHROMIUM_EXECUTABLE = shutil.which("chromium") or shutil.which("chromium-browser") or None
launch_kwargs = {"headless": True}
if CHROMIUM_EXECUTABLE:
    launch_kwargs["executable_path"] = CHROMIUM_EXECUTABLE

print(f"Running page-ID search for page {PAGE_IDS[0]} ...\n")
with sync_playwright() as p:
    browser = p.chromium.launch(**launch_kwargs)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()
    limiter = RateLimiter(min_delay_s=4.0, max_delay_s=8.0, max_requests_per_session=40)
    session = run_scrape(page, limiter, country=COUNTRY, page_ids=PAGE_IDS)
    browser.close()

print(f"session_status   : {session.session_status}")
print(f"urls_attempted   : {session.urls_attempted}")
print(f"graphql_hits     : {session.graphql_hits}")
print(f"dom_fallback_used: {session.dom_fallback_used}")
print(f"total results    : {len(session.results)}")

if session.results:
    print("\nAll results (spot-check against real page):")
    for r in session.results:
        print(
            f"  [{r.status:12s}] {r.source:12s} | "
            f"lib={r.library_id} | "
            f"{r.final_url or r.raw_href or 'NO URL'}"
        )

output = {
    "page_ids": session.page_ids,
    "country": session.country,
    "session_status": session.session_status,
    "graphql_hits": session.graphql_hits,
    "dom_fallback_used": session.dom_fallback_used,
    "results": [
        {
            "library_id":      r.library_id,
            "advertiser_name": r.advertiser_name,
            "raw_href":        r.raw_href,
            "final_url":       r.final_url,
            "status":          r.status,
            "source":          r.source,
            "start_date":      r.start_date,
        }
        for r in session.results
    ],
}
with open("results_page_id.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nSaved to scraper/results_page_id.json")
