"""
ICP filter / compatibility layer.

The old implementation only knew a handful of app stores and SaaS names.
That allowed legitimate-but-useless prospects such as Amazon or marketing
agencies to pass through.

The actual buyer-fit model now lives in icp_classifier.py. This module keeps
the existing check_icp_mismatch(business_name, final_url) API for callers that
only have two fields, while also accepting a full ad record when available.
"""
from __future__ import annotations

from icp_classifier import classify_icp


def check_icp_mismatch(business_name, final_url, ad_record=None):
    """
    Return (mismatch, reason).

    For full scraper records, use all available Meta signals. For legacy
    callers that only provide name + URL, build a minimal record so known hard
    exclusions (marketplaces, app stores, obvious agencies/platforms) still
    work.
    """
    record = dict(ad_record or {})
    record.setdefault("business_name", business_name or "")
    record.setdefault("landing_url", final_url)
    record.setdefault("resolution_status", "resolved")

    result = classify_icp(record)
    if result.get("status") == "excluded":
        reasons = result.get("reasons") or ["Outside the target buyer profile"]
        return True, reasons[0]

    return False, None
