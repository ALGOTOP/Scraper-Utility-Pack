"""
DIAGNOSTIC ONLY — no code changes.

For the "funnel audit" / US Ad Library page already saved as page.html,
find cards that are NOT plain text/link-style ads (video, carousel,
image-only) and report:
  1. The raw HTML of the card container (or nearest useful slice)
  2. What parse_ad_cards() currently extracts for it
  3. All <a> hrefs found inside the card container — so we can judge
     whether _find_outbound_link returns the right one or a wrong/adjacent one
  4. An explicit cross-contamination check: do any links in the card's
     ancestor chain come from a sibling card's content?
"""
import sys
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dom_parser import parse_ad_cards, _find_card_container, _find_outbound_link, LIBRARY_ID_MARKER
from link_unwrapper import unwrap_destination

# ── Load page ─────────────────────────────────────────────────────────────────
with open("page.html", encoding="utf-8") as f:
    raw_html = f.read()

soup = BeautifulSoup(raw_html, "html.parser")

# ── Run the parser as-is and index results by library_id ──────────────────────
parsed_results = parse_ad_cards(raw_html)
parsed_by_id = {r["library_id"]: r for r in parsed_results if r["library_id"]}

# ── Helper: classify an ad card ───────────────────────────────────────────────
def classify_card(card_el):
    """
    Returns a string label for what kind of ad this card appears to be,
    based on signals in the rendered HTML.
    """
    if card_el is None:
        return "unknown (no container)"
    card_html = str(card_el)
    has_video   = "<video" in card_html
    img_count   = card_html.lower().count("<img")
    # Carousel heuristic: Meta often renders each carousel frame as a
    # separate <li> or repeating div; look for multiple images in the card.
    is_carousel = img_count >= 3
    is_image    = img_count >= 1 and not has_video
    # Shim links = CTA button; if none, likely lead-gen / awareness / video view
    shim_links  = [a for a in card_el.find_all("a", href=True)
                   if "l.facebook.com" in a.get("href","")]
    has_cta     = bool(shim_links)

    if has_video:
        return f"VIDEO  (imgs={img_count}, has_cta={has_cta})"
    if is_carousel:
        return f"CAROUSEL  (imgs={img_count}, has_cta={has_cta})"
    if is_image and not has_cta:
        return f"IMAGE-ONLY/no-CTA  (imgs={img_count})"
    if is_image and has_cta:
        return f"image+CTA  (imgs={img_count})"
    return f"text/link  (imgs={img_count}, has_cta={has_cta})"

# ── Helper: all hrefs in a container, grouped by type ─────────────────────────
SHIM_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.instagram.com"}
FB_HOSTS   = {"www.facebook.com", "facebook.com", "www.instagram.com",
              "instagram.com", "www.threads.net", "threads.net"}

def categorise_links(card_el):
    rows = []
    for a in card_el.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith(("http://", "https://")):
            continue
        try:
            host = urlparse(href).netloc
        except Exception:
            host = "?"
        label = a.get_text(strip=True)[:60] or "(no text)"
        if host in SHIM_HOSTS:
            kind = "SHIM"
            dest = unwrap_destination(href).get("final_url") or "(bad shim)"
        elif "facebook.com/ads/library" in href:
            kind = "ADS-LIB"
            dest = href[:80]
        elif host in FB_HOSTS:
            kind = "FB-PROFILE"
            dest = href[:80]
        else:
            kind = "DIRECT"
            dest = href[:80]
        rows.append({"kind": kind, "label": label, "dest": dest})
    return rows

# ── Cross-contamination check ─────────────────────────────────────────────────
def check_cross_contamination(id_node, card_el):
    """
    Walk up from the Library ID text node, one level past the card container,
    and check whether any link found inside the card container is also present
    in a SIBLING card's container (i.e., it leaked across card boundaries).
    Returns a list of suspect hrefs.
    """
    if card_el is None:
        return ["NO CONTAINER — could not isolate card at all"]
    # Collect all links that the card container reports
    card_hrefs = set(a.get("href","") for a in card_el.find_all("a", href=True)
                     if a.get("href","").startswith(("http://","https://")))
    # Find a sibling: the card_el's parent's other children that also contain
    # a Library ID (i.e., adjacent ad cards at the same DOM level).
    suspect = []
    parent = card_el.parent
    if parent is None:
        return []
    for sibling in parent.children:
        if sibling is card_el:
            continue
        try:
            sib_text = sibling.get_text() if hasattr(sibling, "get_text") else ""
        except Exception:
            continue
        if LIBRARY_ID_MARKER not in sib_text:
            continue
        # This sibling also contains a Library ID — it's a different ad card.
        # Check if any of its links appear in our card's link set.
        for a in (sibling.find_all("a", href=True) if hasattr(sibling, "find_all") else []):
            h = a.get("href","")
            if h in card_hrefs and h.startswith(("http://","https://")):
                suspect.append(h[:100])
    return suspect

# ── Main scan ─────────────────────────────────────────────────────────────────
id_nodes = soup.find_all(string=lambda t: t and LIBRARY_ID_MARKER in t)
print(f"Total Library ID nodes found: {len(id_nodes)}\n")

NON_TEXT_TYPES = ("VIDEO", "CAROUSEL", "IMAGE-ONLY")
target_cards = []

for node in id_nodes:
    lib_id_raw = node.split(LIBRARY_ID_MARKER)[-1].strip()
    card = _find_card_container(node)
    card_type = classify_card(card)
    # Keep any card that isn't a plain text/link ad
    if any(t in card_type for t in NON_TEXT_TYPES):
        target_cards.append((lib_id_raw, node, card, card_type))

print(f"Non-text/link cards found: {len(target_cards)}")
if not target_cards:
    # Widen search: show all cards with their type so we can see what's there
    print("\nNo VIDEO/CAROUSEL/IMAGE-ONLY cards found with current heuristics.")
    print("Showing ALL cards with type and link summary:\n")
    for node in id_nodes:
        lib_id_raw = node.split(LIBRARY_ID_MARKER)[-1].strip()
        card = _find_card_container(node)
        card_type = classify_card(card)
        parsed = parsed_by_id.get(lib_id_raw, {})
        links = categorise_links(card) if card else []
        print(f"  LibID={lib_id_raw}")
        print(f"    type       : {card_type}")
        print(f"    parser says: status={parsed.get('status')} final_url={parsed.get('final_url')}")
        print(f"    all links  : {[(l['kind'], l['dest'][:60]) for l in links]}")
        print()
    sys.exit(0)

# ── Per-card report ───────────────────────────────────────────────────────────
SEPARATOR = "\n" + "═"*72 + "\n"

for lib_id_raw, node, card, card_type in target_cards[:10]:
    parsed = parsed_by_id.get(lib_id_raw, {})
    links  = categorise_links(card) if card else []
    cross  = check_cross_contamination(node, card)

    print(SEPARATOR)
    print(f"Library ID : {lib_id_raw}")
    print(f"Card type  : {card_type}")
    print()

    # ── What the parser extracted ──
    print("── parse_ad_cards() output ──")
    print(f"  status         : {parsed.get('status', '(not parsed)')}")
    print(f"  advertiser_name: {repr(parsed.get('advertiser_name'))}")
    print(f"  final_url      : {parsed.get('final_url')}")
    print(f"  raw_href       : {(parsed.get('raw_href') or '')[:100]}")
    print()

    # ── Every link in the card container ──
    print("── All <a> hrefs in _find_card_container() result ──")
    if not links:
        print("  (none)")
    for lk in links:
        print(f"  [{lk['kind']:10s}] text={repr(lk['label'])[:50]}  dest={lk['dest'][:80]}")
    print()

    # ── Cross-contamination check ──
    print("── Cross-contamination check ──")
    if cross:
        print(f"  ⚠️  SUSPECT hrefs shared with a sibling card:")
        for h in cross:
            print(f"    {h}")
    else:
        print("  OK — no links found in both this card and a sibling card container")
    print()

    # ── Raw card HTML (trimmed — first 3000 chars is usually enough) ──
    if card is not None:
        card_html = str(card)
        print(f"── Raw card HTML ({len(card_html)} bytes total, showing first 3000) ──")
        print(card_html[:3000])
        if len(card_html) > 3000:
            print(f"\n... [{len(card_html)-3000} bytes truncated] ...")
    else:
        print("── Raw card HTML ──")
        print("  (no container found — _find_card_container returned None)")

print(SEPARATOR)
print("Done.")
