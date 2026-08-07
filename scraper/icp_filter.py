"""
ICP mismatch filter
--------------------
A flag layered ON TOP of the scoring engine's score/confidence/needs_review
output -- not a replacement for it, and not itself a score. Catches known
bad-ICP patterns so they can be excluded or deprioritized in an export
without deleting the underlying lead data (a business here is a real ad
buyer, just not one worth manually working).

Two rules are automated today:

1. App-store-only destinations: the ad's final_url resolves to an app
   store listing (itunes.apple.com, apps.apple.com, play.google.com)
   rather than the business's own site. Real example: Teero Dental --
   a legitimate dental-software business, but there's no landing page to
   run a CRO/audit against, so it doesn't fit an outreach motion built
   around "here's what's wrong with your landing page."

2. Known large SaaS platforms / affiliate funnels: an explicit denylist
   of names/domains seen misfiring onto this keyword search
   (Builderall, GoHighLevel/HighLevel, CRMPros.ai, Birdeye, NexHealth).
   Deliberately a denylist, not an inferred "is this a large company"
   heuristic -- inferring company size from scraped ad data (e.g. domain
   age, traffic rank) needs data this scraper doesn't collect, and would
   risk false positives against real small/mid prospects. Add more
   entries here as new platforms are observed misfiring.

NOT automated (by design): off-topic results with no relation to the
search keyword's industry at all (e.g. "dental software" surfacing Kong,
HRcosts.com, Coilcraft Inc.). There's no reliable domain/name heuristic
for "wrong industry" without either a real industry taxonomy or an LLM
call, and a false positive here would wrongly exclude a real prospect --
worse than leaving it for manual/LLM-based tagging later. The
icp_mismatch_reason column is free text specifically so a future pass
can fill this in without a schema change.
"""
from urllib.parse import urlparse

APP_STORE_DOMAINS = {"itunes.apple.com", "apps.apple.com", "play.google.com"}

# Each entry: label shown in the reason string, the domain(s) that count as
# a match, and the name token(s) checked against the business name (since a
# denylisted platform can show up as the advertiser name even when the
# landing page uses a different tracking/redirect domain).
PLATFORM_DENYLIST = [
    {"label": "Builderall", "domains": {"builderall.com"}, "name_tokens": {"builderall"}},
    {
        "label": "GoHighLevel/HighLevel",
        "domains": {"gohighlevel.com", "highlevel.com", "leadconnectorhq.com"},
        "name_tokens": {"gohighlevel", "go high level", "highlevel", "high level"},
    },
    {"label": "CRMPros.ai", "domains": {"crmpros.ai"}, "name_tokens": {"crmpros"}},
    {"label": "Birdeye", "domains": {"birdeye.com"}, "name_tokens": {"birdeye"}},
    {"label": "NexHealth", "domains": {"nexhealth.com"}, "name_tokens": {"nexhealth"}},
]


def _get_domain(url):
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.replace("www.", "") or None
    except Exception:
        return None


def check_icp_mismatch(business_name, final_url):
    """
    Returns (icp_mismatch: bool, icp_mismatch_reason: str | None).

    Only rules 1 and 2 from the module docstring are automated here --
    see the docstring for why rule 3 (off-topic industry) is intentionally
    left as a TODO rather than a guessed heuristic.
    """
    domain = _get_domain(final_url)
    name = (business_name or "").lower()

    if domain in APP_STORE_DOMAINS:
        return True, f"App-store-only destination ({domain}) - no landing page to audit"

    for platform in PLATFORM_DENYLIST:
        if domain in platform["domains"]:
            return True, f"Known platform/affiliate-funnel denylist match: {platform['label']} (domain={domain})"
        if name and any(token in name for token in platform["name_tokens"]):
            return True, f"Known platform/affiliate-funnel denylist match: {platform['label']} (business name)"

    return False, None
