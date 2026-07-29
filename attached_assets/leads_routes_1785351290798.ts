import { Router, type IRouter } from "express";
import { eq, and, gte, lte, desc, asc, ilike, SQL } from "drizzle-orm";
import { db, leadsTable } from "@workspace/db";
import {
  ListLeadsQueryParams,
  GetLeadParams,
  ReviewLeadParams,
  ReviewLeadBody,
  ExportLeadsQueryParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

function buildLeadResponse(l: typeof leadsTable.$inferSelect) {
  return {
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
  };
}

// GET /leads/export  (must come before /leads/:id to avoid id collision)
router.get("/leads/export", async (req, res): Promise<void> => {
  const parsed = ExportLeadsQueryParams.safeParse(req.query);
  const filters: SQL[] = [];

  if (parsed.success) {
    if (parsed.data.session_id != null) filters.push(eq(leadsTable.sessionId, parsed.data.session_id));
    if (parsed.data.score_min != null) filters.push(gte(leadsTable.score, parsed.data.score_min));
    if (parsed.data.review_status != null) filters.push(eq(leadsTable.reviewStatus, parsed.data.review_status));
  }

  const leads = await db
    .select()
    .from(leadsTable)
    .where(filters.length > 0 ? and(...filters) : undefined)
    .orderBy(desc(leadsTable.score))
    .limit(5000);

  const header = "id,advertiser_name,final_url,country,score,confidence,needs_review,review_status,source,reasons,created_at\n";
  const rows = leads.map((l) =>
    [
      l.id,
      `"${(l.advertiserName ?? "").replace(/"/g, '""')}"`,
      `"${(l.finalUrl ?? "").replace(/"/g, '""')}"`,
      l.country,
      l.score,
      l.confidence,
      l.needsReview,
      l.reviewStatus,
      l.source ?? "",
      `"${(l.reasons ?? []).join(" | ").replace(/"/g, '""')}"`,
      l.createdAt.toISOString(),
    ].join(",")
  );

  res.setHeader("Content-Type", "text/csv");
  res.setHeader("Content-Disposition", "attachment; filename=leads.csv");
  res.send(header + rows.join("\n"));
});

// GET /leads
router.get("/leads", async (req, res): Promise<void> => {
  const parsed = ListLeadsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const {
    score_min, score_max, country, confidence,
    needs_review, review_status, session_id,
    search, limit = 100, offset = 0,
    sort_by = "score", sort_dir = "desc",
  } = parsed.data;

  const filters: SQL[] = [];
  if (score_min != null) filters.push(gte(leadsTable.score, score_min));
  if (score_max != null) filters.push(lte(leadsTable.score, score_max));
  if (country) filters.push(eq(leadsTable.country, country));
  if (confidence) filters.push(eq(leadsTable.confidence, confidence));
  if (needs_review != null) filters.push(eq(leadsTable.needsReview, needs_review));
  if (review_status) filters.push(eq(leadsTable.reviewStatus, review_status));
  if (session_id != null) filters.push(eq(leadsTable.sessionId, session_id));
  if (search) filters.push(ilike(leadsTable.advertiserName, `%${search}%`));

  const ALLOWED_SORT_COLS = { score: leadsTable.score, created_at: leadsTable.createdAt, advertiser_name: leadsTable.advertiserName } as const;
  const sortCol = ALLOWED_SORT_COLS[sort_by as keyof typeof ALLOWED_SORT_COLS] ?? leadsTable.score;
  const orderFn = sort_dir === "asc" ? asc : desc;

  const [leads, countResult] = await Promise.all([
    db
      .select()
      .from(leadsTable)
      .where(filters.length > 0 ? and(...filters) : undefined)
      .orderBy(orderFn(sortCol))
      .limit(limit)
      .offset(offset),
    db
      .select({ id: leadsTable.id })
      .from(leadsTable)
      .where(filters.length > 0 ? and(...filters) : undefined),
  ]);

  res.json({
    leads: leads.map(buildLeadResponse),
    total: countResult.length,
  });
});

// GET /leads/:id
router.get("/leads/:id", async (req, res): Promise<void> => {
  const params = GetLeadParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [lead] = await db
    .select()
    .from(leadsTable)
    .where(eq(leadsTable.id, params.data.id));

  if (!lead) {
    res.status(404).json({ error: "Lead not found" });
    return;
  }

  res.json(buildLeadResponse(lead));
});

// PATCH /leads/:id/review
router.patch("/leads/:id/review", async (req, res): Promise<void> => {
  const params = ReviewLeadParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const body = ReviewLeadBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }

  const [lead] = await db
    .update(leadsTable)
    .set({ reviewStatus: body.data.review_status })
    .where(eq(leadsTable.id, params.data.id))
    .returning();

  if (!lead) {
    res.status(404).json({ error: "Lead not found" });
    return;
  }

  res.json(buildLeadResponse(lead));
});

export default router;
