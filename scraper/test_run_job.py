"""
Tests run_job.py's score_session() -- the function that converts a
ScrapeSession (as returned by scraper.run_scrape) into the list of
scored lead dicts the Node worker inserts into the DB.

This is the layer that was completely uncovered before: test_orchestration.py
only tests run_scrape() in isolation, and nothing exercised the
run_scrape() -> score_session() hand-off, which is exactly where the
original bugs were (wrong call signature, ScrapedAd dataclasses treated
as dicts). These tests build a ScrapeSession the same way run_scrape()
would (via a mocked Playwright page, reusing test_orchestration's
MockPage/make_graphql_payload helpers) and assert on score_session()'s
output shape and values -- no real browser or network needed.
"""
from rate_limiter import RateLimiter
from scraper import run_scrape
from run_job import score_session
import test_orchestration as helpers


def fast_rate_limiter(max_requests=100):
    return RateLimiter(min_delay_s=0.0, max_delay_s=0.0, max_requests_per_session=max_requests)


def test_score_session_keyword_only_produces_scored_lead():
    payload = helpers.make_graphql_payload([
        {"id": "111", "name": "Bright Smile Dental",
         "href": "https://l.facebook.com/l.php?u=https%3A%2F%2Fbrightsmiledental.com%2Fbook&h=x"},
    ])
    page = helpers.MockPage({
        "q=dental": {
            "visible_text": "some ads here",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload}],
        }
    })
    session = run_scrape(page, fast_rate_limiter(), keyword="dental clinic", country="US")
    assert len(session.results) == 1  # sanity check on the fixture itself

    output = score_session(session, country="US")

    assert len(output) == 1
    lead = output[0]

    # Every field the Node worker's INSERT depends on must be present
    # and of the right shape -- this is the exact contract that used to
    # break silently when run_job.py assumed dicts instead of dataclasses.
    for key in (
        "library_id", "advertiser_name", "final_url", "raw_href", "source",
        "ad_start_date", "country", "score", "confidence", "needs_review",
        "review_status", "reasons",
    ):
        assert key in lead, f"missing key: {key}"

    assert lead["library_id"] == "111"
    assert lead["advertiser_name"] == "Bright Smile Dental"
    assert lead["country"] == "US"
    assert lead["review_status"] == "pending"
    assert isinstance(lead["score"], int)
    assert lead["confidence"] in ("high", "medium", "low")
    assert isinstance(lead["needs_review"], bool)
    assert isinstance(lead["reasons"], list)

    # Regression guard: confidence must come from scoring_engine.score_lead,
    # not be recomputed with a second, separate threshold in run_job.py.
    from scoring_engine import score_lead
    from adapter import adapt_record, TARGET_COUNTRIES
    import dataclasses
    ad_dict = dataclasses.asdict(session.results[0])
    expected_record, _ = adapt_record(ad_dict, session_country="US", target_countries=TARGET_COUNTRIES)
    expected = score_lead(expected_record)
    assert lead["score"] == expected["score"]
    assert lead["confidence"] == expected["confidence"]
    assert lead["needs_review"] == expected["needs_review"]
    assert lead["reasons"] == expected["reasons"]
    print("PASS: test_score_session_keyword_only_produces_scored_lead")


def test_score_session_handles_needs_review_and_dom_fallback():
    # One clean graphql hit, one page-id that triggers DOM fallback via
    # a "Library ID:" anchored card -- mirrors test_orchestration's
    # test_page_ids_mixed_graphql_and_fallback fixture so the DOM path
    # is covered by score_session() too, not just run_scrape().
    payload_a = helpers.make_graphql_payload([
        {"id": "222", "name": "Glow Skincare", "href": "https://directbrand.com/offer"},
    ])
    page = helpers.MockPage({
        "id=222": {
            "visible_text": "some ads here",
            "graphql_responses": [{"url": "/api/graphql/", "json": payload_a}],
        },
    })
    session = run_scrape(page, fast_rate_limiter(), page_ids=["222"], country="GB")
    output = score_session(session, country="GB")

    assert len(output) == len(session.results)
    for lead in output:
        assert lead["country"] == "GB"
        assert lead["confidence"] in ("high", "medium", "low")
    print("PASS: test_score_session_handles_needs_review_and_dom_fallback")


def test_score_session_empty_results_returns_empty_list():
    session = run_scrape(
        helpers.MockPage({"q=nomatch": {"visible_text": "no ads match your search"}}),
        fast_rate_limiter(),
        keyword="nomatch",
        country="US",
    )
    output = score_session(session, country="US")
    assert output == []
    print("PASS: test_score_session_empty_results_returns_empty_list")


if __name__ == "__main__":
    test_score_session_keyword_only_produces_scored_lead()
    test_score_session_handles_needs_review_and_dom_fallback()
    test_score_session_empty_results_returns_empty_list()
    print("\nAll run_job scoring tests passed against mocked Playwright page.")
