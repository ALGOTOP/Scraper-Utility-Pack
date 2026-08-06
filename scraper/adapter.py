"""
adapter.py -- Phase 3 glue layer.

Converts scraper output (ScrapedAd / results.json records) into the
exact input shape scoring_engine.score_lead() expects, then runs the
batch and buckets it for reporting.

Field mapping (per Mehmood's spec):
  business_name       <- advertiser_name
  landing_url          <- final_url
  resolution_status     <- status  (mapped, see STATUS_MAP below)
  ad_active_days        <- computed from start_date at scoring time
                          (NOT stored pre-computed, since "days active"
                          goes stale the moment it's written to disk --
                          store the raw timestamp, compute the delta
                          when you actually score)
  country               <- session-level country (scraper doesn't tag
                          country per-ad; each scrape session is
                          already run against one country at a time,
                          so it's attached here rather than in the
                          scraper itself)
  target_countries      <- config value below, define once per batch

STATUS_MAP reasoning:
  scraper status 'ok' is the only case where final_url is a resolved,
  usable landing page. 'needs_review', 'blocked', and 'no_results' all
  mean the scraper itself couldn't produce a trustworthy destination
  URL for that ad -- that's exactly what scoring_engine's
  resolution_status='failed' hard-escalation path is for. There's no
  meaningful 'timeout' case at the per-ad level (that's a session-level
  concept), so it's left unmapped.
"""
from __future__ import annotations
import json
import sys
import time
from collections import Counter
from pathlib import Path

from scoring_engine import score_lead
from icp_filter import check_icp_mismatch

# --- config: define once, pass in per batch. Edit this list to match
# the real approved outreach country list before running for real. ---
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
    """Strip zero-width/BOM chars that pass a truthiness check but
    aren't a real name. scoring_engine has no such handling itself, so
    a raw '\\u200b' silently defeats name_domain_similarity's 'no name'
    branch and gets treated as if a real name were compared."""
    if not raw_name:
        return ""
    cleaned = "".join(c for c in raw_name if c not in _ZERO_WIDTH_CHARS).strip()
    return cleaned


def ad_active_days_from_start(start_date_unix):
    """Unix timestamp -> whole days since then, as of right now.
    Returns None if start_date isn't available (unknown, not zero)."""
    if not start_date_unix:
        return None
    days = (time.time() - start_date_unix) / 86400
    return max(0, int(days))


def adapt_record(scraped: dict, session_country: str,
                  target_countries: list = None) -> tuple[dict, bool]:
    """
    scraped: one raw scraper output record (library_id, advertiser_name,
    raw_href, final_url, status, source, start_date).

    Returns (ad_record_for_scoring_engine, active_days_unknown_flag).
    """
    target_countries = target_countries if target_countries is not None else TARGET_COUNTRIES
    active_days = ad_active_days_from_start(scraped.get("start_date"))
    active_days_unknown = active_days is None

    ad_record = {
        "business_name": _clean_business_name(scraped.get("advertiser_name")),
        "country": session_country,
        "landing_url": scraped.get("final_url"),
        "resolution_status": STATUS_MAP.get(scraped.get("status"), "failed"),
        # scoring_engine treats a missing key as 0 via .get(..., 0) --
        # made explicit here rather than relying on that default, since
        # "unknown" and "0 days old" are not the same thing (see caveat
        # in the run report below).
        "ad_active_days": active_days if active_days is not None else 0,
        "target_countries": target_countries,
    }
    return ad_record, active_days_unknown


def score_batch(scraped_records: list, session_country: str,
                 target_countries: list = None) -> list:
    scored = []
    for rec in scraped_records:
        ad_record, active_days_unknown = adapt_record(rec, session_country, target_countries)
        result = score_lead(ad_record)
        icp_mismatch, icp_mismatch_reason = check_icp_mismatch(
            ad_record["business_name"], ad_record["landing_url"]
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
            "reasons": result["reasons"],
            "icp_mismatch": icp_mismatch,
            "icp_mismatch_reason": icp_mismatch_reason,
        })
    return scored


def bucket_lead(s: dict) -> str:
    """
    Bucketing is a reporting convention on top of score_lead's raw
    output -- scoring_engine itself only produces score/needs_review,
    not named tiers. Derived from the score's actual achievable range:
      - needs_review flag set          -> needs_review (always wins)
      - score <= 0                     -> disqualified
          (only reachable via the -5 country mismatch; every
          country-matched record scores >= 1)
      - score 1-2                      -> cleared
          (passed, but on a single weak signal)
      - score >= 3                     -> strong_lead
    Thresholds are a starting point -- adjust once real scored volume
    shows where the useful cut points actually are.
    """
    if s["needs_review"]:
        return "needs_review"
    if s["score"] <= 0:
        return "disqualified"
    if s["score"] <= 2:
        return "cleared"
    return "strong_lead"


def run_report(scraped_records: list, session_country: str, label: str,
               target_countries: list = None, sample_size: int = 8):
    scored = score_batch(scraped_records, session_country, target_countries)
    buckets = Counter(bucket_lead(s) for s in scored)
    unknown_active_days = sum(1 for s in scored if s["active_days_unknown"])
    no_name = sum(1 for s in scored if s["business_name"] == "(no name captured)")

    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(f"Total records: {len(scored)}")
    print(f"Bucket counts: {dict(buckets)}")
    print(f"Records with unknown ad_active_days (defaulted to 0): {unknown_active_days}")
    print(f"Records with no advertiser_name captured: {no_name}")

    print(f"\nSample (first {sample_size}):")
    for s in scored[:sample_size]:
        bucket = bucket_lead(s)
        flag = " [active_days unknown->0]" if s["active_days_unknown"] else ""
        print(f"\n  [{bucket.upper()}] score={s['score']} confidence={s['confidence']} "
              f"source={s['source']}{flag}")
        print(f"    business: {s['business_name']}")
        print(f"    landing:  {s['landing_url']}")
        for r in s["reasons"]:
            print(f"    - {r}")
    return scored, buckets


if __name__ == "__main__":
    scraper_dir = Path(__file__).parent

    # --- Run 1: real production data, results.json (keyword search,
    # entirely DOM-fallback in this file) ---
    with open(scraper_dir / "results.json") as f:
        data1 = json.load(f)
    run_report(data1["results"], data1.get("country"),
               label="results.json (keyword search, real scraper output)")

    # --- Run 2: real production data, results_page_id.json (page-id
    # search, also entirely DOM-fallback) ---
    with open(scraper_dir / "results_page_id.json") as f:
        data2 = json.load(f)
    run_report(data2["results"], data2.get("country"),
               label="results_page_id.json (page-id search, real scraper output)")

    # --- Run 3: real captured GraphQL payload, parsed through the
    # actual scraper.py parser -- shown separately because it's the
    # only real data source with both advertiser_name AND start_date
    # populated, so it demonstrates the full field set the adapter
    # was built for. ---
    sys.path.insert(0, str(scraper_dir))
    from scraper import _parse_graphql_payload

    fixture_path = scraper_dir.parent / "attached_assets" / "captured_payload_1784971618300.json"
    with open(fixture_path) as f:
        raw = json.load(f)
    graphql_ads = []
    for item in raw:
        payload = item.get("payload", item)
        graphql_ads.extend(_parse_graphql_payload(payload))
    graphql_records = [
        {
            "library_id": ad.library_id,
            "advertiser_name": ad.advertiser_name,
            "raw_href": ad.raw_href,
            "final_url": ad.final_url,
            "status": ad.status,
            "source": ad.source,
            "start_date": ad.start_date,
        }
        for ad in graphql_ads
    ]
    run_report(graphql_records, "US",
               label="captured_payload.json (real GraphQL capture, full fields)")
