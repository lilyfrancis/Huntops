import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Copy, Handshake, Scale } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { BenchmarkStrip, NoBenchmarkNotice } from "@/components/negotiation/benchmark-strip";
import { negotiationApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { NegotiationReview } from "@/lib/types";
import { useAuth } from "@/hooks/use-auth";

const CONFIDENCE_TONE = { high: "good", medium: "warning", low: "danger" } as const;

function ReviewResult({ review }: { review: NegotiationReview }) {
  const copyScript = async () => {
    try {
      await navigator.clipboard.writeText(review.counter_script);
      toast.success("Counter script copied");
    } catch {
      toast.error("Couldn't copy — select the text and copy manually");
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Badge tone={CONFIDENCE_TONE[review.confidence]}>{review.confidence} confidence</Badge>
          {review.benchmark ? (
            <Badge tone="cyan">n={review.benchmark.sample_size}</Badge>
          ) : (
            <Badge tone="warning">no market data</Badge>
          )}
        </div>
        <CardTitle className="mt-2">{review.role_title}</CardTitle>
        <p className="text-sm text-ink-muted">
          {review.currency} {review.base_salary.toLocaleString()} · {review.location}
          {review.company_name ? ` · ${review.company_name}` : ""}
        </p>
      </CardHeader>

      <CardContent className="space-y-6">
        {review.benchmark ? (
          <BenchmarkStrip data={review.benchmark} base={review.base_salary} />
        ) : (
          <NoBenchmarkNotice currency={review.currency} />
        )}

        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-accent">Verdict</p>
          <p className="mt-1.5 text-sm text-ink-muted">{review.verdict}</p>
        </div>

        {review.levers.length > 0 && (
          <div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-accent">
              What to push on
            </p>
            <ul className="mt-2 space-y-2">
              {review.levers.map((lever) => (
                <li key={lever.lever} className="text-sm">
                  <span className="text-ink">{lever.lever}</span>
                  <span className="text-ink-muted"> — {lever.rationale}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="rounded-lg border border-border bg-surface-2 p-4">
          <div className="mb-2 flex items-center justify-between">
            <p className="font-mono text-[11px] uppercase tracking-widest text-cyan">
              Your counter script
            </p>
            <Button variant="ghost" size="sm" onClick={copyScript}>
              <Copy className="h-3.5 w-3.5" /> Copy
            </Button>
          </div>
          <p className="whitespace-pre-wrap text-sm text-ink-muted">{review.counter_script}</p>
        </div>

        <div>
          <p className="font-mono text-[11px] uppercase tracking-widest text-accent">If they say no</p>
          <p className="mt-1.5 text-sm text-ink-muted">{review.if_they_say_no}</p>
        </div>

        {review.watch_outs.length > 0 && (
          <div>
            <p className="font-mono text-[11px] uppercase tracking-widest text-warning">Watch out</p>
            <ul className="mt-2 space-y-1">
              {review.watch_outs.map((item) => (
                <li key={item} className="text-sm text-ink-muted">
                  — {item}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function NegotiationPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    role_title: "",
    company_name: "",
    location: "",
    currency: "USD",
    base_salary: "",
    equity: "",
    other_terms: "",
    has_competing_offer: false,
  });
  const [active, setActive] = useState<NegotiationReview | null>(null);

  const { data: reviews } = useQuery({ queryKey: ["negotiation", "mine"], queryFn: negotiationApi.mine });
  const { data: coverage } = useQuery({
    queryKey: ["negotiation", "coverage"],
    queryFn: negotiationApi.coverage,
  });

  const reviewMutation = useMutation({
    mutationFn: () =>
      negotiationApi.review({
        role_title: form.role_title.trim(),
        company_name: form.company_name.trim() || undefined,
        location: form.location.trim(),
        currency: form.currency.trim().toUpperCase(),
        base_salary: Number(form.base_salary),
        equity: form.equity.trim() || undefined,
        other_terms: form.other_terms.trim() || undefined,
        has_competing_offer: form.has_competing_offer,
      }),
    onSuccess: (review) => {
      setActive(review);
      queryClient.invalidateQueries({ queryKey: ["negotiation", "mine"] });
      void refreshUser();
      toast.success(review.benchmark ? "Coached against real listings" : "Coached — no market data for this currency");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't review that offer"),
  });

  const isFree = user?.subscription_tier === "free";
  const ready = form.role_title.trim() && form.location.trim() && Number(form.base_salary) > 0;
  const coveredCurrencies = (coverage ?? []).filter((row) => row.listings >= 10);

  return (
    <div>
      <PageHeader
        eyebrow="Offer"
        title="Negotiation coach"
        description="Where your offer sits against real listings, and exactly what to say next."
      />

      {active && (
        <div className="mb-8">
          <ReviewResult review={active} />
          <Button variant="ghost" size="sm" className="mt-3" onClick={() => setActive(null)}>
            Review another offer
          </Button>
        </div>
      )}

      {!active && (
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-accent" /> Your offer
            </CardTitle>
            {coveredCurrencies.length > 0 && (
              <p className="text-sm text-ink-muted">
                We currently hold enough listings to benchmark:{" "}
                {coveredCurrencies.map((row) => row.currency).join(", ")}. Other currencies get
                tactics-only coaching.
              </p>
            )}
          </CardHeader>
          <CardContent>
            {isFree ? (
              <p className="text-sm text-ink-muted">
                The negotiation coach is available on Pro and Elite.
              </p>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-1.5">
                    <Label htmlFor="role_title">Role</Label>
                    <Input
                      id="role_title"
                      value={form.role_title}
                      onChange={(e) => setForm({ ...form, role_title: e.target.value })}
                      placeholder="Senior RevOps Manager"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="company_name">Company (optional)</Label>
                    <Input
                      id="company_name"
                      value={form.company_name}
                      onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="location">Location / market</Label>
                    <Input
                      id="location"
                      value={form.location}
                      onChange={(e) => setForm({ ...form, location: e.target.value })}
                      placeholder="Remote, or Lagos, Nigeria"
                    />
                  </div>
                  <div className="grid grid-cols-[6rem_1fr] gap-3">
                    <div className="space-y-1.5">
                      <Label htmlFor="currency">Currency</Label>
                      <Input
                        id="currency"
                        maxLength={3}
                        value={form.currency}
                        onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="base_salary">Base offered (annual)</Label>
                      <Input
                        id="base_salary"
                        type="number"
                        value={form.base_salary}
                        onChange={(e) => setForm({ ...form, base_salary: e.target.value })}
                        placeholder="110000"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="equity">Equity or bonus (optional)</Label>
                  <Input
                    id="equity"
                    value={form.equity}
                    onChange={(e) => setForm({ ...form, equity: e.target.value })}
                    placeholder="0.15% over 4 years, 1 year cliff"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="other_terms">Anything else that matters (optional)</Label>
                  <Textarea
                    id="other_terms"
                    rows={3}
                    value={form.other_terms}
                    onChange={(e) => setForm({ ...form, other_terms: e.target.value })}
                    placeholder="Start date is flexible; they want an answer by Friday."
                  />
                </div>

                <label className="flex items-center gap-2 text-sm text-ink-muted">
                  <input
                    type="checkbox"
                    checked={form.has_competing_offer}
                    onChange={(e) => setForm({ ...form, has_competing_offer: e.target.checked })}
                    className="h-4 w-4 accent-[var(--color-accent)]"
                  />
                  I have a competing offer
                </label>

                <Button onClick={() => reviewMutation.mutate()} disabled={!ready || reviewMutation.isPending}>
                  <Handshake className="h-3.5 w-3.5" />
                  {reviewMutation.isPending ? "Working through it…" : "Coach this offer"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {reviews && reviews.length > 0 ? (
        <div className="space-y-3">
          <p className="eyebrow">Past offers</p>
          {reviews.map((review) => (
            <Card
              key={review.id}
              role="button"
              onClick={() => setActive(review)}
              className="cursor-pointer p-4 transition-colors hover:border-border-strong"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-ink">{review.role_title}</p>
                  <p className="text-sm text-ink-muted">
                    {review.currency} {review.base_salary.toLocaleString()}
                    {review.benchmark ? ` · median ${review.benchmark.median.toLocaleString()}` : " · no market data"}
                  </p>
                </div>
                <span className="shrink-0 font-mono text-xs text-ink-faint">
                  {formatDistanceToNow(new Date(review.created_at), { addSuffix: true })}
                </span>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        !active && (
          <EmptyState
            icon={Handshake}
            title="No offers reviewed yet"
            description="Paste an offer above and you'll get a benchmark, a strategy, and a script you can send."
          />
        )
      )}
    </div>
  );
}
