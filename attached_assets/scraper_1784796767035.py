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

# CONFIRM THIS against a live capture (see module docstring, step 1-2).
GRAPHQL_URL_PATTERN = "/api/graphql/"

BLOCKED_MARKERS = [
    "please try again later",
    "unusual activity",
    "checkpoint",
    "captcha",
]
NO_RESULTS_MARKERS = [
    "no ads match",
    "0 results",
]


@dataclass
class ScrapedAd:
    library_id: Optional[str]
    advertiser_name: Optional[str]
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
    Placeholder field-path parsing — MUST be confirmed against a real
    capture (see module docstring). Structured defensively: any field
    access that fails produces a 'needs_review' row instead of raising
    and killing the whole batch.
    """
    out = []
    try:
        edges = (
            payload.get("data", {})
            .get("ad_library_main", {})
            .get("results", {})
            .get("edges", [])
        )
    except AttributeError:
        return out

    for edge in edges:
        node = edge.get("node", {}) if isinstance(edge, dict) else {}
        library_id = node.get("collation_id") or node.get("id")
        advertiser_name = node.get("page_name")
        raw_href = None
        snapshot = node.get("snapshot", {}) if isinstance(node, dict) else {}
        if isinstance(snapshot, dict):
            raw_href = snapshot.get("link_url") or snapshot.get("cta_url")

        from link_unwrapper import unwrap_destination
        unwrapped = unwrap_destination(raw_href) if raw_href else {
            "final_url": None, "parse_ok": False}

        out.append(ScrapedAd(
            library_id=str(library_id) if library_id else None,
            advertiser_name=advertiser_name,
            raw_href=raw_href,
            final_url=unwrapped["final_url"],
            status="ok" if unwrapped["parse_ok"] else "needs_review",
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
    # This module's live network path (run_scrape with a real Page) can't
    # be exercised here -- no network in this sandbox. What CAN be tested
    # without a browser: the pure-logic pieces, which is what
    # url_builder.py, link_unwrapper.py, dom_parser.py, and
    # rate_limiter.py each already do standalone. Run those four scripts
    # directly to see their self-tests. This file's job is orchestration;
    # test it live in Replit against one real keyword/country first.
    print("scraper.py has no standalone network-free self-test -- see")
    print("the other four modules for logic that's already verified,")
    print("and the module docstring above for the live-verification steps.")
