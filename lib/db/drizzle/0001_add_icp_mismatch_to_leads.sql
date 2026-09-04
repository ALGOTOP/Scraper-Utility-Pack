ALTER TABLE "leads"
ADD COLUMN "icp_mismatch" boolean DEFAULT false NOT NULL;
--> statement-breakpoint
ALTER TABLE "leads"
ADD COLUMN "icp_mismatch_reason" text;
