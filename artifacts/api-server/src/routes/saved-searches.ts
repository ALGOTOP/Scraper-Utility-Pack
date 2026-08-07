import { Router, type IRouter } from "express";
import { eq, desc } from "drizzle-orm";
import { db, savedSearchesTable } from "@workspace/db";
import {
  CreateSavedSearchBody,
  DeleteSavedSearchParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

function buildSavedSearchResponse(s: typeof savedSearchesTable.$inferSelect) {
  return {
    id: s.id,
    name: s.name,
    keyword: s.keyword,
    page_ids: s.pageIds,
    countries: s.countries,
    created_at: s.createdAt,
  };
}

// GET /saved-searches
router.get("/saved-searches", async (_req, res): Promise<void> => {
  const searches = await db
    .select()
    .from(savedSearchesTable)
    .orderBy(desc(savedSearchesTable.createdAt));

  res.json(searches.map(buildSavedSearchResponse));
});

// POST /saved-searches
router.post("/saved-searches", async (req, res): Promise<void> => {
  const parsed = CreateSavedSearchBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }

  const { name, keyword, page_ids, countries } = parsed.data;

  if (!keyword && (!page_ids || page_ids.length === 0)) {
    res.status(400).json({ error: "Provide at least one of keyword or page_ids" });
    return;
  }

  const [search] = await db
    .insert(savedSearchesTable)
    .values({
      name,
      keyword: keyword ?? null,
      pageIds: page_ids ?? [],
      countries: countries ?? [],
    })
    .returning();

  res.status(201).json(buildSavedSearchResponse(search));
});

// DELETE /saved-searches/:id
router.delete("/saved-searches/:id", async (req, res): Promise<void> => {
  const params = DeleteSavedSearchParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }

  const [deleted] = await db
    .delete(savedSearchesTable)
    .where(eq(savedSearchesTable.id, params.data.id))
    .returning();

  if (!deleted) {
    res.status(404).json({ error: "Saved search not found" });
    return;
  }

  res.sendStatus(204);
});

export default router;
