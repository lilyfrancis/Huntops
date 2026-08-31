import { useQuery } from "@tanstack/react-query";
import { Flame, Inbox, MessageSquare, Send, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageSpinner } from "@/components/ui/spinner";
import { FunnelChart } from "@/components/stats/funnel-chart";
import { ActivityHeatmap } from "@/components/stats/activity-heatmap";
import { statsApi } from "@/lib/api";

function Total({ icon: Icon, label, value }: { icon: typeof Inbox; label: string; value: number }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5 text-ink-faint">
        <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
        <span className="font-mono text-[0.7rem] uppercase tracking-wide">{label}</span>
      </div>
      {/* Proportional figures: these are standalone values, not a column. */}
      <p className="mt-1 font-display text-3xl text-ink">{value}</p>
    </Card>
  );
}

function percent(rate: number | null) {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

export function MomentumPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["stats", "me"],
    queryFn: statsApi.me,
  });

  if (isLoading || !stats) return <PageSpinner />;

  const { streak, totals, funnel, conversion, activity } = stats;

  return (
    <div>
      <PageHeader
        eyebrow="Momentum"
        title="Your hunt"
        description="What you've actually done, and what it's converting into."
      />

      <div className="mb-6 grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_2fr]">
        {/* The one hero figure on this view. */}
        <Card className="p-6">
          <div className="flex items-center gap-1.5 text-accent">
            <Flame className="h-4 w-4" strokeWidth={1.75} />
            <span className="font-mono text-[0.7rem] uppercase tracking-wide">Current streak</span>
          </div>
          <p className="mt-2 font-display text-6xl leading-none text-ink">
            {streak.current_days}
            <span className="ml-2 font-sans text-base font-normal text-ink-muted">
              {streak.current_days === 1 ? "day" : "days"}
            </span>
          </p>
          <p className="mt-3 text-sm text-ink-muted">
            Longest run {streak.longest_days} {streak.longest_days === 1 ? "day" : "days"} ·{" "}
            {streak.active_days_in_window} active in the last {streak.window_days}
          </p>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityHeatmap days={activity} />
          </CardContent>
        </Card>
      </div>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Total icon={Sparkles} label="Matches scored" value={totals.matches_scored} />
        <Total icon={Inbox} label="Applications" value={totals.applications} />
        <Total icon={Send} label="Outreach sent" value={totals.outreach_sent} />
        <Total icon={MessageSquare} label="Interviews done" value={totals.interviews_completed} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Application funnel</CardTitle>
          <p className="text-sm text-ink-muted">
            Each stage counts every application that reached it — an offer counts as reviewed
            and interviewed too. The right-hand figure is the pass-through from the stage above.
          </p>
        </CardHeader>
        <CardContent className="space-y-6">
          <FunnelChart stages={funnel} />

          <div className="flex flex-wrap gap-x-10 gap-y-3 border-t border-border pt-4">
            <div>
              <p className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
                Applied → interviewing
              </p>
              <p className="mt-0.5 font-display text-2xl text-ink">
                {percent(conversion.applied_to_interviewing)}
              </p>
            </div>
            <div>
              <p className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
                Applied → offered
              </p>
              <p className="mt-0.5 font-display text-2xl text-ink">
                {percent(conversion.applied_to_offered)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
