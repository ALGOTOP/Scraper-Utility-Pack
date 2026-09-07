import { spawn, execFileSync } from "child_process";
import fs from "fs"; import path from "path";
import { eq, sql } from "drizzle-orm";
import { db, scrapeSessionsTable, leadsTable } from "@workspace/db";
import { logger } from "./logger.js";
function sqlExcluded(column: string) { return sql.raw(`excluded."${column}"`); }
function findRepoRoot(startDir: string): string { let dir=startDir; for(let i=0;i<10;i++){ if(fs.existsSync(path.join(dir,"pnpm-workspace.yaml"))) return dir; const parent=path.dirname(dir); if(parent===dir) break; dir=parent; } throw new Error(`Could not locate repo root from ${startDir}`); }
function resolvePython3(): string { for(const bin of ["python3","python"]){ try{const r=execFileSync("which",[bin],{encoding:"utf-8"}).trim(); if(r) return r;}catch{} } throw new Error("Could not resolve python3"); }
const REPO_ROOT=findRepoRoot(import.meta.dirname); const SCRAPER_DIR=path.join(REPO_ROOT,"scraper"); const RUN_JOB_SCRIPT=path.join(SCRAPER_DIR,"run_job.py"); const PYTHON_BIN=resolvePython3();
if(!fs.existsSync(RUN_JOB_SCRIPT)) throw new Error(`run_job.py not found at ${RUN_JOB_SCRIPT}`);
logger.info({REPO_ROOT,RUN_JOB_SCRIPT,PYTHON_BIN},"worker.ts paths resolved");
export function enqueueJob(sessionId:number):void{ runJob(sessionId).catch(err=>logger.error({err,sessionId},"Unhandled error in job runner")); }
async function runJob(sessionId:number):Promise<void>{
 const [session]=await db.select().from(scrapeSessionsTable).where(eq(scrapeSessionsTable.id,sessionId)); if(!session){logger.warn({sessionId},"Job not found in DB");return;}
 await db.update(scrapeSessionsTable).set({status:"running"}).where(eq(scrapeSessionsTable.id,sessionId));
 const args=["--country",session.country]; if(session.keyword) args.push("--keyword",session.keyword); if(session.pageIds&&(session.pageIds as string[]).length) args.push("--page-ids",(session.pageIds as string[]).join(","));
 try{
  const rawOutput=await spawnPython(args,sessionId); const leads=JSON.parse(rawOutput); if(!Array.isArray(leads)) throw new Error((leads as {error?:string}).error??"Scraper returned non-array output");
  if(leads.length>0) await db.insert(leadsTable).values(leads.map(l=>({
   sessionId,libraryId:(l.library_id as string)??null,advertiserName:(l.advertiser_name as string)??null,finalUrl:(l.final_url as string)??null,rawHref:(l.raw_href as string)??null,country:session.country,score:Number(l.score??0),confidence:(l.confidence as string)??"low",needsReview:Boolean(l.needs_review??false),reviewStatus:"pending",reasons:(l.reasons as string[])??[],source:(l.source as string)??null,adStartDate:l.ad_start_date!=null?Number(l.ad_start_date):null,icpMismatch:Boolean(l.icp_mismatch??false),icpMismatchReason:(l.icp_mismatch_reason as string)??null,
   productIdentified:Boolean(l.product_identified??false),productEvidence:(l.product_evidence as string)??null,destinationType:(l.destination_type as string)??null,landingOpportunity:(l.landing_opportunity as string)??null,buyerFitStatus:(l.buyer_fit_status as string)??"priority",salesReason:(l.sales_reason as string)??null,searchKeyword:(l.search_keyword as string)??null,
  }))).onConflictDoUpdate({target:leadsTable.libraryId,set:{sessionId,advertiserName:sqlExcluded("advertiser_name"),finalUrl:sqlExcluded("final_url"),rawHref:sqlExcluded("raw_href"),country:sqlExcluded("country"),score:sqlExcluded("score"),confidence:sqlExcluded("confidence"),needsReview:sqlExcluded("needs_review"),reasons:sqlExcluded("reasons"),source:sqlExcluded("source"),adStartDate:sqlExcluded("ad_start_date"),icpMismatch:sqlExcluded("icp_mismatch"),icpMismatchReason:sqlExcluded("icp_mismatch_reason"),productIdentified:sqlExcluded("product_identified"),productEvidence:sqlExcluded("product_evidence"),destinationType:sqlExcluded("destination_type"),landingOpportunity:sqlExcluded("landing_opportunity"),buyerFitStatus:sqlExcluded("buyer_fit_status"),salesReason:sqlExcluded("sales_reason"),searchKeyword:sqlExcluded("search_keyword")}});
  await db.update(scrapeSessionsTable).set({status:"done",resultCount:leads.length,completedAt:new Date()}).where(eq(scrapeSessionsTable.id,sessionId)); logger.info({sessionId,leadCount:leads.length},"Scrape job completed");
 }catch(err){const message=err instanceof Error?err.message:String(err); logger.error({sessionId,err},"Scrape job failed"); await db.update(scrapeSessionsTable).set({status:"failed",errorMessage:message,completedAt:new Date()}).where(eq(scrapeSessionsTable.id,sessionId));}
}
function spawnPython(args:string[],sessionId:number):Promise<string>{return new Promise((resolve,reject)=>{const proc=spawn(PYTHON_BIN,[RUN_JOB_SCRIPT,...args],{cwd:SCRAPER_DIR,env:{...process.env}});const stdout:Buffer[]=[];const stderr:Buffer[]=[];proc.stdout.on("data",c=>stdout.push(c));proc.stderr.on("data",c=>{stderr.push(c);logger.debug({sessionId},c.toString().trim());});proc.on("close",code=>code!==0?reject(new Error(`python3 exited with code ${code}: ${Buffer.concat(stderr).toString().slice(-500)}`)):resolve(Buffer.concat(stdout).toString()));proc.on("error",reject);});}
