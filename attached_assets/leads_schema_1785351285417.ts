import { pgTable, serial, text, integer, boolean, timestamp, jsonb, unique } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { scrapeSessionsTable } from "./scrape_sessions";

export const leadsTable = pgTable("leads", {
  id: serial("id").primaryKey(),
  sessionId: integer("session_id")
    .notNull()
    .references(() => scrapeSessionsTable.id),
  libraryId: text("library_id"),
  advertiserName: text("advertiser_name"),
  finalUrl: text("final_url"),
  rawHref: text("raw_href"),
  country: text("country").notNull(),
  score: integer("score").notNull(),
  confidence: text("confidence").notNull(), // high | medium | low
  needsReview: boolean("needs_review").notNull().default(false),
  reviewStatus: text("review_status").notNull().default("pending"), // pending | approved | rejected
  reasons: jsonb("reasons").$type<string[]>().notNull().default([]),
  source: text("source"), // graphql | dom_fallback
  adStartDate: integer("ad_start_date"), // unix timestamp
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
}, (table) => ({
  // Meta's library_id is a stable, globally unique ad identifier.
  // Without this, re-running an overlapping keyword/page-id search
  // inserts a brand new row for an ad already in the table -- this is
  // exactly why a 59-row export turned out to have only 44 distinct
  // businesses. NULL library_id (a genuine parsing miss) is exempt
  // from the constraint since Postgres treats NULLs as distinct.
  uniqueLibraryId: unique("leads_library_id_unique").on(table.libraryId),
}));

export const insertLeadSchema = createInsertSchema(leadsTable).omit({
  id: true,
  createdAt: true,
});
export type InsertLead = z.infer<typeof insertLeadSchema>;
export type Lead = typeof leadsTable.$inferSelect;
