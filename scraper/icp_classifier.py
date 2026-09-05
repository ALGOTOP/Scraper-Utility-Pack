"""
ICP classifier for the $499 dedicated product landing-page offer.

The goal is not to decide whether a business is "good" in general. It is to
answer a much narrower sales question:

    "Would this advertiser be a realistic prospect for a $499 product-specific
     landing page that improves the conversion path from an existing ad?"

This module is intentionally deterministic and dependency-free. It combines
signals already available in Meta Ad Library responses:
- advertiser/page name
- ad body/title/caption
- CTA
- page categories
- page like count
- destination URL
- ad activity / platforms

Hard exclusions are conservative. Ambiguous cases become `review` rather than
being silently discarded.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

SOCIAL_DOMAINS = {
    "facebook.com", "m.facebook.com", "instagram.com", "l.instagram.com",
    "fb.me", "fb.watch", "tiktok.com", "www.tiktok.com",
}

APP_STORE_DOMAINS = {
    "itunes.apple.com", "apps.apple.com", "play.google.com",
}

MARKETPLACE_DOMAINS = {
    "amazon.com", "amazon.co.uk", "amazon.ca", "amazon.com.au",
    "walmart.com", "ebay.com", "etsy.com", "temu.com", "aliexpress.com",
    "alibaba.com", "shein.com", "wish.com", "wayfair.com",
}

# Known enterprise/marketplace/platform names. Keep this relatively small;
# the positive fit model below does most of the qualification work.
LARGE_OR_NON_BUYER_NAME_PATTERNS = [
    r"\bamazon\b", r"\bwalmart\b", r"\btarget\b", r"\bcostco\b",
    r"\bhome depot\b", r"\blowe'?s\b", r"\bwayfair\b",
    r"\bebay\b", r"\betsy\b", r"\baliexpress\b", r"\balibaba\b",
    r"\btemu\b", r"\bshein\b", r"\bshopify\b", r"\bmeta\b",
    r"\bgoogle\b", r"\bmicrosoft\b", r"\badobe\b", r"\bcanva\b",
    r"\bhubspot\b", r"\bsemrush\b", r"\bmailchimp\b",
]

NON_BUYER_PATTERNS = [
    r"\bmarketing agency\b", r"\bdigital agency\b", r"\bad agency\b",
    r"\bmarketing company\b", r"\bmedia agency\b", r"\bcreative agency\b",
    r"\badvertising agency\b", r"\bperformance marketing\b",
    r"\bseo agency\b", r"\bsocial media agency\b", r"\bweb design agency\b",
    r"\bcrm\b", r"\bsaas\b", r"\bsoftware\b", r"\bplatform\b",
    r"\bapp\b", r"\bmobile app\b", r"\bmarketplace\b",
    r"\baffiliate\b", r"\blead generation\b", r"\blead gen\b",
]

NON_PRODUCT_TEXT_PATTERNS = [
    r"\bbook a call\b", r"\bbook a discovery call\b", r"\bfree consultation\b",
    r"\bmarketing services?\b", r"\bad management\b", r"\bmedia buying\b",
    r"\bseo services?\b", r"\bweb design services?\b", r"\bcoaching program\b",
    r"\bconsulting services?\b", r"\bagency services?\b", r"\bfor our clients\b",
    r"\bour clients\b", r"\bwe manage \S+ (?:in )?monthly ad spend\b",
    r"\bmanage (?:your|their) ads\b", r"\bmanage .*monthly ad spend\b", r"\bfull amazon team\b", r"\bwork with brands\b",
    r"\bdiscovery call\b", r"\bclient acquisition\b",
]

PRODUCT_TEXT_PATTERNS = [
    r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b",
    r"\badd-to-cart\b", r"\bfree shipping\b", r"\bshipping\b",
    r"\bnew drop\b", r"\bnew collection\b", r"\bcollection\b",
    r"\bproduct\b", r"\bshop\b", r"\bstore\b", r"\bsale\b",
    r"\bdiscount\b", r"\b\d+% off\b", r"\bbundle\b", r"\bset\b",
    r"\bsize(s)?\b", r"\bcolors?\b", r"\bvariants?\b",
    r"\bingredients?\b", r"\bformula\b", r"\bserum\b", r"\bcream\b",
    r"\bshampoo\b", r"\bsupplement\b", r"\bvitamins?\b", r"\bprotein\b",
    r"\bskincare\b", r"\bmakeup\b", r"\bcosmetics?\b", r"\bapparel\b",
    r"\bjewelry\b", r"\bclothing\b", r"\bshoes\b", r"\bbags?\b",
    r"\bpet food\b", r"\bpet treats?\b", r"\bcoffee\b", r"\bsnacks?\b",
]

AGENCY_SIGNAL_PATTERNS = [
    r"\bour clients\b", r"\bwe build\b", r"\bwe manage\b",
    r"\bmonthly ad spend\b", r"\baverage roas\b", r"\bfree .* audit\b",
    r"\bdiscovery call\b", r"\bppc\b", r"\bseo\b", r"\basins?\b",
    r"\bfor \d+\+ brands\b",
]

STRONG_PRODUCT_PATTERNS = [
    r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b",
    r"\bfree shipping\b", r"\bnew collection\b", r"\bnew drop\b",
    r"\b\d+% off\b", r"\bdiscount\b", r"\bbundle\b",
    r"\bserum\b", r"\bcream\b", r"\bshampoo\b", r"\bsupplement\b",
    r"\bskincare\b", r"\bmakeup\b", r"\bcosmetics?\b", r"\bclothing\b",
    r"\bjewelry\b", r"\bshoes\b", r"\bbags?\b", r"\bcoffee\b",
]

# Product categories that are especially compatible with a dedicated product
# landing page. This is a positive list, not a requirement: unknown categories
# can still qualify if the ad copy strongly indicates a product purchase.
PRODUCT_CATEGORY_TERMS = {
    "shopping & retail", "retail", "e-commerce", "ecommerce", "clothing",
    "apparel", "beauty", "cosmetics", "health/beauty", "health & beauty",
    "food & beverage", "food", "jewelry", "home decor", "home goods",
    "baby goods", "pet supplies", "sports & recreation", "fitness",
    "consumer goods", "product/service", "brand",
}


def _domain(url):
    if not url:
        return None
    try:
        host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return None


def _root_domain(url):
    host = _domain(url)
    if not host:
        return None
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _text(*values):
    chunks = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            chunks.extend(str(v) for v in value if v is not None)
        elif isinstance(value, dict):
            # Meta body can be either a dict with text or a plain string.
            if "text" in value:
                chunks.append(str(value.get("text") or ""))
            else:
                chunks.extend(str(v) for v in value.values() if v is not None)
        else:
            chunks.append(str(value))
    return " ".join(chunks).lower().strip()


def _matches(text, patterns):
    return [p for p in patterns if re.search(p, text, flags=re.I)]


def _is_social(domain):
    return domain in SOCIAL_DOMAINS or any(domain == d or domain.endswith("." + d) for d in SOCIAL_DOMAINS if domain)


def _is_marketplace(domain):
    return domain in MARKETPLACE_DOMAINS or any(domain == d or domain.endswith("." + d) for d in MARKETPLACE_DOMAINS if domain)


def _is_app_store(domain):
    return domain in APP_STORE_DOMAINS


def _normalise_categories(categories):
    if not categories:
        return []
    if isinstance(categories, str):
        return [categories.strip().lower()]
    return [str(c).strip().lower() for c in categories if c]


def _looks_like_product_business(name, ad_text, categories):
    category_text = " ".join(categories)
    product_hits = _matches(ad_text, PRODUCT_TEXT_PATTERNS)
    category_hits = [c for c in categories if c in PRODUCT_CATEGORY_TERMS or any(t in c for t in PRODUCT_CATEGORY_TERMS)]

    # Strong commerce language is enough even when Meta's category is generic.
    strong_commerce = any(re.search(p, ad_text, re.I) for p in PRODUCT_TEXT_PATTERNS[:18])
    return bool(product_hits or category_hits or strong_commerce), product_hits, category_hits


def _destination_type(domain, url):
    if not domain:
        return "unknown"
    if _is_social(domain):
        if "instagram" in domain:
            return "instagram"
        if "facebook" in domain or domain == "fb.me":
            return "facebook"
        return "social"
    if _is_app_store(domain):
        return "app_store"
    if _is_marketplace(domain):
        return "marketplace"

    path = (urlparse(url).path if url else "").lower()
    query = (urlparse(url).query if url else "").lower()
    full = f"{path}?{query}"
    if any(x in full for x in ("/products/", "/product/", "/p/", "product=")):
        return "product_page"
    if any(x in full for x in ("/collections/", "/category/", "/shop/", "/catalog")):
        return "collection_page"
    if any(x in full for x in ("/landing", "/lp/", "/pages/", "/offer", "/promo")):
        return "landing_page"
    return "owned_site"


def classify_icp(ad_record):
    """
    Return a structured qualification result.

    Keys:
      qualified: bool
      status: 'priority' | 'review' | 'excluded'
      score: 0-100
      destination_type
      business_type
      reasons: list[str]
      exclusion_reason: str | None
    """
    name = (ad_record.get("business_name") or "").strip()
    url = ad_record.get("landing_url")
    domain = _domain(url)
    root_domain = _root_domain(url)
    body = ad_record.get("ad_body") or ad_record.get("body")
    title = ad_record.get("ad_title") or ad_record.get("title")
    caption = ad_record.get("caption")
    cta_text = ad_record.get("cta_text")
    cta_type = ad_record.get("cta_type")
    categories = _normalise_categories(ad_record.get("page_categories") or ad_record.get("categories"))
    likes = ad_record.get("page_like_count")

    ad_text = _text(body, title, caption, cta_text, cta_type)
    identity_text = _text(name, categories, domain)
    combined = _text(identity_text, ad_text)
    destination = _destination_type(domain, url)
    reasons = []
    score = 0

    # --- Hard exclusions ---
    if destination == "app_store":
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "app_or_software",
                "reasons": ["Ad sends traffic to an app-store listing; no product landing-page opportunity"],
                "exclusion_reason": "app_store"}

    if destination == "marketplace":
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "marketplace",
                "reasons": [f"Destination is a marketplace ({root_domain or domain}), not a prospect-owned product funnel"],
                "exclusion_reason": "marketplace"}

    if _matches(identity_text, LARGE_OR_NON_BUYER_NAME_PATTERNS):
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "enterprise_or_platform",
                "reasons": ["Advertiser appears to be a large platform/marketplace/enterprise buyer outside the $499 target"],
                "exclusion_reason": "large_or_non_buyer"}

    if _matches(identity_text, NON_BUYER_PATTERNS):
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "agency_or_software",
                "reasons": ["Advertiser appears to be an agency, software/platform, lead-gen business, or other non-target buyer"],
                "exclusion_reason": "non_buyer_business_type"}

    service_category_terms = ("dating service", "coach", "coaching", "consultant", "consulting", "professional service")
    service_category = any(any(term in category for term in service_category_terms) for category in categories)
    service_hits = _matches(ad_text, NON_PRODUCT_TEXT_PATTERNS)
    if service_category and len(service_hits) >= 1:
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "service_business",
                "reasons": ["Advertiser appears to sell a service rather than a product suited to the $499 offer"],
                "exclusion_reason": "service_business"}

    # Multiple service signals are strong evidence that the advertiser is
    # selling a service/funnel rather than a product, even if Meta's category
    # is generic. Requiring two signals avoids rejecting ordinary product copy
    # that happens to mention a consultation or client.
    agency_hits = _matches(ad_text, AGENCY_SIGNAL_PATTERNS)
    if (len(service_hits) >= 2 or len(agency_hits) >= 2) and not _matches(ad_text, STRONG_PRODUCT_PATTERNS):
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "service_business",
                "reasons": ["Ad contains multiple service/agency signals and no meaningful product-commerce signal"],
                "exclusion_reason": "service_business"}

    # Very large pages are usually a poor $499 prospect. Do not reject local
    # brands purely on follower count unless it is clearly enterprise-scale.
    try:
        likes_int = int(likes) if likes is not None else None
    except (TypeError, ValueError):
        likes_int = None
    if likes_int is not None and likes_int >= 1000000:
        return {"qualified": False, "status": "excluded", "score": 0,
                "destination_type": destination, "business_type": "enterprise_or_platform",
                "reasons": [f"Page has {likes_int:,} likes; business appears too large for the $499 offer"],
                "exclusion_reason": "very_large_page"}

    # --- Business/product fit ---
    looks_product, product_hits, category_hits = _looks_like_product_business(name, ad_text, categories)
    non_product_hits = _matches(ad_text, NON_PRODUCT_TEXT_PATTERNS)

    if not looks_product:
        # Clear service identities should not become prospects merely because
        # their ad happens to contain generic commercial words.
        service_name_terms = ("coaching", "coach", "consulting", "consultant", "agency", "digital marketing", "marketing")
        if any(term in name.lower() for term in service_name_terms):
            return {"qualified": False, "status": "excluded", "score": 0,
                    "destination_type": destination, "business_type": "service_business",
                    "reasons": ["Advertiser name strongly indicates a service/agency business rather than a product seller"],
                    "exclusion_reason": "service_business"}

        # A social destination can still be useful, but without any product
        # signal we do not want to pitch a product landing page blindly.
        if destination in {"instagram", "facebook", "social"}:
            return {"qualified": False, "status": "review", "score": 35,
                    "destination_type": destination, "business_type": "unknown",
                    "reasons": ["Social destination is promising, but the ad does not provide enough product-buying evidence"],
                    "exclusion_reason": None}
        return {"qualified": False, "status": "review", "score": 35,
                "destination_type": destination, "business_type": "unknown",
                "reasons": ["Could not establish a purchasable product from the available ad data; manual review required"],
                "exclusion_reason": None}

    score += 35
    reasons.append("Product/business fit detected")

    if product_hits:
        score += min(15, len(product_hits) * 3)
        reasons.append("Ad copy contains direct product/commerce signals")

    if category_hits:
        score += 10
        reasons.append("Meta page category supports a product/retail business")

    if destination in {"instagram", "facebook", "social"}:
        score += 25
        reasons.append("Ad currently sends traffic to a social profile/page — strong landing-page opportunity")
    elif destination == "owned_site":
        score += 15
        reasons.append("Ad sends traffic to an owned site, but not an obvious product-specific page")
    elif destination == "collection_page":
        score += 18
        reasons.append("Ad sends traffic to a collection/category page — dedicated product page is a clear improvement opportunity")
    elif destination == "product_page":
        score += 7
        reasons.append("Ad already reaches a product page — landing-page opportunity exists but is less obvious")
    elif destination == "landing_page":
        score += 3
        reasons.append("Ad already uses a landing/offer page — lower-priority opportunity")
    else:
        score += 5
        reasons.append("Destination could not be classified precisely")

    # Active ad duration is a useful intent/spend proxy.
    active_days = ad_record.get("ad_active_days")
    if active_days is not None:
        try:
            days = int(active_days)
        except (TypeError, ValueError):
            days = 0
        if days >= 30:
            score += 8
            reasons.append(f"Ad has been active about {days} days — strong evidence of ongoing acquisition spend")
        elif days >= 14:
            score += 5
            reasons.append(f"Ad has been active about {days} days — evidence of ongoing acquisition spend")
        elif days >= 7:
            score += 2
            reasons.append(f"Ad has been active about {days} days")

    # CTA is a useful purchase-intent signal, but do not over-weight it because
    # Meta localizes CTA text and not every ad exposes it.
    purchase_ctas = {"shop now", "buy now", "order now", "get offer", "get yours", "learn more"}
    if (cta_text or "").strip().lower() in purchase_ctas:
        score += 5
        reasons.append(f"CTA '{cta_text}' indicates commercial intent")

    if non_product_hits and not product_hits:
        score -= 15
        reasons.append("Ad copy contains service/consulting language that weakens product-fit confidence")

    # Size signal: enough maturity to spend $499, but not obviously enormous.
    if likes_int is not None:
        if 100 <= likes_int <= 100000:
            score += 5
            reasons.append(f"Page size ({likes_int:,} likes) is consistent with a small/mid-market advertiser")
        elif likes_int < 100:
            score -= 5
            reasons.append("Very small page footprint — purchasing ability is less certain")
        elif likes_int > 250000:
            score -= 8
            reasons.append(f"Large page footprint ({likes_int:,} likes) lowers fit for the $499 offer")

    # Unknown destination / unresolved URL means we cannot confidently sell the
    # opportunity. Keep it for review rather than calling it a good lead.
    if not domain:
        score = min(score, 59)
        reasons.append("Destination URL is missing or unresolved — manual review needed")
        return {"qualified": False, "status": "review", "score": max(0, min(100, score)),
                "destination_type": "unknown", "business_type": "product_business",
                "reasons": reasons, "exclusion_reason": None}

    score = max(0, min(100, score))

    # High = directly pitchable. Medium = potentially useful but inspect first.
    if score >= 70:
        status = "priority"
        qualified = True
    elif score >= 50:
        status = "review"
        qualified = False
        reasons.append("Promising but below the automatic priority threshold")
    else:
        status = "excluded"
        qualified = False
        reasons.append("Overall buyer-fit is too weak for the $499 offer")

    return {
        "qualified": qualified,
        "status": status,
        "score": score,
        "destination_type": destination,
        "business_type": "product_business",
        "reasons": reasons,
        "exclusion_reason": None if qualified or status == "review" else "low_buyer_fit",
    }
