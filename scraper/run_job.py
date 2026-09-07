"""CLI entrypoint: scrape Meta and return only sales-ready prospects."""
from __future__ import annotations
import argparse, dataclasses, json, os, shutil, sys
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from scraper import run_scrape, ScrapeSession
from rate_limiter import RateLimiter, SessionBudgetExceeded
from adapter import adapt_record, TARGET_COUNTRIES
from scoring_engine import score_lead
from icp_filter import check_icp_mismatch


def score_session(session: ScrapeSession, country: str) -> list[dict]:
    output=[]; excluded_count=review_count=priority_count=0
    diagnostics=[]
    for ad in session.results:
        ad_dict=dataclasses.asdict(ad)
        try:
            scored_record,_=adapt_record(ad_dict, country, TARGET_COUNTRIES, search_keyword=session.keyword)
            result=score_lead(scored_record)
            mismatch,mismatch_reason=check_icp_mismatch(scored_record.get("business_name"), scored_record.get("landing_url"), ad_record=scored_record)
            status=result.get("buyer_fit_status", "excluded")
            diagnostics.append({
                "business": scored_record.get("business_name"),
                "score": result.get("score"),
                "status": status,
                "product": result.get("product_evidence"),
                "destination": result.get("destination_type"),
                "ad_days": scored_record.get("ad_active_days"),
                "resolution": scored_record.get("resolution_status"),
                "mismatch": mismatch,
                "reason": (result.get("reasons") or [mismatch_reason or "unknown"])[-1],
            })
            # Primary pool is deliberately quality-first: only a classifier
            # priority with no mismatch reaches PostgreSQL.
            if status != "priority" or mismatch or result.get("icp_mismatch"):
                if status == "review": review_count += 1
                else: excluded_count += 1
                continue
            priority_count += 1
            output.append({
                "library_id": ad_dict.get("library_id"), "advertiser_name": ad_dict.get("advertiser_name"),
                "final_url": ad_dict.get("final_url"), "raw_href": ad_dict.get("raw_href"), "source": ad_dict.get("source"),
                "ad_start_date": ad_dict.get("start_date"), "country": country, "score": int(result["score"]),
                "confidence": result["confidence"], "needs_review": False, "review_status": "pending", "reasons": result["reasons"],
                "icp_mismatch": False, "icp_mismatch_reason": None,
                "product_identified": bool(result.get("product_identified")), "product_evidence": result.get("product_evidence"),
                "destination_type": result.get("destination_type"), "landing_opportunity": result.get("landing_opportunity"),
                "buyer_fit_status": "priority", "sales_reason": result.get("sales_reason"), "search_keyword": session.keyword,
            })
        except Exception as exc:
            print(f"[run_job] Qualification failed for {ad_dict.get('library_id')}: {exc}", file=sys.stderr)
    print(f"[run_job] buyer_fit priority={priority_count} review={review_count} excluded={excluded_count} returned={len(output)}", file=sys.stderr)
    if diagnostics:
        diagnostics.sort(key=lambda x: x.get("score") or 0, reverse=True)
        for d in diagnostics[:12]:
            print(f"[run_job] candidate business={d['business']!r} score={d['score']} status={d['status']} product={d['product']!r} destination={d['destination']} ad_days={d['ad_days']} resolution={d['resolution']} mismatch={d['mismatch']} reason={d['reason']!r}", file=sys.stderr)
    return output


def run_job(keyword, country, page_ids):
    from playwright.sync_api import sync_playwright
    chromium_executable=shutil.which("chromium") or shutil.which("chromium-browser") or None
    launch_kwargs={"headless":True}
    if chromium_executable: launch_kwargs["executable_path"]=chromium_executable
    with sync_playwright() as p:
        browser=p.chromium.launch(**launch_kwargs)
        try:
            context=browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
            page=context.new_page()
            limiter=RateLimiter(min_delay_s=5.0,max_delay_s=10.0,max_requests_per_session=40)
            session=run_scrape(page,limiter,keyword=keyword,country=country,page_ids=page_ids)
        finally: browser.close()
    print(f"[run_job] session_status={session.session_status} urls_attempted={session.urls_attempted} urls_blocked={session.urls_blocked} graphql_hits={session.graphql_hits} dom_fallback_used={session.dom_fallback_used} raw_results={len(session.results)}",file=sys.stderr)
    return score_session(session,country)


def main():
    parser=argparse.ArgumentParser(description="Run a Meta Ad Library scrape job")
    parser.add_argument("--keyword",type=str,default=None)
    parser.add_argument("--country",type=str,required=True)
    parser.add_argument("--page-ids",type=str,default="")
    args=parser.parse_args(); keyword=args.keyword or None; country=args.country.upper(); page_ids=[p.strip() for p in args.page_ids.split(",") if p.strip()] if args.page_ids else []
    if not keyword and not page_ids:
        print(json.dumps({"error":"Provide at least one of --keyword or --page-ids"})); sys.exit(1)
    try: output=run_job(keyword,country,page_ids)
    except Exception as exc:
        print(f"[run_job] Scrape failed: {exc}",file=sys.stderr); print(json.dumps({"error":str(exc)})); sys.exit(1)
    print(json.dumps(output))

if __name__ == "__main__": main()
