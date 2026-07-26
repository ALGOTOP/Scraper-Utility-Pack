"""
Fallback DOM parser for the Ad Library results page.

Design choice, and why: Meta's CSS class names on this page are
hashed/obfuscated and rotate frequently — anchoring on them is why
most scrapers "break monthly." Instead this anchors on stable TEXT
MARKERS that Meta has kept consistent for years because they're
policy-mandated disclosure text ("Library ID:", "Started running on"),
plus structural signals (an <a> tag with an href, near that marker).

This is still a fallback. The primary path (see scraper.py) should be
intercepting the page's own GraphQL responses, which is far more
reliable — this parser exists for when that interception fails, e.g.
because Meta changed the endpoint or is now embedding the payload
differently. Any card that doesn't cleanly match gets flagged
'needs_review' rather than skipped or guessed at.
"""
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from link_unwrapper import unwrap_destination

LIBRARY_ID_MARKER = "Library ID:"
START_DATE_MARKER = "Started running on"

# Social platform hosts whose shim links should be deprioritised
# in favour of the real advertiser landing page.
_SOCIAL_HOSTS = {
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com",
    "twitter.com", "www.twitter.com",
    "x.com", "www.x.com",
    "tiktok.com", "www.tiktok.com",
    "youtube.com", "www.youtube.com",
    "linkedin.com", "www.linkedin.com",
}

# Zero-width / BOM characters that are invisible but trick an emptiness check.
_ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d", "\ufeff"}


def parse_ad_cards(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []

    # Find every text node containing the Library ID marker — this is
    # the one piece of text Meta must show on every ad card by policy,
    # so it's the most stable anchor available.
    id_nodes = soup.find_all(string=lambda t: t and LIBRARY_ID_MARKER in t)

    for node in id_nodes:
        card = _find_card_container(node)
        record = {"library_id": None, "advertiser_name": None,
                  "raw_href": None, "final_url": None,
                  "start_date": None,
                  "parse_ok": False, "status": "needs_review"}

        try:
            record["library_id"] = node.split(LIBRARY_ID_MARKER)[-1].strip()
        except Exception:
            pass

        if card is None:
            results.append(record)
            continue

        # Advertiser name: first non-empty short text node in the card
        # that isn't the library id / date boilerplate.
        record["advertiser_name"] = _guess_advertiser_name(card)

        # Start date: policy-mandated "Started running on <D Mon YYYY>"
        # disclosure text, same stability rationale as the Library ID
        # marker. Used downstream to compute ad_active_days.
        record["start_date"] = _guess_start_date(card)

        # Outbound link: best shim link from the card, with social-domain
        # deprioritisation.  Returns (tag_or_None, ambiguous: bool).
        link_tag, ambiguous = _find_outbound_link(card)
        if ambiguous:
            # Multiple non-social destinations — don't guess, flag for review.
            record["status"] = "needs_review"
        elif link_tag:
            record["raw_href"] = link_tag.get("href")
            unwrapped = unwrap_destination(record["raw_href"])
            record["final_url"] = unwrapped["final_url"]
            record["parse_ok"] = unwrapped["parse_ok"]
            record["status"] = "ok" if unwrapped["parse_ok"] else "needs_review"
        else:
            record["status"] = "needs_review"  # no outbound link found at all

        results.append(record)

    return results


def _find_card_container(text_node, max_levels_up: int = 10):
    """
    Walk up from the text node to find the enclosing ad-card div.
    Stops (returns None) if a level is reached that contains MORE than
    one 'Library ID:' marker -- that means we've walked past this card's
    boundary into a shared ancestor holding multiple cards, and any <a>
    found from there on could belong to a different ad entirely.
    """
    el = text_node.parent
    for _ in range(max_levels_up):
        if el is None:
            return None
        own_text = el.get_text()
        if own_text.count(LIBRARY_ID_MARKER) > 1:
            return None
        if el.find("a", href=True):
            return el
        el = el.parent
    return None


def _guess_advertiser_name(card):
    """
    Return the first short, non-boilerplate text node in the card.

    Zero-width characters (\\u200b, \\u200c, \\u200d, \\ufeff) are stripped
    before the emptiness check so they don't masquerade as real text and
    get returned instead of the actual advertiser name that follows them.
    """
    for tag in card.find_all(string=True):
        t = tag.strip()
        # BUG 2 FIX: strip zero-width chars before testing emptiness.
        t_clean = "".join(c for c in t if c not in _ZERO_WIDTH_CHARS).strip()
        if not t_clean:
            continue
        if LIBRARY_ID_MARKER in t_clean or t_clean.startswith("Started running"):
            continue
        if len(t_clean) < 60:
            return t_clean
    return None


def _guess_start_date(card):
    """
    Find the "Started running on <D Mon YYYY>" disclosure text in the
    card and parse it into a UTC unix timestamp (midnight that day).
    Returns None if the marker isn't present or the date can't be
    parsed — never raises, per the "defensive, flag don't guess" rule
    that governs the rest of this parser.
    """
    for tag in card.find_all(string=True):
        t_clean = "".join(c for c in tag.strip() if c not in _ZERO_WIDTH_CHARS).strip()
        if t_clean.startswith(START_DATE_MARKER):
            date_part = t_clean[len(START_DATE_MARKER):].strip()
            try:
                dt = datetime.strptime(date_part, "%d %b %Y").replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except ValueError:
                return None
    return None


def _is_social_url(url: str) -> bool:
    from urllib.parse import urlparse
    try:
        return urlparse(url).netloc.lower() in _SOCIAL_HOSTS
    except Exception:
        return False


def _find_outbound_link(card):
    """
    Return (best_link_tag_or_None, ambiguous: bool) for an ad card.

    BUG 1 FIX: when a card has multiple l.facebook.com/shim links pointing
    to different destinations, we now prefer the one whose unwrapped
    destination is NOT on a social platform (instagram.com, facebook.com,
    twitter.com/x.com, tiktok.com, youtube.com, linkedin.com).

    Decision logic:
      • Only one shim  → return it regardless of destination.
      • Multiple shims, all social → return first (legitimately social-only
        presence, nothing better to offer).
      • Multiple shims, exactly one non-social → return the non-social one.
      • Multiple shims, 2+ distinct non-social destinations → return
        (None, True) so the caller flags needs_review rather than guessing.

    Preference order for non-shim fallback (unchanged):
      Any http(s) link that isn't a Facebook-owned domain.
    Direct facebook.com/instagram.com profile links are excluded from the
    fallback — they appear before the CTA in the DOM and would win a naive
    first-match.
    """
    from urllib.parse import urlparse
    SHIM_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.instagram.com"}
    SKIP_HOSTS = {
        "www.facebook.com", "facebook.com", "www.instagram.com",
        "instagram.com", "www.threads.net", "threads.net",
    }

    shim_entries = []   # list of (tag, final_url_or_None)
    direct_link = None

    for a in card.find_all("a", href=True):
        href = a["href"]
        if "facebook.com/ads/library" in href:
            continue
        if not href.startswith(("http://", "https://")):
            continue
        try:
            host = urlparse(href).netloc
        except Exception:
            continue
        if host in SHIM_HOSTS:
            unwrapped = unwrap_destination(href)
            final = unwrapped["final_url"] if unwrapped["parse_ok"] else None
            shim_entries.append((a, final))
        elif host not in SKIP_HOSTS and direct_link is None:
            direct_link = a

    # No shims at all — fall back to the first direct link.
    if not shim_entries:
        return direct_link, False

    # Only one shim — unambiguous, return it.
    if len(shim_entries) == 1:
        return shim_entries[0][0], False

    # Multiple shims — partition by social vs non-social destination.
    non_social = [
        (tag, url) for tag, url in shim_entries
        if url and not _is_social_url(url)
    ]

    if len(non_social) == 0:
        # All resolved destinations are social platforms — that's a
        # legitimate social-only ad; return the first shim as-is.
        return shim_entries[0][0], False

    if len(non_social) == 1:
        # Exactly one real landing page among the shims — this is the CTA.
        return non_social[0][0], False

    # 2+ distinct non-social destinations.  Dedup: if they all resolve to
    # the same URL (e.g. the same link repeated for carousel items) it's
    # unambiguous; otherwise flag for human review.
    distinct_urls = {url for _, url in non_social}
    if len(distinct_urls) == 1:
        return non_social[0][0], False

    return None, True  # ambiguous — caller should set status=needs_review


if __name__ == "__main__":
    # ── Synthetic fixture ─────────────────────────────────────────────────────
    # Mirrors the documented stable structure but the REAL page markup must
    # be captured live and diffed before trusting in production.
    fixture_html = """
    <div class="x1n2onr6">
      <div class="_card_a">
        <span>Bright Smile Dental</span>
        <span>Library ID: 123456789012345</span>
        <span>Started running on 12 Jul 2026</span>
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fbrightsmiledental.com%2Fbook&h=xyz">Book Now</a>
      </div>
    </div>
    <div class="x1n2onr6">
      <div class="_card_b">
        <span>Glow Skincare Co</span>
        <span>Library ID: 998877665544332</span>
        <span>Started running on 1 Jul 2026</span>
        <!-- no outbound link at all -- e.g. lead-gen form ad -->
      </div>
    </div>
    <div class="x1n2onr6">
      <div class="_card_c">
        <span>Nothing Ventures</span>
        <span>Library ID: 111122223333444</span>
        <a href="https://l.facebook.com/l.php?h=broken">Shop</a>
      </div>
    </div>
    <div class="x1n2onr6">
      <div class="_card_d">
        <span>Dahaus Digital</span>
        <span>Library ID: 1937960920417752</span>
        <span>Started running on 20 Jul 2026</span>
        <!-- Instagram follow shim appears FIRST in DOM — should be skipped -->
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fwww.instagram.com%2Fdahausdigital%2F&h=ig1">Follow on Instagram</a>
        <!-- Real CTA shim comes second — this is the one we want -->
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fdahausdigital.com%2Ffree-audit-2&h=cta1">Get Free Audit</a>
      </div>
    </div>
    <div class="x1n2onr6">
      <div class="_card_e">
        \u200bReal Agency Name
        <span>Library ID: 555566667777888</span>
        <span>Started running on 15 Jul 2026</span>
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Frealagency.com%2Foffer&h=xyz">See Offer</a>
      </div>
    </div>
    <div class="x1n2onr6">
      <div class="_card_f">
        <span>Ambiguous Brand</span>
        <span>Library ID: 999911112222333</span>
        <!-- Two different real landing-page shims — should flag needs_review -->
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fbrand-site-a.com%2Foffer&h=a1">Offer A</a>
        <a href="https://l.facebook.com/l.php?u=https%3A%2F%2Fbrand-site-b.com%2Foffer&h=b1">Offer B</a>
      </div>
    </div>
    """

    parsed = parse_ad_cards(fixture_html)
    assert len(parsed) == 6, f"expected 6 cards, got {len(parsed)}"

    # Card A — single shim, resolves cleanly
    assert parsed[0]["library_id"] == "123456789012345"
    assert parsed[0]["final_url"] == "https://brightsmiledental.com/book"
    assert parsed[0]["status"] == "ok"

    # Card B — no outbound link
    assert parsed[1]["library_id"] == "998877665544332"
    assert parsed[1]["status"] == "needs_review"
    assert parsed[1]["final_url"] is None

    # Card C — broken shim (no u= param)
    assert parsed[2]["library_id"] == "111122223333444"
    assert parsed[2]["status"] == "needs_review"

    # Card D — BUG 1: Instagram shim before real CTA shim; must return the CTA
    assert parsed[3]["library_id"] == "1937960920417752"
    assert parsed[3]["final_url"] == "https://dahausdigital.com/free-audit-2", \
        f"BUG 1 not fixed — got {parsed[3]['final_url']!r}"
    assert parsed[3]["status"] == "ok"

    # Card E — BUG 2: zero-width space before real name; must return the real name
    assert parsed[4]["library_id"] == "555566667777888"
    assert parsed[4]["advertiser_name"] == "Real Agency Name", \
        f"BUG 2 not fixed — got {parsed[4]['advertiser_name']!r}"

    # Card F — two distinct non-social shims — must be flagged needs_review
    assert parsed[5]["library_id"] == "999911112222333"
    assert parsed[5]["status"] == "needs_review", \
        f"ambiguous multi-shim should be needs_review, got {parsed[5]['status']!r}"
    assert parsed[5]["final_url"] is None, \
        f"ambiguous multi-shim should not pick a URL, got {parsed[5]['final_url']!r}"

    for r in parsed:
        print(r)
    print("\nAll DOM fallback parser tests passed against the synthetic fixture.")
