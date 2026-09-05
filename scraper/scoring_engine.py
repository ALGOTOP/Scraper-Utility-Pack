"""
Buyer-fit scoring engine for the $499 dedicated product landing-page offer.

This is deliberately not a generic "lead quality" score. It measures how
strongly a Meta advertiser looks like a realistic buyer for:

    "We build a dedicated landing page for the product you're already
     advertising, improving the conversion path without increasing ad spend."

The actual qualification model lives in icp_classifier.py. This module keeps
the public score_lead() interface used by the rest of the application and
adds the country/resolution safeguards that belong at scoring time.
"""
from __future__ import annotations

from urllib.parse import urlparse
from difflib import SequenceMatcher

from icp_classifier import classify_icp

SOCIAL_DOMAINS = {
    "facebook.com", "m.facebook.com", "instagram.com", "l.instagram.com",
    "fb.me", "fb.watch", "tiktok.com", "www.tiktok.com",
}
BROKEN_INDICATORS = {None, "", "unknown", "error"}


def get_domain(url):
    """Extract a clean host from a URL."""
    if not url or url in BROKEN_INDICATORS:
        return None
    try:
        netloc = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
        return netloc[4:] if netloc.startswith("www.") else (netloc or None)
    except Exception:
        return None


def name_domain_similarity(business_name, domain):
    if not domain or not business_name:
        return 0.0
    clean_name = "".join(ch.lower() for ch in business_name if ch.isalnum())
    clean_domain = "".join(ch.lower() for ch in domain.split(".")[0] if ch.isalnum())
    if not clean_name or not clean_domain:
        return 0.0
    return SequenceMatcher(None, clean_name, clean_domain).ratio()


def score_lead(ad_record):
    """
    Expected fields include the old scorer fields plus rich Meta fields:
      business_name, country, landing_url, resolution_status,
      ad_active_days, target_countries,
      ad_body, ad_title, caption, cta_text, cta_type,
      page_categories, page_like_count, is_active

    Returns:
      score: 0-100
      confidence: high/medium/low
      needs_review: bool
      reasons: list[str]
      buyer_fit_status: priority/review/excluded
      icp_mismatch: bool
      icp_mismatch_reason: str | None
    """
    reasons = []
    resolution_status = ad_record.get("resolution_status")
    target_countries = ad_record.get("target_countries") or []
    country = (ad_record.get("country") or "").upper()

    # A failed resolution means we cannot responsibly determine the funnel
    # opportunity. It is reviewable, never a priority lead.
    if resolution_status in ("failed", "timeout"):
        return {
            "score": 0,
            "confidence": "low",
            "reasons": ["Landing page could not be resolved - manual review required"],
            "needs_review": True,
            "buyer_fit_status": "review",
            "icp_mismatch": False,
            "icp_mismatch_reason": None,
        }

    # Country is a hard outreach constraint, because there is no value in
    # surfacing an otherwise good prospect in a country the user does not want.
    if target_countries and country not in {str(c).upper() for c in target_countries}:
        return {
            "score": 0,
            "confidence": "high",
            "reasons": [f"Country {country or '(unknown)'} is outside the approved outreach list"],
            "needs_review": False,
            "buyer_fit_status": "excluded",
            "icp_mismatch": True,
            "icp_mismatch_reason": "country_outside_target_list",
        }

    result = classify_icp(ad_record)
    score = int(result.get("score", 0))
    reasons.extend(result.get("reasons") or [])

    if country and country in {str(c).upper() for c in target_countries}:
        score = min(100, score + 2)
        reasons.append("Country is in the approved outreach list (+2)")

    # A long-running ad is evidence that the advertiser is actively acquiring
    # traffic, but the classifier already accounts for this. We intentionally
    # do not add another duplicate duration bonus here.
    status = result.get("status")
    if status == "priority":
        confidence = "high"
        needs_review = False
    elif status == "review":
        confidence = "medium"
        needs_review = True
    else:
        confidence = "high"
        needs_review = False

    # If the business/domain relationship is ambiguous, lower confidence rather
    # than inventing certainty. This is especially useful for branded stores,
    # tracking domains, and founders whose company name differs from the URL.
    domain = get_domain(ad_record.get("landing_url"))
    business_name = ad_record.get("business_name") or ""
    if domain and domain not in SOCIAL_DOMAINS:
        similarity = name_domain_similarity(business_name, domain)
        if business_name and similarity < 0.25:
            reasons.append(f"Destination domain '{domain}' is weakly related to advertiser name")
            if status == "priority":
                status = "review"
                needs_review = True
                confidence = "medium"
        elif business_name and similarity < 0.45:
            reasons.append(f"Advertiser/domain relationship is somewhat unclear (similarity {similarity:.2f})")
            if status == "priority":
                status = "review"
                needs_review = True
                confidence = "medium"

    # Re-cap after the country bonus / domain review adjustments.
    score = max(0, min(100, score))

    return {
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "needs_review": needs_review,
        "buyer_fit_status": status,
        "icp_mismatch": bool(result.get("exclusion_reason")) or status == "excluded",
        "icp_mismatch_reason": result.get("exclusion_reason"),
    }


if __name__ == "__main__":
    test_cases = [
        {
            "business_name": "Glow Organic Lipstick Co",
            "country": "GB",
            "landing_url": "https://www.instagram.com/gloworganiclipstick",
            "resolution_status": "resolved",
            "ad_active_days": 21,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
            "ad_body": "Shop our new lipstick collection. Free shipping. Buy now.",
            "ad_title": "New lipstick shades",
            "cta_text": "Shop Now",
            "page_categories": ["Beauty"],
            "page_like_count": 12000,
        },
        {
            "business_name": "Amazon",
            "country": "US",
            "landing_url": "https://www.amazon.com/dp/example",
            "resolution_status": "resolved",
            "ad_active_days": 30,
            "target_countries": ["US"],
            "ad_body": "Shop beauty products.",
            "page_categories": ["Shopping & Retail"],
            "page_like_count": 10000000,
        },
    ]
    for case in test_cases:
        result = score_lead(case)
        print(f"\n{case['business_name']}: {result}")
