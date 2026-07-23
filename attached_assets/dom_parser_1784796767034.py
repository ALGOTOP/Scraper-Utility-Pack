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
from bs4 import BeautifulSoup
from link_unwrapper import unwrap_destination

LIBRARY_ID_MARKER = "Library ID:"


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

        # Outbound link: first <a> with an http(s) href that isn't a
        # link back into facebook.com/ads/library itself.
        link_tag = _find_outbound_link(card)
        if link_tag:
            record["raw_href"] = link_tag.get("href")
            unwrapped = unwrap_destination(record["raw_href"])
            record["final_url"] = unwrapped["final_url"]
            record["parse_ok"] = unwrapped["parse_ok"]
            record["status"] = "ok" if unwrapped["parse_ok"] else "needs_review"
        else:
            record["status"] = "needs_review"  # no outbound link found at all

        results.append(record)

    return results


def _find_card_container(text_node, max_levels_up: int = 6):
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
    for tag in card.find_all(string=True):
        t = tag.strip()
        if not t or LIBRARY_ID_MARKER in t or t.startswith("Started running"):
            continue
        if len(t) < 60:
            return t
    return None


def _find_outbound_link(card):
    for a in card.find_all("a", href=True):
        href = a["href"]
        if "facebook.com/ads/library" in href:
            continue
        if href.startswith(("http://", "https://")):
            return a
    return None


if __name__ == "__main__":
    # Synthetic fixture standing in for a real ad card. This mirrors the
    # documented structure (Library ID + Started running + outbound CTA
    # link) but the REAL page markup must be captured live and diffed
    # against this before trusting it in production — see the note in
    # the handoff doc.
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
    """

    parsed = parse_ad_cards(fixture_html)
    assert len(parsed) == 3, f"expected 3 cards, got {len(parsed)}"

    assert parsed[0]["library_id"] == "123456789012345"
    assert parsed[0]["final_url"] == "https://brightsmiledental.com/book"
    assert parsed[0]["status"] == "ok"

    assert parsed[1]["library_id"] == "998877665544332"
    assert parsed[1]["status"] == "needs_review"
    assert parsed[1]["final_url"] is None

    assert parsed[2]["library_id"] == "111122223333444"
    assert parsed[2]["status"] == "needs_review"  # broken shim link, no u= param

    for r in parsed:
        print(r)
    print("\nAll DOM fallback parser tests passed against the synthetic fixture.")
