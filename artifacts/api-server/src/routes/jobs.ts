import { Router, type IRouter } from "express";
import { eq, desc } from "drizzle-orm";
import { db, scrapeSessionsTable, leadsTable } from "@workspace/db";
import {
  CreateJobBody,
  ListJobsQueryParams,
  GetJobParams,
} from "@workspace/api-zod";
import { enqueueJob } from "../lib/worker.js";

const router: IRouter = Router();

// GET /jobs
router.get("/jobs", async (req, res): Promise<void> => {
  const parsed = ListJobsQueryParams.safeParse(req.query);
  const limit = parsed.success ? (parsed.data.limit ?? 50) : 50;
  const offset = parsed.success ? (parsed.data.offset ?? 0) : 0;

  const jobs = await db
    .select()
    .from(scrapeSessionsTable)
    .orderBy(desc(scrapeSessionsTable.createdAt))
    .limit(limit)
    .offset(offset);

  res.json(
    jobs.map((j) => ({
      id: j.id,
      keyword: j.keyword,
      page_ids: j.pageIds,
      country: j.country,
      status: j.status,
      result_count: j.resultCount,
      error_message: j.errorMessage,
      created_at: j.createdAt,
      completed_at: j.completedAt,
    }))
  );
});

// POST /jobs
router.post("/jobs", async (req, res): Promise<void> => {
  const parsed = CreateJobBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const { keyword, page_ids, country } = parsed.data;

  if (!keyword && (!page_ids || page_ids.length === 0)) {
    res.status(400).json({ error: "Provide at least one of keyword or page_ids" });
    return;
  }

  const [session] = await db
    .insert(scrapeSessionsTable)
    .values({
      keyword: keyword ?? null,
      pageIds: page_ids ?? [],
      country,
      status: "queued",
    })
    .returning();

  // Kick off the background job (non-blocking)
  enqueueJob(session.id);

  res.status(201).json({
    id: session.id,
    keyword: session.keyword,
    page_ids: session.pageIds,
    country: session.country,
    status: session.status,
    result_count: session.resultCount,
    error_message: session.errorMessage,
    created_at: session.createdAt,
    completed_at: session.completedAt,
  });
});

// GET /jobs/:id
router.get("/jobs/:id", async (req, res): Promise<void> => {
  const params = GetJobParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [session] = await db
    .select()
    .from(scrapeSessionsTable)
    .where(eq(scrapeSessionsTable.id, params.data.id));

  if (!session) {
    res.status(404).json({ error: "Job not found" });
    return;
  }

  const leads = await db
    .select()
    .from(leadsTable)
    .where(eq(leadsTable.sessionId, session.id))
    .orderBy(desc(leadsTable.score));

  res.json({
    id: session.id,
    keyword: session.keyword,
    page_ids: session.pageIds,
    country: session.country,
    status: session.status,
    result_count: session.resultCount,
    error_message: session.errorMessage,
    created_at: session.createdAt,
    completed_at: session.completedAt,
    leads: leads.map((l) => ({
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
