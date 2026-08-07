import { Router, type IRouter } from "express";
import { eq, sql, avg, count, desc } from "drizzle-orm";
import { db, leadsTable, scrapeSessionsTable } from "@workspace/db";

const router: IRouter = Router();

// GET /dashboard/stats
router.get("/dashboard/stats", async (_req, res): Promise<void> => {
  const [
    leadsAgg,
    jobsAgg,
    byCountry,
  ] = await Promise.all([
    db.select({
      total_leads: count(leadsTable.id),
      avg_score: avg(leadsTable.score),
      needs_review_count: sql<number>`count(*) filter (where ${leadsTable.needsReview} = true)`,
      approved_count: sql<number>`count(*) filter (where ${leadsTable.reviewStatus} = 'approved')`,
      rejected_count: sql<number>`count(*) filter (where ${leadsTable.reviewStatus} = 'rejected')`,
    }).from(leadsTable),
    db.select({
      total_jobs: count(scrapeSessionsTable.id),
      running_jobs: sql<number>`count(*) filter (where ${scrapeSessionsTable.status} = 'running')`,
    }).from(scrapeSessionsTable),
    db.select({
      country: leadsTable.country,
      count: count(leadsTable.id),
      avg_score: avg(leadsTable.score),
    })
      .from(leadsTable)
      .groupBy(leadsTable.country)
      .orderBy(desc(count(leadsTable.id))),
  ]);

  const stats = leadsAgg[0];
  const jobStats = jobsAgg[0];

  const buckets = [
    { label: "High (7–10)", min: 7, max: 10 },
    { label: "Mid (4–6)", min: 4, max: 6 },
    { label: "Low (0–3)", min: 0, max: 3 },
  ];

  const byScoreBucket = await Promise.all(
    buckets.map(async (b) => {
      const [row] = await db
        .select({ count: count(leadsTable.id) })
        .from(leadsTable)
        .where(
          sql`${leadsTable.score} >= ${b.min} and ${leadsTable.score} <= ${b.max}`
        );
      return { label: b.label, min: b.min, max: b.max, count: Number(row?.count ?? 0) };
    })
  );

  res.json({
    total_leads: Number(stats.total_leads ?? 0),
    avg_score: stats.avg_score != null ? Number(stats.avg_score) : null,
    needs_review_count: Number(stats.needs_review_count ?? 0),
    approved_count: Number(stats.approved_count ?? 0),
    rejected_count: Number(stats.rejected_count ?? 0),
    total_jobs: Number(jobStats.total_jobs ?? 0),
    running_jobs: Number(jobStats.running_jobs ?? 0),
    by_country: byCountry.map((r) => ({
      country: r.country,
      count: Number(r.count),
      avg_score: r.avg_score != null ? Number(r.avg_score) : null,
    })),
    by_score_bucket: byScoreBucket,
  });
});

// GET /dashboard/recent
router.get("/dashboard/recent", async (_req, res): Promise<void> => {
  const [recentJobs, topLeads] = await Promise.all([
    db
      .select()
      .from(scrapeSessionsTable)
      .orderBy(desc(scrapeSessionsTable.createdAt))
      .limit(10),
    db
      .select()
      .from(leadsTable)
      .where(eq(leadsTable.reviewStatus, "pending"))
      .orderBy(desc(leadsTable.score))
      .limit(10),
  ]);

  res.json({
    recent_jobs: recentJobs.map((j) => ({
      id: j.id,
      keyword: j.keyword,
      page_ids: j.pageIds,
      country: j.country,
      status: j.status,
      result_count: j.resultCount,
      error_message: j.errorMessage,
      created_at: j.createdAt,
      completed_at: j.completedAt,
    })),
    top_leads: topLeads.map((l) => ({
      id: l.id,
      library_id: l.libraryId,
      advertiser_name: l.advertiserName,
      final_url: l.finalUrl,
      raw_href: l.rawHref,
      country: l.country,
      score: l.score,
      confidence: l.confidence,
      needs_review: l.needsReview,
      review_status: l.reviewStatus,
      reasons: l.reasons,
      source: l.source,
      ad_start_date: l.adStartDate,
      session_id: l.sessionId,
      created_at: l.createdAt,
    })),
  });
});

export default router;
