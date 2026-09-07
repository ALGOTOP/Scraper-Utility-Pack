export interface HealthStatus { status: string; }
export interface ApiError { error: string; }
export interface ScrapeJobInput { keyword?: string | null; page_ids?: string[]; country: string; }
export type ScrapeJobStatus = typeof ScrapeJobStatus[keyof typeof ScrapeJobStatus];
export const ScrapeJobStatus = { queued:'queued', running:'running', done:'done', failed:'failed' } as const;
export interface ScrapeJob { id:number; keyword?:string|null; page_ids:string[]; country:string; status:ScrapeJobStatus; result_count?:number|null; error_message?:string|null; created_at:string; completed_at?:string|null; }
export type LeadConfidence = typeof LeadConfidence[keyof typeof LeadConfidence];
export const LeadConfidence = { high:'high', medium:'medium', low:'low' } as const;
export type LeadReviewStatus = typeof LeadReviewStatus[keyof typeof LeadReviewStatus];
export const LeadReviewStatus = { pending:'pending', approved:'approved', rejected:'rejected' } as const;
export interface Lead {
  id:number; library_id?:string|null; advertiser_name?:string|null; final_url?:string|null; raw_href?:string|null; country:string; score:number; confidence:LeadConfidence; needs_review:boolean; review_status:LeadReviewStatus; reasons:string[]; source?:string|null; ad_start_date?:number|null; session_id:number; icp_mismatch:boolean; icp_mismatch_reason?:string|null;
  product_identified:boolean; product_evidence?:string|null; destination_type?:string|null; landing_opportunity?:string|null; buyer_fit_status:string; sales_reason?:string|null; search_keyword?:string|null; created_at:string;
}
export type ScrapeJobDetail = ScrapeJob & { leads:Lead[] };
export interface LeadList { leads:Lead[]; total:number; }
export type LeadReviewInputReviewStatus = typeof LeadReviewInputReviewStatus[keyof typeof LeadReviewInputReviewStatus];
export const LeadReviewInputReviewStatus = { approved:'approved', rejected:'rejected' } as const;
export interface LeadReviewInput { review_status:LeadReviewInputReviewStatus; }
export interface SavedSearchInput { name:string; keyword?:string|null; page_ids?:string[]; countries:string[]; }
export interface SavedSearch { id:number; name:string; keyword?:string|null; page_ids:string[]; countries:string[]; created_at:string; }
export interface CountryStat { country:string; count:number; avg_score?:number|null; }
export interface ScoreBucket { label:string; min:number; max:number; count:number; }
export interface DashboardStats { total_leads:number; avg_score?:number|null; needs_review_count:number; approved_count:number; rejected_count:number; total_jobs:number; running_jobs:number; by_country:CountryStat[]; by_score_bucket:ScoreBucket[]; }
export interface RecentActivity { recent_jobs:ScrapeJob[]; top_leads:Lead[]; }
export type ListJobsParams = { limit?:number; offset?:number; };
export type ListLeadsParams = { score_min?:number; score_max?:number; country?:string; confidence?:ListLeadsConfidence; needs_review?:boolean; review_status?:ListLeadsReviewStatus; session_id?:number; search?:string; limit?:number; offset?:number; sort_by?:ListLeadsSortBy; sort_dir?:ListLeadsSortDir; };
export type ListLeadsConfidence = typeof ListLeadsConfidence[keyof typeof ListLeadsConfidence];
export const ListLeadsConfidence = { high:'high', medium:'medium', low:'low' } as const;
export type ListLeadsReviewStatus = typeof ListLeadsReviewStatus[keyof typeof ListLeadsReviewStatus];
export const ListLeadsReviewStatus = { pending:'pending', approved:'approved', rejected:'rejected' } as const;
export type ListLeadsSortBy = typeof ListLeadsSortBy[keyof typeof ListLeadsSortBy];
export const ListLeadsSortBy = { score:'score', created_at:'created_at', advertiser_name:'advertiser_name' } as const;
export type ListLeadsSortDir = typeof ListLeadsSortDir[keyof typeof ListLeadsSortDir];
export const ListLeadsSortDir = { asc:'asc', desc:'desc' } as const;
export type ExportLeadsParams = { session_id?:number; score_min?:number; review_status?:ExportLeadsReviewStatus; dedupe?:ExportLeadsDedupe; icp_mismatch?:ExportLeadsIcpMismatch; };
export type ExportLeadsReviewStatus = typeof ExportLeadsReviewStatus[keyof typeof ExportLeadsReviewStatus];
export const ExportLeadsReviewStatus = { pending:'pending', approved:'approved', rejected:'rejected' } as const;
export type ExportLeadsDedupe = typeof ExportLeadsDedupe[keyof typeof ExportLeadsDedupe];
export const ExportLeadsDedupe = { business:'business' } as const;
export type ExportLeadsIcpMismatch = typeof ExportLeadsIcpMismatch[keyof typeof ExportLeadsIcpMismatch];
export const ExportLeadsIcpMismatch = { exclude:'exclude', only:'only' } as const;
