ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "product_identified" boolean NOT NULL DEFAULT false;
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "product_evidence" text;
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "destination_type" text;
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "landing_opportunity" text;
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "buyer_fit_status" text NOT NULL DEFAULT 'excluded';
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "sales_reason" text;
ALTER TABLE "leads" ADD COLUMN IF NOT EXISTS "search_keyword" text;
