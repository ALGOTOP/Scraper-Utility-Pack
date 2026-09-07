import { pgTable, serial, text, integer, boolean, timestamp, jsonb, unique } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod/v4";
import { scrapeSessionsTable } from "./scrape_sessions";

export const leadsTable = pgTable("leads", {
  id: serial("id").primaryKey(),
  sessionId: integer("session_id").notNull().references(() => scrapeSessionsTable.id),
  libraryId: text("library_id"), advertiserName: text("advertiser_name"), finalUrl: text("final_url"), rawHref: text("raw_href"),
  country: text("country").notNull(), score: integer("score").notNull(), confidence: text("confidence").notNull(),
  needsReview: boolean("needs_review").notNull().default(false), reviewStatus: text("review_status").notNull().default("pending"),
  reasons: jsonb("reasons").$type<string[]>().notNull().default([]), source: text("source"), adStartDate: integer("ad_start_date"),
  icpMismatch: boolean("icp_mismatch").notNull().default(false), icpMismatchReason: text("icp_mismatch_reason"),
  productIdentified: boolean("product_identified").notNull().default(false),
  productEvidence: text("product_evidence"),
  destinationType: text("destination_type"),
  landingOpportunity: text("landing_opportunity"),
  buyerFitStatus: text("buyer_fit_status").notNull().default("excluded"),
  salesReason: text("sales_reason"),
  searchKeyword: text("search_keyword"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
}, (table) => ({ uniqueLibraryId: unique("leads_library_id_unique").on(table.libraryId) }));

export const insertLeadSchema = createInsertSchema(leadsTable).omit({ id: true, createdAt: true });
export type InsertLead = z.infer<typeof insertLeadSchema>;
export type Lead = typeof leadsTable.$inferSelect;
