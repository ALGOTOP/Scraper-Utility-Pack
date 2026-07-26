/**
 * worker.ts — DB-backed async job runner.
 *
 * When a scrape job is created, enqueueJob(sessionId) is called.
 * It spawns python3 scraper/run_job.py as a subprocess, reads the
 * JSON output, and writes scored leads to the DB.
 *
 * No Redis needed — jobs are tracked in the scrape_sessions table.
 */
import { spawn } from "child_process";
import path from "path";
import { eq } from "drizzle-orm";
import { db, scrapeSessionsTable, leadsTable } from "@workspace/db";
import { logger } from "./logger.js";

// Resolve scraper directory relative to the repo root.
// __dirname is dist/ at runtime; go up two levels to reach repo root.
const REPO_ROOT = path.resolve(import.meta.dirname, "..", "..", "..", "..");
const SCRAPER_DIR = path.join(REPO_ROOT, "scraper");
const RUN_JOB_SCRIPT = path.join(SCRAPER_DIR, "run_job.py");

export function enqueueJob(sessionId: number): void {
  // Fire-and-forget — don't block the HTTP response
  runJob(sessionId).catch((err) => {
    logger.error({ err, sessionId }, "Unhandled error in job runner");
  });
}

async function runJob(sessionId: number): Promise<void> {
  // Fetch session
  const [session] = await db
    .select()
    .from(scrapeSessionsTable)
    .where(eq(scrapeSessionsTable.id, sessionId));

  if (!session) {
    logger.warn({ sessionId }, "Job not found in DB");
    return;
  }

  logger.info({ sessionId, keyword: session.keyword, country: session.country }, "Starting scrape job");

  // Mark as running
  await db
    .update(scrapeSessionsTable)
    .set({ status: "running" })
    .where(eq(scrapeSessionsTable.id, sessionId));

  // Build args
  const args = ["--country", session.country];
  if (session.keyword) args.push("--keyword", session.keyword);
  if (session.pageIds && (session.pageIds as string[]).length > 0) {
    args.push("--page-ids", (session.pageIds as string[]).join(","));
  }

  try {
    const rawOutput = await spawnPython(args, sessionId);

    // Parse output
    let leads: Record<string, unknown>[];
    try {
      leads = JSON.parse(rawOutput);
    } catch {
      throw new Error(`Invalid JSON from scraper: ${rawOutput.slice(0, 200)}`);
    }

    if (!Array.isArray(leads)) {
      // Could be { error: "..." }
      const asObj = leads as unknown as { error?: string };
      throw new Error(asObj.error ?? "Scraper returned non-array output");
    }

    // Insert leads
    if (leads.length > 0) {
      await db.insert(leadsTable).values(
        leads.map((l) => ({
          sessionId,
          libraryId: (l.library_id as string) ?? null,
          advertiserName: (l.advertiser_name as string) ?? null,
          finalUrl: (l.final_url as string) ?? null,
          rawHref: (l.raw_href as string) ?? null,
          country: session.country,
          score: Number(l.score ?? 0),
          confidence: (l.confidence as string) ?? "low",
          needsReview: Boolean(l.needs_review ?? false),
          reviewStatus: "pending",
          reasons: (l.reasons as string[]) ?? [],
          source: (l.source as string) ?? null,
          adStartDate: l.ad_start_date != null ? Number(l.ad_start_date) : null,
        }))
      );
    }

    // Mark done
    await db
      .update(scrapeSessionsTable)
      .set({ status: "done", resultCount: leads.length, completedAt: new Date() })
      .where(eq(scrapeSessionsTable.id, sessionId));

    logger.info({ sessionId, leadCount: leads.length }, "Scrape job completed");
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    logger.error({ sessionId, err }, "Scrape job failed");

    await db
      .update(scrapeSessionsTable)
      .set({ status: "failed", errorMessage: message, completedAt: new Date() })
      .where(eq(scrapeSessionsTable.id, sessionId));
  }
}

function spawnPython(args: string[], sessionId: number): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("python3", [RUN_JOB_SCRIPT, ...args], {
      cwd: SCRAPER_DIR,
      env: { ...process.env },
    });

    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];

    proc.stdout.on("data", (chunk: Buffer) => stdout.push(chunk));
    proc.stderr.on("data", (chunk: Buffer) => {
      stderr.push(chunk);
      // Stream stderr as debug logs so we can see progress
      logger.debug({ sessionId }, chunk.toString().trim());
    });

    proc.on("close", (code) => {
      if (code !== 0) {
        const errText = Buffer.concat(stderr).toString().slice(-500);
        reject(new Error(`python3 exited with code ${code}: ${errText}`));
      } else {
        resolve(Buffer.concat(stdout).toString());
      }
    });

    proc.on("error", (err) => reject(err));
  });
}
