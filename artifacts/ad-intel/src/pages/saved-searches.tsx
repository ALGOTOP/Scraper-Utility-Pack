import { useState } from "react";
import { useListSavedSearches, useCreateSavedSearch, useDeleteSavedSearch, useCreateJob, getListSavedSearchesQueryKey, getListJobsQueryKey } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Play, Trash2, Search, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";

export function SavedSearches() {
  const { data: searches, isLoading } = useListSavedSearches();
  const createSearch = useCreateSavedSearch();
  const deleteSearch = useDeleteSavedSearch();
  const createJob = useCreateJob();
  
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [, setLocation] = useLocation();

  const [name, setName] = useState("");
  const [keyword, setKeyword] = useState("");
  const [countries, setCountries] = useState("US");
  const [pageIds, setPageIds] = useState("");

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    createSearch.mutate({
      data: {
        name,
        keyword: keyword.trim() || undefined,
        countries: countries.split(",").map(s => s.trim().toUpperCase()).filter(Boolean),
        page_ids: pageIds.split(",").map(s => s.trim()).filter(Boolean)
      }
    }, {
      onSuccess: () => {
        toast({ title: "Saved search created" });
        setName("");
        setKeyword("");
        setCountries("US");
        setPageIds("");
        queryClient.invalidateQueries({ queryKey: getListSavedSearchesQueryKey() });
      }
    });
  };

  const handleDelete = (id: number) => {
    deleteSearch.mutate({ id }, {
      onSuccess: () => {
        toast({ title: "Deleted successfully" });
        queryClient.invalidateQueries({ queryKey: getListSavedSearchesQueryKey() });
      }
    });
  };

  const handleRun = (search: any) => {
    if (!search.countries || search.countries.length === 0) return;
    
    // Create a job for the first country in the list (or multiple if backend supports it, but ScrapeJobInput takes a single country)
    // The spec says ScrapeJobInput.country: string. So we pick the first one.
    createJob.mutate({
      data: {
        keyword: search.keyword,
        page_ids: search.page_ids,
        country: search.countries[0]
      }
    }, {
      onSuccess: () => {
        toast({ title: "Job started", description: `Triggered via ${search.name}` });
        queryClient.invalidateQueries({ queryKey: getListJobsQueryKey() });
        setLocation("/jobs");
      }
    });
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Saved Searches</h1>
        <p className="text-muted-foreground mt-1 text-sm">Automate recurring queries by saving search configurations.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">New Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreate} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" required placeholder="e.g. Daily B2B SaaS" value={name} onChange={e => setName(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="keyword">Keyword</Label>
                  <Input id="keyword" placeholder="Search keyword" value={keyword} onChange={e => setKeyword(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="countries">Countries (Comma separated)</Label>
                  <Input id="countries" placeholder="US, GB, CA" value={countries} onChange={e => setCountries(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="pageIds">Page IDs (Comma separated)</Label>
                  <Textarea id="pageIds" placeholder="12345, 67890" value={pageIds} onChange={e => setPageIds(e.target.value)} />
                </div>
                <Button type="submit" className="w-full" disabled={createSearch.isPending}>
                  <Plus className="w-4 h-4 mr-2" /> Save Configuration
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        <div className="lg:col-span-2">
          {isLoading ? (
            <div className="p-8 text-center text-muted-foreground">Loading configs...</div>
          ) : searches?.length === 0 ? (
            <Card className="bg-muted/30 border-dashed">
              <CardContent className="flex flex-col items-center justify-center p-12 text-center">
                <Search className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
                <h3 className="font-medium mb-1">No saved searches</h3>
                <p className="text-sm text-muted-foreground">Create a configuration on the left to quickly trigger recurring jobs.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4">
              {searches?.map(search => (
                <Card key={search.id} className="overflow-hidden group">
                  <CardContent className="p-0">
                    <div className="flex flex-col sm:flex-row items-center justify-between p-5 gap-4">
                      <div className="space-y-1 flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold text-lg">{search.name}</h3>
                        </div>
                        <div className="text-sm text-muted-foreground flex flex-wrap gap-x-4 gap-y-1">
                          {search.keyword && <span>Keyword: <span className="font-medium text-foreground">{search.keyword}</span></span>}
                          {search.countries && search.countries.length > 0 && <span>Target: <span className="font-medium text-foreground">{search.countries.join(", ")}</span></span>}
                          {search.page_ids && search.page_ids.length > 0 && <span>Pages: <span className="font-medium text-foreground">{search.page_ids.length} specified</span></span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Button 
                          variant="outline" 
                          className="bg-primary/5 hover:bg-primary/10 text-primary border-primary/20"
                          onClick={() => handleRun(search)}
                          disabled={createJob.isPending}
                        >
                          <Play className="w-4 h-4 mr-2" /> Run Now
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          className="text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                          onClick={() => handleDelete(search.id)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
