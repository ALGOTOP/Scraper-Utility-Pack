"""
Builds search URLs for Meta's public Ad Library website.
No API key needed — these are URLs a human would type into a browser.

TWO SEARCH MODES (per the requirement that both be supported, configurable
per run):
  - keyword mode:  build_search_url(...)          -> broad discovery
  - page ID mode:  build_search_url_by_page_id(...) -> targeted advertiser list

Same query-string shape for both; only the discovery params differ
(`q=` + search_type for keyword, `view_all_page_id=` for a specific page).
"""
from urllib.parse import urlencode

BASE_URL = "https://www.facebook.com/ads/library/"

def build_search_url(keyword: str, country: str = "US", active_status: str = "active",
                      ad_type: str = "all", media_type: str = "all") -> str:
    """
    country: 2-letter ISO code, e.g. 'US', 'PK', 'GB'
    active_status: 'active' | 'inactive' | 'all'
    """
    params = {
        "active_status": active_status,
        "ad_type": ad_type,
        "country": country,
        "is_targeted_country": "false",
        "media_type": media_type,
        "q": keyword,
        "search_type": "keyword_unordered",
    }
    return f"{BASE_URL}?{urlencode(params)}"


def build_search_url_by_page_id(page_id: str, country: str = "US",
                                 active_status: str = "active",
                                 ad_type: str = "all", media_type: str = "all") -> str:
    """
    Targeted mode: pull every ad from one specific advertiser/page.
    page_id: the numeric Facebook Page ID (found in a page's "Page
    Transparency" section, or from a `page_id` field already captured
    off a prior ad record).
    """
    if not page_id or not str(page_id).strip():
        raise ValueError("page_id is required for build_search_url_by_page_id")
    params = {
        "active_status": active_status,
        "ad_type": ad_type,
        "country": country,
        "is_targeted_country": "false",
        "media_type": media_type,
        "search_type": "page",
        "view_all_page_id": str(page_id).strip(),
    }
    return f"{BASE_URL}?{urlencode(params)}"


def build_search_urls_for_query(keyword: str = None, country: str = "US",
                                 page_ids: list = None, **kwargs) -> list[str]:
    """
    Single entry point matching the 'configurable per run' requirement:
    pass a keyword, a list of page_ids, or both. Returns one URL per
    page_id plus (if given) one keyword-search URL -- run_scrape (in
    scraper.py) iterates this list, so a single ScrapeQuery can mix
    broad discovery with a targeted advertiser list in one run.
    """
    page_ids = page_ids or []
    if not keyword and not page_ids:
        raise ValueError("Provide at least one of: keyword, page_ids")

    urls = []
    if keyword:
        urls.append(build_search_url(keyword, country=country, **kwargs))
    for pid in page_ids:
        urls.append(build_search_url_by_page_id(pid, country=country, **kwargs))
    return urls


if __name__ == "__main__":
    # quick self-test — no network needed, just checking the URL shape
    test_cases = [
        ("dental clinic", "US"),
        ("skincare brand", "PK"),
        ("saas onboarding", "GB"),
    ]
    for kw, cc in test_cases:
        url = build_search_url(kw, cc)
        assert url.startswith(BASE_URL)
        assert f"country={cc}" in url
        assert "q=" in url
        print(url)

    # page-ID mode
    page_url = build_search_url_by_page_id("123456789", country="US")
    assert "view_all_page_id=123456789" in page_url
    assert "search_type=page" in page_url
    print(page_url)

    # missing page_id should raise, not silently build a broken URL
    try:
        build_search_url_by_page_id("")
        raise AssertionError("Expected ValueError on empty page_id")
    except ValueError:
        pass

    # combined mode: keyword + multiple page_ids -> multiple URLs
    combined = build_search_urls_for_query(keyword="funnel audit", country="US",
                                            page_ids=["111", "222"])
    assert len(combined) == 3
    assert "q=funnel" in combined[0]
    assert "view_all_page_id=111" in combined[1]
    assert "view_all_page_id=222" in combined[2]
    print(f"Combined mode produced {len(combined)} URLs as expected.")

    print("\nAll URL builder tests passed.")
