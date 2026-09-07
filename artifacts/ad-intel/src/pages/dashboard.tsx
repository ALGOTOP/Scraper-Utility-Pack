import { useGetDashboardStats, useGetRecentActivity } from "@workspace/api-client-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBadge, StatusBadge } from "@/components/badges";
import { Link } from "wouter";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowRight, Activity, Users, AlertCircle, Database, Sparkles } from "lucide-react";

export function Dashboard() {
  const { data: stats, isLoading: statsLoading, isError: statsError } = useGetDashboardStats();
  const { data: activity, isLoading: activityLoading, isError: activityError } = useGetRecentActivity();

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Sales Intelligence</h1>
            <span className="inline-flex items-center gap-1 rounded-full border bg-primary/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-primary"><Sparkles className="h-3 w-3" /> ICP v2</span>
          </div>
          <p className="text-muted-foreground mt-1 text-sm">Find active product advertisers with a credible reason to buy the $499 landing-page offer.</p>
        </div>
        <Link href="/jobs" className="text-sm font-medium text-primary hover:underline">Run a fresh search →</Link>
      </div>

      {statsError && <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">Unable to load dashboard metrics. Check that the API is healthy.</div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Sales-ready leads" value={stats?.total_leads} icon={Users} loading={statsLoading} />
        <StatCard title="Average score" value={stats?.avg_score?.toFixed(0)} icon={Activity} loading={statsLoading} />
        <StatCard title="Needs review" value={stats?.needs_review_count} icon={AlertCircle} loading={statsLoading} />
        <StatCard title="Running jobs" value={stats?.running_jobs} icon={Database} loading={statsLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2 border-b">
              <CardTitle className="text-base font-semibold">Top Sales-ready Prospects</CardTitle>
              <Link href="/leads" className="text-sm font-medium text-primary flex items-center gap-1 hover:underline">View all <ArrowRight className="h-4 w-4" /></Link>
            </CardHeader>
            <CardContent className="p-0">
              {activityLoading ? <div className="p-4 space-y-3"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div> : activityError ? <div className="p-8 text-center text-sm text-destructive">Unable to load recent prospects.</div> : (
                <div className="divide-y">
                  {activity?.top_leads?.map(lead => (
                    <Link key={lead.id} href={`/leads/${lead.id}`} className="flex items-center justify-between gap-4 p-4 hover:bg-muted/50 transition-colors">
                      <div className="min-w-0 flex flex-col gap-1">
                        <span className="font-medium text-sm truncate">{lead.advertiser_name || "Unknown Advertiser"}</span>
                        <span className="text-xs text-muted-foreground flex flex-wrap items-center gap-2">
                          <span className="uppercase">{lead.country}</span><span>•</span><span>{lead.product_identified ? "Product identified" : "Product unclear"}</span><span>•</span><span>{lead.destination_type?.replace(/_/g, " ") || "Unknown destination"}</span>
                        </span>
                      </div>
                      <ScoreBadge score={lead.score} />
                    </Link>
                  ))}
                  {activity?.top_leads?.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">No sales-ready prospects yet. Run a fresh scrape.</div>}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2 border-b">
              <CardTitle className="text-base font-semibold">Recent Jobs</CardTitle>
              <Link href="/jobs" className="text-sm font-medium text-primary flex items-center gap-1 hover:underline">View all <ArrowRight className="h-4 w-4" /></Link>
            </CardHeader>
            <CardContent className="p-0">
              {activityLoading ? <div className="p-4 space-y-3"><Skeleton className="h-10 w-full" /><Skeleton className="h-10 w-full" /></div> : (
                <div className="divide-y">
                  {activity?.recent_jobs?.map(job => (
                    <div key={job.id} className="flex items-center justify-between gap-4 p-4">
                      <div className="min-w-0 flex flex-col gap-1"><span className="font-medium text-sm truncate">{job.keyword ? `Search: "${job.keyword}"` : `Pages: ${job.page_ids?.length || 0}`}</span><span className="text-xs text-muted-foreground flex items-center gap-2"><span className="uppercase">{job.country}</span><span>•</span><span>{new Date(job.created_at).toLocaleString()}</span></span></div>
                      <div className="flex items-center gap-4 shrink-0">{job.result_count != null && <span className="text-xs text-muted-foreground">{job.result_count} sales-ready</span>}<StatusBadge status={job.status} /></div>
                    </div>
                  ))}
                  {activity?.recent_jobs?.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">No recent jobs.</div>}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card><CardHeader className="pb-2 border-b"><CardTitle className="text-base font-semibold">By Country</CardTitle></CardHeader><CardContent className="p-0">{statsLoading ? <div className="p-4 space-y-3"><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-full" /></div> : <div className="divide-y">{stats?.by_country?.map(c => <div key={c.country} className="flex items-center justify-between p-3 text-sm"><div className="flex items-center gap-2"><span className="font-medium">{c.country}</span><span className="text-muted-foreground">({c.count})</span></div><ScoreBadge score={c.avg_score} /></div>)}</div>}</CardContent></Card>
          <Card><CardHeader className="pb-2 border-b"><CardTitle className="text-base font-semibold">Score Distribution</CardTitle></CardHeader><CardContent className="p-0">{statsLoading ? <div className="p-4 space-y-3"><Skeleton className="h-6 w-full" /><Skeleton className="h-6 w-full" /></div> : <div className="divide-y">{stats?.by_score_bucket?.map(b => <div key={b.label} className="flex items-center justify-between p-3 text-sm"><span className="font-medium">{b.label}</span><span className="text-muted-foreground">{b.count} leads</span></div>)}</div>}</CardContent></Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, loading }: { title: string, value: React.ReactNode, icon: any, loading: boolean }) {
  return <Card><CardContent className="p-6 flex items-center justify-between"><div className="space-y-1"><p className="text-sm font-medium text-muted-foreground">{title}</p>{loading ? <Skeleton className="h-8 w-16" /> : <p className="text-2xl font-bold">{value ?? "—"}</p>}</div><div className="h-10 w-10 bg-muted/50 rounded-full flex items-center justify-center text-muted-foreground"><Icon className="h-5 w-5" /></div></CardContent></Card>;
}
