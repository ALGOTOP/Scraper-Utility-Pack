"""
Save the real HTML and analyse the DOM structure around Library ID markers
so we can understand why _find_card_container / _find_outbound_link aren't
finding advertiser names and outbound links.
"""
import shutil
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from url_builder import build_search_url

KEYWORD = "funnel audit"
COUNTRY = "US"
CHROMIUM_EXECUTABLE = shutil.which("chromium") or shutil.which("chromium-browser") or None

launch_kwargs = {"headless": True}
if CHROMIUM_EXECUTABLE:
    launch_kwargs["executable_path"] = CHROMIUM_EXECUTABLE

with sync_playwright() as p:
    browser = p.chromium.launch(**launch_kwargs)
    ctx = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    )
    page = ctx.new_page()
    search_url = build_search_url(KEYWORD, country=COUNTRY)
    print(f"Loading: {search_url}")
    try:
        page.goto(search_url, wait_until="networkidle", timeout=35000)
    except Exception as e:
        print(f"[WARN] {e}")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(3000)
    html = page.content()
    browser.close()

# Save raw HTML for reference
with open("page.html", "w", encoding="utf-8") as f:
    f.write(html)
print(f"Saved {len(html)} bytes to scraper/page.html")

LIBRARY_ID_MARKER = "Library ID:"
soup = BeautifulSoup(html, "html.parser")

id_nodes = soup.find_all(string=lambda t: t and LIBRARY_ID_MARKER in t)
print(f"\nFound {len(id_nodes)} nodes containing '{LIBRARY_ID_MARKER}'")

for idx, node in enumerate(id_nodes[:5]):
    library_id = node.split(LIBRARY_ID_MARKER)[-1].strip()
    print(f"\n{'='*60}")
    print(f"Card {idx+1}  Library ID: {library_id}")

    # Walk up and report what each ancestor looks like
    el = node.parent
    for level in range(10):
        if el is None:
            print(f"  level {level}: None — stopped")
            break
        own_text = el.get_text()
        id_count = own_text.count(LIBRARY_ID_MARKER)
        has_a = bool(el.find("a", href=True))
        links = [(a.get("href","")[:80]) for a in el.find_all("a", href=True)[:3]]
        print(f"  level {level}: tag={el.name} id_count={id_count} has_a={has_a}")
        if has_a:
            print(f"    links: {links}")
        if id_count > 1:
            print(f"    *** BOUNDARY — multiple IDs, _find_card_container stops here ***")
            break
        el = el.parent

    # Also show all <a> tags anywhere in vicinity (5 levels up)
    el2 = node.parent
    for _ in range(5):
        if el2 is None: break
        el2 = el2.parent
    if el2:
        nearby_links = [(a.get("href","")[:100]) for a in el2.find_all("a", href=True)
                        if not "facebook.com/ads/library" in a.get("href","")]
        print(f"  Outbound links in 5-level ancestor: {nearby_links[:5]}")
