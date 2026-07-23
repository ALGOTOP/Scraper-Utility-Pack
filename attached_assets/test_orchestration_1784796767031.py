"""
Tests scraper.py's run_scrape orchestration logic using a mocked
Playwright Page -- no real browser or network needed. This covers the
part that couldn't be tested before (multi-URL looping across keyword
+ page_ids, per-URL DOM fallback, blocked/budget handling), since it's
pure control flow that doesn't require a live page.
"""
from dataclasses import dataclass, field
from rate_limiter import RateLimiter
from scraper import run_scrape


class MockResponse:
    def __init__(self, url, method, json_data=None, is_json=True):
        self.url = url
        self.request = type("Req", (), {"method": method})()
        self._json_data = json_data
        self._is_json = is_json

    def json(self):
        if not self._is_json:
            raise ValueError("not json")
        return self._json_data


class MockPage:
    """
    Simulates a scripted sequence of page visits. `script` is a dict
    keyed by URL substring -> behavior spec, so each test can define
    exactly what happens when scraper.py calls page.goto() on a
    particular search URL.
    """
    def __init__(self, script: dict):
        self.script = script
        self._response_handler = None
        self.current_url = None
        self.goto_count = 0

    def on(self, event, handler):
        if event == "response":
            self._response_handler = handler

    def remove_listener(self, event, handler):
        self._response_handler = None

    def _match_script(self, url):
        for key, behavior in self.script.items():
            if key in url:
                return behavior
        raise KeyError(f"No script entry matches url: {url}")

    def goto(self, url, wait_until=None):
        self.current_url = url
        self.goto_count += 1
        behavior = self._match_script(url)
        # Fire any GraphQL responses this behavior specifies
        for resp in behavior.get("graphql_responses", []):
            if self._response_handler:
                self._response_handler(MockResponse(
                    url=resp["url"], method="POST", json_data=resp["json"]
                ))

    def inner_text(self, selector):
        behavior = self._match_script(self.current_url)
        return behavior.get("visible_text", "")

    def evaluate(self, script):
        pass  # scroll no-op

    def wait_for_timeout(self, ms):
        pass  # no real waiting in tests

    def content(self):
        behavior = self._match_script(self.current_url)
        return behavior.get("html", "")


def fast_rate_limiter(max_requests=100):
    return RateLimiter(min_delay_s=0.0, max_delay_s=0.0, max_requests_per_session=max_requests)


def make_graphql_payload(ads):
    edges = []
    for ad in ads:
        edges.append({"node": {
            "collation_id": ad["id"],
            "page_name": ad["name"],
            "snapshot": {"link_url": ad["href"]},
        }})
    return {"data": {"ad_library_main": {"results": {"edges": edges}}}}


# --- Test 1: keyword-only run, clean GraphQL hit ---
def test_keyword_only_clean_graphql():
    payload = make_graphql_payload([
        {"id": "111", "name": "Bright Smile Dental",
         "href": "https://l.facebook.com/l.php?u=https%3A%2F%2Fbrightsmiledental.com%2Fbook&h=x"},
    ])
    page = MockPage({
        "q=dental": {
            "visible_text": "some ads here",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        }
    })
    session = run_scrape(page, fast_rate_limiter(), keyword="dental clinic", country="US")
    assert session.session_status == "ok"
    assert session.urls_attempted == 1
    assert len(session.results) == 1
    assert session.results[0].final_url == "https://brightsmiledental.com/book"
    assert session.results[0].status == "ok"
    assert session.dom_fallback_used is False
    print("PASS: test_keyword_only_clean_graphql")


# --- Test 2: page_ids only, multiple pages, one needs DOM fallback ---
def test_page_ids_mixed_graphql_and_fallback():
    payload_a = make_graphql_payload([
        {"id": "222", "name": "Glow Skincare",
         "href": "https://directbrand.com/offer"},
    ])
    fallback_html = """
    <div><span>Nothing Ventures</span><span>Library ID: 333333333333333</span>
    <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fnventures.com&h=y">Shop</a></div>
    """
    page = MockPage({
        "view_all_page_id=111": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload_a}],
        },
        "view_all_page_id=222": {
            # No graphql response fired at all -> triggers DOM fallback for this URL only
            "visible_text": "ads",
            "graphql_responses": [],
            "html": fallback_html,
        },
    })
    session = run_scrape(page, fast_rate_limiter(), country="US", page_ids=["111", "222"])
    assert session.session_status == "ok"
    assert session.urls_attempted == 2
    assert session.dom_fallback_used is True
    assert session.graphql_hits == 1  # only from page 111
    sources = sorted(r.source for r in session.results)
    assert sources == ["dom_fallback", "graphql"], sources
    print("PASS: test_page_ids_mixed_graphql_and_fallback")


# --- Test 3: combined keyword + page_ids in one run ---
def test_combined_keyword_and_page_ids():
    payload = make_graphql_payload([
        {"id": "444", "name": "Funnel Co", "href": "https://funnelco.com/x"},
    ])
    page = MockPage({
        "q=funnel": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
        "view_all_page_id=999": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
    })
    session = run_scrape(page, fast_rate_limiter(), keyword="funnel audit",
                          country="US", page_ids=["999"])
    assert session.urls_attempted == 2
    assert len(session.results) == 2
    print("PASS: test_combined_keyword_and_page_ids")


# --- Test 4: one page_id blocked, another ok -> partially_blocked ---
def test_partial_block():
    payload = make_graphql_payload([
        {"id": "555", "name": "OK Co", "href": "https://okco.com/x"},
    ])
    page = MockPage({
        "view_all_page_id=111": {
            "visible_text": "Please try again later",  # blocked marker
            "graphql_responses": [],
        },
        "view_all_page_id=222": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
    })
    session = run_scrape(page, fast_rate_limiter(), country="US", page_ids=["111", "222"])
    assert session.session_status == "partially_blocked", session.session_status
    assert session.urls_blocked == 1
    assert len(session.results) == 1
    print("PASS: test_partial_block")


# --- Test 5: all urls blocked -> session blocked ---
def test_all_blocked():
    page = MockPage({
        "view_all_page_id=111": {"visible_text": "unusual activity detected", "graphql_responses": []},
        "view_all_page_id=222": {"visible_text": "checkpoint required", "graphql_responses": []},
    })
    session = run_scrape(page, fast_rate_limiter(), country="US", page_ids=["111", "222"])
    assert session.session_status == "blocked"
    assert len(session.results) == 0
    print("PASS: test_all_blocked")


# --- Test 6: budget exhausted mid-run stops remaining URLs ---
def test_budget_exhausted_stops_early():
    payload = make_graphql_payload([{"id": "666", "name": "X", "href": "https://x.com"}])
    page = MockPage({
        "view_all_page_id=111": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
        "view_all_page_id=222": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
        "view_all_page_id=333": {
            "visible_text": "ads",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        },
    })
    # budget of 1 request -> the FIRST url's own goto() consumes the only
    # allowed request, then its scroll loop immediately hits the budget
    # and that url itself returns 'exhausted_budget' -> loop stops there,
    # so only 1 url ever gets attempted, not 2 or 3.
    limiter = RateLimiter(min_delay_s=0.0, max_delay_s=0.0, max_requests_per_session=1)
    session = run_scrape(page, limiter, country="US", page_ids=["111", "222", "333"])
    assert session.urls_attempted == 1, session.urls_attempted
    assert session.session_status == "exhausted_budget"
    print("PASS: test_budget_exhausted_stops_early")


if __name__ == "__main__":
    test_keyword_only_clean_graphql()
    test_page_ids_mixed_graphql_and_fallback()
    test_combined_keyword_and_page_ids()
    test_partial_block()
    test_all_blocked()
    test_budget_exhausted_stops_early()
    print("\nAll orchestration tests passed against mocked Playwright page.")
