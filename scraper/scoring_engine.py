"""Sales-oriented scoring wrapper around the strict ICP classifier."""
from __future__ import annotations
from urllib.parse import urlparse
from difflib import SequenceMatcher
from icp_classifier import classify_icp

SOCIAL_DOMAINS = {"facebook.com", "m.facebook.com", "instagram.com", "l.instagram.com", "fb.me", "fb.watch", "tiktok.com", "www.tiktok.com"}
BROKEN_INDICATORS = {None, "", "unknown", "error"}


def get_domain(url):
    if not url or url in BROKEN_INDICATORS:
        return None
    try:
        host = urlparse(str(url)).netloc.lower().split("@")[-1].split(":")[0]
        return host[4:] if host.startswith("www.") else (host or None)
    except Exception:
        return None


def name_domain_similarity(business_name, domain):
    if not domain or not business_name:
        return 0.0
    clean_name = "".join(ch.lower() for ch in str(business_name) if ch.isalnum())
    clean_domain = "".join(ch.lower() for ch in domain.split(".")[0] if ch.isalnum())
    if not clean_name or not clean_domain:
        return 0.0
    return SequenceMatcher(None, clean_name, clean_domain).ratio()


def score_lead(ad_record):
    result = classify_icp(ad_record)
    reasons = list(result.get("reasons") or [])
    score = int(result.get("score", 0))
    status = result.get("status", "excluded")
    exclusion_reason = result.get("exclusion_reason")
    domain = get_domain(ad_record.get("landing_url"))
    business_name = ad_record.get("business_name") or ""
    target_countries = ad_record.get("target_countries") or []
    country = (ad_record.get("country") or "").upper()

    # Country is a hard outreach constraint, not a quality bonus.
    if target_countries and country not in {str(c).upper() for c in target_countries}:
        return {
            "score": 0, "confidence": "high", "reasons": [f"Country {country or '(unknown)'} is outside the approved outreach list"],
            "needs_review": False, "buyer_fit_status": "excluded",
            "icp_mismatch": True, "icp_mismatch_reason": "country_outside_target_list",
            "product_identified": bool(result.get("product_signal") == "specific_product"),
            "product_evidence": result.get("product_evidence"),
            "destination_type": result.get("destination_type"),
            "landing_opportunity": result.get("landing_opportunity"),
            "sales_reason": None,
        }

    # Resolution failure cannot become a sales-ready prospect.
    if ad_record.get("resolution_status") in ("failed", "timeout"):
        return {
            "score": 0, "confidence": "low",
            "reasons": ["Landing page could not be resolved - manual review required"],
            "needs_review": True, "buyer_fit_status": "review",
            "icp_mismatch": False, "icp_mismatch_reason": None,
            "product_identified": bool(result.get("product_signal") == "specific_product"),
            "product_evidence": result.get("product_evidence"),
            "destination_type": result.get("destination_type"),
            "landing_opportunity": result.get("landing_opportunity"),
            "sales_reason": None,
        }

    # Country is supporting evidence only after the hard country check above.
    if country and country in {str(c).upper() for c in target_countries}:
        reasons.append("Country is in the approved outreach list")

    if domain and domain not in SOCIAL_DOMAINS and business_name:
        similarity = name_domain_similarity(business_name, domain)
        # Very weak relationship is a hard mismatch. Moderate mismatch is
        # review-only, including when a candidate would otherwise qualify.
        if similarity < 0.20:
            return {
                "score": 0, "confidence": "high", "reasons": reasons + [f"Destination domain '{domain}' is not credibly related to advertiser '{business_name}'"],
                "needs_review": False, "buyer_fit_status": "excluded",
                "icp_mismatch": True, "icp_mismatch_reason": "domain_mismatch",
                "product_identified": bool(result.get("product_signal") == "specific_product"),
                "product_evidence": result.get("product_evidence"),
                "destination_type": result.get("destination_type"),
                "landing_opportunity": result.get("landing_opportunity"),
                "sales_reason": None,
            }
        if similarity < 0.40 and status == "priority":
            status = "review"
            reasons.append(f"Advertiser/domain relationship is unclear (similarity {similarity:.2f}); manual verification required")

    # Product-page advertisers are still valid $499 prospects even when Meta
    # does not expose ad-age metadata. The classifier intentionally keeps the
    # base score conservative; this evidence-specific adjustment recognizes
    # the combination of a resolved owned product page, specific product
    # identity, and a credible advertiser/domain relationship.
    if (
        status == "review"
        and result.get("product_signal") == "specific_product"
        and result.get("destination_type") == "product_page"
        and ad_record.get("is_active") is not False
        and ad_record.get("resolution_status") not in ("failed", "timeout")
        and domain
        and business_name
        and name_domain_similarity(business_name, domain) >= 0.40
        and score >= 60
    ):
        score = min(100, score + 20)
        status = "priority"
        reasons.append("Strong product-page evidence clears the sales-ready threshold despite unavailable Meta ad-age metadata")

    # Never promote based on country or domain alone. Specific product evidence
    # plus a resolved product destination is required for this recovery path.
    if status == "priority" and not result.get("product_signal") == "specific_product":
        status = "review"
        reasons.append("Specific product identity is required for sales-ready qualification")

    if status == "priority":
        confidence = "high"
        needs_review = False
        sales_reason = _build_sales_reason(ad_record, result)
    elif status == "review":
        confidence = "medium"
        needs_review = True
        sales_reason = None
    else:
        confidence = "high"
        needs_review = False
        sales_reason = None

    return {
        "score": max(0, min(100, score)),
        "confidence": confidence,
        "reasons": reasons,
        "needs_review": needs_review,
        "buyer_fit_status": status,
        "icp_mismatch": bool(result.get("exclusion_reason")) or status == "excluded",
        "icp_mismatch_reason": exclusion_reason,
        "product_identified": bool(result.get("product_signal") == "specific_product"),
        "product_evidence": result.get("product_evidence"),
        "destination_type": result.get("destination_type"),
        "landing_opportunity": result.get("landing_opportunity"),
        "sales_reason": sales_reason,
    }


def _build_sales_reason(ad_record, result):
    product = result.get("product_evidence") or "the advertised product"
    destination = result.get("destination_type") or "the current destination"
    opportunity = result.get("landing_opportunity") or "a clearer product-specific conversion path"
    days = ad_record.get("ad_active_days")
    duration = f" for about {days} days" if days is not None else ""
    return f"Active Meta ad promotes {product}{duration}; traffic goes to {destination}, creating {opportunity}. This is a credible $499 dedicated product landing-page opportunity."