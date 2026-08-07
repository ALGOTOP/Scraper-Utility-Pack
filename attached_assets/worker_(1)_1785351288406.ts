/**
 * worker.ts — DB-backed async job runner.
 *
 * When a scrape job is created, enqueueJob(sessionId) is called.
 * It spawns python3 scraper/run_job.py as a subprocess, reads the
 * JSON output, and writes scored leads to the DB.
 *
 * No Redis needed — jobs are tracked in the scrape_sessions table.
 */
import { spawn, execFileSync } from "child_process";
import fs from "fs";
import path from "path";
import { eq, sql } from "drizzle-orm";
import { db, scrapeSessionsTable, leadsTable } from "@workspace/db";
import { logger } from "./logger.js";

// Helper for referencing the incoming (conflicting) row's value inside
// an onConflictDoUpdate set clause -- Postgres's "excluded" pseudo-table.
function sqlExcluded(column: string) {
  return sql.raw(`excluded."${column}"`);
}

// --- Resolve the repo root by walking up from this file until we find
// the workspace marker, instead of hardcoding a fixed number of ".."
// segments. The old fixed-depth version (4 levels) assumed a specific
// bundler output layout (dist/ inside artifacts/api-server/); when the
// esbuild output structure ever shifts by one level, that assumption
// silently breaks and every job fails with a bare `spawn ENOENT`
// against a scraper/ directory that doesn't exist at the wrong path.
// Walking up to a known marker file is layout-independent.
function findRepoRoot(startDir: string): string {
  let dir = startDir;
  for (let i = 0; i < 10; i++) {
    if (fs.existsSync(path.join(dir, "pnpm-workspace.yaml"))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(
    `Could not locate repo root (pnpm-workspace.yaml) walking up from ${startDir}. ` +
      "worker.ts's REPO_ROOT resolution assumption is stale — check the build output layout.",
  );
}

// --- Resolve python3's absolute path once at startup instead of
// relying on Node's inherited PATH at spawn time (which can differ
// between a dev shell and the deployed/bundled process, causing
// `spawn python3 ENOENT` even though `python3` works fine manually).
// Hardcoding a specific Nix store path is *not* the fix here — those
// paths are content-hashed and change on every package/channel bump,
// so a hardcoded path breaks again on the next rebuild. `which` (via
// the shell) is what actually resolves it correctly in both dev and
// deployed environments.
function resolvePython3(): string {
  const candidates = ["python3", "python"];
  for (const bin of candidates) {
    try {
      const resolved = execFileSync("which", [bin], { encoding: "utf-8" }).trim();
      if (resolved) return resolved;
    } catch {
      // try next candidate
    }
  }
  throw new Error(
    "Could not resolve a python3 executable via `which python3` / `which python`. " +
      "Confirm the python-3.11 Nix module is present and on PATH for this process.",
  );
}

const REPO_ROOT = findRepoRoot(import.meta.dirname);
const SCRAPER_DIR = path.join(REPO_ROOT, "scraper");
const RUN_JOB_SCRIPT = path.join(SCRAPER_DIR, "run_job.py");
const PYTHON_BIN = resolvePython3();

// Fail loudly and immediately at startup rather than on the first job —
// this exact path/binary resolution was the root cause of a multi-hour
// debugging session (spawn ENOENT, wrong cwd, stacked with other
// unrelated-looking errors). Better to crash the server on boot with a
// clear message than to silently fail every job.
if (!fs.existsSync(RUN_JOB_SCRIPT)) {
  throw new Error(
    `run_job.py not found at ${RUN_JOB_SCRIPT} (REPO_ROOT resolved to ${REPO_ROOT}). ` +
      "Check the repo layout assumption in worker.ts's findRepoRoot().",
  );
}
logger.info({ REPO_ROOT, RUN_JOB_SCRIPT, PYTHON_BIN }, "worker.ts paths resolved");

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
      // Upsert on library_id: a re-run of an overlapping keyword/page-id
      // search will re-surface ads already in the table. Without this,
      // each re-run added a brand new duplicate row per already-known
      // ad instead of refreshing it -- inflating lead counts and
      // silently multiplying outreach candidates for the same business.
      // Rows with a NULL library_id (a genuine parsing miss) always
      // insert fresh, since Postgres does not treat NULL as a conflict
      // match against the unique constraint.
      await db
        .insert(leadsTable)
        .values(
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
        )
        .onConflictDoUpdate({
          target: leadsTable.libraryId,
          set: {
            sessionId,
            advertiserName: sqlExcluded("advertiser_name"),
            finalUrl: sqlExcluded("final_url"),
            rawHref: sqlExcluded("raw_href"),
            country: sqlExcluded("country"),
            score: sqlExcluded("score"),
            confidence: sqlExcluded("confidence"),
            needsReview: sqlExcluded("needs_review"),
            reasons: sqlExcluded("reasons"),
            source: sqlExcluded("source"),
            adStartDate: sqlExcluded("ad_start_date"),
            // Deliberately NOT overwriting reviewStatus -- if a human
            // already approved/rejected this lead, a re-scrape refreshing
            // its score shouldn't silently reset that decision back to
            // "pending".
          },
        });
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
    const proc = spawn(PYTHON_BIN, [RUN_JOB_SCRIPT, ...args], {
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
