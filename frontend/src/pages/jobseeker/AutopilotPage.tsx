import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Check, CircleSlash, Play, Radar, TriangleAlert } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { ChipGroup, RadioChips } from "@/components/ui/chip-group";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TagInput } from "@/components/ui/tag-input";
import { humanize } from "@/lib/labels";
import { autopilotApi, preferencesApi, whatsappApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import type {
  AutopilotAction,
  ExperienceLevel,
  JobLane,
  JobSource,
  JobType,
  PreferencesUpdate,
  WorkMode,
} from "@/lib/types";

const JOB_TYPE_LABEL: Record<JobType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
};

const WORK_MODE_LABEL: Record<WorkMode, string> = {
  remote: "Fully remote",
  hybrid: "Hybrid",
  onsite: "On site",
};

/* The currencies our sources actually quote in. A salary floor is compared to
   a listing character for character — there is no FX rate anywhere in this
   system — so offering a currency nothing is priced in would be a filter that
   silently matches nothing. */
const CURRENCIES = ["NGN", "USD", "GBP", "EUR", "CAD", "ZAR", "KES", "GHS", "AED", "INR"] as const;

const SOURCE_LABEL: Record<JobSource, string> = {
  alerts: "Job-alert emails",
  boards: "Global job boards",
};

const LEVEL_LABEL: Record<ExperienceLevel, string> = {
  entry: "Entry / graduate",
  mid: "Mid-level",
  senior: "Senior",
  lead: "Lead / principal",
  executive: "Executive",
};

const RECENCY_LABEL: Record<number, string> = {
  1: "Last 24 hours",
  3: "Last 3 days",
  7: "Last week",
  14: "Last 2 weeks",
  30: "Last month",
};

function Switch({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className="flex w-full items-start gap-3 rounded-xl border border-border bg-surface p-4 text-left transition-colors hover:border-border-strong"
    >
      <span
        className={cn(
          "mt-0.5 flex h-5 w-9 shrink-0 items-center rounded-full p-0.5 transition-colors",
          checked ? "bg-violet" : "bg-surface-3"
        )}
      >
        <span
          className={cn(
            "h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
            checked && "translate-x-4"
          )}
        />
      </span>
      <span className="min-w-0">
        <span className="block text-sm font-semibold text-ink">{label}</span>
        <span className="mt-0.5 block text-sm text-ink-muted">{description}</span>
      </span>
    </button>
  );
}

/**
 * The range has to be a prop, not a constant. Fit-score thresholds run 50-100
 * (the backend refuses anything lower), but the daily cap runs 1-25 — driving
 * both off one hardcoded range left the cap slider pinned at its minimum and
 * impossible to move.
 */
function RangeSlider({
  value,
  onChange,
  id,
  min,
  max,
  disabled = false,
}: {
  value: number;
  onChange: (v: number) => void;
  id: string;
  min: number;
  max: number;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1.5 flex-1 cursor-pointer appearance-none rounded-full bg-surface-3 accent-violet disabled:cursor-not-allowed disabled:opacity-50"
      />
      <span className="w-10 shrink-0 text-right font-mono text-sm font-bold tabular-nums text-ink">{value}</span>
    </div>
  );
}

const ACTION_ICON = { done: Check, skipped: CircleSlash, failed: TriangleAlert } as const;
const ACTION_TONE = { done: "text-good", skipped: "text-ink-faint", failed: "text-danger" } as const;

function ActionRow({ action }: { action: AutopilotAction }) {
  const Icon = ACTION_ICON[action.status];
  return (
    <li className="flex items-start gap-3 border-b border-border py-3 last:border-0">
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", ACTION_TONE[action.status])} strokeWidth={2} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={action.action === "apply" ? "accent" : "cyan"}>
            {action.action === "apply" ? "Applied" : "Outreach"}
          </Badge>
          {action.fit_score !== null && (
            <span className="font-mono text-xs tabular-nums text-ink-faint">fit {Math.round(action.fit_score)}</span>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-muted">{action.detail}</p>
      </div>
      <span className="shrink-0 whitespace-nowrap font-mono text-xs text-ink-faint">
        {formatDistanceToNow(new Date(action.created_at), { addSuffix: true })}
      </span>
    </li>
  );
}

export function AutopilotPage() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: prefs, isLoading } = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get });
  const { data: options } = useQuery({ queryKey: ["preference-options"], queryFn: preferencesApi.options });
  // A saved number is not the same as a reachable one: Meta drops our
  // template to anyone who has never messaged the business, and says nothing.
  const { data: whatsapp } = useQuery({
    queryKey: ["whatsapp", "connection"],
    queryFn: whatsappApi.connection,
    retry: false,
  });
  const { data: actions } = useQuery({ queryKey: ["autopilot", "actions"], queryFn: () => autopilotApi.actions() });

  /* Local mirror so sliders and chips stay responsive; saved explicitly rather
     than on every keystroke, because each save is a real write and a dragged
     slider would otherwise fire fifty of them. */
  const [draft, setDraft] = useState<PreferencesUpdate | null>(null);
  useEffect(() => {
    if (prefs === undefined || draft !== null) return;
    /* `remote_only` predates work modes and says the same thing less well: a
       boolean cannot express hybrid, which is the distinction that matters
       most to somebody who cannot commute. Anyone who had it switched on
       starts with the remote chip lit instead, and their first save retires
       the boolean. The feed's own per-visit Remote toggle is a query
       parameter and is untouched by this. */
    const retireRemoteOnly =
      prefs.remote_only && (prefs.work_modes ?? []).length === 0
        ? { work_modes: ["remote"] as WorkMode[], remote_only: false }
        : {};
    setDraft({ ...prefs, ...retireRemoteOnly });
  }, [prefs, draft]);

  const saveMutation = useMutation({
    mutationFn: (payload: PreferencesUpdate) => preferencesApi.update(payload),
    onSuccess: (saved) => {
      toast.success("Preferences saved");
      queryClient.setQueryData(["preferences"], saved);
      queryClient.invalidateQueries({ queryKey: ["jobs", "feed"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save"),
  });

  const runMutation = useMutation({
    mutationFn: autopilotApi.runNow,
    onSuccess: (summary) => {
      const total = summary.applied + summary.outreach;
      toast.success(
        total > 0
          ? `Autopilot did ${total} thing${total === 1 ? "" : "s"} — ${summary.applied} applied, ${summary.outreach} outreach`
          : summary.capped
            ? "Daily cap already reached — nothing more today"
            : "Nothing cleared your thresholds this time"
      );
      queryClient.invalidateQueries({ queryKey: ["autopilot", "actions"] });
      queryClient.invalidateQueries({ queryKey: ["jobs", "feed"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Autopilot run failed"),
  });

  if (isLoading || !draft) return <PageSpinner />;

  const set = (patch: PreferencesUpdate) => setDraft((d) => ({ ...d, ...patch }));
  const dirty = prefs ? JSON.stringify({ ...prefs, ...draft }) !== JSON.stringify(prefs) : false;

  return (
    <div>
      <PageHeader
        eyebrow="Preferences & autopilot"
        title="What we hunt, and how far you trust it"
        description="Your feed, your digest and autopilot all read these same settings."
        action={
          <Button size="sm" variant="outline" onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
            <Play className="h-3.5 w-3.5" />
            {runMutation.isPending ? "Running…" : "Run autopilot now"}
          </Button>
        }
      />

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>What to hunt for</CardTitle>
            <CardDescription>Leave a row empty to mean "show me everything".</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>The exact role</Label>
              <TagInput
                aria-label="Role titles"
                value={draft.title_keywords ?? []}
                onChange={(title_keywords) => set({ title_keywords })}
                placeholder="e.g. React developer — type and press Enter"
                max={10}
              />
              <p className="text-xs text-ink-faint">
                Matched against the job title. Job families below are broad on purpose —
                "engineering" covers QA, SRE and mobile alike — so this is how you say
                "React developer" and get only that.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Job families</Label>
              <ChipGroup
                aria-label="Job families"
                options={(options?.lanes ?? []).map((l) => ({ value: l, label: humanize(l) }))}
                value={draft.lanes ?? []}
                onChange={(v) => set({ lanes: v as JobLane[] })}
              />
            </div>
            <div className="space-y-2">
              <Label>Seniority</Label>
              <ChipGroup
                aria-label="Seniority"
                options={(options?.experience_levels ?? []).map((l) => ({
                  value: l,
                  label: LEVEL_LABEL[l] ?? humanize(l),
                }))}
                value={draft.experience_levels ?? []}
                onChange={(v) => set({ experience_levels: v as ExperienceLevel[] })}
              />
              <p className="text-xs text-ink-faint">
                Read from each listing's title, so it is as good as the title is — a role
                advertised with no level lands in mid.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Employment type</Label>
              <ChipGroup
                aria-label="Employment types"
                options={(options?.job_types ?? []).map((t) => ({ value: t, label: JOB_TYPE_LABEL[t] ?? humanize(t) }))}
                value={draft.job_types ?? []}
                onChange={(v) => set({ job_types: v as JobType[] })}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Where you can work</CardTitle>
            <CardDescription>
              Who may apply, not where the listing was posted. Pick Nigeria and you get
              roles open to applicants in Nigeria — remote roles anywhere that have not
              ruled Nigerians out, and onsite roles in Nigeria. A US-only role is excluded
              however remote it is.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label>Where listings come from</Label>
              <ChipGroup
                aria-label="Supply source"
                options={(options?.sources ?? []).map((kind) => ({
                  value: kind,
                  label: SOURCE_LABEL[kind] ?? humanize(kind),
                }))}
                value={draft.sources ?? []}
                onChange={(v) => set({ sources: v as JobSource[] })}
              />
              <p className="text-xs text-ink-faint">
                Empty means both. The global boards are remote-first and hire mostly out of
                the US and Europe; the alert emails are Indeed, LinkedIn, Jobberman and the
                rest for one country. If your market is thin on the boards, picking
                job-alert emails is the only thing that surfaces it — the other filters
                narrow a pool, they cannot reorder which pool you are looking at.
              </p>
            </div>

            <div className="space-y-2">
              <Label>You can apply from</Label>
              <ChipGroup
                aria-label="Where you can apply from"
                options={(options?.eligibility ?? []).map((place) => ({ value: place, label: place }))}
                value={draft.eligibility ?? []}
                onChange={(eligibility) => set({ eligibility })}
              />
              <p className="text-xs text-ink-faint">
                Pick more than one if you hold more than one right to work. Empty means
                every job in the pool, including ones you could not be hired for.
              </p>
            </div>

            <div className="space-y-2">
              <Label>How the work is done</Label>
              <ChipGroup
                aria-label="Work mode"
                options={(options?.work_modes ?? []).map((m) => ({
                  value: m,
                  label: WORK_MODE_LABEL[m] ?? humanize(m),
                }))}
                value={draft.work_modes ?? []}
                onChange={(v) => set({ work_modes: v as WorkMode[] })}
              />
              <p className="text-xs text-ink-faint">
                Hybrid is kept apart from remote on purpose: a listing that says both means
                two or three days in an office.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Markets</Label>
              <ChipGroup
                aria-label="Target markets"
                options={(options?.markets ?? []).map((m) => ({ value: m, label: m }))}
                value={draft.target_markets ?? []}
                onChange={(v) => set({ target_markets: v })}
                emptyHint="No markets are live yet — you're seeing every job we have."
              />
              <p className="text-xs text-ink-faint">
                Which of our job-alert mailboxes a listing arrived through. Most of the pool
                comes from global boards and belongs to no market, so this narrows the
                email-sourced supply only.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Cities</Label>
              <TagInput
                aria-label="Cities"
                value={draft.locations ?? []}
                onChange={(locations) => set({ locations })}
                placeholder="Type a city and press Enter"
              />
              <p className="text-xs text-ink-faint">
                Narrows within your markets. Remote roles always show regardless.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pay and freshness</CardTitle>
            <CardDescription>
              Most boards publish no salary at all, so a floor hides only the listings that
              name a figure and fall short — never the silent ones, and never one quoted in
              another currency, which we have no rate to convert.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="salary-floor">Minimum salary, per year</Label>
              <div className="flex gap-2">
                <Input
                  id="salary-floor"
                  type="number"
                  min={0}
                  step={1000}
                  inputMode="numeric"
                  placeholder="No minimum"
                  value={draft.salary_min_annual ?? ""}
                  onChange={(e) => {
                    const raw = e.target.value.trim();
                    set({ salary_min_annual: raw === "" ? null : Number(raw) });
                  }}
                  className="flex-1"
                />
                <Select
                  value={draft.salary_currency ?? undefined}
                  onValueChange={(code) => set({ salary_currency: code })}
                >
                  <SelectTrigger aria-label="Salary currency" className="w-28 shrink-0">
                    <SelectValue placeholder="Currency" />
                  </SelectTrigger>
                  <SelectContent>
                    {CURRENCIES.map((code) => (
                      <SelectItem key={code} value={code}>
                        {code}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {!!draft.salary_min_annual && !draft.salary_currency && (
                <p className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-warning">
                  Pick the currency too, or this is ignored — ₦8,000,000 and $8,000,000 are
                  not the same floor, and we won't guess which you meant.
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label>Posted within</Label>
              <RadioChips
                aria-label="How recently posted"
                options={[
                  { value: "any", label: "Any time" },
                  ...(options?.recency_choices ?? []).map((days) => ({
                    value: String(days),
                    label: RECENCY_LABEL[days] ?? `Last ${days} days`,
                  })),
                ]}
                value={draft.posted_within_days ? String(draft.posted_within_days) : "any"}
                onChange={(v) => set({ posted_within_days: v === "any" ? null : Number(v) })}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Daily digest</CardTitle>
            <CardDescription>Where the morning summary of your matches goes.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <RadioChips
              aria-label="Digest channel"
              options={[
                { value: "email", label: "Email" },
                { value: "whatsapp", label: "WhatsApp" },
                { value: "both", label: "Both" },
                { value: "none", label: "Don't send it" },
              ]}
              value={draft.digest_channel ?? "email"}
              onChange={(v) => set({ digest_channel: v as typeof draft.digest_channel })}
            />
            {(draft.digest_channel === "whatsapp" || draft.digest_channel === "both") &&
              whatsapp?.configured &&
              !whatsapp.opted_in && (
                <p className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-warning">
                  {whatsapp.number_on_file ? (
                    <>
                      Your number is saved, but WhatsApp will not deliver until you have
                      messaged us once — connect it on your{" "}
                      <Link to="/app/profile" className="underline">
                        profile
                      </Link>
                      .
                    </>
                  ) : (
                    <>
                      Add a WhatsApp number on your{" "}
                      <Link to="/app/profile" className="underline">
                        profile
                      </Link>{" "}
                      or nothing will be sent.
                    </>
                  )}
                </p>
              )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Autopilot</CardTitle>
            <CardDescription>
              Off by default. When on, it acts without asking — above the score you set, and never more than your
              daily cap.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-3">
              <Switch
                checked={draft.autopilot_apply_enabled ?? false}
                onChange={(v) => set({ autopilot_apply_enabled: v })}
                label="Auto-apply to jobs posted on JobQuick AI"
                description="Only jobs posted here — a listing on someone else's site is behind their form, so we can't submit it for you."
              />
              <div className="space-y-1.5 pl-3">
                <Label htmlFor="apply-threshold" className="text-xs text-ink-faint">
                  Minimum fit score to apply
                </Label>
                <RangeSlider
                  id="apply-threshold"
                  min={50}
                  max={100}
                  value={draft.autopilot_apply_threshold ?? 85}
                  onChange={(v) => set({ autopilot_apply_threshold: v })}
                  disabled={!draft.autopilot_apply_enabled}
                />
              </div>
            </div>

            <div className="space-y-3">
              <Switch
                checked={draft.autopilot_outreach_enabled ?? false}
                onChange={(v) => set({ autopilot_outreach_enabled: v })}
                label="Auto-reach out about jobs found elsewhere"
                description="Finds a hiring contact, drafts a pitch and sends it. Elite tier — spends credits per send."
              />
              <div className="space-y-1.5 pl-3">
                <Label htmlFor="outreach-threshold" className="text-xs text-ink-faint">
                  Minimum fit score to reach out
                </Label>
                <RangeSlider
                  id="outreach-threshold"
                  min={50}
                  max={100}
                  value={draft.autopilot_outreach_threshold ?? 90}
                  onChange={(v) => set({ autopilot_outreach_threshold: v })}
                  disabled={!draft.autopilot_outreach_enabled}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="daily-cap" className="text-xs text-ink-faint">
                Most actions per day
              </Label>
              <RangeSlider
                id="daily-cap"
                min={1}
                max={25}
                value={draft.autopilot_daily_cap ?? 5}
                onChange={(v) => set({ autopilot_daily_cap: v })}
              />
            </div>

            {user?.subscription_tier !== "elite" && draft.autopilot_outreach_enabled && (
              <p className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-warning">
                Auto-outreach needs the Elite plan. It'll stay switched on and start working the moment you upgrade.
              </p>
            )}
          </CardContent>
        </Card>

        <div className="flex items-center gap-3">
          <Button onClick={() => saveMutation.mutate(draft)} disabled={!dirty || saveMutation.isPending}>
            {saveMutation.isPending ? "Saving…" : "Save preferences"}
          </Button>
          {dirty && <span className="text-sm text-ink-faint">Unsaved changes</span>}
        </div>

        <Card>
          <CardHeader>
            <CardTitle>What autopilot has done</CardTitle>
            <CardDescription>
              Including the jobs it looked at and passed on, and why.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!actions || actions.length === 0 ? (
              <EmptyState
                icon={Radar}
                title="Nothing yet"
                description="Autopilot runs each morning after your matches are scored."
              />
            ) : (
              <ul>
                {actions.map((action) => (
                  <ActionRow key={action.id} action={action} />
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
