"""
run_job.py — CLI entrypoint for the async job runner.

Called by the Node.js worker as a subprocess:
  python3 scraper/run_job.py --keyword "solar panels" --country US
  python3 scraper/run_job.py --country GB --page-ids 123456,789012

Outputs a JSON array to stdout:
  [{ "library_id", "advertiser_name", "final_url", "raw_href",
     "status", "source", "start_date",
     "score", "confidence", "needs_review", "review_status",
     "reasons", "country" }, ...]

Stderr is used for progress/debug logging (worker captures it separately).

NOTE (fix, 2026-07-27): the previous version of this file called
run_scrape(keyword=..., country=..., page_ids=...) directly, with no
Playwright `page` and no `RateLimiter` -- but run_scrape() requires both
as its first two positional args (see scraper.py). It also treated the
return value as a dict with a "results" key of plain ad dicts, when
run_scrape() actually returns a ScrapeSession dataclass whose .results
are ScrapedAd dataclass instances (no .get()). Both bugs meant every
job crashed immediately with:
    run_scrape() missing 2 required positional arguments: 'page' and
    'rate_limiter'
This version launches a real browser/rate limiter the same way
live_capture.py does, converts each ScrapedAd to a dict before scoring,
and uses scoring_engine's own `confidence` value instead of
recomputing a second, possibly-inconsistent one.
"""
from __future__ import annotations
import argparse
import dataclasses
import json
import shutil
import sys
import os

# Ensure scraper dir is on path regardless of working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from scraper import run_scrape, ScrapeSession
from rate_limiter import RateLimiter
from adapter import adapt_record, TARGET_COUNTRIES
from scoring_engine import score_lead

STATUS_MAP = {
    "ok": "resolved",
    "needs_review": "failed",
    "blocked": "failed",
    "no_results": "failed",
}


def score_session(session: ScrapeSession, country: str) -> list[dict]:
    """
    Convert a ScrapeSession's ScrapedAd results into scored lead dicts
    ready for the Node worker to insert into the DB.

    Pure function (no browser/network) so it's directly unit-testable
    against a ScrapeSession built from a mocked Playwright page --
    see test_run_job.py.
    """
    output = []
    for ad in session.results:
        ad_dict = dataclasses.asdict(ad)
        try:
            scored_record, _ = adapt_record(
                ad_dict, session_country=country, target_countries=TARGET_COUNTRIES
            )
            result = score_lead(scored_record)

            output.append({
                "library_id": ad_dict.get("library_id"),
                "advertiser_name": ad_dict.get("advertiser_name"),
                "final_url": ad_dict.get("final_url"),
                "raw_href": ad_dict.get("raw_href"),
                "source": ad_dict.get("source"),
                "ad_start_date": ad_dict.get("start_date"),
                "country": country,
                "score": result["score"],
                "confidence": result["confidence"],
                "needs_review": result["needs_review"],
                "review_status": "pending",
                "reasons": result["reasons"],
            })
        except Exception as exc:
            print(f"[run_job] Failed to score ad {ad_dict.get('library_id')}: {exc}", file=sys.stderr)
            continue

    return output


def run_job(keyword: str | None, country: str, page_ids: list[str]) -> list[dict]:
    """Launches a real browser, runs the scrape, and scores the results."""
    from playwright.sync_api import sync_playwright

    chromium_executable = (
        shutil.which("chromium") or shutil.which("chromium-browser") or None
    )
    launch_kwargs = {"headless": True}
    if chromium_executable:
        launch_kwargs["executable_path"] = chromium_executable

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            limiter = RateLimiter(min_delay_s=5.0, max_delay_s=10.0, max_requests_per_session=40)
            session = run_scrape(page, limiter, keyword=keyword, country=country, page_ids=page_ids)
        finally:
            browser.close()

    print(
        f"[run_job] session_status={session.session_status} "
        f"urls_attempted={session.urls_attempted} urls_blocked={session.urls_blocked} "
        f"graphql_hits={session.graphql_hits} dom_fallback_used={session.dom_fallback_used} "
        f"total_results={len(session.results)}",
        file=sys.stderr,
    )

    return score_session(session, country)


def main():
    parser = argparse.ArgumentParser(description="Run a Meta Ad Library scrape job")
    parser.add_argument("--keyword", type=str, default=None, help="Search keyword")
    parser.add_argument("--country", type=str, required=True, help="ISO 2-letter country code")
    parser.add_argument(
        "--page-ids",
        type=str,
        default="",
        help="Comma-separated list of Facebook Page IDs",
    )
    args = parser.parse_args()

    keyword = args.keyword or None
    country = args.country.upper()
    page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()] if args.page_ids else []

    if not keyword and not page_ids:
        print(json.dumps({"error": "Provide at least one of --keyword or --page-ids"}))
        sys.exit(1)

    print(f"[run_job] Starting scrape: keyword={keyword!r} country={country} page_ids={page_ids}", file=sys.stderr)

    try:
        output = run_job(keyword, country, page_ids)
    except Exception as exc:
        print(f"[run_job] Scrape failed: {exc}", file=sys.stderr)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    print(f"[run_job] Scored {len(output)} leads", file=sys.stderr)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
