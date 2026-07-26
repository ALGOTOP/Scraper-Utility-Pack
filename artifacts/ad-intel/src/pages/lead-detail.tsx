import { useGetLead, useReviewLead, getGetLeadQueryKey } from "@workspace/api-client-react";
import { useParams, Link, useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { ArrowLeft, Check, X, ExternalLink, Calendar, Link as LinkIcon, Database } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function LeadDetail() {
  const params = useParams();
  const id = Number(params.id);
  const { data: lead, isLoading } = useGetLead(id, { query: { enabled: !!id } });
  
  const reviewLead = useReviewLead();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [, setLocation] = useLocation();

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground">Loading lead details...</div>;
  }

  if (!lead) {
    return <div className="p-8 text-center text-muted-foreground">Lead not found.</div>;
  }

  const handleReview = (status: 'approved' | 'rejected') => {
    reviewLead.mutate(
      { id, data: { review_status: status } },
      {
        onSuccess: () => {
          toast({ title: `Lead ${status}` });
          queryClient.invalidateQueries({ queryKey: getGetLeadQueryKey(id) });
          // optionally go back
          setLocation('/leads');
        }
      }
    );
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in duration-500">
      <Button variant="ghost" size="sm" asChild className="mb-4">
        <Link href="/leads"><ArrowLeft className="w-4 h-4 mr-2" /> Back to Leads</Link>
      </Button>

      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-3xl font-bold tracking-tight">{lead.advertiser_name || "Unknown Advertiser"}</h1>
            <ScoreBadge score={lead.score} className="text-base px-3 py-1" />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="flex items-center gap-1 bg-muted px-2 py-0.5 rounded uppercase text-foreground">{lead.country}</span>
            <span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" /> Library ID: {lead.library_id || 'N/A'}</span>
            <span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Found: {new Date(lead.created_at).toLocaleDateString()}</span>
            {lead.ad_start_date && (
               <span className="flex items-center gap-1">Ad Started: {new Date(lead.ad_start_date * 1000).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={lead.review_status} className="text-sm px-3 py-1" />
          {lead.needs_review && lead.review_status === 'pending' && (
            <div className="flex gap-2 mt-2">
              <Button 
                variant="outline" 
                className="bg-green-50 hover:bg-green-100 text-green-700 border-green-200"
                onClick={() => handleReview('approved')}
                disabled={reviewLead.isPending}
              >
                <Check className="w-4 h-4 mr-2" /> Approve
              </Button>
              <Button 
                variant="outline" 
                className="bg-red-50 hover:bg-red-100 text-red-700 border-red-200"
                onClick={() => handleReview('rejected')}
                disabled={reviewLead.isPending}
              >
                <X className="w-4 h-4 mr-2" /> Reject
              </Button>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Scoring Breakdown</CardTitle>
              <CardDescription>Engine analysis and confidence logic</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-6">
                <div className="text-sm font-medium text-muted-foreground mb-1">Confidence Level</div>
                <div className="capitalize font-semibold text-lg">{lead.confidence}</div>
              </div>
              <div className="space-y-3">
                <div className="text-sm font-medium text-muted-foreground">Contributing Factors</div>
                {lead.reasons && lead.reasons.length > 0 ? (
                  <ul className="space-y-2">
                    {lead.reasons.map((r, i) => (
                      <li key={i} className="flex gap-3 text-sm bg-muted/30 p-3 rounded border">
                        <span className="text-primary mt-0.5">•</span>
                        <span className="leading-relaxed">{r}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-muted-foreground">No explicit reasons provided by the scoring engine.</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Target URLs</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {lead.final_url && (
                <div className="space-y-1.5">
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Final URL</div>
                  <a href={lead.final_url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:underline flex items-start gap-2 break-all bg-primary/5 p-2 rounded">
                    <ExternalLink className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    {lead.final_url}
                  </a>
                </div>
              )}
              {lead.raw_href && lead.raw_href !== lead.final_url && (
                <div className="space-y-1.5 mt-4">
                  <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Raw Href (Ad Link)</div>
                  <div className="text-sm text-muted-foreground break-all bg-muted p-2 rounded font-mono text-xs">
                    {lead.raw_href}
                  </div>
                </div>
              )}
              {!lead.final_url && !lead.raw_href && (
                <p className="text-sm text-muted-foreground">No URLs extracted.</p>
              )}
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle>System Data</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between border-b pb-2">
                <span className="text-muted-foreground">Session ID</span>
                <span className="font-mono">{lead.session_id}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-muted-foreground">Needs Review Flag</span>
                <span>{lead.needs_review ? "Yes" : "No"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Lead ID</span>
                <span className="font-mono">{lead.id}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
