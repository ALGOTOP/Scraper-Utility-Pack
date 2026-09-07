import { cn } from "@/lib/utils";

export function ScoreBadge({ score, className }: { score: number | undefined | null, className?: string }) {
  if (score === undefined || score === null) return <span className="text-muted-foreground text-xs">—</span>;

  const normalized = Math.max(0, Math.min(100, score));
  let colorClass = "bg-red-50 text-red-700 border-red-200";
  if (normalized >= 90) colorClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
  else if (normalized >= 80) colorClass = "bg-green-50 text-green-700 border-green-200";
  else if (normalized >= 70) colorClass = "bg-blue-50 text-blue-700 border-blue-200";
  else if (normalized >= 50) colorClass = "bg-amber-50 text-amber-700 border-amber-200";

  return (
    <span className={cn("inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold rounded-sm border", colorClass, className)}>
      {Math.round(normalized)}
    </span>
  );
}

export function StatusBadge({ status, className }: { status: string, className?: string }) {
  let colorClass = "bg-muted text-muted-foreground border-transparent";

  if (status === 'running') colorClass = "bg-blue-50 text-blue-700 border-blue-200 animate-pulse";
  else if (status === 'done') colorClass = "bg-green-50 text-green-700 border-green-200";
  else if (status === 'failed') colorClass = "bg-red-50 text-red-700 border-red-200";
  else if (status === 'queued') colorClass = "bg-gray-100 text-gray-700 border-gray-200";
  else if (status === 'approved') colorClass = "bg-green-50 text-green-700 border-green-200";
  else if (status === 'rejected') colorClass = "bg-red-50 text-red-700 border-red-200";
  else if (status === 'pending') colorClass = "bg-yellow-50 text-yellow-700 border-yellow-200";

  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border capitalize", colorClass, className)}>
      {status}
    </span>
  );
}
