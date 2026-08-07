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

export function Jobs() {
  const { data: jobs, isLoading } = useListJobs(undefined, { query: { refetchInterval: 5000 } });
  const [keyword, setKeyword] = useState("");
  const [country, setCountry] = useState("US");
  const [pageIds, setPageIds] = useState("");
  
  const createJob = useCreateJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!keyword.trim() && !pageIds.trim()) {
      toast({ title: "Error", description: "Provide a keyword or page IDs", variant: "destructive" });
      return;
    }

    const ids = pageIds.split(",").map(s => s.trim()).filter(Boolean);

    createJob.mutate({
      data: {
        keyword: keyword.trim() || undefined,
        country,
        page_ids: ids.length > 0 ? ids : undefined
      }
    }, {
      onSuccess: () => {
        toast({ title: "Job started", description: "Scrape job queued successfully." });
        setKeyword("");
        setPageIds("");
        queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() });
      },
      onError: (err) => {
        toast({ title: "Failed to start job", description: err?.data?.error ?? err?.message ?? "Unknown error", variant: "destructive" });
      }
    });
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Scrape Jobs</h1>
        <p className="text-muted-foreground mt-1 text-sm">Trigger new scraping operations and monitor active runs.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">New Job</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="keyword">Search Keyword</Label>
                  <Input 
                    id="keyword" 
                    placeholder="e.g. CRM software" 
                    value={keyword} 
                    onChange={e => setKeyword(e.target.value)} 
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Target Country</Label>
                  <Select value={country} onValueChange={setCountry}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select country" />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pageIds">Page IDs (Optional)</Label>
                  <Textarea 
                    id="pageIds" 
                    placeholder="Comma-separated IDs" 
                    value={pageIds} 
                    onChange={e => setPageIds(e.target.value)} 
                    className="min-h-[100px]"
                  />
                </div>
                <Button type="submit" className="w-full" disabled={createJob.isPending}>
                  {createJob.isPending ? "Starting..." : "Run Job"}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                  <thead className="bg-muted text-muted-foreground uppercase text-xs font-semibold">
                    <tr>
                      <th className="px-4 py-3">Target</th>
                      <th className="px-4 py-3">Country</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Result</th>
                      <th className="px-4 py-3">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {isLoading ? (
                      <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">Loading...</td></tr>
                    ) : jobs?.length === 0 ? (
                      <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">No jobs history.</td></tr>
                    ) : (
                      jobs?.map(job => (
                        <tr key={job.id} className="hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">
                            {job.keyword ? `"${job.keyword}"` : `${job.page_ids.length} pages`}
                          </td>
                          <td className="px-4 py-3">{job.country}</td>
                          <td className="px-4 py-3">
                            <StatusBadge status={job.status} />
                          </td>
                          <td className="px-4 py-3">
                            {job.result_count != null ? (
                              <span className="font-medium text-foreground">{job.result_count} leads</span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {new Date(job.created_at).toLocaleString()}
                            {job.error_message && (
                              <div className="text-red-500 text-xs mt-1 max-w-[200px] truncate" title={job.error_message}>
                                {job.error_message}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
