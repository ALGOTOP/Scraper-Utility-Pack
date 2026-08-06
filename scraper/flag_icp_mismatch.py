"""
One-shot script: backfill icp_mismatch / icp_mismatch_reason for leads
already in the DB, using their existing advertiser_name and final_url
(no re-scrape needed -- those fields never change, only the detection
rules layered on top of them do).

Does not touch score, confidence, needs_review, or reasons.

Reads DATABASE_URL from env. Safe to re-run (idempotent).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import psycopg2
import psycopg2.extras
from icp_filter import check_icp_mismatch


def flag(conn):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT id, advertiser_name, final_url, icp_mismatch, icp_mismatch_reason
        FROM leads
        ORDER BY id
    """)
    rows = cur.fetchall()

    updates = []
    for row in rows:
        icp_mismatch, icp_mismatch_reason = check_icp_mismatch(
            row["advertiser_name"], row["final_url"]
        )
        changed = (
            icp_mismatch != row["icp_mismatch"]
            or icp_mismatch_reason != row["icp_mismatch_reason"]
        )
        updates.append({
            "id": row["id"],
            "advertiser_name": row["advertiser_name"],
            "final_url": row["final_url"],
            "icp_mismatch": icp_mismatch,
            "icp_mismatch_reason": icp_mismatch_reason,
            "changed": changed,
        })

    update_cur = conn.cursor()
    for u in updates:
        update_cur.execute(
            """
            UPDATE leads
            SET icp_mismatch = %s, icp_mismatch_reason = %s
            WHERE id = %s
            """,
            (u["icp_mismatch"], u["icp_mismatch_reason"], u["id"]),
        )
    conn.commit()

    return updates


if __name__ == "__main__":
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    updates = flag(conn)
    conn.close()

    flagged = [u for u in updates if u["icp_mismatch"]]
    print(f"Checked {len(updates)} leads. Flagged {len(flagged)} as icp_mismatch:\n")
    for u in flagged:
        print(f"  id={u['id']:>4}  {u['advertiser_name']!r:40}  {u['final_url']}")
        print(f"        reason: {u['icp_mismatch_reason']}")
