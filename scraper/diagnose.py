"""
Diagnostic pass — capture ALL GraphQL responses, find the ad-results
payload, print its exact field path, and show visible page text so we
know what state the page is in.
"""
import json
import shutil
from playwright.sync_api import sync_playwright
from url_builder import build_search_url

KEYWORD = "funnel audit"
COUNTRY = "US"
CHROMIUM_EXECUTABLE = shutil.which("chromium") or shutil.which("chromium-browser") or None
GRAPHQL_PATTERN = "/api/graphql/"

all_responses = []

def on_response(response):
    if GRAPHQL_PATTERN in response.url and response.request.method == "POST":
        try:
            data = response.json()
            all_responses.append({"url": response.url, "payload": data})
        except Exception:
            pass

search_url = build_search_url(KEYWORD, country=COUNTRY)
launch_kwargs = {"headless": True}
if CHROMIUM_EXECUTABLE:
    launch_kwargs["executable_path"] = CHROMIUM_EXECUTABLE
    print(f"Using system Chromium: {CHROMIUM_EXECUTABLE}")

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
    page.on("response", on_response)

    print(f"\nNavigating to: {search_url}")
    try:
        page.goto(search_url, wait_until="networkidle", timeout=35000)
    except Exception as e:
        print(f"[WARN] goto: {e}")

    # Scroll 3 times
    for i in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3000)

    visible = page.inner_text("body")
    html = page.content()
    browser.close()

print(f"\nCaptured {len(all_responses)} GraphQL responses.\n")

# Save all to disk
with open("all_captured.json", "w") as f:
    json.dump(all_responses, f, indent=2, default=str)
print("All responses saved to scraper/all_captured.json\n")

# Print visible page text (first 1000 chars)
print("=" * 60)
print("Visible page text (first 1000 chars):")
print(visible[:1000])
print("=" * 60)

# Check for blocked/no-results markers
low = visible.lower()
print("\nBlocked markers present:", any(m in low for m in [
    "please try again later", "unusual activity", "checkpoint", "captcha"]))
print("No-results markers present:", any(m in low for m in ["no ads match", "0 results"]))
print("Library ID present:", "library id" in low)

# Find the response(s) that have ad results (look for 'edges' or ad-like structures)
print("\n--- Scanning responses for ad results ---")
for i, item in enumerate(all_responses):
    p_str = json.dumps(item["payload"], default=str)
    has_edges = "edges" in p_str
    has_error = "errors" in item["payload"]
    has_results = "results" in p_str
    print(f"  Response {i+1}: has_edges={has_edges} has_results={has_results} has_error={has_error} len={len(p_str)}")
    if has_edges:
        # Print a deeper shape
        def print_shape(obj, prefix="", depth=0):
            if depth > 5: return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    print(f"{prefix}{k}:")
                    print_shape(v, prefix+"  ", depth+1)
            elif isinstance(obj, list):
                print(f"{prefix}[list len={len(obj)}]")
                if obj: print_shape(obj[0], prefix+"  [0] ", depth+1)
            else:
                print(f"{prefix}{type(obj).__name__} = {repr(obj)[:80]}")
        print(f"\n  --- Response {i+1} deep shape ---")
        print_shape(item["payload"])

# Check the HTML for Library ID marker
print(f"\n'Library ID:' occurrences in HTML: {html.count('Library ID:')}")

# If we have ad results, try extracting a sample
for item in all_responses:
    try:
        edges = (item["payload"].get("data", {})
                 .get("ad_library_main", {})
                 .get("results", {})
                 .get("edges", []))
        if edges:
            print(f"\nFound {len(edges)} edges with existing field path!")
            node = edges[0].get("node", {})
            print("First node keys:", list(node.keys()))
            print("First node sample:", json.dumps(node, default=str)[:500])
            break
    except Exception:
        pass
