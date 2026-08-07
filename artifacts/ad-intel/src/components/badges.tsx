import { cn } from "@/lib/utils";

export function ScoreBadge({ score, className }: { score: number | undefined | null, className?: string }) {
  if (score === undefined || score === null) return <span className="text-muted-foreground text-xs">—</span>;

  let colorClass = "";
  if (score <= 3) colorClass = "bg-[#fef2f2] text-[#e11d48] border-[#f43f5e]";
  else if (score <= 6) colorClass = "bg-[#fffbeb] text-[#f59e0b] border-[#fbbf24]";
  else if (score <= 8) colorClass = "bg-[#eff6ff] text-[#2563eb] border-[#3b82f6]";
  else colorClass = "bg-[#f0fdf4] text-[#16a34a] border-[#22c55e]";

  return (
    <span className={cn("inline-flex items-center justify-center px-2 py-0.5 text-xs font-bold rounded-sm border", colorClass, className)}>
      {score.toFixed(1)}
    </span>
  );
}

export function StatusBadge({ status, className }: { status: string, className?: string }) {
  let colorClass = "bg-muted text-muted-foreground border-transparent";
  
  if (status === 'running') colorClass = "bg-blue-50 text-blue-700 border-blue-200 animate-pulse";
  else if (status === 'done') colorClass = "bg-green-50 text-green-700 border-green-200";
  else if (status === 'failed') colorClass = "bg-red-50 text-red-700 border-red-200";
  else if (status === 'queued') colorClass = "bg-gray-100 text-gray-700 border-gray-200";
  
  if (status === 'approved') colorClass = "bg-green-50 text-green-700 border-green-200";
  if (status === 'rejected') colorClass = "bg-red-50 text-red-700 border-red-200";
  if (status === 'pending') colorClass = "bg-yellow-50 text-yellow-700 border-yellow-200";

  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-sm border capitalize", colorClass, className)}>
      {status}
    </span>
  );
}
