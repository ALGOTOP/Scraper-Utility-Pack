"""
Meta Ad Library scraper — Playwright driven.

ARCHITECTURE, and why:
Meta's Ad Library page fetches results via internal GraphQL calls, then
renders them into a page full of hashed, rotating CSS classes. Selector
scraping against that rendered HTML is what breaks monthly. Instead:

  PRIMARY PATH: intercept the page's own network responses and read
  the JSON the page itself already parsed and rendered from. This
  survives CSS/layout changes untouched — it only breaks if Meta
  changes the GraphQL schema itself, which is far rarer.

  FALLBACK PATH: if no matching GraphQL response is seen (endpoint
  renamed, response shape changed), fall back to dom_parser.py's
  text-marker-based DOM scraping.

  Either way, every result gets a status: 'ok' | 'needs_review' |
  'blocked' | 'no_results'. Nothing is silently treated as a clean
  miss — 'needs_review' rows are exactly what should be queued for the
  Claude judgment layer, per the existing scoring engine design.

IMPORTANT — WHAT THIS FILE CANNOT DO IN THIS SANDBOX:
This environment has no network access, so the GraphQL response shape
below (GRAPHQL_URL_PATTERN, field paths in _parse_graphql_payload) is
based on documented/public writeups of the Ad Library's structure, NOT
a live capture. Before trusting this in production:
  1. Open the Ad Library in a real browser with DevTools > Network > Fuse
     filter set to "Fetch/XHR", run one search, and find the request
     that returns the ad results as JSON.
  2. Confirm/update GRAPHQL_URL_PATTERN and the field paths in
     _parse_graphql_payload against that real payload.
  3. Run this scraper against ONE keyword/country combo first and
     manually spot-check 5-10 results before scaling up.
This is a 15-minute check in Replit (which has network) and it's the
single highest-leverage step for hitting real 90%+ accuracy, because
it's the one part of this pipeline I could not verify without network
access.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Optional

from dom_parser import parse_ad_cards
from rate_limiter import RateLimiter, SessionBudgetExceeded
from url_builder import build_search_urls_for_query

# CONFIRMED against a real live capture on 2026-07-25 (non-Replit network,
# home wifi, Windows — no rate limiting observed):
#   - Endpoint: https://www.facebook.com/api/graphql/ (POST) ✓
#   - Pattern "/api/graphql/" matches correctly ✓
#   - Real ad-results path (confirmed against captured_payload.json):
#       data -> ad_library_main -> search_results_connection -> edges
#       edge -> node -> collated_results (list, usually 1 item, can be more)
#       each item: ad_archive_id, page_name, publisher_platform,
#                  start_date, end_date, snapshot.link_url, snapshot.cards
#   - NOTE: the earlier guess ("results.edges") was wrong — it's
#     "search_results_connection.edges" with an extra collated_results
#     nesting level. Fixed in _parse_graphql_payload below.
#   - Rate limiting appears IP-range-specific to Replit: on home wifi the
#     GraphQL endpoint returned real payloads immediately, no 1675004 errors.
GRAPHQL_URL_PATTERN = "/api/graphql/"

BLOCKED_MARKERS = [
    "please try again later",
    "unusual activity",
    "checkpoint",
    "captcha",
]
NO_RESULTS_MARKERS = [
    "no ads match",
    # NOTE: "0 results" was removed because it false-positives on page text
    # like "~730 results" (substring match). "no ads match" covers the real
    # zero-results case. Confirmed against a live page on 2026-07-23.
]


@dataclass
class ScrapedAd:
    library_id: Optional[str]
    advertiser_name: Optional[str]
    platforms: list          # e.g. ['FACEBOOK', 'INSTAGRAM'] — from publisher_platform
    raw_href: Optional[str]
    final_url: Optional[str]
    status: str  # 'ok' | 'needs_review' | 'blocked' | 'no_results'
    source: str  # 'graphql' | 'dom_fallback'


@dataclass
class ScrapeSession:
    keyword: Optional[str]
    country: str
    page_ids: list = field(default_factory=list)
    results: list = field(default_factory=list)
    graphql_hits: int = 0
    dom_fallback_used: bool = False
    urls_attempted: int = 0
    urls_blocked: int = 0
    session_status: str = "incomplete"  # 'ok' | 'partially_blocked' | 'blocked' | 'exhausted_budget'


def classify_page_text(visible_text: str) -> Optional[str]:
    """Cheap pre-check on visible page text before trying to parse anything."""
    low = visible_text.lower()
    for marker in BLOCKED_MARKERS:
        if marker in low:
            return "blocked"
    for marker in NO_RESULTS_MARKERS:
        if marker in low:
            return "no_results"
    return None


def _parse_graphql_payload(payload: dict) -> list[ScrapedAd]:
    """
    Parse a real Meta Ad Library GraphQL response.

    Confirmed field path (live capture 2026-07-25):
      payload
        ["data"]["ad_library_main"]["search_results_connection"]["edges"]
        -> each edge["node"]["collated_results"]   # list, usually 1 item
        -> each ad:
             ad_archive_id       — the library ID shown in the UI
             page_name           — advertiser name
             publisher_platform  — list e.g. ['FACEBOOK', 'INSTAGRAM']
             snapshot.link_url   — the real landing-page URL (already unwrapped)
             snapshot.cards      — list; each card also has link_url
                                   (usually identical to snapshot.link_url, but
                                   flagged needs_review when they diverge)

    Structured defensively: any missing field produces a needs_review row
    rather than raising and killing the whole batch.
    """
    from link_unwrapper import unwrap_destination

    out = []
    try:
        edges = (
            payload.get("data", {})
            .get("ad_library_main", {})
            .get("search_results_connection", {})
            .get("edges", [])
        )
    except AttributeError:
        return out

    for edge in edges:
        if not isinstance(edge, dict):
            continue
        node = edge.get("node") or {}
        if not isinstance(node, dict):
            continue
        collated = node.get("collated_results") or []
        if not isinstance(collated, list):
            continue

        for ad in collated:
            if not isinstance(ad, dict):
                continue

            library_id = ad.get("ad_archive_id") or ad.get("collation_id")
            advertiser_name = ad.get("page_name")
            platforms = ad.get("publisher_platform") or []

            snapshot = ad.get("snapshot") or {}
            snap_url = snapshot.get("link_url") if isinstance(snapshot, dict) else None

            # Multi-card conflict check: if any card has a different link_url
            # than snapshot.link_url, we can't be sure which is the real CTA —
            # flag needs_review rather than silently picking one.
            cards = snapshot.get("cards") or [] if isinstance(snapshot, dict) else []
            card_urls = {
                c.get("link_url") for c in cards
                if isinstance(c, dict) and c.get("link_url")
            }
            card_urls.discard(None)
            conflicting = card_urls - ({snap_url} if snap_url else set())

            if conflicting:
                out.append(ScrapedAd(
                    library_id=str(library_id) if library_id else None,
                    advertiser_name=advertiser_name,
                    platforms=list(platforms),
                    raw_href=snap_url,
                    final_url=None,
                    status="needs_review",
                    source="graphql",
                ))
                continue

            # snapshot.link_url on Ad Library is already the real destination
            # (not a shim), so unwrap_destination is a no-op but kept for
            # defence against future changes.
            unwrapped = unwrap_destination(snap_url) if snap_url else {
                "final_url": None, "parse_ok": False}

            out.append(ScrapedAd(
                library_id=str(library_id) if library_id else None,
                advertiser_name=advertiser_name,
                platforms=list(platforms),
                raw_href=snap_url,
                final_url=unwrapped["final_url"],
                status="ok" if unwrapped.get("parse_ok") else "needs_review",
                source="graphql",
            ))

    return out


def _scrape_one_url(url: str, page, rate_limiter: RateLimiter, session: ScrapeSession) -> str:
    """
    Runs one search URL (either the keyword search or one page_id search)
    against the given Playwright page, appending results onto `session`.
    Returns this URL's own status: 'ok' | 'blocked' | 'no_results' |
    'exhausted_budget' -- the caller decides how that rolls up into the
    overall session_status.
    """
    captured_payloads = []

    def on_response(response):
        if GRAPHQL_URL_PATTERN in response.url and response.request.method == "POST":
            try:
                captured_payloads.append(response.json())
            except Exception:
                pass  # non-JSON response on this URL, ignore

    page.on("response", on_response)
    session.urls_attempted += 1

    try:
        rate_limiter.wait()
        page.goto(url, wait_until="networkidle")
    except SessionBudgetExceeded:
        return "exhausted_budget"

    visible_text = page.inner_text("body")
    early_status = classify_page_text(visible_text)
    if early_status == "blocked":
        return "blocked"
    if early_status == "no_results":
        return "no_results"

    # Scroll a few times to trigger lazy-loaded results, respecting the
    # rate limiter between each scroll (each scroll typically fires a
    # new GraphQL request for the next page of results).
    for _ in range(5):
        try:
            rate_limiter.wait()
        except SessionBudgetExceeded:
            return "exhausted_budget"
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)

    found_any = False
    for payload in captured_payloads:
        parsed = _parse_graphql_payload(payload)
        if parsed:
            found_any = True
        session.results.extend(parsed)
        session.graphql_hits += 1

    if not found_any:
        # GraphQL interception found nothing usable for THIS url -- fall
        # back to DOM parsing for this url only, not the whole session.
        session.dom_fallback_used = True
        html = page.content()
        dom_results = parse_ad_cards(html)
        for r in dom_results:
            session.results.append(ScrapedAd(
                library_id=r["library_id"],
                advertiser_name=r["advertiser_name"],
                platforms=[],  # DOM fallback has no platform data
                raw_href=r["raw_href"],
                final_url=r["final_url"],
                status=r["status"],
                source="dom_fallback",
            ))

    page.remove_listener("response", on_response)
    return "ok"


def run_scrape(page, rate_limiter: RateLimiter, keyword: str = None,
               country: str = "US", page_ids: list = None) -> ScrapeSession:
    """
    Entry point supporting all three modes, per the "configurable per
    run" requirement:
      - keyword only        -> broad discovery
      - page_ids only        -> targeted advertiser list
      - keyword + page_ids   -> both, combined into one session

    `page` is a Playwright Page object (passed in so this function stays
    testable / mockable without a real browser).
    """
    page_ids = page_ids or []
    urls = build_search_urls_for_query(keyword=keyword, country=country, page_ids=page_ids)
    session = ScrapeSession(keyword=keyword, country=country, page_ids=page_ids)

    statuses = []
    for url in urls:
        status = _scrape_one_url(url, page, rate_limiter, session)
        statuses.append(status)
        if status == "blocked":
            session.urls_blocked += 1
        if status == "exhausted_budget":
            # Stop attempting further URLs this session -- don't keep
            # hammering a rate-limited session.
            break

    if all(s == "exhausted_budget" for s in statuses) and statuses:
        session.session_status = "exhausted_budget"
    elif all(s == "blocked" for s in statuses) and statuses:
        session.session_status = "blocked"
    elif session.urls_blocked > 0:
        session.session_status = "partially_blocked"
    else:
        session.session_status = "ok"

    return session


if __name__ == "__main__":
    # Fixture-based self-test: run _parse_graphql_payload against the real
    # captured payload from the 2026-07-25 live run (no browser/network needed).
    import json, pathlib, sys

    # Accept an optional path argument; default to the attached_assets copy.
    search_paths = [
        pathlib.Path(__file__).parent.parent / "attached_assets" / "captured_payload_1784971618300.json",
        pathlib.Path(__file__).parent / "captured_payload.json",
    ]
    fixture_path = next((p for p in search_paths if p.exists()), None)

    if fixture_path is None:
        print("No fixture file found; run live_capture.py first to generate captured_payload.json")
        sys.exit(1)

    print(f"Loading fixture: {fixture_path}")
    with open(fixture_path) as f:
        raw = json.load(f)

    # The fixture is a list of captured responses; find the one with ad results.
    all_results = []
    for item in raw:
        payload = item.get("payload", item)  # handle both wrapped and bare
        parsed = _parse_graphql_payload(payload)
        all_results.extend(parsed)

    print(f"\nTotal parsed results: {len(all_results)}")
    assert len(all_results) >= 10, f"Expected >=10 results, got {len(all_results)}"

    print("\nFirst 5 results:")
    for r in all_results[:5]:
        print(
            f"  [{r.status:12s}] {(r.advertiser_name or 'N/A'):35s} | "
            f"platforms={r.platforms} | {r.final_url or r.raw_href or 'NO URL'}"
        )

    ok_count = sum(1 for r in all_results if r.status == "ok")
    nr_count = sum(1 for r in all_results if r.status == "needs_review")
    print(f"\nstatus breakdown: ok={ok_count}  needs_review={nr_count}")
    print("\nscraper.py fixture test passed.")
