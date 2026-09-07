import { useState } from "react";
import { useListSavedSearches, useCreateSavedSearch, useDeleteSavedSearch, useCreateJob, getListSavedSearchesQueryKey, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Play, Trash2, Search, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";

export function SavedSearches() {
  const { data: searches, isLoading, isError } = useListSavedSearches();
  const createSearch = useCreateSavedSearch();
  const deleteSearch = useDeleteSavedSearch();
  const createJob = useCreateJob();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [, setLocation] = useLocation();
  const [name, setName] = useState(""); const [keyword, setKeyword] = useState(""); const [countries, setCountries] = useState("US"); const [pageIds, setPageIds] = useState("");

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { toast({ title: "Name required", variant: "destructive" }); return; }
    const targetCountries = countries.split(",").map(s => s.trim().toUpperCase()).filter(Boolean);
    if (!targetCountries.length) { toast({ title: "Country required", variant: "destructive" }); return; }
    createSearch.mutate({ data: { name: name.trim(), keyword: keyword.trim() || undefined, countries: targetCountries, page_ids: pageIds.split(",").map(s => s.trim()).filter(Boolean) } }, { onSuccess: () => { toast({ title: "Saved search created" }); setName(""); setKeyword(""); setCountries("US"); setPageIds(""); queryClient.invalidateQueries({ queryKey: getListSavedSearchesQueryKey() }); }, onError: (err) => toast({ title: "Could not save search", description: err?.data?.error ?? err?.message, variant: "destructive" }) });
  };

  const handleDelete = (id: number) => deleteSearch.mutate({ id }, { onSuccess: () => { toast({ title: "Saved search deleted" }); queryClient.invalidateQueries({ queryKey: getListSavedSearchesQueryKey() }); } });
  const handleRun = (search: any) => {
    const country = search.countries?.[0]; if (!country) return;
    createJob.mutate({ data: { keyword: search.keyword || undefined, page_ids: search.page_ids?.length ? search.page_ids : undefined, country } }, { onSuccess: () => { toast({ title: "Search queued", description: `Running ${search.name}` }); queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() }); setLocation("/jobs"); }, onError: (err) => toast({ title: "Could not start search", description: err?.data?.error ?? err?.message, variant: "destructive" }) });
  };

  return <div className="space-y-8 animate-in fade-in duration-500">
    <div><h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Saved Searches</h1><p className="text-muted-foreground mt-1 text-sm">Keep proven product-advertiser searches ready to run again.</p></div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-1"><Card><CardHeader><CardTitle className="text-lg">Save a Search</CardTitle></CardHeader><CardContent><form onSubmit={handleCreate} className="space-y-4">
        <div className="space-y-2"><Label htmlFor="name">Name</Label><Input id="name" required placeholder="e.g. US skincare advertisers" value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="keyword">Product keyword</Label><Input id="keyword" placeholder="e.g. sunscreen" value={keyword} onChange={e => setKeyword(e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="countries">Countries</Label><Input id="countries" placeholder="US, GB, CA" value={countries} onChange={e => setCountries(e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="pageIds">Page IDs <span className="font-normal text-muted-foreground">(optional)</span></Label><Textarea id="pageIds" placeholder="12345, 67890" value={pageIds} onChange={e => setPageIds(e.target.value)} /></div>
        <Button type="submit" className="w-full" disabled={createSearch.isPending}><Plus className="w-4 h-4 mr-2" />{createSearch.isPending ? "Saving..." : "Save Search"}</Button>
      </form></CardContent></Card></div>
      <div className="lg:col-span-2">{isLoading ? <div className="p-8 text-center text-muted-foreground">Loading saved searches...</div> : isError ? <Card><CardContent className="p-8 text-center text-destructive">Unable to load saved searches.</CardContent></Card> : searches?.length === 0 ? <Card className="bg-muted/30 border-dashed"><CardContent className="flex flex-col items-center justify-center p-12 text-center"><Search className="h-10 w-10 text-muted-foreground mb-4 opacity-50" /><h3 className="font-medium mb-1">No saved searches</h3><p className="text-sm text-muted-foreground">Save a product keyword and target country to quickly rerun a controlled search.</p></CardContent></Card> : <div className="grid gap-4">{searches?.map(search => <Card key={search.id} className="overflow-hidden"><CardContent className="p-0"><div className="flex flex-col sm:flex-row items-start sm:items-center justify-between p-5 gap-4"><div className="space-y-1 flex-1 min-w-0"><h3 className="font-semibold text-lg">{search.name}</h3><div className="text-sm text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">{search.keyword && <span>Keyword: <strong className="text-foreground">{search.keyword}</strong></span>}<span>Target: <strong className="text-foreground">{search.countries.join(", ")}</strong></span>{search.page_ids?.length ? <span>Pages: <strong className="text-foreground">{search.page_ids.length}</strong></span> : null}</div></div><div className="flex items-center gap-2 shrink-0"><Button variant="outline" onClick={() => handleRun(search)} disabled={createJob.isPending}><Play className="w-4 h-4 mr-2" /> Run Now</Button><Button variant="ghost" size="icon" className="text-muted-foreground hover:text-destructive" onClick={() => handleDelete(search.id)} disabled={deleteSearch.isPending}><Trash2 className="w-4 h-4" /></Button></div></div></CardContent></Card>)}</div>}</div>
    </div>
  </div>;
}
