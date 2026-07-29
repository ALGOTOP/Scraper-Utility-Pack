CREATE TABLE "scrape_sessions" (
	"id" serial PRIMARY KEY NOT NULL,
	"keyword" text,
	"page_ids" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"country" text NOT NULL,
	"status" text DEFAULT 'queued' NOT NULL,
	"result_count" integer,
	"error_message" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
CREATE TABLE "leads" (
	"id" serial PRIMARY KEY NOT NULL,
	"session_id" integer NOT NULL,
	"library_id" text,
	"advertiser_name" text,
	"final_url" text,
	"raw_href" text,
	"country" text NOT NULL,
	"score" integer NOT NULL,
	"confidence" text NOT NULL,
	"needs_review" boolean DEFAULT false NOT NULL,
	"review_status" text DEFAULT 'pending' NOT NULL,
	"reasons" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"source" text,
	"ad_start_date" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "leads_library_id_unique" UNIQUE("library_id")
);
--> statement-breakpoint
CREATE TABLE "saved_searches" (
	"id" serial PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"keyword" text,
	"page_ids" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"countries" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "leads" ADD CONSTRAINT "leads_session_id_scrape_sessions_id_fk" FOREIGN KEY ("session_id") REFERENCES "public"."scrape_sessions"("id") ON DELETE no action ON UPDATE no action;