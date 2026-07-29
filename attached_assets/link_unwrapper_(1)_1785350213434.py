"""
Meta wraps outbound links in a redirect shim (l.facebook.com/l.php?u=...)
or sometimes lm.facebook.com. The real destination is a URL-encoded
query param. This extracts it. If a link is NOT wrapped (some ad types
link directly), it's returned as-is.
"""
from urllib.parse import urlparse, parse_qs, unquote


SHIM_HOSTS = {"l.facebook.com", "lm.facebook.com", "l.instagram.com"}

# Meta's own link-shortener domains. These are redirect *services*, not
# destinations -- a genuinely resolved short link always has something
# after the slash (fb.me/someSlug redirects to a real page/post). A
# bare root (fb.me/ with nothing after it, or nothing at all) means the
# advertiser's own destination link is broken/misconfigured, not that
# they've chosen "a Facebook page" as their site. Scoring that as a
# legitimate resolved destination (SOCIAL_DOMAINS' +3 in scoring_engine)
# rewards a dead link as if it were a real, if lower-quality, funnel.
SHORTENER_ROOTS = {"fb.me", "fb.watch"}


def _is_bare_shortener_root(url: str) -> bool:
    try:
        p = urlparse(url)
    except Exception:
        return False
    return p.netloc in SHORTENER_ROOTS and (not p.path or p.path == "/")


def unwrap_destination(raw_href: str) -> dict:
    """
    Returns {"final_url": str, "was_wrapped": bool, "parse_ok": bool}
    parse_ok=False means this needs to be escalated for manual/AI review
    rather than silently treated as a valid or invalid domain.

    A resolved URL that's just a bare Meta shortener root (fb.me/,
    fb.watch/ with no slug after it) is treated the same as a failed
    resolution -- see SHORTENER_ROOTS above.
    """
    if not raw_href:
        return {"final_url": None, "was_wrapped": False, "parse_ok": False}

    try:
        parsed = urlparse(raw_href)
    except Exception:
        return {"final_url": None, "was_wrapped": False, "parse_ok": False}

    if parsed.netloc not in SHIM_HOSTS:
        # Not a shim link — treat the href itself as the destination
        if parsed.scheme in ("http", "https") and parsed.netloc:
            if _is_bare_shortener_root(raw_href):
                return {"final_url": None, "was_wrapped": False, "parse_ok": False}
            return {"final_url": raw_href, "was_wrapped": False, "parse_ok": True}
        return {"final_url": None, "was_wrapped": False, "parse_ok": False}

    qs = parse_qs(parsed.query)
    if "u" not in qs or not qs["u"]:
        return {"final_url": None, "was_wrapped": True, "parse_ok": False}

    final_url = unquote(qs["u"][0])
    if not final_url.startswith(("http://", "https://")):
        return {"final_url": None, "was_wrapped": True, "parse_ok": False}
    if _is_bare_shortener_root(final_url):
        return {"final_url": None, "was_wrapped": True, "parse_ok": False}

    return {"final_url": final_url, "was_wrapped": True, "parse_ok": True}


if __name__ == "__main__":
    cases = [
        # (input, expected_final_url_or_None, expected_parse_ok)
        ("https://l.facebook.com/l.php?u=https%3A%2F%2Fexample.com%2Flanding&h=abc123",
         "https://example.com/landing", True),
        ("https://directbrand.com/offer", "https://directbrand.com/offer", True),
        ("https://l.facebook.com/l.php?h=abc123", None, False),  # missing u param
        ("", None, False),
        (None, None, False),
        ("javascript:void(0)", None, False),
    ]
    for raw, expected_url, expected_ok in cases:
        result = unwrap_destination(raw)
        assert result["final_url"] == expected_url, f"FAIL on {raw!r}: got {result}"
        assert result["parse_ok"] == expected_ok, f"FAIL on {raw!r}: got {result}"
        print(f"OK  {raw!r:70s} -> {result}")
    print("\nAll link unwrapper tests passed.")
