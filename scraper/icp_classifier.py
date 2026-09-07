"""Strict buyer-fit classifier for the $499 product landing-page offer.

This module is intentionally conservative. A record is not a prospect merely
because it contains words such as "shop", "sale", or "product". To qualify as
an outreach prospect we need evidence for the actual sales premise:

    an active Meta advertiser + a real product business + a specific product
    being promoted + a credible landing-page opportunity + a business that is
    plausible to contact for a $499 implementation.

The classifier uses only fields already captured by the scraper. Search terms
are discovery context and are deliberately NOT treated as proof of product
identity.
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

LARGE_OR_NON_BUYER_NAME_PATTERNS = [
    r"\bamazon\b", r"\bwalmart\b", r"\btarget\b", r"\bcostco\b",
    r"\bhome depot\b", r"\blowe'?s\b", r"\bwayfair\b", r"\bebay\b",
    r"\betsy\b", r"\baliexpress\b", r"\balibaba\b", r"\btemu\b",
    r"\bshein\b", r"\bshopify\b", r"\bmeta\b", r"\bgoogle\b",
    r"\bmicrosoft\b", r"\badobe\b", r"\bcanva\b", r"\bhubspot\b",
    r"\bsemrush\b", r"\bmailchimp\b",
]

NON_BUYER_PATTERNS = [
    r"\bmarketing agency\b", r"\bdigital agency\b", r"\bad agency\b",
    r"\bmarketing company\b", r"\bmedia agency\b", r"\bcreative agency\b",
    r"\badvertising agency\b", r"\bperformance marketing\b",
    r"\bseo agency\b", r"\bsocial media agency\b", r"\bweb design agency\b",
    r"\bcrm\b", r"\bsaas\b", r"\bsoftware\b", r"\bplatform\b",
    r"\bmobile app\b", r"\bmarketplace\b", r"\baffiliate\b",
    r"\blead generation\b", r"\blead gen\b", r"\bdropshipping\b",
]

SERVICE_PATTERNS = [
    r"\bbook a call\b", r"\bbook a discovery call\b", r"\bfree consultation\b",
    r"\bmarketing services?\b", r"\bad management\b", r"\bmedia buying\b",
    r"\bseo services?\b", r"\bweb design services?\b", r"\bcoaching program\b",
    r"\bconsulting services?\b", r"\bagency services?\b", r"\bclient acquisition\b",
    r"\bmonthly ad spend\b", r"\baverage roas\b", r"\bfor \d+\+ brands\b",
    r"\bour clients\b", r"\bwork with brands\b", r"\bwe manage\b",
]

# These are intentionally WEAK signals. They can support commerce intent but
# never establish that a specific product is being advertised.
TRANSACTION_PATTERNS = [
    r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b",
    r"\bfree shipping\b", r"\bshipping\b", r"\bnew collection\b",
    r"\bnew drop\b", r"\bsale\b", r"\bdiscount\b", r"\b\d+% off\b",
    r"\bbundle\b", r"\bget yours\b", r"\bget offer\b", r"\bshop\b",
]

# Product identity is the critical gate. These patterns describe concrete
# product classes or a concrete product + modifier, not generic commerce.
SPECIFIC_PRODUCT_PATTERNS = [
    # Beauty / skincare
    r"\b(?:vitamin\s*c|retinol|hyaluronic|niacinamide|salicylic|glycolic)\b.{0,40}\b(?:serum|cream|cleanser|toner|moisturizer|lotion)\b",
    r"\b(?:serum|cream|cleanser|toner|moisturizer|lotion|face wash|facial oil)\b",
    r"\b(?:spf\s*\d+|sunscreen|sunblock|sun screen)\b",
    r"\b(?:lip balm|lip gloss|lipstick|mascara|foundation|concealer|blush|eyeliner)\b",
    r"\b(?:shampoo|conditioner|hair mask|hair oil|body wash|deodorant)\b",
    # Apparel / accessories
    r"\b(?:running|hiking|trail|basketball|tennis|training)\s+shoes\b",
    r"\b(?:sneakers?|boots?|sandals?|loafers?)\b",
    r"\b(?:hoodie|sweatshirt|jacket|coat|leggings|joggers|dress|jeans|t-shirt|shirt)\b",
    r"\b(?:crossbody|tote|backpack|duffel|handbag|wallet|purse)\b",
    r"\b(?:necklace|bracelet|earrings?|ring|pendant|watch)\b",
    # Food / supplements
    r"\b(?:protein powder|protein shake|creatine|electrolytes?|pre-workout|post-workout)\b",
    r"\b(?:vitamins?|probiotics?|collagen|omega[- ]?3|fish oil)\b",
    r"\b(?:coffee beans?|ground coffee|tea|matcha|snack|granola|chocolate)\b",
    # Home / pet / other consumer products
    r"\b(?:dog|cat)\s+(?:food|treats?|supplements?)\b",
    r"\b(?:candle|diffuser|bedding|duvet|pillow|mattress|lamp|rug|blanket)\b",
    r"\b(?:water bottle|tumbler|backpack|phone case|air purifier|vacuum)\b",
    r"\b(?:baby carrier|diaper bag|baby monitor|stroller|toys?)\b",
    # SKU/model-style product naming is strong evidence.
    r"\b(?:model|sku|style)\s*[#:-]?\s*[a-z0-9-]{2,}\b",
]

# A product noun on its own is useful but weaker than a clearly identified
# product. These signals can qualify only when paired with other evidence.
WEAK_PRODUCT_PATTERNS = [
    r"\bskincare\b", r"\bmakeup\b", r"\bcosmetics?\b", r"\bapparel\b",
    r"\bclothing\b", r"\bjewelry\b", r"\bfootwear\b", r"\baccessories\b",
    r"\bpet supplies\b", r"\bhome goods\b", r"\bhome decor\b",
    r"\bconsumer goods\b", r"\bproducts?\b",
]

PRODUCT_CATEGORY_TERMS = {
    "shopping & retail", "retail", "e-commerce", "ecommerce", "clothing",
    "apparel", "beauty", "cosmetics", "health/beauty", "health & beauty",
    "food & beverage", "food", "jewelry", "home decor", "home goods",
    "baby goods", "pet supplies", "sports & recreation", "fitness",
    "consumer goods", "product/service", "brand",
}

PURCHASE_CTA_PATTERNS = [
    r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b",
    r"\bget yours\b", r"\bget offer\b",
]


def _domain(url):
    if not url:
        return None
    try:
        host = urlparse(str(url)).netloc.lower().split("@")[-1].split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return None


def _root_domain(url):
    host = _domain(url)
    if not host:
        return None
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _text(*values):
    chunks = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            chunks.extend(str(v) for v in value if v is not None)
        elif isinstance(value, dict):
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
    if not domain:
        return False
    return domain in SOCIAL_DOMAINS or any(domain.endswith("." + d) for d in SOCIAL_DOMAINS)


def _is_marketplace(domain):
    if not domain:
        return False
    return domain in MARKETPLACE_DOMAINS or any(domain.endswith("." + d) for d in MARKETPLACE_DOMAINS)


def _is_app_store(domain):
    return bool(domain and domain in APP_STORE_DOMAINS)


def _normalise_categories(categories):
    if not categories:
        return []
    if isinstance(categories, str):
        return [categories.strip().lower()]
    return [str(c).strip().lower() for c in categories if c]


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

    parsed = urlparse(str(url))
    full = f"{parsed.path.lower()}?{parsed.query.lower()}"
    if any(x in full for x in ("/products/", "/product/", "/p/", "product=")):
        return "product_page"
    if any(x in full for x in ("/collections/", "/category/", "/shop/", "/catalog")):
        return "collection_page"
    if any(x in full for x in ("/landing", "/lp/", "/offer", "/promo")):
        return "landing_page"
    return "owned_site"


def _result(status, score, destination, business_type, reasons, exclusion_reason=None,
            product_signal=None):
    return {
        "qualified": status == "priority",
        "status": status,
        "score": max(0, min(100, int(score))),
        "destination_type": destination,
        "business_type": business_type,
        "product_signal": product_signal,
        "reasons": reasons,
        "exclusion_reason": exclusion_reason,
    }


def classify_icp(ad_record):
    """Return conservative, sales-oriented buyer-fit qualification."""
    name = (ad_record.get("business_name") or "").strip()
    url = ad_record.get("landing_url")
    domain = _domain(url)
    root_domain = _root_domain(url)
    categories = _normalise_categories(ad_record.get("page_categories") or ad_record.get("categories"))
    likes = ad_record.get("page_like_count")

    ad_text = _text(
        ad_record.get("ad_body") or ad_record.get("body"),
        ad_record.get("ad_title") or ad_record.get("title"),
        ad_record.get("caption"),
        ad_record.get("cta_text"),
        ad_record.get("cta_type"),
    )
    identity_text = _text(name, categories, domain)
    destination = _destination_type(domain, url)

    # ------------------------------------------------------------------
    # HARD GATES: these are not scoreable weaknesses. They invalidate the
    # sales premise and therefore never become a priority lead.
    # ------------------------------------------------------------------
    if destination == "app_store":
        return _result("excluded", 0, destination, "app_or_software",
                       ["Destination is an app-store listing, not a prospect-owned product funnel"],
                       "app_store")

    if destination == "marketplace":
        return _result("excluded", 0, destination, "marketplace",
                       [f"Destination is marketplace domain {root_domain or domain}, not an owned prospect funnel"],
                       "marketplace")

    if _matches(identity_text, LARGE_OR_NON_BUYER_NAME_PATTERNS):
        return _result("excluded", 0, destination, "enterprise_or_platform",
                       ["Advertiser appears to be a large platform, marketplace, or enterprise buyer outside the $499 target"],
                       "large_or_non_buyer")

    if _matches(identity_text, NON_BUYER_PATTERNS):
        return _result("excluded", 0, destination, "agency_or_software",
                       ["Advertiser appears to be an agency, software/platform, affiliate, lead-gen, or other non-target business"],
                       "non_buyer_business_type")

    service_hits = _matches(ad_text, SERVICE_PATTERNS)
    name_service = re.search(r"\b(coach|coaching|consultant|consulting|agency|marketing)\b", name, re.I)
    if name_service and not _matches(ad_text, SPECIFIC_PRODUCT_PATTERNS):
        return _result("excluded", 0, destination, "service_business",
                       ["Advertiser identity indicates a service/agency business rather than a physical product seller"],
                       "service_business")

    if len(service_hits) >= 2 and not _matches(ad_text, SPECIFIC_PRODUCT_PATTERNS):
        return _result("excluded", 0, destination, "service_business",
                       ["Ad contains multiple service/agency signals without a specific product signal"],
                       "service_business")

    try:
        likes_int = int(likes) if likes is not None else None
    except (TypeError, ValueError):
        likes_int = None

    if likes_int is not None and likes_int >= 1_000_000:
        return _result("excluded", 0, destination, "enterprise_or_platform",
                       [f"Page has {likes_int:,} likes and appears too large for the $499 offer"],
                       "very_large_page")

    if not name or not ad_record.get("landing_url"):
        return _result("excluded", 0, destination, "unknown",
                       ["Missing advertiser identity or destination; cannot responsibly make a sales recommendation"],
                       "missing_core_identity")

    # ------------------------------------------------------------------
    # PRODUCT IDENTITY GATE
    # ------------------------------------------------------------------
    specific_hits = _matches(ad_text, SPECIFIC_PRODUCT_PATTERNS)
    weak_hits = _matches(ad_text, WEAK_PRODUCT_PATTERNS)
    transaction_hits = _matches(ad_text, TRANSACTION_PATTERNS)
    category_hits = [
        c for c in categories
        if c in PRODUCT_CATEGORY_TERMS or any(term in c for term in PRODUCT_CATEGORY_TERMS)
    ]

    # Generic commerce language is explicitly NOT enough.
    # Example: "Shop our collection" + Beauty category remains review/excluded.
    if not specific_hits:
        if weak_hits and transaction_hits and category_hits:
            return _result(
                "review", 48, destination, "possible_product_business",
                [
                    "Commerce intent is present, but the ad does not identify a specific product",
                    "Generic category/commerce language is insufficient for automatic $499 outreach",
                ],
                product_signal="weak_category_only",
            )
        return _result(
            "excluded", 0, destination, "unproven_product_business",
            ["No specific purchasable product is identifiable from the advertiser/ad evidence"],
            "no_specific_product",
        )

    # Social profiles are acceptable as a destination because the offer can
    # directly fix the missing landing-page path. Owned sites are stronger for
    # legitimacy and purchase readiness.
    owned_site = destination not in {"instagram", "facebook", "social", "unknown"}

    # ------------------------------------------------------------------
    # SCORE: active intent 20 + product fit 20 + size 15 + opportunity 25
    #        + funnel quality 10 + legitimacy 10.
    # ------------------------------------------------------------------
    score = 0
    reasons = []

    # 1) ACTIVE AD INTENT / 20
    active_days = ad_record.get("ad_active_days")
    try:
        days = int(active_days) if active_days is not None else None
    except (TypeError, ValueError):
        days = None

    is_active = ad_record.get("is_active")
    if is_active is False:
        return _result("excluded", 0, destination, "inactive_product_business",
                       ["Meta record is marked inactive; offer targets businesses currently buying traffic"],
                       "inactive_ad")

    if days is None:
        active_points = 4
        reasons.append("Ad age is unknown; active-spend confidence is limited")
    elif days >= 30:
        active_points = 20
        reasons.append(f"Ad has been active about {days} days — strong evidence of ongoing acquisition spend")
    elif days >= 14:
        active_points = 15
        reasons.append(f"Ad has been active about {days} days — meaningful ongoing acquisition signal")
    elif days >= 7:
        active_points = 10
        reasons.append(f"Ad has been active about {days} days")
    elif days >= 2:
        active_points = 6
        reasons.append(f"Ad has been active about {days} days; spend persistence is not yet proven")
    else:
        active_points = 3
        reasons.append("Ad is very new; ongoing acquisition intent is not yet proven")
    score += active_points

    # 2) PRODUCT / COMMERCE FIT / 20
    if len(specific_hits) >= 2:
        product_points = 16
    else:
        product_points = 12
    if transaction_hits:
        product_points += 2
    if category_hits:
        product_points += 2
    product_points = min(20, product_points)
    score += product_points
    reasons.append("Ad identifies a specific physical product suitable for a dedicated landing page")
    if transaction_hits:
        reasons.append("Ad contains direct purchase/commerce intent")

    # 3) BUSINESS SIZE / AFFORDABILITY / 15
    if likes_int is None:
        size_points = 7
        reasons.append("Page-size signal is unavailable; affordability is moderately uncertain")
    elif 1_000 <= likes_int <= 250_000:
        size_points = 15
        reasons.append(f"Page size ({likes_int:,} likes) fits a small/mid-market advertiser")
    elif 250_001 <= likes_int <= 500_000:
        size_points = 10
        reasons.append(f"Page size ({likes_int:,} likes) suggests a larger brand; still plausible, but less aligned to $499")
    elif 100 <= likes_int < 1_000:
        size_points = 8
        reasons.append(f"Page has {likes_int:,} likes; business may be early-stage but is not automatically too small")
    elif likes_int < 100:
        size_points = 3
        reasons.append("Very small page footprint makes $499 purchasing ability less certain")
    else:
        size_points = 5
        reasons.append(f"Page has {likes_int:,} likes; scale lowers fit for the $499 offer")
    score += size_points

    # 4) LANDING-PAGE OPPORTUNITY / 25
    if destination in {"instagram", "facebook", "social"}:
        opportunity_points = 25
        opportunity_reason = "Ad sends traffic to a social destination — the missing product-specific landing page is an obvious conversion opportunity"
    elif destination == "owned_site":
        opportunity_points = 22
        opportunity_reason = "Ad sends traffic to the business site but not an identifiable product-specific destination"
    elif destination == "collection_page":
        opportunity_points = 23
        opportunity_reason = "Ad sends traffic to a collection/category page — a dedicated product page is a clear conversion opportunity"
    elif destination == "product_page":
        opportunity_points = 10
        opportunity_reason = "Ad already reaches a product page; opportunity exists but is less urgent than a generic/social destination"
    elif destination == "landing_page":
        opportunity_points = 4
        opportunity_reason = "Ad already uses an offer/landing destination; the $499 opportunity is comparatively weak"
    else:
        opportunity_points = 0
        opportunity_reason = "Destination cannot be classified confidently"
    score += opportunity_points
    reasons.append(opportunity_reason)

    # 5) WEBSITE / FUNNEL QUALITY / 10
    if destination in {"instagram", "facebook", "social"}:
        funnel_points = 4
        reasons.append("Social destination creates a clear funnel gap, but owned-site quality cannot be verified from the captured URL")
    elif owned_site:
        funnel_points = 8
        if destination in {"owned_site", "collection_page", "product_page"}:
            funnel_points += 2
        reasons.append("Resolved owned-domain destination provides a credible commercial funnel")
    else:
        funnel_points = 0
    score += min(10, funnel_points)

    # 6) BUSINESS LEGITIMACY / 10
    legitimacy_points = 0
    if owned_site:
        legitimacy_points += 5
        reasons.append(f"Destination is an owned commercial domain ({root_domain or domain})")
    else:
        legitimacy_points += 3
        reasons.append("Advertiser has a real social destination rather than a marketplace/app-store destination")
    if category_hits:
        legitimacy_points += 2
    if name and domain:
        # Exact brand/domain relation is useful, but do not reject legitimate
        # brands with a founder/company naming difference.
        name_clean = re.sub(r"[^a-z0-9]", "", name.lower())
        domain_clean = re.sub(r"[^a-z0-9]", "", (domain.split(".")[0] if domain else "").lower())
        if name_clean and domain_clean and (name_clean in domain_clean or domain_clean in name_clean):
            legitimacy_points += 3
            reasons.append("Advertiser name and destination domain show a direct brand relationship")
        else:
            legitimacy_points += 1
            reasons.append("Advertiser/domain relationship is not exact, so legitimacy confidence is slightly reduced")
    score += min(10, legitimacy_points)

    score = max(0, min(100, score))

    # ------------------------------------------------------------------
    # Final gate: a lead must have a concrete product AND a meaningful
    # opportunity. Scores cannot compensate for missing sales evidence.
    # ------------------------------------------------------------------
    if opportunity_points < 10:
        return _result("review", min(score, 69), destination, "product_business",
                       reasons + ["Landing-page opportunity is too weak for automatic outreach; inspect manually"],
                       product_signal="specific_product_low_opportunity")

    if days is None or days < 2:
        return _result("review", min(score, 69), destination, "product_business",
                       reasons + ["Active-spend persistence is not established enough for automatic outreach"],
                       product_signal="specific_product_new_ad")

    if score >= 90:
        status = "priority"
    elif score >= 80:
        status = "priority"
    elif score >= 70:
        status = "review"
    elif score >= 50:
        status = "review"
    else:
        status = "excluded"

    if status == "review":
        reasons.append("Good candidate for review, but evidence is not strong enough for automatic primary outreach")
    elif status == "excluded":
        reasons.append("Overall buyer-fit is too weak for the $499 offer")

    return _result(
        status, score, destination, "product_business", reasons,
        None if status != "excluded" else "low_buyer_fit",
        product_signal="specific_product",
    )
