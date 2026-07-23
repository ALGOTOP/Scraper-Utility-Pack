---
name: Meta Ad Library scraper quirks
description: Fixes confirmed against real page (2026-07-23) for the Ad Library scraper
---

Three fixes confirmed against the real Meta Ad Library page (2026-07-23):

**1. "0 results" false-positive (scraper.py NO_RESULTS_MARKERS)**
"0 results" is a substring of "~730 results". Removed it. "no ads match" covers real zero-results pages.

**2. DOM card container depth (dom_parser.py _find_card_container)**
max_levels_up: 6 → 10. Real page links are at DOM depth 7-8; multi-ID boundary is at depth 9.

**3. _find_outbound_link prefers shim links over FB profile links (dom_parser.py)**
Direct www.facebook.com profile links appear first in card DOM but are not landing pages. Must skip them and prefer l.facebook.com shim links.

**GraphQL:** GRAPHQL_URL_PATTERN="/api/graphql/" confirmed correct. Meta rate-limits GraphQL ad-results from Replit's shared IP (code 1675004). DOM fallback is effective primary path in Replit.

**Chromium:** Use system Chromium via Nix — see playwright-nixos.md.
