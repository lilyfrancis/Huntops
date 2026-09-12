import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Briefcase, Radio, Search, SlidersHorizontal, X } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { FeedCard } from "@/components/jobs/feed-card";
import { JobDetailDialog } from "@/components/jobs/job-detail-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { applicationsApi, jobsApi, outreachApi, preferencesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { humanize } from "@/lib/labels";
import type { Job } from "@/lib/types";

/** Delays a fast-changing value so it doesn't fire a request per keystroke. */
function useDebounced<T>(value: T, delayMs: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return settled;
}

export function JobFeedPage() {
  const queryClient = useQueryClient();
  const [ignorePreferences, setIgnorePreferences] = useState(false);
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [search, setSearch] = useState("");
  /* Debounced so typing doesn't fire a request per keystroke. */
  const debouncedSearch = useDebounced(search, 300);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const { data: prefs } = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get });
  const { data: feed, isLoading } = useQuery({
    queryKey: ["jobs", "feed", { ignorePreferences, remoteOnly, debouncedSearch }],
    queryFn: () =>
      jobsApi.feed({
        ignore_preferences: ignorePreferences || undefined,
        remote_only: remoteOnly || undefined,
        q: debouncedSearch.trim() || undefined,
        limit: 50,
      }),
    /* Keeps the previous list on screen while a new search resolves, instead
       of flashing the empty state between keystrokes. */
    placeholderData: (previous) => previous,
  });

  const refreshFeed = () => queryClient.invalidateQueries({ queryKey: ["jobs", "feed"] });

  const applyMutation = useMutation({
    mutationFn: (jobId: string) => applicationsApi.apply(jobId),
    onSuccess: () => {
      toast.success("Application submitted");
      refreshFeed();
      queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't apply"),
  });

  const outreachMutation = useMutation({
    mutationFn: (jobId: string) => outreachApi.create(jobId),
    onSuccess: (result) => {
      toast.success(
        result.status === "sent"
          ? "Contact found and your pitch was sent"
          : "Draft ready — no contact email found, so it wasn't sent"
      );
      refreshFeed();
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start outreach"),
  });

  const filterSummary = [
    ...(prefs?.target_markets ?? []),
    ...(prefs?.locations ?? []),
    ...(prefs?.lanes ?? []).map(humanize),
  ];
  const hasFilters = filterSummary.length > 0;

  return (
    <div>
      <PageHeader
        eyebrow="Your feed"
        title="Job feed"
        description="Drawn from the markets you picked — our alert mailboxes plus six live job-board sources."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link to="/app/autopilot">
              <SlidersHorizontal className="h-3.5 w-3.5" /> Preferences
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-56 flex-1 sm:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <Input
            aria-label="Search this feed"
            placeholder="Search title, company or location…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 pr-9"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-ink-faint transition-colors hover:bg-surface-2 hover:text-ink"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <Button
          variant={remoteOnly ? "solid" : "outline"}
          size="sm"
          onClick={() => setRemoteOnly((v) => !v)}
          aria-pressed={remoteOnly}
        >
          <Radio className="h-3.5 w-3.5" /> Remote only
        </Button>

        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIgnorePreferences((v) => !v)}
            aria-pressed={ignorePreferences}
          >
            {ignorePreferences ? "Back to my preferences" : "Show everything"}
          </Button>
        )}
      </div>

      <p className="mb-6 text-sm text-ink-muted">
        {hasFilters && !ignorePreferences ? (
          <>
            Showing <span className="font-semibold text-ink">{filterSummary.join(", ")}</span>
          </>
        ) : (
          "Showing everything in the pool"
        )}
        {/* Says these are temporary, so nobody goes hunting for where they
            were saved. */}
        {(remoteOnly || debouncedSearch.trim()) && " — narrowed for this visit only"}
      </p>

      {isLoading ? (
        <PageSpinner />
      ) : !feed || feed.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={
            debouncedSearch.trim() || remoteOnly
              ? "Nothing matches that here"
              : hasFilters
                ? "Nothing matches your preferences yet"
                : "No jobs in the pool yet"
          }
          description={
            debouncedSearch.trim() || remoteOnly
              ? "Clear the search or the remote filter to see the rest of your feed."
              : hasFilters
                ? "Widen your markets or job families, or check back after the next mailbox sync."
                : "New listings arrive each morning from the alert mailboxes and the aggregation run."
          }
          action={
            debouncedSearch.trim() || remoteOnly ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setSearch("");
                  setRemoteOnly(false);
                }}
              >
                Clear filters
              </Button>
            ) : hasFilters ? (
              <Button size="sm" variant="outline" onClick={() => setIgnorePreferences(true)}>
                Show everything
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {feed.map((item) => (
            <FeedCard
              key={item.job.id}
              item={item}
              onOpen={() => setSelectedJob(item.job)}
              onApply={() => applyMutation.mutate(item.job.id)}
              onOutreach={() => outreachMutation.mutate(item.job.id)}
              isApplying={applyMutation.isPending && applyMutation.variables === item.job.id}
              isDrafting={outreachMutation.isPending && outreachMutation.variables === item.job.id}
            />
          ))}
        </div>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
