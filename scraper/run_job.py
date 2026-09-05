"""
run_job.py — CLI entrypoint for the async job runner.

The Node worker invokes this script and expects a JSON array on stdout.
The scraper now performs buyer-fit qualification for the $499 dedicated
product landing-page offer before returning records to the database.

Hard ICP exclusions are intentionally NOT inserted into the leads table.
Ambiguous records are retained as needs_review so a potentially good prospect
is never silently discarded just because Meta gave us incomplete metadata.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from scraper import run_scrape, ScrapeSession
from rate_limiter import RateLimiter
from adapter import adapt_record, TARGET_COUNTRIES
from scoring_engine import score_lead
from icp_filter import check_icp_mismatch


def score_session(session: ScrapeSession, country: str) -> list[dict]:
    """
    Convert scraped ads into DB-ready lead records.

    Priority leads and ambiguous review leads are returned. Hard ICP rejects
    are deliberately omitted from the output so the lead table remains useful
    for actual prospecting.
    """
    output = []
    excluded_count = 0
    review_count = 0
    priority_count = 0

    for ad in session.results:
        ad_dict = dataclasses.asdict(ad)
        try:
            scored_record, _ = adapt_record(
                ad_dict,
                session_country=country,
                target_countries=TARGET_COUNTRIES,
            )
            result = score_lead(scored_record)

            # Use the same full record for the compatibility ICP flag. This
            # does not run a second classifier with different inputs.
            icp_mismatch, icp_mismatch_reason = check_icp_mismatch(
                scored_record.get("business_name"),
                scored_record.get("landing_url"),
                ad_record=scored_record,
            )

            buyer_fit_status = result.get("buyer_fit_status", "review")
            if buyer_fit_status == "excluded":
                excluded_count += 1
                continue
            if buyer_fit_status == "priority":
                priority_count += 1
            else:
                review_count += 1

            output.append({
                "library_id": ad_dict.get("library_id"),
                "advertiser_name": ad_dict.get("advertiser_name"),
                "final_url": ad_dict.get("final_url"),
                "raw_href": ad_dict.get("raw_href"),
                "source": ad_dict.get("source"),
                "ad_start_date": ad_dict.get("start_date"),
                "country": country,
                "score": int(result["score"]),
                "confidence": result["confidence"],
                "needs_review": bool(result["needs_review"]),
                "review_status": "pending",
                "reasons": result["reasons"],
                "icp_mismatch": bool(icp_mismatch),
                "icp_mismatch_reason": icp_mismatch_reason,
            })
        except Exception as exc:
            print(
                f"[run_job] Failed to qualify ad {ad_dict.get('library_id')}: {exc}",
                file=sys.stderr,
            )
            # A classifier failure is a review item, never an automatic reject.
            output.append({
                "library_id": ad_dict.get("library_id"),
                "advertiser_name": ad_dict.get("advertiser_name"),
                "final_url": ad_dict.get("final_url"),
                "raw_href": ad_dict.get("raw_href"),
                "source": ad_dict.get("source"),
                "ad_start_date": ad_dict.get("start_date"),
                "country": country,
                "score": 0,
                "confidence": "low",
                "needs_review": True,
                "review_status": "pending",
                "reasons": [f"Buyer-fit qualification failed; manual review required: {exc}"],
                "icp_mismatch": False,
                "icp_mismatch_reason": None,
            })

    print(
        f"[run_job] buyer_fit priority={priority_count} review={review_count} "
        f"excluded={excluded_count} returned={len(output)}",
        file=sys.stderr,
    )
    return output


def run_job(keyword: str | None, country: str, page_ids: list[str]) -> list[dict]:
    """Launch a browser, scrape Meta, and qualify the results."""
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
            limiter = RateLimiter(
                min_delay_s=5.0,
                max_delay_s=10.0,
                max_requests_per_session=40,
            )
            session = run_scrape(
                page,
                limiter,
                keyword=keyword,
                country=country,
                page_ids=page_ids,
            )
        finally:
            browser.close()

    print(
        f"[run_job] session_status={session.session_status} "
        f"urls_attempted={session.urls_attempted} urls_blocked={session.urls_blocked} "
        f"graphql_hits={session.graphql_hits} dom_fallback_used={session.dom_fallback_used} "
        f"raw_results={len(session.results)}",
        file=sys.stderr,
    )
    return score_session(session, country)


def main():
    parser = argparse.ArgumentParser(description="Run a Meta Ad Library scrape job")
    parser.add_argument("--keyword", type=str, default=None, help="Search keyword")
    parser.add_argument("--country", type=str, required=True, help="ISO 2-letter country code")
    parser.add_argument("--page-ids", type=str, default="", help="Comma-separated Facebook Page IDs")
    args = parser.parse_args()

    keyword = args.keyword or None
    country = args.country.upper()
    page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()] if args.page_ids else []

    if not keyword and not page_ids:
        print(json.dumps({"error": "Provide at least one of --keyword or --page-ids"}))
        sys.exit(1)

    print(
        f"[run_job] Starting scrape: keyword={keyword!r} country={country} page_ids={page_ids}",
        file=sys.stderr,
    )

    try:
        output = run_job(keyword, country, page_ids)
    except Exception as exc:
        print(f"[run_job] Scrape failed: {exc}", file=sys.stderr)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    print(f"[run_job] Returning {len(output)} prospect records", file=sys.stderr)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
