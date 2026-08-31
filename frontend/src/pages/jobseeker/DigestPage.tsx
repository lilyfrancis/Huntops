import { useQuery } from "@tanstack/react-query";
import { Newspaper } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { digestApi } from "@/lib/api";

export function DigestPage() {
  const { data, isLoading } = useQuery({ queryKey: ["digest", "preview"], queryFn: digestApi.preview });

  return (
    <div>
      <PageHeader
        eyebrow="Sent daily at 07:30 UTC"
        title="Digest"
        description='Renders from your latest scored matches — refresh matches first if this looks stale.'
      />

      {isLoading ? (
        <PageSpinner />
      ) : !data || data.entries.length === 0 ? (
        <EmptyState
          icon={Newspaper}
          title="Nothing to show yet"
          description="Score some matches first — the digest reads from whatever's already been scored, it doesn't call the AI itself."
        />
      ) : (
        <div className="space-y-3">
          <p className="font-mono text-xs uppercase tracking-wide text-ink-faint">{data.subject}</p>
          {data.entries.map((entry) => (
            <Card key={entry.job_id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{entry.title}</p>
                <p className="text-xs text-ink-muted">
                  {entry.company_name ?? "Company withheld"} — {entry.location}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {entry.geo_boost_applied && <Badge tone="good">Home market</Badge>}
                <span className="font-mono text-sm text-accent-strong">{Math.round(entry.fit_score)}</span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
