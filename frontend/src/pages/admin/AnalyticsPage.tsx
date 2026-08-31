import { useQuery } from "@tanstack/react-query";
import { Briefcase, DollarSign, Inbox, Send, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { StatTile } from "@/components/admin/stat-tile";
import { PageSpinner } from "@/components/ui/spinner";
import { adminApi } from "@/lib/api";

function pct(value: number | null): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function AnalyticsPage() {
  const { data, isLoading } = useQuery({ queryKey: ["admin", "analytics"], queryFn: adminApi.analytics });

  if (isLoading || !data) return <PageSpinner />;

  return (
    <div>
      <PageHeader eyebrow="Ops" title="Analytics" description="Business and pipeline health, in one place." />

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatTile icon={Users} label="Users" value={data.users.total} sub={`${data.users.job_seekers} seekers, ${data.users.employers} employers`} />
        <StatTile icon={Briefcase} label="Active jobs" value={data.jobs.active} sub={`${data.jobs.aggregated} aggregated, ${data.jobs.featured} featured`} />
        <StatTile icon={Inbox} label="Applications" value={data.applications.total} />
        <StatTile
          icon={Send}
          label="Outreach sent"
          value={data.outreach.sent}
          sub={`${pct(data.outreach.success_rate)} of ${data.outreach.total} attempts`}
          tone={data.outreach.success_rate != null && data.outreach.success_rate > 0.7 ? "good" : "default"}
        />
        <StatTile
          icon={DollarSign}
          label="MRR estimate"
          value={`$${data.revenue.monthly_recurring_estimate_usd.toLocaleString()}`}
          sub={`${data.revenue.pro_subs} Pro, ${data.revenue.elite_subs} Elite`}
        />
        <StatTile
          icon={Briefcase}
          label="Ingestion health"
          value={pct(data.ingestion_health.success_rate)}
          sub={`last ${data.ingestion_health.recent_runs_checked} runs`}
          tone={
            data.ingestion_health.success_rate != null && data.ingestion_health.success_rate < 0.8 ? "danger" : "good"
          }
        />
      </div>
    </div>
  );
}
