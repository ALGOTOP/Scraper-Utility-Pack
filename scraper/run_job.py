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
"""
from __future__ import annotations
import argparse
import json
import sys
import os

# Ensure scraper dir is on path regardless of working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from scraper import run_scrape
from adapter import adapt_record, TARGET_COUNTRIES

STATUS_MAP = {
    "ok": "resolved",
    "needs_review": "failed",
    "blocked": "failed",
    "no_results": "failed",
}


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

    # Run the scrape
    try:
        scrape_result = run_scrape(
            keyword=keyword,
            country=country,
            page_ids=page_ids,
        )
    except Exception as exc:
        print(f"[run_job] Scrape failed: {exc}", file=sys.stderr)
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)

    raw_ads = scrape_result.get("results", [])
    print(f"[run_job] Scraped {len(raw_ads)} ads", file=sys.stderr)

    # Score each ad via the adapter
    output = []
    for ad in raw_ads:
        try:
            scored_record, _ = adapt_record(ad, session_country=country, target_countries=TARGET_COUNTRIES)

            # Map confidence
            score_val = scored_record.get("score", 0)
            confidence = "high" if score_val >= 7 else "medium" if score_val >= 4 else "low"

            output.append({
                "library_id": ad.get("library_id"),
                "advertiser_name": ad.get("advertiser_name"),
                "final_url": ad.get("final_url"),
                "raw_href": ad.get("raw_href"),
                "source": ad.get("source"),
                "ad_start_date": ad.get("start_date"),
                "country": country,
                "score": scored_record.get("score", 0),
                "confidence": confidence,
                "needs_review": scored_record.get("needs_review", False),
                "review_status": "pending",
                "reasons": scored_record.get("reasons", []),
            })
        except Exception as exc:
            print(f"[run_job] Failed to score ad {ad.get('library_id')}: {exc}", file=sys.stderr)
            continue

    print(f"[run_job] Scored {len(output)} leads", file=sys.stderr)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
