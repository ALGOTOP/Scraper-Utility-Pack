import { pgTable, serial, text, integer, timestamp, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const scrapeSessionsTable = pgTable("scrape_sessions", {
  id: serial("id").primaryKey(),
  keyword: text("keyword"),
  pageIds: jsonb("page_ids").$type<string[]>().notNull().default([]),
  country: text("country").notNull(),
  status: text("status").notNull().default("queued"), // queued | running | done | failed
  resultCount: integer("result_count"),
  errorMessage: text("error_message"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

export const insertScrapeSessionSchema = createInsertSchema(scrapeSessionsTable).omit({
  id: true,
  createdAt: true,
});
export type InsertScrapeSession = z.infer<typeof insertScrapeSessionSchema>;
export type ScrapeSession = typeof scrapeSessionsTable.$inferSelect;
