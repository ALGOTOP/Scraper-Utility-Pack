# Live capture step — do this once before trusting scraper.py in production

Everything in this folder is built and tested EXCEPT one thing: the exact
shape of Meta's internal GraphQL response. That can only be seen by loading
the real Ad Library page with network access, which this sandbox doesn't
have. This is a 10-15 minute manual step, then you're done with it.

## Steps

1. Open `https://www.facebook.com/ads/library/` in Chrome or Firefox.
2. Open DevTools (F12 or Cmd+Opt+I) → **Network** tab → filter to **Fetch/XHR**.
3. Run a real search (e.g. country=US, keyword="funnel audit").
4. Scroll down once to trigger a second page of results.
5. Look through the Fetch/XHR requests for one that:
   - Is a **POST** request
   - Has a URL containing `/api/graphql/` (or similar — confirm the exact path)
   - Returns a JSON response containing the ad results (page names, ad text,
     library IDs, links)
6. Click that request → **Response** tab → copy the full JSON.
7. Compare its structure against `_parse_graphql_payload()` in `scraper.py`:
   - Does `payload["data"]["ad_library_main"]["results"]["edges"]` exist?
   - If the path is different, update the `.get(...)` chain in
     `_parse_graphql_payload()` to match the REAL path.
   - Confirm field names: is it `page_name` or `advertiser_name`? Is the
     destination link under `snapshot.link_url`, `snapshot.cta_url`, or
     somewhere else?
8. Update `GRAPHQL_URL_PATTERN` in `scraper.py` if the real endpoint path
   differs from `/api/graphql/`.
9. Run the scraper against this ONE keyword/country combo in Replit and
   manually check 5-10 results against what you see on the actual page,
   before scaling up to scheduled/bulk runs.

## Why this matters for the 90%+ accuracy goal

Everything downstream (the scoring engine, the Claude judgment layer) is
only as good as what comes in. If `_parse_graphql_payload()` is silently
reading the wrong field path, it won't error — it'll just return `None`
for fields it can't find, which then get correctly flagged `needs_review`
by the existing logic. So a wrong field mapping won't cause silent bad
data, but it WILL send everything to the DOM fallback or `needs_review`
queue instead of the fast structured path, which defeats the point of
having it. This step is what makes the fast path actually fast.
