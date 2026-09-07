import { useGetLead, useReviewLead, getGetLeadQueryKey } from "@workspace/api-client-react";
import { useParams, Link, useLocation } from "wouter";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { ArrowLeft, Check, X, ExternalLink, Calendar, Database, Sparkles, Target, Globe, Megaphone } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

export function LeadDetail() {
  const params = useParams();
  const id = Number(params.id);
  const { data: lead, isLoading, isError } = useGetLead(id, { query: { queryKey: getGetLeadQueryKey(id), enabled: Number.isFinite(id) && id > 0 } });
  const reviewLead = useReviewLead();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [, setLocation] = useLocation();

  if (isLoading) return <div className="p-8 text-center text-muted-foreground">Loading prospect details...</div>;
  if (isError || !lead) return <div className="space-y-4 p-8 text-center"><p className="text-muted-foreground">Prospect not found or unavailable.</p><Button variant="outline" asChild><Link href="/leads"><ArrowLeft className="w-4 h-4 mr-2" /> Back to Leads</Link></Button></div>;

  const handleReview = (status: 'approved' | 'rejected') => {
    reviewLead.mutate({ id, data: { review_status: status } }, { onSuccess: () => { toast({ title: `Lead ${status}` }); queryClient.invalidateQueries({ queryKey: getGetLeadQueryKey(id) }); setLocation('/leads'); } });
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in duration-500">
      <Button variant="ghost" size="sm" asChild><Link href="/leads"><ArrowLeft className="w-4 h-4 mr-2" /> Back to Sales-ready Leads</Link></Button>

      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3 mb-2"><h1 className="text-2xl sm:text-3xl font-bold tracking-tight break-words">{lead.advertiser_name || "Unknown Advertiser"}</h1><ScoreBadge score={lead.score} className="text-sm px-3 py-1" /><span className="inline-flex items-center gap-1 rounded-full border bg-primary/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-primary"><Sparkles className="h-3 w-3" /> {lead.buyer_fit_status || "qualified"}</span></div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground"><span className="bg-muted px-2 py-0.5 rounded uppercase text-foreground">{lead.country}</span><span className="flex items-center gap-1"><Database className="w-3.5 h-3.5" /> Library {lead.library_id || 'N/A'}</span><span className="flex items-center gap-1"><Calendar className="w-3.5 h-3.5" /> Found {new Date(lead.created_at).toLocaleDateString()}</span>{lead.search_keyword && <span>Search: <strong className="text-foreground">{lead.search_keyword}</strong></span>}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0"><StatusBadge status={lead.review_status} className="text-sm px-3 py-1" />{lead.needs_review && lead.review_status === 'pending' && <><Button variant="outline" onClick={() => handleReview('approved')} disabled={reviewLead.isPending}><Check className="w-4 h-4 mr-2" /> Approve</Button><Button variant="outline" onClick={() => handleReview('rejected')} disabled={reviewLead.isPending}><X className="w-4 h-4 mr-2" /> Reject</Button></>}</div>
      </div>

      <Card className="border-primary/20 bg-primary/[0.02]"><CardHeader><CardTitle className="flex items-center gap-2"><Target className="h-5 w-5 text-primary" /> Why this prospect is sellable</CardTitle><CardDescription>Evidence supporting the $499 dedicated product landing-page offer.</CardDescription></CardHeader><CardContent><p className="text-sm leading-6">{lead.sales_reason || "No sales rationale was captured for this prospect."}</p></CardContent></Card>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <Card><CardHeader><CardTitle>Qualification</CardTitle><CardDescription>What the engine verified before admitting this prospect.</CardDescription></CardHeader><CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Signal icon={Megaphone} label="Ad intent" value={lead.ad_start_date ? `Active since ${new Date(lead.ad_start_date * 1000).toLocaleDateString()}` : "Active ad signal captured"} />
            <Signal icon={Target} label="Product" value={lead.product_identified ? "Specific product identified" : "Product unclear"} detail={lead.product_evidence || undefined} />
            <Signal icon={Globe} label="Destination" value={lead.destination_type?.replace(/_/g, " ") || "Unknown"} />
            <Signal icon={Target} label="Landing opportunity" value={lead.landing_opportunity?.replace(/_/g, " ") || "Not specified"} />
          </CardContent></Card>

          <Card><CardHeader><CardTitle>Scoring Breakdown</CardTitle><CardDescription>Engine reasons and confidence.</CardDescription></CardHeader><CardContent><div className="mb-5"><div className="text-sm font-medium text-muted-foreground mb-1">Confidence</div><div className="capitalize font-semibold">{lead.confidence}</div></div>{lead.reasons?.length ? <ul className="space-y-2">{lead.reasons.map((r, i) => <li key={i} className="flex gap-3 text-sm bg-muted/30 p-3 rounded border"><span className="text-primary mt-0.5">•</span><span className="leading-relaxed">{r}</span></li>)}</ul> : <p className="text-sm text-muted-foreground">No explicit scoring reasons provided.</p>}</CardContent></Card>
        </div>

        <div className="space-y-6">
          <Card><CardHeader><CardTitle>Target URLs</CardTitle></CardHeader><CardContent className="space-y-4">
            {lead.library_id && <UrlField label="Ad Library" href={`https://www.facebook.com/ads/library/?id=${lead.library_id}`} />}
            {lead.final_url && <UrlField label="Final URL" href={lead.final_url} />}
            {lead.raw_href && lead.raw_href !== lead.final_url && <div><div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1">Raw Ad Link</div><div className="text-xs text-muted-foreground break-all bg-muted p-2 rounded font-mono">{lead.raw_href}</div></div>}
          </CardContent></Card>
          <Card><CardHeader><CardTitle>System Data</CardTitle></CardHeader><CardContent className="space-y-3 text-sm"><Row label="Session ID" value={String(lead.session_id)} /><Row label="Lead ID" value={String(lead.id)} /><Row label="Review flag" value={lead.needs_review ? "Yes" : "No"} /></CardContent></Card>
        </div>
      </div>
    </div>
  );
}

function Signal({ icon: Icon, label, value, detail }: { icon: any; label: string; value: string; detail?: string }) { return <div className="rounded-md border bg-background p-4"><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground"><Icon className="h-4 w-4" />{label}</div><div className="mt-2 text-sm font-semibold capitalize">{value}</div>{detail && <div className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</div>}</div>; }
function UrlField({ label, href }: { label: string; href: string }) { return <div className="space-y-1.5"><div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{label}</div><a href={href} target="_blank" rel="noreferrer" className="text-xs text-primary hover:underline flex items-start gap-2 break-all bg-primary/5 p-2 rounded"><ExternalLink className="w-4 h-4 flex-shrink-0" />{href}</a></div>; }
function Row({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-4 border-b pb-2 last:border-0"><span className="text-muted-foreground">{label}</span><span className="font-mono text-right">{value}</span></div>; }
