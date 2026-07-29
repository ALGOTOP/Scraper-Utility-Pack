"""
One-shot script: fix bare-shortener-root false positives in the leads table.

For every lead whose final_url is a bare fb.me / fb.watch root:
  - Nulls out final_url in the DB (so the fix is durable for the UI too)
  - Re-scores with landing_url=None (triggers needs_review instead of +3)

For every other lead:
  - Re-scores with its existing final_url (idempotent; keeps the DB consistent
    with the updated scoring engine in case any other logic changed)

Reads DATABASE_URL from env. Safe to re-run.
"""
import os, sys, time, csv, io
from pathlib import Path

# Make sure scraper/ is on the path
sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
import psycopg2.extras
from link_unwrapper import _is_bare_shortener_root
from scoring_engine import score_lead
from adapter import TARGET_COUNTRIES

NOW_TS = int(time.time())

def ad_active_days(ad_start_date):
    if not ad_start_date:
        return 0
    return max(0, (NOW_TS - int(ad_start_date)) // 86400)


def rescore(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, advertiser_name, final_url, raw_href,
               country, score, confidence, needs_review, ad_start_date
        FROM leads
        ORDER BY id
    """)
    rows = cur.fetchall()

    patched = 0
    rescored = 0
    updates = []

    for row in rows:
        original_final_url = row["final_url"]
        corrected_final_url = original_final_url

        # Apply the bare-root fix
        if original_final_url and _is_bare_shortener_root(original_final_url):
            corrected_final_url = None
            patched += 1

        record = {
            "business_name":    row["advertiser_name"] or "",
            "country":          row["country"],
            "landing_url":      corrected_final_url,
            "resolution_status": "resolved",   # all stored leads passed the pipeline
            "ad_active_days":   ad_active_days(row["ad_start_date"]),
            "target_countries": TARGET_COUNTRIES,
        }

        result = score_lead(record)

        old = (row["score"], row["confidence"], row["needs_review"])
        new = (result["score"], result["confidence"], result["needs_review"])
        if old != new or corrected_final_url != original_final_url:
            rescored += 1

        updates.append({
            "id":           row["id"],
            "final_url":    corrected_final_url,   # may be nulled
            "score":        result["score"],
            "confidence":   result["confidence"],
            "needs_review": result["needs_review"],
            "reasons":      result["reasons"],
            "old_score":    row["score"],
            "old_conf":     row["confidence"],
        })

    # Bulk update
    update_cur = conn.cursor()
    for u in updates:
        update_cur.execute("""
            UPDATE leads
            SET final_url    = %s,
                score        = %s,
                confidence   = %s,
                needs_review = %s,
                reasons      = %s
            WHERE id = %s
        """, (
            u["final_url"],
            u["score"],
            u["confidence"],
            u["needs_review"],
            psycopg2.extras.Json(u["reasons"]),
            u["id"],
        ))
    conn.commit()

    return updates, patched, rescored


def export_csv(updates):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "score", "old_score", "confidence", "old_confidence",
                     "needs_review", "final_url", "reasons"])
    for u in updates:
        writer.writerow([
            u["id"], u["score"], u["old_score"],
            u["confidence"], u["old_conf"],
            u["needs_review"], u["final_url"] or "",
            "; ".join(u["reasons"]),
        ])
    return buf.getvalue()


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    updates, patched, rescored = rescore(conn)
    conn.close()

    print(f"\nRe-scored {len(updates)} leads total.")
    print(f"  bare-shortener-root nulled : {patched}")
    print(f"  leads with changed output  : {rescored}")

    print("\nChanged leads:")
    changed = [u for u in updates if u["score"] != u["old_score"] or u["confidence"] != u["old_conf"]]
    if changed:
        for u in changed:
            print(f"  id={u['id']:>4}  score {u['old_score']:>2} → {u['score']:>2}  "
                  f"conf {u['old_conf']} → {u['confidence']}  "
                  f"url={u['final_url'] or '(null)'}")
    else:
        print("  (none)")

    # Write CSV export
    out_path = Path(__file__).parent / "leads_rescored.csv"
    out_path.write_text(export_csv(updates))
    print(f"\nFull export written to {out_path}")
