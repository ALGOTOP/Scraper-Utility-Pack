import { LeadsTable } from "@/components/leads-table";

export function Review() {
  return (
    <LeadsTable 
      title="Needs Review"
      description="These leads were flagged by the engine as borderline or high-value and require manual approval."
      baseFilters={{ needs_review: true, review_status: 'pending' }}
      showReviewActions={true}
    />
  );
}
