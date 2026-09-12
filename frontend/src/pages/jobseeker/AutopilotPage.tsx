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
import { ChipGroup } from "@/components/ui/chip-group";
import { TagInput } from "@/components/ui/tag-input";
import { humanize } from "@/lib/labels";
import { autopilotApi, preferencesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import type { AutopilotAction, JobLane, JobType, PreferencesUpdate } from "@/lib/types";

const JOB_TYPE_LABEL: Record<JobType, string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
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
  const { data: actions } = useQuery({ queryKey: ["autopilot", "actions"], queryFn: () => autopilotApi.actions() });

  /* Local mirror so sliders and chips stay responsive; saved explicitly rather
     than on every keystroke, because each save is a real write and a dragged
     slider would otherwise fire fifty of them. */
  const [draft, setDraft] = useState<PreferencesUpdate | null>(null);
  useEffect(() => {
    if (prefs && draft === null) setDraft({ ...prefs });
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
              <Label>Markets</Label>
              <ChipGroup
                aria-label="Target markets"
                options={(options?.markets ?? []).map((m) => ({ value: m, label: m }))}
                value={draft.target_markets ?? []}
                onChange={(v) => set({ target_markets: v })}
                emptyHint="No markets are live yet — you're seeing every job we have."
              />
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
              <Label>Employment type</Label>
              <ChipGroup
                aria-label="Employment types"
                options={(options?.job_types ?? []).map((t) => ({ value: t, label: JOB_TYPE_LABEL[t] ?? humanize(t) }))}
                value={draft.job_types ?? []}
                onChange={(v) => set({ job_types: v as JobType[] })}
              />
            </div>
            <div className="space-y-2">
              <Label>Where to send your daily digest</Label>
              <ChipGroup
                aria-label="Digest channel"
                options={[
                  { value: "email", label: "Email" },
                  { value: "whatsapp", label: "WhatsApp" },
                  { value: "both", label: "Both" },
                  { value: "none", label: "Don't send it" },
                ]}
                /* Single-select dressed as chips: ChipGroup toggles, so the
                   last click wins and an empty click keeps the current value —
                   a channel of "nothing" is spelled "Don't send it", not
                   reached by deselecting. */
                value={[draft.digest_channel ?? "email"]}
                onChange={(next) => {
                  const picked = next.find((v) => v !== (draft.digest_channel ?? "email"));
                  if (picked) set({ digest_channel: picked as typeof draft.digest_channel });
                }}
              />
              {(draft.digest_channel === "whatsapp" || draft.digest_channel === "both") &&
                !user?.whatsapp_number && (
                  <p className="rounded-lg border border-warning/30 bg-warning-soft px-3 py-2 text-sm text-warning">
                    Add a WhatsApp number on your{" "}
                    <Link to="/app/profile" className="underline">
                      profile
                    </Link>{" "}
                    or nothing will be sent.
                  </p>
                )}
            </div>

            <Switch
              checked={draft.remote_only ?? false}
              onChange={(v) => set({ remote_only: v })}
              label="Remote only"
              description="Hide anything that isn't explicitly remote."
            />
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
                label="Auto-apply to jobs posted on HuntOps"
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
