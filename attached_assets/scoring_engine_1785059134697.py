"""
Lead Scoring Engine
-------------------
Takes a scraped ad record (from Meta Ad Library + Playwright landing page
resolution) and produces a lead score + confidence level.

Design principle: deterministic rules handle every case for free, no AI
calls. Genuinely ambiguous cases (unclear domain match, failed scrapes)
are flagged as "needs_review" instead of being force-scored, and show up
in a separate manual review tab in the interface. This keeps the clear-cut
majority fully automated while protecting accuracy on the fuzzy cases,
at zero cost.
"""

from urllib.parse import urlparse
from difflib import SequenceMatcher

SOCIAL_DOMAINS = {
    "facebook.com", "m.facebook.com", "instagram.com", "l.instagram.com",
    "fb.me", "fb.watch"
}

BROKEN_INDICATORS = {None, "", "unknown", "error"}


def get_domain(url):
    """Extract a clean root domain from a URL. Returns None if unparseable."""
    if not url or url in BROKEN_INDICATORS:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        netloc = netloc.replace("www.", "")
        return netloc if netloc else None
    except Exception:
        return None


def name_domain_similarity(business_name, domain):
    """
    Rough similarity between a business's name and their domain.
    Used to flag "domain doesn't match business name" cases.
    Returns a 0-1 score.
    """
    if not domain or not business_name:
        return 0.0
    clean_name = "".join(ch.lower() for ch in business_name if ch.isalnum())
    clean_domain = "".join(ch.lower() for ch in domain.split(".")[0] if ch.isalnum())
    if not clean_name or not clean_domain:
        return 0.0
    return SequenceMatcher(None, clean_name, clean_domain).ratio()


def score_lead(ad_record):
    """
    ad_record expected fields:
      - business_name: str
      - country: str
      - landing_url: str or None
      - resolution_status: "resolved" | "failed" | "timeout"
      - ad_active_days: int (how long the ad has been running)
      - target_countries: list[str] (your approved outreach countries)

    Returns dict: {score, confidence, reasons, needs_review}
    """
    reasons = []
    score = 0
    needs_review = False

    domain = get_domain(ad_record.get("landing_url"))
    resolution_status = ad_record.get("resolution_status")

    # --- Hard disqualifiers / escalations first ---
    if resolution_status in ("failed", "timeout"):
        return {
            "score": 0,
            "confidence": "low",
            "reasons": ["Landing page could not be resolved - scrape failed"],
            "needs_review": True,
        }

    # --- Rule 1: destination is a social page, not an owned domain ---
    if domain in SOCIAL_DOMAINS:
        score += 3
        reasons.append("Ad destination is a Facebook/Instagram page, not a real site (+3)")
    elif domain is None:
        score += 0
        reasons.append("Could not determine destination domain")
        needs_review = True
    else:
        # --- Rule 2: domain doesn't match business name ---
        similarity = name_domain_similarity(ad_record.get("business_name", ""), domain)
        if similarity < 0.35:
            score += 2
            reasons.append(f"Domain '{domain}' doesn't clearly match business name (+2)")
        elif similarity < 0.6:
            # Ambiguous middle ground - not confident either way
            needs_review = True
            reasons.append(f"Domain match to business name is unclear (similarity {similarity:.2f}) - needs review")

    # --- Rule 3: ad has been running a while = real ongoing spend ---
    ad_active_days = ad_record.get("ad_active_days", 0)
    if ad_active_days >= 14:
        score += 1
        reasons.append(f"Ad has been active {ad_active_days} days - real ongoing spend (+1)")

    # --- Rule 4: country matches target list ---
    target_countries = ad_record.get("target_countries", [])
    if ad_record.get("country") in target_countries:
        score += 1
        reasons.append("Country matches target outreach list (+1)")
    else:
        score -= 5
        reasons.append("Country NOT in target outreach list (-5, effectively disqualifies)")

    confidence = "low" if needs_review else "high"

    return {
        "score": score,
        "confidence": confidence,
        "reasons": reasons,
        "needs_review": needs_review,
    }


if __name__ == "__main__":
    # --- Test cases to verify the logic before handing this to Replit ---
    test_cases = [
        {
            "business_name": "Glow Organic Lipstick Co",
            "country": "GB",
            "landing_url": "https://www.instagram.com/gloworganiclipstick",
            "resolution_status": "resolved",
            "ad_active_days": 21,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
        },
        {
            "business_name": "Bright Smile Dental",
            "country": "AU",
            "landing_url": "https://brightsmiledental.com.au/",
            "resolution_status": "resolved",
            "ad_active_days": 30,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
        },
        {
            "business_name": "Bright Smile Dental",
            "country": "AU",
            "landing_url": "https://xz9promo-page.net/offer",
            "resolution_status": "resolved",
            "ad_active_days": 5,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
        },
        {
            "business_name": "Local Cafe",
            "country": "PK",
            "landing_url": "https://facebook.com/localcafe",
            "resolution_status": "resolved",
            "ad_active_days": 10,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
        },
        {
            "business_name": "Some Brand",
            "country": "US",
            "landing_url": None,
            "resolution_status": "failed",
            "ad_active_days": 0,
            "target_countries": ["GB", "AU", "US", "CA", "IE"],
        },
    ]

    for i, case in enumerate(test_cases, 1):
        result = score_lead(case)
        print(f"\n--- Test case {i}: {case['business_name']} ---")
        print(f"Landing URL: {case['landing_url']}")
        print(f"Score: {result['score']} | Confidence: {result['confidence']} | Needs review: {result['needs_review']}")
        for r in result["reasons"]:
            print(f"  - {r}")
        if result["needs_review"]:
            print("  >> Flagged for manual review (appears in the 'Needs Review' tab, not auto-scored)")
