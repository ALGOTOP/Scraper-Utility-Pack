import { useState } from "react";
import { useListJobs, useCreateJob, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/badges";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

const COUNTRIES = ["US", "GB", "AU", "CA", "IE", "NZ", "DE", "NL", "SE", "NO", "DK", "CH", "AE", "SG"];
const EXAMPLE_KEYWORDS = ["beauty products", "sunscreen", "skincare serum", "lip balm"];

export function Jobs() {
  const { data: jobs, isLoading, isError } = useListJobs(undefined, { query: { queryKey: getListJobsQueryKey(), refetchInterval: (query) => query.state.data?.some((job) => job.status === "queued" || job.status === "running") ? 5000 : false } });
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("US");
  const [pageIds, setPageIds] = useState("");
  const createJob = useCreateJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() && !pageIds.trim()) { toast({ title: "Search required", description: "Enter a product keyword or page IDs.", variant: "destructive" }); return; }
    const ids = pageIds.split(",").map(s => s.trim()).filter(Boolean);
    createJob.mutate({ data: { keyword: keyword.trim() || undefined, country, page_ids: ids.length ? ids : undefined } }, { onSuccess: () => { toast({ title: "Job queued", description: "The scraper is now processing the search." }); setKeyword(""); setPageIds(""); queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() }); }, onError: (err) => toast({ title: "Failed to start job", description: err?.data?.error ?? err?.message ?? "Unknown error", variant: "destructive" }) });
  };

  return <div className="space-y-8 animate-in fade-in duration-500">
    <div><h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Scrape Jobs</h1><p className="text-muted-foreground mt-1 text-sm">Run controlled product-advertiser searches and monitor their qualification results.</p></div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-1"><Card><CardHeader><CardTitle className="text-lg">New Search</CardTitle></CardHeader><CardContent><form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2"><Label htmlFor="keyword">Product keyword</Label><Input id="keyword" placeholder="e.g. sunscreen" value={keyword} onChange={e => setKeyword(e.target.value)} /><div className="flex flex-wrap gap-1.5 pt-1">{EXAMPLE_KEYWORDS.map(example => <button key={example} type="button" onClick={() => setKeyword(example)} className="rounded-full border px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground">{example}</button>)}</div></div>
        <div className="space-y-2"><Label htmlFor="country">Target country</Label><Select value={country} onValueChange={setCountry}><SelectTrigger><SelectValue placeholder="Select country" /></SelectTrigger><SelectContent>{COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent></Select></div>
        <div className="space-y-2"><Label htmlFor="pageIds">Page IDs <span className="font-normal text-muted-foreground">(optional)</span></Label><Textarea id="pageIds" placeholder="Comma-separated IDs" value={pageIds} onChange={e => setPageIds(e.target.value)} className="min-h-[90px]" /></div>
        <Button type="submit" className="w-full" disabled={createJob.isPending}>{createJob.isPending ? "Starting..." : "Run Search"}</Button>
      </form></CardContent></Card></div>
      <div className="lg:col-span-2"><Card><CardContent className="p-0"><div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead className="bg-muted text-muted-foreground uppercase text-xs font-semibold"><tr><th className="px-4 py-3">Target</th><th className="px-4 py-3">Country</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Qualified</th><th className="px-4 py-3">Started</th></tr></thead><tbody className="divide-y">
        {isLoading ? <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">Loading jobs...</td></tr> : isError ? <tr><td colSpan={5} className="p-8 text-center text-destructive">Unable to load job history.</td></tr> : jobs?.length === 0 ? <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">No jobs yet. Run a controlled search to start building the sales-ready pool.</td></tr> : jobs?.map(job => <tr key={job.id} className="hover:bg-muted/30"><td className="px-4 py-3 font-medium">{job.keyword ? `"${job.keyword}"` : `${job.page_ids.length} pages`}</td><td className="px-4 py-3">{job.country}</td><td className="px-4 py-3"><StatusBadge status={job.status} /></td><td className="px-4 py-3">{job.result_count != null ? <span className="font-medium">{job.result_count}</span> : <span className="text-muted-foreground">—</span>}</td><td className="px-4 py-3 text-muted-foreground text-xs">{new Date(job.created_at).toLocaleString()}{job.error_message && <div className="text-red-500 mt-1 max-w-[220px] truncate" title={job.error_message}>{job.error_message}</div>}</td></tr>)}
      </tbody></table></div></CardContent></Card></div>
    </div>
  </div>;
}
