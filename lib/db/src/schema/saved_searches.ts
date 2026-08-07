import { pgTable, serial, text, timestamp, jsonb } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";

export const savedSearchesTable = pgTable("saved_searches", {
  id: serial("id").primaryKey(),
  name: text("name").notNull(),
  keyword: text("keyword"),
  pageIds: jsonb("page_ids").$type<string[]>().notNull().default([]),
  countries: jsonb("countries").$type<string[]>().notNull().default([]),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const insertSavedSearchSchema = createInsertSchema(savedSearchesTable).omit({
  id: true,
  createdAt: true,
});
export type InsertSavedSearch = z.infer<typeof insertSavedSearchSchema>;
export type SavedSearch = typeof savedSearchesTable.$inferSelect;
