import { pgTable, serial, text, integer, boolean, timestamp, jsonb } from "drizzle-orm/pg-core";
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
});

export const insertLeadSchema = createInsertSchema(leadsTable).omit({
  id: true,
  createdAt: true,
});
export type InsertLead = z.infer<typeof insertLeadSchema>;
export type Lead = typeof leadsTable.$inferSelect;
