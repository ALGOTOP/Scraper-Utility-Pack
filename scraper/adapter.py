"""
Adapter / scoring glue.

Converts raw ScrapedAd records into the richer record consumed by the
buyer-fit scoring engine. The adapter deliberately preserves the Meta fields
that matter for the $499 landing-page offer instead of reducing an ad to only
business name + URL.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from scoring_engine import score_lead
from icp_filter import check_icp_mismatch

TARGET_COUNTRIES = [
    "US", "GB", "AU", "CA", "IE", "NZ", "DE", "NL",
    "SE", "NO", "DK", "CH", "AE", "SG",
]

STATUS_MAP = {
    "ok": "resolved",
    "needs_review": "failed",
    "blocked": "failed",
    "no_results": "failed",
}

_ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def _clean_business_name(raw_name):
    if not raw_name:
        return ""
    return "".join(c for c in str(raw_name) if c not in _ZERO_WIDTH_CHARS).strip()


def ad_active_days_from_start(start_date_unix):
    if not start_date_unix:
        return None
    try:
        days = (time.time() - float(start_date_unix)) / 86400
    except (TypeError, ValueError):
        return None
    return max(0, int(days))


def adapt_record(scraped: dict, session_country: str,
                 target_countries: list = None) -> tuple[dict, bool]:
    """Build the scoring record while preserving rich Meta ad signals."""
    target_countries = target_countries if target_countries is not None else TARGET_COUNTRIES
    active_days = ad_active_days_from_start(scraped.get("start_date"))

    page_categories = scraped.get("page_categories") or scraped.get("categories") or []
    if isinstance(page_categories, str):
        page_categories = [page_categories]

    ad_record = {
        "business_name": _clean_business_name(scraped.get("advertiser_name")),
        "country": (session_country or "").upper(),
        "landing_url": scraped.get("final_url"),
        "raw_href": scraped.get("raw_href"),
        "resolution_status": STATUS_MAP.get(scraped.get("status"), "failed"),
        "ad_active_days": active_days if active_days is not None else 0,
        "target_countries": target_countries,
        "ad_body": scraped.get("ad_body") or scraped.get("body"),
        "ad_title": scraped.get("ad_title") or scraped.get("title"),
        "caption": scraped.get("caption"),
        "cta_text": scraped.get("cta_text"),
        "cta_type": scraped.get("cta_type"),
        "page_categories": page_categories,
        "page_like_count": scraped.get("page_like_count"),
        "is_active": scraped.get("is_active"),
        "platforms": scraped.get("platforms") or [],
        "library_id": scraped.get("library_id"),
    }
    return ad_record, active_days is None


def score_batch(scraped_records: list, session_country: str,
                target_countries: list = None) -> list:
    scored = []
    for rec in scraped_records:
        ad_record, active_days_unknown = adapt_record(rec, session_country, target_countries)
        result = score_lead(ad_record)
        mismatch, mismatch_reason = check_icp_mismatch(
            ad_record["business_name"], ad_record["landing_url"], ad_record=ad_record
        )
        scored.append({
            "library_id": rec.get("library_id"),
            "business_name": ad_record["business_name"] or "(no name captured)",
            "landing_url": ad_record["landing_url"],
            "source": rec.get("source"),
            "active_days_unknown": active_days_unknown,
            "score": result["score"],
            "confidence": result["confidence"],
            "needs_review": result["needs_review"],
            "buyer_fit_status": result.get("buyer_fit_status"),
            "reasons": result["reasons"],
            "icp_mismatch": mismatch,
            "icp_mismatch_reason": mismatch_reason,
        })
    return scored


def bucket_lead(s: dict) -> str:
    status = s.get("buyer_fit_status")
    if status == "priority":
        return "priority"
    if status == "review" or s.get("needs_review"):
        return "needs_review"
    return "excluded"


def run_report(scraped_records: list, session_country: str, label: str,
               target_countries: list = None, sample_size: int = 8):
    scored = score_batch(scraped_records, session_country, target_countries)
    buckets = Counter(bucket_lead(s) for s in scored)
    unknown_active_days = sum(1 for s in scored if s["active_days_unknown"])

    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"Total records: {len(scored)}")
    print(f"Buyer-fit buckets: {dict(buckets)}")
    print(f"Records with unknown ad_active_days: {unknown_active_days}")

    print(f"\nSample (first {sample_size}):")
    for s in scored[:sample_size]:
        print(f"\n  [{bucket_lead(s).upper()}] score={s['score']} confidence={s['confidence']}")
        print(f"    business: {s['business_name']}")
        print(f"    landing:  {s['landing_url']}")
        for reason in s["reasons"]:
            print(f"    - {reason}")
    return scored, buckets


if __name__ == "__main__":
    scraper_dir = Path(__file__).parent
    for filename, label, country in (
        ("results.json", "results.json", None),
        ("results_page_id.json", "results_page_id.json", None),
    ):
        path = scraper_dir / filename
        if not path.exists():
            continue
        with open(path) as f:
            data = json.load(f)
        run_report(data.get("results", []), country or data.get("country"), label=label)
