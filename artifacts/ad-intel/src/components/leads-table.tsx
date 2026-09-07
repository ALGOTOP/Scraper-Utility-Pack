import { useState } from "react";
import { useListLeads, useReviewLead, useExportLeads, getListLeadsQueryKey, getExportLeadsQueryKey, ListLeadsParams } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, Search, Check, X, ArrowUp, ArrowDown, Sparkles } from "lucide-react";
import { Link, useLocation } from "wouter";
import { useToast } from "@/hooks/use-toast";

const COUNTRIES = ["US", "GB", "AU", "CA", "IE", "NZ", "DE", "NL", "SE", "NO", "DK", "CH", "AE", "SG"];
type QualificationLead = { product_identified?: boolean; product_evidence?: string | null; destination_type?: string | null; landing_opportunity?: string | null; buyer_fit_status?: string | null; sales_reason?: string | null; search_keyword?: string | null };

interface LeadsTableProps { baseFilters?: Partial<ListLeadsParams>; showReviewActions?: boolean; title: string; description: string; }

export function LeadsTable({ baseFilters = {}, showReviewActions = false, title, description }: LeadsTableProps) {
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState<string>("all");
  const [confidence, setConfidence] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"score" | "created_at" | "advertiser_name">("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const queryParams: ListLeadsParams = { ...baseFilters, search: search || undefined, country: country !== "all" ? country : undefined, confidence: confidence !== "all" ? (confidence as any) : undefined, sort_by: sortBy, sort_dir: sortDir, limit: 100 };
  const { data, isLoading, isError } = useListLeads(queryParams);
  const exportParams = { ...baseFilters, score_min: baseFilters.score_min };
  const { refetch: fetchExport } = useExportLeads(exportParams, { query: { queryKey: getExportLeadsQueryKey(exportParams), enabled: false } });
  const reviewLead = useReviewLead(); const queryClient = useQueryClient(); const { toast } = useToast(); const [, setLocation] = useLocation();

  const handleExport = async () => { try { const { data: csv } = await fetchExport(); if (!csv) return; const blob = new Blob([csv as unknown as string], { type: 'text/csv' }); const url = window.URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `sales-ready-leads-${Date.now()}.csv`; document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(url); } catch { toast({ title: "Export failed", variant: "destructive" }); } };
  const handleReview = (id: number, status: 'approved' | 'rejected', e: React.MouseEvent) => { e.stopPropagation(); reviewLead.mutate({ id, data: { review_status: status } }, { onSuccess: () => { toast({ title: `Lead ${status}` }); queryClient.invalidateQueries({ queryKey: getListLeadsQueryKey() }); } }); };
  const toggleSort = (field: "score" | "created_at" | "advertiser_name") => { if (sortBy === field) setSortDir(sortDir === "asc" ? "desc" : "asc"); else { setSortBy(field); setSortDir("desc"); } };
  const SortIcon = ({ field }: { field: string }) => sortBy === field ? (sortDir === "asc" ? <ArrowUp className="w-3 h-3 inline ml-1" /> : <ArrowDown className="w-3 h-3 inline ml-1" />) : null;

  return <div className="space-y-6 animate-in fade-in duration-500">
    <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div><div className="flex items-center gap-2"><h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1><span className="inline-flex items-center gap-1 rounded-full border bg-primary/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-primary"><Sparkles className="h-3 w-3" /> Sales-ready</span></div><p className="text-muted-foreground mt-1 text-sm">{description}</p></div>
      <Button variant="outline" onClick={handleExport} className="flex items-center gap-2"><Download className="w-4 h-4" /> Export CSV</Button>
    </div>
    <div className="bg-card border rounded-md shadow-sm">
      <div className="p-4 border-b flex flex-wrap gap-4 items-center bg-muted/20">
        <div className="relative flex-1 min-w-[200px]"><Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" /><Input placeholder="Search advertisers or reasons..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 bg-background" /></div>
        <Select value={country} onValueChange={setCountry}><SelectTrigger className="w-[140px] bg-background"><SelectValue placeholder="Country" /></SelectTrigger><SelectContent><SelectItem value="all">All Countries</SelectItem>{COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select>
        <Select value={confidence} onValueChange={setConfidence}><SelectTrigger className="w-[140px] bg-background"><SelectValue placeholder="Confidence" /></SelectTrigger><SelectContent><SelectItem value="all">All Confidence</SelectItem><SelectItem value="high">High</SelectItem><SelectItem value="medium">Medium</SelectItem><SelectItem value="low">Low</SelectItem></SelectContent></Select>
      </div>
      <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead className="bg-muted/50 text-muted-foreground uppercase text-xs font-semibold"><tr>
        <th className="px-4 py-3 cursor-pointer hover:text-foreground" onClick={() => toggleSort("advertiser_name")}>Advertiser <SortIcon field="advertiser_name" /></th>
        <th className="px-4 py-3 cursor-pointer hover:text-foreground" onClick={() => toggleSort("score")}>Score <SortIcon field="score" /></th>
        <th className="px-4 py-3">Opportunity</th><th className="px-4 py-3">Product</th>
        <th className="px-4 py-3 cursor-pointer hover:text-foreground" onClick={() => toggleSort("created_at")}>Found Date <SortIcon field="created_at" /></th><th className="px-4 py-3">Status</th>{showReviewActions && <th className="px-4 py-3 text-right">Actions</th>}
      </tr></thead><tbody className="divide-y">
        {isLoading ? <tr><td colSpan={showReviewActions ? 7 : 6} className="p-10 text-center text-muted-foreground">Loading sales-ready prospects...</td></tr> : isError ? <tr><td colSpan={showReviewActions ? 7 : 6} className="p-10 text-center"><div className="font-medium text-destructive">Unable to load prospects</div><div className="text-sm text-muted-foreground mt-1">The API may be restarting or the database migration may still be applying.</div></td></tr> : data?.leads.length === 0 ? <tr><td colSpan={showReviewActions ? 7 : 6} className="p-10 text-center"><div className="font-medium">No sales-ready prospects yet</div><div className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">This view intentionally hides research and rejected leads. Run a fresh scrape and look for prospects scoring 80+ with a verified product and landing-page opportunity.</div></td></tr> : data?.leads.map(lead => {
          const q = lead as typeof lead & QualificationLead;
          return <tr key={lead.id} className="hover:bg-muted/30 cursor-pointer group" onClick={() => setLocation(`/leads/${lead.id}`)}>
            <td className="px-4 py-4 font-medium text-foreground">{lead.advertiser_name || "Unknown"}{lead.final_url && <div className="text-xs font-normal text-muted-foreground truncate max-w-[250px] mt-0.5">{lead.final_url.replace(/^https?:\/\//, '')}</div>}</td>
            <td className="px-4 py-4"><ScoreBadge score={lead.score} /></td>
            <td className="px-4 py-4"><div className="text-xs font-medium capitalize">{q.landing_opportunity?.replace(/_/g, ' ') || '—'}</div><div className="text-xs text-muted-foreground capitalize">{q.destination_type?.replace(/_/g, ' ') || 'Unknown destination'}</div></td>
            <td className="px-4 py-4"><div className="text-xs font-medium">{q.product_identified ? 'Identified' : 'Unclear'}</div><div className="text-xs text-muted-foreground line-clamp-2 max-w-[240px]">{q.product_evidence || 'No product evidence captured.'}</div></td>
            <td className="px-4 py-4 text-muted-foreground text-xs whitespace-nowrap">{new Date(lead.created_at).toLocaleDateString()}</td>
            <td className="px-4 py-4"><StatusBadge status={lead.review_status} /></td>
            {showReviewActions && <td className="px-4 py-4 text-right"><div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity"><Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={(e) => handleReview(lead.id, 'approved', e)}><Check className="h-4 w-4" /></Button><Button size="sm" variant="outline" className="h-7 w-7 p-0" onClick={(e) => handleReview(lead.id, 'rejected', e)}><X className="h-4 w-4" /></Button></div></td>}
          </tr>;
        })}
      </tbody></table></div>
      {data?.total ? <div className="p-4 border-t text-xs text-muted-foreground text-center">Showing {data.leads.length} of {data.total} sales-ready prospects.</div> : null}
    </div>
  </div>;
}
