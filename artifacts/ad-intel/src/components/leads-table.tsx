import { useState } from "react";
import { useListLeads, useReviewLead, useExportLeads, getListLeadsQueryKey, getExportLeadsQueryKey, ListLeadsParams } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Download, Search, Check, X, ArrowUp, ArrowDown } from "lucide-react";
import { Link, useLocation } from "wouter";
import { useToast } from "@/hooks/use-toast";

const COUNTRIES = ["US", "GB", "AU", "CA", "IE", "NZ", "DE", "NL", "SE", "NO", "DK", "CH", "AE", "SG"];

interface LeadsTableProps {
  baseFilters?: Partial<ListLeadsParams>;
  showReviewActions?: boolean;
  title: string;
  description: string;
}

export function LeadsTable({ baseFilters = {}, showReviewActions = false, title, description }: LeadsTableProps) {
  const [search, setSearch] = useState("");
  const [country, setCountry] = useState<string>("all");
  const [confidence, setConfidence] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"score" | "created_at" | "advertiser_name">("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const queryParams: ListLeadsParams = {
    ...baseFilters,
    search: search || undefined,
    country: country !== "all" ? country : undefined,
    confidence: confidence !== "all" ? (confidence as any) : undefined,
    sort_by: sortBy,
    sort_dir: sortDir,
    limit: 100, // simple single-page for now to keep it clean
  };

  const { data, isLoading } = useListLeads(queryParams);
  const exportParams = { ...baseFilters, score_min: baseFilters.score_min };
  const { refetch: fetchExport } = useExportLeads(exportParams, { query: { queryKey: getExportLeadsQueryKey(exportParams), enabled: false } });
  
  const reviewLead = useReviewLead();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [, setLocation] = useLocation();

  const handleExport = async () => {
    try {
      const { data: csv } = await fetchExport();
      if (!csv) return;
      const blob = new Blob([csv as unknown as string], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `leads-export-${new Date().getTime()}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      toast({ title: "Export failed", variant: "destructive" });
    }
  };

  const handleReview = (id: number, status: 'approved' | 'rejected', e: React.MouseEvent) => {
    e.stopPropagation();
    reviewLead.mutate(
      { id, data: { review_status: status } },
      {
        onSuccess: () => {
          toast({ title: `Lead ${status}` });
          queryClient.invalidateQueries({ queryKey: getListLeadsQueryKey() });
        }
      }
    );
  };

  const toggleSort = (field: "score" | "created_at" | "advertiser_name") => {
    if (sortBy === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortBy !== field) return null;
    return sortDir === "asc" ? <ArrowUp className="w-3 h-3 inline ml-1" /> : <ArrowDown className="w-3 h-3 inline ml-1" />;
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
          <p className="text-muted-foreground mt-1 text-sm">{description}</p>
        </div>
        <Button variant="outline" onClick={handleExport} className="flex items-center gap-2">
          <Download className="w-4 h-4" /> Export CSV
        </Button>
      </div>

      <div className="bg-card border rounded-md shadow-sm">
        <div className="p-4 border-b flex flex-wrap gap-4 items-center bg-muted/20">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Search advertisers or reasons..." 
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 bg-background"
            />
          </div>
          <Select value={country} onValueChange={setCountry}>
            <SelectTrigger className="w-[140px] bg-background">
              <SelectValue placeholder="Country" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Countries</SelectItem>
              {COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={confidence} onValueChange={setConfidence}>
            <SelectTrigger className="w-[140px] bg-background">
              <SelectValue placeholder="Confidence" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Confidence</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-muted/50 text-muted-foreground uppercase text-xs font-semibold">
              <tr>
                <th className="px-4 py-3 cursor-pointer hover:text-foreground transition-colors" onClick={() => toggleSort("advertiser_name")}>
                  Advertiser <SortIcon field="advertiser_name" />
                </th>
                <th className="px-4 py-3 cursor-pointer hover:text-foreground transition-colors" onClick={() => toggleSort("score")}>
                  Score <SortIcon field="score" />
                </th>
                <th className="px-4 py-3">Details</th>
                <th className="px-4 py-3 cursor-pointer hover:text-foreground transition-colors" onClick={() => toggleSort("created_at")}>
                  Found Date <SortIcon field="created_at" />
                </th>
                <th className="px-4 py-3">Status</th>
                {showReviewActions && <th className="px-4 py-3 text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y">
              {isLoading ? (
                <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">Loading leads...</td></tr>
              ) : data?.leads.length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-muted-foreground">No leads match your criteria.</td></tr>
              ) : (
                data?.leads.map(lead => (
                  <tr 
                    key={lead.id} 
                    className="hover:bg-muted/30 cursor-pointer group"
                    onClick={() => setLocation(`/leads/${lead.id}`)}
                  >
                    <td className="px-4 py-4 font-medium text-foreground">
                      {lead.advertiser_name || "Unknown"}
                      {lead.final_url && (
                        <div className="text-xs font-normal text-muted-foreground truncate max-w-[250px] mt-0.5">
                          {lead.final_url.replace(/^https?:\/\//, '')}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4">
                      <ScoreBadge score={lead.score} />
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex gap-2 mb-1">
                        <span className="text-xs uppercase bg-muted px-1.5 py-0.5 rounded font-mono">{lead.country}</span>
                        <span className="text-xs bg-muted px-1.5 py-0.5 rounded capitalize">{lead.confidence}</span>
                      </div>
                      {lead.reasons[0] && (
                        <div className="text-xs text-muted-foreground line-clamp-1 max-w-[300px]">
                          {lead.reasons[0]}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-4 text-muted-foreground text-xs whitespace-nowrap">
                      {new Date(lead.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-4">
                      <StatusBadge status={lead.review_status} />
                    </td>
                    {showReviewActions && (
                      <td className="px-4 py-4 text-right">
                        <div className="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="h-7 w-7 p-0 bg-green-50 hover:bg-green-100 text-green-600 border-green-200"
                            onClick={(e) => handleReview(lead.id, 'approved', e)}
                          >
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button 
                            size="sm" 
                            variant="outline" 
                            className="h-7 w-7 p-0 bg-red-50 hover:bg-red-100 text-red-600 border-red-200"
                            onClick={(e) => handleReview(lead.id, 'rejected', e)}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {data?.total ? (
          <div className="p-4 border-t text-xs text-muted-foreground text-center">
            Showing {data.leads.length} of {data.total} leads.
          </div>
        ) : null}
      </div>
    </div>
  );
}
