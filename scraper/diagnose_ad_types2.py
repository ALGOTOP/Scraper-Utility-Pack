"""
DIAGNOSTIC ONLY — no code changes.

Produces a concise report for every non-text/link ad card in page.html:
  - ad type, library ID, parser output, all hrefs (categorised), cross-contamination check
  - Prints raw card HTML ONLY when a cross-contamination risk or
    unexpected URL is found (i.e. something worth investigating).

All output goes to stdout so it can be captured to a file.
"""
import sys, textwrap
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from dom_parser import (parse_ad_cards, _find_card_container,
                        _find_outbound_link, LIBRARY_ID_MARKER)
from link_unwrapper import unwrap_destination

# ── Load ──────────────────────────────────────────────────────────────────────
with open("page.html", encoding="utf-8") as f:
    raw_html = f.read()
soup = BeautifulSoup(raw_html, "html.parser")
parsed_by_id = {r["library_id"]: r
                for r in parse_ad_cards(raw_html) if r["library_id"]}

SHIM_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.instagram.com"}
FB_HOSTS   = {"www.facebook.com", "facebook.com", "www.instagram.com",
              "instagram.com", "www.threads.net", "threads.net"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def classify_card(el):
    if el is None:
        return "NO-CONTAINER"
    h = str(el)
    has_video  = "<video" in h
    img_count  = h.lower().count("<img")
    has_shim   = "l.facebook.com" in h
    if has_video:
        return f"VIDEO(imgs={img_count},shim={has_shim})"
    if img_count >= 3:
        return f"CAROUSEL(imgs={img_count},shim={has_shim})"
    if img_count >= 1 and not has_shim:
        return f"IMG-NO-CTA(imgs={img_count})"
    if img_count >= 1:
        return f"IMG+CTA(imgs={img_count})"
    return f"text/link(imgs={img_count},shim={has_shim})"

def all_links(el):
    """Return list of (kind, text, resolved_dest) for every http(s) link in el."""
    rows = []
    if el is None:
        return rows
    for a in el.find_all("a", href=True):
        href = a.get("href", "")
        if not href.startswith(("http://", "https://")):
            continue
        try:
            host = urlparse(href).netloc
        except Exception:
            host = "?"
        text = a.get_text(strip=True)[:50] or "(no text)"
        if "facebook.com/ads/library" in href:
            kind, dest = "ADS-LIB", href[:90]
        elif host in SHIM_HOSTS:
            kind = "SHIM"
            dest = unwrap_destination(href).get("final_url") or f"(bad shim) {href[:60]}"
        elif host in FB_HOSTS:
            kind, dest = "FB-PROF", href[:90]
        else:
            kind, dest = "DIRECT", href[:90]
        rows.append((kind, text, dest))
    return rows

def cross_contamination(id_node, card_el):
    """
    Returns list of hrefs that appear BOTH in this card and in a sibling
    card container at the same DOM level — true cross-contamination.
    Also checks if the card's boundary logic might fail.
    """
    if card_el is None:
        return ["(no container)"]
    card_hrefs = {a.get("href","") for a in card_el.find_all("a", href=True)
                  if a.get("href","").startswith(("http://","https://"))}
    suspects = []
    parent = card_el.parent
    if parent is None:
        return []
    for sib in parent.children:
        if sib is card_el:
            continue
        try:
            sib_text = sib.get_text() if hasattr(sib, "get_text") else ""
        except Exception:
            continue
        if LIBRARY_ID_MARKER not in sib_text:
            continue
        for a in (sib.find_all("a", href=True) if hasattr(sib, "find_all") else []):
            h = a.get("href","")
            if h in card_hrefs and h.startswith(("http://","https://")):
                suspects.append(h[:100])
    return suspects

def card_html_excerpt(el, max_bytes=4000):
    """
    Return the raw HTML of the card but focusing on the most useful section:
    strip the opening deep-nesting preamble (before Library ID) and show
    from Library ID onward, up to max_bytes.
    """
    if el is None:
        return "(no container)"
    full = str(el)
    # Find Library ID in the card HTML and start from a bit before it
    idx = full.find("Library ID:")
    if idx == -1:
        excerpt = full
    else:
        start = max(0, idx - 200)
        excerpt = full[start:]
    if len(excerpt) > max_bytes:
        return excerpt[:max_bytes] + f"\n... [{len(excerpt)-max_bytes} bytes more] ..."
    return excerpt

# ── Scan ──────────────────────────────────────────────────────────────────────
id_nodes = soup.find_all(string=lambda t: t and LIBRARY_ID_MARKER in t)
print(f"Total Library ID nodes: {len(id_nodes)}")
print()

NON_TEXT = ("VIDEO", "CAROUSEL", "IMG-NO-CTA")

rows = []
for node in id_nodes:
    lib_id  = node.split(LIBRARY_ID_MARKER)[-1].strip()
    card    = _find_card_container(node)
    ctype   = classify_card(card)
    parsed  = parsed_by_id.get(lib_id, {})
    links   = all_links(card)
    cross   = cross_contamination(node, card)
    rows.append(dict(lib_id=lib_id, card=card, ctype=ctype,
                     parsed=parsed, links=links, cross=cross))

# ── Summary table (all cards) ─────────────────────────────────────────────────
print(f"{'LibraryID':<20}  {'Type':<30}  {'parser-status':<14}  {'final_url'}")
print("-"*110)
for r in rows:
    url = (r["parsed"].get("final_url") or "")[:55]
    print(f"{r['lib_id']:<20}  {r['ctype']:<30}  {r['parsed'].get('status','?'):<14}  {url}")
print()

# ── Detailed report for non-text/link cards ───────────────────────────────────
non_text_rows = [r for r in rows if any(t in r["ctype"] for t in NON_TEXT)]
print(f"Non-text/link cards: {len(non_text_rows)} of {len(rows)} total")
print()

for r in non_text_rows:
    SEP = "─" * 72
    print(SEP)
    print(f"Library ID : {r['lib_id']}")
    print(f"Card type  : {r['ctype']}")
    print()

    p = r["parsed"]
    print(f"  parse_ad_cards() ► status={p.get('status')}  "
          f"advertiser_name={repr(p.get('advertiser_name'))}  "
          f"final_url={p.get('final_url')}")
    if p.get("raw_href"):
        print(f"                     raw_href={p.get('raw_href')[:100]}")
    print()

    print("  All hrefs in _find_card_container() result:")
    if not r["links"]:
        print("    (none)")
    for kind, text, dest in r["links"]:
        print(f"    [{kind:8s}] text={repr(text):<40}  dest={dest}")
    print()

    if r["cross"]:
        print(f"  ⚠️  CROSS-CONTAMINATION — link(s) shared with a sibling card:")
        for h in r["cross"]:
            print(f"    {h}")
    else:
        print("  Cross-contamination: NONE")
    print()

    # Print raw HTML if cross-contamination found OR if parser returned a URL
    # for an ad that has_cta=False in our classification (potential wrong URL)
    has_cta_in_type = "shim=True" in r["ctype"]
    parser_found_url = bool(p.get("final_url"))
    suspicious = r["cross"] or (parser_found_url and not has_cta_in_type)

    if suspicious:
        print("  ⚠️  Printing raw card HTML (suspicious case):")
        print()
        print(card_html_excerpt(r["card"]))
    else:
        print("  Raw HTML: omitted (no anomaly detected)")
    print()

print("─" * 72)
print("Done.")
