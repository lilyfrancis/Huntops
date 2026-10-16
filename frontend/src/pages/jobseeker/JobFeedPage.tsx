import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Briefcase, ChevronLeft, ChevronRight, Radio, Search, SlidersHorizontal, X } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { FeedCard } from "@/components/jobs/feed-card";
import { JobDetailDialog } from "@/components/jobs/job-detail-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { applicationsApi, jobsApi, outreachApi, preferencesApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api-client";
import { humanize } from "@/lib/labels";
import type { Job } from "@/lib/types";

/* One screenful. Paging is offset-based over what is already in the pool, so
   a page costs one query and no AI call — which is why "next" can be a button
   rather than something that quietly spends credits. */
const PAGE_SIZE = 25;

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
  const [page, setPage] = useState(0);

  /* Any change to what is being asked for puts you back on page one. Without
     this, narrowing the search while three pages deep leaves you on a page
     that no longer exists and the feed reads as empty. */
  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, remoteOnly, ignorePreferences]);

  const { refreshUser } = useAuth();
  const { data: prefs } = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get });
  const { data: feed, isLoading, isFetching } = useQuery({
    queryKey: ["jobs", "feed", { ignorePreferences, remoteOnly, debouncedSearch, page }],
    queryFn: () =>
      jobsApi.feed({
        ignore_preferences: ignorePreferences || undefined,
        remote_only: remoteOnly || undefined,
        q: debouncedSearch.trim() || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    /* Keeps the previous list on screen while a new search resolves, instead
       of flashing the empty state between keystrokes. */
    placeholderData: (previous) => previous,
  });

  const refreshFeed = () => queryClient.invalidateQueries({ queryKey: ["jobs", "feed"] });

  // From the server, not hardcoded: the price of a look is a pricing
  // decision, and a stale number in the client is a promise broken at the
  // moment somebody clicks.
  const { data: allowance } = useQuery({
    queryKey: ["concierge", "allowance"],
    queryFn: applicationsApi.conciergeAllowance,
  });
  const unlockCost = allowance?.unlock_credit_cost ?? 5;

  const unlockMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.unlock(jobId),
    onSuccess: () => {
      refreshFeed();
      // Credits live on the auth user, not in a query — spending them
      // without this leaves a stale balance in the sidebar.
      void refreshUser();
      queryClient.invalidateQueries({ queryKey: ["concierge", "allowance"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't unlock"),
  });

  const applyMutation = useMutation({
    mutationFn: (jobId: string) => applicationsApi.apply(jobId),
    onSuccess: (application) => {
      toast.success(
        application.is_concierge
          ? "Queued — we'll file this for you and the status will change to filed"
          : "Application sent"
      );
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
    ...(prefs?.title_keywords ?? []),
    ...(prefs?.lanes ?? []).map(humanize),
    ...(prefs?.experience_levels ?? []).map(humanize),
    ...(prefs?.sources ?? []).map(humanize),
    ...(prefs?.eligibility ?? []),
    ...(prefs?.work_modes ?? []),
    ...(prefs?.target_markets ?? []),
    ...(prefs?.locations ?? []),
  ];
  const hasFilters = filterSummary.length > 0;
  /* Distinct from hasFilters: somebody can have picked a market and still
     have neither a field nor a right to work chosen, which is the case that
     floods the feed. Eligibility is named here because it is the filter that
     decides whether a listing is applicable at all — the rest only decide
     whether it is interesting. */
  const unset = [
    ...((prefs?.lanes ?? []).length === 0 ? ["which field you work in"] : []),
    ...((prefs?.eligibility ?? []).length === 0 ? ["where you can apply from"] : []),
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Your feed"
        title="Job feed"
        description="Drawn from the markets you picked "
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

      <p className="mb-4 text-sm text-ink-muted">
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

      {/* An empty preference set means "show me everything", and the feed
          looked identical to one somebody had deliberately set that way.
          Backend and React roles arriving for a marketing candidate reads as
          the matching being broken, when nothing has been asked of it — and
          every one of those is scored at our expense. */}
      {unset.length === 0 ? null : (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3">
          <p className="text-sm text-warning">
            <strong className="font-semibold">You have not told us {unset.join(" or ")}</strong>,
            so this shows every role we have — including ones in fields you don't work in and
            ones you could not be hired for.
          </p>
          <Button size="sm" asChild>
            <Link to="/app/autopilot">Set your preferences</Link>
          </Button>
        </div>
      )}

      {isLoading ? (
        <PageSpinner />
      ) : page > 0 && (!feed || feed.length === 0) ? (
        /* Reached by clicking Next once too often. "Nothing matches your
           preferences" would be a lie here — plenty matched, on the pages
           behind you. */
        <EmptyState
          icon={Briefcase}
          title="That's the end of your feed"
          description="New listings arrive each morning from the alert mailboxes and the aggregation run."
          action={
            <Button size="sm" variant="outline" onClick={() => setPage((p) => Math.max(0, p - 1))}>
              <ChevronLeft className="h-3.5 w-3.5" /> Back a page
            </Button>
          }
        />
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
        <>
          <div className="space-y-3">
            {feed.map((item) => (
              <FeedCard
                key={item.job.id}
                item={item}
                onOpen={() => setSelectedJob(item.job)}
                onApply={() => applyMutation.mutate(item.job.id)}
                onUnlock={() => unlockMutation.mutate(item.job.id)}
                isUnlocking={unlockMutation.isPending && unlockMutation.variables === item.job.id}
                unlockCost={unlockCost}
                onOutreach={() => outreachMutation.mutate(item.job.id)}
                isApplying={applyMutation.isPending && applyMutation.variables === item.job.id}
                isDrafting={outreachMutation.isPending && outreachMutation.variables === item.job.id}
              />
            ))}
          </div>

          {/* A full page is the only evidence there is more; the feed returns
              rows, not a count, and counting the whole pool on every request
              to render one greyed-out button is not worth the query. The last
              page therefore ends by the button going quiet rather than by an
              announcement. */}
          {(page > 0 || feed.length === PAGE_SIZE) && (
            <div className="mt-6 flex items-center justify-between gap-3 border-t border-border pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || isFetching}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </Button>
              <span className="font-mono text-xs tabular-nums text-ink-faint">Page {page + 1}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={feed.length < PAGE_SIZE || isFetching}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
