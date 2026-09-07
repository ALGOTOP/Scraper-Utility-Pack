"""Strict, evidence-first buyer-fit classifier for the $499 product landing-page offer."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

SOCIAL_DOMAINS = {"facebook.com", "m.facebook.com", "instagram.com", "l.instagram.com", "fb.me", "fb.watch", "tiktok.com", "www.tiktok.com"}
APP_STORE_DOMAINS = {"itunes.apple.com", "apps.apple.com", "play.google.com"}
MARKETPLACE_DOMAINS = {"amazon.com", "amazon.co.uk", "amazon.ca", "amazon.com.au", "walmart.com", "ebay.com", "etsy.com", "temu.com", "aliexpress.com", "alibaba.com", "shein.com", "wish.com", "wayfair.com"}
NON_BUYER = [r"\bmarketing agency\b", r"\bdigital agency\b", r"\bad agency\b", r"\bmedia agency\b", r"\bcreative agency\b", r"\badvertising agency\b", r"\bperformance marketing\b", r"\bseo agency\b", r"\bsocial media agency\b", r"\bweb design agency\b", r"\bcrm\b", r"\bsaas\b", r"\bsoftware\b", r"\bplatform\b", r"\bmobile app\b", r"\bmarketplace\b", r"\baffiliate\b", r"\blead generation\b", r"\blead gen\b", r"\bdropshipping\b"]
LARGE = [r"\bamazon\b", r"\bwalmart\b", r"\btarget\b", r"\bcostco\b", r"\bhome depot\b", r"\blowe'?s\b", r"\bwayfair\b", r"\bebay\b", r"\betsy\b", r"\baliexpress\b", r"\balibaba\b", r"\btemu\b", r"\bshein\b", r"\bshopify\b", r"\bmeta\b", r"\bgoogle\b", r"\bmicrosoft\b", r"\badobe\b", r"\bcanva\b", r"\bhubspot\b", r"\bsemrush\b", r"\bmailchimp\b"]
SERVICE = [r"\bbook (?:a|an) (?:call|discovery call)\b", r"\bfree consultation\b", r"\bmarketing services?\b", r"\bad management\b", r"\bmedia buying\b", r"\bseo services?\b", r"\bweb design services?\b", r"\bcoaching program\b", r"\bconsulting services?\b", r"\bagency services?\b", r"\bclient acquisition\b", r"\bmonthly ad spend\b", r"\baverage roas\b", r"\bfor \d+\+ brands\b", r"\bour clients\b", r"\bwork with brands\b", r"\bwe manage\b"]
SPECIFIC = [
    r"\b(?:vitamin\s*c|retinol|hyaluronic|niacinamide|salicylic|glycolic)\b.{0,50}\b(?:serum|cream|cleanser|toner|moisturizer|lotion)\b",
    r"\b(?:serum|cream|cleanser|toner|moisturizer|lotion|face wash|facial oil|sunscreen|sunblock|spf\s*\d+)\b",
    r"\b(?:lip balm|lip gloss|lipstick|mascara|foundation|concealer|blush|eyeliner)\b",
    r"\b(?:shampoo|conditioner|hair mask|hair oil|body wash|deodorant)\b",
    r"\b(?:running|hiking|trail|basketball|tennis|training)\s+shoes\b|\b(?:sneakers?|boots?|sandals?|loafers?)\b",
    r"\b(?:hoodie|sweatshirt|jacket|coat|leggings|joggers|dress|jeans|t-shirt|shirt)\b",
    r"\b(?:crossbody|tote|backpack|duffel|handbag|wallet|purse)\b",
    r"\b(?:necklace|bracelet|earrings?|ring|pendant|watch)\b",
    r"\b(?:protein powder|protein shake|creatine|electrolytes?|pre-workout|post-workout)\b",
    r"\b(?:vitamins?|probiotics?|collagen|omega[- ]?3|fish oil)\b",
    r"\b(?:coffee beans?|ground coffee|tea|matcha|snack|granola|chocolate)\b",
    r"\b(?:dog|cat)\s+(?:food|treats?|supplements?)\b",
    r"\b(?:candle|diffuser|bedding|duvet|pillow|mattress|lamp|rug|blanket)\b",
    r"\b(?:water bottle|tumbler|phone case|air purifier|vacuum)\b",
    r"\b(?:baby carrier|diaper bag|baby monitor|stroller|toys?)\b",
    r"\b(?:model|sku|style)\s*[#:-]?\s*[a-z0-9-]{2,}\b",
]
WEAK = [r"\bskincare\b", r"\bmakeup\b", r"\bcosmetics?\b", r"\bapparel\b", r"\bclothing\b", r"\bjewelry\b", r"\bfootwear\b", r"\baccessories\b", r"\bpet supplies\b", r"\bhome goods\b", r"\bhome decor\b", r"\bconsumer goods\b"]
TRANSACTION = [r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b", r"\bfree shipping\b", r"\bshipping\b", r"\bnew collection\b", r"\bnew drop\b", r"\bsale\b", r"\bdiscount\b", r"\b\d+% off\b", r"\bbundle\b", r"\bget yours\b", r"\bget offer\b", r"\bshop\b"]
PURCHASE_CTA = [r"\bshop now\b", r"\bbuy now\b", r"\border now\b", r"\badd to cart\b", r"\bget yours\b", r"\bget offer\b"]
CATEGORIES = {"shopping & retail", "retail", "e-commerce", "ecommerce", "clothing", "apparel", "beauty", "cosmetics", "health/beauty", "health & beauty", "food & beverage", "food", "jewelry", "home decor", "home goods", "baby goods", "pet supplies", "sports & recreation", "fitness", "consumer goods", "product/service", "brand"}
PRODUCT_PATHS = ("/products/", "/product/", "/items/", "/item/", "/dp/")
COLLECTION_PATHS = ("/collections/", "/category/", "/categories/", "/shop/", "/catalog")


def _domain(url):
    if not url: return None
    try:
        host = urlparse(str(url)).netloc.lower().split("@")[-1].split(":")[0]
        return host[4:] if host.startswith("www.") else host
    except Exception: return None


def _root_domain(url):
    host = _domain(url)
    if not host: return None
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _text(*values):
    out = []
    for v in values:
        if v is None: continue
        if isinstance(v, (list, tuple, set)): out.extend(str(x) for x in v if x is not None)
        elif isinstance(v, dict): out.append(str(v.get("text") or v))
        else: out.append(str(v))
    return " ".join(out).lower().strip()


def _matches(text, patterns): return [p for p in patterns if re.search(p, text, re.I)]
def _is_social(domain): return bool(domain and (domain in SOCIAL_DOMAINS or any(domain.endswith("." + d) for d in SOCIAL_DOMAINS)))
def _is_marketplace(domain): return bool(domain and (domain in MARKETPLACE_DOMAINS or any(domain.endswith("." + d) for d in MARKETPLACE_DOMAINS)))
def _is_app_store(domain): return bool(domain and domain in APP_STORE_DOMAINS)


def _normalise_categories(categories):
    if not categories: return []
    if isinstance(categories, str): return [categories.strip().lower()]
    return [str(c).strip().lower() for c in categories if c]


def _destination_type(domain, url):
    if not domain: return "unknown"
    if _is_social(domain): return "instagram" if "instagram" in domain else ("facebook" if "facebook" in domain or domain == "fb.me" else "social")
    if _is_app_store(domain): return "app_store"
    if _is_marketplace(domain): return "marketplace"
    path = urlparse(str(url)).path.lower()
    if any(x in path for x in PRODUCT_PATHS): return "product_page"
    if any(x in path for x in COLLECTION_PATHS): return "collection_page"
    if any(x in path for x in ("/landing", "/lp/", "/offer", "/promo")): return "landing_page"
    return "owned_site"


def _url_product_text(url):
    if not url: return ""
    path = unquote(urlparse(str(url)).path.lower())
    match = re.search(r"/(?:products?|items?|item|dp)/([^/?#]+)", path)
    if not match: return ""
    slug = re.sub(r"[-_]+", " ", match.group(1))
    return re.sub(r"\s+", " ", re.sub(r"\d{2,}", " ", slug)).strip()


def _result(status, score, destination, business_type, reasons, exclusion_reason=None, product_signal=None, product_evidence=None, landing_opportunity=None):
    return {"qualified": status == "priority", "status": status, "score": max(0, min(100, int(score))), "destination_type": destination, "business_type": business_type, "product_signal": product_signal, "product_evidence": product_evidence, "landing_opportunity": landing_opportunity, "reasons": reasons, "exclusion_reason": exclusion_reason}


def classify_icp(ad_record):
    name = (ad_record.get("business_name") or "").strip()
    url = ad_record.get("landing_url")
    domain = _domain(url)
    root = _root_domain(url)
    categories = _normalise_categories(ad_record.get("page_categories") or ad_record.get("categories"))
    likes = ad_record.get("page_like_count")
    text = _text(ad_record.get("ad_body") or ad_record.get("body"), ad_record.get("ad_title") or ad_record.get("title"), ad_record.get("caption"), ad_record.get("cta_text"), ad_record.get("cta_type"))
    identity = _text(name, categories, domain)
    destination = _destination_type(domain, url)
    url_product = _url_product_text(url)
    specific_hits = _matches(text, SPECIFIC)
    weak_hits = _matches(text, WEAK)
    tx_hits = _matches(text, TRANSACTION)
    cta_hits = _matches(text, PURCHASE_CTA)
    category_hits = [c for c in categories if c in CATEGORIES or any(term in c for term in CATEGORIES)]
    url_specific = _matches(url_product, SPECIFIC)

    if destination == "app_store": return _result("excluded", 0, destination, "app_or_software", ["Destination is an app-store listing, not a prospect-owned product funnel"], "app_store")
    if destination == "marketplace": return _result("excluded", 0, destination, "marketplace", [f"Destination is marketplace domain {root or domain}, not an owned prospect funnel"], "marketplace")
    if _matches(identity, LARGE): return _result("excluded", 0, destination, "enterprise_or_platform", ["Advertiser appears to be a large platform, marketplace, or enterprise buyer outside the $499 target"], "large_or_non_buyer")
    if _matches(identity, NON_BUYER): return _result("excluded", 0, destination, "agency_or_software", ["Advertiser appears to be an agency, software/platform, affiliate, lead-gen, or other non-target business"], "non_buyer_business_type")
    if not name or not url: return _result("excluded", 0, destination, "unknown", ["Missing advertiser identity or destination; cannot responsibly make a sales recommendation"], "missing_core_identity")

    name_service = re.search(r"\b(coach|coaching|consultant|consulting|agency|marketing)\b", name, re.I)
    service_hits = _matches(text, SERVICE)
    if name_service and not (specific_hits or url_specific or destination == "product_page"):
        return _result("excluded", 0, destination, "service_business", ["Advertiser identity indicates a service/agency business rather than a physical product seller"], "service_business")
    if len(service_hits) >= 2 and not (specific_hits or url_specific or destination == "product_page"):
        return _result("excluded", 0, destination, "service_business", ["Ad contains multiple service/agency signals without product evidence"], "service_business")

    try: likes_int = int(likes) if likes is not None else None
    except (TypeError, ValueError): likes_int = None
    if likes_int is not None and likes_int >= 1_000_000:
        return _result("excluded", 0, destination, "enterprise_or_platform", [f"Page has {likes_int:,} likes and appears too large for the $499 offer"], "very_large_page")

    # Product evidence hierarchy. A first-party product URL is strong evidence even
    # when the slug is unfamiliar; Meta ad copy frequently sells benefits instead.
    if specific_hits:
        product_signal, product_evidence = "specific_product", "Specific product identified in ad copy" + ("; multiple product signals" if len(specific_hits) >= 2 else "")
    elif destination == "product_page" and url_product:
        product_signal, product_evidence = "specific_product", f"Specific product destination identified by URL: {url_product}"
    elif destination == "product_page" and (category_hits or tx_hits or cta_hits):
        product_signal, product_evidence = "specific_product", "First-party product-page destination with independent commerce evidence"
    elif weak_hits and (tx_hits or cta_hits) and category_hits:
        return _result("review", 55, destination, "possible_product_business", ["Commerce intent is present, but only category-level product evidence is available"], product_signal="weak_category_only", product_evidence="Category-level product evidence only")
    else:
        return _result("excluded", 0, destination, "unproven_product_business", ["No specific purchasable product is identifiable from the advertiser, ad, or destination evidence"], "no_specific_product")

    if ad_record.get("is_active") is False:
        return _result("excluded", 0, destination, "inactive_product_business", ["Meta record is marked inactive; offer targets businesses currently buying traffic"], "inactive_ad", product_signal=product_signal, product_evidence=product_evidence)

    active_days = ad_record.get("ad_active_days")
    try: days = int(active_days) if active_days is not None else None
    except (TypeError, ValueError): days = None

    score, reasons = 0, []
    if days is None: score += 8; reasons.append("Ad age is unknown; active-spend confidence is limited")
    elif days >= 30: score += 20; reasons.append(f"Ad has been active about {days} days — strong evidence of ongoing acquisition spend")
    elif days >= 14: score += 15; reasons.append(f"Ad has been active about {days} days — meaningful ongoing acquisition signal")
    elif days >= 7: score += 11; reasons.append(f"Ad has been active about {days} days")
    elif days >= 2: score += 7; reasons.append(f"Ad has been active about {days} days; spend persistence is developing")
    else: score += 4; reasons.append("Ad is very new; ongoing acquisition intent is not yet proven")

    product_points = 18 if (specific_hits or url_specific or destination == "product_page") else 14
    if tx_hits or cta_hits: product_points += 2
    if category_hits: product_points += 1
    score += min(20, product_points); reasons.append(f"Product evidence: {product_evidence}")
    if tx_hits or cta_hits: reasons.append("Ad contains direct purchase/commerce intent")

    if likes_int is None: score += 7; reasons.append("Page-size signal is unavailable; affordability is moderately uncertain")
    elif 1_000 <= likes_int <= 250_000: score += 15; reasons.append(f"Page size ({likes_int:,} likes) fits a small/mid-market advertiser")
    elif 250_001 <= likes_int <= 500_000: score += 10; reasons.append(f"Page size ({likes_int:,} likes) suggests a larger brand; still plausible")
    elif 100 <= likes_int < 1_000: score += 8; reasons.append(f"Page has {likes_int:,} likes; early-stage but not automatically too small")
    elif likes_int < 100: score += 3; reasons.append("Very small page footprint makes $499 purchasing ability less certain")
    else: score += 5; reasons.append(f"Page has {likes_int:,} likes; scale lowers fit for the $499 offer")

    if destination in {"instagram", "facebook", "social"}: opportunity, opportunity_points = "Ad sends traffic to a social destination — the missing product-specific landing page is an obvious conversion opportunity", 25
    elif destination == "owned_site": opportunity, opportunity_points = "Ad sends traffic to the business site but not an identifiable product-specific destination", 22
    elif destination == "collection_page": opportunity, opportunity_points = "Ad sends traffic to a collection/category page — a dedicated product page is a clear conversion opportunity", 23
    elif destination == "product_page": opportunity, opportunity_points = "Ad reaches a product page; the opportunity is a stronger dedicated conversion experience around the advertised offer", 10
    elif destination == "landing_page": opportunity, opportunity_points = "Ad already uses an offer/landing destination; the $499 opportunity is comparatively weak", 4
    else: opportunity, opportunity_points = "Destination cannot be classified confidently", 0
    score += opportunity_points; reasons.append(opportunity)

    if destination in {"instagram", "facebook", "social"}: score += 4; reasons.append("Social destination creates a clear funnel gap, but owned-site quality cannot be verified")
    elif destination not in {"unknown", "app_store", "marketplace"}: score += 10; reasons.append("Resolved owned-domain destination provides a credible commercial funnel")

    legitimacy = 5 + (2 if category_hits else 0)
    if name and domain:
        nc = re.sub(r"[^a-z0-9]", "", name.lower()); dc = re.sub(r"[^a-z0-9]", "", domain.split(".")[0].lower())
        legitimacy += 3 if nc and dc and (nc in dc or dc in nc) else 1
        reasons.append("Advertiser name and destination domain show a direct brand relationship" if legitimacy >= 10 else "Advertiser/domain relationship is not exact, so legitimacy confidence is slightly reduced")
    score += min(10, legitimacy); score = max(0, min(100, score))

    # Evidence gates: do not turn an unknown/very-new ad into an automatic lead,
    # but do not pretend unknown age means zero days either.
    if opportunity_points < 10:
        return _result("review", min(score, 69), destination, "product_business", reasons + ["Landing-page opportunity is too weak for automatic outreach; inspect manually"], product_signal="specific_product_low_opportunity", product_evidence=product_evidence, landing_opportunity=opportunity)
    if days is not None and days < 2:
        return _result("review", min(score, 69), destination, "product_business", reasons + ["Ad is too new to prove ongoing acquisition spend; inspect manually"], product_signal="specific_product_new_ad", product_evidence=product_evidence, landing_opportunity=opportunity)
    if days is None and score < 88:
        return _result("review", min(score, 79), destination, "product_business", reasons + ["Ad age is unknown and total evidence is not strong enough for automatic outreach"], product_signal="specific_product_age_unknown", product_evidence=product_evidence, landing_opportunity=opportunity)

    status = "priority" if score >= 80 else ("review" if score >= 50 else "excluded")
    if status == "priority": reasons.append("Evidence clears the automatic sales-ready threshold")
    elif status == "review": reasons.append("Candidate is plausible but evidence is not strong enough for automatic primary outreach")
    else: reasons.append("Overall buyer-fit is too weak for the $499 offer")
    return _result(status, score, destination, "product_business", reasons, None if status != "excluded" else "low_buyer_fit", product_signal=product_signal, product_evidence=product_evidence, landing_opportunity=opportunity)
